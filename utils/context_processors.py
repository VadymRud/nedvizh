# coding: utf-8
from django.conf import settings

def django_settings(request):
    return {name: getattr(settings, name) for name in (
        'DEBUG',
    )}