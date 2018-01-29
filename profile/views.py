# coding: utf-8
import os
import datetime
import json
import logging
import re
import urllib
import uuid

from functools import wraps
from PIL import Image

from django import forms
from django.contrib import messages
from django.db import transaction as db_transaction
from django.shortcuts import redirect, render, get_object_or_404
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect, Http404, HttpResponseBadRequest, JsonResponse
from django.db.models import Sum, F, Count
from django.conf import settings
from django.utils.translation import ugettext as _
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.views import login as login_view
from django.contrib.sites.requests import RequestSite

from ajaxuploader.views.base import AjaxFileUploader

from ad.models import Ad, Region, Photo, ViewsCount, PHOTO_THUMBNAILS, Phone
from ad.forms import PropertyForm, AdPhonesFormSet, UserPhonesFormSet
from ad.phones import validate
from custom_user.models import User, UserPhone
from callcenter.models import ManagerCallRequest
from newhome.models import Newhome
from paid_services.models import VipPlacement, Transaction, Plan, UserPlan, CatalogPlacement, Order, InsufficientFundsError
from paid_services.views import get_plan_action
from ppc.models import LeadGeneration
from ppc.forms import LeadGenerationForm
from profile.forms import ProfileForm, EmailForm
from profile.models import Ban, EmailChange, SavedAd, SavedSearch, get_banned_users, Notification
from staticpages.models import ContentBlock
from utils import ajax_upload
from utils.currency import get_currency_rates
from utils.decorators import update_ads_status
from utils.new_thumbnails import Thumbnailer, save_to_jpeg_content
from utils.storage import overwrite
from utils.paginator import HandyPaginator

def auth_logout(request):
    if request.user.is_authenticated():
        logout(request)
        if 'next' in request.GET:
            response = redirect(request.GET['next'])
        else:
            response = redirect('index')
        response.delete_cookie('user_location')
        return response
    return redirect('index')


def auth_login(request):
    if not request.user.is_authenticated():
        return login_view(request, template_name='profile/login.jinja.html')
    else:
        return redirect('index')

def check_ban(func):
    @wraps(func)
    def decorated_view(request, *args, **kwargs):
        if request.user.id in get_banned_users():
            bans = request.user.bans.filter(expire_date__gt=datetime.datetime.now())
            title = _(u'Аккаунт заблокирован')
            return render(request, 'profile/ban.jinja.html', locals())
        else:
            return func(request, *args, **kwargs)
    return decorated_view


@login_required
def index(request):
    title = _(u'Личный кабинет')
    content = ContentBlock.objects.get(name='account_index').content
    description = ''
    return render(request, 'profile/index.jinja.html', locals())


