# coding: utf-8

from django.conf import settings
from django.db.models import Q
from django.template.loader import get_template, render_to_string
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.urls import translate_url

from collections import defaultdict
from difflib import get_close_matches

from ad.models import Ad, Region, DeactivationForSale
from ad.models import PROPERTY_COMMERCIAL_TYPE_CHOICES
from ad.choices import PROPERTY_TYPE_CHOICES, CURRENCY_CHOICES
from paid_services.models import CatalogPlacement
from utils.storage import overwrite
from utils.currency import get_currency_rates
from custom_user.models import User

import time
import math
import os
import sys
import codecs
import traceback

from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile

import pymorphy2


class BadProperty(Exception):
    pass

class BaseFeed(object):
    autofields = []
    name = None
    template = None
    comment = None
    limit = None

    def __init__(self, show_progress):
        self.show_progress = show_progress

    def queryset(self):
        sold_ads = DeactivationForSale.objects.filter(basead__isnull=False).filter(returning_time__isnull=True).values_list('basead', flat=True)
        return Ad.objects.filter(is_published=True, user__isnull=False, region__isnull=False).exclude(id__in=sold_ads).prefetch_related('region', 'photos')

    def generate(self):
        self.start_time = time.time()

        try:
            template_filename = self.template or ('%s.jinja.xml' % self.name)
            backend_template = get_template('export/%s' % template_filename)
            context ={
                'feed': self,
                'now': datetime.now(),
            }
            filename = 'export/%s.xml' % self.name

            # создаем временный файл и в него рендерим шаблон
            tmpfile = NamedTemporaryFile(delete=False)
            # возвращаемый лоадером django_jinja.backend.Template не умеет выполнять поточный рендеринг,
            # используется его атрибут - низкоуровневый шаблон django_jinja.base.Template(jinja2.Template)
            backend_template.template.stream(context).dump(tmpfile, encoding='utf-8')

            # копируем файл в storage
            overwrite(filename, tmpfile)

            tmpfile.close()
            os.unlink(tmpfile.name)

            info = {
                'comment': self.comment,
                'properties': len(self.rendered_items),
                'link': default_storage.url(filename),
                'time': datetime.now(),
            }

            export_info = cache.get('export_status', {})
            export_info[self.name] = info
            cache.set('export_status', export_info, 7 * 24 * 3600)
        except:
            print '%-15s    EXCEPTION' % self.name
            traceback.print_exc()
        else:
            print '%-15s   %7.2f sec    %7d ads' % (self.name, time.time() - self.start_time, len(self.rendered_items))

    def iterate_items(self):
        items_to_process = self.queryset().count()
        if self.limit and self.limit < items_to_process:
            items_to_process = self.limit

        chunk_size = 500
        chunks_total = int(math.ceil(items_to_process / float(chunk_size)))
        chunks_processed = 0
        processed_items = 0

        self.rendered_items = []

        while chunks_processed < chunks_total:
            items = list(self.queryset()[chunk_size * chunks_processed: chunk_size * (chunks_processed + 1)])

            for item in items:
                try:
                    self.extra(item)
                except BadProperty:
                    pass
                else:
                    self.clean_item_photos(item)
                    self.rendered_items.append(item.id)
                    yield item

                    if self.limit and len(self.rendered_items) >= self.limit:
                        raise StopIteration()

                processed_items += 1
                if self.show_progress and processed_items % 10 == 0:
                    sys.stdout.write('%-15s    %d/%d\r' % (self.name, processed_items, items_to_process))
                    sys.stdout.flush()

            chunks_processed += 1

    def clean_item_photos(self, item):
        item.cleaned_photos = []
        for photo in item.photos.all():
            if photo.image: # and default_storage.exists(photo.image.name):
                item.cleaned_photos.append(photo)

    def extra(self, item):
        item.location = item.region.get_location()
        if 'country' not in item.location:
            raise BadProperty
        return item


class LunUaBaseFeed(BaseFeed):
    template = 'lun.jinja.xml'
    autofields = (
        ('title', 'get_full_title'),
        ('realty_type', 'get_property_type_display'),
        ('price', 'price'),
        ('currency', 'currency'),
        ('floor', 'floor'),
        ('floor_count', 'floors_total'),
        ('total_area', 'area'),
        ('living_area', 'area_living'),
        ('kitchen_area', 'area_kitchen'),
        ('room_count', 'rooms'),
        ('room_type', 'get_building_layout_display'),
        ('house_type', 'get_building_type_display'),
        ('url', 'get_absolute_url'),
    )

    def queryset(self):
        return super(LunUaBaseFeed, self).queryset().filter(addr_street__gt='').prefetch_related('phones')

    def extra(self, item):
        super(LunUaBaseFeed, self).extra(item)
        item.url_uk = translate_url(item.get_absolute_url(), 'uk')


