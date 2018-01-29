# coding=utf-8
import uuid
import urllib2
import socket
import datetime
import json
import random
import re
import math

from django.contrib.postgres.fields import ArrayField
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point, GEOSGeometry
from django.contrib.gis.measure import Distance
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import connection
from django.db.models import Q, Count
from django.db.models.fields.files import ImageFieldFile
from django.db.models.signals import post_delete, pre_save, post_save, m2m_changed
from django.db import transaction as db_transaction
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import activate
from django.utils.http import urlencode
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.urlresolvers import reverse
from django.dispatch import receiver

from phones import pprint_phones
from utils.currency import get_currency_rates
from utils.new_thumbnails import ThumbnailedImageField, ThumbnailedImageFieldFile, save_to_jpeg_content, resize_image
from utils import yandex_translator
from utils.sms import clean_numbers_for_sms
from seo.meta_tags import get_relation_links, get_property_type
from seo.cross_linking import generate_link, check_uk_preposition
from mail.models import Notification
from paid_services.choices import VIP_TYPE_CHOICES

import choices as ad_choices

from dirtyfields import DirtyFieldsMixin
from pytils import translit
from PIL import Image
from utils import ymaps_api
from sorl.thumbnail.engines.pil_engine import Engine

import requests
import phonenumbers


REGION_TYPE_CHOICES = (
    ('country', _(u'страна')),
    ('province', _(u'область')),
    ('area', _(u'областной район')),
    ('locality', _(u'город')),
    ('village', _(u'село/поселок')),
    ('district', _(u'район города')),
    ('vegetation', _(u'парк')),
    ('hydro', _(u'озеро')),
    ('street', _(u'улица')),
    ('group', _(u'группировка m2m')),
    ('group2', _(u'группировка по parent')),
)
PROPERTY_TYPE_CHOICES_BANK = (
    ('residential', _(u'Жильё')),
    ('land', _(u'Земля')),
    ('commercial', _(u'Коммерческие объекты')),
)
PROPERTY_COMMERCIAL_TYPE_CHOICES = (
    ('office', _(u'офис')),
    ('storage', _(u'склад')),
    ('non_residential', _(u'нежилые помещения')),
    ('manufacturing', _(u'производственные мощности')),
    ('for_business', _(u'под бизнес')),
    ('ready_business', _(u'работающий бизнес')),
)

REGION_PRICE_LEVEL_CHOICES = (
    ('low', u'низкий'),
    ('medium', u'средний'),
    ('high', u'высокий'),
)

def get_distance(region_kind):
    return {
        'country': Distance(km=100),
        'province': Distance(km=50),
        'area': Distance(km=50),
        'locality': Distance(km=15),
        'district': Distance(km=2.2),
        'street': Distance(km=1.7),
    }.get(region_kind, Distance(km=2))


def get_coords_deltas(coords, distance):
    earth_radius = 6371000
    earth_arc_distance_per_degree = earth_radius * math.pi * (1. / 180) # формула длины дуги для центрального угла в 1 градус
    lon, lat = coords
    delta_lat = distance.m / earth_arc_distance_per_degree
    delta_lon = delta_lat / math.cos(math.radians(lat))
    return delta_lon, delta_lat

def make_coords_ranges_filters(coords, distance):
    lon, lat = coords
    delta_lon, delta_lat = get_coords_deltas(coords, distance)
    return {
        'coords_x__range': (lon - delta_lon, lon + delta_lon),
        'coords_y__range': (lat - delta_lat, lat + delta_lat),
    }

def make_sphere_distance_filters(field_name, point_from, distance):
    #lon, lat = point_from.coords
    delta_lon, delta_lat = get_coords_deltas(point_from.coords, distance)

    # фильтр dwithin (квадрат по градусам) отсекает большую часть заведомо лишних строк (используется spatial_index),
    # чтобы на них не выполнялась ST_Sphere_Distance из фильтра distance_lte, иначе будет медленно;
    # можно сделать более грубый фильтр с одним "квадратом", оставив один dwithin
    return {
        '%s__dwithin' % field_name: (point_from, delta_lon), # квадрат с максимальной стороной delta_lon
        '%s__distance_lte' % field_name: (point_from, distance),
    }

    ## альтернативный грубый вариант с "прямоугольником"
    #from django.contrib.gis.geos import Polygon
    #poly = Polygon.from_bbox((lon - delta_lon, lat - delta_lat, lon + delta_lon, lat + delta_lat))
    #return {'%s__contained' % field_name: poly}

def truncate_slug(slug, max_length):
    return re.compile(r'^(.{1,%d})(-.*?|)$' % (max_length)).match(slug).group(1)

# TODO наверное можно упростить, так как default_storage умеет добавлять _1, _2 если файл существует
def make_upload_path(instance, filename):
    subfolder = 'u%d' % instance.basead.ad.user_id if instance.basead.ad.user_id else 'r%d' % int(instance.basead.ad.region_id or 0)
    return u'upload/ad/photo/%s/%d_%s.jpg' % (subfolder, instance.basead_id, uuid.uuid4().hex)

class DealType(models.Model):
    name = models.CharField(_(u'название'), max_length=50)
    slug = models.SlugField(_(u'часть URL-а'), max_length=20)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = u'тип сделки'
        verbose_name_plural = u'типы сделки'


update_region_tree_path_sql = '''
UPDATE ad_region SET tree_path = recursive_region_query.tree_path FROM (
    WITH RECURSIVE cte (id, tree_path, parent_id) AS (
        SELECT id,
            '%(initial_tree_path_prefix)s' || id::text AS tree_path,
            parent_id
        FROM ad_region
        WHERE %(parent_id_condition)s

        UNION ALL

        SELECT ad_region.id,
            cte.tree_path || '.' || ad_region.id::text,
            ad_region.parent_id
        FROM ad_region
        JOIN cte ON ad_region.parent_id = cte.id

    ) SELECT id, tree_path, parent_id FROM cte

) AS recursive_region_query WHERE ad_region.id = recursive_region_query.id;
'''


