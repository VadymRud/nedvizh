# coding: utf-8
from django.contrib import admin
from django.core.urlresolvers import reverse
from django.db import models
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from models import Webinar, Speaker, WebinarReminder, SeminarPhoto, SeminarVideo


def make_copy(modeladmin, request, queryset):
    for qs in queryset:
        qs.id = None
        qs.pk = None
        qs.title_ru += u' (Копия)'
        qs.slug = None
        qs.emails_sent = 0
        qs.save()

make_copy.short_description = u'Создать копию выделенных вебинаров/семинаров'


class SeminarPhotoInline(admin.TabularInline):
    model = SeminarPhoto
    extra = 5


class SeminarVideoInline(admin.TabularInline):
    model = SeminarVideo
    extra = 2


@admin.register(Webinar)
class WebinarAdmin(admin.ModelAdmin):
    def _people_amount(self, obj):
        return u'<a href="%s?webinar__exact=%s">Участники (%s)</a>' % (
            reverse('admin:webinars_webinarreminder_changelist'), obj.id, obj.reminders.all().count()
        )

    _people_amount.short_description = u'Кол-во участников'
    _people_amount.allow_tags = True

    formfield_overrides = {
        models.TextField: {'widget': CKEditorUploadingWidget},
    }

    filter_horizontal = ['speakers']
    list_display = [
        'title_ru', 'status', 'emails_sent', 'city_ru', 'start_at', 'finish_at', 'is_published', '_people_amount']
    list_filter = ['is_published', 'type', 'is_registration_available', 'status']
    readonly_fields = ['youtube_views_count', 'emails_sent']
    exclude = ['title', 'teaser', 'address', 'description', 'seo_title', 'seo_description', 'seo_keywords', 'city']
    actions = [make_copy]
    inlines = [SeminarVideoInline, SeminarPhotoInline]
    date_hierarchy = 'start_at'
    ordering = ['-start_at']
    raw_id_fields = ['region']


@admin.register(Speaker)
class SpeakerAdmin(admin.ModelAdmin):
    list_display = ['name_ru']
    exclude = ['name', 'title']


@admin.register(WebinarReminder)
class WebinarReminderAdmin(admin.ModelAdmin):
    list_display = ['webinar', 'user', 'name', 'email', 'phone', 'city', 'is_sent_email', 'is_sent_sms']
    readonly_fields = ['webinar', 'user', 'name', 'email', 'phone', 'city', 'is_sent_email', 'is_sent_sms']
    list_filter = ['is_sent_email', 'is_sent_sms']
