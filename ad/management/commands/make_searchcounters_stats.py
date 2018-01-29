# coding: utf-8
from django.core.management.base import BaseCommand
from django.db.models import Sum, Count

from ad.models import SearchCounter, Region, Ad

import os
import datetime
import codecs


def smart_mkdir(path):
    if not os.path.exists(path):
        os.mkdir(path)


class Command(BaseCommand):
    help = u'Формирует csv-файлы со статистикой поисков (3 вида) за прошлый месяц'

    def add_arguments(self, parser):
        parser.add_argument('path', type=str, help=u'полный путь к папке, в которую сохраняются csv-файлы')

    def handle(self, *args, **options):
        current_month_start = datetime.datetime.now().replace(day=1).date()
        previous_month_start = (current_month_start - datetime.timedelta(days=1)).replace(day=1)

        base_dir_name = previous_month_start.strftime('%Y-%m')
        base_dir = os.path.join(options['path'], base_dir_name)
        smart_mkdir(base_dir)

        ukraina = Region.objects.get(static_url=';')

        for deal_type in ['sale', 'rent']:
            deal_type_dir = os.path.join(base_dir, deal_type)
            smart_mkdir(deal_type_dir)

            for city_slug in ['kiev', 'harkov', 'dnepropetrovsk', 'odessa']:
                city_dir = os.path.join(deal_type_dir, city_slug)
                smart_mkdir(city_dir)

                city = ukraina.get_descendants().get(slug=city_slug)

                base_queryset = SearchCounter.objects.filter(
                    date__gte=previous_month_start,
                    date__lt=current_month_start,
                    region__in=city.get_descendants(include_self=True),
                    deal_type=deal_type,
                )

                # 1: файл с суммой поисков по ценам и комнатам
                print deal_type, city_slug, 1

                queryset1 = base_queryset.filter(property_type='flat').exclude(price_from=None, price_to=None).extra(
                    select={'unnested_rooms': "unnest(rooms)"}
                ).values(
                    'unnested_rooms', 'price_from', 'price_to', 'currency'
                ).annotate(searches=Sum('searches_first_page')).order_by('-searches')

                with codecs.open(os.path.join(city_dir, '1.csv'), 'w', 'utf-8') as f:
                    f.write(';'.join([u'комнаты', u'цена от', u'цена до', u'поиски']) + '\n')
                    for row in queryset1:
                        f.write(';'.join(
                            unicode(row[column]) for column in ['unnested_rooms', 'price_from', 'price_to', 'currency', 'searches']
                        ) + '\n')

                # 2: файл с суммой поисков по районам и комнатам
                print deal_type, city_slug, 2

                districts = {
                    region.tree_path: region.name for region in Region.objects.filter(kind__in=['district', 'village'], parent=city)
                }
                districts_regexp = r'^(%s)(?:\..*)?$' % '|'.join(
                    tree_path.replace('.', r'\.') for tree_path in districts.keys()
                )

                queryset2 = base_queryset.filter(property_type='flat', region__kind__in=['district', 'street', 'village']).extra(
                    select={
                        # вырезаем "районы города" из tree_path
                        'district_tree_path': "substring(ad_region.tree_path from '%s')" % districts_regexp,
                        'unnested_rooms': "unnest(rooms)",
                    }
                ).values('unnested_rooms', 'district_tree_path').annotate(searches=Sum('searches_first_page')).order_by('-searches')

                with codecs.open(os.path.join(city_dir, '2.csv'), 'w', 'utf-8') as f:
                    f.write(';'.join([u'комнаты', u'район', u'поиски']) + '\n')
                    for row in queryset2:
                        if row['district_tree_path'] is None:
                            # например, для Киева попадаются объекты (не районы), привязанные напрямую к Киеву (#19336 - Бориспольское шоссе)
                            print '  no district'
                        else:
                            f.write(';'.join(
                                unicode(value) for value in [row['unnested_rooms'], districts[row['district_tree_path']], row['searches']]
                            ) + '\n')

                # 3: файл с сопоставлением количеств опубликованных объявлений и поисков по типу недвижимости и комнатам
                print deal_type, city_slug, 3

                ads_count_queryset = Ad.objects.filter(
                    deal_type=deal_type,
                    property_type__in=['flat', 'house'],
                    region__in=city.get_descendants(include_self=True),
                    status=1,
                    is_published=True,
                ).values('property_type', 'rooms').annotate(ads=Count('pk')).order_by('ads')

                with codecs.open(os.path.join(city_dir, '3.csv'), 'w', 'utf-8') as f:
                    f.write(';'.join([u'тип', u'комнаты', u'объявления', u'поиски']) + '\n')
                    for row in ads_count_queryset:
                        searches = base_queryset.filter(
                            property_type=row['property_type'], rooms__contains=[row['rooms']]
                        ).aggregate(searches=Sum('searches_first_page'))['searches']

                        f.write(';'.join(
                            unicode(value) for value in [row['property_type'], row['rooms'], row['ads'], searches]
                        ) + '\n')