class GeoObject(models.Model):
    """
    todo: проверить чтобы не затрагивались сторонние атрибуты и методы
    """
    region = models.ForeignKey(
        'ad.Region', verbose_name=_(u'присвоенный регион'), null=True, on_delete=models.SET_NULL,
        related_name='%(class)ss'
    )
    region.region_filter_spec = True
    
    address = models.CharField(_(u'полный адрес'), max_length=255, blank=True)
    addr_country = models.CharField(_(u'страна'), max_length=2, choices=ad_choices.COUNTRY_CODE_CHOICES, default='UA')
    addr_city = models.CharField(_(u'населенный пункт'), max_length=100, null=True)
    addr_street = models.CharField(_(u'улица'), max_length=255, null=True, blank=True)
    addr_house = models.CharField(_(u'номер дома'), max_length=10, null=True, blank=True)

    geo_source = models.CharField(
        _(u'источник местоположения'), choices=ad_choices.GEO_SOURCE_CHOICES, max_length=15, default='addr'
    )

    # point = models.PointField(u'точка на карте', null=True, blank=True)
    coords_x = models.FloatField(_(u'долгота/longitude'), null=True, blank=True)
    coords_y = models.FloatField(_(u'широта/latitude'), null=True, blank=True)

    class Meta:
        abstract = True

    def build_address(self):
        parts = []
        for attr in ('addr_city', 'addr_street', 'addr_house'):
            value = getattr(self, attr)
            if value:
                parts.append(value)
        return u', '.join(parts)

    @classmethod
    @db_transaction.atomic
    def sync_partition_indexes(cls):
        '''
            Удаляет и пересоздает индексы для дочерних таблиц партицирования
        '''
        from django.db import connection
        with connection.cursor() as cursor:
            for deal_type in ['sale', 'rent', 'rent_daily', 'archive']:
                table = 'ad_ad_%s' % deal_type

                # очистка всех старых индексов
                cursor.execute('''SELECT 'DROP INDEX ' || string_agg(indexrelid::regclass::text, ', ')
                    FROM   pg_index i LEFT JOIN pg_depend d ON d.objid = i.indexrelid AND d.deptype = 'i'
                    WHERE  i.indrelid = '%s'::regclass AND d.objid IS NULL''' % table)
                drop_index_sql = cursor.fetchone()[0]
                if drop_index_sql:
                    cursor.execute(drop_index_sql)
                    print 'Indexes of %s have been dropped.' % table

                # составляем список новых индексов по полям и настройкам модели
                index_fields = [(field.column,)for field in  cls._meta.fields if field.db_index]
                for fields in cls._meta.index_together:
                    index_fields.append([cls._meta.get_field(field).column for field in fields])

                for fields in index_fields:
                    index_name = '%s_%s' % (deal_type, '_'.join(fields))
                    sql = "CREATE INDEX {0} ON {1} USING btree ({2});".format(index_name, table, ','.join(fields))
                    print " ", sql
                    cursor.execute(sql)
                print

    # проверка регионов в базе и возврат объекта
    @staticmethod
    def _fill_region_from_address_detail(address_list):
        address4add = []
        region = None
        for address in address_list:
            kind, name, coords, text, bounded_by = address

            # поиск по полному названию региона
            region = Region.objects.filter(text=text).first()

            if not region:
                # поиск по имени и ближайшим кординатам для исключения создания дубля
                float_coords = [float(coord) for coord in coords]
                if settings.MESTO_USE_GEODJANGO:
                    point = Point(float_coords, srid=4326)
                    distance_filters = make_sphere_distance_filters('centroid', point, get_distance(kind))
                else:
                    distance_filters = make_coords_ranges_filters(float_coords, get_distance(kind))

                region = Region.objects.filter(name=name, **distance_filters).first()

            if region:  # выходим из цикла, если найден хотя бы один из регионов
                break

            # дополнительная проверка на дублирование по имени, т.к. иногда в ответах Яндекса бывает проблема:
            # ... город Киев вложен в обл. район Киев, а тот вложен в область Киев
            if not address4add or name != address4add[0][1]:
                address4add.insert(0, address)

        for address in address4add:
            slug = translit.slugify(address[1])
            slug = truncate_slug(slug, 50)

            if address[0] == 'country':
                region = Region.objects.filter(slug='international').first()

            if settings.MESTO_USE_GEODJANGO:
                boundary_diagonal = GEOSGeometry(
                    'LINESTRING (%s)' % address[4].replace(';', ','),
                    srid=4326
                )
                boundary_polygon = boundary_diagonal.envelope

                region = Region(
                    parent=region,
                    kind=address[0],
                    name_ru=address[1],
                    slug=slug,
                    centroid=Point([float(coord) for coord in address[2]], srid=4326),
                    text=address[3],
                    boundary=boundary_polygon,
                )
            else:
                region = Region(
                    parent=region,
                    kind=address[0],
                    name_ru=address[1],
                    slug=slug,
                    coords_x=address[2][0],
                    coords_y=address[2][1],
                    text=address[3],
                    bounded_by_coords=address[4],
                )
            region.save()

        return region

    # получение гео-координат по адресу, добавление новых регионов
    def process_address(self):
        self.region = None
        district = district_name = None

        if len(self.address) < 4:
            return

        # хак для ListGlobally, т.к. у них много объявлений с одинаковым адресом
        if hasattr(self, 'content_provider') and self.content_provider:
            ad_with_region = Ad.objects.filter(addr_country=self.addr_country, address=self.address, region__isnull=False).first()
            if ad_with_region:
                self.region = ad_with_region.region
                if self.moderation_status == 11:  # возврат объявления к публикации после неудачного определения региона
                    self.moderation_status = None
                return self.region

        # прямой геокодер не используется, если координаты были получены с карты или из фида отдельными значениями
        if 'coords' in self.geo_source and self.coords_x and self.coords_y:
            geocode = {'coords': (self.coords_x, self.coords_y), 'kind': 'house'}

        else:
            # основной запрос к геокодеру по полному адресу без указания страны
            geocode = ymaps_api.geocode('%s, %s' % (self.get_addr_country_display(), self.address), 2, True)

            # если координаты не найдены или по адресу найдена только страна,
            # то оставляем объявление без региона и координат
            if geocode['coords'][0] is None or geocode['kind'] == 'country':
                return

            # получение имени района
            address_kinds = [addr[0] for addr in geocode['address']]
            if 'street' in address_kinds:
                try:
                    district = ymaps_api.geocode_reverse('%s,%s' % geocode['coords'], kind='district')[0]
                    district_name = district[1]
                    # добавляем имя района в ответ геокодера
                    geocode['address'].insert(address_kinds.index('street'), ('district', district_name))
                except:
                    pass

            if geocode['coords'][0] and geocode['coords'][1]:
                if settings.MESTO_USE_GEODJANGO:
                    self.point = Point([float(coord) for coord in geocode['coords']], srid=4326)
                else:
                    self.coords_x, self.coords_y = geocode['coords']

            # получения названия региона для поиска из списка родительских регионов (без учета улиц/домов)
            for addr in geocode['address'][::-1]:
                if addr[0] != 'house':
                    region_kind, region_name = addr

                    if settings.MESTO_USE_GEODJANGO:
                        distance_filters = make_sphere_distance_filters('centroid', self.point,
                                                                        get_distance(region_kind))
                    else:
                        float_coords = [float(coord) for coord in geocode['coords']]
                        distance_filters = make_coords_ranges_filters(float_coords, get_distance(region_kind))

                    self.region = Region.objects.filter(name=region_name, **distance_filters).order_by('id').first()
                    break

        # обратный геокодер по имеющимся координатам
        if all(geocode.get('coords')) and not self.region:
            address_arr = []
            geocode_reverse = ymaps_api.geocode_reverse('%s,%s' % geocode['coords'])

            for addr in geocode_reverse:
                kind = addr[0]

                # мы совсем не добавляем в базу дома, а для зарубежной недвижимости не добавляем улицы, районы и областные районы
                if not(kind in ['house'] or (self.addr_country != 'UA' and kind in ['area', 'district', 'street'])):
                    address_arr.append(addr)

                # если в прямом геокодинге искался город, то мы не опускаемся ниже найденного региона
                if kind == geocode['kind'] or (geocode['kind'] == 'district' and kind == 'locality'):
                    break

            # пытаемся найти район города
            if district_name and address_arr[-1][0] == 'locality':
                address_arr.append(district)

            self.region = self._fill_region_from_address_detail(address_arr[::-1])

        if self.region:
            if self.moderation_status == 11:  # возврат объявления к публикации после неудачного определения региона
                self.moderation_status = None
        else:
            if not self.moderation_status:  # чтобы не сбросить другие статусы модерации
                self.moderation_status = 11

        return self.region

    def get_subway_stations(self):
        # todo: сделать возможность работы с геокодингом
        stations = cache.get('subway-stations')
        if not stations:
            stations = list(SubwayStation.objects.select_related('subway_line').all())
            cache.set('subway-stations', stations, 60 * 60 * 24)

        near_stations = []
        for station in stations:
            checks = [
                self.coords_x is None,
                self.coords_y is None,
                station.coords_x is None,
                station.coords_y is None
            ]
            if any(checks):
                continue

            fake_distanse = abs(station.coords_x - self.coords_x) + abs(station.coords_y - self.coords_y)
            if fake_distanse < 0.02:
                near_stations.append([fake_distanse, station])

        near_stations = sorted(near_stations, key=lambda station_: station_[0])

        return [station[1] for station in near_stations]


class CollateCCharField(models.CharField):
    def db_type(self, connection):
        db_type_ = super(CollateCCharField, self).db_type(connection)
        if db_type_:
            db_type_ += ' COLLATE pg_catalog."C"'
        return db_type_


if settings.MESTO_USE_GEODJANGO:
    region_objects_manager = models.GeoManager()
else:
    region_objects_manager = models.Manager()