@login_required
def edit_profile(request):
    initial_phones = [{'phone': nubmer} for nubmer in request.user.phones_m2m.values_list('phone_id', flat=True)]
    initial = {'is_realtor': bool(request.user.get_agency()), 'is_developer': request.user.is_developer()}

    if request.method == 'POST' and 'profile_form' in request.POST:
        form = ProfileForm(request.POST, request.FILES, instance=request.user, initial=initial)
        phones_formset = UserPhonesFormSet(request.POST, initial=initial_phones, prefix='phones', user=request.user)

        if form.is_valid() and phones_formset.is_valid():
            form.save()
            phones_formset.update_phones_m2m(request.user.phones_m2m)

            if 'is_realtor' in form.changed_data and form.cleaned_data['is_realtor']:
                request.user.create_agency()
            if 'is_developer' in form.changed_data and form.cleaned_data['is_developer']:
                request.user.create_developer()

            return HttpResponseRedirect(reverse(edit_profile))
    else:
        phones_formset = UserPhonesFormSet(initial=initial_phones, prefix='phones', user=request.user)
        form = ProfileForm(instance=request.user, initial=initial)

    leadgeneration = request.user.get_leadgeneration()
    if request.method == 'POST' and 'leadgeneration_form' in request.POST:
        leadgeneration_form = LeadGenerationForm(request.POST, instance=leadgeneration)
        if leadgeneration_form.is_valid():
            leadgeneration = leadgeneration_form.save(commit=False)
            leadgeneration.user = request.user

            # Если застройщики Укрбуд, Киевгорстрой, Интегралбуд или Дарий Бендарчик
            # то мы им разрешаем показывать собственные телефоны, вместо наших
            if request.user.id in [129163, 128586, 128226, 147304]:
                leadgeneration.is_shown_users_phone = True

            leadgeneration.save()
            if 'next' in request.POST:
                return redirect(request.POST['next'])
    else:
        leadgeneration_form = LeadGenerationForm(instance=leadgeneration)

    # удаление привязки к соц. сетям
    if 'social_link_disconnect' in request.GET:
        request.user.social_auth.filter(pk=request.GET['social_link_disconnect']).delete()
        return redirect(edit_profile)

    enabled_social_auths = [
        {'key':'vkontakte', 'backend':'vk-oauth2', 'name':u'ВКонтакте'},
        {'key':'facebook', 'backend':'facebook', 'name':u'Facebook'},
        {'key':'google', 'backend':'google-oauth2', 'name':u'Google'},
        {'key':'twitter', 'backend':'twitter', 'name':u'Twitter'},
    ]

    title = _(u'Редактирование профиля')

    # Для риелтора (ограничение в шаблоне) с лидогенерацией дополнительно проверяем необходимость пополнения баланса
    money_to_activate_ad = 0
    if request.user.has_active_leadgeneration() and request.user.get_balance() < 10:
        money_to_activate_ad = int(200 - request.user.get_balance())

    return render(request, 'profile/edit_profile.jinja.html', locals())


@login_required
def manager_callrequest(request):
    phone = validate(request.POST['phone'])
    ManagerCallRequest.objects.create(user1=request.user, phone=phone, ip=request.META.get('REMOTE_ADDR'))
    messages.info(
        request, _(u'Заявка принята.<br/>Менеджер вам перезвонит.'),
        extra_tags='modal-dialog-w400 modal-success'
    )
    return redirect(request.META.get('HTTP_REFERER', reverse('index')))


