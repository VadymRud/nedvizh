# coding=utf-8
import datetime
import random
import time
import urllib
import math
import logging
import collections
import types
import json

from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, render, redirect
from django.core.cache import cache
from django.template.loader import render_to_string
from django.http import HttpResponsePermanentRedirect, HttpResponse, JsonResponse, Http404, HttpResponseGone, QueryDict
from django.db.models import Q, F, Model
from django.contrib import messages
from django.contrib.gis.measure import Distance
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils import translation
from django.middleware.csrf import get_token

from ad.models import (
    Region, Ad, ViewsCount, DealType, Facility, SubwayLine, SubwayStation,
    make_sphere_distance_filters, make_coords_ranges_filters, SearchCounter
)
from ad.choices import DEAL_TYPE_CHOICES, MODERATION_STATUS_CHOICES
from ad.forms import PropertySearchForm, InternationalContactForm
from banner.models import Banner
from custom_user.models import User
from profile.models import SavedSearch, get_sorted_urlencode, convert_dict_to_lists, get_banned_users
from ppc.models import ViewsCount as PpcViewsCount
from paid_services.models import CatalogPlacement
from seo.cross_linking import get_crosslinks
from seo.models import TextBlock
from seo.meta_tags import SEO, get_details_metatags, image_title as seo_image_title
from staticpages.models import Article
from utils.currency import get_currency_rates
from utils.paginator import AdPaginator, HandyPaginator
from utils.gtm import make_gtm_data

import django_filters


def mainpage_ads_counter(international=False):
    """
    подсчет количества объявлений на сайте
    """
    cache_key = 'ads_counter_UA' if not international else 'ads_counter_int'
    properties_counter = cache.get(cache_key, {})
    if not properties_counter:
        if not international:
            ads = Ad.objects.filter(is_published=True, status=1)
        else:
            ads = Ad.objects.filter(is_published=True, status=1).exclude(addr_country='UA')

        properties_counter['total'] = ads.count()

        last_week = datetime.datetime.now() - datetime.timedelta(days=7)
        properties_counter['increment'] = ads.filter(created__gte=last_week).count()
        properties_counter['processing_time'] = int(time.time())

        # обновление раз в час
        cache.set(cache_key, properties_counter, 60 * 60)

    else:
        # увеличиваем общий счетчик количества объявлений с учетом добавленных объявлений
        increment_per_second = float(properties_counter['increment']) / (7*24*60*60)
        diff = (int(time.time()) - properties_counter['processing_time']) * increment_per_second
        properties_counter['total'] += int(diff)

    return properties_counter


def get_region_slug_for_menu(region):
    ''' ссылки в верхнем меню не должны вести на страницы районов/удиц, только на более крупные регионы
    '''
    allowed_region_kind_for_menu = ['country', 'province', 'locality', 'village']
    if region.kind in allowed_region_kind_for_menu:
        return region.static_url.split(';')[-1]
    else:
        for r in region.get_parents()[::-1]:
            if r.kind in allowed_region_kind_for_menu:
                return  r.static_url.split(';')[-1]


# home page
def index(request):
    if request.subdomain == 'international':
        return index_international(request)

    is_homepage = True

    categories = settings.NEWS_CATEGORIES
    realestate_news = Article.objects.filter(category__in=categories, visible=True).prefetch_related('subdomains')\
                          .exclude(category='events').order_by('-published')

    if request.subdomain:
        # Для поддоменов показываем новости доступные только для текущего поддомена
        realestate_news = realestate_news.filter(subdomains__slug=request.subdomain)

    realestate_news = realestate_news[:3]
    slider = Banner.active_banners.filter(place='slider').order_by('order')

    from staticpages.models import ContentBlock
    content_homepage_after_properties = ContentBlock.objects.filter(name='homepage_after_properties').first()

    properties = Ad.objects.filter(is_published=True, has_photos=True, coords_x__isnull=False).exclude(
        get_exclude_rules()).prefetch_related('photos', 'region').order_by('-vip_type', '-updated')

    # применяем фильтр по регионам
    if request.subdomain_region.slug == 'ukraina':
        properties = properties.filter(addr_country='UA')
    else:
        properties = properties.filter(region__in=request.subdomain_region.get_descendants(True))
    properties = properties[:4]

    properties_counter = mainpage_ads_counter()
    region_for_search = region = request.subdomain_region if request.subdomain else Region.objects.get(slug=settings.MESTO_CAPITAL_SLUG)
    search_form = PropertySearchForm(initial={'property_type': 'flat'}) # A form bound to the POST data
    search_form.prepare_choices(region_for_search, 'sale')

    if settings.MESTO_SITE == 'mesto':
        # Готовим SEO
        seo_klass = SEO(current_language=request.LANGUAGE_CODE)
        seo = seo_klass.get_seo(
            region=request.subdomain_region,
            deal_type='index',
            region_kind=('country' if request.subdomain_region.kind == 'country' else 'default')
        )
        title = seo['title']
        description = seo['description']
        seo_text_block = TextBlock.find_by_request(request, request.subdomain_region)
    else:
        seo = collections.defaultdict(unicode)
        seo_text_block = None

    return render(request, 'homepage.jinja.html', locals())


def index_international(request):
    properties = Ad.objects.filter(is_published=True).exclude(addr_country='UA')\
        .prefetch_related('photos', 'region').order_by('-vip_type', '-updated')

    properties = properties.filter(region__in=request.subdomain_region.get_descendants())

    # выводятся только фиды и платные объявления пользователей
    international_filter = Q(user__isnull=True) | Q(pk__in=CatalogPlacement.get_active_user_ads())
    properties = properties.filter(international_filter)

    properties = {
        'rent': properties.filter(deal_type='rent')[:2],
        'sale': properties.filter(deal_type='sale')[:2]
    }

    region_for_search = region = request.subdomain_region
    properties_counter = mainpage_ads_counter(international=True)
    countries = Region.objects.filter(parent=request.subdomain_region, kind='country', region_counter__count__gt=0).distinct()
    form = PropertySearchForm(initial={'property_type': 'flat'}) # A form bound to the POST data
    form.prepare_choices(region_for_search, 'sale')

    # Готовим SEO
    seo_klass = SEO(current_language=request.LANGUAGE_CODE)
    seo = seo_klass.get_seo(
        region=request.subdomain_region,
        deal_type='index',
        region_kind=('country' if request.subdomain_region.kind == 'country' else 'default')
    )
    title = seo['title']
    description = seo['description']

    seo_text_block = TextBlock.find_by_request(request, request.subdomain_region)
    return render(request, 'international.jinja.html', locals())


