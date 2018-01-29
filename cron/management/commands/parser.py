# coding: utf-8
import time
import os
import re
import requests
import datetime
import traceback
import collections
from tempfile import NamedTemporaryFile, gettempdir

import phonenumbers

from lxml import etree
from collections import defaultdict
from django import forms
from django.db import DataError
from django.core.management.base import BaseCommand
from django.template.loader import get_template, render_to_string

from ad.models import *
from ad.forms import create_ad_phones_formset
from utils.storage import overwrite


class Command(BaseCommand):
    help = u'Парсинг XML-фидов. Запуск раз в сутки, либо два раза в сутки (смотреть по посещаемости)'
    leave_locale_alone = True

    def add_arguments(self, parser):
        parser.add_argument('--only', dest='only', type=str, help='pass comma-separated feed names to generate only these feeds')
        parser.add_argument('--limit', dest='limit', type=int, default=0, help='number of ads for processing (default = unlim)')
        parser.add_argument('--add_limit', dest='add_limit', type=int, default=0, help='number of new ads (default = unlim)')
        parser.add_argument('--skip', dest='skip', type=int, default=0, help='number of ads to skip (default = unlim)')

        parser.add_argument('--debug', '-d', dest='debug', action='store_true', help='debug mode')
        parser.add_argument('--recheck_errors', dest='recheck_errors', action='store_true', help='dont skip ads with errors')
        parser.add_argument('--list', '-l', dest='list', action='store_true', help='list all available feeds')
        parser.add_argument('--check', '-c', dest='check', action='store_true', help='check feed')
        parser.add_argument('--update_existing', dest='update_existing', action='store_true', help='update existing ads')
        parser.add_argument('--no_image', dest='no_image', action='store_true', help='do not download image')

    def handle(self, *args, **options):
        available_feed_classes = [Fornova, Fornova2, FornovaTest, ListGlobally, WorldPosting]
        feed_classes_by_names = {class_.__name__.lower(): class_ for class_ in available_feed_classes}

        active_feed_classes = [ListGlobally]

        if options['list']:
            print 'Available feeds:', u', '.join(feed_classes_by_names.keys())
            return

        if options['only']:
            active_feed_classes = {feed_classes_by_names[options['only']]}

        # объявления с телефонами наших пользователей будут проигнорированы
        # UPD: кеширование добавлено, т.к. запрос очень долгий и это мешает во время отладки
        phone_filter = Q(ads__ad__user__isnull=False) | Q(ignore_in_parser=True)
        phones_in_users_ads = cache.get('user_phones')
        if not phones_in_users_ads:
            print 'Getting users phones - ',
            phones_in_users_ads = set(Phone.objects.filter(phone_filter).values_list('number', flat=True).distinct())
            cache.set('user_phones', phones_in_users_ads, 60*60*3)
            print 'OK'

        for feed_class in active_feed_classes:
            try:
                feed = feed_class(command_options=options)
                status = feed.sync_ads(phones_in_users_ads=phones_in_users_ads)
            except:
                print '%7.2f sec %7s ads      EXCEPTION' % ((time.time() - feed._start), '?')
                traceback.print_exc()
            else:
                print '%7.2f sec %7d ads processed' % ((time.time() - feed._start), status.get('properties', 0))
                updated_rows = Ad.objects.filter(content_provider=feed.content_provider_id, xml_id__in=feed.ids_for_update).update(modified=datetime.datetime.now())
                print '%7.2f sec %7d ads updated of %d xml_ids' % ((time.time() - feed._start), updated_rows, len(feed.ids_for_update))

            if not options['check'] and not options['update_existing']:
                feed.make_reports()



# получает содержимое файла по FTP
def download_file_from_ftp(url, file, auth=None):
    from ftplib import FTP
    from urlparse import urlparse

    url_parts = urlparse(url)
    ftp = FTP(url_parts.netloc)
    if auth:
        ftp.login(*auth)

    ftp.retrbinary('RETR %s' % url_parts.path, open(file, 'wb').write)


# скачиваем файлы через stream (это сделано, чтобы не держать большие файлы в памяти при парсинге)
def download_file(url, filename):
    with open(filename, 'wb') as handle:
        response = requests.get(url, stream=True)

        if not response.ok:
            response.raise_for_status()

        for block in response.iter_content(1024):
            handle.write(block)


