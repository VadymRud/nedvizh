from django.core.management.base import BaseCommand
from django.conf import settings
import time, datetime, re


class Command(BaseCommand):
    help = 'deleted old feed properties'

    def handle(self, *args, **options):
        from ad.models import Ad

        try:
            days = int(args[0])
        except:
            days = 7

        def delete_cycle(objects):
            count = objects.count()
            print '%s found.' % count
            key = 0
            for object in objects:
                object.delete()
                print '%s of %s deleted' % (key, count)
                key+=1
            print 'All of these deleted'

        if days>=1000:
            old_properties = Ad.objects.filter(user__isnull=True).order_by('id')[:days]
            print '\nFinding %s properties for deletion:' % days,
            delete_cycle(old_properties)
        else:
            days_ago = datetime.datetime.now() - datetime.timedelta(days=days)
            old_properties = Ad.objects.filter(modified__lt=days_ago, user__isnull=True).order_by('id')
            print '\nFinding properties with update date until %s:' % days_ago,
            delete_cycle(old_properties)

        # удаляем объявления без телефонов, которые отлежались в базе более 7 дней
        days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        old_properties = Ad.objects.filter(user__isnull=True, phones__isnull=True, created__lt=days_ago).order_by('id')
        print '\nFinding properties withouh contact details:',
        delete_cycle(old_properties)