def short_property(request, id):
    item = get_object_or_404(Ad, id=id, region__isnull=0)
    return redirect(item.get_absolute_url(), permanent=True)


def detail(request, deal_type, id, region_slug=None, property_type=None):
    region = Region.get_region_from_slug(region_slug, request.subdomain, request.subdomain_region)
           
    try:
        item = Ad.objects.select_related('region').prefetch_related('photos').get(id=id)
    except (Ad.DoesNotExist, Http404, IndexError):
        return HttpResponseGone(render_to_string('410.jinja.html', locals(), request=request))

    if request.LANGUAGE_CODE != settings.LANGUAGE_CODE:
        translation.activate(settings.LANGUAGE_CODE)
        canonical_url = item.get_absolute_url()
        translation.activate(request.LANGUAGE_CODE)

    # на поддомене с группой регионов проверяем корректность URL и региона в нем
    if deal_type != item.deal_type or not region and item.region \
            or (request.subdomain_region.kind != 'group' and item.region and item.region.static_url != region.static_url):
        return redirect(item.get_absolute_url())

    # для ссылок на другие типы сделок в верхнем меню
    region_slug_for_menu = get_region_slug_for_menu(region)

    # исключаем объявления заблокированных пользователей и сами забаненные объявления + объявления робота
    if (not item.is_published or (item.user_id and item.user_id in get_banned_users())) or not item.region:

        shown_only_for_you = request.user.is_staff or (request.user.is_authenticated() and request.user.id == item.user_id)

        if not shown_only_for_you: # можно показать объявление владельцу или админу
            return HttpResponseGone(render_to_string('410.jinja.html', locals(), request=request))

    # блоки ссылок для перелинковки (SEO от октября 2014)
    crosslinks_blocks = get_crosslinks(
        request.build_absolute_uri(), region, item.deal_type, item.property_type,
        current_language=request.LANGUAGE_CODE, detail=True
    )

    # для всех пользователей, кроме владельцев и ботов
    if request.is_customer and not (request.user.is_authenticated() and request.user == item.user):
        # считаем просмотры
        viewscount_updated_rows = ViewsCount.objects.filter(basead=item, date=datetime.date.today(), is_fake=False).update(detail_views=F('detail_views')+1)
        if not viewscount_updated_rows:
            ViewsCount.objects.create(basead=item, date=datetime.date.today(), detail_views=1)

        if item.user and item.user.has_active_leadgeneration('ads') and not item.user.has_paid_dedicated_numbers():
            ppcviewscount_updated_rows = PpcViewsCount.objects.filter(
                basead=item,
                date=datetime.date.today(),
                traffic_source=request.traffic_source,
            ).update(detail_views=F('detail_views')+1)
            if not ppcviewscount_updated_rows:
                PpcViewsCount.objects.create(basead=item, date=datetime.date.today(), traffic_source=request.traffic_source, detail_views=1)

        # хак для маркетологов, просмотр считается поиском
        if request.traffic_source == 'lun':
            searchcount_parameters = dict(
                is_ad_view_referred_by_lunua=True,
                date=datetime.date.today(),
                price_from=item.price,
                price_to=item.price,
                currency=item.currency,
                rooms=[item.rooms] if item.rooms else [],
                deal_type=item.deal_type,
                property_type=item.property_type,
                region=item.region,

                # видимо в форме поиска эти поля обязательны
                # TODO: можно попробовать в модели сделать их необязательными
                facilities=[],
                without_commission=False,
            )
            searchcount_updated_rows = SearchCounter.objects.filter(**searchcount_parameters).update(
                searches_first_page=F('searches_first_page') + 1,
                searches_all_pages=F('searches_all_pages') + 1,
            )
            if not searchcount_updated_rows:
                SearchCounter.objects.create(searches_first_page=1, searches_all_pages=1, **searchcount_parameters)

    usercard = item.prepare_usercard(host_name=request.host.name, traffic_source=request.traffic_source)

    # Для объектов новостроек расширяем данные
    if item.newhome_layouts.exists():
        (flats_rooms_options, flats_available, flats_prices_by_floor, flats_info_exists, flats_floor_options,
         flats_area_by_rooms, flats_prices_by_rooms,
         currency) = item.newhome_layouts.first().newhome.get_aggregation_floors_info(request)

        # Всего доступно квартир в ЖК
        flats_available_amount = 0
        for key in flats_available.keys():
            for sub_key in flats_available[key]:
                flats_available_amount += flats_available[key][sub_key]

    if 'show_lead_button' in usercard:
        now_stamp = int(time.mktime(datetime.datetime.now().timetuple()))
        blocking = request.session.get('block_callrequests_until', {})

        # очистка старых блокировок
        for ad_id, stamp in blocking.items():
            if stamp < now_stamp:
                del blocking[ad_id]

        if str(item.id) in blocking:
            usercard['show_message_button'] = True
        else:
            from ppc.forms import CallRequestForm
            from ppc.models import CallRequest

            initial = {}
            if 'callrequest' in request.POST:
                callrequest = CallRequest(object=item, user2=item.user, referer=request.META.get('HTTP_REFERER'),
                                          ip=request.META.get('REMOTE_ADDR'),
                                          traffic_source=request.traffic_source)
                if request.user.is_authenticated():
                    callrequest.user1 = request.user

                callrequest_form = CallRequestForm(request.POST, instance=callrequest)
                if callrequest_form.is_valid():
                    callrequest_form.save()
                    messages.info(request, _(u'Ваша заявка успешно отправлена.<br/><br/>Ожидайте звонок.'), extra_tags='modal-dialog-w400 modal-success')

                    # блокировка заказа звонка по объявления. Для ППК - не чаще, чем раз в 4 часа, для остальные - не чаще чем 1 раз в минуту
                    if usercard.get('phone_for_lead'):
                        blocking[str(item.id)] = now_stamp + 60*60*4
                    else:
                        blocking[str(item.id)] = now_stamp + 60

                    # чтобы повторно не выводить кнопку заявки и форму, а показать кнопи отправки сообщений и контр-оферты
                    usercard['show_message_button'] = True
                    callrequest_form = False
            else:
                callrequest_form = CallRequestForm()

        request.session['block_callrequests_until'] = blocking

    if item.content_provider == 2:
        if request.method == 'POST':
            contact_form = InternationalContactForm(data=request.POST)
            if contact_form.is_valid():
                contact_form_success = True
        else:
            contact_form = InternationalContactForm(initial={'id': item.xml_id})

    # для динамического ремаркетинга в analytics
    gtm_data = make_gtm_data(request, extra_data={'dimension2': item.id})

    item.image_title = seo_image_title(item)
    title = item.address # TODO: добавить тип сделки к урлу

    united_facilities = list(Facility.get_facilities_by_deal_type(deal_type)) + list(item.rules.model.objects.all())
    selected_facilties = list(item.facilities.all()) + list(item.rules.all())

    # Диапазон поиска по цене + ХК
    related_query_dict = {
        'price_from': roundToBig(item.price_uah*0.95, False),
        'price_to': roundToBig(item.price_uah*1.05, True)
    }

    if item.rooms: related_query_dict['rooms'] = item.rooms
    related_search_url = '%s?%s' % (item.region.get_deal_url(item.deal_type, item.property_type), urllib.urlencode(related_query_dict))

    # Корректируем отображение ХК
    related_query_dict['local_price_from'] = roundToBig(item.get_converted_price(item.currency)*0.95, False)
    related_query_dict['local_price_to'] = roundToBig(item.get_converted_price(item.currency)*1.05, True)

    # related_block = cache.get('related_properties_%s' % related_search_url, {})
    related_block = {}

    #TODO переделать
    if type(related_block)==dict and 'count' not in related_block:
        related_items_query = Ad.objects.exclude(id=item.id).prefetch_related('photos').filter(
            is_published=True,
            region=item.region,
            deal_type=item.deal_type,
            property_type=item.property_type,
            rooms=item.rooms,
            price_uah__gte=related_query_dict['price_from'],
            price_uah__lte=related_query_dict['price_to'],
        )
        related_block['url'] = related_search_url
        related_block['count'] = related_items_query.count()
        related_block['items'] = related_items_query.order_by('?')[:2]
        # cache.set('related_properties_%s' % related_search_url, related_block, 3600*6)

    if request.user.is_authenticated():
        from profile.models import SavedAd
        item.saved = SavedAd.objects.filter(user=request.user, basead=item).count()

    # используется в форме модерации
    statuses = MODERATION_STATUS_CHOICES

    if deal_type == 'rent_daily':
        reserved_dates = [r.date.strftime('%Y-%m-%d') for r in item.reserved.all()]

    # Готовим SEO
    title, description = get_details_metatags(region, item)

    return render(request, 'ad/detail.jinja.html', locals())

