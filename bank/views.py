# coding=utf-8
import datetime

from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Q, F
from django.http import Http404, HttpResponsePermanentRedirect, HttpResponse
from django.conf import settings
from django.middleware.csrf import get_token
from profile.models import SavedAd
from ad.models import Ad, ViewsCount, Region
from ad.forms import PropertySearchForm
from ad.views import clear_get, get_exclude_rules, get_price_range, get_banned_users, _check_region_subdomain
from seo.meta_tags import SEO, image_title
from bank.callback import CallbackForm
from bank.models import Bank, convert_to_bank, convert_to_ad
from utils.paginator import HandyPaginator
from staticpages.models import SimplePage

#main page
def index(request):
    banks = Bank.objects.filter(is_active=True, logo__gt='')
    autocomplete_list = sorted(set(Region.objects.filter(kind='locality').values_list('name',flat=True)))
    hot_offers = Ad.objects.filter(is_published=True, bank__isnull=False, region_id__gt=0).order_by('-modified').prefetch_related('photos')[:4]
    if request.subdomain is not None:
        return HttpResponsePermanentRedirect( '/residential/' )
    title = u'Банковская залоговая недвижимость Украины'
    return render(request, 'bank/index.html', locals())

def bank_list(request):
    bank_list = Bank.objects.filter(is_active=True)
    paginator = HandyPaginator(bank_list, 4, request=request)
    title = u'Список банков'
    return render(request, 'bank/bank_list.html', locals())

def bank_detail(request, id):
    bank = get_object_or_404(Bank, id=id, is_active=True)
    properties_count = Ad.objects.filter(is_published=True, bank_id=id).count()
    other_banks = Bank.objects.filter(is_active=True).exclude(id=id).order_by('?')[:3]
    title = u'Банк %s' % bank
    return render(request, 'bank/bank_detail.html', locals())

def search(request, deal_type, property_type, regions_slug=None, show_result=None):
    region  = Region.get_region_from_slug(regions_slug, '' if request.subdomain == 'bank' else request.subdomain, request.subdomain_region)
    if not region:
        raise Http404
    
    # весь список объявлений с указанном типом объявления
    items_list = Ad.objects.filter(bank__isnull=False, is_published=True, deal_type__in=deal_type.split(',')).exclude(get_exclude_rules())\
        .prefetch_related('region','photos','user')

    # применяем фильтр по регионам
    items_list = items_list.filter(region__in=region.get_descendants(True))

    ad_property_types = convert_to_ad(property_type)
    items_list = items_list.filter(property_type__in=ad_property_types)
    
    min_price, max_price = get_price_range('%s_%s_%s_bank' % (deal_type, property_type, region.pk), items_list)
    
    # применяем фильтры поиска
    if len(request.GET) > 0:
        form = PropertySearchForm(request.GET) # A form bound to the POST data
        
        if form.is_valid():
            if not (len(request.GET)== 1 and 'property_type' in request.GET):
                show_result = True
            
            # currency rate
            curr_rate = 1
            if ('currency' in form.cleaned_data and form.cleaned_data['currency'] and form.cleaned_data['currency'] != 'UAH') and ((form.cleaned_data['price_from'] > 0) or (form.cleaned_data['price_to'] > 0)):
                from utils.currency import get_currency_rates
                curr_rate = get_currency_rates()[form.cleaned_data['currency']]
                
            if form.cleaned_data['price_from'] > 0:
                items_list = items_list.filter(price_uah__gte=form.cleaned_data['price_from'] * curr_rate)
            if form.cleaned_data['price_to'] > 0:
                items_list = items_list.filter(price_uah__lte=form.cleaned_data['price_to'] * curr_rate)
            
            if form.cleaned_data['rooms']:
                Q_rooms = Q()
                for room in form.cleaned_data['rooms']:
                    if room.find('+') > 0:
                        Q_rooms = Q_rooms | Q(rooms__gte=room[:-1])
                    else:
                        Q_rooms = Q_rooms | Q(rooms=room)
                items_list = items_list.filter(Q_rooms)
                
            if form.cleaned_data['property_commercial_type']:
                items_list = items_list.filter(property_commercial_type=form.cleaned_data['property_commercial_type'])
            
            if form.cleaned_data['with_image'] > 0:
                items_list = items_list.filter(has_photos=True)
                
            if form.cleaned_data['without_commission'] > 0:
                items_list = items_list.filter(without_commission=True)

            if form.cleaned_data['sort']:
                items_list = items_list.order_by(form.cleaned_data['sort'])
                
            # ключевые слова
            if form.cleaned_data['keywords'] != '':
                keywords = form.cleaned_data['keywords'].split(',')
                criterions = Q()
                for keyword in keywords:
                    keyword = keyword.strip()
                    selected_region = _check_region_subdomain(keyword)
                    if type(selected_region) == Region:
                        if selected_region != region:
                            kwargs = {'property_type': property_type}
                            region_slug = selected_region.get_region_slug()
                            if region_slug:
                                kwargs['regions_slug'] = region_slug
                            url = selected_region.get_host_url('bank-ad-search-result', host='bank', kwargs=kwargs)
                            return HttpResponsePermanentRedirect(url)
                    criterions.add(Q(description__icontains=keyword) | Q(address__icontains=keyword), Q.AND)
                items_list = items_list.filter(criterions)
            
    else:
        try:
            # в __init__ подготовка списка регионов для формы
            form = PropertySearchForm(request.GET)
        except Region.DoesNotExist: # не найден активный регион в выпадающем списке
            return redirect('..')
    
    if not show_result:
        items_list = items_list.filter(has_photos=True).order_by('-updated')
        items_list = items_list[:4]
    else:
        pass

    items_list = items_list.prefetch_related('photos')

    paginator = HandyPaginator(items_list, 10, request=request)

    seo_klass = SEO(current_language=settings.LANGUAGE_CODE)
    seo = seo_klass.get_seo(
        region=region,
        deal_type=deal_type,
        property_type=ad_property_types[0],
    )

    return render(request, 'bank/search.html', locals())

