from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q, F, Sum
import time, datetime, re

from ad.models import Ad, ViewsCount
from custom_user.models import User
from datetime import timedelta, datetime, date
from qsstats import QuerySetStats
from django.core.cache import cache

class Command(BaseCommand):
    help = 'run functions every day'

    def handle(self, *args, **options):
        self.graph_new_user()
        self.graph_feeds_properties()
        self.graph_users_properties()
        self.collect_users_and_properties_data_for_statistics()
        self.collect_viewscount_data()

        print '\nChecking:'
        for key in [
            'graph_users',
            'graph_feeds_properties',
            'graph_users_properties',
            'global_properties_statistics',
            'global_users_statistics']:

            print '%s: %s' % (key, len(cache.get(key, '')))


    # новые пользователи за месяц
    def graph_new_user(self):
        print 'Graph new users -',
        attrs = {}
        attrs['legend'] = {1:u'Частник',2:u'Агентство'}
        values = []
        for key in attrs['legend']:
            if key == 1:
                qs = User.objects.filter(is_active=1, agencies__isnull=True).only('date_joined')
            else:
                qs = User.objects.filter(is_active=1, agencies__isnull=False).only('date_joined')

            end = datetime.today()
            start = end-timedelta(days=30)

            # готовим данные для графика
            data = QuerySetStats(qs, 'date_joined').time_series(start, end)
            values.append( [t[1] for t in data] )
        attrs['max_value'] = max([values[0][key]+values[1][key] for key in range(0, len(values[0]))])
        attrs['captions'] = [t[0].day for t in data]
        attrs['values'] = values
        cache.set('graph_users', attrs, 60*60*24*7)
        print 'OK'

    # новые объявления из фидов
    def graph_feeds_properties(self):
        print 'Graph new properties from feeds -',
        attrs = {}
        qs = Ad.objects.filter(user__isnull=1, status__lt=200).only('created')
        end = datetime.today()
        start = end-timedelta(days=30)
        data = QuerySetStats(qs, 'created').time_series(start, end)
        attrs['values'] = [t[1] for t in data]
        attrs['captions'] = [t[0].day for t in data]
        cache.set('graph_feeds_properties', attrs, 60*60*24*7)
        print 'OK'

    # новые объявления от пользователей
    def graph_users_properties(self):
        print 'Graph new properties from users -',
        attrs = {}
        attrs['legend'] = {1:u'Частник',2:u'Агентство'}
        values = []
        for key in attrs['legend']:
            if key == 1:
                users = User.objects.filter(agencies__isnull=True)
            else:
                users = User.objects.filter(agencies__isnull=False)

            qs = Ad.objects.filter(user__in=users).only('created')
            end = datetime.today()
            start = end-timedelta(days=30)
            # готовим данные для графика
            data = [] if not qs else QuerySetStats(qs, 'created').time_series(start, end)
            values.append( [t[1] for t in data] )
        try:
            attrs['max_value'] = max([values[0][key]+values[1][key] for key in range(0, len(values[0]))])
        except:
            pass
        attrs['captions'] = [t[0].day for t in data]
        attrs['values'] = values
        cache.set('graph_users_properties', attrs, 60*60*24*7)
        print 'OK'

    def collect_viewscount_data(self):
        monthes_choises = [u'',u'Янв',u'Фев',u'Мар',u'Апр',u'Май',u'Июн',u'Июл',u'Авг',u'Сен',u'Окт',u'Ноя',u'Дек']
        start = (datetime.today() - timedelta(days=60)).replace(day=1)

        print 'Stats from viewscounts by months -',
        attrs = {'values':[]}
        attrs['legend'] = (
            ('sale', u'Продажа'),
            ('rent', u'Аренда'),
            ('rent_daily', u'Посуточная'),
            ('newhomes', u'Новостройки'),
            ('bank','Банки'),
        )
        values = {}
        rows = ViewsCount.objects.filter(date__gt=start).extra(
            select={
                'is_bank': 'ad_ad.bank_id IS NOT NULL',
                'year': 'extract(year from date)::int',
                'month': 'extract(month from date)::int',
            }
        ).values(
            'basead__ad__deal_type', 'is_bank', 'year', 'month'
        ).annotate(
            detail_views=Sum('detail_views'),
            contacts_views=Sum('contacts_views'),
        ).order_by('year', 'month')

        monthes = []
        for row in rows:
            month = "%s %d" % (monthes_choises[row['month']], row['year'])
            if month not in monthes:
                monthes.append(month)
        attrs['monthes'] = monthes

        for row in rows:
            if row['is_bank']:
                type = 'bank'
            else:
                type = row['basead__ad__deal_type']
            date = "%s %d" % (monthes_choises[row['month']], row['year'])
            if type not in values:
                values[type] = {month: [0, 0] for month in monthes}

            values[type][date][0] = row['detail_views']
            values[type][date][1] = row['contacts_views']

        for type, label in attrs['legend']:
            if type in values:
                attrs['values'].append([
                    label, [values[type][month] for month in monthes]
                ])

        cache.set('viewscount_per_month_statistics', attrs, 60*60*24*7)
        print 'OK'

    def collect_users_and_properties_data_for_statistics(self):
        agencies = User.objects.filter(agencies__isnull=False).values_list('id', flat=True)
        persons = User.objects.filter(agencies__isnull=True).values_list('id', flat=True)
        end = datetime.today()

        print 'Stats for properties by months -',
        stats = {
            'legend': None,
            'rows': (
                ['Агентства', agencies],
                ['Частные лица', persons],
                ['Фиды', ['feeds']],
            )
        }
        if end.month - 2 > 0:
            start = datetime(end.year, end.month-2, 1)
        else:
            start = datetime(end.year - 1, 12 - end.month, 1)
        #start = datetime(end.year, end.month-2, 1) # статистика за два полных предыдущих месяца
        for row in stats['rows']:
            if len(row[1]) > 0 and row[1][0] == 'feeds':
                qs = Ad.objects.filter(user__isnull=1).only('created')
            else:
                qs = Ad.objects.filter(user__in=row[1]).only('created')
            if qs:
                data = QuerySetStats(qs, 'created').time_series(start, end, interval='months')
                row.append(data)
                if not stats['legend']: stats['legend'] = data

        cache.set('global_properties_statistics', stats, 60*60*24*7)
        print 'OK'


        print 'Stats for users by months -',
        stats = {
            'legend': None,
            'rows': (
                ['Агентства', agencies],
                ['Частные лица', persons],
            )
        }
        if end.month - 2 > 0:
            start = datetime(end.year, end.month-2, 1)
        else:
            start = datetime(end.year - 1, 12 - end.month, 1)
        #start = datetime(end.year, end.month-2, 1) # статистика за два полных предыдущих месяца
        for row in stats['rows']:
            qs = User.objects.filter(is_active=True, id__in=row[1]).only('date_joined')
            if qs:
                data = QuerySetStats(qs, 'date_joined').time_series(start, end, interval='months')
                row.append(data)
                if not stats['legend']: stats['legend'] = data

        cache.set('global_users_statistics', stats, 60*60*24*7)
        print 'OK'