def roundToBig(num, up=True, accuracy=2):
    rounder = math.ceil if up else math.floor
    mult = math.pow(10, len(str(int(num)))-accuracy)
    return int(rounder( num / mult ) * mult)

# TODO: переписать, добавить кеширование, оптимизировать и т.п.
def get_price_range(cache_key, properties):
    price_range = cache.get('price_range_%s' % cache_key, [None, None])
    if price_range[0] is None or price_range[1] is None:
        try:
            from django.db.models import Max, Min
            price_range = properties.aggregate(Min('price_uah'), Max('price_uah')).values()
            if price_range[1] > 100:
                pow = math.pow(10, len(str(price_range[1]))-2)
                price_range[1] = int(math.ceil( price_range[1] / pow ) * pow)
        finally:
            if not price_range[1]:
                price_range[1] = 20000000
            if not price_range[0] or price_range[0] == price_range[1]:
                price_range[0] = 100
        cache.set('price_range_%s' % cache_key, price_range, 3600*24*3)
    return price_range


def clear_get(request, region, deal_type, property_type, GET):
    if len(GET) > 1:
        need_redirect = False

        if GET.get('id'):
            ad = Ad.objects.filter(pk=GET['id']).first()
            if ad:
                GET['redirect'] = ad.get_absolute_url()
                return GET

        if GET.get('currency') == 'UAH':
            del GET['currency']

        property_type = GET.get('property_type', property_type)
        for key in sorted(GET.keys()):
            value = GET.get(key, '')
            if len(value) == 0 or key.find('ufd-') != -1 or \
                key in ['property_type', 'deal_type', 'region_choose', 'section'] or \
                key == 'page' or \
                (key == 'p' and value == '1') or \
                (key == 'added_days' and value == '0'):

                need_redirect = True
                del GET[key]

        subway_stations = GET.getlist('subway_stations')
        if len(subway_stations) == 1:
            subway = get_object_or_404(SubwayStation, pk=subway_stations[0])

        districts = GET.getlist('district')
        if len(districts) == 1:
            district = get_object_or_404(Region, pk=districts[0])
            if district != region:
                region = district
                del GET['district']
                need_redirect = True
        elif region.kind == 'district':
            # если districts пуст или содержит несколько районов, то страница поиска берется от родительского региона района
            region = region.parent
            need_redirect = True

        if need_redirect:
            if len(subway_stations) == 1:
                GET['redirect'] =  u'%s%s' % (region.get_deal_url(deal_type, property_type, subway.slug),
                                                     u'?%s' % get_sorted_urlencode(GET.lists()) if len(GET) else '')
            else:
                GET['redirect'] =  u'%s%s' % (region.get_deal_url(deal_type, property_type),
                                                     u'?%s' % get_sorted_urlencode(GET.lists()) if len(GET) else '')
    elif GET.get('page') == '1': # если только один параметр и он - номер страницы
        GET['redirect'] = request.path
        return GET

    return GET

def get_exclude_rules():
    exclude_rules = cache.get('properties_exclude_rules')
    if exclude_rules is None:
        exclude_rules = Q()

        # demo_users = set(Ad.objects.filter(xml_id='demo').values_list('user', flat=True))
        # exclude_rules.add(Q(user_id__in=demo_users), Q.AND)

        cache.set('properties_exclude_rules', exclude_rules, 3600*24) # бан обновляется раз в день

    return exclude_rules


