# coding: utf-8

"""
Yandex.Maps API wrapper
"""
import random

from django.conf import settings
from django.core.cache import cache
import xml.dom.minidom
import urllib
import requests
import logging

try:
    import win_inet_pton # используется для работы прокси через Sock5 на Windows
except ImportError:
    pass

STATIC_MAPS_URL = 'https://static-maps.yandex.ru/1.x/?'
GEOCODE_URL = 'https://geocode-maps.yandex.ru/1.x/?'

logger = logging.getLogger('geocoder')

def get_map_url(longtitude, latitude, zoom, width, height):
    ''' returns URL of static yandex map '''
    params = [
       'll=%0.7f,%0.7f' % (float(longtitude), float(latitude),),
       'size=%d,%d' % (width, height,),
       'z=%d' % zoom,
       'l=map',
       'pt=%0.7f,%0.7f' % (float(longtitude), float(latitude),),
       # 'key=%s' % random.choice(settings.YANDEX_MAPS_API_KEYS)
    ]
    return STATIC_MAPS_URL + '&'.join(params)


def make_random_internal_ip():
    return '192.168.%d.%d' % (random.randint(10, 240), random.randint(10, 240))

def proxied_get(*args, **kwargs):
    # меням порядок прокси
    random.shuffle(settings.MESTO_PROXIES)

    selected_proxy = None
    for proxy in settings.MESTO_PROXIES:
        if not cache.get('banned-proxy-%s' % proxy):
            selected_proxy = proxy
            break

    try:
        r = requests.get(*args, proxies={'http': selected_proxy, 'https':selected_proxy}, **kwargs)
    except requests.exceptions.ConnectionError as e:
        if selected_proxy:
            logger.debug('problem with proxy: %s' % e, extra={'url': args[0], 'status_code': 504, 'requests_settings': {'proxy':selected_proxy}})
            # cache.set('banned-proxy-%s' % selected_proxy, True, 60 * 5) # 5 min

            # повторная попытка с другим прокси или вообще без него
            return proxied_get(*args, **kwargs)
        else:
            raise e

    return r, selected_proxy

def geocode(address, timeout=2, full_info=False, lang='ru_RU'):
    if isinstance(address, unicode):
        address = address.encode('utf8')

    params = {'geocode': address, 'lang': lang}
    if 'Украина, ' not in address:
        params['key'] = random.choice(settings.YANDEX_MAPS_API_KEYS)

    url = GEOCODE_URL + urllib.urlencode(params)

    # Добавляем случайный внутренний IP в заголовок, для обхода ограничений по подключению для яндекса
    request_headers = {'X-Forwarded-For': make_random_internal_ip()}

    try:
        r, proxy = proxied_get(url, headers=request_headers, timeout=timeout)
    except IOError:
        return {
            'coords': (None, None),
            'kind': None
        }

    response = r.text.encode('utf-8')
    if r.status_code != 200:
        message = response
    else:
        message = ''
    logger.debug(message, extra={'url': url, 'status_code': r.status_code, 'requests_settings': {'proxy':proxy}})

    geocode = {
        'coords': _get_coords(response),
        'kind': _get_kind(response),
    }
    
    if full_info:
        geocode['address'] = _get_address_details(response)
        geocode['street'] = _get_street(response)
        geocode['description'] = ', '.join(_get_desciption(response).split(', ')[::-1])
    return geocode
        

# получение адреса по координатам. выводит адрес от района города и крупнее.
def geocode_reverse(coords, timeout=2, kind=None, lang='ru_RU'):
    params = {'geocode': coords, 'lang': lang}
    if kind:
        params['kind'] = kind
        params['results'] = 1

    lat, long = map(float, coords.split(','))

    # long, lat формат
    areas_without_key = [
        [[47.89181, 22.17120], [54.29787, 47.12248]], # Основаная часть Украины и Белорусия
        [[42.70399, 29.52238], [48.11543, 55.95549]], # Юг украины
        [[43.47420, 30.92863], [48.11543, 55.95549]], # Россия, Казахстан
    ]
    for lb_corner, rt_corner in areas_without_key:
        if lb_corner[0] < long < rt_corner[0] and lb_corner[1] < lat < rt_corner[1]:
            break
    else:
        params['key'] = random.choice(settings.YANDEX_MAPS_API_KEYS)

    url = GEOCODE_URL + urllib.urlencode(params)

    # Добавляем случайный внутренний IP в заголовок, для обхода ограничений по подключению для яндекса
    request_headers = {'X-Forwarded-For': make_random_internal_ip()}

    try:
        r, proxy = proxied_get(url, headers=request_headers, timeout=timeout)
    except IOError:
        return []

    response = r.text.encode('utf-8')
    if r.status_code != 200:
        message = response
    else:
        message = ''
    logger.debug(message, extra={'url': url, 'status_code': r.status_code, 'requests_settings': {'proxy':proxy}})

    return _get_address(response)