@login_required
@check_ban
@update_ads_status
def my_properties(request, agency_realtors=None):
    # возможность подглядывать в личные кабинеты пользователей
    if request.user.is_staff and request.GET.get('override_user'):
        from custom_user.models import User
        request.user = User.objects.get(pk=request.GET.get('override_user'))

    # временное исключение для юзера. который не хочет видить объявления риелторов у себя в кабине
    if request.user.id == 114818:
        items_list = Ad.objects.filter(user=request.user).exclude(status=211)
    else:
        items_list = Ad.objects.filter(user__in=request.user.get_owned_users(request)).exclude(status=211)

    ads_groups_counts = {
        'active': 0,
        'inactive': 0,
        'rejected': 0,
        'vip': 0,
        'import': 0,
        '': 0,
    }
    for values in items_list.values('vip_type', 'status', 'moderation_status', 'xml_id').order_by().annotate(count=Count('id')):
        ads_groups_counts[''] += values['count']

        if values['moderation_status']:
            ads_groups_counts['rejected'] += values['count']
        elif values['status'] == 1:
            ads_groups_counts['active'] += values['count']
        elif values['status'] == 210:
            ads_groups_counts['inactive'] += values['count']

        if values['vip_type']:
            ads_groups_counts['vip'] += values['count']

        if values['xml_id']:
            ads_groups_counts['import'] += values['count']


    # TODO: может вообще сделать только по -id сортировку?
    items_list = items_list.select_related('user', 'region').prefetch_related('photos').order_by('-updated', '-pk')

    class FilterForm(forms.Form):
        status = forms.ChoiceField(required=False, choices=(
            ('', _(u'Все объявления')),
            ('active', _(u'Активные')),
            ('inactive', _(u'Неактивные')),
            ('vip', _(u'VIP')),
            ('rejected', _(u'Отклоненные')),
            ('import', _(u'Импорт')),
        ))
        deal_type = forms.ChoiceField(required=False, choices=(
            ('', _(u'Все типы сделки')),
            ('sale', _(u'Продажа')),
            ('rent', _(u'Долгосрочная аренда')),
            ('rent_daily', _(u'Посуточно')),
            # ('newhomes', _(u'Новостройка')),
        ))
        property_type = forms.ChoiceField(required=False, choices=(
            ('', _(u'Вся недвижимость')),
            ('flat', _(u'Квартира')),
            ('room', _(u'Комната')),
            ('house', _(u'Дом')),
            ('plot', _(u'Участок')),
            ('commercial', _(u'Коммерческая')),
            ('garages', _(u'Гаражи')),
        ))
        search = forms.CharField(required=False)

    filter_form = FilterForm(request.GET)
    if not filter_form.is_valid():
        redirect(reverse('profile_my_properties'))

    # Статус объявления
    status = filter_form.cleaned_data['status']

    if status == 'rejected':
        items_list = items_list.filter(moderation_status__isnull=False)
    elif status == 'active':
        items_list = items_list.filter(status=1)
    elif status == 'inactive':
        items_list = items_list.filter(status=210)
    elif status == 'vip':
        items_list = items_list.filter(pk__in=VipPlacement.objects.filter(is_active=True).values('basead'))
    elif status == 'import':
        items_list = items_list.exclude(xml_id=None)

    # Тип сделки
    deal_type = filter_form.cleaned_data['deal_type']
    if deal_type:
        items_list = items_list.filter(deal_type=deal_type)

    # Тип недвижимости
    property_type = filter_form.cleaned_data['property_type']
    if property_type:
        items_list = items_list.filter(property_type=property_type)

    search = filter_form.cleaned_data['search'].strip()
    if search:
        if search.isdigit():
            items_list = items_list.filter(id=search)

            # при поиске по ID сбрасываются другие фильтры
            filter_form = FilterForm({'search': search})
            # в шаблонах используется cleaned_data
            filter_form.is_valid()
        else:
            items_list = items_list.filter(address__icontains=search)

    paginator = HandyPaginator(items_list, 10, request=request, per_page_variants=[5, 10, 20, 50])

    views_by_ad = get_views_for_ads(paginator.current_page.object_list)

    from ad.choices import DEACTIVATION_REASON_CHOICES

    vips = {}
    for vip in VipPlacement.objects.filter(is_active=True, basead__ad__user__in=request.user.get_owned_users(request)):
        vips[vip.basead_id] = vip

    title = _(u'Мои объявления')
    template = 'profile/my_properties.jinja.html' if not request.own_agency else 'agency/agency_ads.jinja.html'
    return render(request, template, locals())


def get_views_for_ads(ads):
    viewscount_queryset = ViewsCount.objects.filter(
        basead__in=ads,
        is_archived=False
    ).values('basead').annotate(
        detail_views=Sum('detail_views'),
        contacts_views=Sum('contacts_views')
    )

    views_by_ad = {}
    for row in viewscount_queryset:
        views_by_ad[row['basead']] = {
            'detail_views': row['detail_views'],
            'contacts_views': row['contacts_views'],
        }
    return views_by_ad


@login_required
def views_graph(request, property_id):
    property = get_object_or_404(Ad, id=property_id)
    if not request.user.is_staff and property.user != request.user:
        raise Http404("Forbidden")

    today = datetime.datetime.today()
    date_list = [today - datetime.timedelta(days=x) for x in range(0, 30)]
    start = date_list[-1]

    tmp = { date.strftime('%Y.%m.%d') : [0, 0, date.strftime('%d.%m')] for date in date_list }
    for stat in ViewsCount.objects.filter(basead=property, date__gte=start, is_archived=False):
        day = stat.date.strftime('%Y.%m.%d')
        tmp[day][0] += stat.detail_views
        tmp[day][1] += stat.contacts_views

    data = sorted(tmp.items(), key=lambda stat: stat[0])
    return render(request, 'profile/views_graph_highcharts.jinja.html', locals())


@login_required
def clear_views_graph(request, property_id):
    property = get_object_or_404(Ad, id=property_id)
    if not request.user.is_staff and property.user != request.user:
        raise Http404("Forbidden")

    ViewsCount.objects.filter(basead=property, date__lt=datetime.date.today()).update(is_archived=True)

    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))


