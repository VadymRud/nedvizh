# coding: utf-8
from __future__ import unicode_literals

import requests
from decimal import Decimal
from django.core.management import BaseCommand
from django.core.serializers import json
from django.db.models import Sum
from django.conf import settings

from ad.models import ViewsCount, Ad
from paid_services.models import Transaction, VipPlacement


class Command(BaseCommand):
    leave_locale_alone = True
    help = 'Выгрузка данных для прогнозирования поведения пользователей'
    data = {'Inputs': {'input1': {'ColumnNames': [
        'User ID', 'Transaction ID', 'Region', 'Region Type', 'Transaction Sum', 'Limit', 'Pageviewes Total',
        'Pageviewes Sale', 'Pageviewes Rent', 'Pageviewes Daily', 'Contacts Total', 'Contacts Sale',
        'Contacts Rent', 'Contacts Daily', 'Messages', 'Requests for a callback',
        'Average completeness of ad\'s descriptions', 'Average completeness of ad\'s descriptions sale',
        'Average completeness of ad\'s descriptions rent', 'Average completeness of ad\'s descriptions daily',
        'Average q-ty of photos per 1 ad', 'Average q-ty of photos per 1 ad sale',
        'Average q-ty of photos per 1 ad rent', 'Average q-ty of photos per 1 ad daily',
        'Average Q-ty of fields filled-in (except description)',
        'Average Q-ty of fields filled-in (except description) sale',
        'Average Q-ty of fields filled-in (except description) rent',
        'Average Q-ty of fields filled-in (except description) daily', 'Sale Q-ty of 1room',
        'Sale average price per m2 for 1r', 'Sale Q-ty of 2room', 'Sale average price per m2 for 2r',
        'Sale Q-ty of 3room', 'Sale average price per m2 for 3r', 'Sale Q-ty of 4room',
        'Sale average price per m2 for 4r', 'Sale Q-ty of 5+room', 'Sale average price per m2 for 5+r',
        'Rent Q-ty of 1room', 'Rent average price per m2 for 1r', 'Rent Q-ty of 2room',
        'Rent average price per m2 for 2r', 'Rent Q-ty of 3room', 'Rent average price per m2 for 3r',
        'Rent Q-ty of 4room', 'Rent average price per m2 for 4r', 'Rent Q-ty of 5+room',
        'Rent average price per m2 for 5+r', 'Daily Q-ty of 1room', 'Daily average price per m2 for 1r',
        'Daily Q-ty of 2room', 'Daily average price per m2 for 2r', 'Daily Q-ty of 3room',
        'Daily average price per m2 for 3r', 'Daily Q-ty of 4room', 'Daily average price per m2 for 4r',
        'Daily Q-ty of 5+room', 'Daily average price per m2 for 5+r', 'Q-ty of VIP purchased this month Sale',
        'Q-ty of VIP purchased this month Rent', 'Q-ty of VIP purchased this month Daily', 'Purchase -1 month',
        'Purchase -2 month', 'Purchase -3 month', 'Purchase -4 month', 'Purchase -5 month', 'Purchase -6 month',
        'Purchase -7 month', 'Purchase -8 month', 'Purchase -9 month', 'Purchase -10 month', 'Purchase -11 month',
        'Purchase -12 month', 'Purchase +1 month', 'Purchase +2 month', 'Purchase +3 month'
    ], 'Values': []}}, 'GlobalParameters': {}}

    def __init__(self):
        super(Command, self).__init__()

        self.azureml_url = getattr(settings, 'AZUREML_URL')
        self.azureml_api_key = getattr(settings, 'AZUREML_API_KEY')

        assert self.azureml_url is not None and self.azureml_api_key is not None

        # self.headers = {'Authorization': ('Bearer %s' % self.azureml_api_key), 'Content-Type': 'application/json'}
        self.headers = {'Authorization': ('Bearer %s' % self.azureml_api_key)}

    def handle(self, *args, **options):
        # todo: Написать алгоритм выборки пользователей
        users_id = [46182, 5439, 11611, 159779, 143283, 106627, 83316, 139117, 155300, 144333, 42044, 142272, 89797,
                    89751, 47015, 101129, 150383, 21631, 151178]

        user_purchase_dates = {}
        transactions = Transaction.objects.filter(
            user_plan__isnull=False, time__gte='2016-04-01 00:00:00', user__region__isnull=False, type=11,
            user__id__in=users_id
        ).values('user_id', 'user_plan__start')
        for transaction in transactions:
            upm = user_purchase_dates.setdefault(transaction['user_id'], [])
            upm.append(transaction['user_plan__start'])

        transactions = Transaction.objects.filter(
            user_plan__isnull=False, time__gte='2016-04-01 00:00:00', user__region__isnull=False, type=11,
            user__id__in=users_id
        ).select_related('user', 'user_plan', 'user_plan__plan')

        users = {}
        for transaction in transactions:
            user_info = users.setdefault(transaction.user_id, [])

            # Пока нам нужны только последнии транзакции пользователей
            if len(user_info):
                continue

            user_plan_info = [
                transaction.user_id,
                transaction.id,
                transaction.user.region.slug,
                transaction.user.region.price_level,
                int(transaction.amount),
                transaction.user_plan.plan.ads_limit or '9999',
                ViewsCount.objects.filter(
                    basead__ad__user__id=transaction.user_id,
                    date__range=(transaction.user_plan.start.date(), transaction.user_plan.end.date())
                ).aggregate(Sum('detail_views'))['detail_views__sum'] or 0,
                ViewsCount.objects.filter(
                    basead__ad__user__id=transaction.user_id, basead__ad__deal_type='sale',
                    date__range=(transaction.user_plan.start.date(), transaction.user_plan.end.date())
                ).aggregate(Sum('detail_views'))['detail_views__sum'] or 0,
                ViewsCount.objects.filter(
                    basead__ad__user__id=transaction.user_id, basead__ad__deal_type='rent',
                    date__range=(transaction.user_plan.start.date(), transaction.user_plan.end.date())
                ).aggregate(Sum('detail_views'))['detail_views__sum'] or 0,
                ViewsCount.objects.filter(
                    basead__ad__user__id=transaction.user_id, basead__ad__deal_type='rent_daily',
                    date__range=(transaction.user_plan.start.date(), transaction.user_plan.end.date())
                ).aggregate(Sum('detail_views'))['detail_views__sum'] or 0,
                ViewsCount.objects.filter(
                    basead__ad__user__id=transaction.user_id,
                    date__range=(transaction.user_plan.start.date(), transaction.user_plan.end.date())
                ).aggregate(Sum('contacts_views'))['contacts_views__sum'] or 0,
                ViewsCount.objects.filter(
                    basead__ad__user__id=transaction.user_id, basead__ad__deal_type='sale',
                    date__range=(transaction.user_plan.start.date(), transaction.user_plan.end.date())
                ).aggregate(Sum('contacts_views'))['contacts_views__sum'] or 0,
                ViewsCount.objects.filter(
                    basead__ad__user__id=transaction.user_id, basead__ad__deal_type='rent',
                    date__range=(transaction.user_plan.start.date(), transaction.user_plan.end.date())
                ).aggregate(Sum('contacts_views'))['contacts_views__sum'] or 0,
                ViewsCount.objects.filter(
                    basead__ad__user__id=transaction.user_id, basead__ad__deal_type='rent_daily',
                    date__range=(transaction.user_plan.start.date(), transaction.user_plan.end.date())
                ).aggregate(Sum('contacts_views'))['contacts_views__sum'] or 0,
                transaction.user.messages_to.filter(basead__isnull=False).count(),
                transaction.user.callrequests_to.filter(
                    time__range=(transaction.user_plan.start, transaction.user_plan.end)).count(),
            ]

            ads = transaction.user.ads.order_by('created', '-updated').prefetch_related('photos')
            ads = ads[:transaction.user_plan.plan.ads_limit]
            ads_len = len(ads)
            ads_sale_len = 0
            ads_rent_len = 0
            ads_daily_len = 0

            if ads_len:
                # Avg Descriptions length
                description_length = 0
                description_sale_length = 0
                description_rent_length = 0
                description_daily_length = 0

                # Average q-ty of photos per 1 ad
                photos_amount = 0
                photos_amount_sale = 0
                photos_amount_rent = 0
                photos_amount_daily = 0

                # Average Q-ty of fields filled-in (except description)
                filled_fields = 0
                filled_fields_sale = 0
                filled_fields_rent = 0
                filled_fields_daily = 0

                # Rooms
                sale_amount_1r = 0
                sale_area_1r = 0
                sale_price_1r = 0
                sale_amount_2r = 0
                sale_area_2r = 0
                sale_price_2r = 0
                sale_amount_3r = 0
                sale_area_3r = 0
                sale_price_3r = 0
                sale_amount_4r = 0
                sale_area_4r = 0
                sale_price_4r = 0
                sale_amount_5rp = 0
                sale_area_5rp = 0
                sale_price_5rp = 0

                rent_amount_1r = 0
                rent_area_1r = 0
                rent_price_1r = 0
                rent_amount_2r = 0
                rent_area_2r = 0
                rent_price_2r = 0
                rent_amount_3r = 0
                rent_area_3r = 0
                rent_price_3r = 0
                rent_amount_4r = 0
                rent_area_4r = 0
                rent_price_4r = 0
                rent_amount_5rp = 0
                rent_area_5rp = 0
                rent_price_5rp = 0

                daily_amount_1r = 0
                daily_area_1r = 0
                daily_price_1r = 0
                daily_amount_2r = 0
                daily_area_2r = 0
                daily_price_2r = 0
                daily_amount_3r = 0
                daily_area_3r = 0
                daily_price_3r = 0
                daily_amount_4r = 0
                daily_area_4r = 0
                daily_price_4r = 0
                daily_amount_5rp = 0
                daily_area_5rp = 0
                daily_price_5rp = 0

                for ad in ads:
                    description_length += len(ad.description or '')
                    ad_photos_amount = ad.photos.count()
                    photos_amount += ad_photos_amount

                    if ad.deal_type == 'sale':
                        ads_sale_len += 1
                        description_sale_length += len(ad.description or '')
                        photos_amount_sale += ad_photos_amount

                        for field in Ad._meta.get_fields():
                            if isinstance(field, str) and ad.__getattribute__(field) and field != 'description':
                                filled_fields += 1
                                filled_fields_sale += 1

                        sale_amount_1r += int(ad.rooms == 1)
                        sale_price_1r += ad.get_converted_price('UAH') if ad.rooms == 1 and ad.area else 0
                        sale_area_1r += ad.area if ad.rooms == 1 and ad.area else 0

                        sale_amount_2r = int(ad.rooms == 2)
                        sale_price_2r = ad.get_converted_price('UAH') if ad.rooms == 2 and ad.area else 0
                        sale_area_2r += ad.area if ad.rooms == 2 and ad.area else 0

                        sale_amount_3r = int(ad.rooms == 3)
                        sale_price_3r = ad.get_converted_price('UAH') if ad.rooms == 3 and ad.area else 0
                        sale_area_3r += ad.area if ad.rooms == 3 and ad.area else 0

                        sale_amount_4r = int(ad.rooms == 4)
                        sale_price_4r = ad.get_converted_price('UAH') if ad.rooms == 4 and ad.area else 0
                        sale_area_4r += ad.area if ad.rooms == 4 and ad.area else 0

                        sale_amount_5rp = int(ad.rooms > 4)
                        sale_price_5rp = ad.get_converted_price('UAH') if ad.rooms > 4 and ad.area else 0
                        sale_area_5rp += ad.area if ad.rooms > 4 and ad.area else 0

                    elif ad.deal_type == 'rent':
                        ads_rent_len += 1
                        description_rent_length += len(ad.description or '')
                        photos_amount_rent += ad_photos_amount

                        for field in Ad._meta.get_fields():
                            if isinstance(field, str) and ad.__getattribute__(field) and field != 'description':
                                filled_fields += 1
                                filled_fields_rent += 1

                        rent_amount_1r += int(ad.rooms == 1)
                        rent_price_1r += ad.get_converted_price('UAH') if ad.rooms == 1 and ad.area else 0
                        rent_area_1r += ad.area if ad.rooms == 1 and ad.area else 0

                        rent_amount_2r = int(ad.rooms == 2)
                        rent_price_2r = ad.get_converted_price('UAH') if ad.rooms == 2 and ad.area else 0
                        rent_area_2r += ad.area if ad.rooms == 2 and ad.area else 0

                        rent_amount_3r = int(ad.rooms == 3)
                        rent_price_3r = ad.get_converted_price('UAH') if ad.rooms == 3 and ad.area else 0
                        rent_area_3r += ad.area if ad.rooms == 3 and ad.area else 0

                        rent_amount_4r = int(ad.rooms == 4)
                        rent_price_4r = ad.get_converted_price('UAH') if ad.rooms == 4 and ad.area else 0
                        rent_area_4r += ad.area if ad.rooms == 4 and ad.area else 0

                        rent_amount_5rp = int(ad.rooms > 4)
                        rent_price_5rp = ad.get_converted_price('UAH') if ad.rooms > 4 and ad.area else 0
                        rent_area_5rp += ad.area if ad.rooms > 4 and ad.area else 0

                    elif ad.deal_type == 'rent_daily':
                        ads_daily_len += 1
                        description_daily_length += len(ad.description or '')
                        photos_amount_daily += ad_photos_amount

                        for field in Ad._meta.get_fields():
                            if isinstance(field, str) and ad.__getattribute__(field) and field != 'description':
                                filled_fields += 1
                                filled_fields_daily += 1

                        daily_amount_1r += int(ad.rooms == 1)
                        daily_price_1r += ad.get_converted_price('UAH') if ad.rooms == 1 and ad.area else 0
                        daily_area_1r += ad.area if ad.rooms == 1 and ad.area else 0

                        daily_amount_2r = int(ad.rooms == 2)
                        daily_price_2r = ad.get_converted_price('UAH') if ad.rooms == 2 and ad.area else 0
                        daily_area_2r += ad.area if ad.rooms == 2 and ad.area else 0

                        daily_amount_3r = int(ad.rooms == 3)
                        daily_price_3r = ad.get_converted_price('UAH') if ad.rooms == 3 and ad.area else 0
                        daily_area_3r += ad.area if ad.rooms == 3 and ad.area else 0

                        daily_amount_4r = int(ad.rooms == 4)
                        daily_price_4r = ad.get_converted_price('UAH') if ad.rooms == 4 and ad.area else 0
                        daily_area_4r += ad.area if ad.rooms == 4 and ad.area else 0

                        daily_amount_5rp = int(ad.rooms > 4)
                        daily_price_5rp = ad.get_converted_price('UAH') if ad.rooms > 4 and ad.area else 0
                        daily_area_5rp += ad.area if ad.rooms > 4 and ad.area else 0

                # 21
                user_plan_info.append(description_length / ads_len)
                user_plan_info.append(description_sale_length / ads_sale_len if ads_sale_len else 0)
                user_plan_info.append(description_rent_length / ads_rent_len if ads_rent_len else 0)
                user_plan_info.append(description_daily_length / ads_daily_len if ads_daily_len else 0)

                user_plan_info.append(photos_amount / ads_len)
                user_plan_info.append(photos_amount_sale / ads_sale_len if ads_sale_len else 0)
                user_plan_info.append(photos_amount_rent / ads_rent_len if ads_rent_len else 0)
                user_plan_info.append(photos_amount_daily / ads_daily_len if ads_daily_len else 0)

                user_plan_info.append(filled_fields / ads_len)
                user_plan_info.append(filled_fields_sale / ads_sale_len if ads_sale_len else 0)
                user_plan_info.append(filled_fields_rent / ads_rent_len if ads_rent_len else 0)
                user_plan_info.append(filled_fields_daily / ads_daily_len if ads_daily_len else 0)

                user_plan_info.append(sale_amount_1r)
                user_plan_info.append(sale_price_1r / sale_area_1r if sale_area_1r else 0)
                user_plan_info.append(sale_amount_2r)
                user_plan_info.append(sale_price_2r / sale_area_2r if sale_area_2r else 0)
                user_plan_info.append(sale_amount_3r)
                user_plan_info.append(sale_price_3r / sale_area_3r if sale_area_3r else 0)
                user_plan_info.append(sale_amount_4r)
                user_plan_info.append(sale_price_4r / sale_area_4r if sale_area_4r else 0)
                user_plan_info.append(sale_amount_5rp)
                user_plan_info.append(sale_price_5rp / sale_area_5rp if sale_area_5rp else 0)

                user_plan_info.append(rent_amount_1r)
                user_plan_info.append(rent_price_1r / rent_area_1r if rent_area_1r else 0)
                user_plan_info.append(rent_amount_2r)
                user_plan_info.append(rent_price_2r / rent_area_2r if rent_area_2r else 0)
                user_plan_info.append(rent_amount_3r)
                user_plan_info.append(rent_price_3r / rent_area_3r if rent_area_3r else 0)
                user_plan_info.append(rent_amount_4r)
                user_plan_info.append(rent_price_4r / rent_area_4r if rent_area_4r else 0)
                user_plan_info.append(rent_amount_5rp)
                user_plan_info.append(rent_price_5rp / rent_area_5rp if rent_area_5rp else 0)

                user_plan_info.append(daily_amount_1r)
                user_plan_info.append(daily_price_1r / daily_area_1r if daily_area_1r else 0)
                user_plan_info.append(daily_amount_2r)
                user_plan_info.append(daily_price_2r / daily_area_2r if daily_area_2r else 0)
                user_plan_info.append(daily_amount_3r)
                user_plan_info.append(daily_price_3r / daily_area_3r if daily_area_3r else 0)
                user_plan_info.append(daily_amount_4r)
                user_plan_info.append(daily_price_4r / daily_area_4r if daily_area_4r else 0)
                user_plan_info.append(daily_amount_5rp)
                user_plan_info.append(daily_price_5rp / daily_area_5rp if daily_area_5rp else 0)

                user_plan_info.append(VipPlacement.objects.filter(
                    basead__ad__deal_type='sale', since__range=(transaction.user_plan.start,
                                                                transaction.user_plan.end)).count())
                user_plan_info.append(VipPlacement.objects.filter(
                    basead__ad__deal_type='rent', since__range=(transaction.user_plan.start,
                                                                transaction.user_plan.end)).count())
                user_plan_info.append(VipPlacement.objects.filter(
                    basead__ad__deal_type='rent_daily', since__range=(transaction.user_plan.start,
                                                                      transaction.user_plan.end)).count())

            else:
                for i in range(39):
                    user_plan_info.append(0)

            for i in range(1, 13):
                month_status = 0
                for start_date in user_purchase_dates[transaction.user_id]:
                    if start_date < transaction.user_plan.start:
                        month_difference = (transaction.user_plan.start - start_date).days / 30
                        if month_difference == i:
                            month_status = 1
                            break

                user_plan_info.append(month_status)

            for i in range(1, 4):
                month_status = 0
                for start_date in user_purchase_dates[transaction.user_id]:
                    if start_date > transaction.user_plan.start:
                        month_difference = (start_date - transaction.user_plan.start).days / 30
                        if month_difference == i:
                            month_status = 1
                            break

                user_plan_info.append(month_status)

            # Корректируем типы данных
            for pos, val in enumerate(user_plan_info):
                if type(val) == Decimal:
                    user_plan_info[pos] = float(val)

            user_info.append(user_plan_info)

        for user_id in users_id:
            self.data['Inputs']['input1']['Values'] = users[user_id]
            transaction_id = users[user_id][0][1]
            response = requests.post(self.azureml_url, json=self.data, headers=self.headers)
            user_response = response.json()
            scored_labels = user_response['Results']['output1']['value']['Values'][0][-2]
            scored_probabilities = int(float(user_response['Results']['output1']['value']['Values'][0][-1]) * 100.0)
            # print user_response
            print 'User ID: %s, Transaction ID: %s,  Scored Labels: %s, Scored Probabilities: %s%%' % (
                user_id, transaction_id, scored_labels, scored_probabilities)
            # print self.data
            # print '\n\n\n\n------------\n\n\n\n'