# получение массива элементов адреса для обратного геокодера
def _get_address(response):
    try:
        detail_address = []
        dom = xml.dom.minidom.parseString(response)
        members = dom.getElementsByTagName('featureMember')
        for member in members:
            kind = member.getElementsByTagName('kind')[0].firstChild.data
            name = member.getElementsByTagName('Component')[-1].getElementsByTagName('name')[0].firstChild.data
            pos = member.getElementsByTagName('pos')[0].firstChild.data.split()
            text = member.getElementsByTagName('text')[0].firstChild.data
            bounded_by = '%s;%s' % (member.getElementsByTagName('lowerCorner')[0].firstChild.data,
                                    member.getElementsByTagName('upperCorner')[0].firstChild.data)

            # для некоторых поселков/сел геокодер яндекса передает тип locality
            if name.startswith(u'село') or name.startswith(u'поселок') or name.startswith(u'посёлок'):
                kind = 'village'

            addr_replaces = {
                u', город ':u', ',
                u'Крым автономная республика':u'Республика Крым',
                u'автономная республика Крым':u'Республика Крым',
            }
            for str in [name, text]:
                for i, j in addr_replaces.iteritems():
                    str = str.replace(i, j)

            detail_address.insert(0, [kind, name, pos, text, bounded_by])

        return detail_address
        
    except IndexError:
        return None
    
        
# получение улицу из ответа геокодера
def _get_street(response):
    street = ''
    try:
        dom = xml.dom.minidom.parseString(response)
        street += dom.getElementsByTagName('ThoroughfareName')[0].firstChild.data
        street += ', ' + dom.getElementsByTagName('PremiseNumber')[0].firstChild.data
    except IndexError:
        pass
    return street

# получение улицу из ответа геокодера
def _get_desciption(response):
    try:
        dom = xml.dom.minidom.parseString(response)
        return dom.getElementsByTagName('description')[0].firstChild.data
    except IndexError:
        return ''

# получение массива элементов адреса из ответа геокодера
def _get_address_details(response):
    try:
        dom = xml.dom.minidom.parseString(response)
        pos_elem = dom.getElementsByTagName('AddressDetails')[0]
        return _get_address_turple(pos_elem)
    except IndexError:
        return None

# рекурсивная функция для _get_address_details
def _get_address_turple(parent):
    kinds = {
        'CountryName':'country',
        'AdministrativeAreaName':'province',
        'SubAdministrativeAreaName':'area',
        'LocalityName':'locality',
        'DependentLocalityName':'district',
        'ThoroughfareName':'street',
        'PremiseName':'vegetation',
        'PremiseNumber':'house',
    }
    addresses = []
    for node in parent.childNodes:
        if node.nodeType == node.ELEMENT_NODE:
            if node.tagName in kinds:
                addresses.append((kinds[node.tagName], node.firstChild.data))
            else:
                addresses += _get_address_turple(node)

    return addresses
    
def _get_coords(response):
    try:
        dom = xml.dom.minidom.parseString(response)
        pos_elem = dom.getElementsByTagName('pos')[0]
        pos_data = pos_elem.childNodes[0].data
        return tuple(pos_data.split())
    except IndexError:
        return None, None
        
def _get_kind(response):
    try:
        dom = xml.dom.minidom.parseString(response)
        return dom.getElementsByTagName('kind')[0].childNodes[0].data
    except IndexError:
        return None

