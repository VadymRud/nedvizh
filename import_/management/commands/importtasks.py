# coding: utf-8

from django.core.management.base import BaseCommand

from agency.models import Agency
from import_.models import ImportTask
from import_.tasks import perform_importtask

import datetime

class Command(BaseCommand):
    help = u'Команда для работы с задачами импорта'

    def add_arguments(self, parser):
        parser.add_argument('action', type=str, choices=['create', 'complete', 'cleanup'])
        parser.add_argument('agency_id', nargs='*', type=int)

    def handle(self, *args, **options):
        print datetime.datetime.now()
        if options['action'] == 'create':
            incompleted_importtasks = ImportTask.objects.exclude(is_test=False).exclude(status='completed')
            agencies_queryset = Agency.objects.filter(import_url__gt='').exclude(importtasks__in=incompleted_importtasks)

            if options['agency_id']:
                agencies_queryset = agencies_queryset.filter(id__in=options['agency_id'])

            for agency in agencies_queryset:
                importtask = ImportTask(agency=agency, url=agency.import_url)
                importtask.save()
                perform_importtask(importtask.id)

        elif options['action'] == 'complete':
            importtasks_to_complete = ImportTask.get_queryset_to_complete()

            if options['agency_id']:
                importtasks_to_complete = importtasks_to_complete.filter(agency__in=options['agency_id'])

            for importtask in importtasks_to_complete:
                importtask.complete()

        elif options['action'] == 'cleanup':
            week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
            to_delete = ImportTask.objects.filter(is_test=False, status='completed', completed__lt=week_ago)

            if options['agency_id']:
                to_delete = to_delete.filter(agency__in=options['agency_id'])

            to_delete.delete()

            # отключение импорта для агентств, у которых было три последних запуска импорта с ошибкой
            for agency in Agency.objects.filter(import_url__gt=''):
                importtasks = agency.importtasks.order_by('-completed')[:3]
                if len(importtasks) == 3 and all([task.error for task in importtasks]):
                    agency.import_url = None
                    agency.save()
                    print 'agency #%d: import has been disabled' % agency.id