@login_required
@check_ban
def edit_property(request, property_id=None):
    # если есть активный план, но лимит исчерпан, то должна быть неактивна кнопка "Добавить объявление"
    # но если вдруг юзер открыл страницу добавления, то шел бы он лучше на страницу тарифов
    if not property_id and request.subdomain != 'international' and request.user.region and not request.active_plan and not request.user.has_active_leadgeneration():
        # юзера с недавней лидогенерацией кидаем на форму пополнения баланса
        if request.user.get_leadgeneration('ads'):
            return redirect(reverse('services:lead_activate') + '?next=%s&show_topup' % request.path)
        else:
            messages.info(request, _(u'Выберете способ размещения, перед тем как добавлять объявления.'), extra_tags='modal-style1 text-center')
            return redirect(reverse('services:index') + '?next=%s' % request.path)

    if property_id:
        title = _(u'Редактирование объявления')
        try:
            property = Ad.objects.get(user__isnull=False, id=property_id)
            property._edit_from_cabinet = True
        except Ad.DoesNotExist:
            raise Http404

        if property.user != request.user:
            can_edit = False

            if property.newhome_layouts.exists():
                if request.user.has_perm('newhome.newhome_admin'):
                    can_edit = True
            else:
                if request.own_agency and property.user.get_agency() == request.own_agency:
                    can_edit = True

            if not can_edit:
                raise Http404

        property.images = Photo.objects.filter(basead=property)
    else:
        title = _(u'Добавление объявления')
        property = Ad(user=request.user)

        # чтобы не подставлялись дефолтные значения в форму (задумка дизайнера)
        property.deal_type = None
        property.property_type = None

    initial = {'is_agency': property.user.get_agency() is not None}
    if property_id:
        initial.update(property.reserved_json())
        initial_phones = property.phones_in_ad.values('phone')
    else:
        initial_phones = [{'phone': phone} for phone in request.user.phones.values_list('number', flat=True)]

    if request.method == 'POST':
        phones_formset = AdPhonesFormSet(request.POST, initial=initial_phones, prefix='phones')
        form = PropertyForm(
            request.POST, request.FILES, instance=property, initial=initial, language_code=request.LANGUAGE_CODE
        )
        if form.is_valid() and phones_formset.is_valid():
            property = form.save()
            phones_formset.update_phones_m2m(property.phones_in_ad)

            if getattr(form, 'update_m2m_reservations', False):
                property.update_reserved_from_json(form.cleaned_data['reserved'])

            uploading_images(request, property)

            # логируем факт добавления объявлений
            if not property_id:
                logger_data = {'ip': request.META['REMOTE_ADDR'] , 'user': request.user.id}
                action_logger = logging.getLogger('user_action')
                action_logger.debug('Property %s has been created' % property.id, extra=logger_data)

            json_resposnse = {'success': True}

            # редиректы
            checkout_params = {}

            if form.cleaned_data.get('international', 'no') == 'yes' and property.id not in CatalogPlacement.get_active_user_ads():
                checkout_params['intl_catalog'] = 'intl_mesto'
            if form.cleaned_data.get('uk_to_international') and property.addr_country == 'UA' and property.id not in CatalogPlacement.get_active_user_ads():
                checkout_params['intl_catalog'] = 'worldwide'

            promotion = form.cleaned_data.get('promotion')
            if promotion == 'vip' and not property.vip_type:
                checkout_params['vip'] = ''

            # покупка услуг для объявления
            if 'vip' in checkout_params or 'intl_catalog' in checkout_params:
                checkout_params['ads'] = property.id
                json_resposnse['redirect_url'] = reverse('profile_checkout') + '?%s' % urllib.urlencode(checkout_params)
            else:
                json_resposnse['redirect_url'] = reverse('profile_my_properties')

            # если это объявление в Украине и нет тарифа, а так же обявление новое или планируется покупка доп. услуг, то сначала перекидывам на покупку тарифа
            if property.addr_country == 'UA' and property.status != 1 and \
                    ('ads' in checkout_params or not property_id):
                # обычных юзеров шлем на выбор плана, остальных - на выбор типа размещения
                if property.user.get_realtor() or property.user.is_developer():
                    json_resposnse['redirect_url'] = reverse('services:index') + '?%s' % urllib.urlencode(checkout_params)
                else:
                    json_resposnse['redirect_url'] = reverse('services:plans') + '?%s' % urllib.urlencode(checkout_params)

            return JsonResponse(json_resposnse)

        else:
            errors = dict(form.errors)
            for index, phone_form_errors in enumerate(phones_formset.errors):
                for key, value in phone_form_errors.iteritems():
                    errors['%s-%s-%s' % (phones_formset.prefix, index, key)] = value
            json_resposnse = {'success': False, 'errors': errors}

        return JsonResponse(json_resposnse)

    else:
        form = PropertyForm(instance=property, initial=initial, language_code=request.LANGUAGE_CODE, subdomain=request.subdomain)
        phones_formset = AdPhonesFormSet(initial=initial_phones, prefix='phones')

    description = ''
    return render(request, 'profile/my_property_form.jinja.html', locals())