def detail(request, property_type, id, regions_slug=None):
    region  = Region.get_region_from_slug(regions_slug, '' if request.subdomain == 'bank' else request.subdomain, request.subdomain_region)
       
    banks = Bank.objects.filter(is_active=True, logo__gt='')

    ad_property_types = convert_to_ad(property_type)

    try:
        item = Ad.objects.select_related('region').prefetch_related('photos').get(id=id, bank__isnull=False, property_type__in=ad_property_types)
        usercard = item.prepare_usercard(host_name=request.host.name)
    except (Ad.DoesNotExist, Http404, IndexError) :
        raise Http404
    
    if not region or (request.subdomain_region.kind != 'group' and item.region and item.region.static_url != region.static_url) :
        return redirect(item.get_bank_url())

    # на поддомене с группой регионов не проверяем корректность URL и региона в нем or \
    # исключаем объявления заблокированных пользователей и сами забаненные объявления
    if (item.status == 200 or not item.region or (item.user and item.user.pk in get_banned_users())):
        raise Http404

    # считаем просмотры
    updated_rows = ViewsCount.objects.filter(basead=item, date=datetime.date.today(), is_fake=False).update(detail_views=F('detail_views')+1)
    if not updated_rows:
        ViewsCount.objects.create(basead=item, date=datetime.date.today(), detail_views=1)
    
    item.image_title = image_title(item)
    title = item.address # TODO: добавить тип сделки к урлу
    
    if request.user.is_authenticated():
        item.saved = SavedAd.objects.filter(user=request.user, basead=item).count()
    
    callback_form = CallbackForm(initial={'property_id':item.id})
    csrf_token = get_token(request)
    
    return render(request, 'bank/detail.html', locals())


def simplepage(request, url):
    try:
        page = SimplePage.objects.get(urlconf='bank.urls', url=url)
    except SimplePage.DoesNotExist:
        raise Http404
    else:
        return render(request, 'bank/simplepage.html', {'page': page})