'''
    Форма для валидации объявлений с парсера
'''
class AdCheckForm(forms.ModelForm):
    class Meta:
        model = Ad
        fields = [
            'xml_id', 'deal_type', 'property_type', 'description', 'rooms',
            'addr_country',  'addr_city', 'addr_street', 'addr_house', # 'address',
            'price', 'currency', 'area', 'source_url', 'guests_limit', 'contact_person', 'buy_vip',
            'coords_x', 'coords_y', 'geo_source' # TODO: после возвращения GeoDjango добавить 'point'
        ]

    price = forms.IntegerField(required=True, min_value=0)
    rooms = forms.IntegerField(required=False, min_value=0)
    source_url = forms.URLField(required=False, max_length=512)
    buy_vip = forms.IntegerField(required=False, min_value=1, max_value=1)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')

        super(AdCheckForm, self).__init__(*args, **kwargs)

        for key in ['addr_country', 'addr_city', 'addr_street', 'coords_x', 'coords_y', 'geo_source']: # TODO: после возвращения GeoDjango добавить 'point'
            self.fields[key].required = False

    def clean_property_type(self):
        property_type = self.cleaned_data['property_type']
        if property_type == 'commercial':
            raise forms.ValidationError(u"Недопустимый тип недвижимости")
        return property_type

    def clean(self):
        cleaned_data = super(AdCheckForm, self).clean()

        # Какой-то странный хак получился, как мне хвается.
        # Если в kwargs не передавать в форму addr_country, то он остается пустым и не срабатывают default/initial и т.п.
        if 'addr_country' not in cleaned_data or not cleaned_data['addr_country']:
            cleaned_data['addr_country'] = 'UA'

        if 'rooms' in cleaned_data and 'property_type' in cleaned_data:
            if cleaned_data['property_type'] in ('flat', 'house') and not cleaned_data['rooms']:
                self._errors['rooms'] = self.error_class([u'Обязательное поле для выбранного типа недвижимости'])
                del cleaned_data['rooms']

        return cleaned_data