class Region(DirtyFieldsMixin, models.Model):
    kind = models.CharField(_(u'тип региона'), choices=REGION_TYPE_CHOICES, max_length=10)

    name = models.CharField(_(u'название'), max_length=255)
    name_declension = models.CharField(_(u'склонения названия'), blank=True, max_length=700)

    old_name = models.CharField(u'старое название', blank=True, max_length=255)
    old_name_declension = models.CharField(u'склонение старого названия', blank=True, max_length=700)

    parent = models.ForeignKey('self', verbose_name=_(u'относится к'), null=True, blank=True)
    text = models.CharField(_(u'полное название'), max_length=255)

    slug = models.SlugField(_(u'часть URL-а'), max_length=50, db_index=True)
    static_url = models.CharField(_(u'постоянная ссылка'), max_length=255, blank=True, db_index=True)

    subdomain = models.BooleanField(_(u'выводить на поддомене'), default=False, db_index=True)
    main_city = models.BooleanField(_(u'административный центр области'), default=False, db_index=True)
    active_properties = models.PositiveIntegerField(_(u'кол-во активных объявлений в регионе'), default=0)
    created = models.DateTimeField(_(u'время создания'), auto_now=False, default=datetime.datetime.now)

    analytics = models.CharField(_(u'ID аккаунта Google Analytics'), max_length=20, blank=True)

    groupped = models.ManyToManyField("self", verbose_name=_(u'содержимое группы'), blank=True)

    # centroid = models.PointField(u'центральная точка на карте', null=True, blank=True)
    # boundary = models.PolygonField(u'граница на карте', null=True, blank=True)

    coords_x = models.FloatField(_(u'долгота LONG'), null=True, blank=True)
    coords_y = models.FloatField(_(u'широта LAT'), null=True, blank=True)
    bounded_by_coords = models.CharField(_(u'координаты границ области геообъекта'), max_length=60, null=True, blank=True)

    tree_path = CollateCCharField(u'путь в дереве', max_length=100, null=True, db_index=True)

    price_level = models.CharField(u'уровень цен на платные услуги', choices=REGION_PRICE_LEVEL_CHOICES, max_length=10, null=True, blank=True)
    plan_discount = models.DecimalField(u'скидка на тарифы', max_digits=2, decimal_places=2, null=True, blank=True)

    objects = region_objects_manager

    class Meta:
        # сортировка отключена, т.к. она замедляет запросы в генераторе фидов при prefetch('region'), это можно будет оптимизировать с Django 1.7
        # ordering = ['-subdomain','name']
        verbose_name = u'город'
        verbose_name_plural = u'города'

    @classmethod
    def update_tree_path(cls):
        with connection.cursor() as cursor:
            cursor.execute(update_region_tree_path_sql % {
                'initial_tree_path_prefix': '',
                'parent_id_condition': 'parent_id IS NULL',
            })

    def update_descendants_tree_path(self):
        with connection.cursor() as cursor:
            cursor.execute(update_region_tree_path_sql % {
                'initial_tree_path_prefix': '%s.' % self.tree_path,
                'parent_id_condition': 'parent_id = %d' % self.id,
            })

    def get_descendants(self, include_self=False):
        filter_ = Q(tree_path__range=('%s.' % self.tree_path, '%s.a' % self.tree_path))
        if include_self:
            filter_ |= Q(tree_path=self.tree_path)
        return Region.objects.filter(filter_)

    def get_ancestors(self, ascending=False, include_self=False):
        parent_ids = self.tree_path.split('.')
        if not include_self:
            parent_ids.pop()
        if ascending:
            order = '-depth'
        else:
            order = 'depth'
        return Region.objects.filter(id__in=parent_ids).extra(
            select={'depth': "char_length(regexp_replace(tree_path, '\d', ''))"}
        ).order_by(order)

    def get_siblings(self, include_self=False):
        queryset = Region.objects.filter(parent=self.parent)
        if include_self:
            queryset = queryset.exclude(id=self.id)
        return queryset

    def get_children(self):
        return Region.objects.filter(parent=self)

    def get_absolute_url(self):
        parent = self
        url = []
        while parent:
            url.append(parent.slug)
            parent = parent.parent

        url.reverse()
        return "/".join(url[1:])

    def get_region_slug(self):
        if self.static_url == ';': 
            return None
        else:
            return self.static_url.split(';')[1]

    def get_main_city(self):
        cache_key = 'province_to_main_city'
        main_cities = cache.get(cache_key)

        if main_cities is None:
            main_cities = {}
            for main_city in Region.objects.filter(main_city=True):
                province = main_city.get_parents(kind='province')[0]
                main_cities[province.pk] = main_city

            cache.set(cache_key, main_cities, 60*60*24)

        return main_cities.get(self.pk)

    def get_host(self):
        subdomain_slug = self.static_url.split(';')[0]
        if subdomain_slug:
            return '%s.%s' % (subdomain_slug, settings.MESTO_PARENT_HOST)
        else:
            return settings.MESTO_PARENT_HOST

    def get_host_url(self, name, args=None, kwargs=None, host='default', scheme=None):
        subdomain_slug = self.static_url.split(';')[0]
        host_args = [subdomain_slug] if subdomain_slug else []
        from django_hosts.resolvers import reverse
        return reverse(name, args=args or [], kwargs=kwargs or {}, host_args=host_args, host=host, scheme=scheme)

    def get_deal_url(self, deal_type, property_type=None, subway_slug=None):
        view_kwargs = {'deal_type': deal_type}

        if property_type and property_type != 'flat':
            view_kwargs['property_type'] = property_type

        region_slug = self.get_region_slug()
        if region_slug:
            view_kwargs['region_slug'] = region_slug

        if subway_slug:
            view_kwargs['subway_slug'] = subway_slug

        return self.get_host_url('ad-search', kwargs=view_kwargs)

    def __unicode__(self):
        return self.name

    def relation_links(self):
        if self.kind != 'locality':
            return None
        return get_relation_links(self)

    def _inflect_name(self, name):
        import re
        subkinds = (u'улица', u'переулок', u'проспект', u'площадь', u'бульвар', u'спуск',
                 u'село', u'поселок городского типа', u'поселок', u'город')
        a = re.compile("(.*)(^|\s)(%s)($|\s)(.*)" % u'|'.join(subkinds), re.IGNORECASE | re.UNICODE)
        match = a.match(name)

        # если было найдено определяемое существительное
        if match:
            prepended_name, subkind, appended_name = match.group(1,3,5)
            cleaned_name = prepended_name or appended_name
        else:
            cleaned_name = name

        name_declensions = [cleaned_name] * 6

        import pymorphy2
        morph = pymorphy2.MorphAnalyzer()

        declension_assoc_pymorphy = ['nomn', 'gent', 'datv', 'accs', 'ablt', 'loct']
        if match:
            subkind_morphed = filter(lambda x: 'NOUN' in x.tag, morph.parse(subkind.split()[0]))[0]
            for (index, declension_code) in enumerate(declension_assoc_pymorphy):
                subkind_inflected = ' '.join([subkind_morphed.inflect({declension_code})[0]] + subkind.split()[1:])
                if prepended_name:
                    name_declensions[index] = ' '.join([name_declensions[index], subkind_inflected])
                else:
                    name_declensions[index] = ' '.join([subkind_inflected, name_declensions[index]])
        else:
            for (index, declension_code) in enumerate(declension_assoc_pymorphy):
                inflected = morph.parse(name_declensions[0])[0].inflect({declension_code})
                if inflected:
                    name_declensions[index] = (inflected.word).capitalize()

        return name_declensions

    def _get_name_declension(self):
        declensions_assoc = ['original', 'chego', 'chemu', 'chto', 'chem', 'gde']

        # Важно: проверяется поле name_declension, значение которого зависит от текущей локали
        if not self.name_declension or (self.name_declension and len(self.name_declension.split(';')) != 6):
            update_declensions(self, force=True)
            Region.objects.filter(pk=self.pk).update(name_declension=self.name_declension_ru,
                                                     name_declension_ru=self.name_declension_ru,
                                                     name_declension_uk=self.name_declension_uk)

        if self.old_name != '':
            if not self.old_name_declension or (self.old_name_declension and len(self.old_name_declension.split(';')) != 6):
                update_declensions(self)
                Region.objects.filter(pk=self.pk).update(old_name_declension=self.old_name_declension_ru,
                                                         old_name_declension_ru=self.old_name_declension_ru,
                                                         old_name_declension_uk=self.old_name_declension_uk)

        declensions = {declensions_assoc[index]: word for (index, word) in enumerate(self.name_declension.split(';'))}
        return declensions
    nameD = property(_get_name_declension)

    def delete_cache(self):
        if self.kind == 'province':
            cache.delete('provinces')
        if self.subdomain:
            cache.delete('subdomains')

        for key in ['region%d_%s' % (self.pk, cache_type) for cache_type in ['children', 'parents', 'location']]:
            cache.delete(key)

    def get_children_ids(self):
        cache_key = 'region%d_children' % self.pk
        children = cache.get(cache_key)

        # проверка на корректность данных в кеше: среди children должен быть ID текущего региона
        if children and self.pk not in children:
            self.delete_cache()
            children = None

        if not children:
            if self.kind == 'country':
                children = []
            elif self.kind == 'group':
                first_children = self.groupped.all()
                children = []
                for region in first_children:
                    children += region.get_children_ids()
            else:
                children = list(self.get_descendants(include_self=True).values_list('id', flat=True))

            cache.set(cache_key, children, 60*60*24)  # дочерние регионы обновляются раз в сутки

        return children

    def get_parents(self, kind=None):
        cache_key = 'region%d_parents_%s' % (self.pk, kind if kind else 'all')
        parents = cache.get(cache_key)

        # проверка на корректность данных в кеше: среди parents должен быть текущий регион
        if not kind and parents and not [region for region in parents if self.id == region.id]:
            self.delete_cache()
            parents = None

        if parents is None:
            parents = self.get_parents_as_queryset()
            if kind:
                parents = parents.filter(kind=kind)

            cache.set(cache_key, list(parents), 3600*24)

        return parents

    def get_siblings_by_distanse(self, flat=True):
        regions = []
        for region in self.get_siblings().filter(kind=self.kind):
            fake_distanse = abs(region.coords_x - self.coords_x) + abs(region.coords_y - self.coords_y)
            regions.append([region, fake_distanse])

        regions.sort(key=lambda x: x[1])
        if flat:
            return [region[0] for region in regions]
        else:
            return regions

    def get_parents_as_queryset(self):
        return self.get_ancestors(ascending=False, include_self=True)

    def get_breadcrumbs(self, deal_type, property_type=None, detail=None, current_language='ru', rooms=None):
        deal_type_choices = {
            'sale': u'купить',
            'rent': u'арендовать',
            'rent_daily': u'снять посуточно'
        }

        if deal_type:

            # разкомментировать, когда потребуется случайные анкоры в хлебных крошках
            # random_by_ID = random.Random()
            # random_by_ID.seed(self.id)
            random_by_ID = None
            main_city = None

            breadcrumbs = [
                [
                    region.get_deal_url(deal_type, property_type),
                    generate_link(random_by_ID, region, deal_type, property_type, use_random=random_by_ID is not None)[1],
                    region
                ] for region in self.get_parents()[1:]
                if region.kind in ['country', 'province', 'locality', 'village', 'district', 'street']
            ]

            subdomain_in_breadcrumbs = [row[2] for row in breadcrumbs if row[2].subdomain]
            province_in_breadcrumbs = [row[2] for row in breadcrumbs if row[2].kind == 'province']

            if province_in_breadcrumbs:
                province = province_in_breadcrumbs[0]
                main_city = Region.objects.filter(parent=province, main_city=True).first()

                if main_city:
                    # если текущий регион - область, то добавляем две ссылки на крупный город (домен и тип сделки)
                    if self.kind == 'province':
                        breadcrumbs.insert(0, [
                            main_city.get_host_url('index'),
                            u'Вся недвижимость',
                            main_city
                        ])

                        if deal_type in deal_type_choices:
                            breadcrumbs.insert(1, [
                                main_city.get_deal_url(deal_type, property_type),
                                '%s %s' % (deal_type_choices[deal_type].capitalize(),
                                           get_property_type(property_type, 3)) + u' в %(gde)s',
                                main_city
                            ])

                    # добавляем ссылку на главый город, если такой еще нет, но указана при этом указана область
                    if self.kind != 'province' and not subdomain_in_breadcrumbs:
                        breadcrumbs.insert(1, [
                            main_city.get_deal_url(deal_type, property_type),
                            get_property_type(property_type, 4).capitalize() + u' в %(gde)s',
                            main_city
                        ])

                    # на странице поддомена нужно добавить ссылку на поддомен без типа сделки
                    if subdomain_in_breadcrumbs:
                        breadcrumbs.insert(1, [
                            main_city.get_host_url('index'),
                            u'Вся недвижимость',
                            main_city
                        ])
                        breadcrumbs.pop(0)

            if deal_type == 'newhomes':

                breadcrumbs = [
                    [
                        region.get_deal_url(deal_type, property_type),
                        generate_link(random_by_ID, region, deal_type, property_type, use_random=random_by_ID is not None)[1],
                        region
                    ] for region in self.get_parents()[1:]
                    if region.kind in ['province', 'locality', 'village', 'district', 'street']
                ]

                if len(breadcrumbs) > 2:
                    breadcrumbs[1][1] = u'Новостройки %(chego)s'

                if main_city is not None:
                    breadcrumbs.insert(0, [
                        main_city.get_host_url('index'),
                        u'Вся недвижимость',
                        main_city
                    ])

                    if main_city == region:
                        breadcrumbs.insert(1, [
                            main_city.get_deal_url('sale', 'flat'),
                            u'Купить квартиру в %(gde)s' % region.nameD,
                            main_city
                        ])

                if subdomain_in_breadcrumbs:
                    new_breadcrumbs = []
                    for i in breadcrumbs:
                        reg = i[2]
                        if reg.kind != 'province':
                            new_breadcrumbs.append(i)
                    breadcrumbs = new_breadcrumbs

            if main_city and rooms:
                if rooms >= 5:
                    rooms_display = _(u'Пятикомнатные')
                else:
                    rooms_display = {
                        1:_(u'Однокомнатные'),
                        2:_(u'Двухкомнатные'),
                        3:_(u'Трехкомнатные'),
                        4:_(u'Четырехкомнатные')
                    }[rooms]
                breadcrumbs.insert(2, [
                    main_city.get_deal_url(deal_type, property_type) + '?rooms=%d' % rooms,
                    rooms_display + ' ' + get_property_type(property_type, 4) + u' в %(gde)s',
                    main_city
                ])

            can_use_short_link = False
            short_rules = (
                [(unicode(u'Долгосрочная аренда'), unicode(u'Посуточная аренда')), unicode(u'Аренда')],
                [(unicode(u'Продажа квартир'), ), unicode(u'Купить квартиру')],
            )

            from seo.models import SEOCachedPhrase

            scp = SEOCachedPhrase()
            for i, crumb in enumerate(breadcrumbs):
                region = crumb[2]
                if not region: 
                    continue

                if crumb[2].kind in ['street', 'district']:
                    crumb[1] = '%(original)s'

                # последний элемент breadcrumbs является текущей страницей и ссылается сам на себя,
                # поэтому выводится только при вводе параметров в форме поиска и имеет сокращенный вид
                # UPD: отключено после корректировок от 02.11.2015
                # if not detail and self == region and i == len(breadcrumbs)-1:
                #     crumb[1] = crumb[1].split(u' в ')[0]

                # сокращение длинных названий, а так же использование синонимов,
                # чтобы исключить дублирование типа сделки в breadcrumbs
                for rule in short_rules:
                    for words in rule[0]:
                        if words in crumb[1]:
                            if can_use_short_link:
                                crumb[1] = crumb[1].replace(words, rule[1])
                            else:
                                # for replace in next itaration
                                can_use_short_link = True

                if current_language == 'uk':
                    crumb[1] = scp.get_translated_phrase(crumb[1].replace('  ', ' '))

                crumb[1] = crumb[1] % crumb[2].nameD

                if current_language == 'uk':
                    crumb[1] = check_uk_preposition(crumb[1])

            return breadcrumbs

    def get_breadcrumbs_bank(self):
        from django_hosts.resolvers import reverse
        property_type = getattr(self, "property_type", None)
        if property_type:
            property_type_name = [row[1].title() for row in PROPERTY_TYPE_CHOICES_BANK if row[0] == property_type][0]
            return [[reverse('bank-ad-search', host='bank', kwargs={'property_type': property_type}), property_type_name]] + \
                   [[region.get_deal_url(property_type).replace('//', '//bank.'), region.name] for
                    region in self.get_parents()[1:]]

    # собирает по родителям все регионы и их тип
    def get_location(self):
        location = {self.kind: self.name}
        for region in self.get_parents():
            location[region.kind] = region.name
        return location

    def make_static_url(self):
        if self.kind == 'country' and self.slug == 'ukraina':
            return ';'
        elif self.subdomain:
            return '%s;' % self.slug
        else:
            parent_static_url = self.parent.static_url if self.parent else ';'
            separator = '' if parent_static_url[-1] == ';' else '/'
            return parent_static_url + separator + self.slug

    # Костыль пока Jinja не обновится до версии 2.8 и будет доступен тест rejectattr("slug", "equalto", "abroad") и т.п.
    # TODO: Либо нужно поменять как-то логику. Цель: спрятать Украину и Зарубежная недвижимость из списка поддоменов
    @property
    def is_shown_in_subdomains_list(self):
        if self.kind == 'country' or self.slug == 'international':
            return None
        return True

    # Еще костыль, но теперь для стандартизированного вывода названия улиц
    # TODO: Либо нужно поменять как-то логику, но менять названия при добавлении нежелательно, т.к. с геокодером возникнут проблемы
    @property
    def street_formatted_name(self):
        formatted_name = self.name
        for street_kind in [u'вулиця', u'улица', u'проспект', u'шоссе', u'шосе', u'спуск', u'бульвар']:
            if street_kind in formatted_name:
                formatted_name = '%s %s' % (formatted_name.replace(street_kind, '').strip(), street_kind)
        formatted_name = formatted_name[:1].capitalize() + formatted_name[1:]
        return formatted_name
    
    @staticmethod
    def get_provinces():
        provinces = cache.get('provinces')
        if provinces is None:
            provinces = list(Region.objects.filter(kind='province', parent=1).order_by('name'))
            cache.set('provinces', provinces, 60*60*24)
        return provinces

    @staticmethod
    def get_capital_province():
        return Region.objects.get(slug=settings.MESTO_CAPITAL_SLUG).get_parents('province')[0]

    @staticmethod
    def get_region_and_params_from_url(url):
        import urlparse
        from django.core.urlresolvers import resolve
        from django.http import Http404

        parsed_url = urlparse.urlparse(url)

        try:
            subdomain = parsed_url.netloc.split('.')[-3]
        except IndexError:
            subdomain = ''

        subdomain_region = None
        for region in Region.get_subdomains():
            if region.slug == subdomain or (region.static_url == ';' and subdomain == ''):
                subdomain_region = region

        try:
            url_language = ([code for code, name in settings.LANGUAGES if parsed_url.path.startswith(u'/%s/' % code)] \
                           or [settings.LANGUAGE_CODE])[0]
            activate(url_language)

            view, args, kwargs = resolve(parsed_url.path)
            static_url = '%s;%s' % (subdomain, kwargs.get('region_slug') or '')

            activate(settings.LANGUAGE_CODE)

            try:
                region = Region.objects.get(static_url=static_url)
            except Region.DoesNotExist:
                region = None

            return {
                'subdomain_region': subdomain_region,
                'region': region,
                'view': view,
                'kwargs': kwargs,
                'GET': urlparse.parse_qs(parsed_url.query),
                'language': url_language
            }
        except Http404:
            return {
                'error': 'URL not resolving'
            }

    @staticmethod
    def get_region_from_slug(region_slug, subdomain, default_region=None):
        if default_region and not region_slug:
            return default_region

        try:
            return Region.objects.filter(static_url='%s;%s' % (subdomain or '', region_slug or '')).order_by('id')[0]
        except IndexError:
            return None


    @staticmethod
    def get_subdomains():
        subdomains = cache.get('subdomains')
        if subdomains is None:
            subdomains = list(Region.objects.filter(subdomain=True).order_by('subdomain', 'name'))
            cache.set('subdomains', subdomains, 60*60*24)
        return subdomains

    def get_coords(self):
        if settings.MESTO_USE_GEODJANGO:
            if self.centroid:
                return self.centroid.coords
        else:
            if self.coords_x:
                return (self.coords_x, self.coords_y)

