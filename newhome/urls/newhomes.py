# coding: utf-8
from django.conf.urls import url

import newhome.views.newhomes
import ad.views

urlpatterns = [
    url(r'^(?P<newhome_id>\d+)-layouts.html', newhome.views.newhomes.layouts, name='layouts'),
    url(r'^(?P<newhome_id>\d+)-layout(?P<layout_id>\d+).html', newhome.views.newhomes.layout_flat, name='layout-flat'),
    url(r'^(?P<newhome_id>\d+)-floors.html', newhome.views.newhomes.floors, name='floors'),

    url(r'^streets.html', ad.views.streets, name='streets'),
    url(r'^subway.html', ad.views.subway, name='subway'),
    url(r'^districts.html', ad.views.districts, name='districts'),

    url(r'^(?P<id>\d+).html', newhome.views.newhomes.detail, name='ad-detail'),
    url(r'^$', newhome.views.newhomes.search, name='ad-search'),
]