class LunDaily(LunUaBaseFeed):
    name = 'lun-1'
    comment = u'lun.ua (посуточная)'

    def queryset(self):
        return super(LunDaily, self).queryset().filter(deal_type='rent_daily')

class LunOther(LunUaBaseFeed):
    name = 'lun-2'
    comment = u'lun.ua (кроме посуточной)'

    def queryset(self):
        return super(LunOther, self).queryset().exclude(deal_type='rent_daily')

class Trovit(BaseFeed):
    name = 'trovit'
    comment = u'TROVIT'

    def __init__(self, *args, **kwargs):
        self.provinces_cache = {}
        self.morph = pymorphy2.MorphAnalyzer()
        self.morph_cache = {}
        super(Trovit, self).__init__(*args, **kwargs)

    def queryset(self):
        return super(Trovit, self).queryset().filter(coords_x__isnull=False, deal_type__in=['rent', 'sale'])

    def extra(self, item):
        super(Trovit, self).extra(item)

        if item.region_id in self.provinces_cache:
            province_slug = self.provinces_cache[item.region_id]
        else:
            province_slug = item.region.get_parents_as_queryset().filter(kind='province').values_list('slug', flat=True).first()
            self.provinces_cache[item.region_id] = province_slug

        if province_slug is None:
            raise BadProperty

        item.segmentation_text = province_slug

        self.extra_morphed_title(item)

    def extra_morphed_title(self, item):
        morph_key = (item.deal_type, item.property_type, item.rooms)
        morphed_title = self.morph_cache.get(morph_key, None)

        if morphed_title is None:
            action = {'rent': u'Сдается в аренду', 'sale': u'Продается'}[item.deal_type]
            morphed_title_parts = [action]

            property_type_text = item.get_property_type_display()
            property_type_words = property_type_text.split(' ')

            if item.property_type in ('flat', 'house') and item.rooms > 0:
                gender = self.morph.parse(property_type_words[-1])[0].tag.gender
                room_info = u'%d-%s' % (item.rooms, self.morph.parse(u'комнатный')[0].inflect({gender}).word)
                morphed_title_parts.append(room_info)

            morphed_property_type = u' '.join(self.morph.parse(word)[0].inflect({'nomn', 'sing'}).word for word in property_type_words)
            morphed_title_parts.append(morphed_property_type)

            morphed_title = u' '.join(morphed_title_parts)
            self.morph_cache[morph_key] = morphed_title

        item.morphed_title = morphed_title


# использует формат Яндекс-недвижимости
class Krysha(BaseFeed):
    name = 'krysha'
    comment = 'krysha.ua'
    autofields = (
        ('category', 'get_property_type_display'),
        # ('url', 'get_absolute_url'),
        ('rooms', 'rooms'),
        ('rooms-type', 'get_building_layout_display'),
        ('building-type', 'get_building_walls_display'),
        ('floor', 'floor'),
        ('floors-total', 'floors_total'),
        ('living-space', 'area_living', {'prefix':u'<value>', 'postfix':u'</value><unit>кв.м</unit>'}),
        ('kitchen-space', 'area_kitchen', {'prefix':u'<value>', 'postfix':u'</value><unit>кв.м</unit>'}),
    )

    def queryset(self):
        return super(Krysha, self).queryset().filter(
            addr_street__gt='',
            user__in=User.objects.filter(id__in=User.get_user_ids_with_active_ppk(), region__slug__in=[
                'kievskaya-oblast',
                'odesskaya-oblast',
                'hersonskaya-oblast',
                'hmelnitskaya-oblast'
            ]),
        ).prefetch_related('phones')


class BankFeed(BaseFeed):
    def queryset(self):
        return super(BankFeed, self).queryset().filter(bank__isnull=False, deal_type='sale', property_type__in=['flat', 'house', 'plot', 'commercial'])


class Prom(BankFeed):
    name = 'prom'
    comment = u'prom.ua'

    def __init__(self, *args, **kwargs):
        self.categories = {None: (1, u'недвижимость', None)}
        for id, type in enumerate(PROPERTY_TYPE_CHOICES, start=11):
            self.categories[type[0]] = (id, type[1], 1)
        for id, type in enumerate(PROPERTY_COMMERCIAL_TYPE_CHOICES, start=151):
            self.categories[type[0]] = (id, type[1], 15)
        rates = get_currency_rates()
        self.currencies = [(currency[0], rates[currency[0]]) for currency in CURRENCY_CHOICES]

        super(Prom, self).__init__(*args, **kwargs)

    def extra(self, item):
        super(Prom, self).extra(item)
        item.category_id = self.categories[item.property_type][0]
        if item.property_type == 'commercial':
            if item.property_commercial_type:
                item.category_id = self.categories[item.property_commercial_type][0]

