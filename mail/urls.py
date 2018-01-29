# coding: utf-8
from __future__ import unicode_literals

from django.conf.urls import url
from django.views.generic import TemplateView
from .views import view_render_email

urlpatterns = [
    url(r'^poltava/$', TemplateView.as_view(template_name='mail/landings/poltava/landing.jinja.html'), name='poltava'),
    url(r'^view_render_email/$', view_render_email  , name='view_render_email'),
]
