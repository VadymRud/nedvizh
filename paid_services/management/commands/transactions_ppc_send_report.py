# coding=utf-8
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand

import time
import datetime
import StringIO

from paid_services.models import Transaction
from ppc.models import ActivityPeriod


class Command(BaseCommand):
    leave_locale_alone = True
    help = u'Отчет по транзакциям пользователей'

    def add_arguments(self, parser):
        parser.add_argument('--emails', type=str, default=['am@mesto.ua'], nargs="+", help='user emails')
        parser.add_argument('--days', type=int, default=10, help='start from days before now')

    def handle(self, *args, **options):
        script_start = time.time()

        # Транзакции
        start_at = datetime.datetime.now() + datetime.timedelta(days=-options['days'])
        transactions = Transaction.objects.filter(time__gte=start_at).select_related(
            'user', 'user__region', 'user_plan', 'user_plan__plan')

        transactions_list = []
        for transaction in transactions:
            user_type = u''
            if transaction.user.agencies.exists():
                user_type += u'А'
            if transaction.user.newhomes.exists():
                user_type += u'З'

            transactions_list.append(u'"{}";"{}";"{}";"{}";"{}";"{}";"{}";"{}";"{}";"{}";"{}";"{}";"{}"'.format(
                transaction.time.month, transaction.id, transaction.time.strftime("%d/%m/%Y"),
                transaction.time.strftime('%H:%M'), transaction.user_id, transaction.user.email, transaction.amount,
                transaction.user.date_joined, transaction.user.region,
                transaction.user.region.price_level if transaction.user.region else '', transaction.get_type_display(),
                transaction.user_plan.plan if transaction.user_plan_id else '', user_type
            ))

        transaction_file = StringIO.StringIO()
        transaction_file.write(u'\n'.join(transactions_list))

        # Активности ППК, пока их мало, высылаем все
        ppc_list = []
        for user in ActivityPeriod.objects.all():
            ppc_list.append(u'"{}";"{}";"{}"'.format(
                user.user_id, user.start.strftime("%Y-%m-%d %H:%M") if user.start else '',
                user.end.strftime("%Y-%m-%d %H:%M") if user.end else ''
            ))

        ppc_file = StringIO.StringIO()
        ppc_file.write(u'\n'.join(ppc_list))

        # Отправляем отчеты
        message = EmailMessage(subject=u"Транзакции и ППК за последние 10 дней", body=u"Файлы с отчетом во вложении", to=options['emails'])
        message.attach('transaction.csv', transaction_file.getvalue(), "text/plain")
        message.attach('ppc.csv', ppc_file.getvalue(), "text/plain")
        message.send()

        print '%.2f sec' % (time.time() - script_start)