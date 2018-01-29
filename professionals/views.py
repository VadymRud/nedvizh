# coding: utf-8
from django.shortcuts import render, redirect
from django.utils.translation import ugettext_lazy as _
from django.http import Http404, QueryDict, HttpResponsePermanentRedirect, JsonResponse
from django.db.models import Prefetch, Q, Avg, Count, F
from django import forms
from django.core.urlresolvers import reverse

from ad.models import Ad, Region, DealType
from ad.choices import DEAL_TYPE_CHOICES
from agency.models import Agency, Realtor, city_region_filters, ViewsCount
from seo import meta_tags
from seo.models import TextBlock
from utils.paginator import HandyPaginator
from custom_user.models import User
from professionals.models import Review, Reply
from ad.phones import pprint_phones

import datetime
import collections


def get_public_agencies():
    # через m2m с distinct запрос более медленный
    return Agency.objects.filter(show_in_agencies=True, id__in=Realtor.objects.filter(is_active=True, user__ads_count__gt=0).values('agency'))


class ProfessionalForm(forms.Form):
    city = forms.IntegerField(label=_(u'Город'), label_suffix='', required=False, min_value=1, widget=forms.HiddenInput)
    deal_type = forms.ModelChoiceField(label=_(u'Тип сделки'), label_suffix='', queryset=DealType.objects.all(), required=False, empty_label=_(u'Выберите тип сделки'))
    search = forms.CharField(label=_(u'Имя риелтора, или название организации'), required=False)

    def clean_city(self):
        if self.cleaned_data['city']:
            try:
                return Region.objects.get(id=self.cleaned_data['city'], **city_region_filters)
            except Region.DoesNotExist:
                raise forms.ValidationError('Wrong city ID %d' % self.cleaned_data['city'])


def build_normalized_search_url(request, professional_type):
    query_dict = request.GET.copy()

    region = request.subdomain_region

    city = query_dict.get('city')
    if city:
        city_subdomain_region = Region.objects.filter(subdomain=True, id=city).first()
        if city_subdomain_region:
            query_dict.pop('city')
            region = city_subdomain_region

    kwargs = {'professional_type': professional_type} if professional_type else {}
    normalized_url = region.get_host_url('professionals:search', kwargs=kwargs, scheme=request.scheme)

    for key, value in query_dict.items():
        if not value:
            query_dict.pop(key)

    if query_dict:
        normalized_url += '?%s' % query_dict.urlencode()

    return normalized_url

def search(request, professional_type=None):
    normalized_url = build_normalized_search_url(request, professional_type)
    if normalized_url != request.build_absolute_uri():
        return HttpResponsePermanentRedirect(normalized_url)

    query_dict = request.GET.copy()
    if request.subdomain_region.kind == 'locality' and not request.GET.get('city'):
        query_dict['city'] = request.subdomain_region.id

    form = ProfessionalForm(query_dict)

    if form.is_valid():
        # .filter(...).filter(...) или exclude() приводят к дополнительным JOIN, поэтому фильтр общий
        # TODO возможно имеет смысл расписать get_public_agencies через фильтры

        search = form.cleaned_data['search']

        agency_q = Q(
            Q(agency__name__icontains=search) if search else Q(),
            agency__logo__gt='',
            is_admin=True,
        )

        realtor_q = Q(
            is_admin=False,
            user__in=User.objects.filter(
                (Q(first_name__icontains=search) | Q(last_name__icontains=search)) if search else Q(),
                image__gt='',
                ads_count__gt=0,
            ),
        )

        if professional_type == 'agency':
            type_q = agency_q
        elif professional_type == 'realtor':
            type_q = realtor_q
        else:
            type_q = agency_q | realtor_q

        deal_type = form.cleaned_data['deal_type']
        city = form.cleaned_data['city']

        realtors = Realtor.objects.filter(
            type_q,
            agency__in=get_public_agencies().filter(
                Q(deal_types=deal_type) if deal_type else Q(),
                Q(city=city) if city else Q(),
            )
        ).select_related('user').order_by('-user__last_action').prefetch_related(
            Prefetch('agency', queryset=Agency.objects.annotate(reviews_count=Count('reviews'), avg_rating=Avg('reviews__rating'))),
            'agency__city',
            'user__phones',
        )

    else:
        realtors = Realtor.objects.none()

    paginator = HandyPaginator(realtors, 16, request=request)

    title, description = meta_tags.get_professionals_search_metatags(request.subdomain_region, professional_type)
    seo_text_block = TextBlock.find_by_request(request, request.subdomain_region)

    return render(request, 'professionals/search.jinja.html', locals())


def agency_profile(request, agency_id):
    try:
        agency = get_public_agencies().get(id=agency_id)
    except Agency.DoesNotExist:
        raise Http404

    agency_ads = Ad.objects.filter(
        is_published=True,
        user__in=set(agency.users.filter(realtors__is_active=True).values_list('id', flat=True)) # todo проверить
    ).prefetch_related('photos', 'region').order_by('-vip_type')
    agency_ads_count = agency_ads.count()

    # выбор основных типов сделки объявлений
    deal_types = [(deal_type, dict(DEAL_TYPE_CHOICES)[deal_type]) for deal_type, cnt in collections.Counter(agency_ads.values_list('deal_type', flat=True)).most_common(4)]


    # фильтруем по типу сделки
    if deal_types:
        agency_ads = agency_ads.filter(deal_type=request.GET.get('deal_type', deal_types[0][0]))

    paginator = HandyPaginator(agency_ads, 4, request=request)

    realtor = agency.realtors.get(is_admin=True)

    reviews_stat = agency.reviews.aggregate(avg_rating=Avg('rating'), count=Count('id'))

    is_agency = True
    contacts_link = reverse('professionals:agency_contacts', args=[agency.id])

    # seo-корректировки за январь 2016 для раздела профессионалы
    title, description = meta_tags.get_professionals_agency_metatags(request.subdomain_region, agency)

    return render(request, 'professionals/profile.jinja.html', locals())


