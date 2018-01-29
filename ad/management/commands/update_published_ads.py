# coding=utf-8
from django.core.management.base import BaseCommand
from django.db.models import F, Q

from ad.models import Ad, DeactivationForSale

import datetime


class Command(BaseCommand):
    help = u'Поднятие объявление, которые не поднимались более недели'

    def handle(self, *args, **options):
        now = datetime.datetime.now()
        week_ago = now - datetime.timedelta(days=7)
        two_weeks_ago = now - datetime.timedelta(days=14)
        print now, ': ',

        sold_ads = DeactivationForSale.objects.filter(basead__isnull=False).filter(returning_time__isnull=True).values_list('basead', flat=True)
        published_ads = Ad.objects.filter(is_published=True, status=1).exclude(id__in=sold_ads)

        # более старые объявления сразу поднимаем в самый верх (это случай, когда неактивный юзер купил тариф/ППК)
        print published_ads.filter(updated__lt=two_weeks_ago).update(updated=now,
                                                                     expired=now + datetime.timedelta(days=30)),
        print 'elder ads updated |',

        # остальные объявления обновляются в зависимости от предыдущей дате их обновления
        print published_ads.filter(updated__lt=week_ago).update(updated=F('updated') + datetime.timedelta(days=7),
                                                                expired=F('updated') + datetime.timedelta(days=30)),
        print 'ads updated'
