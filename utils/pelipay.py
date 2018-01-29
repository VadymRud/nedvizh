# -*- coding: utf-8 -*-
import json
import hashlib
import requests


class PelipayConnector:
    def __init__(self, **kwargs):
        self.SECRET_KEY = kwargs.get('SECRET_KEY')
        self.HOST = kwargs.get('HOST')
        self.API_URL = kwargs.get("API_URL")

    def get_pay_form(self, data):
        return self.send_request("getPayForm", data)

    def get_paysystems(self):
        response = self.send_request("getAvailablePaysystems", {})
        return map(lambda s: s.lower(), response['data']['paySystems']) if response['success'] else []

    def status_url(self, data):
        return self.send_request("statusUrl", data)

    def check_return_url(self, data):
        return self.send_request("checkReturnUrl", data)

    def send_request(self, action, data):
        out = self.prepare_request(action, data)
        r = requests.post(self.API_URL, data=out, timeout=20)
        if r.status_code == 200:
            return r.json()
        return {"statuscode": 503, "error": "Server is not responding"}

    def prepare_request(self, action, data):
        out_json = json.dumps({
            "action": action,
            "host": self.HOST,
            "request": data
        })
        m = hashlib.md5()
        check_string = self.SECRET_KEY + out_json + self.SECRET_KEY
        m.update(check_string)
        md5_string = m.hexdigest()
        return {
            "data": out_json.encode('base64', 'strict').strip(),
            "sign": md5_string.encode('base64', 'strict').strip()
        }

