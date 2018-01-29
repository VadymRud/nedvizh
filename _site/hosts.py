# coding: utf-8

from django.conf import settings
from django_hosts import patterns, host

def callback(request, **kwargs):
    # TODO переименовать, так как это не поддомен
    request.subdomain = kwargs.get('region_subdomain_slug', None)

root_host_pattern = '%s' % settings.MESTO_PARENT_HOST.replace('.', '\\.')

host_patterns = patterns('',
    host(r'bank(?:[-\.](?P<region_subdomain_slug>\w+(?:-\w+)?))?\.%s' % root_host_pattern, 'bank.urls', name='bank', callback=callback),
    host(r'(?:(?P<region_subdomain_slug>\w+(?:-\w+)?)\.)?%s' % root_host_pattern, settings.ROOT_URLCONF, name='default', callback=callback),
)