class AddressUA(BankFeed):
    name = 'addressUA'
    comment = u'address.ua'


class Ria(BankFeed):
    name = 'ria'
    comment = u'dom.ria.com'
#    limit = 110

    def queryset(self):
        # queryset = super(Ria, self).queryset().exclude(
            # description__icontains='аукцион'
        # ).exclude(
            # description__icontains='выселени'
        # ).exclude(
            # description__icontains='торги'
        # ).exclude(
            # region__in=Region.objects.get(slug='karpaty').get_descendants(include_self=True)
        # ).filter(
            # region__in=Region.objects.get(static_url=';').get_descendants()
        # ).order_by('-id')


        # # попросили убрать объявления с dom.ria.ua
        # if settings.MESTO_DOMRIA_IGNORE_USERS:
            # queryset = queryset.exclude(user__in=settings.MESTO_DOMRIA_IGNORE_USERS)

        # # эти объявления вносятся вручную менеджерами банковской недвижимости через админку DOM.RIA.COM
        # if settings.MESTO_DOMRIA_IGNORE_ADS:
            # queryset = queryset.exclude(pk__in=settings.MESTO_DOMRIA_IGNORE_ADS)

        # # объявления, которые обязательно должны быть в фиде
        # if settings.MESTO_DOMRIA_PRIORITY_ADS:
            # queryset = queryset | Ad.objects.filter(id__in=settings.MESTO_DOMRIA_PRIORITY_ADS, is_published=True, status=1)
            # queryset = queryset.extra(select={'priority': "id IN (%s)" % ','.join(map(str, settings.MESTO_DOMRIA_PRIORITY_ADS))}).order_by('-priority', '-id')

        # return queryset

        if settings.MESTO_DOMRIA_PRIORITY_ADS:
            return super(Ria, self).queryset().filter(pk__in=settings.MESTO_DOMRIA_PRIORITY_ADS)
        else:
            return Ad.objects.none()

    def __init__(self, *args, **kwargs):
        super(Ria, self).__init__(*args, **kwargs)

        self.ria_data = defaultdict(lambda: defaultdict(list))
        with codecs.open(os.path.join(settings.BASE_DIR, 'data', 'ria_data.csv'), 'r', 'cp1251') as f:
            for lineno, line in enumerate(f, start=1):
                if line and line != 1:
                    district, district_ua, city, province, type = line.strip().split(';')
                    self.ria_data[province][district].append(city)

    def extra(self, item):
        super(Ria, self).extra(item)
        item.ria = {}
        self.extra_property_type(item)
        self.extra_location(item)

    def extra_property_type(self, item):
        if item.property_type in ('flat', 'house'):
            item.ria['property_type'] = item.get_property_type_display()
        elif item.property_type == 'plot':
            item.ria['property_type'] = u'земля коммерческого назначения'
        elif item.property_type == 'commercial':
            item.ria['property_type'] = {
                'office': u'офисное помещение',
                'storage': u'складские помещения',
                'ready_business': u'готовый бизнес',
            }.get(item.property_commercial_type, u'помещения свободного назначения')
        else:
            raise Exception('Wrong property type %s' % item.property_type)

    def extra_location(self, item):
        # область
        try:
            province = item.location['province']
        except KeyError:
            locality = item.location.get('locality', None)
            if locality == u'Киев':
                province = u'Киевская область'
            elif locality == u'Севастополь':
                province = u'автономная республика Крым'
            else:
                province = u'нет области'

        if u'Ровненская' in province:
            province = u'Ровенская'
            
        if u'крым' in province.lower():
            item.ria['province'] = u'Республика Крым'
        else:
            item.ria['province'] = province.replace(u'область', '').strip()

        # город/деревня проверка на наличие в базе РИА (ria_data)
        village = None
        if 'locality' in item.location:
            locality = item.location['locality']

            # на их сайте старое название Днепра и выдается ошибка при импорте
            if locality == u'Днепр':
                locality = u'Днепропетровск'

            cities = []
            for values in self.ria_data[item.ria['province']].values():
                cities.extend(values)

            matches = get_close_matches(locality, cities, cutoff=0.8)
            if matches:
                item.ria['city'] = matches[0]
            else:
                village = locality
        elif item.region.kind == 'village':
            village = item.region.name

        if village:
            for label in (u'коттеджный поселок', u'поселок городского типа', u'поселок', u'село', u'посёлок городского типа', u'посёлок'):
                village = village.replace(label, '')
            village = village.strip()

            matches = get_close_matches(village, self.ria_data[item.ria['province']].keys(), cutoff=0.8)
            if matches:
                village = matches[0]

            city = None
            cities = self.ria_data[item.ria['province']][village]
            count = len(cities)
            if count == 1:
                city = cities[0]
            elif count > 1:
                if item.region.parent.kind == 'area':
                    district = item.region.parent.name.replace(u'район', '').strip()
                    matches = get_close_matches(district, cities)
                    if matches:
                        city = matches[0]

            # на удачу!
            if not city and cities:
                city = cities[0]

            if city:
                item.ria['district'] = village
                item.ria['city'] = city
            else:
                pass # fail

        if 'city' not in item.ria:
            item.ria['city'] = u'нет города'

    def generate(self):
        super(Ria, self).generate()
        cache.set('export_ria_ads', self.rendered_items, 60*60*24*3)