from ad import choices as ad_choices
class PropertyFilter(django_filters.FilterSet):
    area_from = django_filters.NumberFilter(name="area", lookup_type='gt')
    area_to = django_filters.NumberFilter(name="area", lookup_type='lt')
    area_living_from = django_filters.NumberFilter(name="area_living", lookup_type='gt')
    area_living_to = django_filters.NumberFilter(name="area_living", lookup_type='lt')

    with_image = django_filters.MethodFilter()
    without_commission = django_filters.MethodFilter()
    no_agent = django_filters.MethodFilter()
    facilities = django_filters.MethodFilter()
    floor_variants = django_filters.MethodFilter()
    rooms = django_filters.MethodFilter()
    guests_limit = django_filters.MethodFilter()
    subway_stations = django_filters.MethodFilter()
    added_days = django_filters.MethodFilter()

    district = django_filters.MethodFilter()
    addr_street_id = django_filters.MethodFilter()

    currency = django_filters.MethodFilter()
    price_from = django_filters.NumberFilter(name="price_uah", lookup_type='gte')
    price_to = django_filters.NumberFilter(name="price_uah", lookup_type='lte')

    building_type = django_filters.MultipleChoiceFilter(name='building_type', choices=ad_choices.BUILDING_TYPE_CHOICES, lookup_type='in')
    building_layout = django_filters.MultipleChoiceFilter(name='building_layout', choices=ad_choices.LAYOUT_CHOICES, lookup_type='in')

    order_by_field = 'sort'

    class Meta:
        model = Ad
        fields = ['id', 'property_commercial_type']
        order_by = (
            ('-updated', _(u'по дате')),
            ('price_uah', _(u'по возрастанию цены')),
            ('-price_uah', _(u'по убыванию цены')),
        )

    def filter_currency(self, qs, value):
        """ Хак, конвертирующий исходные значения фильтра по цене из ин. валюты в гривны, т.к. поиск происходит по price_uah """
        if value and value != 'UAH':
            from decimal import Decimal
            curr_rate = get_currency_rates()[value]

            if self.form.cleaned_data['price_from']:
                self.form.cleaned_data['price_from'] *= Decimal(curr_rate * 0.998)
            if self.form.cleaned_data['price_to']:
                self.form.cleaned_data['price_to'] *= Decimal(curr_rate * 1.002)
        return qs

    def filter_with_image(self, qs, value):
        if value:
            qs = qs.filter(has_photos=True)
        return qs

    def filter_without_commission(self, qs, value):
        if value:
            qs = qs.filter(without_commission=True)
        return qs

    def filter_no_agent(self, qs, value):
        if value:
            qs = qs.filter(user__realtors__isnull=True)
        return qs

    def filter_facilities(self, qs, value):
        if value:
            return qs.filter(facilities_array__contains=[f.id for f in value])
        return qs

    def filter_floor_variants(self, qs, value):
        floor_variants = self.data['floor_variants']
        if 'first' in floor_variants:
            qs = qs.filter(floor=1)
        if 'not-first' in floor_variants:
            qs = qs.exclude(floor=1)
        if 'last' in floor_variants:
            qs = qs.filter(floor=F('floors_total'), floors_total__gt=0)
        if 'not-last' in floor_variants:
            qs = qs.exclude(floor=F('floors_total'), floors_total__gt=0)
        return qs

    # Фильтруем по ближайшим станциям метро, расстояние выбрано эксперементальным методом тыка
    def filter_subway_stations(self, qs, values):
        if values:
            q = Q()
            for subway_station in values:
                if settings.MESTO_USE_GEODJANGO:
                    distance_filters = make_sphere_distance_filters('point', subway_station.point, Distance(m=1000))
                else:
                    coords = (subway_station.coords_x, subway_station.coords_y)
                    distance_filters = make_coords_ranges_filters(coords, Distance(m=1000))
                q = q | Q(**distance_filters)
            qs = qs.filter(q)
        return qs

    def filter_rooms(self, qs, values, field='rooms'):
        filter = Q()
        for value in values:
            if int(value) >= 5:
                filter.add(Q(**{'%s__gte' % field:value}), Q.OR)
            else:
                filter.add(Q(**{field:value}), Q.OR)
        return qs.filter(filter)

    def filter_addr_street_id(self, qs, value):
        if value:
            qs = qs.filter(region_id=value)
        return qs

    def filter_district(self, qs, values):
        district_filter = Q()
        for district in values:
            district_children = district.get_descendants(True)
            district_filter.add(Q(region__in=district_children), Q.OR)

        if district_filter:
            qs = qs.filter(district_filter)
        return qs

    def filter_added_days(self, qs, value):
        if value:
            return qs.filter(modified__gt=datetime.datetime.now() - datetime.timedelta(days=int(value)))
        return qs

    def filter_guests_limit(self, qs, value):
        return self.filter_rooms(qs, value, 'guests_limit')

    def get_order_by(self, order_value):
        if order_value == '-updated':
            return ['-vip_type', '-updated', '-pk']
        return super(PropertyFilter, self).get_order_by(order_value)


