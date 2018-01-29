# coding: utf-8

from django.shortcuts import render
from django.contrib import admin
from django.conf.urls import url
from django.utils import translation
from django.forms import TextInput
from django.db import models
from django import forms
from ckeditor.widgets import CKEditorWidget


from seo.models import TextBlock, SEORule


class TextBlocAdminForm(forms.ModelForm):
    text = forms.CharField(widget=CKEditorWidget(), label=u'Текст блока', required=False)


class TextBlockAdmin(admin.ModelAdmin):
    form = TextBlocAdminForm
    list_display = ('url', 'title', 'region', 'id')
    search_fields = ('url', 'title')
    readonly_fields = ('region',)
    ordering = ['url']


admin.site.register(TextBlock, TextBlockAdmin)


class SEORuleAdmin(admin.ModelAdmin):
    list_display = ['__unicode__', 'deal_type', 'subpage', 'region_kind', 'property_type']
    list_filter = ['deal_type', 'subpage', 'region_kind', 'property_type', 'check_rooms']
    exclude = ['crosslink_header', 'h1', 'title', 'keywords', 'description']

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'200'})},
    }

    def get_urls(self):
        urls = super(SEORuleAdmin, self).get_urls()
        return [ url(r'^find_rules/$', self.find_rules_by_url), ] + urls

    def find_rules_by_url(self, request):
        url = request.GET.get('url')

        if url:
            from ad.models import Region
            url_data = Region.get_region_and_params_from_url(url)

            deal_type = url_data['kwargs'].get('deal_type', 'index')
            property_type = url_data['kwargs'].get('property_type', 'default')
            region = url_data['region'] or url_data['subdomain_region']
            rooms = url_data['GET'].get('rooms', None)
            subway = url_data['GET'].get('subway', None)

            subpage = url_data['view'].__name__
            if subpage  == 'search':
                subpage = 'default'

            # устанавлием язык запрашиваемой страницы
            translation.activate(url_data['language'])

            # получаем список подходящих правил и словарь метатегов
            rules, seo = SEORule.get_suitable_rules(region, deal_type, property_type, subpage, rooms, subway)

            # возвращаем язык админки
            translation.activate(request.LANGUAGE_CODE)

        return render(request, "admin/seo/find_rules.html", locals())


admin.site.register(SEORule, SEORuleAdmin)
