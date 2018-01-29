# coding=utf-8
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.conf import settings
from django.db import connection

from collections import defaultdict
import time

from ad.models import Ad, Region


def center(str, width=20):
    return '{:^15}'.format(str)

cte_sql = '''
    WITH RECURSIVE cte (id) AS (
        SELECT id
            
        FROM ad_region
        WHERE parent_id = %d

        UNION ALL

        SELECT ad_region.id
            
        FROM ad_region
        JOIN cte ON ad_region.parent_id = cte.id

    ) SELECT id FROM cte
'''

class Command(BaseCommand):
    help = 'Benchmark common SQL queries'

    def add_arguments(self, parser):
        parser.add_argument('--dealtype', '-d', dest='dealtype', type=str, default='sale', help='Deal type (sale, rent, etc.)')
        parser.add_argument('--region', '-r', dest='region_id', type=str, default=None, help='Region ID (separated by comma if you want)')
        parser.add_argument('--filter', '-f', dest='filter', type=str, default=None, help='Short name of filter set')
        parser.add_argument('--page', '-p', dest='page', type=int, default=1, help='Page of search results')
        parser.add_argument('--count', '-c', dest='count', action='store_true', help='Check COUNT(*) queries')
        parser.add_argument('--sql', '-s', dest='sql', action='store_true', help='Show SQL queries')
        parser.add_argument('--children_method', '-cm', dest='children_method', type=str, default='default', help='Children get-method by join/ids/default')

    def handle(self, *args, **options):

        region_static_urls = [
            'kiev;',
            'kiev;darnitskij-rajon',
            'irpen;',
            'karpaty;',
            'dnepropetrovsk;',
            ';kievskaya-oblast',
            ';zhitomirskaya-oblast',
            ';odesskaya-oblast',
            ';zaporozhskaya-oblast',
            ';dnepropetrovskaya-oblast',
            ';ukraina/dnepropetrovskaya-oblast',
            ';',
        ]
        default_params = {'status':1, 'deal_type':options['dealtype'], 'property_type':'flat'}
        params_list = {
            'all': {},
            'Rm1': {'rooms':1},
            'Prc': {'price_uah__lt':437979},
            'Prc<>': {'price_uah__gt':437979, 'price_uah__lt':659600},
            'Rm1Prc': {'rooms':1, 'price_uah__lt':659600},
            'HasPht': {'has_photos':True},
            'HARD': {'has_photos':True, 'property_type':'house', 'rooms__in':[1,2], 'price_uah__lt':5000 },
        }

        start = time.time()
        total = 0.0
        regions = Region.objects.filter(static_url__in=region_static_urls)

        if options['filter']:
            params_list = { key:value for key, value in params_list.items() if key in options['filter'].split(',') }

        if options['region_id']:
            regions = Region.objects.filter(pk__in=options['region_id'].split(','))

        print 'Basic where filter: %s\n' % default_params

        print ''.ljust(25),
        for label in params_list.keys():
            print center(label),
        print

        for region in regions.order_by('id'):
            # выбор способа фильтрации по региону
            if options['children_method'] == 'ids':
                region_filter = Q(region__in=region.get_children_ids())
            elif options['children_method'] == 'cte':
                with connection.cursor() as cursor:
                    cursor.execute(cte_sql % region.id)
                    region_filter = Q(region__in=cursor.fetchall())
            elif options['children_method'] == 'join':
                region_filter = Q(region__tree_path__range=('%s.' % region.tree_path, '%s.a' % region.tree_path)) | Q(region__tree_path=region.tree_path)
            else:
                region_filter = Q(region__in=region.get_descendants(include_self=True))

            if region.pk == 1:
                region_filter = Q(addr_country='UA')

            print (u'%s %s' % (region.pk, region.name.replace(u" область", ""))).rjust(25),
            for filter_name, params in params_list.items():
                filter = default_params.copy()
                filter.update(params)

                queryset = Ad.objects.filter(region_filter, **filter)\
                    .order_by('-vip_type', '-updated', '-pk')

                queryset = queryset.defer("description", "address", "source_url", "addr_city", "contact_person")

                try:
                    query_start = time.time()
                    str = ''
                    if options['count']:
                        count = queryset.count()
                        str += '%s@' % count
                    else:
                        page_size = 30
                        top = (options['page'] - 1) * page_size
                        bottom = top + page_size
                        queryset = queryset[top:bottom]
                        list(queryset)
                except KeyboardInterrupt:
                    print '\n--- Exit. Last SQL: '
                    print queryset.query
                    return

                elapsed_time = time.time() - query_start
                total += elapsed_time
                str += '%0.2f' % elapsed_time

                if elapsed_time > 0.2:
                    str = '> %s <' % str

                if not options['sql']:
                    print center(str),
                else:
                    print
                    print '  --- %s ---' % str
                    print queryset.query

            print

        print 'Total', total, '\n'
