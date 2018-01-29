# coding: utf-8

import collections

from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseGone
from django.http import HttpResponsePermanentRedirect
from django.http import HttpResponseRedirect
from django.http import QueryDict
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from django.db.models import Sum, Prefetch

from ad.models import Region, SubwayStation, Ad
from ad.views import clear_get, get_exclude_rules, search_related
from newhome.decorators import mark_unique_user
from newhome.filters import NewhomePropertyFilter
from newhome.forms import NewhomeSearchForm
from newhome.models import Newhome, Layout, Flat, NewhomePhoto
from ppc.models import ProxyNumber, get_lead_price
from profile.models import get_sorted_urlencode
from profile.views import get_banned_users
from seo.cross_linking import get_crosslinks
from seo.meta_tags import get_details_newhome_metatags, SEO
from seo.models import TextBlock
from utils.paginator import AdPaginator


def get_callrequest_form(request, newhome_id):
    """
    Запрос застройщику подробностей

    todo: перенести полностью в приложение mail
    todo: Информировать пользователя об успешности
    """
    from ppc.models import CallRequest
    from ppc.forms import CallRequestForm

    referer = request.META.get('HTTP_REFERER', '/')
    if request.method == 'POST':

        newhome = get_object_or_404(Newhome, id=newhome_id)
        callrequest = CallRequest(object=newhome, user2=newhome.user, referer=referer,
                                  ip=request.META.get('REMOTE_ADDR'), traffic_source=request.traffic_source)

        if request.user.is_authenticated():
            callrequest.user1 = request.user

        callrequest_form = CallRequestForm(request.POST, instance=callrequest)
        if callrequest_form.is_valid():
            callrequest_form.save()

    else:
        callrequest_form = CallRequestForm()

    return callrequest_form


@mark_unique_user
def detail(request, deal_type, id, region_slug=None, property_type=None):
    newhome_id = id
    region = Region.get_region_from_slug(region_slug, request.subdomain, request.subdomain_region)

    try:
        newhome = Newhome.objects.select_related('region').prefetch_related('newhome_photos').get(id=newhome_id)

    except (Newhome.DoesNotExist, Http404, IndexError):
        return HttpResponseGone(render_to_string('410.jinja.html', locals(), request=request))

    if not newhome.user.leadgeneration.is_shown_users_phone:
        callrequest_form = get_callrequest_form(request, newhome.pk)

    # подобные новостройки
    # similar_newhomes = Ad.objects.filter(deal_type='newhomes', status=1, region__in=request.subdomain_region.get_descendants(True))\
    #                        .exclude(pk=newhome.pk).select_related('region').prefetch_related('photos')[:4]
    similar_newhomes = []

    # Информация по этажам и квартирам
    (flats_rooms_options, flats_available, flats_prices_by_floor, flats_info_exists, flats_floor_options,
     flats_area_by_rooms, flats_prices_by_rooms, currency) = newhome.get_aggregation_floors_info(request)

    # ход строительства
    progress, progress_next, progress_prev = newhome.get_progress(request.GET.get('progress'))

    # на поддомене с группой регионов проверяем корректность URL и региона в нем
    # todo: может вынести в декоратор?
    if deal_type != 'newhomes' or not region and newhome.region \
            or (request.subdomain_region.kind != 'group' and newhome.region and newhome.region.static_url != region.static_url):
        return redirect(newhome.get_absolute_url())

    # исключаем объявления заблокированных пользователей и сами забаненные объявления + объявления робота
    if (newhome.status != 1 or (newhome.user_id and newhome.user_id in get_banned_users())) or not newhome.region:
        shown_only_for_you = [
            request.user.is_staff,
            request.user.has_perm('newhome.newhome_admin'),
            request.user.is_authenticated() and request.user.id == newhome.user_id,

            # Удаленные открываем только для админов
            newhome.status == 211 and any([request.user.is_staff, request.user.has_perm('newhome.newhome_admin')])
        ]

        # можно показать объявление владельцу или админу
        if not any(shown_only_for_you):
            messages.error(
                request,
                _(u'На данный момент выбранный Вами объект недоступен. Пожалуйста, выберите из списка доступных')
            )
            return HttpResponseRedirect(reverse('ad-search', kwargs={'deal_type': 'newhomes'}))

    # Готовим SEO
    title, description = get_details_newhome_metatags(region, newhome)

    # Телефон показываем только при балансе большем чем за одного лида у застройщика
    if (
        newhome.user.leadgeneration.is_shown_users_phone or
        newhome.user.get_balance() > get_lead_price('call', 'newhomes', 'high')
    ):
        developer_phone = ProxyNumber.get_numbers(newhome.user, 'newhomes', request.traffic_source, newhome)[0]

    else:
        developer_phone = None

    crosslinks_blocks = get_crosslinks(request.build_absolute_uri(), region, 'newhomes', 'flat',
                                       current_language=request.LANGUAGE_CODE, detail=True)

    return render(request, 'newhome/detail.jinja.html', locals())


