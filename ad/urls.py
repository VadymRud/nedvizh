from django.conf.urls import url

import ad.views

urlpatterns = [
    url(r'^streets.html', ad.views.streets, name='streets'),
    url(r'^subway.html', ad.views.subway, name='subway'),
    url(r'^districts.html', ad.views.districts, name='districts'),
    url(r'^settlements.html', ad.views.settlements, name='settlements'),
    url(r'^(?P<id>\d+).html', ad.views.detail, name='ad-detail'),
    url(r'^(?P<id>\d+)-contacts.html', ad.views.show_contacts, name='ad-contacts'),
    url(r'^ajax$', ad.views.search, name='ad-ajax'),
    url(r'^$', ad.views.search, name='ad-search'),
]