def search(request, deal_type, region_slug=None, property_type='flat', subway_slug=None):
    region = Region.get_region_from_slug(region_slug, request.subdomain, request.subdomain_region)
    currency_rates = get_currency_rates()
    asnu_users = User.get_asnu_members()
    if not region:
        raise Http404

    # для ссылок на другие типы сделок в верхнем меню
    region_slug_for_menu = get_region_slug_for_menu(region)

    request.GET = clear_get(request, region, deal_type, property_type, request.GET.copy())
    if request.GET.get('redirect'):
        return HttpResponsePermanentRedirect(request.GET.get('redirect'))

    # SEO-корректировки от ноября 2017
    if 'district' in request.GET:
        GET = request.GET.copy()
        del GET['district']
        canonical_url =  u'%s%s' % (region.get_deal_url(deal_type, property_type), u'?%s' % get_sorted_urlencode(GET.lists()) if len(GET) else '')

    # выбор региона для селектора населенного пункта в форме
    region_for_search = region
    for parent in region.get_parents()[::-1]:
        if parent.kind in ['country', 'province', 'village', 'locality']:
            region_for_search = parent
            break

    # чтобы в форме это метро было выделено
    if subway_slug is not None:
        subway_station = get_object_or_404(SubwayStation, slug=subway_slug)
        get_dict = dict(request.GET.lists())
        if 'subway_stations' in get_dict:
            if str(subway_station.id) not in get_dict['subway_stations']:
                request.GET.appendlist('subway_stations', str(subway_station.id))
        else:
            request.GET.appendlist('subway_stations', str(subway_station.id))

    # теперь данные из region_slug нужно запихнуть в GET, чтобы в форме этот район тоже был выделен
    if region.kind == 'district' and str(region.id) not in request.GET.getlist('district'):
        request.GET.appendlist('district', region.id)

    # весь список объявлений с указанном типом объявления
    items_list = Ad.objects.filter(is_published=True, deal_type=deal_type).exclude(get_exclude_rules()) \
        .prefetch_related('photos', 'region', 'user', 'deactivations')

    # TODO international_crutch: переделать после обкатки, перепроверил логику или управлять публикацией через статусы
    if request.subdomain == 'international':
        international_filter = Q(user__isnull=True) | Q(pk__in=CatalogPlacement.get_active_user_ads())
        items_list = items_list.filter(international_filter)

    if property_type != 'all-real-estate':
        items_list = items_list.filter(property_type=property_type)

    # этот queryset используется в случае для вывода альтернативных результатов, если нет никаких объявлений в поиске
    base_items_list = items_list

    # применяем фильтр по регионам, если не применились фильтры по району/улице
    if region.kind == 'country' and region.slug == 'ukraina':
        region_filter = Q(addr_country='UA')
    else:
        region_filter = Q(region__in=region.get_descendants(True))

    # применяем фильтры по региону
    items_list = items_list.filter(region_filter)

    query_parameters = SavedSearch.extract_query_parameters_from_querydict(request.GET)
    savedsearch_parameters = dict({
        'deal_type': deal_type,
        'property_type': property_type,
        'region': region.id,
    }, **query_parameters)
    saved_search_query = get_sorted_urlencode(convert_dict_to_lists(savedsearch_parameters))

    try:
        form = PropertySearchForm(request.GET.copy())
        form.prepare_choices(region_for_search, deal_type)

        if request.subdomain == 'international':
            form.fields['currency'].choices = [('USD', u'$'), ('EUR', u'€'), ('UAH', u'грн.'),  ('RUR', u'руб.'),]

    except Region.DoesNotExist:
        # не найден активный регион в выпадающем списке
        return redirect('..')

    # тип недвижимости берется из URL, а не из параметров GET
    form.data['deal_type'] = deal_type
    form.data['property_type'] = property_type

    rooms_filter_for_seo = 0
    subway_filter_for_seo = 0
    if form.is_valid():
        # вся фильтрация делается через этот чудо-фильтр
        items_list = PropertyFilter(form.cleaned_data, queryset=items_list).qs

        if len(form.cleaned_data['rooms']) == 1:
            rooms_filter_for_seo = form.cleaned_data['rooms'][0]

        if form.cleaned_data['subway_stations']:
            subway_filter_for_seo = form.cleaned_data['subway_stations'][0]

    else:
        items_list = Ad.objects.none()

    if settings.MESTO_SITE == 'mesto':
        seo_klass = SEO(current_language=request.LANGUAGE_CODE)
        seo = seo_klass.get_seo(
            region=region,
            deal_type=deal_type,
            property_type=property_type,
            rooms=rooms_filter_for_seo,
            subway_stations=subway_filter_for_seo
        )

        seo_text_block = TextBlock.find_by_request(request, region)

        # генерация (без сохранения) текствого блока для страниц улиц
        if not seo_text_block:
            seo_text_block = TextBlock.generate_text_block(request, deal_type, property_type, region)
    else:
        seo = collections.defaultdict(unicode)
        seo_text_block = None


    # А/Б тест для Google Analytics: размер выдачи увеличен до 50 объявлений в Киеве, Днепре, Одессе и Харькове
    items_per_page = 20
    ga_experiment_ids = {
        11191: 'll1faxO-S7OS3gy2lIGDfg', # dnepr
        65:    'f8xETCkvS0SUrNdEZo2CeQ', # kiev
        11208: 'KpVr94OeQveyhOlK2HNL7g', # odessa
        11213: '9mfcJZT9SQ-6LPqpHKrB9w', #harkov
    }
    experiment_id = ga_experiment_ids.get(region.id)
    if experiment_id:
        if 'ga_experiment_variant' not in request.session:
            import random
            request.session['ga_experiment_variant'] =  random.randint(0, 1)
        experiment_variant = request.session['ga_experiment_variant']
        if experiment_variant == 1:
            items_per_page = 50

        gtm_data = make_gtm_data(request, extra_data={'expId': experiment_id, 'expVar': experiment_variant})

    # используется для ajax-запрос для формы поиска, установлен специально перед ненужными блоками перелинковки и т.п.
    if 'no_ads' in request.GET:
        items_list = Ad.objects.none()
        paginator = AdPaginator(items_list, items_per_page, request=request)
        return render(request, 'ad/search.jinja.html', locals())

    if settings.MESTO_SITE == 'mesto':
        # блоки ссылок для перелинковки (SEO от октября 2014)
        crosslinks_blocks = get_crosslinks(
            request.build_absolute_uri(), region, deal_type, property_type, rooms=rooms_filter_for_seo,
            subway_station=subway_filter_for_seo, current_language=request.LANGUAGE_CODE, scp=seo_klass.scp
        )

    # проверяем сохранен ли этот поиск у пользователя
    if request.user.is_authenticated():
        is_saved_search = request.build_absolute_uri() in request.user.get_savedsearch_urls()

    paginator = AdPaginator(items_list, items_per_page, request=request)

    # счетчики поисков
    if form.is_valid() and not request.is_ajax() and request.is_customer:
        count_search(deal_type, property_type, region, form, paginator.current_page_number)

    # отображение похожих результатов поиска
    if form.is_valid() and paginator.current_page_number == 1:
        if not paginator.current_page.object_list:
            related_results = search_related(base_items_list, deal_type, property_type, region, form.cleaned_data)
            callrequest_form = get_callrequest_form_for_search(request, related_results['agencies'], deal_type, property_type, region, query_parameters)
            return render(request, 'ad/search_related.jinja.html', locals())
        elif paginator.num_pages == 1:
            related_results = search_related(base_items_list, deal_type, property_type, region, form.cleaned_data, only_agencies=True)
            callrequest_form = get_callrequest_form_for_search(request, related_results['agencies'], deal_type, property_type, region, query_parameters)

    if request.is_ajax():
        return render(request, 'ad/results.jinja.html', locals())

    return render(request, 'ad/search.jinja.html', locals())