@receiver(post_save, sender=Region)
def update_region_tree_path(sender, instance, created, **kwargs):
    if instance.parent is None:
        tree_path = '%d' % instance.id
    else:
        tree_path = '%s.%d' % (instance.parent.tree_path, instance.id)

    if instance.tree_path != tree_path:
        instance.tree_path = tree_path
        instance.save()
        instance.update_descendants_tree_path()

@receiver(pre_save, sender=Region)
def update_declensions(instance, **kwargs):
    if settings.MESTO_SITE == 'mesto':
        if not instance.name_declension_ru or kwargs.get('force'):
            declensions_ru = instance._inflect_name(instance.name_ru)
            instance.name_declension_ru = u';'.join(declensions_ru)
            # если переводить строку целиком, то в некоторых случаях яндекс переводит неправильно
            #   [ru] Ивано-Франковск;Ивано-Франковска;Ивано-Франковску;Ивано-Франковска;Ивано-Франковском;Ивано-Франковске
            #   [uk] Ивано-Франковск;Ивано-Франковска;Ивано-Франковску;Ивано-Франковска;Ивано-Франковском;Ивано-Франковске
            # еще пример:
            #   [ru] Кировоград;Кировограда;Кировограду;Кировограда;Кировоградом;Кировограде
            #   [uk] Кіровоград;Вінниці;Кіровограді;Кіровограда;Кіровоградом;Кіровограді
            # поэтому перевод отдельно по словам
            instance.name_declension_uk = u';'.join(yandex_translator.translate(declensions_ru, 'ru-uk'))
        if instance.old_name != '' and not instance.old_name_declension_ru:
            old_declensions_ru = instance._inflect_name(instance.old_name_ru)
            instance.old_name_declension_ru = u';'.join(old_declensions_ru)
            instance.old_name_declension_uk = u';'.join(yandex_translator.translate(old_declensions_ru, 'ru-uk'))

@receiver(pre_save, sender=Region)
def translate_fields(instance, **kwargs):
    # получение перевода названия региона
    if settings.MESTO_SITE == 'mesto' and not instance.name_uk:
        instance.name_uk = yandex_translator.translate([instance.name_ru], 'ru-uk')[0]
    if settings.MESTO_SITE == 'nesto' and not instance.name_hu:
        instance.name_hu = yandex_translator.translate([instance.name_ru], 'ru-hu')[0]

@receiver(pre_save, sender=Region)
def update_static_url(sender, instance, **kwargs):
    if set(['subdomain', 'slug']) & set(instance.get_dirty_fields().keys()):
        instance.static_url = instance.make_static_url()

@receiver(post_save, sender=Region)
def dirty_region(sender, instance, created, **kwargs):
    if created:
        # чтобы новый регион появился в get_children_ids у родителей
        for parent in instance.get_parents():
            parent.delete_cache()

    else:
        if 'static_url' in instance.get_dirty_fields().keys():
            for region in instance.get_children():
                region.static_url = region.make_static_url()
                region.save()
                region.delete_cache()

            # TODO нужно более точно определять момент когда нужен сброс
            cache.delete('subdomains')
            cache.delete('provinces')


class RegionCounter(models.Model):
    region = models.ForeignKey(Region, verbose_name=_(u'город'), related_name='region_counter')
    deal_type = models.CharField(_(u'тип операции'), choices=ad_choices.DEAL_TYPE_CHOICES, max_length=20)
    count = models.PositiveIntegerField(_(u'кол-во объявлений'))
    modified = models.DateTimeField(_(u'время изменения'), auto_now=True)

    def __unicode__(self):
        return u'%d properties with %s in %s' % (self.count, self.region.slug, self.deal_type)

    class Meta:
        verbose_name = u'счетчик объявлений в городе'
        verbose_name_plural = u'счетчики объявлений'


