# coding: utf-8
from __future__ import unicode_literals

from decimal import Decimal
from django.core.management.base import BaseCommand

import time
import xlwt
import StringIO

from django.db.models import Sum

from ad.models import *
from paid_services.models import *
from seo.models import *
from custom_user.models import *


def center(raw, width=20):
    return '{:^20}'.format(raw)


class Command(BaseCommand):
    args = 'nothing'
    leave_locale_alone = True
    help = 'Отчет по пользователям с бонусом'
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

    def add_arguments(self, parser):
        parser.add_argument('--emails', type=str, default=['zeratul268@gmail.com'], nargs="+", help='user emails')
        parser.add_argument('--limit', dest='limit', type=int, default=None, help='number of user for test')
        parser.add_argument('--local_save', dest='local_save', action='store_true', help='save order to local file')

    def determinate_probability(self, users_id):
        """
        Determination of the probability of prolongation
        :return:
        """

        # return {44577: 27}

        user_purchase_dates = {}
        transactions = Transaction.objects.filter(
            user_plan__isnull=False, time__gte=(datetime.datetime.now() - datetime.timedelta(days=365)),
            user__region__isnull=False, type=11, user__id__in=users_id
        )
        for transaction in transactions.values('user_id', 'user_plan__start'):
            upm = user_purchase_dates.setdefault(transaction['user_id'], [])
            upm.append(transaction['user_plan__start'])

        users = {}
        users_probabilities = {}
        transactions = transactions.filter(
            time__gte=(datetime.datetime.now() - datetime.timedelta(days=31)), user_plan__is_active=True,
            user_plan__end__range=(datetime.datetime.now(), datetime.datetime.now() + datetime.timedelta(days=3))
        ).select_related('user', 'user_plan', 'user_plan__plan')

        for transaction in transactions:
            if transaction.user_id in users_probabilities:
                continue

            if hasattr(transaction, 'azureml'):
                users_probabilities[transaction.user_id] = transaction.azureml.get_or_receive_probability()
                continue

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
                int(transaction.user_plan.plan.ads_limit or '9999'),
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

        # Сортируем выборку по количеству объявлений в пакете
        user_transactions = sorted(
            [val[0] for key, val in users.iteritems()], key=lambda val_item: val_item[5], reverse=True)

        # Локальный счетчик, проверяющий 200 запросов в день, ни как не спасет при множественном запуске скрипта в день
        query_counter = 0
        for user_transaction in user_transactions:
            user_id = user_transaction[0]

            if user_id in users_probabilities:
                continue

            self.data['Inputs']['input1']['Values'] = users[user_id]
            if AzureMLEntry.objects.filter(transaction__id=users[user_id][0][1]).exists():
                azure_log = AzureMLEntry.objects.filter(transaction__id=users[user_id][0][1]).first()
                azure_log.scored_probabilities = 0

            else:
                azure_log = AzureMLEntry()
                azure_log.transaction_id = users[user_id][0][1]

            azure_log.request = self.data
            azure_log.save()

            users_probabilities[user_id] = azure_log.get_or_receive_probability()

            query_counter += 1
            if query_counter > 199:
                break

        return users_probabilities

    def handle(self, *args, **options):
        script_start = time.time()

        now = datetime.datetime.now()
        end_range = [now - datetime.timedelta(days=30),
                     now + datetime.timedelta(days=3)]

        userplans = UserPlan.objects.filter(end__range=end_range).exclude(user_id__in=User.get_user_ids_with_active_ppk())\
            .order_by('id').prefetch_related('user__transactions', 'user__phones', 'user__region')

        if options['limit']:
            userplans = userplans[:options['limit']]

        book = xlwt.Workbook(encoding='utf8')

        users_id = list(userplans.values_list('user_id', flat=True))

        # Определяем вероятность продления
        users_probabilities = self.determinate_probability(users_id)

        users_by_manager = defaultdict(list)
        for user in User.objects.filter(id__in=users_id):
            last_plan = user.user_plans.order_by('end').last()

            # есть продленные планы
            if end_range[1] < last_plan.end:
                continue

            phones = ','.join([p.number for p in user.phones.all()])
            phones_from_ads = ','.join(set(PhoneInAd.objects.filter(basead__ad__user=user).values_list('phone', flat=True)))
            transaction = last_plan.transactions.order_by('time').first()

            row = [user.id, last_plan.end.strftime('%Y-%m-%d'), transaction.id, last_plan.ads_limit,
                   abs(transaction.amount),
                   user.get_plan_discount(last_plan.start),
                   '%s %s' % (user.first_name, user.last_name),
                   phones_from_ads or phones,
                   '%s' % (users_probabilities.get(user.id) or 'not_checked')]

            users_by_manager[unicode(user.manager)].append(row)

        for manager, rows in users_by_manager.items():
            sheet = book.add_sheet(manager)
            header = ['UserID', 'Expiration_date', 'Last_Purchase_ID', 'Last_Purchase_Total_Limit', 'Amount',
                      'Discount', 'Name', 'Phone', 'Probabilities_Of_Prolongation']
            [sheet.write(0, k, v) for k, v in enumerate(header)]

            for row_index, row in enumerate(rows):
                for k, v in enumerate(map(unicode, row)):
                    sheet.write(row_index + 1, k, v)

        filename = 'users_for_crm_%s.xls' % datetime.datetime.now().strftime('%Y%m%d')

        if options['local_save']:
            book.save(filename)

        else:
            f = StringIO.StringIO()
            book.save(f)

            message = EmailMessage(
                subject="Пользователи для ЦРМ",
                body="Пользователи, у которых тариф закончится в ближайшие 3 дня "
                     "или уже закночился в течении последнего месяца. "
                     "Файл со списком пользователей",
                to=options['emails'])
            message.attach(filename, f.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            message.send()

        print '%.2f sec' % (time.time() - script_start)