def prepare_to_serialize(obj):
    if isinstance(obj, Model):
        return obj.pk
    else:
        return obj

def count_search(deal_type, property_type, region, form, page):
    search_parameters = {
        'region': region,
        'deal_type': deal_type,
        'property_type': None if property_type == 'all-real-estate' else property_type,
        'rooms': [int(room) for room in form.cleaned_data['rooms']],
        'facilities': [facility.id for facility in form.cleaned_data['facilities']],
        'currency': form.cleaned_data['currency'] or 'UAH',
    }

    for attr in ('without_commission', 'area_from', 'area_to', 'price_from', 'price_to'):
        search_parameters[attr] = form.cleaned_data[attr]

    other_parameters = {}

    for key, value in form.cleaned_data.items():
        if key not in search_parameters.keys():
            if value:
                if not isinstance(value, types.StringTypes) and isinstance(value, collections.Iterable):
                    other_parameters[key] = [prepare_to_serialize(value_item) for value_item in value]
                else:
                    other_parameters[key] = prepare_to_serialize(value)

    if other_parameters:
        search_parameters['other_parameters'] = json.dumps(other_parameters, sort_keys=True, ensure_ascii=False)
    else:
        search_parameters['other_parameters'] = None

    today = datetime.date.today()
    searchcounters = SearchCounter.objects.filter(date=today, **search_parameters)
    if page == 1:
        updated_rows = searchcounters.update(
            searches_all_pages=F('searches_all_pages') + 1,
            searches_first_page=F('searches_first_page') + 1,
        )
    else:
        updated_rows = searchcounters.update(searches_all_pages=F('searches_all_pages') + 1)

    if updated_rows == 0:
        SearchCounter.objects.create(searches_all_pages=1, searches_first_page=1, date=today, **search_parameters)
    elif updated_rows > 1:
        # при одновременных запросах возможно появляение дублей,
        # вместе с оригиналом они будут наращивать счетчики, искажая статистику,
        # поэтому удаляем дубли при очередном (следующем после их возможного создания) обновлении
        for searchcounter in searchcounters[:1]:
            searchcounter.delete()

def get_callrequest_form_for_search(request, agencies, deal_type, property_type, region, query_parameters):
    from ppc.forms import CallRequestForm
    from ppc.models import CallRequest

    if 'callrequest' in request.POST:
        callrequest = CallRequest(referer=request.META.get('HTTP_REFERER'), ip=request.META.get('REMOTE_ADDR'),
                                  traffic_source=request.traffic_source)
        if request.user.is_authenticated():
            callrequest.user1 = request.user

        callrequest_form = CallRequestForm(request.POST, instance=callrequest)
        if callrequest_form.is_valid():
            # этот список агентств создается в search_related
            if callrequest_form.cleaned_data['destination']:
                agencies = agencies.filter(pk__in=callrequest_form.cleaned_data['destination'].split(','))

            callrequest = callrequest_form.save(commit=False)

            # здесь должен быть объект лога поиска или типа того
            qs_filters = dict(user_id=1, deal_type=deal_type, property_type=property_type, region=region, query_parameters=query_parameters)
            search = SavedSearch.objects.filter(**qs_filters).first()
            if not search :
                search = SavedSearch.objects.create(**qs_filters)

            callrequest.object = search
            presave_state = { fld.name: getattr(callrequest, fld.name) for fld in callrequest._meta.fields}

            for agency in agencies:
                callrequest = CallRequest(**presave_state)
                callrequest.user2 = agency.get_admin_user()
                try:
                    callrequest.save()
                except CallRequest.DuplicationException:
                    pass

            messages.info(request, _(u'Ваша заявка отправлена.<br/><br/>С вами свяжутся.'), extra_tags='modal-dialog-w400 modal-success')
    else:
        callrequest_form = CallRequestForm()

    return callrequest_form