'''
    Классы парсеров
'''
class BaseFeedParser(object):
    command_options = {}
    current_node = None

    name = None
    content_provider_id = 0
    url = None
    auth = None
    settings = {
        'fields_options': {
            'photos': {'many': True},
            'area': {'type': float},
            'price': {'type': int},
            'rooms': {'type': int},
            'xml_id': {'type': int},
        },
    }
    _max_phone_count = 2
    ids_for_update = set()

    def __init__(self, command_options):
        self.command_options = command_options
        self.exists_ids = set(Ad.objects.filter(content_provider=self.content_provider_id).values_list('xml_id', flat=True).order_by('xml_id'))
        self.no_photos_ids = set(Ad.objects.filter(content_provider=self.content_provider_id, photos__isnull=True).values_list('xml_id', flat=True).order_by('xml_id'))
        self.error_ids = set()
        self._start = time.time()

    def sync_ads(self, phones_in_users_ads=[]):
        print '----- %s -----' % self.__class__.__name__

        import_stats = collections.Counter()
        self.feed_errors = {
            'ids': collections.defaultdict(set),
            'samples' :collections.defaultdict(list),
        }

        self.progress_time = time.time()
        options = self.command_options

        # пропускаем объявления, которые были с ошибками в предыдущем парсинге
        if not options['recheck_errors']:
            previous_parser_errors = cache.get('parsing-feed-errors-%s' % self.__class__.__name__)
            if previous_parser_errors:
                values = previous_parser_errors['ids'].values()
                self.error_ids |= set([id for sublist in values for id in sublist ])

        for xml_id, node in self.get_ad_element():
            self.ids_for_update.add(xml_id)
            skip_processing_reason = None

            if options['update_existing'] and xml_id not in self.no_photos_ids:
                import_stats['skip'] += 1
                continue

            if time.time() - self.progress_time > 60:
                self.progress_time = time.time()
                print '%7.2f sec %7d ads processed' % (time.time() - self._start, sum(import_stats.values()))

            if xml_id in self.exists_ids:
                if not options['update_existing'] and not options['check']:
                    skip_processing_reason = 'Exist'

            if xml_id in self.error_ids:
                skip_processing_reason = 'Error in previous parsing'

            # если достигнут лимит по количество обработанный или количеству добавленых, то пропускаем оставшуюся часть с обработкой полей
            if (options['limit'] and sum(import_stats.values()) >= options['limit']) or \
                    (options['add_limit'] and import_stats['Added'] >= options['add_limit']):
                skip_processing_reason = 'Skip by limit'

            if options['skip'] and sum(import_stats.values()) < options['skip']:
                skip_processing_reason = 'Skip first %s ads' % options['skip']

            # если есть причина для пропуска дальнейшей обработки
            if skip_processing_reason:
                import_stats[skip_processing_reason] += 1
                continue

            attrs = self._get_attrs_from_node(node)

            raw_photos = attrs.pop('photos')[:4] if 'photos' in attrs else []
            raw_phones = attrs.pop('phones') if 'phones' in attrs else []

            if options['no_image']:
                raw_photos = []

            if options['update_existing'] and xml_id in self.exists_ids:
                ad = Ad.objects.filter(content_provider=self.content_provider_id, xml_id=xml_id).first()

                if not ad:
                    import_stats['Exist, but didnt find'] += 1
                    continue
                if ad.photos.count() > 0:
                    import_stats['Exist and has photos'] += 1
                    continue
            else:
                # статус модерации снимается после присвоения региона
                ad = Ad(status=1, moderation_status=11, user=None, content_provider=self.content_provider_id)

            form = AdCheckForm(attrs, instance=ad, user=None)

            # обработка телефонов
            phones_formset = create_ad_phones_formset(raw_phones)

            if form.is_valid() and phones_formset.is_valid():
                if len(set([phone['phone'] for phone in phones_formset.cleaned_data]) & phones_in_users_ads):
                    import_stats['Phone from user`s ad'] += 1
                    continue

                if options['check']:
                    if xml_id in self.exists_ids:
                        import_stats['Valid (exist)'] += 1
                    else:
                        import_stats['Valid'] += 1
                    continue
                else:
                    ad = form.save()
                    try:
                        phones_formset.update_phones_m2m(ad.phones_in_ad)
                    except DataError:
                        import_stats['Too long phone number'] += 1
                        continue

                    # обработка фото
                    for order, image in enumerate(raw_photos, 1):
                        Photo.objects.get_or_create(basead=ad, source_url=image, defaults={'order':order})

                    import_stats['Added'] += 1
            else:
                error_type = ",".join(list(form.errors) + [key for phone_error in phones_formset.errors for key in phone_error.keys()])
                import_stats["Errors with %s" % error_type ] += 1

                self.feed_errors['ids'][error_type].add(xml_id)
                if len(self.feed_errors['samples'][error_type]) < 3:
                    self.feed_errors['samples'][error_type].append(self.current_node)

                if options['debug']:
                    print xml_id,
                    if not form.is_valid():
                        print {name:form.errors[name] for name in form.errors}
                    if not phones_formset.is_valid():
                        print phones_formset.errors

        print u'Feed stats:'
        print u'\n'.join([u'\t%s - %s' % (k, import_stats[k]) for k in import_stats.keys()])

        if options['debug']:
            for key, arr in self.feed_errors['samples'].items():
                print '----------', key
                for val in arr:
                    print val
                    print '-------'

        # сохраняются в кеше объявления с ошибками: их id и примеры из XML
        cache.set('parsing-feed-errors-%s' % self.__class__.__name__, self.feed_errors, 60*60*24)

        return {'properties': sum(import_stats.values())}

    def get_ad_element(self):
        '''
            Итератор - открывает фид и возвращает поэлементно в виде набора аттрибутов
        '''
        if os.path.isfile(self.local_url):
            self.url = self.local_url

        print 'Feed URL: %s' % (self.url),

        # выкачиваем файл фида
        tempdir = gettempdir()
        extension = os.path.split(self.url)[-1].split('.', 1)[-1]
        file = os.path.join(tempdir, 'tmp-%s.%s' % (self.name, extension))
        if '://' in self.url:
            if 'ftp://' in self.url:
                download_file_from_ftp(self.url, file, self.auth)
            else:
                download_file(self.url, file)

            print '| download: %s' % (time.time() - self._start),
        else:
            file = self.url

        print

        # распаковываем gzip-архив, сам архив удаляем
        if '.gz' in file:
            import gzip
            newfile = file.replace('.gz', '')

            with open(newfile, 'w') as outfile, gzip.GzipFile(file, 'rb') as decompressedFile:
                outfile.write(decompressedFile.read())

            if 'tmp-' in file:
                os.remove(file)
            file = newfile

        if '.zip' in file:
            import zipfile

            fh = open(file, 'rb')
            z = zipfile.ZipFile(fh)
            for name in z.namelist():
                z.extract(name, tempdir)
                file = os.path.join(tempdir, name)
                break
            fh.close()

        for event, node in etree.iterparse(file, tag=self.settings['iterator'].split('/')[-1]):
            self.current_node = etree.tostring(node)
            xml_id = self._get_field_value('xml_id', node, self.settings['fields_xpath']['xml_id'])
            yield xml_id, node
            node.clear()

        # удаляем временный файл фида
        if 'tmp-' in file:
            os.remove(file)

    def _get_attrs_from_node(self, node):
        attrs = defaultdict(list)
        for field, xpath in self.settings['fields_xpath'].items():
            value = self._get_field_value(field, node, xpath)

            if value:
                attrs[field] = value

        self._process_ad(attrs)
        self._process_phones(attrs)

        return attrs

    def _get_field_value(self, field, node, xpath):
        options = self.settings.get('fields_options', {}).get(field, {})
        values = []

        for res in node.xpath(xpath):
            value = None
            if 'attr' in options:
                value = res.get(options['attr'])
            elif options.get('raw'):
                value = res
            elif res.text:
                value = res.text.strip()

            value = self._process_field(field, value)

            if value is not None:
                if not options.get('many'):
                    return value
                else:
                    values.append(value)

        return values

    # пост-обработка конкретного поля во время парсинга XML
    def _process_field(self, field, value):
        field_value_converter = self.settings.get('value_converter', {}).get(field)
        if field_value_converter and value in field_value_converter:
            value = field_value_converter[value]

        try:
            field_type = self.settings['fields_options'][field]['type']
        except KeyError:
            field_type = 'default'

        if field_type in [float, int]:
            try:
                value = field_type(value)
            except (ValueError, TypeError):
                value = None

        return value

    # пост-обработка всех полей объявления
    def _process_ad(self, attrs):
        if attrs['coords_x'] and attrs['coords_y']:
            attrs['geo_source'] = 'addr_coords'

    # пост-обработка телефонов и приведение их к международному формату
    def _process_phones(self, attrs):
        country_code = attrs.get('addr_country', 'UA')

        phones = attrs.get('phones', [])
        if isinstance(phones, basestring):
            phones = [phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164)
                      for match in phonenumbers.PhoneNumberMatcher(phones, country_code)]

        attrs['phones'] = []
        for raw_phone in phones:
            try:
                phone = phonenumbers.parse(raw_phone, country_code)
                phone_e164 = phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164)
                if len(phone_e164) <= 14 and phone_e164 not in attrs['phones']:
                    attrs['phones'].append(phone_e164)
            except (phonenumbers.NumberParseException):
                pass

        attrs['phones'] = attrs['phones'][:self._max_phone_count]

    def render_to_storage(self, template, context, output):
        # создаем временный файл и в него рендерим шаблон
        tmpfile = NamedTemporaryFile(delete=False)

        # возвращаемый лоадером django_jinja.backend.Template не умеет выполнять поточный рендеринг,
        # используется его атрибут - низкоуровневый шаблон django_jinja.base.Template(jinja2.Template)
        backend_template = get_template(template)
        backend_template.template.stream(context).dump(tmpfile, encoding='utf-8')

        # копируем файл в storage
        overwrite(output, tmpfile)

        tmpfile.close()
        os.unlink(tmpfile.name)

        return default_storage.url(output)

    # генерации отчетов
    def make_reports(self):
        return


