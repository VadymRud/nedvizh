# coding: utf-8
from __future__ import unicode_literals

from django.http import QueryDict


def make_utm_dict(utm_campaign, **kwargs):
    utm = QueryDict(mutable=True)
    utm.update({
        'utm_source': 'newsletter',
        'utm_medium': 'email',
        'utm_campaign': utm_campaign
    })
    utm.update(kwargs)

    return utm


def make_ga_pixel_dict(user, utm):
    """
    Для корректного подсчета данных в ГА формируем словарь необходимых данных

    :param user:
    :param utm:
    :return:
    """

    if user is None:
        return None

    ga_pixel_dict = QueryDict(mutable=True)
    ga_pixel_dict.update({
        'v': 1,
        'tid': 'UA-24628616-30',
        'cid': utm['utm_campaign'],
        't': 'event',
        'ea': 'open',
        'ec': utm['utm_medium'],
        'el': utm['utm_campaign'],
        'cs': utm['utm_source'],
        'cm': utm['utm_medium'],
        'cn': utm['utm_campaign'],
        'cd1': user.id,
    })

    user_region_host = user.get_region_host() if user is not None else None
    if user_region_host:
        ga_pixel_dict.update({
            'dl': 'https://' + user_region_host
        })

    return ga_pixel_dict
