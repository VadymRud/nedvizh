# coding: utf-8
from django.conf.urls import url

import newhome.views.admin

urlpatterns = [
    url(r'^moderation/$', newhome.views.admin.newhome_moderation, name='newhome_moderation_queue'),
    url(r'^moderation/(?P<moderation_id>\d+)/$', newhome.views.admin.newhome_moderation, name='newhome_moderation_detail'),
]

