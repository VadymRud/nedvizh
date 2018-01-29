# coding: utf-8

from django.core.management.base import BaseCommand
from django.core.cache import cache

from lxml import etree

import requests
import datetime


class Command(BaseCommand):
    help = u'Обновляет кэш с номерами АСНУ'

    def handle(self, *args, **options):
        print datetime.datetime.now()
        r = requests.get('http://www.asnu.net/users/xml')
        root = etree.fromstring(r.content)
        valid_asnu_numbers = [tag.text.replace('-', '') for tag in root.iterfind('.//asnu-cert') if tag.text is not None]
        cache.set('valid_asnu_numbers', valid_asnu_numbers, 60*60*24)

