# coding: utf-8
from django.core.management.base import BaseCommand
from django.db.models import Sum, F, Value

from ad.models import ViewsCount, Ad
from custom_user.models import User

import datetime
import random


class Command(BaseCommand):
    help = 'Adds fake contacts views for published ads having less then 2 real contact views in the last month. Should be run every 7 days'

    def handle(self, *args, **options):
        now = datetime.datetime.now()
        print 'started', now

        ads_with_views_lt_2 = ViewsCount.objects.filter(
            date__range=[now - datetime.timedelta(days=30), now],
            basead__ad__user__in=User.get_user_ids_with_active_plan(),
            basead__ad__is_published=True,
        ).values_list('basead').annotate(contacts_views=Sum('contacts_views')).filter(contacts_views__lt=2)

        ads_without_views = Ad.objects.filter(
            user__in=User.get_user_ids_with_active_plan(), 
            is_published=True, viewscounts__isnull=True
        ).extra(select={'contacts_views': 0}).values_list('basead_ptr', 'contacts_views')

        count = 0

        for query in (ads_with_views_lt_2, ads_without_views):
            for basead_id, contacts_views in query:
                # для 0 или 1 реальных просмотров итоговое число просмотров с учетом добавленных будет от 2 до 3
                views_to_add = random.randint(2 - contacts_views, 3 - contacts_views)
                updated_rows = ViewsCount.objects.filter(basead_id=basead_id, date=now.date(), is_fake=True).update(
                    detail_views=F('detail_views') + views_to_add,
                    contacts_views=F('contacts_views') + views_to_add,
                )
                if not updated_rows:
                    ViewsCount.objects.create(basead_id=basead_id, date=now.date(), is_fake=True, 
                                              detail_views=views_to_add, contacts_views=views_to_add)
                count += 1

        print 'finished %s, added views for %d ads' % (datetime.datetime.now(), count)