'''

import urllib
from logging import getLogger

import lxml.html
from django.shortcuts import redirect

def set_transaction_successed_by_id(transaction_id, amount):
    pass

def redirect_form(values, transaction):
    transaction.user_amount = values.get('amount', type=float)
    transaction.save()
    pc_request_dict = dict(
        paySystem=transaction.ps_payment_method.pay_system,
        paymentCurrency=transaction.ps_payment_method.payment_currency,
        paymentId=transaction.invoice,
        paymentDescr=transaction.description,
        paymentAmount=transaction.user_amount,
        paymentIframeSrc=1,
        paymentTarget="_blank"
    )
    pc = PelipayConnector()
    result = pc.get_pay_form(pc_request_dict)
    pay_form_type = result['data']['payFormType']
    if pay_form_type.lower() == "form" and result['data']['payMethod'].lower() == "get":
        return redirect(result['data']['payAction'])
    return redirect(request.referrer)


def get_payment_form(transaction):
    action_url = "{domain}_ps/api_v2/redirect/{transaction_id}/{user_token}/".format(
        domain="http://%s/" % transaction.ps_provider.domain,
        transaction_id=transaction.id,
        user_token=transaction.user.token)
    result = dict(
        action=action_url,
        method="POST",
        hidden_fields=dict(),
        redirect=True
    )
    return result


def complete_url(host_id):
    # {u'data': {u'paymentId': u'66830'}, u'success': True}
    # pelipay_provider = PelipayProvider.objects(host_id=host_id).first()
    pc = PelipayConnector()
    result = pc.check_return_url(request.values.to_dict())
    try:
        if result.get('success', False):
            data = result.get('data', None)
            if data:
                redirect_url = data.get('redirectUrl', None)
                payment_id = data.get('paymentId', None)
                if redirect_url:
                    return redirect(redirect_url)
                if payment_id:
                    transaction = get_transaction_by_invoice(int(payment_id))
                    return redirect(transaction.user.payment_completed_url)
    except Exception as ex:
        getLogger().exception(ex)
    return redirect(request.referrer)


def iframe_url(**data):
    try:
        # pelipay_provider = PelipayProvider.objects(host_id=host_id).first()
        pc = PelipayConnector()
        pay_form = pc.get_pay_form(data)
        return pay_form['data']['payForm']
    except Exception as ex:
        getLogger().exception(ex)
    return '{"success": false}'


def status_url(host_id):
    # pelipay_provider = PelipayProvider.objects(host_id=host_id).first()
    if pelipay_provider:
        pc = PelipayConnector()
        result = pc.status_url(request.values.to_dict())
        if 'success' in result and result['success'] == True:
            data = result.get('data', False)
            if not data:
                return "YES"
            transaction = get_transaction_by_invoice(int(result['data']['paymentId']))
            if transaction:
                transaction = set_transaction_successed_by_id(transaction.pk,
                                                              float(result['data']['paymentAmount']))
                api_send_status(transaction)
        return ""
    else:
        getLogger().error("CANT FIND PelipayTransactionRef by")
        return ""


def api_do_buy_request(request_data, transaction):
    try:
        transaction.ps_provider = PelipayProvider.objects.get(user=transaction.user)
        transaction.save()
    except Exception as ex:
        getLogger().exception(ex)

    pc_request_dict = dict(
        paySystem=transaction.ps_payment_method.pay_system,
        paymentCurrency=transaction.ps_payment_method.payment_currency,
        paymentId=transaction.invoice,
        paymentDescr=transaction.description,
        paymentAmount=transaction.summ,
        paymentIframeSrc=1,
        paymentTarget="_blank",
        paymentSubmitButton="Ok",
        paymentH2="%s %s$" % (str(transaction.currency), str(transaction.user_amount)),
        paymentCss=transaction.user.iframe_css
    )
    pc = PelipayConnector()
    result = pc.get_pay_form(pc_request_dict)
    if 'error' in result:
        getLogger().exception(result)
        return redirect(request.referrer)

    pay_ext_id = result['data']['payExtId']
    PelipayTransactionRef(transaction=transaction, user=transaction.user, pay_ext_id=int(pay_ext_id),
                          pelipay_provider=transaction.ps_provider).save()

    if not 'payFormType' in result['data']:
        raise Exception('500')
    pay_form_type = result['data']['payFormType']
    if pay_form_type == 'iframe':
        transaction.interaction_type = InteractionType.IFRAME
        transaction.save()
        return result['data']['payForm']
    elif pay_form_type == 'form':
        location = result['data']['payAction']
        method = result['data']['payMethod']
        location += '?'
        doc = lxml.html.fromstring(result['data']['payForm'])
        data_dict = {}
        for elem in doc:
            if hasattr(elem, 'value'):
                data_dict[elem.name] = elem.value
        response_data = urllib.urlencode(data_dict)
        location += response_data
        return location, method
    else:
        raise Exception('500')


def _sci_form_request(transaction, amount):

    # transaction.ps_provider = PelipayProvider.objects.get(type='INTERNAL')
    # transaction.save()
    pc_request_dict = dict(
        paySystem=transaction.ps_payment_method.pay_system,
        paymentCurrency=transaction.ps_payment_method.payment_currency,
        paymentId=transaction.invoice,
        paymentDescr=transaction.description,
        paymentAmount=transaction.summ,
        paymentIframeSrc=1,
        paymentTarget="_blank",
        paymentSubmitButton="Ok",
        paymentH2="Test payment for mesto.ua. %s %s" % (transaction.summ, transaction.currency),
        paymentCss=transaction.user.iframe_css
    )
    pc = PelipayConnector()
    result = pc.get_pay_form(pc_request_dict)

    if 'error' in result:
        getLogger().exception(result)

    # pay_ext_id = result['data']['payExtId']
    # PelipayTransactionRef(transaction=transaction, user=transaction.user, pay_ext_id=int(pay_ext_id),
    #                       pelipay_provider=transaction.ps_provider).save()

    # if not 'payFormType' in result['data']:
    #     raise Exception('500')
    # pay_form_type = result['data']['payFormType']
    # if pay_form_type == 'iframe':
    #     transaction.interaction_type = InteractionType.IFRAME
    #     transaction.save()
    #     return result['data']['payForm']
    # elif pay_form_type == 'form':
    #     location = result['data']['payAction']
    #     method = result['data']['payMethod']
    #     location += '?'
    #     doc = lxml.html.fromstring(result['data']['payForm'])
    #     data_dict = {}
    #     for elem in doc:
    #         if hasattr(elem, 'value'):
    #             data_dict[elem.name] = elem.value
    #     response_data = urllib.urlencode(data_dict)
    #     location += response_data
    #     return location, method
    # else:
    #     raise Exception('500')

    return result


def make_payment_form(transaction, amount):
    req_result = _sci_form_request(transaction, amount)
    if req_result:
        result = dict(
            action=req_result['action'],
            fields=req_result['parameters'],
        )
        return result
    else:
        payment_method = get_transaction_payment_method(transaction)
        result = dict(
            action="https://sci.interkassa.com/",
            fields=dict(
                ik_co_id=transaction.ps_provider.ik_co_id,
                ik_pw_via=payment_method.ik_pw_via,
                ik_am='%.2f' % float(amount),
                ik_pm_no=transaction.invoice,
                ik_desc=transaction.description,
                ik_cur=payment_method.ik_cur,
                ik_act=payment_method.ik_act,
                ik_suc_u=transaction.user.payment_completed_url,
                ik_suc_m='GET',
                ik_fal_u=transaction.user.payment_completed_url,
                ik_fal_m='GET',
                ik_pnd_u=transaction.user.payment_completed_url,
                ik_pnd_m='GET',
                ik_ia_m='POST',
            )
        )
        return result
    return {}

'''