class Facility(models.Model):
    name = models.CharField(_(u'название удобства'), max_length=30)
    deal_type = models.ManyToManyField(DealType, verbose_name=_(u'доступно в типах сделки'), blank=True, related_name='facilities')

    def __unicode__(self):
        return self.name

    @staticmethod
    def get_facilities_by_deal_type(deal_type):
        facilities = cache.get('facilities_%s' % deal_type)
        if not facilities:
            facilities = Facility.objects.filter(deal_type__slug=deal_type)
            cache.set('facilities_%s' % deal_type, facilities, 60 * 60 * 24 * 7)
        return facilities

    class Meta:
        verbose_name = u'удобство'
        verbose_name_plural = u'удобства'
        ordering = ['name']


class Rules(models.Model):
    name = models.CharField(_(u'название правила заселения'), max_length=30)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = u'правило заселения'
        verbose_name_plural = u'правила заселения'
        ordering = ['name']


METRO_CHOICES = (
    ('no', _(u'Метро отсутствует')),
    ('5', _(u'5 минут')),
    ('10', _(u'10 минут')),
    ('15', _(u'15 минут')),
    ('30', _(u'30 минут')),
)

# TODO: возможно, здесь понядобятся координаты или привязка к городу
class MetroStation(models.Model):
    name = models.CharField(_(u'название'), max_length=30)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = u'станция метро'
        verbose_name_plural = u'станции метро'
        ordering = ['name']


class BaseAd(models.Model):
    phones = models.ManyToManyField('ad.Phone', through='ad.PhoneInAd', verbose_name=u'телефоны', related_name='ads')
    facilities = models.ManyToManyField(Facility, verbose_name=_(u'удобства'), blank=True, related_name='facilities+')
    rules = models.ManyToManyField(Rules, verbose_name=_(u'правила заселения'), blank=True, related_name='rules+')

    def __unicode__(self):
        return self.ad.__unicode__()


from django.contrib.postgres.fields import ArrayField

@receiver(m2m_changed, sender=BaseAd.facilities.through)
def update_facilities_array(sender, instance, **kwargs):
    Ad.objects.filter(basead_ptr_id=instance.id).update(
        facilities_array=[facility.id for facility in instance.facilities.all()] or None
    )


if settings.MESTO_USE_GEODJANGO:
    ad_objects_manager = models.GeoManager()
else:
    ad_objects_manager = models.Manager()


def validate_iframe_url(value):
    """
    Функция-валидатор, нужен чтобы не пропускать некорректные URL для поля Ad.iframe_url
    В настоящий момент смотрит чтобы поле работало только для URL начинающихся с http://premium.giraffe360.com/mesto/
    В планах разрешить добавлять ссылку на видео

    Например: http://premium.giraffe360.com/mesto/ukraine-binnica/
    """

    if value and 'giraffe360.com' not in value:
        raise ValidationError(_('Enter a valid URL.'))


