# coding: utf-8
import collections
import datetime
import json
import random
import string
import uuid
import urllib
from django.conf import settings
from django.contrib import messages

from django.shortcuts import render, get_object_or_404, redirect
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from django.utils import translation
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.db.models import Sum, Avg, Q
from django.core.urlresolvers import reverse
from django.http import JsonResponse, HttpResponseRedirect, Http404

from ad.models import Ad, ViewsCount, Phone, Region
from custom_user.models import User, UserPhone
from profile.models import Message, Stat, StatGrouped
from profile.views import get_views_for_ads
from paid_services.models import VipPlacement, Transaction, Plan, UserPlan
from agency.models import Agency, Realtor, Note, LEAD_LABELS, Lead, LeadHistoryEvent, city_region_filters
from agency.forms import AgencyForm, AddRealtorForm, RieltorFilterForm, StatFilterForm, RieltorStatFilterForm, NoteForm, \
    TransactionFilterForm
from utils.decorators import update_ads_status
from utils.paginator import HandyPaginator, AdPaginator


@login_required
def agency_form(request):
    title = _(u'Редактирование агентства')
    agency = request.own_agency
    if not agency:
        raise Http404

    if request.method == 'POST':
        form = AgencyForm(request.POST, request.FILES, instance=agency)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('profile_settings_agency'))
    else:
        form = AgencyForm(instance=agency, initial={'city_typeahead': getattr(agency.city, 'name', '')})

    return render(request, 'agency/agency_form.jinja.html', locals())


@login_required
def realtors(request):
    title = _(u'Риелторы агентства')
    agency = request.own_agency
    if not agency:
        raise Http404

    # клик по кнопке "Показать статистику"
    if 'show-stats' in request.GET:
        return HttpResponseRedirect(reverse('agency_admin:stats') + '?%s'
                                    % urllib.urlencode({'realtor':request.GET.getlist('realtor')}, True))

    if request.method == 'POST':
        add_form = AddRealtorForm(request.POST, request.FILES, agency=agency)
        if add_form.is_valid():
            with db_transaction.atomic():
                agency_realtor = Realtor.objects.filter(is_admin=True, user=request.user).get()

                try:
                    user = User.objects.get(email__iexact=add_form.cleaned_data['email'])
                except User.DoesNotExist:
                    user = add_form.save(commit=False)
                    user.username = User.make_unique_username(add_form.cleaned_data['email'])
                    password = ''.join(random.choice(string.digits) for i in xrange(8))
                    user.set_password(password)
                    user.save()
                    phone, created = Phone.objects.get_or_create(number=add_form.cleaned_data['phone'])
                    UserPhone(user=user, phone=phone, order=1).save()
                else:
                    password = None

                new_realtor = Realtor(agency=agency_realtor.agency, user=user, is_active=False, confirmation_key=uuid.uuid4().hex)
                new_realtor.save()
                new_realtor.send_mail(password)
                new_realtor.send_message()

            add_form = AddRealtorForm(agency=agency)
            messages.info(request, _(u'Рилетор добавлен.<br/>Риелтору отправлено личное сообщений с ссылкой для подтверждения'), extra_tags='modal-dialog-w400 modal-success')
            return HttpResponseRedirect(reverse('agency_admin:realtors'))
        else:
            add_form.set_required()

    else:
        add_form = AddRealtorForm(agency=agency)
        add_form.set_required()

    # удаляем неугодных
    if 'delete' in request.GET:
        agency.realtors.filter(pk=request.GET['delete']).delete()

    # риелторы агентства
    realtors = agency.realtors.prefetch_related('user__phones').order_by('-is_admin', 'pk')

    form = RieltorFilterForm(request.GET)
    if form.is_valid():
        if form.cleaned_data['search']:
            q = form.cleaned_data['search']
            search_filter = Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) | Q(user__email__icontains=q)
            realtors = realtors.filter(search_filter)

    paginator = HandyPaginator(realtors, 5, request=request)

    # статистика просмотров и входов
    for i, realtor in enumerate(paginator.current_page.object_list):
        try:
            paginator.current_page.object_list[i].stats = Stat.objects.filter(user=realtor.user).order_by().values('user')\
                .annotate(ad_views=Sum('ad_views'), ad_contacts_views=Sum('ad_contacts_views'), entrances=Sum('entrances'))[0]
        except IndexError:
            paginator.current_page.object_list[i].stats = None

    return render(request, 'agency/realtors.jinja.html', locals())


