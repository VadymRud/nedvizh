# coding: utf-8

from django.core.management.base import BaseCommand

from custom_user.models import User
from ppc.models import ActivityPeriod

import datetime
import traceback


class Command(BaseCommand):
    def handle(self, *args, **options):
        now = datetime.datetime.now()
        print 'start', now

        # интервал запуска команды (должен совпадать с кроном), если потребуется чаще, можно будет сделать опцию --interval
        interval = datetime.timedelta(days=1)

        for expiration_days_delta, text in (
            (-1, u'Завтра истекает срок действия вашего тарифного плана. Продлить услугу публикации ваших объявлений и продолжайте получать звонки от потенциальных клиентов'),
            (+3, u'Ваш аккаунт неактивен уже 3 дня! Купите тариф и получайте звонки www.mesto.ua'),
            (+7, u'Ваш аккаунт неактивен уже 7 дней! Купите тариф и получайте звонки www.mesto.ua'),
            (+15, u'Ваш аккаунт неактивен уже 15 дней! Купите тариф и получайте звонки www.mesto.ua'),
        ):
            userplan_end_range = [
                now - datetime.timedelta(days=expiration_days_delta) - interval,
                now - datetime.timedelta(days=expiration_days_delta),
            ]

            users_to_notify = User.objects.filter(
                is_active=True,
                phones__isnull=False,
                user_plans__end__range=userplan_end_range,
            ).exclude(
                user_plans__end__gt=userplan_end_range[1],  # для продленных тарифов
            ).exclude(
                id__in=ActivityPeriod.objects.filter(end=None).values('user'),
            ).prefetch_related('phones').distinct()

            for user in users_to_notify:
                print 'notification: user #%d, expiration_days_delta=%d, ' % (user.id, expiration_days_delta),
                print user.send_notification(text)


