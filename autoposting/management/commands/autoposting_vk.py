# coding: utf-8
from __future__ import unicode_literals

import datetime
import os

import requests

from vk_api import vk_api
from django.conf import settings
from django.core.management import BaseCommand
from django.db.models import Q
from django.utils import translation

from ad.models import Ad
from autoposting.models import VkAutoposting, VkAutopostingAd
from custom_user.models import User


class Command(BaseCommand):
    leave_locale_alone = True
    help = 'Автоматический постинг объявлений на стены групп в Vk'

    def handle(self, *args, **options):
        print '--> Start Vk autoposting process'

        # Внимание!!! Нельзя публиковать чаще чем 1 раз в 90 минут, иначе Vk забанит
        allow_date = datetime.datetime.now() - datetime.timedelta(minutes=91)
        vkontakte_autoposting = VkAutoposting.objects.filter(
            (Q(last_posting_at__lt=allow_date) | Q(last_posting_at__isnull=True)) & Q(is_active=True))

        # access token
        response = requests.get(
            'https://oauth.vk.com/access_token',
            params={
                'client_id': settings.VK_APP_ID,
                'client_secret': settings.VK_APP_SECRET_KEY,
                'v': 5.62,
                'grant_type': 'client_credentials'
            })

        access_token = response.json()['access_token']

        if vkontakte_autoposting.exists():
            for vk_autoposting in vkontakte_autoposting:
                translation.activate(vk_autoposting.language)

                print '  --> choose ad for Vk autoposting #%d' % vk_autoposting.id
                # Выбираем одно объявление по заданным параметрам, которое еще ни разу не публиковали
                ads = Ad.objects.filter(
                    deal_type=vk_autoposting.deal_type, region__id__in=vk_autoposting.region.get_children_ids(),
                    is_published=True, status=1, vk_autoposting_ads__isnull=True, has_photos=True
                ).order_by('-created')

                ad = ads.filter(user__in=User.get_user_ids_with_active_ppk()).first() or ads.first()

                if ad:
                    print '    --> chosen ad #%d' % ad.pk
                    vk_session = vk_api.VkApi(
                        login=settings.VK_APP_LOGIN, password=settings.VK_APP_PASSWORD, token=access_token,
                        config_filename=os.path.join(settings.VAR_ROOT, 'vk_config.json'))

                    try:
                        vk_session.authorization()
                    except vk_api.AuthorizationError as e:
                        print '    --> error while posting ad', e.message
                        continue

                    vk = vk_session.get_api()
                    response = vk.wall.post(
                        owner_id='-%s' % vk_autoposting.page_id, attachments=ad.get_absolute_url(),
                        signed=0, from_group=1, guid=ad.pk, message=ad.get_absolute_url())

                    vk_autoposting.last_posting_at = datetime.datetime.now()
                    vk_autoposting.save()

                    VkAutopostingAd.objects.create(
                        vk_autoposting=vk_autoposting, basead=ad.basead_ptr, page_id=response['post_id'])
                    print '    --> success posting to Vk and mark Ad'

        print '<-- Finish Vk autoposting process'