@login_required
@update_ads_status
def realtor_detail(request, realtor_id):
    title = _(u'Риелторы агентства')
    agency = request.own_agency
    agency_realtors = agency.get_realtors().exclude(user=request.user).select_related('user').prefetch_related('notes')
    realtor = agency.realtors.filter(pk=realtor_id, is_active=True).first()

    if not agency or not realtor:
        raise Http404

    # обработка заметок
    note = Note.objects.filter(user=request.user, realtor=realtor).first() or Note(user=request.user, realtor=realtor)
    if 'text' in request.POST:
        note_form = NoteForm(request.POST, instance=note)
        if note_form.is_valid():
            note_form.save()
    else:
        note_form = NoteForm(instance=note)

    # общая статистика по риелтору
    session_key = 'realtor_stats_period_length'
    period_length = request.session.get(session_key, 0)
    stats_form = RieltorStatFilterForm(request.POST if 'period' in request.POST else {'period': period_length})
    if stats_form.is_valid():
        period_length = int(stats_form.cleaned_data['period'])
        request.session[session_key] = period_length

    # это временное решение, позже все данные будут храниться в модели Stat
    period_filter = {'time': Q(), 'date': Q()}
    if period_length:
        period_filter = {
            'time': Q(time__gte=datetime.datetime.now() - datetime.timedelta(days=period_length)),
            'date': Q(date__gte=datetime.datetime.now() - datetime.timedelta(days=period_length)),
        }

    try:
        stats = Stat.objects.filter(user=realtor.user).filter(period_filter['date']).values('user')\
                    .annotate(ad_views=Sum('ad_views'), contact_views=Sum('ad_contacts_views'), logins=Sum('entrances'))[0]
    except IndexError:
        stats = collections.Counter()

    # TODO: можно тоже добавить в статистику данные о количестве сообщений
    stats['messages'] = Message.objects.filter(to_user=realtor.user).filter(period_filter['time']).count()

    # список объявлений риелтора
    ads = Ad.objects.filter(user=realtor.user).exclude(status=211)
    paginator = AdPaginator(ads, 10, request=request)

    # данные просмотров и активных VIP по объявлениям
    views_by_ad = get_views_for_ads(paginator.current_page.object_list)

    vips = {}
    for vip in VipPlacement.objects.filter(is_active=True, basead__ad__user=request.user):
        vips[vip.basead_id] = vip

    return render(request, 'agency/realtor_detail.jinja.html', locals())


@login_required
@db_transaction.atomic
def realtor_topup(request, realtor_id):
    agency = request.own_agency
    realtor = agency.realtors.filter(pk=realtor_id).first()

    if not agency or not realtor:
        raise Http404

    import decimal
    amount = request.GET.get('amount') or request.POST.get('amount')
    amount = decimal.Decimal(amount.replace(',', '.'))
    balance = request.user.get_balance(force=True)

    if balance >= amount:
        Transaction.move_money(request.user, realtor.user, amount, u'через кабинет')
        return redirect(reverse('agency_admin:realtor_detail', args=[realtor_id]))
    else:
        from django.core.cache import cache
        deficit = abs(balance - amount)
        cache.set('interrupted_purchase_url_for_user%s' % request.user.id, request.get_full_path(), 60*10)
        return redirect(reverse('profile_balance_topup') + ('?amount=%s' % deficit))


@login_required
def ads(request):
    if not request.own_agency:
        raise Http404

    from profile.views import my_properties

    agency_realtors = request.own_agency.get_realtors().exclude(user=request.user).select_related('user').prefetch_related('notes')
    return my_properties(request, agency_realtors)


@login_required
def crm(request):
    title = _(u'CRM')
    agency = request.own_agency
    if not request.user.get_realtor() and not request.is_developer_cabinet_enabled:
        return render(request, 'agency/crm_person_redirect.jinja.html', locals())

    from agency.models import LEAD_LABELS

    lead_labels_json = json.dumps([{'value': label, 'text': unicode(label_display)} for label, label_display in LEAD_LABELS])

    # Новые лиды
    has_hew_leads = LeadHistoryEvent.objects.filter(
        lead__user=request.user, is_readed=False, object_id__isnull=False).exists()

    return render(request, 'agency/crm.jinja.html', locals())