# похожие результатов поиска
def search_related(base_ads, deal_type, property_type, region, cleaned_data, only_agencies=False):
    import collections
    from agency.models import Agency

    def get_url_from_cleaned_data(region, data):
        query = QueryDict(mutable=True)
        for key, values in data.items():
            if key in ['deal_type']:
                continue
            if not hasattr(values, '__iter__'):
                values = [values]

            for value in values:
                if value:
                    # getattr для обработки объектов типа Region
                    query.appendlist(key, unicode(getattr(value, 'id', value)))

        return clear_get(None, region, deal_type, property_type, query).get('redirect', '')

    results = {'searches': [], 'agencies': Agency.objects.none()}

    # применяем фильтр по регионам, если не применились фильтры по району/улице
    if region.kind == 'country' and region.slug == 'ukraina':
        ads_with_region = base_ads.filter(addr_country='UA')

    else:
        ads_with_region = base_ads.filter(region__in=region.get_descendants(True))

    # Поиск 1: меняем количество комнат вниз или вверх на один размер отображаем там где больше объявлений.
    # Если нет объявлений по этим критериям увеличиваем или уменьшаем на еще одну комнату.
    if not only_agencies and cleaned_data['rooms']:
        filter_ = cleaned_data.copy()
        rooms_original = int(filter_['rooms'][0])
        for rooms_diff in [-1, +1, -2, +2]:
            rooms_suggest = rooms_original + rooms_diff
            if 0 < rooms_suggest < 6:
                filter_['rooms'] = [rooms_suggest]

                ads_by_room = PropertyFilter(filter_, queryset=ads_with_region).qs
                if ads_by_room.count():
                    url = get_url_from_cleaned_data(region, filter_)
                    results['searches'].append({'filter': filter_.copy(), 'ads': ads_by_room, 'url': url})
                    break

    # Поиск 2: меняем стоимость на 20% вниз или вверх и отображаем там где больше объявлений.
    # Если нет объявлений по этим критериям увеличиваем % стоимости до 30, потом до 40% итд.
    if not only_agencies and any([cleaned_data['price_from'], cleaned_data['price_to']]):
        filter_ = cleaned_data.copy()
        price_treshold = 0.1
        for step in range(5):
            if filter_['price_from']:
                filter_['price_from'] = int(filter_['price_from'] * (1 - price_treshold))
            if filter_['price_to']:
                filter_['price_to'] = int(filter_['price_to'] * (1 + price_treshold))

            ads_by_price = PropertyFilter(filter_, queryset=ads_with_region).qs
            if ads_by_price.count():
                url = get_url_from_cleaned_data(region, filter_)
                results['searches'].append({'filter': filter_.copy(), 'ads': ads_by_price, 'url': url})
                break

    # Поиск 3: меняем район города где по остальным параметрам есть объявления.
    # Приоритет районам которые рядом с указными параметрами.
    # если район задан в ссылке, то переводим его в параметры
    if region.kind == 'district' and not cleaned_data['district']:
        cleaned_data['district'] = [region]

    if not only_agencies and cleaned_data['district']:
        filter_ = cleaned_data.copy()
        filter_['district'] = list(filter_['district'])
        for district in filter_['district'][:]:  # копия списка район делается, т.к. далее эта переменная меняется
            for nearest_district in district.get_siblings_by_distanse()[:10]:
                filter_['district'] = [nearest_district]
                ads_nearest = PropertyFilter(filter_, queryset=base_ads).qs
                if ads_nearest.count():
                    url = get_url_from_cleaned_data(region, filter_)
                    results['searches'].append({'filter': filter_.copy(), 'ads': ads_nearest, 'url': url})
                    break

    # поиск подходящих агентств
    agency_region = region
    while not results['agencies'] and agency_region and agency_region.kind not in ['country', 'group2']:
        target_ads = base_ads.filter(region__in=agency_region.get_descendants(True), bank=None,
                                     user__agencies__logo__gt='', user__agencies__show_in_agencies=True)
        user_stats = collections.Counter(target_ads.values_list('user__realtors__agency', flat=True))
        results['agencies'] = Agency.objects.filter(pk__in=dict(user_stats.most_common(4)).keys())
        agency_region = agency_region.parent

    return results


def streets(request, deal_type, region_slug=None, property_type='flat'):

    # разделям отфильтрованный список улиц на группы по первой букве
    def get_alphabetic_index(street_links, letter_limit=1):
        index = collections.defaultdict(list)
        for link in street_links:
            letter = link['name'][:letter_limit]
            if letter.isnumeric():
                letter = '1'
            index[letter].append(link)

        return collections.OrderedDict(sorted(index.items()))

    import collections

    region = Region.get_region_from_slug(region_slug, request.subdomain, request.subdomain_region)
    if not region or region.kind not in ['locality', 'district']:
        raise Http404

    # для ссылок на другие типы сделок в верхнем меню
    region_slug_for_menu = get_region_slug_for_menu(region)

    # Генерируем SEO метатеги по специальным правилам 
    seo_klass = SEO(current_language=request.LANGUAGE_CODE)
    seo = seo_klass.get_seo(
        region=region,
        deal_type=deal_type,
        subpage='streets',
        region_kind=region.kind,
    )

    selected_letter = request.GET.get('letter')

    cache_key = 'region%d_streets_%s_%s' % (region.id, deal_type, request.LANGUAGE_CODE)
    street_links = cache.get(cache_key)
    if not street_links:
        street_links = []
        for street in region.get_descendants()\
                       .filter(kind='street', region_counter__deal_type=deal_type, region_counter__count__gt=0)\
                       .extra(select={'ads_count': '"ad_regioncounter"."count"'}).order_by():
            street_links.append({
                'name': street.street_formatted_name,
                'ads_count': street.ads_count,
                'link': street.get_deal_url(deal_type),
            })
        street_links.sort(key=lambda x: x['name'])
        cache.set(cache_key, street_links, 60 * 60)

    # если улиц с активными объявлениями нет, то возвращаем на страницу поиска
    if not street_links:
        return redirect('.')

    # алфавитный указатель вообще всех улиц
    alphabetic_index = [letter for letter in get_alphabetic_index(street_links).keys()]

    # выделение самый популярных улиц, если не выбрана буква алфавитного указателя
    if not selected_letter:
        street_ad_counts = sorted([link['ads_count'] for link in street_links])
        count_limit = street_ad_counts[min(len(street_ad_counts), 50) * -1]
        street_links = filter(lambda x: x['ads_count'] > count_limit, street_links)
    else:
        if selected_letter == '1':
            street_links = filter(lambda x: x['name'][0].isnumeric(), street_links)
        else:
            street_links = filter(lambda x: x['name'].startswith(selected_letter), street_links)

    # список улиц разделенный по буквам
    streets_in_alphabetic_index = get_alphabetic_index(street_links, 2 if selected_letter else 1)

    return render(request, 'ad/streets.jinja.html', locals())


def subway(request, deal_type, region_slug=None, property_type='flat'):

    region = Region.get_region_from_slug(region_slug, request.subdomain, request.subdomain_region)
    if not region or region.kind not in ['locality', 'district']:
        raise Http404

    # для ссылок на другие типы сделок в верхнем меню
    region_slug_for_menu = get_region_slug_for_menu(region)

    subway_list = SubwayStation.objects.all()
    subway_dict = {}
    subway_lines = SubwayLine.objects.filter(city_id=region.id)

    for line in subway_lines:
        subway_dict[line] = subway_list.filter(subway_line_id=line)

    subway_url = region.get_deal_url(deal_type)

    # Генерируем SEO метатеги по специальным правилам 
    seo_klass = SEO(current_language=request.LANGUAGE_CODE)
    seo = seo_klass.get_seo(
        region=region,
        deal_type=deal_type,
        subpage='metro_stations',
        region_kind=region.kind,
    )

    return render(request, 'ad/subway.jinja.html', locals())


