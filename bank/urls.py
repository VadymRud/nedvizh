from django.conf import settings
from django.conf.urls import url, include

import django.views

import bank.views
import bank.callback
import ad.views

end_patterns = [
    url(r'^result.html', bank.views.search, {'deal_type': 'sale', 'show_result': True }, name='bank-ad-search-result'),
    url(r'^(?P<id>\d+).html', bank.views.detail, name='bank-ad-detail'),
    url(r'^(?P<id>\d+)-contacts.html', ad.views.show_contacts),
    url(r'^$', bank.views.search, {'deal_type': 'sale'}, name='bank-ad-search'),
]

urlpatterns = [
    url(r'^$', bank.views.index, name='bank-index'),
    
    url(r'^banks/$', bank.views.bank_list),
    url(r'^banks/(?P<id>[0-9]*)/$', bank.views.bank_detail),

    url(r'^(?P<property_type>residential|land|commercial)/(?P<regions_slug>[/a-z0-9\-]*)/', include(end_patterns)),
    url(r'^(?P<property_type>residential|land|commercial)/', include(end_patterns)),

    url(r'^callback/$', bank.callback.callback),

    url(r'^pages(?P<url>.*/)$', bank.views.simplepage, name='simplepage'),
]

if settings.DEBUG:
    urlpatterns.append(
        url(r'^media/(?P<path>.*)$', django.views.static.serve, {'document_root': settings.MEDIA_ROOT, 'show_indexes': True })
    )
    import debug_toolbar
    urlpatterns.append(url(r'^__debug__/', include(debug_toolbar.urls)))