class InternationalBaseFeed(BaseFeed):
    def queryset(self):
        user_ads = CatalogPlacement.get_active_user_ads('worldwide')
        return super(InternationalBaseFeed, self).queryset().filter(id__in=user_ads)


class ListGloballyFeed(InternationalBaseFeed):
    name = 'listglobally'
    comment = u'ListGlobally (зарубеженая)'

    autofields = (
        ('AdvertId', 'id'),
        ('Country', 'addr_country'),
        ('GoodType', 'property_type'),
        ('LivingArea', 'area'),
        ('Price', 'price'),
        ('PriceCurrency', 'currency'),
        ('Rooms', 'rooms'),
    )


class WorldPostingFeed(InternationalBaseFeed):
    name = 'worldposting'
    comment = u'WorldPosting (зарубеженая)'

    autofields = (
        ('id', 'id'),
        ('currency', 'currency'),
        ('room_count', 'rooms'),
        ('living_area', 'area'),
        ('floor_number', 'floor'),
        ('floor_count', 'floors_total'),
        ('url_listing', 'get_absolute_url'),
        ('reference', 'id'),
        ('source_reference', 'id'),
    )


class GoogleRemarketing(BaseFeed):
    name = 'googleDR'
    comment = u'google dynamic remarketing'

    def generate(self):
        self.start_time = time.time()

        try:
            tmpfile = NamedTemporaryFile(delete=False)

            import csv
            with open(tmpfile.name, 'wb') as csvfile:
                csvwriter = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_NONNUMERIC)
                csvwriter.writerow(['ID', 'ID2', 'Item title', 'Final URL', 'Image URL', 'Item subtitle',
                                    'Item description', 'Item category', 'Price', 'Sale price', 'Contextual keywords',
                                    'Item address', 'Tracking template', 'Custom parameter'])
                for item in self.iterate_items():
                    row = [item.id, '', '%s %s' % (item.addr_street, item.addr_house), item.get_absolute_url(),
                            item.get_first_photo().smart_thumbnail("md"), '', '', item.deal_type, u"%d UAH" % item.price_uah,
                           '', '', item.address, '', '']
                    for key, value in enumerate(row):
                        if isinstance(value, basestring):
                            row[key] = unicode(value).encode('utf8')
                    csvwriter.writerow(row)

            # копируем файл в storage
            filename = 'export/%s.csv' % self.name
            overwrite(filename, tmpfile)

            tmpfile.close()
            os.unlink(tmpfile.name)

            info = {
                'comment': self.comment,
                'properties': len(self.rendered_items),
                'link': default_storage.url(filename),
                'time': datetime.now(),
            }

            export_info = cache.get('export_status', {})
            export_info[self.name] = info
            cache.set('export_status', export_info, 7 * 24 * 3600)
        except:
            print '%-15s    EXCEPTION' % self.name
            traceback.print_exc()
        else:
            print '%-15s   %7.2f sec    %7d ads' % (self.name, time.time() - self.start_time, len(self.rendered_items))


feeds = [LunDaily, LunOther, Trovit, Prom, Ria, AddressUA, ListGloballyFeed, GoogleRemarketing, Krysha]


class Command(BaseCommand):
    help = 'generates export feed files'
    leave_locale_alone = True

    def add_arguments(self, parser):
        parser.add_argument('feed', nargs='?', choices=[f.name for f in feeds])
        parser.add_argument('--progress', action='store_true', dest='progress', help='show progress')

    def handle(self, *args, **options):
        print datetime.now()

        for feed_class in feeds:
            if options['feed'] is None or feed_class.name == options['feed']:
                feed = feed_class(options['progress'])
                feed.generate()

