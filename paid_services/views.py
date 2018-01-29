# coding: utf-8
from django import forms
from django.contrib import messages
from django.conf import settings
from django.core.urlresolvers import reverse, reverse_lazy
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _

from ad.models import Region
from ad.phones import PhoneField
from custom_user.models import User
from newhome.decorators import restrict_access_for_developer
from paid_services.models import VIP_PRICES, VIP_PRICE_RENT_DAILY, Plan, get_plan_end


import json
import datetime


@login_required
@restrict_access_for_developer
def index(request):
    title = _(u'Размещение объявлений')
    return render(request, 'paid_services/index.jinja.html', locals())

def vips(request):
    title = _(u'VIP объявление')
    provinces = Region.get_provinces()
    if request.user.is_authenticated and request.user.region:
        selected_province = request.user.region
    else:
        selected_province = Region.get_capital_province()
    vip_prices_json = json.dumps(VIP_PRICES)
    vip_price_rent_daily = VIP_PRICE_RENT_DAILY
    return render(request, 'paid_services/vips.jinja.html', locals())


def get_plan_action(plan, active_plan):
    if active_plan:
        if active_plan.plan == plan:
            return 'prolong'
        else:
            if plan.ads_limit > active_plan.ads_limit:
                return 'upgrade'
            else:
                return None
    else:
        return 'purchase'

@login_required
def plans(request):
    title = _(u'Тарифный план')

    user_recipient = request.user
    if 'realtor' in request.GET:
        user_recipient = user_recipient.get_own_agency().get_realtors().get(pk=request.GET['realtor']).user

    region_for_plan = request.user.region or Region.get_capital_province()

    if region_for_plan:
        active_plan = user_recipient.get_active_plan()

        price_level = region_for_plan.price_level

        query_dict = request.GET.copy()
        plans = {}

        for duration in [30]: # 180
            plans[duration] = user_recipient.get_available_plans()

            for plan in plans[duration]:
                action = get_plan_action(plan, active_plan)

                # используется при переходе со страницы активации объявления
                # когда у юзера лимит исчерпан и нужно апгрейдить тариф, чтобы он случайно не продлил его
                if action == 'prolong' and 'no_prolong' in request.GET:
                    action = None

                plan._detail = {}
                plan._detail['action'] = action
                plan._detail['expiration'] = get_plan_end(datetime.datetime.now())
                plan._detail['checkout_url'] = '%s?plan=%d' % (reverse('profile_checkout'), plan.id)

                if action == 'prolong':
                    purchase_time = user_recipient.get_unexpired_plans().order_by('-end').first().end
                else:
                    purchase_time = datetime.datetime.now()

                plan._detail['discount'] = user_recipient.get_plan_discount(purchase_time)
                if duration == 180:
                    plan._detail['discount'] = max(plan._detail['discount'], 0.4)
                    plan._detail['checkout_url'] += '&duration=180'

                plan._detail['full_price'] = Plan.get_price(price_level, plan.ads_limit) * duration/30
                plan._detail['final_price'] = Plan.get_price(price_level, plan.ads_limit, plan._detail['discount']) * duration/30

                if action == 'upgrade':
                    plan._detail['upgrade_price'] = plan._detail['final_price'] - active_plan.get_payback()

    return render(request, 'paid_services/plans.jinja.html', locals())

def international(request):
    title = _(u'Зарубежные каталоги')
    return render(request, 'paid_services/international.jinja.html', locals())

def tour360(request):
    title = _(u'Виртуальные туры 360')

    prices = {'apartment': 1820, 'house': 3340, 'commerical': 10150}

    class TourRequestForm(forms.Form):
        name = forms.CharField(label=_(u'Имя'))
        city = forms.CharField(label=_(u'Город'))
        company = forms.CharField(label=_(u'Организация'), required=False)
        email = forms.EmailField(label=_(u'E-mail'))
        phone = PhoneField(label=u'Телефон', required=False)
        property_type = forms.CharField(label=u'Тип недвижимости', required=False, widget=forms.HiddenInput())

    tourrequest_form = TourRequestForm(data=request.POST if request.method == 'POST' else None)
    if tourrequest_form.is_valid():
        data = tourrequest_form.cleaned_data

        sms_data = [value for key, value in data.items() if value and key not in ['property_type']]
        customer_info = ' '.join(sms_data)

        # заказ с последующей оплатой
        if data['property_type']:
            price = prices[data['property_type']]

            # отправка уведомления Дарию
            user = User.objects.get(email='bednarchikd@gmail.com', is_staff=True)
            user.send_email(u'Заявка на вирт. тур / предоплата', u'Возможна предоплата %d грн!\n\nДанные клиента: %s' % (price, customer_info))
            user.send_notification(u'Заявка на вирт. тур (предоплата %d?): %s' % (price, customer_info))

            return redirect(reverse('profile_balance_topup') + '?amount=%d' % price)
        else:
            # отправка уведомления Дарию
            user = User.objects.get(email='bednarchikd@gmail.com', is_staff=True)
            user.send_email(u'Заявка на вирт. тур', u'Данные клиента: %s' % customer_info)
            user.send_notification(u'Заявка на вирт. тур: %s' % customer_info)

            messages.info(request, _(u'<div class="text-36">Спасибо!</div>Мы свяжемся с Вами в кратчайшее время'), extra_tags='modal-dialog-w500 modal-success-small')
            return redirect('.')

    return render(request, 'paid_services/tour360.jinja.html', locals())