def districts(request, deal_type, region_slug=None, property_type='flat'):

    region = Region.get_region_from_slug(region_slug, request.subdomain, request.subdomain_region)
    if not region or region.kind not in ['locality']:
        raise Http404

    # для ссылок на другие типы сделок в верхнем меню
    region_slug_for_menu = get_region_slug_for_menu(region)

    districts_list = region.get_children().filter(kind='district').exclude(name__icontains=u'микрорайон').order_by('name')
    neighborhoods_list = region.get_children().filter(kind='district', name__icontains=u'микрорайон').order_by('name')

    region_links = []
    for district in districts_list:
        region_links.append({
            'name': district.name,
            'text': district.text.replace(region.text + ', ', ''),
            'link': district.get_deal_url(deal_type),
        })

    # Генерируем SEO метатеги по специальным правилам
    seo_klass = SEO(current_language=request.LANGUAGE_CODE)
    seo = seo_klass.get_seo(
        region=region,
        deal_type=deal_type,
        subpage='streets',
        region_kind=region.kind,
    )

    return render(request, 'ad/districts.jinja.html', locals())


def settlements(request, deal_type, region_slug=None, property_type='flat'):

    region = Region.get_region_from_slug(region_slug, request.subdomain, request.subdomain_region)
    if not region or region.kind not in ['province']:
        raise Http404

    # для ссылок на другие типы сделок в верхнем меню
    region_slug_for_menu = get_region_slug_for_menu(region)

    settlements_list = region.get_descendants().filter(kind__in=['locality', 'village']).order_by('name')

    region_links = []
    for settlement in settlements_list:
        region_links.append({
            'name': settlement.name,
            'text': settlement.text.replace(region.text + ', ', ''),
            'link': settlement.get_deal_url(deal_type),
        })

    # Генерируем SEO метатеги по специальным правилам
    seo_klass = SEO(current_language=request.LANGUAGE_CODE)
    seo = seo_klass.get_seo(
        region=region,
        deal_type=deal_type,
        subpage='streets',
        region_kind=region.kind,
    )

    return render(request, 'ad/districts.jinja.html', locals())


def get_deal_type_display(deal_type):
    return [row[1].title() for row in DEAL_TYPE_CHOICES if row[0] == deal_type][0]


def _check_region(region_name):
    regions = Region.objects.filter(name__icontains=region_name,kind__in=['locality','district']).order_by('-kind')

    if regions.count() > 0:
        return regions[0]
    else:
        return None


def _check_region_subdomain(region_name):
    regions = Region.objects.filter(name__icontains=region_name, kind__in=['locality', 'district'], subdomain=1).order_by('-kind')

    if regions.count() > 0:
        return regions[0]
    else:
        return None


def log_request_if_its_bad(request):
    # список IP-адресов, которые очень хорошо притворяются юзерами и проходят через проверки Distil
    # конкретно эти адреса вычислены по многократным запросам с параметром ?&p=1
    blacklist = ['46.148.30.', '46.148.31.',
                '79.110.17.', '79.110.18.', '79.110.19.', '79.110.25.',
                '91.200.80.', '91.200.81.', '91.200.82.', '185.14.192.',
                '185.50.250.', '185.50.251.',
                '193.9.158.']
    ip_in_blacklist = False
    for ip in blacklist:
        if request.META['REMOTE_ADDR'].startswith(ip):
            ip_in_blacklist = True
            break

    if request.method != 'POST' or ip_in_blacklist:
        logger = logging.getLogger('common')
        message = u'Request method %s, IP %s' % (request.method, request.META['REMOTE_ADDR'])
        if ip_in_blacklist:
            message += u' in blacklist'
        logger.debug(message)


def show_contacts(request, *args, **kwargs):
    item = Ad.objects.get(id=kwargs.get('id'))

    usercard = item.prepare_usercard(host_name=request.host.name, traffic_source=request.traffic_source)
    data = {
        'phone': usercard.get('phone'),
        'email': usercard.get('email'),
        'skype': usercard.get('skype'),
    }

    log_request_if_its_bad(request)

    # считаем просмотры для всех пользователей, кроме владельцев и ботов (хорошие боты имеют значение -1)
    if (
        request.method == 'POST' and
        request.is_customer and
        not (request.user.is_authenticated() and request.user == item.user)
    ):
        updated_rows = ViewsCount.objects.filter(
            basead=item, date=datetime.date.today(), is_fake=False).update(contacts_views=F('contacts_views')+1)
        if not updated_rows:
            ViewsCount.objects.create(basead=item, date=datetime.date.today(), contacts_views=1)

    return JsonResponse(data)


def cities_autocomplete(request):
    response = [] # TODO: переименовать во что-то более точное
    term = request.GET.get("term").strip().split()
    if term:
        international = Region.objects.get(slug='international').get_descendants(include_self=True)

        if request.subdomain == 'international':
            regions = Region.objects.filter(kind__in=['country', 'locality', 'village'], parent__in=international)
        else:
            regions = Region.objects.filter(kind__in=['locality', 'village'], region_counter__count__gt=0).exclude(parent__in=international)

        if len(term) == 1:
            regions = regions.filter(Q(name_ru__icontains=term[0]) | Q(name_uk__icontains=term[0]))
        else:
            for word in term:
                regions = regions.filter(text__icontains=word)

        for region in regions.select_related('parent__parent').order_by('-subdomain', 'kind', 'name').distinct():
            data = {
                'id': region.id,
                'name': region.name,
                'value': region.name,
                'static_url': region.static_url
            }
            if region.kind == 'village' or region.parent.kind not in ['province', 'group', 'group2']:
                if region.parent.parent:
                    data['name'] += '<br/><small>%s, %s</small>' % (region.parent.name, region.parent.parent.name)
                else:
                    data['name'] += '<br/><small>%s</small>' % region.parent.name

            response.append(data)

    return JsonResponse(response, safe=False)

# TODO: функция должна возвращать один тип данных. переделать
def region_cities(request, rid):
    province = get_object_or_404(Region, kind__in=['province', 'country'], id=rid)
    region_cities = province.get_descendants().filter(kind='locality').order_by('name')
    return render(request, 'includes/cities_list_4_column.jinja.html', locals())

def no_thumbnails(request):
    return HttpResponse('')
