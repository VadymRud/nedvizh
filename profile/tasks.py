# coding: utf-8
import csv
import datetime
import os
import re
import StringIO
import xlwt
import logging

from django.core.files.storage import default_storage
from django.db.models import Q
from django.core.mail import EmailMessage

from task_queues import close_db, task
from ad.models import Region, Ad, PhoneInAd
from profile.models import Stat
from custom_user.models import User
from paid_services.models import UserPlan
from ppc.models import ActivityPeriod


task_logger = logging.getLogger('task_queues')


@task(queue='important')
@close_db
def start_message_list(message_list, from_user):
    message_list.perform(from_user, False)


@task(queue='photo_download')
@close_db
def statistics_analysis_disclosed_contacts(user_email, start_at, finish_at):
    task_logger.debug('statistics_analysis_disclosed_contacts: start')
    regions = Region.get_provinces()
    start_at = datetime.datetime.combine(start_at, datetime.time.min)
    finish_at = datetime.datetime.combine(finish_at, datetime.time.max)
    date_range = (start_at, finish_at)

    book = xlwt.Workbook(encoding='utf8')
    font = xlwt.Font()
    font.bold = True
    bold_style = xlwt.XFStyle()
    bold_style.font = font
    sheet = book.add_sheet(u'Лист 1')
    user_columns = [u'Период отчета', u'Тип сделки', u'Region_type', u'Region_full', u'Кол-во активных пакетов ',
                    u'Кол-во обьявлений (по подписке)', u'Кол-во взятых контактов', u'Контактов на обьявление',
                    u'Кол-во клиентов на ППК', u'Кол-во обьявлений ППК', u'Кол-во звонков', u'Кол-во пропущеных',
                    u'Кол-во заявок', u'Возвратов', u'Итого действий', u'Звонков на обьявление']
    [sheet.write(0, k, v, style=bold_style) for k, v in enumerate(user_columns)]

    google_analytics_ads = {}
    path = 'statistics_analysis_disclosed_contacts.csv'
    if default_storage.exists(path):
        with default_storage.open(path, 'rb+') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=';')
            re_url = re.compile(r'/(\d+)\.html')
            for row in csv_reader:
                parsed_url = re_url.search(row[0])
                if parsed_url:
                    google_analytics_ads[int(parsed_url.group(1))] = int(row[1])

            task_logger.debug('statistics_analysis_disclosed_contacts: working with data')
            position = 1
            period = u'%s - %s' % (start_at.strftime('%d.%m'), finish_at.strftime('%d.%m'))
            for region in regions:
                region_full = u'%s' % region.name
                regions_children_ids = region.get_children_ids()
                users_id = list(User.objects.filter(region=region).values_list('id', flat=True))

                range_filter = Q(start__range=date_range) | Q(end__range=date_range) | Q(start__lt=start_at, end__gt=finish_at)

                active_plans_amount = UserPlan.objects.filter(Q(user__id__in=users_id) & range_filter).count()
                active_properties_amount = sum(Stat.objects.filter(
                    user__id__in=users_id, date__range=date_range).values_list('active_properties', flat=True) or [0])
                active_ads = int(float(active_properties_amount) / float((finish_at - start_at).days))

                ppc_users_id = set(ActivityPeriod.objects.filter(
                    Q(user__id__in=users_id) & range_filter).values_list('user_id', flat=True))
                ppc_amount = len(ppc_users_id)
                ads_ppc_amount = sum(Stat.objects.filter(
                    user__id__in=ppc_users_id, date__range=date_range).values_list('active_properties', flat=True) or [0])

                calls = 0
                missed_calls = 0
                requests = 0
                returned = 0
                ap_list = ActivityPeriod.objects.filter(Q(user__id__in=users_id) & range_filter)
                for ap in ap_list:
                    calls += ap.user.answered_ppc_calls.filter(call_time__range=date_range).count()
                    missed_calls += ap.user.answered_ppc_calls.filter(call_time__range=date_range, duration=0).count()
                    requests += ap.user.callrequests_to.filter(time__range=date_range).count()
                    returned += ap.user.answered_ppc_calls.filter(
                        call_time__range=date_range, complaint__isnull=False).count()

                result = calls + missed_calls + requests - returned

                for deal_type in ['sale', 'rent', 'rent_daily']:
                    ads_id = set(Ad.objects.filter(
                        region__in=regions_children_ids, pk__in=google_analytics_ads.keys(), deal_type=deal_type
                    ).values_list('pk', flat=True))
                    cont_add = sum([val for key, val in google_analytics_ads.iteritems() if key in ads_id])
                    cont_adv = float(PhoneInAd.objects.filter(basead__in=ads_id).count()) / len(ads_id) if ads_id else 0

                    zadv = float(calls + missed_calls) / len(ads_id) if ads_id else 0

                    sheet.write(position, 0, period)
                    sheet.write(position, 1, deal_type)
                    sheet.write(position, 2, region.price_level)
                    sheet.write(position, 3, region_full)
                    sheet.write(position, 4, active_plans_amount)
                    sheet.write(position, 5, active_ads)
                    sheet.write(position, 6, cont_add)
                    sheet.write(position, 7, float(u"{0:.2f}".format(cont_adv)))
                    sheet.write(position, 8, ppc_amount)
                    sheet.write(position, 9, ads_ppc_amount)
                    sheet.write(position, 10, calls)
                    sheet.write(position, 11, missed_calls)
                    sheet.write(position, 12, requests)
                    sheet.write(position, 13, returned)
                    sheet.write(position, 14, result)
                    sheet.write(position, 15, float(u"{0:.2f}".format(zadv)))
                    position += 1

            buffer_io = StringIO.StringIO()
            book.save(buffer_io)

            # Отправляем отчет
            message = EmailMessage(
                subject=u"Анализ расскрытых контактов", body=u"Файл с отчетом во вложении", to=[user_email]
            )
            message.attach('report.xls', buffer_io.getvalue(), "application/vnd.ms-excel")
            message.send()

            task_logger.debug('statistics_analysis_disclosed_contacts: finish')

    else:
        task_logger.debug('statistics_analysis_disclosed_contacts: error open file %s' % path)
