# coding: utf-8

from django.core.management.base import BaseCommand

from paid_services.models import VipPlacement
from mail.models import Notification
from ad.models import Ad

import datetime


# может, надо переименовать команду, так как тут не только останаливаются VIP, но и могут запуститься в теории
class Command(BaseCommand):
    def handle(self, *args, **options):
        now = datetime.datetime.now()
        print now

        interval = 20  # сделать параметром команды
        delta = datetime.timedelta(minutes=interval)

        # возможно стоит как-то уменьшить (или увеличить?) выборку
        for ad in Ad.objects.filter(pk__in=VipPlacement.objects.values('basead')):
            ad.update_vip()

        # а если VIP отменен и куплен заново, тогда надо не отправлять уведомления?
        for vipplacement in VipPlacement.objects.filter(until__range=(now - delta, now)).prefetch_related('basead__ad'):
            if vipplacement.basead:  # а иначе может быть?
                Notification.objects.create(user_id=vipplacement.basead.ad.user_id, type='vip_expired', object=vipplacement)