class Fornova(BaseFeedParser):
    name = 'Fornova'
    content_provider_id = 1
    url = 'https://s3.amazonaws.com/re_ua_feeds/re_ua_feed_latest.xml'

    settings = {
        'iterator': '/resultset/row',
        'fields_xpath': {
            'xml_id': 'id', 'title': 'title', 'deal_type': 'deal_type', 'property_type': 'property_type',
            'created': 'first_update_timestamp', 'address': 'address', 'rooms': 'number_of_rooms', 'area': 'area',
            'description': 'description', 'price': 'price', 'currency': 'currency', 'price_period': 'PriceType',
            'phones': 'contact_details', 'photos': 'large_image_url', 'photos_additional': 'additional_di_image_urls',
            'source_url': 'deep_link',
        },
        'fields_options': {
            'photos': {'many': True},
            'area': {'type': float},
            'price': {'type': int},
            'rooms': {'type': int},
        },
        'value_converter': {
            'deal_type': {u'аренда': 'rent', u'на продажу': 'sale', u'посуточно': 'rent_daily', u'': 'newhomes'},
            'currency': {u'у.е.': 'USD'},
        }
    }

    def _process_ad(self, attrs):
        self._set_property_type(attrs)
        if 'photos_additional' in attrs:
            attrs['photos'] += [photo.strip('"')
                                for photo in attrs['photos_additional'].split(",")
                                if photo.strip('"') not in attrs['photos']]
            del attrs['photos_additional']

        super(Fornova, self)._process_ad(attrs)

    def _set_property_type(self, attrs):
        PROPERTY_TYPES = {
            u'квартира': 'flat',
            u'дома, котеджи, дачи': 'house',
            u'участки, земля': 'plot',
            u'комната': 'room',
            u'коммерческая недвижи': 'commercial',
            u'гараж': 'garages'
        }

        property_type = (attrs.get('property_type') or '').lower()

        # default
        attrs['property_type'] = 'flat'

        if (property_type or '').startswith(u'новострой'):
            attrs['deal_type'] = 'newhomes'

        if property_type in PROPERTY_TYPES:
            attrs['property_type'] = PROPERTY_TYPES[property_type]
        else:
            for entry, type in PROPERTY_TYPES.iteritems():
                if property_type.startswith(entry):
                    attrs['property_type'] = type