@mark_unique_user
def layout_flat(request, deal_type, newhome_id, layout_id, region_slug=None):
    """
    Показываем планировку одной квартиры
    """

    callrequest_form = get_callrequest_form(request, newhome_id)

    layout = get_object_or_404(Layout, newhome=newhome_id, id=layout_id)

    return render(request, 'newhome/layout-flat.jinja.html', locals())


@mark_unique_user
def floors(request, deal_type, newhome_id, region_slug=None):
    """
    План этажа
    """

    callrequest_form = get_callrequest_form(request, newhome_id)

    newhome = get_object_or_404(Newhome, id=newhome_id)
    floor = newhome.floors.filter(id=request.GET['floor']).first()
    floor_number = floor.number
    layouts_ = list(floor.layouts.all().order_by('name'))

    unavailable_layouts = list(newhome.flats.filter(
        floor__id=floor.id, is_available=False
    ).values_list('layout__id', flat=True))

    available_flats = []

    if 'building' in request.GET:
        available_flats = Flat.objects.filter(building=request.GET['building'])
    else:
        # available_flats = Flat.objects.filter(building__newhome_id=newhome_id)
        for layout in floor.layouts.filter(rooms_total__gt=0):
            for flat in layout.layout_flats.all():
                flat.rooms = layout.rooms_total
                available_flats.append(flat)

    available_flats = {flat.rooms: flat for flat in available_flats}

    layouts_ordering = range(len(layouts_))

    # import random
    # random_by_url = random.Random()
    # random_by_url.seed(request.build_absolute_uri())
    # random_by_url.shuffle(layouts_ordering)
    #
    # for index in layouts_ordering:
    #     rooms = layouts_[index].rooms_total
    #     if available_flats.get(rooms):
    #         layouts_[index].price = available_flats[rooms].price
    #         if available_flats[rooms].is_available > 0:
    #             layouts_[index].available = True
    #             available_flats[rooms]['available'] -= 1

    return render(request, 'newhome/floor.jinja.html', locals())


@mark_unique_user
def layouts(request, deal_type, newhome_id, region_slug=None):
    """
    Планировки этажей для объявления
    """

    callrequest_form = get_callrequest_form(request, newhome_id)

    layout_floors = collections.defaultdict(list)
    layouts_ = Layout.objects.filter(newhome__id=newhome_id)

    if layouts_.exists():
        for layout in layouts_:
            # Получаем минимальную цену квартир с этой планировкой
            flats_ = Flat.objects.filter()
            layout.price = 0

            layout_floors[layout.rooms_total].append(layout)

        return render(request, 'newhome/layouts.jinja.html', locals())

    raise Http404