class Ad(DirtyFieldsMixin, BaseAd, GeoObject):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'пользователь'), db_index=True, blank=True, null=True,
                             related_name='ads')
    content_provider = models.PositiveIntegerField(_(u'контент провайдер'), db_index=True, choices=ad_choices.CONTENT_PROVIDER_CHOICES,
                                                   null=True, blank=True)
    bank = models.ForeignKey('bank.Bank', verbose_name=_(u'банк'), blank=True, null=True, related_name='ads')

    is_published = models.BooleanField(_(u'опубликовано на сайте'), db_index=True, default=False)
    status = models.PositiveIntegerField(_(u'статус'), choices=ad_choices.STATUS_CHOICES, db_index=True, default=210)
    moderation_status = models.PositiveIntegerField(_(u'статус модерации'), null=True, blank=True, choices=ad_choices.MODERATION_STATUS_CHOICES)

    # для объявлений, у которых нет VipPlacement, используем костыль с vip_type=0 (при vip_type=None сортировка '-vip_type' будет работать с NULLS FIRST по умолчанию)
    # TODO: при обновлении до Django-1.11 можно переделать - в ней появилась возможность делать Expression(...).desc(nulls_last=True)
    vip_type = models.PositiveIntegerField(u'тип VIP-размещения', choices=[(0, 0)] + list(VIP_TYPE_CHOICES), db_index=True, default=0)

    is_bargain_possible = models.BooleanField(_(u'торг возможен'), default=False)

    deal_type = models.CharField(_(u'тип операции'), choices=ad_choices.DEAL_TYPE_CHOICES, default='rent',
                                 max_length=20)
    property_type = models.CharField(_(u'тип недвижимости'), choices=ad_choices.PROPERTY_TYPE_CHOICES,
                                     default='flat', max_length=20)
    property_commercial_type = models.CharField(_(u'тип коммерческой недвижимости'),
                                                choices=PROPERTY_COMMERCIAL_TYPE_CHOICES, blank=True, null=True,
                                                max_length=20)
    title = models.CharField(_(u'заголовок объявления'), max_length=255)

    price = models.BigIntegerField(_(u'цена'), default=0)
    currency = models.CharField(_(u'валюта цены'), choices=ad_choices.CURRENCY_CHOICES, default='UAH', max_length=3)
    price_uah = models.BigIntegerField(_(u'цена в гривнах'), default=0, db_index=True)

    building_type = models.PositiveSmallIntegerField(_(u'тип здания'), choices=ad_choices.BUILDING_TYPE_CHOICES, null=True, blank=True)
    building_type_other = models.CharField(_(u'тип здания (другое)'), max_length=50, null=True, blank=True, help_text=u'укажите тип здания')
    building_layout = models.PositiveSmallIntegerField(_(u'планировка'), choices=ad_choices.LAYOUT_CHOICES, null=True, blank=True)
    building_walls = models.PositiveSmallIntegerField(_(u'тип стен'), choices=ad_choices.WALLS_CHOICES, null=True, blank=True)
    building_windows = models.PositiveSmallIntegerField(_(u'тип окон'), choices=ad_choices.WINDOWS_CHOICES, null=True, blank=True)
    building_heating = models.PositiveSmallIntegerField(_(u'тип отопления'), choices=ad_choices.HEATING_CHOICES, null=True, blank=True)

    # metro = models.ForeignKey(MetroStation, verbose_name=_(u'станция метро'), blank=True, null=True,
    #                           related_name='metro_stations')
    # metro_distance = models.CharField(_(u'расстояние до станции метро'), max_length=2, choices=METRO_CHOICES,
    #                                   default='no')

    rooms = models.PositiveIntegerField(_(u'количество комнат'), blank=True, null=True)
    guests_limit = models.PositiveIntegerField(_(u'максимальное кол-во гостей'), blank=True, null=True)
    area = models.DecimalField(_(u'площадь общая'), help_text=_(u'общая'), max_digits=8, decimal_places=2, null=True, blank=True)
    area_living = models.DecimalField(_(u'площадь жилая'), help_text=_(u'жилая'), max_digits=6, decimal_places=2, null=True, blank=True)
    area_kitchen = models.DecimalField(_(u'площадь кухни'), help_text=_(u'кухня'), max_digits=6, decimal_places=2, null=True, blank=True)
    description = models.TextField(_(u'описание'), null=True, blank=True, 
        help_text=_(u'Запрещено размещать в описании контактные данные и ссылки на другие ресурсы, в противном случае объявление будет деактивировано')
    )
    floor = models.PositiveSmallIntegerField(_(u'этаж'), choices=ad_choices.FLOOR_CHOICES, null=True, blank=True)
    floors_total = models.PositiveSmallIntegerField(_(u'этажность дома'), choices=ad_choices.FLOOR_CHOICES, null=True, blank=True)

    price_period = models.CharField(_(u'периодичность оплаты'), max_length=20, null=True, blank=True)
    space_units = models.CharField(_(u'единица площади для оплаты'), max_length=20, null=True, blank=True)
    source_url = models.CharField(_(u'ссылка на источник'), blank=True, max_length=512)
    created = models.DateTimeField(_(u'время создания'), auto_now=False, default=datetime.datetime.now, db_index=True)
    modified = models.DateTimeField(_(u'время изменения'), auto_now=True)
    updated = models.DateTimeField(_(u'время обновления'), db_index=True, auto_now_add=True, null=True, blank=True)
    expired = models.DateTimeField(_(u'истекает'), auto_now=False, auto_now_add=False, null=True, blank=True)
    fields_for_moderation = models.CharField(_(u'поля, требующие проверки модератором'), max_length=100, null=True, blank=True)

    modified_calendar = models.DateTimeField(_(u'время обновления календаря'), null=True, auto_now=False,
                                             auto_now_add=False)

    xml_id = models.CharField(_(u'индентификатор в XML'), max_length=50, null=True)
    iframe_url = models.URLField(_(u'Ссылка на 3D тур или видео'), blank=True, null=True, max_length=255)

    international_catalog = models.PositiveSmallIntegerField(_(u'каталог зарубежной недвижимости'), choices=ad_choices.INTERNATIONAL_CATALOG_CHOICES, null=True, blank=True)

    contact_person = models.CharField(_(u'владелец/контактное лицо (для агентств)'), max_length=100, blank=True, null=True)

    has_photos = models.BooleanField(verbose_name=_(u'У объявления есть фото?'), default=False)

    facilities_array = ArrayField(models.IntegerField(), verbose_name=u'денормализованные удобства', blank=True, null=True)

    without_commission = models.BooleanField(verbose_name=_(u'Без комиссии'), default=False)

    # custom admin filters
    user.isnull_filter_spec = True

    objects = ad_objects_manager

    class Meta:
        verbose_name = u'объявление'
        verbose_name_plural = u'объявления недвижимости'
        ordering = ['-pk']
        index_together = [
            ["region", "property_type", "rooms"], # для фильтров в поиске на сайте
            ["region", "has_photos"], # для фильтров в поиске на сайте
            ["user", "created"], # вероятно для админки
            ["vip_type", "updated", "basead_ptr"], # для сортировки в поиске на сайте
        ]

    # Грязный хак: # из-за триггеров постгреса UPDATE не возвращает количество обновленных строк,
    # а django пытается сделать следом INSERT и создает дубль
    def _do_update(self, *args, **kwargs):
        super(Ad, self)._do_update(*args, **kwargs)
        return Ad.objects.filter(pk=self.pk).count()

    def __unicode__(self):
        title = self.addr_street
        if title and self.addr_house:
            title += ', %s' % self.addr_house
        return title if title else self.address.replace(u"Украина, ", "")

    def classname(self):
        return self.__class__.__name__.lower()

    def get_full_title(self, limit=None):
        words = [self.get_property_type_display(), self.addr_street, self.addr_house, '-', self.price, self.get_currency_display()]

        # чтобы можно было отбросить часть информациии из названия
        if limit:
            words = words[:limit]

        if self.property_type in ['flat', 'house']:
            words.insert(0, u'%sк' % self.rooms)

        return ' '.join(map(unicode, filter(None, words)))

    def get_absolute_url(self):
        if not self.pk:
            return "#not-saved"

        if not self.region_id:
            return "#region-error"

        view_kwargs = {'deal_type': self.deal_type, 'id': self.pk}
        region_slug = self.region.get_region_slug()
        if region_slug:
            view_kwargs['region_slug'] = region_slug

        return self.region.get_host_url('ad-detail', kwargs=view_kwargs)

    def get_bank_url(self):
        if not self.region_id:
            return "#region-error"

        from bank.models import convert_to_bank

        kwargs = {
            'property_type': convert_to_bank(self.property_type),
            'id': self.pk
        }
        region_slug = self.region.get_region_slug()
        if region_slug:
            kwargs['regions_slug'] = region_slug

        return self.region.get_host_url('bank-ad-detail', host='bank', kwargs=kwargs)

    def prepare_usercard(self, host_name, traffic_source=None):
        usercard = {}

        if self.user_id:
            usercard['profile_image'] = self.user.image
            usercard['callcenter'] = False
            usercard['show_message_button'] = self.user.show_message_button

            if self.bank_id:
                usercard['email'] = 'bank@mesto.ua'
                usercard['skype'] = 'bankmestoua'
                usercard['profile_image'] = self.bank.logo

                if host_name == 'bank':
                    usercard['phone'] = '+38 (044) 228 88 48'
                else:
                    usercard['phone'] = '+38 (044) 384 07 09'

            elif self.newhome_layouts.exists() and self.user.has_active_leadgeneration('newhomes'):
                from ppc.models import ProxyNumber

                phones = ProxyNumber.get_numbers(
                    self.user, 'newhomes', traffic_source, newhome=self.newhome_layouts.first().newhome)
                usercard['phone'] = pprint_phones(phones, delimiter="<br/>", extension='p%s' % str(self.id).zfill(8))
                # todo: Отображать номер телефона только в случае достаточности средств для получения звонка.
                # todo: Внимание! В шаблоне при выключении этой опции показываются обычные телефоны пользователя
                usercard['phone_for_lead'] = True

                usercard['show_message_button'] = False
                usercard['show_lead_button'] = True

            else:
                realtor = self.user.realtors.filter(is_active=True).first()
                if realtor:
                    if realtor.is_admin:
                        usercard['profile_image'] = realtor.agency.logo
                        usercard['working_hours'] = realtor.agency.working_hours
                        if realtor.agency.show_in_agencies:
                            if self.user.has_active_leadgeneration('ads') or self.user.has_active_plan():
                                usercard['all_ads_button'] = (
                                    reverse('professionals:agency_profile', args=[realtor.agency_id]),
                                     _(u'Объявления агентства')
                                )
                    else:
                        if self.user.has_active_leadgeneration('ads') or self.user.has_active_plan():
                            usercard['all_ads_button'] = (
                                reverse('professionals:realtor_profile', args=[realtor.agency_id, realtor.user_id]),
                                 _(u'Объявления риелтора')
                            )

                    usercard['contact_person'] = self.contact_person or self.user.get_full_name()

                if self.user.has_active_leadgeneration('ads'):
                    from ppc.models import ProxyNumber

                    phones = ProxyNumber.get_numbers(self.user, self.deal_type, traffic_source)
                    usercard['phone'] = pprint_phones(phones, delimiter="<br/>", extension='p%s' % str(self.id).zfill(8))
                    # todo: Отображать номер телефона только в случае достаточности средств для получения звонка.
                    # todo: Внимание! В шаблоне при выключении этой опции показываются обычные телефоны пользователя
                    usercard['phone_for_lead'] = True
                    usercard['phone_with_ivr'] = not self.user.leadgeneration.dedicated_numbers

                    usercard['show_message_button'] = False
                    usercard['show_lead_button'] = True

                else:
                    phones = [relation.phone_id for relation in self.phones_in_ad.all()]

                    # если не телефона в объявлении, то берем телефоны из профиля юзера, а если и там нет, то из профила админа агентства
                    if not phones:
                        phones = self.user.phones.all().values_list('number', flat=True)
                        if not phones and realtor and not realtor.is_admin:
                            agency_admin = realtor.agency.realtors.filter(is_admin=True, is_active=True).first()
                            if agency_admin:
                                phones = agency_admin.user.phones.values_list('number', flat=True)

                    usercard['phone'] = pprint_phones(phones, delimiter="<br/>")

                    if self.get_numbers_for_sms():
                        usercard['show_lead_button'] = True

                    if self.user.show_email:
                        usercard['email'] = self.user.email
        else:
            usercard['phone'] = pprint_phones([relation.phone_id for relation in self.phones_in_ad.all()], delimiter="<br/>")

        return usercard

    # получает первый подходящий укранский сотовый номер для отправки смс
    def get_numbers_for_sms(self):
        # сохранена оптимизация (из-за использования метода в prepare_usercard):
        # запрос в базу self.user.phones.all() выполнялся только когда у самого объявления нет телефонов, пригодных для смс
        cleaned_ad_phones = clean_numbers_for_sms(phone.number for phone in self.phones.all())
        if cleaned_ad_phones:
            return cleaned_ad_phones[:1]
        else:
            return self.user.get_numbers_for_sms()[:1]

    def get_converted_price(self, currency, rates=None, approximately=False):
        if self.currency == currency:
            return self.price
        else:
            if rates is None:
                rates = get_currency_rates()

            coverted_price = int( float(self.price) * rates[self.currency] / rates[currency] )
            round_level = 0 if not approximately else (len(str(coverted_price)) * -1 + 3)
            return int( round(coverted_price, round_level) )

    def reserved_json(self):
        if not self.pk:
            return {}
        else:
            return {
                'reserved': json.dumps([r.date.strftime('%Y-%m-%d') for r in self.reserved.all()]),
            }

    def update_reserved_from_json(self, reserved_json):
        new_dates = []
        for date in reserved_json:
            new_dates.append(date)
            ReservedDate.objects.get_or_create(basead=self, date=date)

        ReservedDate.objects.filter(basead=self).exclude(date__in=new_dates).delete()

    # конвертация валют
    def set_uah_prices(self):
        rates = get_currency_rates()
        self.price_uah = self.price * rates[self.currency]

    def moderate(self, action, reject_status, moderator):
        now = datetime.datetime.now()
        open_moderations = self.moderations.filter(moderator__isnull=True)

        if open_moderations.exists():
            moderation = open_moderations[0]
        else:
            moderation = Moderation(basead=self, start_time=now)

        # выходим, если не был указана причина отклонения или подтверждается объявление, у которого и так всё хорошо
        if (action == 'reject' and not reject_status) \
                or (action == 'accept' and not self.moderation_status and not moderation.id and not self.fields_for_moderation):
            return

        self.fields_for_moderation = None
        moderation.moderator = moderator
        moderation.end_time = now

        # объявление отклоняется, только если указывается новый статус
        if action == 'reject':
            moderation.new_status = self.moderation_status = int(reject_status)
            if reject_status >= 20:
                self.status = 210

        # если объявления было отклонено и мы его пропускаем, то очищаем статус модерации
        if action == 'accept' and self.moderation_status:
            self.moderation_status = None

        moderation.save()
        self.save()

    def is_favorite(self, user):
        favorite_properties_ids = cache.get('saved_properties_for_user%d' % user.id, [])
        return self.pk in favorite_properties_ids

    @property
    def is_exported_to_ria(self):
        return self.id in cache.get('export_ria_ads', [])

    def get_first_photo(self):
        for photo in self.photos.all():
            if photo.image:
                return photo
        return no_photo

    def has_deactivation_reason(self):
        if self.deal_type == 'sale':
            for deactivation in self.deactivations.all():
                if not deactivation.returning_time:
                    return deactivation

    def get_duplicates_queryset(self):
        import math
        hashes = [photo.hash for photo in self.photos.all()]
        duplicate_threshold = min(3, math.ceil(len(hashes)*0.66))
        duplicate_ad_ids = set(Photo.objects.filter(hash__in=hashes).values('basead').order_by().annotate(cnt=Count('basead')).filter(cnt__gt=duplicate_threshold).values_list('basead', flat=True))
        return Ad.objects.filter(pk__in=duplicate_ad_ids).exclude(pk=self.pk).exclude(moderation_status=22)

    def get_coords(self):
        if settings.MESTO_USE_GEODJANGO:
            if self.point:
                return self.point.coords
        else:
            if self.coords_x:
                return self.coords_x, self.coords_y

    def update_vip(self):
        from paid_services.models import VipPlacement

        vipplacement = self.vipplacements.filter(is_active=True).first()
        if vipplacement:
            if self.vip_type != vipplacement.type:
                self.vip_type = vipplacement.type
        else:
            self.vip_type = 0

        if 'vip_type' in self.get_dirty_fields():
            self.save()


class DeactivationForSale(models.Model):
    reason = models.PositiveIntegerField(_(u'причина снятия с продажи'), choices=ad_choices.DEACTIVATION_REASON_CHOICES)
    basead = models.ForeignKey(BaseAd, verbose_name=u'объявление', related_name='deactivations', null=True, on_delete=models.SET_NULL)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'пользователь'), db_index=True)
    deactivation_time = models.DateTimeField(_(u'время деактивации'), auto_now=False, default=datetime.datetime.now)
    returning_time = models.DateTimeField(_(u'время возврата к публикации'), null=True, blank=True)

    class Meta:
        verbose_name = u'причина деактивации'
        verbose_name_plural = u'причины деактивации'


from django.templatetags.static import static

class NoPhotoImage(object):
    @property
    def thumbnails(self):
        return (lambda alias: static('img/no-photo.png'))