def realtor_profile(request, agency_id, user_id):
    try:
        agency = get_public_agencies().get(id=agency_id)
        realtor = agency.realtors.filter(is_active=True).get(user_id=user_id)
    except (Agency.DoesNotExist, Realtor.DoesNotExist):
        raise Http404

    agency_ads = Ad.objects.filter(
        is_published=True,
        user__in=set(agency.users.filter(realtors__is_active=True).values_list('id', flat=True)) # todo проверить
    )
    agency_ads_count = agency_ads.count()

    # выбор основных типов сделки объявлений
    deal_types = [(deal_type, dict(DEAL_TYPE_CHOICES)[deal_type]) for deal_type, cnt in collections.Counter(agency_ads.values_list('deal_type', flat=True)).most_common(4)]

    # фильтруем по типу сделки
    if deal_types:
        agency_ads = agency_ads.filter(deal_type=request.GET.get('deal_type', deal_types[0][0]))

    realtor_ads = realtor.user.ads.filter(is_published=True).prefetch_related('photos', 'region').order_by('-vip_type')
    paginator = HandyPaginator(realtor_ads, 4, request=request)

    is_agency = False
    contacts_link = reverse('professionals:realtor_contacts', args=[realtor.agency_id, realtor.user_id])

    # seo-корректировки за январь 2016 для раздела профессионалы
    title, description = meta_tags.get_professionals_realtor_metatags(request.subdomain_region, realtor)

    return render(request, 'professionals/profile.jinja.html', locals())


def agency_realtors(request, agency_id):
    try:
        agency = get_public_agencies().get(id=agency_id)
    except Agency.DoesNotExist:
        raise Http404

    realtors = agency.realtors.filter(is_active=True, is_admin=False).prefetch_related('user', 'agency', 'user__phones')
    paginator = HandyPaginator(realtors, 16, request=request)

    return render(request, 'professionals/agency_realtors.jinja.html', locals())

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ('title', 'rating', 'text')

    title = forms.CharField(label=_(u'Введите тему отзыва'))
    rating = forms.IntegerField(label=_(u'Понравилось ли вам работать с агентством?'), required=False)
    text = forms.CharField(label=_(u'Введите текст отзыва'), widget=forms.Textarea())

class ReplyForm(forms.ModelForm):
    class Meta:
        model = Reply
        fields = ('text',)

def agency_reviews(request, agency_id):
    try:
        agency = get_public_agencies().get(id=agency_id)
    except Agency.DoesNotExist:
        raise Http404

    if request.user.is_authenticated():
        request_user_is_agency_realtor = agency.realtors.filter(is_active=True, user=request.user).exists()

    review_form = ReviewForm()
    reply_form = ReplyForm()

    if request.method == 'POST':
        if request.user.is_anonymous():
            raise Exception('Anonymous user can`t post reviews or replies')

        if 'review' in request.POST:
            review_to_reply = agency.reviews.get(id=request.POST.get('review'))
            reply_form = ReplyForm(request.POST, instance=Reply(user=request.user, review=review_to_reply))

            if reply_form.is_valid():
                reply_form.save()
                return redirect(request.get_full_path())

        else:
            if request_user_is_agency_realtor:
                raise Exception('Realtors can`t post reviews on its agency')

            review_form = ReviewForm(request.POST, instance=Review(agency=agency, user=request.user))

            if review_form.is_valid():
                review_form.save()
                return redirect(request.path)

    reviews = agency.reviews.prefetch_related('user', 'replies', 'replies__user')
    paginator = HandyPaginator(reviews, 15, request=request)

    is_agency = True
    return render(request, 'professionals/agency_reviews.jinja.html', locals())

def agency_redirect(request, agency_id):
    try:
        agency = get_public_agencies().get(id=agency_id)
    except Agency.DoesNotExist:
        raise Http404
    return render(request, 'professionals/agency_redirect.jinja.html', locals())

def increment_viewscount(request, user):
    if request.method == 'POST' and request.is_customer:
        updated_rows = ViewsCount.objects.filter(user=user, date=datetime.date.today()).update(
            professionals_contacts_views=F('professionals_contacts_views') + 1
        )
        if not updated_rows:
            ViewsCount.objects.create(user=user, date=datetime.date.today(), professionals_contacts_views=1)

def agency_contacts(request, agency_id):
    agency = Agency.objects.get(id=agency_id)
    admin_user = agency.get_admin_user()

    from ad.views import log_request_if_its_bad
    log_request_if_its_bad(request)

    increment_viewscount(request, admin_user)
    numbers = admin_user.phones.values_list('number', flat=True)

    return JsonResponse({
        'phones': pprint_phones(numbers, delimiter=u'<br>')
    })

def realtor_contacts(request, agency_id, user_id):
    realtor = Realtor.objects.get(agency_id=agency_id, user_id=user_id, is_active=True, is_admin=False)

    from ad.views import log_request_if_its_bad
    log_request_if_its_bad(request)

    increment_viewscount(request, realtor.user)
    numbers = realtor.user.phones.values_list('number', flat=True)

    return JsonResponse({
        'phones': pprint_phones(numbers, delimiter=u'<br>')
    })

