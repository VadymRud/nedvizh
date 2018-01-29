# coding: utf-8
import datetime
import math
import collections
import json
import os

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

from ad.models import Ad, Region
from custom_user.models import User
from staticpages.models import FAQArticle


def subscription_old(request):
    base_prices = (
        (_(u'1 объявление'), 25),
        (_(u'до 5 объявлений'), 62.5),
        (_(u'до 10 объявлений'), 125),
        (_(u'до 20 объявлений'), 250),
        (_(u'до 30 объявлений'), 375),
        (_(u'до 40 объявлений'), 500),
    )
    diff_month = math.ceil((datetime.date(2016, 10, 1) - datetime.date.today()).days / 30.0)
    diff_month = min(max(diff_month, 0), 6)
    months_discount = 1 - diff_month / 10.0

    zone_coefficient = 1
    if 'city' in request.GET:
        region = Region.objects.filter(name__icontains=request.GET['city'], kind__in=['locality', 'village']).first()
        if region:
            province = region.get_parents(kind='province')[0]
            if province.id in [22, 43, 73, 90, 9, 98]:
                zone_coefficient = 1
            elif province.id in [29, 51, 55, 60, 19, 122, 11994, 173, 62, 12, 233]:
                zone_coefficient = 0.75
            else:
                zone_coefficient = 0.5

    # итоговые цены
    prices = [(price[0], price[1], price[1] * zone_coefficient * months_discount) for price in base_prices]

    return render(request, 'promo/index.jinja.html', locals())

def subscription(request):
    if request.user.is_authenticated():
        user_province = request.user.region
    else:
        user_province = Region.get_capital_province()

    provinces = Region.get_provinces()
    for province in provinces:
        # Волынская, Закарпатская, Кировоградская, Полтавская, Ровенская, Сумская, Тернопольская, Черкасская, Донецкая, Крым, Луганская
        if province.id in [270, 189, 2, 92, 283, 240, 631, 15, 43, 11994, 19]:
            province.zone = 'low'
        # Винницкая, Житомирская, Запорожская, Ивано-Франковская, Львовская, Николаевская, Херсонская, Хмельницкая, Черниговская, Черновицкая
        elif province.id in [29, 51, 55, 60, 90, 122, 173, 62, 12, 233]:
            province.zone = 'med'
        else:
            province.zone = 'high'

    base_price = 25 * 1.2 # базовая цена за размещение одного объявления 25 грн без учета НДС
    discount = 67 # скидка при покупке в текущем месяце

    prices_by_zone = collections.defaultdict(list)
    for zone, zone_coefficient in {'low':0.5, 'med':0.75, 'high':1}.items():
        price_for_one_ad = int(math.ceil(base_price * zone_coefficient))

        for ads_count in [1, 5, 10, 20, 30, 40]:
            if ads_count == 1:
                label = u'1 объявление'
                price = price_for_one_ad
            else:
                label = u'до %s объявлений' % ads_count
                price = price_for_one_ad /  2.0 * ads_count

            prices_by_zone[zone].append(
                [
                    label,
                    int(math.ceil(price)),
                    int(math.ceil(math.ceil(price) * (100 - discount) / 100))
                ]
            )

    faq_articles = {}
    for category_id in [2,3,9,10]:
        faq_articles[category_id] = FAQArticle.objects.filter(category=category_id, is_published=True)

    return render(request, 'promo/index2.jinja.html', locals())


@csrf_exempt
def training_with_topal(request):
    from paid_services.models import Transaction
    free_slots = 30 - Transaction.objects.filter(type=62, amount__lt=-10).count()

    presales = datetime.date.today() < datetime.date(2017,10,1)
    if presales:
        price = 1500
    else:
        price = 1800

    if request.user.is_authenticated():
        # 10% скидка для АСНУ
        if request.user.is_asnu_member():
            price = int(price * 0.9)

        if request.user.id in [156501, 38560, 33838, 172758, 54178, 129284, 148798, 9655, 77247]:
            price = 1350

        if request.user.id == 171065:
            price = 1000

        if request.user.is_staff and 'test' in request.GET:
            price = 1

    class TrainingForm(forms.Form):
        name = forms.CharField(label=_(u'Имя'))
        agency = forms.CharField(label=_(u'Агентство'))
        tel = forms.CharField(label=_(u'Телефон'))
        email = forms.EmailField(label=_(u'E-mail'))
        agency = forms.CharField(label=_(u'Агентство'), required=False)
        position = forms.CharField(label=_(u'Должность'), required=False)

    training_form = TrainingForm(data=request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        if training_form.is_valid():
            sms_data = [value for key, value in training_form.cleaned_data.items()]
            customer_info = ' / '.join(sms_data)
            if "r" in request.GET:
                customer_info += (" " + request.GET["r"])

            responsible_user = User.objects.get(email='d.yarik@gmail.com', is_staff=True)

            # отправка уведомления пользователю ответственному за сбор заявок
            if 'test' not in request.GET:
                responsible_user.send_email(u'Заявка на участие в интенсиве', u'Участник подал заявку: %s' % customer_info)
                responsible_user.send_notification(u'Заявка на участие на интенсив: %s' % customer_info)

    return render(request, 'promo/training-with-topal.jinja.html', locals())

@csrf_exempt
def training_kharkiv(request):
    from paid_services.models import Transaction

    price = 450
    if request.user.is_authenticated():
        if request.user.is_staff and 'test' in request.GET:
            price = 1

    class TrainingForm(forms.Form):
        name = forms.CharField(label=_(u'Имя'))
        second_name = forms.CharField(label=_(u'Имя'))
        agency = forms.CharField(label=_(u'Агентство'))
        tel = forms.CharField(label=_(u'Телефон'))
        email = forms.EmailField(label=_(u'E-mail'))
        asnu_number = forms.CharField(label=_(u'номер АСНУ'), required=False)

    training_form = TrainingForm(data=request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        if not training_form.is_valid():
            return JsonResponse({'error':training_form.errors})
        else:
            sms_data = [value for key, value in training_form.cleaned_data.items()]
            customer_info = ' / '.join(sms_data)
            if "r" in request.GET:
                customer_info += (" " + request.GET["r"])

            responsible_user = User.objects.get(email='d.yarik@gmail.com', is_staff=True)

            # отправка уведомления пользователю ответственному за сбор заявок
            if 'test' not in request.GET:
                responsible_user.send_email(u'Заказ билета', u'Участник подал заявку: %s' % customer_info)
                responsible_user.send_notification(u'Заказ билета: %s' % customer_info)


            # 22% скидка для АСНУ
            from django.core.cache import cache
            if training_form.cleaned_data['asnu_number'].replace('-', '').replace(' ', '') in cache.get('valid_asnu_numbers', []):
                price = 350

            from paid_services.models import Order
            order_user  = request.user if request.user.is_authenticated() else responsible_user
            services = [{'type':'training', 'user_recipient': order_user.id, 'participant': customer_info,
                         'form_data': training_form.cleaned_data}]
            if 'test' in request.GET:
                services[0]['test'] = True
            order = Order.objects.create(user=order_user, services=json.dumps(services), amount=price)
            form = order.get_liqpay_payment_form(description=_(u'Оплата участия в семинаре Mesto.ua'))

            # используется для возврата пользователя на сайт после платежной системы
            request.session['payment_referrer'] = request.get_full_path()

            redirect_template = 'profile/balance/form_redirect.jinja.html'
            return render(request, redirect_template, locals())

    return render(request, 'promo/training-kharkiv.jinja.html', locals())