class NoPhoto(object):
    image = NoPhotoImage()

    def smart_thumbnail(self, alias):
        return static('img/no-photo.png')

no_photo = NoPhoto()


@receiver(post_save, sender=Ad)
def check_rejection_status(sender, instance, **kwargs):
    rejected_statuses = [10, 11, 12, 13, 14, 15, 20]
    if instance.moderation_status in rejected_statuses and instance.user and 'moderation_status' in instance.get_dirty_fields():

        # возможно такой статус из-за ошибок геокодера - слать уведомление не нужно
        if instance.moderation_status == 11 and not instance.region:
            return

        Notification(type='ad_rejected', user=instance.user, object=instance).save()


@receiver(post_save, sender=Ad)
def process_address(sender, instance, **kwargs):
    # только для парсера
    if instance.xml_id and not instance.user_id:
        dirty_fields = instance.get_dirty_fields()
        if 'address' in dirty_fields or 'addr_country' in dirty_fields:
            import tasks
            tasks.process_address(instance.pk)


@receiver(pre_save, sender=Ad)
def dirty_ad(instance, **kwargs):
    obj = instance

    def df():
        return obj.get_dirty_fields()

    def df_keys():
        return df().keys()

    if obj.title == '':
        if obj.rooms:
            obj.title += _(u'%s-комн. ') % obj.rooms
        obj.title += obj.get_property_type_display()

    if 'price' in df_keys():
        obj.set_uah_prices()  # установка цен в гривнах

    for key in df_keys():
        if key.startswith('addr_') and getattr(obj, key) is not None:
            obj.address = obj.build_address()

    if 'address' in df_keys() or 'addr_country' in df_keys():
        if obj.xml_id and not obj.user_id:
            # для объявлений из парсера присвоение региона происходит в задаче (см. post_save)
            obj.region = None
        else:
            if not obj.process_address():
                obj.moderation_status = 11  # не найден регион

    # список полей на которые нужно обращать внимание при изменении пользователем
    important_field = ['deal_type', 'property_type', 'addr_city', 'phone_1', 'phone_2', 'addr_street',
                       'price', 'currency', 'description', 'iframe_url']

    # при создании объявления нет смысла перечислять все поля, поэтому используем ключевое слово __all__
    if not obj.pk:
        obj.fields_for_moderation = '__all__'
    else:
        # заполняем список полей для модерации из изменных
        fields_for_moderation_set = set(df_keys()) & set(important_field)
        if fields_for_moderation_set:
            # добавляем поля, которые ранее нужно было проверить
            fields_for_moderation_set |= set((obj.fields_for_moderation or '').split(','))
            obj.fields_for_moderation = ','.join(filter(None, fields_for_moderation_set))

    # если объявление было отклонено ранее, то отправляем его на пре-модерацию
    # Важно: за исключением статуса 20, т.к. блокировка делается без возможности возврата объявления на модерацию
    # if obj.fields_for_moderation and (10 <= obj.status < 20):
    #     obj.status = 0

    # блокировка публикации объявления, если предыдущая модерация была с отклонением
    # if obj.pk and obj.status == 1 and obj.moderations.exists() and 10 <= obj.moderations.all()[0].new_status <= 20:
    #     obj.status = obj.moderations.all()[0].new_status


# проверяем флаг публикации
@receiver(pre_save, sender=Ad)
def publication_check(sender, instance, **kwargs):
    # объявления юзеров, что не с импорта,
    # отредактированные в кабинете или даже новые
    # публикуются автоматически при активном тарифе с доступным лимитом
    if instance.user and not instance.xml_id and (not instance.pk or getattr(instance, '_edit_from_cabinet', False)) \
            and instance.addr_country == 'UA' and instance.user.can_activate_ad():
        # Новые объявления от пользователей
        instance.status = 1

    elif instance.user and instance.newhome_layouts.exists() and not instance.pk \
            and instance.user.has_active_leadgeneration('newhomes') and \
            instance.newhome_layouts.first().has_available_flats:
        # Новые объявления на основе планировок новостроек
        instance.status = 1

    instance.is_published = (instance.status == 1 and not instance.moderation_status)


# оптравляем на модерацию, если объявление не скрыто и у него есть непроверенные поля
# заблокированнные объявлений (moderation_status=20) на модерацию не возвращаются
@receiver(post_save, sender=Ad)
def on_status_change(sender, instance, **kwargs):
    if instance.user and instance.status == 1 and instance.fields_for_moderation and instance.moderation_status != 20:
        try:
            moderation, create = Moderation.objects.get_or_create(basead=instance, moderator=None)
        except Moderation.MultipleObjectsReturned:
            moderations = Moderation.objects.filter(basead=instance, moderator__isnull=True).order_by('id')
            moderation = moderations[0]
            moderations.exclude(pk=moderation.pk).delete()

    # при снятии объявления с пубилкации удаляем открытые заявки на модерацию
    if 'status' in instance.get_dirty_fields() and instance.status != 1:
        instance.moderations.filter(moderator=None).delete()


# обновление количеста активных объявлений пользователя
@receiver(post_delete, sender=Ad)
@receiver(post_save, sender=Ad)
def update_user_ads_count(sender, instance, **kwargs):
    if instance.user_id and not instance.xml_id:
        instance.user.update_ads_count()


@receiver(post_delete, sender=Ad)
@receiver(post_save, sender=Ad)
def update_user_region(sender, instance, **kwargs):
    if instance.user_id and (not instance.xml_id):
        from custom_user.models import update_region
        update_region(instance.user)


class ViewsCount(models.Model):
    date = models.DateField(u'дата')
    basead = models.ForeignKey(BaseAd, verbose_name=u'объявление', related_name='viewscounts')
    is_archived = models.BooleanField(u'скрыт для пользователя?', default=False)
    is_fake = models.BooleanField(u'фэйковые просмотры?', default=False)
    detail_views = models.PositiveIntegerField(u'просмотры страницы объявления', default=0)
    contacts_views = models.PositiveIntegerField(u'просмотры контактов', default=0)

    class Meta:
        verbose_name = u'просмотр объявления'
        verbose_name_plural = u'просмотры объявлений'


def normalize_image(image):
    if image.format == 'JPEG':
        # поворот по EXIF
        sorl_engine = Engine()
        image = sorl_engine._orientation(image)

    # в последствии изображения сохраняются в формате JPEG - без прозрачности
    # изображения с прозрачностью накладываем на белый непрозрачный фон, иначе
    # PIL при convert('RGB') или при сохранении как JPEG не сделает никакой магии с фонами, а просто отбросит альфа-канал,
    # например, http://stackoverflow.com/questions/9166400/convert-rgba-png-to-rgb-with-pil
    if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
        white_background = Image.new('RGBA', image.size, (255, 255, 255))
        image = Image.alpha_composite(white_background, image.convert('RGBA'))

    image = image.convert('RGB')

    if max(image.size) > settings.IMAGE_MAX_SIZE:
        image = resize_image(image, size=(settings.IMAGE_MAX_SIZE,)*2, crop=False)

    return image


class NormalizedImageFieldFile(ImageFieldFile):
    def save(self, name, content, save=True):
        image = Image.open(content.file)
        content = save_to_jpeg_content(normalize_image(image))
        super(NormalizedImageFieldFile, self).save(name, content, save)
    save.alters_data = True


class NormalizedImageField(models.ImageField):
    attr_class = NormalizedImageFieldFile


# TODO: написать умный комментарий как мы до этого докатились
class ExtendedImageFieldFile(ThumbnailedImageFieldFile, NormalizedImageFieldFile):
    pass


# порядок наследования важен, см. конструктор ThumbnailedImageField
class ExtendedImageField(ThumbnailedImageField, NormalizedImageField):
    attr_class = ExtendedImageFieldFile

    def update_dimension_fields(self, instance, force=False, *args, **kwargs):
        if settings.MESTO_UPDATE_DIMENSION_FIELDS_FOR_PHOTOS:
            old_dimension = [getattr(instance, self.width_field), getattr(instance, self.height_field)]
            try:
                super(ExtendedImageField, self).update_dimension_fields(instance, force, *args, **kwargs)
            except IOError:
                pass
            else:
                new_dimension = [getattr(instance, self.width_field), getattr(instance, self.height_field)]
                if instance.pk and all(new_dimension) and new_dimension != old_dimension:
                    instance.is_dimension_changed = True
                    instance.save()


from utils.thumbnail import WATERMARK

PHOTO_THUMBNAILS = {
    'prefix': 'ad/photo',
    'aliases': {
        'xs': {'size': (96, 72), 'crop': True},
        'md': {'size': (288, 192), 'crop': True},
        'lg': {'size': (640, 640), 'watermark': WATERMARK},
        'full': {'size': (1200, 1200), 'watermark': WATERMARK},
    }
}


