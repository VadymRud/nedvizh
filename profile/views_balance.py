# coding: utf-8
from django import forms
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db import transaction as db_transaction
from django.db.models import Sum
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.http import HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import ugettext_lazy as _
from lxml import html

from paid_services.models import Transaction, Order, InsufficientFundsError
from custom_user.models import User
from utils import pelipay
from utils.paginator import HandyPaginator

import datetime
import hashlib
import urllib
import base64
import random
import json

PERIOD_CHOICES = (
    (7, _(u'Неделя')),
    (30, _(u'Месяц')),
    (90, _(u'3 месяца')),
    (0, _(u'За всё время')),
)
TRANSACTION_TYPE_CHOICES = (
    ('', _(u'Все операции')),
    ('in', _(u'Пополнения')),
    ('out', _(u'Расходы')),
)

class TransactionFilterForm(forms.Form):
    period = forms.ChoiceField(label=u'Временной отрезок', choices=PERIOD_CHOICES)
    type = forms.ChoiceField(label=u'Тип операции', choices=TRANSACTION_TYPE_CHOICES, required=False)


ORDER_STATUS_CHOICES = (
    ('', 'Все счета'),
    ('unpaid', 'Неоплаченые'),
    ('paid', 'Оплаченные'),
)

class OrderFilterForm(forms.Form):
    period = forms.ChoiceField(label=u'Временной отрезок', choices=PERIOD_CHOICES)
    type = forms.ChoiceField(label=u'Статус счета', choices=ORDER_STATUS_CHOICES, required=False)


@db_transaction.atomic
@login_required
def orders(request):
    title = _(u'Счет')

    if 'period' in request.GET:
        form = OrderFilterForm(request.GET)
    else:
        form = OrderFilterForm(initial={'period': 0})

    orders = request.user.orders.order_by('-time')

    if form.is_valid():
        if int(form.cleaned_data['period']):
            time_start = datetime.datetime.now() - datetime.timedelta(days=int(form.cleaned_data['period']))
            orders = orders.filter(time__gt=time_start)

        if form.cleaned_data['type'] == 'paid':
            orders = orders.filter(is_paid=True)
        elif form.cleaned_data['type'] == 'unpaid':
            orders = orders.filter(is_paid=False)

    paginator = HandyPaginator(orders, 20, request=request)

    if 'pay_for_order' in request.GET:
        balance = request.user.get_balance(force=True)
        order = Order.objects.get(pk=request.GET['pay_for_order'], user=request.user, time__gt=datetime.datetime.now() - datetime.timedelta(days=3))
        if balance >= order.amount:
            order.execute()
            if 'next' in request.GET:
                return redirect(request.GET['next'])
            else:
                if request.own_agency:
                    return redirect(reverse('agency_admin:ads'))
                else:
                    return redirect(reverse('profile_my_properties'))

    return render(request, 'profile/balance/orders.jinja.html', locals())


@login_required
def balance(request):
    title = _(u'Баланс')

    # realtor = request.user.get_realtor_admin()
    transactions = request.user.transactions.all()

    # обновление комментариев к транзакциям
    if request.POST.get('name') == 'note':
        Transaction.objects.filter(pk=request.POST['pk'], user=request.user).update(note=request.POST['value'])

    if 'period' in request.GET:
        form = TransactionFilterForm(request.GET)
    else:
        form = TransactionFilterForm(initial={'period': 0})

    if form.is_valid():

        if int(form.cleaned_data['period']):
            time_start = datetime.datetime.now() - datetime.timedelta(days=int(form.cleaned_data['period']))
            transactions = transactions.filter(time__gt=time_start)

        if form.cleaned_data['type']:
            qs_filter = {'amount__gte': 0} if form.cleaned_data['type'] == 'in' else {'amount__lt': 0}
            transactions = transactions.filter(**qs_filter)

    paginator = HandyPaginator(transactions, 20, request=request)

    # для подсчета остатка после каждой транзакции
    if paginator.current_page.object_list:
        first_transaction_on_page = paginator.current_page.object_list[0]
        balance_on_period_start = request.user.transactions.filter(
            time__lte=first_transaction_on_page.time).aggregate(total=Sum('amount'))['total'] or 0

        rest_of_money = balance_on_period_start
        for transaction in paginator.current_page.object_list:
            transaction.rest_of_money = rest_of_money
            rest_of_money -= transaction.amount

    return render(request, 'profile/balance/index.jinja.html', locals())


