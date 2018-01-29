# -*- coding: utf-8 -*-
from django.utils import timezone
from django.test import TestCase
from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase, RequestFactory


from ad.models import Ad, Region
from profile.views import edit_property
from custom_user.models import User


class RegionTest(TestCase):
    def setUp(self):
        # Every test needs access to the request factory.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='andrey', email='zeratul268@gmail.com', password='top_secret')

    def test_create_ad(self):
        data = {
            'deal_type': 'rent',
            'property_type': 'flat',
            'addr_country': 'UA',
            'addr_city': 'Киев',
            'addr_street': 'Крещатик',
            'rooms': '1',
            'area': '43.4',
            'description': 'фыва',
            'price': '55',
            'currency': 'UAH',
            'phones-TOTAL_FORMS': '1',
            'phones-INITIAL_FORMS': '1',
            'phones-MIN_NUM_FORMS': '3',
            'phones-MAX_NUM_FORMS': '3',
            'phones-0-phone': '+7 (908) 578-86-20',
            'tos': '1',
            'promotion': 'no',
        }
        request = self.factory.post('/account/my_properties/add/', data)
        request.user = self.user
        request.LANGUAGE_CODE = 'ru'

        # проверка http-кода ответа
        response = edit_property(request)
        self.assertEqual(response.status_code, 200)

        # проверка успешности добавления через форму
        import json
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])

        # проверяем получило ли объявление регион
        self.assertTrue(Ad.objects.filter(region__isnull=False).exists())


    def test_geocoder(self):
        ad = Ad.objects.create(address=u'Киев, Крещатик 22')
        ad.process_address()
        ad.save()

        # проверяем привязку к Киеву
        kiev = Region.objects.get(slug='kiev')
        ads = Ad.objects.filter(region__in=kiev.get_descendants(True))
        self.assertTrue(ads.exists())
