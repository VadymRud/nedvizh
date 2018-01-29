# coding: utf-8
from django.contrib import admin
from django.conf.urls import url, include
from django.views.decorators.cache import never_cache
from django.db.models import Q

import i18n.admin_urls

import collections

class ExtendedAdminSite(admin.AdminSite):
    index_template = 'admin_ext/index.html'
    site_header = 'Mesto.UA'

    # без этих настроек попытки поменять пароль из меню в админке приводят к рендерингу
    # несуществующих шаблонов 'registration/*.html', а нам нужны 'registration/*.jinja.html'
    password_change_template = 'registration/password_change_form.jinja.html'
    password_change_done_template = 'registration/password_change_done.jinja.html'

    def get_urls(self):
        urls = super(ExtendedAdminSite, self).get_urls()
        return [url(r'^translate/', include(i18n.admin_urls, namespace='translate'))] + urls

    # мы используем свой шаблон для admin:index (см. index_template), для него необходим дополнительный контекст
    @never_cache
    def index(self, request, extra_context=None):
        extra_context = extra_context or {}

        from ad.models import Ad, Moderation
        from paid_services.models import CatalogPlacement

        new_ads_stats = collections.Counter()
        new_moderations = Moderation.objects.filter(moderator__isnull=True).values_list('basead__ad__user__agencies', 'basead__ad__xml_id')
        for agency_id, xml_id in new_moderations:
            if xml_id:
                new_ads_stats['import'] += 1
            if agency_id:
                new_ads_stats['agency'] += 1
            else:
                new_ads_stats['person'] += 1
            new_ads_stats['all'] += 1

        inactive_paid_ads = Ad.objects.filter(is_published=False).filter(
            Q(vip_type__gt=0) | Q(id__in=CatalogPlacement.get_active_user_ads())
        ).values_list('id', flat=True)

        extra_context.update(
            inactive_paid_ads=inactive_paid_ads,
            new_ads=new_ads_stats,
        )
        return super(ExtendedAdminSite, self).index(request, extra_context=extra_context)

extended_admin_site = ExtendedAdminSite()

admin.site = extended_admin_site
admin.sites.site = extended_admin_site