def search(request, deal_type, region_slug=None, property_type=None, subway_slug=None):
    region = Region.get_region_from_slug(region_slug, request.subdomain, request.subdomain_region)
    if not region:
        raise Http404

    if property_type is not None:
        return HttpResponsePermanentRedirect(request.path_info.replace('-%s/' % property_type, ''))

    property_type = 'flat'
    request.GET = clear_get(request, region, deal_type, property_type, request.GET.copy())
    if request.GET.get('redirect'):
        return HttpResponsePermanentRedirect(request.GET.get('redirect'))

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
    if region.kind == 'district':
        request.GET.appendlist('district', region.id)

    # весь список опубликованных активных объектов
    base_items_list = Newhome.objects.filter(status=1, is_published=True).order_by('-modified', '-pk')

    try:
        # копия GET-словаря нужна, т.к. ниже она модифицируется через form.data
        form = NewhomeSearchForm(request.GET)
        form.prepare_choices(region_for_search)

        # города и области, в которых есть новостройки
        # TODO: возможно, есть смысл сделать поле "город/область" у новостройки для упрощения алгоритма
        cities_with_newhomes = []
        cities_with_newhomes_in_province = []

        main_cities = Region.objects.get(static_url=';').get_descendants().filter(main_city=True).prefetch_related('parent')
        for city in main_cities:
            if city.parent.kind != 'province':
                raise Exception('Parent of city #%d is not province' % city)

        for path in Newhome.objects.filter(region__isnull=False, is_published=True).values_list('region__tree_path', flat=True).distinct():
            ids_in_path = [int(region_id) for region_id in path.split('.')]
            for city in main_cities:
                if city.id in ids_in_path:
                    if city not in cities_with_newhomes:
                        cities_with_newhomes.append(city)
                elif city.parent.id in ids_in_path and city not in cities_with_newhomes_in_province:
                    cities_with_newhomes_in_province.append(city)

        cities_with_newhomes.sort(key=lambda obj: obj.name)

    except Region.DoesNotExist:
        # не найден активный регион в выпадающем списке
        return redirect('..')

    # тип недвижимости берется из URL, а не из параметров GET
    form.data['deal_type'] = deal_type
    form.data['property_type'] = property_type

    region_filter_applied = False
    rooms_filter_for_seo = 0
    subway_filter_for_seo = 0
    filtered_by_region_search = False
    show_developer_intro = True

    if form.is_valid():
        items_list = NewhomePropertyFilter(form.cleaned_data, queryset=base_items_list).qs

        show_developer_intro = bool(filter(
            lambda key_: form.cleaned_data[key_],
            ['name', 'developer', 'rooms', 'subway_stations']
        ))

        region_filter_applied = bool(filter(
            lambda key_: form.cleaned_data[key_],
            ['region_search', 'addr_street_id', 'district']
        ))

        if len(form.cleaned_data['rooms']) == 1:
            rooms_filter_for_seo = form.cleaned_data['rooms'][0]

        if form.cleaned_data['subway_stations']:
            subway_filter_for_seo = form.cleaned_data['subway_stations'][0]

        for city in cities_with_newhomes:
            if region.id == city.id:
                if form.cleaned_data['region_search']:
                    items_list = items_list.filter(
                        region__in=city.parent.get_descendants(include_self=True)
                    ).exclude(
                        region__in=city.get_descendants(include_self=True)
                    )

                    filtered_by_region_search = True
                    region_filter_applied = True
                else:
                    items_list = items_list.filter(region__in=city.get_descendants(include_self=True))
                break
            else:
                items_list = items_list.filter(region__in=region.get_descendants(include_self=True))
    elif request.GET:
        items_list = Newhome.objects.none()
    else:
        items_list = base_items_list

    # применяем фильтр по регионам, если не применились фильтры по району/улице
    if not region_filter_applied:
        if region.kind == 'country' and region.slug == 'ukraina':
            pass

        elif not filtered_by_region_search:
            province = region.get_ancestors().filter(kind='province').first()

            # Добавлен 301 редирект на старые ссылки, что хранятся у поисковиков
            if province is None:
                return HttpResponsePermanentRedirect('/newhomes/')

            items_list = items_list.filter(region__in=province.get_descendants(True))

    # todo: временно убрано, т.к. данные не готовы к таким координальным переменам
    # todo: Prefetch('newhome_photos', queryset=NewhomePhoto.objects.filter(is_main=True))
    items_list = items_list.annotate(
        balance=Sum('user__transactions__amount')).filter(balance__gt=0).prefetch_related('newhome_photos', 'region')
    paginator = AdPaginator(items_list, 20, request=request)

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

    # блоки ссылок для перелинковки (SEO от октября 2014)
    crosslinks_blocks = get_crosslinks(
        request.build_absolute_uri(), region, 'newhomes', property_type, rooms=rooms_filter_for_seo,
        subway_station=subway_filter_for_seo, current_language=request.LANGUAGE_CODE, scp=seo_klass.scp
    )

    show_developer_intro = paginator.current_page_number == 1 and show_developer_intro

    # отображение похожих результатов поиска
    related_results = None
    related_newhomes = None
    if form.is_valid() and paginator.current_page_number == 1 and not paginator.current_page.object_list:
        related_newhomes = search_newhome_related(base_items_list, region, form.cleaned_data)

        base_items_list = Ad.objects.filter(is_published=True, deal_type='sale').exclude(
            get_exclude_rules()).prefetch_related('photos', 'region').order_by('-vip_type', '-updated', '-pk')

        form.cleaned_data.update({'property_type': 'flat'})
        related_results = search_related(base_items_list, 'sale', property_type, region, form.cleaned_data)

    response_status = None
    if not form.is_valid() or not len(paginator.current_page.object_list):
        response_status = 404

    return render(request, 'newhome/search.jinja.html', locals(), status=response_status)