class Fornova2(Fornova):
    name = 'Fornova Agent'
    url = 'https://s3.amazonaws.com/re_ua_agents_feeds/re_ua_agents_feed_latest.xml'


class FornovaTest(Fornova):
    url = 'http://mesto.loc:8000/media/re_ua_feed_latest.xml'


class ListGlobally(BaseFeedParser):
    name = 'ListGlobally'
    url = 'http://mesto.edenhome.com/listglobally_full.zip'
    local_url = '/dev/django/mesto/ListGlobally.xml'
    content_provider_id = 2

    settings = {
        'iterator': '/Adverts/Advert',
        'fields_xpath': {
            'xml_id': 'AdvertId', 'deal_type': 'AdvertType', 'property_type': 'GoodType', 'created': 'PublicationDate',
            'addr_country': 'Country', 'addr_city': 'City', 'addr_street': 'Address', 'rooms': 'Rooms', 'bedrooms': 'Bedrooms',
            'area': 'LandArea', 'area_living': 'LivingArea', 'floor': 'Floor', 'description': 'Descriptions/Description',
            'price': 'Price', 'currency': 'PriceCurrency', 'phones': 'Contact/MobilePhone|Contact/LandPhone', 'price_period': 'PriceType',
            'coords_x': 'Geolocation/Longitude', 'coords_y': 'Geolocation/Latitude', 'photos': 'Photos/Photo',
        },
        'fields_options': {
            'photos': {'many': True, 'attr': 'Big'},
            'area': {'type': float},
            'price': {'type': int},
            'rooms': {'type': int},
        },
        'value_converter': {
            'deal_type': {'Sale': 'sale', 'Rent': 'rent', 'Holiday': 'rent'},
            'property_type': {
                'Flat': 'flat', 'House': 'house', 'Villa': 'house', 'Farm': 'plot', 'Chalet': 'house', 'Castle': 'house',
                'Business_Office': 'commercial', 'Commercial': 'commercial', 'Residential_Building': 'house', 'Residential Building': 'house',
                'Industrial_Building': 'commercial', 'Land': 'plot', 'Bungalow': 'house', 'Garage_Parking': 'garages',
            },
        }
    }

    def _process_ad(self, attrs):
        super(ListGlobally, self)._process_ad(attrs)
        
        if 'addr_street' in attrs:
            attrs['addr_street'] = attrs['addr_street'].split('/')[0]
        if 'addr_city' in attrs:
            attrs['addr_city'] = attrs['addr_city'].split('/')[0]

        if attrs['bedrooms']:
            attrs['rooms'] = attrs.get('rooms', attrs['bedrooms'])

        # ускоренная валидация, чтобы не использовать форму форму
        # реализованно именно здесь, а не в отдельной функции, т.к. это критично только для больших фидов, а таких у нас мало
        # UPD 2016-07-05: временно отключено, т.к. потребовался полноценный вывод ошибок в отчетах для ListGlobally
        '''
        if not attrs.get('rooms') or attrs.get('property_type') == 'commercial' or attrs.get('currency') not in ['UAH', 'RUB', 'USD', 'EUR']:
            error_type = 'fast_check_error'
            attrs['error'] = 'Errors with %s' % error_type

            self.feed_errors['ids'][error_type].add(attrs['xml_id'])
            if len(self.feed_errors['samples'][error_type]) < 3:
                self.feed_errors['samples'][error_type].append(self.current_node)

            return
        '''

        # вырезается ссылка на сервис, который создают превью
        attrs['photos'] = [re.sub(r'(.*)image.portia.ch\/remote\/(.*)\?width=600&height=450', r'\1\2', photo, re.I) for photo in attrs['photos']]

        # у них бывает по 20 фотографий в одном объявлении, нафиг нужно!
        attrs['photos'] = attrs['photos'][:5]

    def make_reports(self):
        start = time.time()
        ads = Ad.objects.filter(is_published=True, content_provider=self.content_provider_id).only('id', 'xml_id', 'moderation_status', 'status', 'deal_type', 'region').prefetch_related('region').order_by()
        print 'Backlinks report: %s, %s sec' % (self.render_to_storage('parser/listglobally_backlinks.jinja.xml', {'ads':ads, 'errors':self.feed_errors['ids']}, 'reports/listglobally_backlinks.xml'), time.time() - start)

        from django.db.models import Sum
        start = time.time()
        stats = ViewsCount.objects.filter(basead__ad__content_provider=self.content_provider_id).values(
            'date', 'basead', 'basead__ad__xml_id').order_by('date').annotate(detail_views=Sum('detail_views'))
        print 'Statistics report: %s, %s sec ' % (self.render_to_storage('parser/listglobally_stats.jinja.xml', {'stats':stats}, 'reports/listglobally_stats.csv'), time.time() - start)