@login_required
def topup(request):
    payment_system = request.POST.get('payment_system') or request.GET.get('payment_system') or settings.PAYMENT_SYSTEM_DEFAULT
    subpayment_system = None
    order_id = request.POST.get('order') or request.GET.get('order')

    # используется для pelipay
    if '-' in payment_system:
        payment_system, subpayment_system = payment_system.split('-')

    shop = settings.PAYMENT_SYSTEMS[payment_system]
    amount_raw = request.POST.get('amount') or request.GET.get('amount')

    if amount_raw:
        amount = float(amount_raw.replace(',', '.'))
        topup_comment = _(u'Пополнение баланса пользователя #%s') % (request.user.id)
        redirect_template = 'redirect.jinja.html'

        if payment_system == 'copayco':
            amount = int(amount * 100)
            params = {
                'shop_id': shop['SHOP_ID'],
                'ta_id': request.user.id,
                'amount': amount,
                'currency': 'UAH',
                'description': topup_comment.encode('utf-8'),
                'custom': order_id or '', # urllib.urlencode(request.POST),
                'date_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'random': random.randint(1,1024),
            }
            params['signature'] = hashlib.md5(''.join([str(params[key]) for key in  ['ta_id', 'amount', 'currency', 'custom', 'date_time', 'random']] + \
                      [ shop['SECRET'] ])).hexdigest()
            link = "https://www.copayco.com/pay.php?%s" % urllib.urlencode(params)
        elif 'liqpay' in payment_system:
            from utils.liqpay import LiqPay
            liqpay = LiqPay(shop['PUBLIC_KEY'], shop['PRIVATE_KEY'])
            form = liqpay.cnb_form({
                "action": "pay",
                "amount": amount,
                "currency": "UAH",
                "description": topup_comment,
                "order_id": order_id,
                "customer": request.user.id,
                "version": "3"
            })
            redirect_template = 'profile/balance/form_redirect.jinja.html'
        elif payment_system == 'pelipay':
            params = dict(
                paySystem=subpayment_system or 'visa', paymentCurrency='UAH', paymentId=request.user.id, paymentDescr=topup_comment,
                paymentAmount=amount, paymentIframeSrc=1, paymentSubmitButton=u"Оплатить",
            )
            pc = pelipay.PelipayConnector(**shop)
            result = pc.get_pay_form(params)

            if not result.get('success'):
                raise Http404("Some errors")

            formIframeUrl = result.get('data', {}).get('payForm')

            # эти странные люди (PeliPay) иногда сразу форму возвращают вместо ссылки
            if 'pay_form_id' in formIframeUrl:
                form = formIframeUrl
            else:
                tree = html.parse(formIframeUrl)
                form = html.tostring(tree.getroot().get_element_by_id('pay_form_id')).replace("target", "data-target")

            redirect_template = 'profile/balance/form_redirect.jinja.html'
        elif payment_system in ['interkassa2', 'interkassa_old']:
            params = {
                'ik_co_id': shop['SHOP_ID'],
                'ik_am': amount,
                'ik_cur': 'UAH',
                'ik_pm_no' : request.user.id,
#                'ik_usr' : request.user.id,
                'ik_desc' : topup_comment.encode('utf-8'),
                # 'ik_baggage_fields': '' # urllib.urlencode(request.POST)
            }
            if order_id:
                params['ik_x_order'] = order_id

            params_str = ':'.join([str(params[key]) for key in sorted(params.iterkeys())] + [shop['SECRET']])
            params['ik_sign'] = base64.b64encode(hashlib.md5(params_str).digest())
            link = "https://sci.interkassa.com/?%s" % urllib.urlencode(params)
        else:
            raise Http404("Incorrect payment system")

        cache.set('topup_amount_user%s' % request.user.id, amount_raw, 60*10) # TODO: см. topup_fail
        return render(request, redirect_template, locals())

    raise Http404("Incorrect value")

