# coding: utf-8

from django.conf import settings

import requests

import random


def translate(texts, language_direction):
    request_params = {
        'text': texts,
        'key': random.choice(settings.YANDEX_TRANSLATOR_KEYS),
        'lang': language_direction,  # например, 'ru-uk'
    }
    response = requests.post('https://translate.yandex.net/api/v1.5/tr.json/translate', params=request_params)

    if response.status_code == 200:
        json = response.json()
        if json['code'] == 200:
            return json['text']
        else:
            raise Exception('Yander translator error: bad code in response')
    else:
        raise Exception('Yander translator error: bad response status')

