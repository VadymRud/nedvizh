# coding: utf-8
from __future__ import unicode_literals

import datetime

import StringIO

from django.core.mail import EmailMessage
from django.core.management import BaseCommand

from paid_services.models import Transaction


class Command(BaseCommand):
    leave_locale_alone = True
    help = 'Отчет для отдела продаж'

    def add_arguments(self, parser):
        parser.add_argument('--emails', type=str, default=['oyaremchuk@mesto.ua'], nargs="+", help='user emails')

    def handle(self, *args, **options):
        transactions = Transaction.objects.filter(time__range=(
            datetime.datetime.now() - datetime.timedelta(days=7),
            datetime.datetime.now()
        )).select_related('user__region', 'user_plan', 'user_plan__plan')
        report_header = ['"TransactionID"', '"Date"', '"Time"', '"UserID"', '"UserPlan"', '"Tariff"', '"Limit"',
                         '"Email"', '"VIPid"', '"Amount\количество"', '"Comment"', '"Comment_2"', '"Type\код тарифа"',
                         '"RegionName"', '"RegionPriceLevel"', '"RegionId"', '"Наименование агентства"']
        report = [';'.join(report_header)]
        for transaction in transactions:
            realtor = transaction.user.get_realtor()
            report.append(
                ';'.join(['"%s"' % col for col in [
                    transaction.id,
                    transaction.time.strftime('%d.%m.%y'),
                    transaction.time.strftime('%H:%M:%S'),
                    transaction.user_id,
                    transaction.user_plan_id if transaction.user_plan else '',
                    transaction.user_plan.plan if transaction.user_plan else '',
                    transaction.user_plan.ads_limit if transaction.user_plan else '',
                    transaction.user.email,
                    '',
                    transaction.amount,
                    transaction.comment,
                    transaction.note,
                    transaction.type,
                    transaction.user.region if transaction.user.region else '',
                    transaction.user.region.price_level if transaction.user.region else '',
                    transaction.user.region_id if transaction.user.region else '',
                    realtor.agency if realtor else ''
                ]]))

        csv_report = StringIO.StringIO()
        csv_report.write('\n'.join(report))

        message = EmailMessage(subject=u"Транзакции за последние 7 дней", body=u"Файлы с отчетом во вложении", to=options['emails'])
        message.attach('transaction.csv', csv_report.getvalue(), "text/plain")
        message.send()

