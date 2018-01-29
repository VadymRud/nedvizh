# coding: utf-8

from django.conf import settings
from django.core.urlresolvers import reverse

from django_jinja import library

from staticpages.models import SimplePage

@library.global_function
def get_simplepages_footer_menu():
    urls = ['/about/', '/about/contact/']
    pages = list(SimplePage.objects.filter(urlconf='_site.urls', url__in=urls))
    pages.sort(key=lambda page: urls.index(page.url))
    return [(reverse('simplepage', kwargs={'url': page.url}), page.title, {}) for page in pages]