class WorldPosting(BaseFeedParser):
    name = 'WorldPosting'
    url = 'ftp://ftp.eu2.previsite.com/mesto.xml'
    local_url = '/django/mesto/worldposting.xml'
    auth = ('mesto', 'MSmc-2266')
    content_provider_id = 3

    settings = {
        'iterator': '/listings/listing',
        'fields_xpath': {
            'xml_id': 'id', 'deal_type': 'transaction_type', 'property_type': 'property_type', 'created': 'created_date',
            'addr_country': 'country', 'addr_city': 'city', 'addr_street': 'streetaddress', 'rooms': 'room_count', 'bedrooms': 'bedroom_count',
            'area': 'land_area', 'area_living': 'living_area', 'floor': 'floor_number', 'floor_total': 'floor_count',
            'description': 'descriptions/description',
            'price': 'price', 'currency': 'currency', 'phones': 'contacts/contact/contact_phone', 'price_period': 'PriceType',
            'coords_x': 'geocode_longitude', 'coords_y': 'geocode_latitude', 'photos': 'medias/media/media_url',
        },
        'fields_options': {
            'photos': {'many': True},
            'phones': {'many': True},
            'description': {'raw': True, 'many': True},
            'area': {'type': float},
            'price': {'type': int},
            'rooms': {'type': int},
        },
        'value_converter': {
            'deal_type': {'rental': 'rent'},
            'property_type': {'apartment': 'flat', 'land':'plot'},
        }
    }

    def _process_ad(self, attrs):
        super(WorldPosting, self)._process_ad(attrs)

        # обработка описание
        descriptions = {}
        for node in attrs.get('description', []):
            language = node.find('language').text
            descriptions[language] = node.find('description').text
        if descriptions:
            attrs['description'] = descriptions.get('RU', descriptions.itervalues().next())

        if attrs['bedrooms']:
            attrs['rooms'] = attrs.get('rooms', attrs['bedrooms'])

        if attrs['coords_x'] and attrs['coords_y']:
            if settings.MESTO_USE_GEODJANGO:
                attrs['point'] = Point([float(attrs['coords_x']), float(attrs['coords_y'])], srid=4326)

        # на всякий случай
        attrs['photos'] = attrs['photos'][:5]

        return attrs

    def make_reports(self):
        ads = Ad.objects.filter(content_provider=self.content_provider_id).prefetch_related('viewscounts').order_by()
        for ad in ads:
            ad.detail_views = 0
            for row in ad.viewscounts.all():
                if row.type == 0:
                    ad.detail_views += row.views
        print 'Statistics report : ', self.render_to_storage('parser/worldposting_stats.jinja.xml', {'ads':ads}, 'reports/worldposting_stats.xml')