# обработка загружаемых фото вынесена в отдельную функцию, т.к. функция стала слишком длинной
def uploading_images(request, ad):
    # обновление подписей фото и поля сортировка
    photos_by_id = {photo.id: photo for photo in ad.photos.all()}
    for key, value in request.POST.items():
        match = re.match(r'image_order_(\d+)', key)
        if match:
            photo_id = int(match.group(1))
            order = int(value) or 1000
            caption = request.POST.get('image_caption_%s' % photo_id)
            photo = photos_by_id.get(photo_id)

            if photo:
                if photo.caption != caption or photo.order != order:
                    Photo.objects.filter(id=photo_id).update(order=order, caption=caption)

                rotated_image_name = request.POST.get('image_rotated_%s' % photo_id)
                if rotated_image_name:
                    old_thumbnailer = Thumbnailer(photo.image.name, PHOTO_THUMBNAILS)
                    old_thumbnailer.delete()
                    default_storage.delete(photo.image.name)

                    # новое имя файла (и, следовательно, превью) позволяет обойти проблему с кешированием в CDN
                    rotated_image_path = u'%s/%s' % (settings.AJAX_UPLOAD_DIR, rotated_image_name)
                    photo.image.save('', default_storage.open(rotated_image_path))

                    thumbnailer = Thumbnailer(photo.image.name, PHOTO_THUMBNAILS)
                    thumbnailer.create()

    new_images = []
    for filename in request.POST.getlist('ajax_add_images'):
        # должно приходить имя файла, а не путь к файлу, иначе - подозрительно
        if os.path.basename(filename) == filename:
            path = u'%s/%s' % (settings.AJAX_UPLOAD_DIR, filename)
            if default_storage.exists(path):
                content = default_storage.open(path).read()
                new_images.append([filename, ContentFile(content)])
        else:
            raise Exception('Suspicious image filename')

    # загрузка файлов без AJAX
    for f in request.FILES.getlist('add_images'):
        new_images.append([f.name, f])

    for name, content in new_images:
        img = Photo(basead=ad)
        img.caption = request.POST.get('ajax_image_caption_%s' % name)
        img.order = request.POST.get('ajax_image_order_%s' % name) or 1000
        img.image.save(name, content)

    if request.POST.getlist('delete_images'):
        Photo.objects.filter(basead=ad, pk__in=request.POST.getlist('delete_images')).delete()


@login_required
def saved_searches(request):
    searches_list = list(SavedSearch.objects.filter(user=request.user).order_by('created'))

    for search in searches_list:
        search.day = search.created.date()

    if request.GET:
        item = get_object_or_404(SavedSearch, id=request.GET.get('saved_search_id'))
        item.subscribe = request.GET.get('subscribe')
        item.save()
        return HttpResponseRedirect(reverse(saved_searches))
    title = _(u'Сохраненные поиски')
    return render(request, 'profile/saved_searches.jinja.html', locals())


@login_required
def saved_properties(request):
    items_list = SavedAd.objects.filter(user=request.user).order_by('-created')
    paginator = HandyPaginator(items_list, 10, request=request)
    title = _(u'Сохраненные объявления')
    return render(request, 'profile/saved_properties.jinja.html', locals())