@login_required
def stats(request):
    title = _(u'Статистика по риелторам')
    agency = request.own_agency
    if not agency:
        raise Http404

    agency_realtors = agency.realtors.filter(is_active=True).prefetch_related('user__phones', 'notes').order_by('pk')
    if agency_realtors.count() > 1:
        selected_realtors = agency_realtors.filter(pk__in=[id
                                                           for id in request.GET.get('realtors', u'').split('-')
                                                           if id.isnumeric()])
    else:
        selected_realtors = agency_realtors

    period_length = int(request.GET.get('period', 7))
    stat_type = request.GET.get('stat_type', 'ads')
    initial = {'period': period_length, 'stat_type': stat_type}
    form = StatFilterForm(initial)

    stats_interval = 'days'
    if period_length > 30:
        stats_interval = 'weeks'
    elif period_length == 0:
        period_length = 360
        stats_interval = 'months'

    period_end = datetime.datetime.now()
    period_start = period_end - datetime.timedelta(days=period_length)

    # для готового отчета период начинаем с первого дня месяца
    if period_length == 360:
        period_start = period_start.replace(day=1)

    # для остальных отчетов, кроме недельного, сдвигаем первый день на понедельник
    elif period_length != 7:
        period_start = period_start - datetime.timedelta(days=period_start.weekday())

    period_range = [period_start, period_end]

    import qsstats

    series = []
    labels = None
    colors = ['#ffb400', '#007df2', '#8bbc21', '#492970', '#0d233a', '#f28f43', '#77a1e5', '#c42525', '#a6c96a'] * 3

    for realtor in selected_realtors:
        realtor.color = colors.pop(0)

        if stat_type == 'ad_views':
            # qss = qsstats.QuerySetStats(ViewsCount.objects.filter(basead__ad__user=realtor.user), 'date', aggregate=Sum('detail_views'))
            qss = qsstats.QuerySetStats(Stat.objects.filter(user=realtor.user), 'date', aggregate=Sum('ad_views'))
        elif stat_type == 'contact_views':
            # qss = qsstats.QuerySetStats(ViewsCount.objects.filter(basead__ad__user=realtor.user), 'date', aggregate=Sum('contacts_views'))
            qss = qsstats.QuerySetStats(Stat.objects.filter(user=realtor.user), 'date', aggregate=Sum('ad_contacts_views'))
        elif stat_type == 'inbox':
            qss = qsstats.QuerySetStats(Message.objects.filter(to_user=realtor.user), 'time')
        elif stat_type == 'login':
            qss = qsstats.QuerySetStats(Stat.objects.filter(user=realtor.user), 'date', aggregate=Sum('entrances'))
        else: # ads
            # qss = qsstats.QuerySetStats(Ad.objects.filter(user=realtor.user), 'created')
            qss = qsstats.QuerySetStats(Stat.objects.filter(user=realtor.user), 'date', aggregate=Avg('active_properties'))

        time_series = qss.time_series(period_start, period_end, interval=stats_interval)
        series.append({'name': str(realtor.user), 'color': realtor.color, 'data': [int(x[1]) for x in time_series]})
        if not labels:
            labels = [x[0].strftime("%d.%m.%y") for x in time_series]

    return render(request, 'agency/stats.jinja.html', locals())


def add_realtor_user_exists(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if email:
            return JsonResponse(User.objects.filter(email=email).exists(), safe=False)
        else:
            raise Exception('empty email')
    else:
        raise Exception('Why not POST?')


def add_realtor_confirm(request, key):
    try:
        realtor = Realtor.objects.get(confirmation_key=key)
    except Realtor.DoesNotExist:
        raise Http404
    else:
        realtor.is_active = True
        realtor.save()

        # удаляем старые агентства юзера
        Agency.objects.filter(realtors__user=realtor.user).exclude(realtors=realtor).delete()

        messages.info(request, _(u'Вы присоединились к агентству "%s"' % realtor.agency.name))
        return HttpResponseRedirect(reverse('profile_index'))


def city_typeahead(request):
    translation.activate(request.LANGUAGE_CODE)
    cities = list(Region.objects.filter(name__icontains=request.GET.get('q'), **city_region_filters).order_by('name').values('id', 'name'))
    return JsonResponse(cities, safe=False)