@db_transaction.atomic
@csrf_exempt
def topup_status(request, payment_system=None):
    if not payment_system:
        payment_system = request.POST.get('payment_system') or request.GET.get('payment_system') or settings.PAYMENT_SYSTEM_DEFAULT
    shop = settings.PAYMENT_SYSTEMS[payment_system]
    comment = ''
    note = ''

    if payment_system == 'copayco':
        if not request.POST['signature'] == hashlib.md5(''.join([str(request.POST.get(key, '')) for key in  ['ta_id', 'amount', 'currency', 'custom', 'date_time', 'random']] + \
                      [shop['SECRET']])).hexdigest():
            raise Http404("Incorrect data")

        request_type = request.POST.get('request_type', False)
        if request_type == 'perform' and request.POST.get('status') == 'finished':
            trans_id = request.POST['cpc_ta_id']
            amount = float(request.POST['amount'])/100
            user = User.objects.get(pk=int(request.POST['ta_id']))
            order_id = request.POST.get('custom')
        else:
            return HttpResponse("ok", content_type="text/plain")
    elif 'liqpay' in payment_system:
        from utils.liqpay import LiqPay

        liqpay = LiqPay(shop['PUBLIC_KEY'], shop['PRIVATE_KEY'])
        sign = liqpay.str_to_sign(shop['PRIVATE_KEY'] + request.POST.get('data') + shop['PRIVATE_KEY'])
        if request.POST.get('signature') != sign:
            raise Http404("Incorrect data")

        data = json.loads(base64.b64decode(request.POST.get('data')))
        if data['status'] == 'success':
            trans_id = data['payment_id']
            amount = float(data['amount'])
            order_id = data.get('order_id')

            # почему-то иногда Liqpay теряет поле customer
            if 'customer' in data:
                user = User.objects.get(pk=data['customer'])
            elif u'#' in data['description']:
                user = User.objects.get(pk=data['description'].split(u'#')[-1])
        else:
            return HttpResponse("ok", content_type="text/plain")
    elif payment_system == 'pelipay':
        pc = pelipay.PelipayConnector(**shop)
        result = pc.status_url(request.POST.dict())
        if not result.get('success') or 'data' not in result:
            raise Http404("Incorrect data")

        trans_id = result['data']['paymentExternalId']
        amount = float(result['data']['paymentAmountOrig'])
        user = User.objects.get(pk=int(result['data']['paymentId']))
    elif payment_system in ['interkassa2', 'interkassa_old']:
        params = request.POST.copy()
        del params['ik_sign']
        params_str = u':'.join([request.POST[key] for key in sorted(params.iterkeys())] + [shop['SECRET']])
        if (not 'ik_sign' in request.POST or request.POST['ik_sign'] != base64.b64encode(hashlib.md5(params_str.encode('utf-8')).digest())):
            raise Http404("Incorrect data")
        trans_id = request.POST['ik_trn_id']
        amount = float(request.POST['ik_am'])
        user = User.objects.get(pk=int(request.POST['ik_pm_no']))
        order_id = request.POST.get('ik_x_order')

    order = Order.objects.get(id=order_id) if order_id and order_id.isnumeric() else None

    comment = _(u'Пополнение баланса пользователя #%d %s (%s %s)') % (user.pk, user.username, payment_system, trans_id)
    trans, created = Transaction.objects.get_or_create(amount=amount, user=user, type=2, comment=comment, note=note, order=order)

    if order and not order.is_paid:
        # если у юзера после пополнения баланса не хватит денег на выполнение заказа, то он сам виноват
        try:
            order.execute()
        except InsufficientFundsError:
            pass

    return HttpResponse("OK", content_type="text/plain")

@csrf_exempt
@login_required
def topup_success(request):
    title = _(u'Успешная оплата')

    # получаем список последних оплаченных заказов
    five_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes=5)
    orders = [transaction.order for transaction in request.user.transactions.filter(type=2, order__isnull=False, order__is_paid=True, time__gt=five_minutes_ago)]

    return render(request, 'profile/balance/topup_success.jinja.html', locals())

@csrf_exempt
@login_required
def topup_fail(request):
    title = _(u'Ошибка во время проведения оплаты')
    topup_amount = cache.get('topup_amount_user%s' % request.user.id) # TODO: вероятно, неправильно покажет сумму при параллельных заказах - надо удалить или как-то переделать
    return render(request, 'profile/balance/topup_fail.jinja.html', locals())

@csrf_exempt
def topup_comeback_from_payment_system(request):
    '''
        Некоторые платежные системы не позволяют указать разные страницы редиректа для юзера после успешного/ошибочного платежа,
        поэтому здесь происходит своеобразный роутинг
    '''
    if 'payment_referrer' in request.session:
        url = request.session['payment_referrer']
        del request.session['payment_referrer']
        return redirect(url)
    elif request.user.is_authenticated():
        # получаем список последних оплаченных заказов
        five_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes=5)
        if request.user.transactions.filter(type=2, time__gt=five_minutes_ago).count():
            return redirect(topup_success)
        else:
            return redirect(balance) # так же можно переводить на topup_fail, но нет гарантий что действительно была ошибка платежа

@csrf_exempt
@login_required
def pelipay_finish(request, fail=False):
    shop = settings.PAYMENT_SYSTEMS['pelipay']

    pc = pelipay.PelipayConnector(**shop)
    result = pc.check_return_url(request.POST.dict() or request.GET.dict())
    if not result.get('success') or 'data' not in result:
        raise Http404("Incorrect data")

    if 'redirectUrl' in result['data'] and request.GET.get('action') != 'checkreturnurl':
        return redirect(result['data']['redirectUrl'])

    return topup_success(request) if not fail else topup_fail(request)
