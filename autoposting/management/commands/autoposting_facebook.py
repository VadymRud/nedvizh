# coding: utf-8
from __future__ import unicode_literals

import datetime

from facebook import GraphAPI, GraphAPIError
from django.core.management import BaseCommand
from django.db.models import Q
from django.utils import translation

from ad.models import Ad
from autoposting.models import FacebookAutoposting, FacebookAutopostingAd
from custom_user.models import User


class Command(BaseCommand):
    leave_locale_alone = True
    help = 'Автоматический постинг объявлений на стены групп в Facebook'

    def handle(self, *args, **options):
        print '--> Start Facebook autoposting process'

        # Внимание!!! Нельзя публиковать чаще чем 1 раз в 90 минут, иначе Facebook забанит
        allow_date = datetime.datetime.now() - datetime.timedelta(minutes=91)
        facebook_autoposting = FacebookAutoposting.objects.filter(
            (Q(last_posting_at__lt=allow_date) | Q(last_posting_at__isnull=True)) &
            Q(access_token_expires_at__gt=datetime.datetime.now(), is_active=True)).exclude(access_token__isnull=True)

        if facebook_autoposting.exists():
            for fb_autoposting in facebook_autoposting:
                translation.activate(fb_autoposting.language)

                print '  --> choose ad for Facebook autoposting #%d' % fb_autoposting.id
                # Выбираем одно объявление по заданным параметрам, которое еще ни разу не публиковали
                ads = Ad.objects.filter(
                    deal_type=fb_autoposting.deal_type, region__id__in=fb_autoposting.region.get_children_ids(),
                    is_published=True, status=1, facebook_autoposting_ads__isnull=True, has_photos=True,
                    price_uah__gte=fb_autoposting.min_price
                ).order_by('-created')

                ad = ads.filter(user__in=User.get_user_ids_with_active_ppk()).first() or ads.first()

                if ad:
                    print '    --> chosen ad #%d' % ad.pk
                    graph = GraphAPI(access_token=fb_autoposting.access_token)
                    try:
                        object_id = graph.put_object(
                            parent_object=fb_autoposting.page_id, connection_name='feed', link=ad.get_absolute_url(),
                            message=ad.get_absolute_url(), published=True)

                    except GraphAPIError as e:
                        print '    --> error while posting ad', e
                        continue

                    fb_autoposting.last_posting_at = datetime.datetime.now()
                    fb_autoposting.save()

                    FacebookAutopostingAd.objects.create(
                        facebook_autoposting=fb_autoposting, basead=ad.basead_ptr, page_id=object_id)
                    print '    --> success posting to Facebook and mark Ad'

        print '<-- Finish Facebook autoposting process'
