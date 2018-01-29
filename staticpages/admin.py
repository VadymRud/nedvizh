# coding: utf-8
from django import forms
from django.contrib import admin
from django.db.models import Q
from django.db import models
from modeltranslation.admin import TranslationAdmin
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from models import Article, FAQArticle, FAQCategory, SimplePage, ContentBlock
from guide.admin import SubdomainFilter


class ArticleForm(forms.ModelForm):
    def clean_slug(self):
        if Article.objects.filter(slug__iexact=self.cleaned_data['slug']).exclude(pk=self.instance.pk):
            raise forms.ValidationError('Поле часть URL-а не уникальна, попробуйте другой вариант')
        return self.cleaned_data['slug']
        
    def __init__(self, *args, **kwargs): 
        super(ArticleForm, self).__init__(*args, **kwargs) 
        self.fields['subdomains'].queryset = self.fields['subdomains'].queryset.order_by('name')

        for field in self.fields:
            if field.startswith('content_'):
                self.fields[field].widget = CKEditorUploadingWidget()
        
    class Meta:
        model = Article
        fields = '__all__'

class ArticleBySource(admin.SimpleListFilter):
    title = u'по источнику'
    parameter_name = 'source'

    def lookups(self, request, model_admin):
        return ( 
            ('agvego', u'advego.ru'),
            ('custom', u'добавленные вручную'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'agvego':
            return queryset.filter(xml_id__isnull=False)
        elif self.value() == 'custom':
            return queryset.filter(xml_id__isnull=True)
        else: 
            return queryset

class ArticleWithTranslate(admin.SimpleListFilter):
    title = u'по переводу'
    parameter_name = 'translated'

    def lookups(self, request, model_admin):
        return (
            ('uk', u'Без перевода на украинский'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'uk':
            return queryset.exclude(name_uk__gt='')
        else:
            return queryset

class ArticleSubdomainFilter(SubdomainFilter):
    def queryset(self, request, queryset):
        if self.value(): 
            return queryset.filter(Q(subdomains__isnull=True) | Q(subdomains=self.value()))

class ArticleAdmin(TranslationAdmin):
    form = ArticleForm
    list_display = ('__unicode__', 'published', 'subdomains_list', 'slug','visible', 'has_translate')
    list_filter = ['visible','category', ArticleBySource, ArticleWithTranslate, ArticleSubdomainFilter]
    filter_horizontal  = ['subdomains', 'related']
    search_fields = ['name','slug']

    def subdomains_list(self, obj):
        return ', '.join([region.name for region in obj.subdomains.order_by('name')])
    subdomains_list.admin_order_field = 'subdomains'
    subdomains_list.short_description = u'Поддомены (города)'

    def has_translate(self, obj):
        return admin.templatetags.admin_list._boolean_icon(bool(obj.name_uk))
    has_translate.short_description = u'Перевод'

admin.site.register(Article, ArticleAdmin)


class FAQCategoryAdmin(admin.ModelAdmin):
    exclude = ['title', 'seo_title', 'seo_description', 'seo_keywords']
    list_filter = ['is_published']
    list_display = ['title', 'order', 'is_published']
    list_editable = ['order', 'is_published']
    fieldsets = (
        (u'Основное [ru]', {
            'fields': ('title_ru',)
        }),
        (u'Основное [uk]', {
            'fields': ('title_uk',)
        }),
        (u'Настройки отображения', {
            'fields': ('slug', 'is_published', 'order'),
        }),
        (u'SEO', {
            'classes': ('collapse',),
            'fields': (
                ('seo_title_ru', 'seo_description_ru', 'seo_keywords_ru'),
                ('seo_title_uk', 'seo_description_uk', 'seo_keywords_uk')
            ),
        }),
    )

admin.site.register(FAQCategory, FAQCategoryAdmin)


class FAQArticleAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': CKEditorUploadingWidget},
    }
    exclude = ['title', 'seo_title', 'seo_description', 'seo_keywords', 'content', 'video']
    list_filter = ['is_published', 'category']
    list_display = ['title', 'category', 'order', 'is_published']
    list_editable = ['order', 'is_published']
    fieldsets = (
        (u'Основное [ru]', {
            'fields': ('title_ru', 'content_ru', 'video_ru')
        }),
        (u'Основное [uk]', {
            'fields': ('title_uk', 'content_uk', 'video_uk')
        }),
        (u'Настройки отображения', {
            'fields': ('category', 'slug', 'is_published', 'order'),
        }),
        (u'SEO', {
            'classes': ('collapse',),
            'fields': (
                ('seo_title_ru', 'seo_description_ru', 'seo_keywords_ru'),
                ('seo_title_uk', 'seo_description_uk', 'seo_keywords_uk')
            ),
        }),
    )

admin.site.register(FAQArticle, FAQArticleAdmin)


class SimplePageAdmin(TranslationAdmin):
    list_display = ('url', 'urlconf', 'title')
    list_filter = ('urlconf',)
    formfield_overrides = {
        models.TextField: {'widget': CKEditorUploadingWidget},
    }


class ContentBlockAdmin(TranslationAdmin):
    list_display = ('name',)
    formfield_overrides = {
        models.TextField: {'widget': CKEditorUploadingWidget},
    }


admin.site.register(SimplePage, SimplePageAdmin)
admin.site.register(ContentBlock, ContentBlockAdmin)

