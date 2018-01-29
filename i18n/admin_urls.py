from django.conf.urls import url
from django.conf import settings

import i18n.admin_views

url_pattern = r'^(?P<language>%s)/%%s(?P<domain>django|djangojs)/(?P<filter>untranslated|all)/$' % \
    '|'.join(i18n.admin_views.languages_to_translate)

urlpatterns = [
    url(r'^$', i18n.admin_views.translate_index, name='index'),
    url(url_pattern % r'(?P<app_label>[a-z0-9_\.]+)/', i18n.admin_views.translate_edit, name='edit'),
    url(url_pattern % r'', i18n.admin_views.translate_edit, {'app_label': None}, name='edit'),
]

