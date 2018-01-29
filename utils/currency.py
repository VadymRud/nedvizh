# coding: utf-8
import urllib
from django.core.cache import cache

import datetime
import requests

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET


def get_currency_rates(force_update=False):
    """
    Получаем текущие курсы валют
    
    :param force_update:
    :return:
    """
    cached_rates = cache.get('currency_rates', None)
    update_time = cache.get('currency_rates_update_time', None)

    if force_update or (cached_rates is None) or (update_time is None) or ((datetime.datetime.now() - update_time).days >= 1):
        try:
            tree = ET.fromstring(requests.get('https://api.privatbank.ua/p24api/pubinfo?exchange&coursid=3', timeout=5).content)
        except Exception as e:
            # чтобы кинуть ошибку в sentry, но следующую попытку делать через час
            cache.set('currency_rates_update_time', datetime.datetime.now() - datetime.timedelta(hours=23), timeout=None)
            raise e

        new_rates = {'UAH': 1}
        for node in tree.getiterator('exchangerate'):
            if 'ccy' not in node.attrib:
                continue

            current_code = node.attrib['ccy']
            if current_code in ['EUR', 'USD', 'RUR']:
                new_rates[current_code] = float(node.attrib['sale'])

        if 'USD' in new_rates:
            cache.set('currency_rates', new_rates, timeout=None)
            cache.set('currency_rates_update_time', datetime.datetime.now(), timeout=None)

            return new_rates

    if cached_rates is not None:
        return cached_rates

    else:
        raise Exception('cannot get new rates and no cached rates')


def update_properties_price(force_update=False):
    from django.db.models import F
    from ad.models import Ad

    for currCode, rate in get_currency_rates(force_update).iteritems():
        print 'Currency update:', Ad.objects.filter(currency=currCode).update(price_uah=F('price') * rate ), 'rows for', currCode
