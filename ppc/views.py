# coding: utf-8
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.core.cache import cache
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt

from ppc.models import get_lead_price, LeadGeneration, ProxyNumber, Call, Review
from forms import LeadGenerationForm
from ad.models import Region

import json
import datetime

from newhome.decorators import restrict_access_for_developer

@login_required
@restrict_access_for_developer
def lead_activate(request):
    user_recipient = request.user
    if 'realtor' in request.GET:
        user_recipient = user_recipient.get_own_agency().get_realtors().get(pk=request.GET['realtor']).user

    # периоды лидогенерации создаются в сигнале check_leadgeneration_status у LeadGeneration
    leadgeneration, created = LeadGeneration.objects.get_or_create(user=user_recipient)
    leadgeneration.is_active_ads = True
    leadgeneration.save()

    balance_limit_for_activation = 200

    # выделенный номер стоит 100 грн
    # TODO: пусть пока будет общая логика и минималка без учета стоимости выделенного номера
    if user_recipient.get_leadgeneration() and user_recipient.get_leadgeneration().dedicated_numbers:
        balance_limit_for_activation += 100

    user_balance = user_recipient.get_balance(force=True)
    user_plan = user_recipient.get_active_plan()

    # учитываем возврат денег за тариф при переходе на ППК
    if user_plan:
         user_balance += user_plan.get_payback()

    if not user_recipient.get_realtor() and not user_recipient.is_developer():
        messages.error(request, _(u'Данной услугой могут воспользоваться только риелторы и застройщики'))
        
    elif user_balance < balance_limit_for_activation and not user_recipient.has_active_leadgeneration('ads'):
        from paid_services.models import Transaction, Order
        topup_amount = balance_limit_for_activation - user_balance

        # если услуги покупаются не риелтора агентства, но у риелтора не хватило денег,
        # то перекидываем деньги от текущего юзера
        if user_recipient != request.user and request.user.get_balance(force=True) >= topup_amount:
            Transaction.move_money(request.user, user_recipient, topup_amount, u'для активации ППК из кабинета агентства')

        if 'show_topup' not in request.GET:
            html = '''
                <p>%s</p><br/><button class="btn btn-danger btn-lg btn-block" type="button" data-toggle="modal" data-target=".topup-modal">%s</button>
            ''' % (_(u'Для активации услуги "Оплата за звонок" остаток на балансе должен быть более %(balance_limit)s грн.')  % {'balance_limit':balance_limit_for_activation},
                   _(u'Пополнить'), )
            messages.info(request, html, extra_tags='modal-style1')

        query_string = request.GET.copy()
        query_string ['topup_amount'] = topup_amount
        return HttpResponseRedirect('%s?%s' % (reverse('services:lead'), query_string.urlencode()))

    elif user_recipient.has_active_leadgeneration('ads'):
        if user_recipient.ads.count() > 0:
            messages.success(request, _(u'Оплата за звонок активирована'))
        else:
            if request.is_developer_cabinet_enabled:
                add_property_url = reverse('profile_newhome_object_add')
            else:
                add_property_url = reverse('profile_add_property')

            html = '''<h5>%s<br/><br/>%s:</h5><br/><a href="%s" class="btn btn-danger btn-lg btn-block">%s</a>
            ''' % (_(u'Услуга оплата за звонок успешно активирована.'), _(u'Добавьте своё первое объявление'),
                   add_property_url, _(u'Добавить'),  )
            messages.info(request, html, extra_tags='modal-sm text-center')

        if 'next' in request.GET:
            return redirect(request.GET['next'])

    # возвращается на REFERER, т.к. на исходной странице могут переданы параметры типа ?realtor=
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('services:lead')))


def lead(request):
    title = _(u'Оплата за звонок')
    selected_province = Region.get_capital_province()

    if request.user.is_authenticated:
        if request.user.region:
            selected_province = request.user.region

        user_recipient = request.user
        if 'realtor' in request.GET:
            user_recipient = user_recipient.get_own_agency().get_realtors().get(pk=request.GET['realtor']).user

        leadgeneration = request.user.get_leadgeneration() or LeadGeneration(user=request.user)
        leadgeneration_form = LeadGenerationForm(instance=leadgeneration)

    lead_prices = {}
    for lead_type in ['call', 'callrequest']:
        for deal_type in ['sale', 'rent', 'rent_daily']:
            lead_prices['%s_%s' % (lead_type, deal_type)] = get_lead_price(lead_type, deal_type,
                                                                           selected_province.price_level)
    active_proxynumbers = ProxyNumber.objects.filter(is_shared=False, user__isnull=True).count()
    reviews = Review.objects.all()

    return render(request, 'ppc/lead.jinja.html', locals())


@csrf_exempt
def incoming_call(request):
    """ обработка входящего звонка на сервис calltracking и возврат номера для переадресации
        data sample: {u'date': u'2016-11-23 00:52:47', u'src': u'79085788620', u'dst': u'74996491657', u'uuid': u'3677960d-9b14-4497-91b6-c03fea4f1bc6', u'additional_number': u'6543217'}
    """
    data = json.loads(request.body)

    print 'incoming call', data
    if 'dst' in data:
        user = None

        numbers = [data['dst']]
        if data['dst'][0] == '0':
            numbers.append('38%s' % data['dst'])
        proxynumber = ProxyNumber.objects.get(number__in=numbers)

        object_id = data.get('additional_number', '').replace('*', '')
        if object_id and object_id.isdigit():
            object_id = int(object_id)
        else:
            object_id = None

        extra_numbers = []
        if proxynumber.is_shared:
            if object_id:
                # номер объекта хранится в хэше, т.к. при завершении звонка телефония не передает additional number
                cache.set('additional_number_for_call_%s' % data['uuid'], object_id, 60*60*24)

                if proxynumber.deal_type == 'newhomes':
                    from newhome.models import Newhome
                    newhome = Newhome.objects.get(pk=object_id)
                    user = newhome.user
                    extra_numbers = list(newhome.priority_phones.values_list('number', flat=True))

                else:
                    from ad.models import Ad
                    user = Ad.objects.get(pk=object_id).user
        elif proxynumber.user:
            user = proxynumber.user

        if user and user.has_active_leadgeneration():
            if user.leadgeneration.is_working_time():
                user_numbers = list(user.phones.values_list('number', flat=True)[:3])
                if extra_numbers:
                    user_numbers = (extra_numbers + user_numbers)[:3]

                print ' Owner found: user #', user.id, 'Chosen numbers:', user_numbers
                return JsonResponse({"number_01": ",".join(user_numbers)})

            else:
                print " User isn't working right now"
                return JsonResponse({"number_01": "voicemail"})

    return JsonResponse({"error": "no numbers"})


@csrf_exempt
def finished_call(request):
    data = json.loads(request.body)

    print 'finished call', data

    Call.sync_data_from_ringostat(1)

    # запускаем callback
    if data['status'] == 'NO EXTENSION' and not data['target_number']:
        import requests
        callback_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "Api\\V2\\Callback.external",
            "params": {"caller": data['src'], "callee": "mestoua_moder1", "projectId": "38466",}
        }
        requests.post('https://api.ringostat.net/a/v2', json=callback_data, headers={'Auth-Key':'1VmQaYHNwxw9XSEIR64'})

    return HttpResponse("ok", content_type="text/plain")