@login_required
def save_property(request, property_id):
    property = Ad.objects.get(pk=property_id)

    def _save_property(user, property):
        obj, created = SavedAd.objects.get_or_create(user=user, basead=property)
        if not created: obj.delete()  # удаляем из израбнного, если объявления уже находилось в избранном
        return 'add' if created else 'delete'

    response = _save_property(request.user, property)
    if 'ajax' in request.GET:
        response = HttpResponse(response)
        response['Access-Control-Allow-Origin'] = request.META.get('HTTP_ORIGIN')
        response['Access-Control-Allow-Credentials'] = 'true'
        return response
    else:
        return HttpResponseRedirect(reverse(saved_properties))


@login_required
def clear_saved_properties(request):
    SavedAd.objects.filter(user=request.user).delete()
    return HttpResponseRedirect(reverse(saved_properties))


@login_required
def save_search(request, subscribe=False):
    qs_filters = {
        'user': request.user,
        'deal_type': request.GET['deal_type'],
        'property_type': request.GET['property_type'],
        'region': Region.objects.get(id=request.GET['region']),
        'query_parameters': SavedSearch.extract_query_parameters_from_querydict(request.GET),
    }

    now = datetime.datetime.now()
    try:
        search, created = SavedSearch.objects.update_or_create(defaults={'created': now, 'subscribe': subscribe}, **qs_filters)
    except SavedSearch.MultipleObjectsReturned:
        # удаляем дубликаты
        searches = SavedSearch.objects.filter(**qs_filters)
        searches.exclude(pk=searches[0]).delete()
        searches[0].subscribe = subscribe
        searches[0].created = now
        searches[0].save()

    messages.info(request, _(u'Поиск сохранен.<br/><br/>Вы будете получать уведомления о новых объявлениях на вашу почту'),
                  extra_tags='modal-dialog-w400 modal-success')

    return HttpResponseRedirect(search.get_full_url())


@login_required
def delete_saved_searches(request, search_id):
    SavedSearch.objects.get(pk=search_id, user=request.user).delete()
    return HttpResponseRedirect(reverse(saved_searches))


@login_required
def clear_saved_searches(request):
    SavedSearch.objects.filter(user=request.user).delete()
    return HttpResponseRedirect(reverse(saved_searches))


@login_required
@check_ban
def change_email(request):
    if request.method == 'POST':
        form = EmailForm(request.POST)
        if form.is_valid():
            change = EmailChange(
                user=request.user,
                old_email=request.user.email,
                new_email=form.cleaned_data['email']
            )
            change.create_key()
            change.save()
            change.send_mail(RequestSite(request))
    else:
        form = EmailForm()
    return render(request, 'profile/change_email.jinja.html', locals())


def confirm_email_change(request, key):
    try:
        change = EmailChange.objects.get(confirmation_key=key)
    except EmailChange.DoesNotExist:
        raise Exception('There is no such key %s' % key)
    else:
        if change.status != 'inactive':
            return HttpResponse(u'Ошибка. Данная заявка на изменение email адреса %s' % {
                'confirmed': u'уже подтверждена',
                'cancelled': u'отменена',
            }[change.status])
        elif User.objects.filter(email__iexact=change.new_email).exists():
            return HttpResponse(u'Ошибка. Пользователь с email "%s" уже зарегистрирован' % change.new_email)
        else:
            with db_transaction.atomic():
                change.user.email = change.new_email
                change.user.save()
                change.status = 'confirmed'
                change.save()
                # ожидающие заявки этого пользователя нужно отменять, иначе при их активации
                # old_email в них будет неверным и хронологию событий будет невозможно восстановить
                EmailChange.objects.filter(user=change.user, status='inactive').update(status='cancelled')

            change.user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, change.user)

            content = _(u'<span class="pink h5">E-mail успешно изменен!</span><br><br>Ваш новый E-mail - %s') % change.user.email
            messages.info(request, content, extra_tags='modal-success text-center')

            return redirect('profile_settings')

import_uploader = login_required(AjaxFileUploader(backend=ajax_upload.StorageBackend, UPLOAD_DIR=settings.AJAX_UPLOAD_DIR))

