from django.conf.urls import url

import views
from profile import views_messages

urlpatterns = [
    url(r'^$', views.search, name='search'),
    url(r'^(?P<professional_type>agency|realtor)/$', views.search, name='search'),
    url(r'^agency/(?P<agency_id>\d+)/$', views.agency_profile, name='agency_profile'),
    url(r'^agency/(?P<agency_id>\d+)/realtor/$', views.agency_realtors, name='agency_realtors'),
    url(r'^agency/(?P<agency_id>\d+)/realtor/(?P<user_id>\d+)/$', views.realtor_profile, name='realtor_profile'),
    url(r'^agency/(?P<agency_id>\d+)/reviews/$', views.agency_reviews, name='agency_reviews'),
    url(r'^agency/(?P<agency_id>\d+)/redirect/$', views.agency_redirect, name='agency_redirect'),
    url(r'^send_message/(?P<user_id>\d+)/$', views_messages.add_message, name='send_message'),
    url(r'^agency/(?P<agency_id>\d+)/contacts/', views.agency_contacts, name='agency_contacts'),
    url(r'^agency/(?P<agency_id>\d+)/realtor/(?P<user_id>\d+)/contacts/', views.realtor_contacts, name='realtor_contacts'),
]

