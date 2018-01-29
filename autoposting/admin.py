# coding: utf-8
from __future__ import unicode_literals

import datetime

from facebook import auth_url
from django.conf import settings
from django.contrib import admin

from autoposting.models import FacebookAutoposting, VkAutoposting
from utils.templatetags.jinja import host_url


@admin.register(FacebookAutoposting)
class FacebookAutopostingAdmin(admin.ModelAdmin):
    def _auth_status(self, obj):
        if obj:
            login_url = auth_url(
                settings.FACEBOOK_APP_ID, host_url('autoposting-facebook-callback'), ['manage_pages', 'publish_pages'])

            # Специально занижаем дату действия токена, чтобы не забывали обновлять, а постинг работал
            if obj.access_token and obj.access_token_expires_at - datetime.timedelta(days=3) > datetime.datetime.now():
                return 'Активно до %s<br><a href="%s">Обновить токен</a>' % (
                    (obj.access_token_expires_at - datetime.timedelta(days=3)).strftime('%H:%M %d.%m.%Y'), login_url
                )

            return '<a href="%s">Получить токен</a>' % login_url

        return '&ndash;'

    _auth_status.allow_tags = True
    _auth_status.short_description = 'Токен'

    list_display = ['name', 'page_id', '_auth_status', 'is_active', 'region', 'deal_type']
    list_filter = ['deal_type', 'is_active']
    search_fields = ['name', 'page_id']
    raw_id_fields = ['region']
    exclude = ['access_token', 'access_token_expires_at', 'last_posting_at']


@admin.register(VkAutoposting)
class VkAutopostingAdmin(admin.ModelAdmin):
    list_display = ['name', 'page_id', 'is_active', 'region', 'deal_type']
    list_filter = ['deal_type', 'is_active']
    search_fields = ['name', 'page_id']
    raw_id_fields = ['region']
    exclude = ['last_posting_at']