class RequestForm(forms.Form):
    name = forms.CharField(label=_(u'Имя'))
    phone = PhoneField(label=u'Телефон', required=False)
    email = forms.EmailField(label=_(u'E-mail'))
    city = forms.CharField(label=_(u'Город'))


def analysis(request):
    title = _(u'Экспертная проверка жилья')

    prices_by_region_slug = {
        'kiev': [2000, 2900, 5900, 14900],
        'dnepropetrovsk': [1600, 2320, 4720, 11000],
        'odessa': [1600, 2320, 4720, 11000],
        'harkov': [1600, 2320, 4720, 11000],
        'lvov': [1600, 2320, 4720, 11000],
    }
    if request.subdomain_region.slug in prices_by_region_slug:
        prices = prices_by_region_slug[request.subdomain_region.slug]
    else:
        prices = [1400, 2030, 4130, 10430]

    analysisrequest_form = RequestForm(data=request.POST if request.method == 'POST' else None)
    if analysisrequest_form.is_valid():
        sms_data = [value for key, value in analysisrequest_form.cleaned_data.items()]
        customer_info = ' '.join(sms_data)

        # отправка уведомления Дарию
        user = User.objects.filter(email='olga.k@mesto.ua', is_staff=True).first() or User.objects.get(id=1)
        user.send_email(u'Заявка на анализ новостроя', u'Данные клиента: %s' % customer_info)
        user.send_notification(u'Заявка на анализ новостроя: %s' % customer_info)

        messages.info(request, _(u'<div class="text-36">Спасибо!</div>Мы свяжемся с Вами в кратчайшее время'), extra_tags='modal-dialog-w500 modal-success-small')
        return redirect('.')

    if 'show_popup' in request.GET:
        from django.template.loader import render_to_string
        content = render_to_string('paid_services/analysis_popup.jinja.html')
        messages.info(request, content, extra_tags='modal-newhome-analysis')

    return render(request, 'paid_services/analysis.jinja.html', locals())

PROPERTY_TYPE_CHOICES = list(enumerate([
    u'Квартира', u'Дом, коттедж', u'Комната', u'Гараж, машино-место', u'Коммерческий объект до 100 м.кв',
    u'Коммерческий объект до 100-200 м.кв', u'Коммерческий объект до 200-400 м.кв', u'Коммерческий объект от 400 м.кв',
    u'Земельный участок до 25 соток', u'Земельный участок 25-50 соток', u'Земельный участок от 50 соток',
]))

class OcenkaRequestForm(RequestForm):
    property_type = forms.ChoiceField(label=_(u'Тип недвижимости'), choices=PROPERTY_TYPE_CHOICES)
    city = forms.CharField(label=_(u'Город'), widget=forms.TextInput(attrs={'class': 'form-control city-chooser js_city_search international', 'autocomplete':'off', 'data-action':reverse_lazy('cities_autocomplete')}))

    field_order = ['name', 'phone', 'property_type', 'email', 'city']


def ocenka_nedvizh(request):
    title = _(u'Оценка недвижимости')

    request_form = OcenkaRequestForm(data=request.POST if request.method == 'POST' else None)
    if request_form.is_valid():
        sms_data = [value for key, value in request_form.cleaned_data.items() if key != 'property_type']

        property_type = int(request_form.cleaned_data['property_type'])
        sms_data.append(dict(request_form.fields['property_type'].choices)[property_type])

        customer_info = u' ; '.join(filter(None, sms_data))

        # отправка уведомления Дарию
        user = User.objects.filter(email='olga.k@mesto.ua', is_staff=True).first() or User.objects.get(id=1)
        user.send_email(u'Заявка на оценку недвижимости', u'Данные клиента:\n %s' % customer_info.replace(';', '\n'))
        user.send_notification(u'Заявка на оценку недвижимости: %s' % customer_info)

        messages.info(request, _(u'<div class="text-36">Спасибо!</div>Мы свяжемся с Вами в кратчайшее время'), extra_tags='modal-dialog-w500 modal-success-small')
        return redirect('.')

    return render(request, 'paid_services/ocenka-nedvizh.jinja.html', locals())


class NotaryRequestForm(RequestForm):
    property_type = forms.ChoiceField(label=_(u'Тип недвижимости'), choices=PROPERTY_TYPE_CHOICES)
    city = forms.CharField(label=_(u'Город'), widget=forms.TextInput(attrs={'class': 'form-control city-chooser js_city_search international', 'autocomplete':'off', 'data-action':reverse_lazy('cities_autocomplete')}))

    field_order = ['name', 'phone', 'property_type',  'city', 'email',]

