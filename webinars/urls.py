# coding=utf-8
from django.conf.urls import url, include
from django.views.generic import RedirectView

import webinars.views

seminar_urlpatterns = [
    url(r'^$', webinars.views.index, name='webinars'),
    url(r'^(?P<slug>[_a-zA-Z0-9\-\.]*)/$', webinars.views.detail, name='webinar_detail'),
    url(r'^load-comments/(?P<slug>[_a-zA-Z0-9\-\.]*)/$', webinars.views.load_comments, name='webinar_load_comments'),
]

urlpatterns = [
    url(r'^$', RedirectView.as_view(pattern_name='school:webinars', permanent=True), kwargs={'type': 'webinar'}, name='index'),
    url(r'^articles/$', webinars.views.category_list, name='articles'),
    url(r'^articles/(?P<slug>[_a-zA-Z0-9\-\.]*)/$', webinars.views.article_detail, name='article_detail'),
    url(r'^(?P<type>webinar|seminar)s/', include(seminar_urlpatterns)),
]