class Photo(models.Model):
    basead = models.ForeignKey(BaseAd, verbose_name=_(u'недвижимость'), related_name='photos', null=True, blank=True, on_delete=models.SET_NULL)
    order = models.PositiveIntegerField(_(u'порядковый номер'))
    source_url = models.CharField(_(u'ссылка на источник'), max_length=512, blank=True)
    image = ExtendedImageField(_(u'фотография'), upload_to=make_upload_path, blank=True, null=True,
                               thumbnails=PHOTO_THUMBNAILS, width_field='width', height_field='height')
    caption = models.CharField(_(u'подпись к фотографии'), max_length=255, null=True)
    width = models.PositiveIntegerField(_(u'ширина фото'), default=0)
    height = models.PositiveIntegerField(_(u'высота фото'), default=0)
    hash = models.CharField(u'хэш фото', max_length=16, null=True, db_index=True)

    def __unicode__(self):
        if self.pk:
            return u'Фото №%(pk)d недвижимости №%(ad_id)s' % {'pk': self.pk, 'ad_id': self.basead_id}
        else:
            return u'Удаленное фото'

    class Meta:
        verbose_name = u'фотография'
        verbose_name_plural = u'фотографии'
        ordering = ['order']

    # вычисление хеша фотографии по превью (смысла запускать в сигналах нет, т.к. превью генерируется асинхронно)
    def update_hash(self):
        from utils.hash_image import dhash
        try:
            file = default_storage.open(self.image.thumbnailer.get_path('xs'))
        except IOError:
            return
        else:
            hash = dhash(Image.open(file))
            Photo.objects.filter(pk=self.pk).update(hash=hash)
            return hash

    @classmethod
    def find_ads_duplicates(cls, duplicate_limit=4, force=False):
        groups = cache.get('group_of_ad_duplicates')
        if not groups or force:
            from collections import Counter

            def ref_check(val, list):
                avg = sum(list)/float(len(list))
                return (avg * 0.7) < val < (avg * 1.3)

            week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
            hashes_qs = Photo.objects.filter(basead__isnull=False, hash__isnull=False).values('hash').annotate(cnt=Count('hash')).filter(cnt__gt=duplicate_limit)

            if getattr(settings, 'MESTO_DUPLICATES_IGNORE_HASH', None):
                hashes_qs = hashes_qs.exclude(hash__in=settings.MESTO_DUPLICATES_IGNORE_HASH)

            cntr = Counter({hash['hash']: hash['cnt'] for hash in hashes_qs})
            groups = []
            for ad_id, hash in Photo.objects.filter(basead__ad__updated__gt=week_ago, hash__in=dict(cntr).keys()).order_by('hash').values_list('basead', 'hash'):
                rate = cntr[hash]
                hash_group = None

                # print dict(enumerate(groups)).keys()
                for i, group in enumerate(groups):
                    if (hash in group['hashes'] or ad_id in group['ad_ids']) and ref_check(rate, group['rates']):
                        hash_group = group
                        break

                if not hash_group:
                    hash_group = {'ad_ids': set(), 'hashes': set(), 'rates': [], 'ads': [], 'photos': []}
                    groups.append(hash_group)

                hash_group['ad_ids'].add(ad_id)
                if hash not in hash_group['hashes']:
                    hash_group['hashes'].add(hash)
                    hash_group['rates'].append(rate)

            groups = sorted(groups, key=lambda x: len(x['ad_ids']), reverse=True)
            cache.set('group_of_ad_duplicates', groups, 60*60*24*7)

        return groups

    def download(self):
        if not self.image:
            request = requests.get(self.source_url, timeout=10, verify=False)
            self.image.save('temp', ContentFile(request.content))

    def get_fake_crc(self):
        if self.image:
            import zlib
            return zlib.crc32(self.image.url)

    def smart_thumbnail(self, alias):
        return self.image.thumbnailer.get_url(alias)


@receiver(post_delete, sender=Photo)
@receiver(post_save, sender=Photo)
def ad_photos_updated(sender, instance, **kwargs):
    # блокировка на случай сохранения сразу нескольких фотографий
    cache_key = 'ad-%s-photos-update-lock' % instance.basead_id

    # instance.basead.ad добавлен в условие, т.к. при удалении объявлений объект Ad удаляется раньше, чем Photo
    if not cache.get(cache_key) and getattr(instance.basead, 'ad', None):
        cache.set(cache_key, True, 10)

        ad = instance.basead.ad

        # добавлеяем "photos" в список измененных полей для модерции, если это не обновление размеров
        if not hasattr(instance, 'is_dimension_changed'):
            fields_for_moderation_set = set((ad.fields_for_moderation or '').split(',')) | set(['photos'])
            ad.fields_for_moderation = ','.join(filter(None, fields_for_moderation_set))

        ad.has_photos = ad.photos.exists()

        if ad.is_dirty():
            ad.save()


@receiver(post_delete, sender=Photo)
def post_delete_photo(sender, instance, **kwargs):
    if instance.image:
        instance.image.thumbnailer.delete()
        default_storage.delete(instance.image.name)


@receiver(post_save, sender=Photo)
def post_save_photo(sender, instance, created, **kwargs):
    import tasks
    if created:
        if instance.source_url:
            tasks.download_photo(instance.id, 1)

        elif instance.image:
            if instance.basead.ad.user_id:
                tasks.process_photo_priority(instance.id)
            else:
                tasks.process_photo(instance.id)

        else:
            raise Exception('WTF with this photo?')


class ReservedDate(models.Model):
    class Meta:
        verbose_name = u'занятый день'
        verbose_name_plural = u'занятые дни'

    basead = models.ForeignKey(BaseAd, related_name='reserved')
    date = models.DateField()

    def __unicode__(self):
        return _(u'%(date)s - объявление #%(id)s') % {'date': self.date.strftime('%d.%m.%Y'), 'id': self.basead_id}


class Phone(models.Model):
    class Meta:
        verbose_name = u'телефон'
        verbose_name_plural = u'телефоны'

    number = models.CharField(u'номер телефона', max_length=12, primary_key=True)
    is_agency = models.BooleanField(u'номер агентства', default=False)
    is_banned = models.BooleanField(u'забанен', default=False)
    ignore_in_parser = models.BooleanField(u'игнорировать в парсере', default=False,
                                           help_text=u'объявления с этим телефоном не будут импортироваться')

    def __unicode__(self):
        return self.number


class PhoneInAd(models.Model):
    class Meta:
        verbose_name = u'телефон в объявлении'
        verbose_name_plural = u'телефоны в объявлении'
        unique_together = (('phone', 'basead'),)
        ordering = ['order']

    phone = models.ForeignKey(Phone, verbose_name=_(u'телефон'), related_name='phones_in_ad')
    basead = models.ForeignKey(BaseAd, verbose_name=_(u'объявление'), related_name='phones_in_ad')
    order = models.PositiveIntegerField(_(u'порядковый номер'))


class BaseModeration(models.Model):
    start_time = models.DateTimeField(_(u'дата отправки на модерацию'), auto_now_add=True)
    end_time = models.DateTimeField(_(u'дата снятия с модерации'), null=True, blank=True)
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_(u'модератор'), blank=True, null=True,
        related_name='%(app_label)s_%(class)s_moderations'
    )
    new_status = models.PositiveIntegerField(
        _(u'новый статус'), choices=ad_choices.MODERATION_STATUS_CHOICES, null=True, blank=True
    )

    @classmethod
    def get_stats_by_user(cls, user_id, **qs):
        from collections import Counter
        stats = Counter()
        new_statuses = cls.objects.filter(**qs).values_list('new_status', flat=True)
        for status in new_statuses:
            stats['total'] += 1
            if status == 22:
                stats['duplicates'] += 1
            elif status is None:
                stats['good'] += 1
            else:
                stats['bad'] += 1

        return stats

    class Meta:
        abstract = True


class Moderation(BaseModeration):
    class Meta:
        verbose_name = u'объявление на модерации'
        verbose_name_plural = u'объявления на модерации'
        ordering = ['-start_time']

    basead = models.ForeignKey(BaseAd, verbose_name=_(u'недвижимость'), related_name='moderations')

    def __unicode__(self):
        return u'ID %s от %s' % (self.basead_id, self.start_time)

    @classmethod
    def get_stats_by_user(cls, user_id, **qs):
        return super(Moderation, cls).get_stats_by_user(user_id, **{'basead__ad__user_id': user_id})


class SubwayLine(models.Model):
    name = models.CharField(verbose_name=_(u'Название ветки метро'), max_length=100, blank=True, default='')
    order = models.PositiveIntegerField(_(u'порядковый номер'), default=0)
    color = models.CharField(verbose_name=_(u'HEX-цвет ветки'), max_length=7, default='#000000')
    city = models.ForeignKey('ad.Region', verbose_name=_(u'Город'))

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ('order',)
        verbose_name_plural = u'Метро'
        verbose_name = u'Ветку'


if settings.MESTO_USE_GEODJANGO:
    subway_station_objects_manager = models.GeoManager()
else:
    subway_station_objects_manager = models.Manager()

class SubwayStation(models.Model):
    subway_line = models.ForeignKey('ad.SubwayLine', verbose_name=_(u'Ветка метро'), related_name='stations')
    order = models.PositiveIntegerField(_(u'порядковый номер'), default=0)
    name = models.CharField(verbose_name=_(u'Название станции метро'), max_length=100, blank=True, default='')
    # point = models.PointField(u'точка на карте', null=True, blank=True)
    coords_x = models.FloatField(_(u'долгота/longitude'), null=True, blank=True)
    coords_y = models.FloatField(_(u'широта/latitude'), null=True, blank=True)
    slug = models.SlugField(_(u'часть URL-а'), max_length=100, blank=True, null=True)

    objects = subway_station_objects_manager

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ('order',)
        verbose_name_plural = u'Станции метро'
        verbose_name = u'станцию'


class SearchCounter(models.Model):
    class Meta:
        verbose_name = u'счетчик поиска'
        verbose_name_plural = u'счетчики поисков'
        index_together = ['date', 'deal_type', 'region']

    date = models.DateField(u'дата', auto_now_add=True)
    region = models.ForeignKey('ad.Region', verbose_name=u'регион')
    deal_type = models.CharField(u'тип сделки', max_length=20, choices=ad_choices.DEAL_TYPE_CHOICES)
    property_type = models.CharField(u'тип недвижимости', max_length=20, choices=ad_choices.PROPERTY_TYPE_CHOICES, null=True)
    rooms = ArrayField(models.PositiveIntegerField(u'количество комнат', choices=ad_choices.ROOMS_CHOICES))
    without_commission = models.BooleanField(u'без комиссии')
    area_from = models.IntegerField(u'площадь от', null=True)
    area_to = models.IntegerField(u'площадь до', null=True)
    price_from = models.IntegerField(u'цена от', null=True)
    price_to = models.IntegerField(u'цена до', null=True)
    currency = models.CharField(u'валюта цены', choices=ad_choices.CURRENCY_CHOICES, max_length=3)
    facilities = ArrayField(models.PositiveIntegerField(u'удобства'))
    other_parameters = models.TextField(u'другие параметры', null=True) # нельзя добавлять blank, используется проверка на null
    searches_first_page = models.PositiveIntegerField(u'поиски - первая страница', default=0)
    searches_all_pages = models.PositiveIntegerField(u'поиски - все страницы', default=0)

    # хак для маркетологов, просмотр объявления при переходе с lun.ua считается поиском
    is_ad_view_referred_by_lunua = models.BooleanField(u'просмотр объявления при переходе с lun.ua?', default=False)