def notary(request):
    title = _(u'Услуги нотариуса')

    request_form = NotaryRequestForm(data=request.POST if request.method == 'POST' else None)
    if request_form.is_valid():
        sms_data = [value for key, value in request_form.cleaned_data.items() if key != 'property_type']

        property_type = int(request_form.cleaned_data['property_type'])
        sms_data.append(dict(request_form.fields['property_type'].choices)[property_type])

        customer_info = u' ; '.join(filter(None, sms_data))

        # отправка уведомления Дарию
        user = User.objects.filter(email='olga.k@mesto.ua', is_staff=True).first() or User.objects.get(id=1)
        user.send_email(u'Заявка на услуги нотариуса', u'Данные клиента:\n %s' % customer_info.replace(';', '\n'))
        user.send_notification(u'Заявка на услуги нотариуса: %s' % customer_info)

        messages.info(request, _(u'<div class="text-36">Спасибо!</div>Мы свяжемся с Вами в кратчайшее время'), extra_tags='modal-dialog-w500 modal-success-small')
        return redirect('.')

    return render(request, 'paid_services/notary.jinja.html', locals())


def legal_services(request):
    title = _(u'Юридические услуги')

    return render(request, 'paid_services/legal_services.jinja.html', locals())


ROOM_TYPE_CHOICES = (
    ('Гостиная', _(u'Гостиная')),
    ('Спальня', _(u'Спальня')),
    ('Кухня', _(u'Кухня')),
    ('Ванная', _(u'Ванная')),
    ('Коридор', _(u'Коридор')),
    ('Детская комната', _(u'Детская комната')),
    ('Игровая комната', _(u'Игровая комната')),
    ('Столовая', _(u'Столовая')),
    ('Подсобка', _(u'Подсобка')),
    ('Гараж', _(u'Гараж')),
    ('Офис', _(u'Офис')),
    ('Подвал', _(u'Подвал')),
    ('Туалет', _(u'Туалет')),
    ('Внутренний двор', _(u'Внутренний двор')),
)

class Interior3dRequestForm(RequestForm):
    project_name = forms.CharField(label=_(u'Название проекта'), widget=forms.TextInput(attrs={'placeholder': _(u'Ваш текст')}))
    property_type = forms.CharField(label=_(u'Тип недвижимости'), required=False)
    photo = forms.ImageField()
    room_type = forms.ChoiceField(label=_(u'Тип комнаты'), choices=ROOM_TYPE_CHOICES, required=False)
    description = forms.CharField(label=_(u'Особые пожелания'), required=False,
                                  widget=forms.Textarea(attrs={'rows': 10, 'placeholder':_(u'Особые пожелания')}))
    style = forms.CharField(label=_(u'Стиль'))
    phone = forms.CharField(label=_(u'Телефон'))

    class Meta:
        fieldsets = (
            (None, {'fields': ('name', 'city', 'email')}),
            # (None, {'fields': ('photo', 'project_name', 'property_type', 'room_type')}),
        )

def interior3d(request):
    title = _(u'3D интерьер')
    price = 2800

    if request.method == 'POST':
        request_form = Interior3dRequestForm(request.POST, request.FILES)
        
        if request_form.is_valid():
            request_info = ''
            for key, field in request_form.fields.items():
                value = request_form.cleaned_data[key]
                if key != 'photo' and value:
                    request_info += ' %s: %s\n' % (request_form.fields[key].label, value)


            # отправка уведомления ответственному за услугу пользователю
            responsible_user = User.objects.filter(email='sergey@mesto.ua').first() or User.objects.get(id=1)
            photo = request_form.cleaned_data['photo']
            responsible_user.send_email(
                u'Заявка на 3D интерьер', u'Поступила заявка. на 3D интерьер. Данные заказа:\n %s' % request_info.replace(';', '\n'),
                attach=[photo._name, photo.file.getvalue(), photo.content_type]
            )
            # поиск или создание пользователя по email
            email = request_form.cleaned_data['email']
            order_user = User.objects.filter(email=email).first()
            if not order_user:
                order_user = User.fast_register(email)
                new_user = True

            services = [{'type':'interior3d', 'name':u'услуги 3D дизайна', 'user_recipient': order_user.id, 'request_info': request_info}]

            if 'test' in request.GET:
                price = 1
                services[0]['test'] = True

            from paid_services.models import Order
            order = Order.objects.create(user=order_user, services=json.dumps(services), amount=price)
            form = order.get_liqpay_payment_form()

            # используется для возврата пользователя на сайт после платежной системы
            request.session['payment_referrer'] = request.get_full_path()

            redirect_template = 'profile/balance/form_redirect.jinja.html'
            return render(request, redirect_template, locals())
    else:
        request_form = Interior3dRequestForm()

    return render(request, 'paid_services/interior3d.jinja.html', locals())