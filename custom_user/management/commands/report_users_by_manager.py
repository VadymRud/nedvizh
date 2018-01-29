# coding=utf-8
from django.core.management.base import BaseCommand

import time
import datetime
import xlwt
import StringIO

from profile.models import *
from custom_user.models import *

def center(str, width=20):
    return '{:^20}'.format(str)


class Command(BaseCommand):
    leave_locale_alone = True
    help = u'Отчет по пользователям с бонусом'

    def add_arguments(self, parser):
        parser.add_argument('--emails', type=str, default=['zeratul268@gmail.com'], nargs="+", help='user emails')
        parser.add_argument('--limit', dest='limit', type=int, default=None, help='number of user for test')
        parser.add_argument('--local_save', dest='local_save', action='store_true', help='save order to local file')

    def handle(self, *args, **options):
        script_start = time.time()

        book = xlwt.Workbook(encoding='utf8')

        for manager in Manager.objects.all():
            row_index = 0

            sheet = book.add_sheet(u'Пользователи %s' % manager)
            header = [u'User ID', u'E-mail', u'Регион', u'Уровень цен региона', u'План', u'Лидген объяв', u'Лидген новостр',]
            [sheet.write(row_index, k, v) for k, v in enumerate(header)]

            users = User.objects.filter(manager=manager)
            for user in users:
                active_plan = user.get_active_plan()
                row_index += 1
                row = [user.id, user.email, user.region, user.region.price_level if user.region else '',
                       active_plan.ads_limit if active_plan else '-',
                       u'да' if user.has_active_leadgeneration('ads') else '-',
                       u'да' if user.has_active_leadgeneration('newhomes') else '-']


                for k, v in enumerate(row):
                    sheet.write(row_index + 1, k, unicode(v))

        filename = 'users_by_manager_%s.xls' % datetime.datetime.now().strftime('%Y%m%d')

        if options['local_save']:
            book.save(filename)
        else:
            f = StringIO.StringIO()
            book.save(f)

            message = EmailMessage(subject=u"Пользователи с бонусами", body="Файл с отчетом во вложении", to=options['emails'])
            message.attach(filename , f.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            message.send()

        print '%.2f sec' % (time.time() - script_start)