def search_newhome_related(base_ads, region, cleaned_data):
    """похожие результатов поиска новостроек"""

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

        return u'?%s' % get_sorted_urlencode(query.lists()) if len(query) else ''

    results = {'searches': []}

    # применяем фильтр по регионам, если не применились фильтры по району/улице
    if region.kind == 'country' and region.slug == 'ukraina':
        ads_with_region = base_ads.filter(addr_country='UA')

    else:
        ads_with_region = base_ads.filter(region__in=region.get_descendants(True))

    # Поиск 1: меняем количество комнат вниз или вверх на один размер отображаем там где больше объявлений.
    # Если нет объявлений по этим критериям увеличиваем или уменьшаем на еще одну комнату.
    if cleaned_data['rooms']:
        filter_ = cleaned_data.copy()
        rooms_original = int(filter_['rooms'][0])
        for rooms_diff in [-1, +1, -2, +2]:
            rooms_suggest = rooms_original + rooms_diff
            if 0 < rooms_suggest < 6:
                filter_['rooms'] = [rooms_suggest]

                ads_by_room = NewhomePropertyFilter(filter_, queryset=ads_with_region).qs
                if ads_by_room.count():
                    url = get_url_from_cleaned_data(region, filter_)
                    results['searches'].append({'filter': filter_.copy(), 'ads': ads_by_room, 'url': url})
                    break

    # Поиск 2: меняем стоимость на 20% вниз или вверх и отображаем там где больше объявлений.
    # Если нет объявлений по этим критериям увеличиваем % стоимости до 30, потом до 40% итд.
    if any([cleaned_data['price_from'], cleaned_data['price_to']]):
        filter_ = cleaned_data.copy()
        price_treshold = 0.1
        for step in range(5):
            if filter_['price_from']:
                filter_['price_from'] = int(filter_['price_from'] * (1 - price_treshold))
            if filter_['price_to']:
                filter_['price_to'] = int(filter_['price_to'] * (1 + price_treshold))

            ads_by_price = NewhomePropertyFilter(filter_, queryset=ads_with_region).qs
            if ads_by_price.count():
                url = get_url_from_cleaned_data(region, filter_)
                results['searches'].append({'filter': filter_.copy(), 'ads': ads_by_price, 'url': url})
                break

    # Поиск 3: меняем район города где по остальным параметрам есть объявления.
    # Приоритет районам которые рядом с указными параметрами.
    # если район задан в ссылке, то переводим его в параметры
    if region.kind == 'district' and not cleaned_data['district']:
        cleaned_data['district'] = [region]

    if cleaned_data['district']:
        filter_ = cleaned_data.copy()
        filter_['district'] = list(filter_['district'])
        for district in filter_['district'][:]:  # копия списка район делается, т.к. далее эта переменная меняется
            for nearest_district in district.get_siblings_by_distanse()[:10]:
                filter_['district'] = [nearest_district]
                ads_nearest = NewhomePropertyFilter(filter_, queryset=base_ads).qs
                if ads_nearest.count():
                    url = get_url_from_cleaned_data(region, filter_)
                    results['searches'].append({'filter': filter_.copy(), 'ads': ads_nearest, 'url': url})
                    break

    return results
