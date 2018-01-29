# coding: utf-8
from django.core.management.base import BaseCommand

from paid_services.models import Transaction, TRANSACTION_TYPE_CHOICES

import os
import codecs


class Command(BaseCommand):
    help = u'Формирует csv-файл со списком транзакций (альтернатива аутсорсерского сервиса отчетов, переставшего работать)'

    def add_arguments(self, parser):
        parser.add_argument('path', type=str, help=u'путь к файлу')

    def handle(self, *args, **options):
        transaction_types = dict(TRANSACTION_TYPE_CHOICES)

        with codecs.open(os.path.join(options['path']), 'w', 'utf-8') as f:
            f.write(';'.join([
                u'ID', u'время', u'ID пользователя', u'email пользователя', u'тип транзакции', u'сумма',
                u'ID тарифа', u'лимит тарифа', u'регион тарифа', u'уровень цен тарифа', u'начало тарифа', u'конец тарифа',
            ]) + '\n')

            for values in Transaction.objects.order_by('time').values_list(
                'id', 'time', 'user_id', 'user__email', 'type', 'amount',
                'user_plan__plan_id', 'user_plan__ads_limit', 'user_plan__region__name',
                'user_plan__region__price_level', 'user_plan__start', 'user_plan__end'
            ):
                f.write(';'.join(unicode(value) for value in values) + '\n')