@login_required
def rotate_ad_photo(request):
    if request.method == 'POST':
        if 'photo_id' in request.POST:
            photo_id = int(request.POST['photo_id'])
            photo = Photo.objects.get(id=photo_id, basead__ad__user=request.user)
            old_path = photo.image.name
        else:
            if 'image_name' in request.POST:
                old_name = request.POST['image_name']
                # должно приходить имя файла, а не путь к файлу, иначе - подозрительно
                if os.path.basename(old_name) == old_name:
                    old_path = u'%s/%s' % (settings.AJAX_UPLOAD_DIR, old_name)
                else:
                    raise Exception('Suspicious image filename')
            else:
                return HttpResponseBadRequest()

        # новое имя файла (и, следовательно, превью) позволяет обойти проблему с кешированием в CDN
        new_name = 'u%d_rotated_%s.jpg' % (request.user.id, uuid.uuid4().hex)
        new_path = u'%s/%s' % (settings.AJAX_UPLOAD_DIR, new_name)

        old_image = Image.open(default_storage.open(old_path))
        rotated_image = old_image.transpose(Image.ROTATE_270)
        overwrite(new_path, save_to_jpeg_content(rotated_image))

        thumbnailer = ajax_upload.UploadThumbnailer(new_path, ajax_upload.AD_THUMBNAILER_PARAMETERS)
        thumbnailer.create()
        thumbnail_url = thumbnailer.get_url(None)

        return JsonResponse({
            'new_name': new_name,
            'new_thumbnail_url': thumbnail_url,
        })


@login_required
def set_language(request, language_code):
    request.user.language = language_code
    request.user.save()
    return HttpResponseRedirect(request.GET['next'], language_code)


# Полученеи списка доступных платных услуг
# Суть в том, что GET-параметры из checkout так же используются в purchase (ads/vip/plan/intl_catalog)
# Только в первом случае они используются для вывода в списке услуг, а во втором для подтверждения и оплаты
def get_checkout_options(func):
    @wraps(func)
    def decorated_view(request, *args, **kwargs):
        title = _(u'Подтверждение заказа')

        # Делаем копию словаря, т.к. при работе с VIP у нас есть необходимость добавлять тарифный план к покупке
        request_get = request.GET.copy()

        if 'realtor' in request_get:
            user_recipient = request.user.get_own_agency().get_realtors().get(pk=request_get['realtor']).user
        else:
            user_recipient = request.user

        # берется общий баланс риелтора и админа, чтобы знать нужно ли будет переводить на платежную систему
        # или хватит перевода денег с админского аккаунта
        balance = request.user.get_balance(force=True)
        if user_recipient != request.user:
            balance += user_recipient.get_balance(force=True)

        region = user_recipient.region or Region.get_capital_province()

        if 'ads' in request_get:
            ads = Ad.objects.filter(id__in=request_get['ads'].split(','), user__in=user_recipient.get_owned_users(request))
        else:
            ads = Ad.objects.none()

        total_amount = 0
        payback = 0

        # VIP
        if 'vip' in request_get:
            ads_to_vip = ads.exclude(pk__in=VipPlacement.objects.filter(is_active=True).values('basead'))
            vips_amount = sum(user_recipient.get_paidplacement_price(ad, 'vip') for ad in ads_to_vip)
            total_amount += vips_amount

            # Если не хватает активного плана для работы с VIP на время действия VIP,
            # то предлагаем пролонгацию плана
            user_plan = user_recipient.get_active_plan()
            if user_plan is not None and user_plan.get_days_to_finish() < 7:
                request_get['plan'] = user_plan.plan_id

        # зарубежные каталоги
        selected_catalogs = request_get.getlist('intl_catalog')
        if selected_catalogs:
            # TODO international_crutch: убрать поднятие зарубежных объявления при работе тарифа
            # для международной недвижимости нет тарифов
            plans = None

            intl_catalogs = {
                'intl_mesto': {'name': _(u'Размещение зарубежной недвижимости на сайте mesto.ua'), 'amount':0 },
                'worldwide': {'name': _(u'Размещение в международных каталогах'), 'amount':0} ,
            }

            ads_to_intl = ads.exclude(id__in=CatalogPlacement.get_active_user_ads())

            # для недвижимости на украине размещения на нашем сайте бесплатно
            if ads_to_intl.exists() and ads_to_intl[0].addr_country == 'UA':
                del intl_catalogs['intl_mesto']

            # недвижимость вне украины мы не можем публиковать на сайтах-партнеров
            if ads_to_intl.exists() and ads_to_intl[0].addr_country != 'UA':
                del intl_catalogs['worldwide']

            # подсчет стоимостьи размещения объявлений в каждом каталоге
            for catalog in intl_catalogs:
                for ad in ads_to_intl:
                    intl_catalogs[catalog]['amount'] += user_recipient.get_paidplacement_price(ad, catalog)

            # подсчитываем итоговую стоимость выбранный каталогов(для purchase)
            for catalog in selected_catalogs:
                total_amount += intl_catalogs[catalog]['amount']

        # тарифы
        if 'plan' in request_get:
            plan = user_recipient.get_available_plans().get(id=request_get['plan'])

            active_plan = user_recipient.get_active_plan()
            unexpired_plans = user_recipient.get_unexpired_plans().order_by('-end')

            plan_action = get_plan_action(plan, active_plan)

            if plan_action:
                if plan_action == 'prolong':
                    purchase_time = unexpired_plans[0].end
                    discount = user_recipient.get_plan_discount(purchase_time)
                else:
                    discount = user_recipient.get_plan_discount()

                if plan_action == 'upgrade':
                    payback = active_plan.get_payback()
                else:
                    payback = 0

                plan_price = Plan.get_price(region.price_level, plan.ads_limit, discount)
                plan_price_with_payback = plan_price - payback
                total_amount += plan_price
            else:
                raise Exception('Cannot upgrade plan from #%d to #%d' % (active_plan.plan.id, plan.id))

        request.checkout_options = locals()

        return func(request, *args, **kwargs)
    return decorated_view


