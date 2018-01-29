# coding=utf-8
from django.conf.urls import url

import views
import profile.views_balance

urlpatterns = [
    url(r'^realtors/$', views.realtors, name='realtors'),
    url(r'^realtors/add/user_exists/$', views.add_realtor_user_exists, name='add_realtor_user_exists'),
    url(r'^realtors/add/confirm/(?P<key>[\da-f]{32})/$', views.add_realtor_confirm, name='add_realtor_confirm'),
    url(r'^realtors/(?P<realtor_id>\d+)/$', views.realtor_detail, name='realtor_detail'),
    url(r'^realtors/(?P<realtor_id>\d+)/topup/$', views.realtor_topup, name='realtor_topup'),
    url(r'^properties/$', views.ads, name='ads'),
    url(r'^ads/$', views.ads), # чтобы работали старые ссылки
    url(r'^stats/$', views.stats, name='stats'),
    url(r'^balance/$', profile.views_balance.balance, name='balance'),
    url(r'^crm/$', views.crm, name='crm'),
    url(r'^city_typeahead/$', views.city_typeahead, name='city_typeahead'),
]