@login_required
@check_ban
@get_checkout_options
def checkout(request):
    return render(request, 'profile/checkout.jinja.html', request.checkout_options)

@login_required
@check_ban
@db_transaction.atomic
@get_checkout_options
def purchase(request):
    # дефолтный получатель услуги - текущий юзер, а в некоторых ситуациях - риелтор агентства при покупке услуг админом агентства
    user_recipient = request.checkout_options['user_recipient']
    balance = request.checkout_options['balance']
    total_amount = request.checkout_options['total_amount']
    total_amount_with_payback = total_amount - request.checkout_options['payback']
    services = []

    # ВИПы
    if 'vip' in request.GET:
        for ad in request.checkout_options['ads_to_vip']:
            services.append({'type': 'vip', 'ad': ad.pk, 'user_recipient': user_recipient.id})

    # Зарубежные каталоги
    if 'intl_catalog' in request.GET:
        ads_to_intl = request.checkout_options['ads_to_intl']
        for catalog in request.GET.getlist('intl_catalog'):
            for ad in ads_to_intl:
                services.append({'type': catalog, 'ad': ad.pk, 'user_recipient': user_recipient.id})

    # Планы
    if 'plan' in request.GET:
        services.append({'type': 'plan', 'id': request.checkout_options['plan'].id, 'user_recipient': user_recipient.id})

    order = Order.objects.create(user=request.user, services=json.dumps(services), amount=total_amount)
    if balance >= total_amount_with_payback:
        order.execute()
        if 'next' in request.GET:
            return redirect(request.GET['next'])
        else:
            if request.own_agency:
                return redirect(reverse('agency_admin:ads'))
            else:
                return redirect(reverse('profile_my_properties'))
    else:
        topup_params = {
            'amount': total_amount_with_payback - balance,
            'payment_system': request.POST.get('payment_system') or request.GET.get('payment_system') or settings.PAYMENT_SYSTEM_DEFAULT,
            'order': order.id,
        }
        redirect_url = reverse('profile_balance_topup') + '?' + urllib.urlencode(topup_params)
        return redirect(redirect_url)

@login_required
def notification_link_click(request):
    Notification.objects.filter(id=request.GET['notification']).update(link_clicks=F('link_clicks') + 1)
    return redirect(request.GET['url'])

