# coding=utf-8
from urlparse import urlparse

import datetime
from django.contrib import admin

from ad import filterspec as fs
from ad.admin import icon_website
from ad.choices import MODERATION_STATUS_CHOICES, STATUS_CHOICES
from newhome.models import (
    Newhome, Developer, Floor, Flat, Layout, LayoutFlat, Building, Room, Progress, ProgressPhoto, Moderation, LayoutNameOption)
from profile.admin import get_user_filter_link


# закрываем заявку на модерацию и очищаем список полей, требующих проверки
def approve_ads(modeladmin, request, queryset, new_status=None):
    queryset.update(fields_for_moderation=None, is_published=True)

    now = datetime.datetime.now()
    update_fields = {'moderator': request.user, 'end_time': now}
    if new_status:
        update_fields['new_status'] = new_status

    for newhome in queryset:
        updated_rows = newhome.newhome_moderations.filter(moderator__isnull=True).update(**update_fields)
        if not updated_rows:
            Moderation.objects.create(
                newhome=newhome, start_time=now, end_time=now, moderator=request.user, new_status=new_status)

approve_ads.short_description = u'Подтвердить (снять отметку о модерации)'


def reject_action_factory(short_description, status):
    def reject_action(modeladmin, request, queryset):
        # при статусе модерации >= 20 объявления не возвращаются на модерацию и соответственно к публикации
        if status >= 20:
            queryset.update(moderation_status=status, status=210, is_published=False)

        else:
            queryset.update(moderation_status=status, is_published=False)

        approve_ads(modeladmin, request, queryset, new_status=status)

        for user in set(ad.user for ad in queryset):
            if user:
                user.update_ads_count()

    reject_action.short_description = short_description
    reject_action.__name__ = 'reject_action_with_status_%d' % status
    return reject_action

wrong_ad_actions = []
for status in (10, 11, 12, 13, 14, 15, 16, 20, 22):
    short_description = u'Отклонить: %s' % dict(MODERATION_STATUS_CHOICES)[status]
    action = reject_action_factory(short_description, status)
    wrong_ad_actions.append(action)


def change_status_factory(short_description, status):
    def change_status(modeladmin, request, queryset):
        queryset.update(status=status)
        if status == 1:
            queryset.filter(moderation_status=None).update(is_published=True)

        else:
            queryset.update(is_published=False)

    change_status.short_description = short_description
    change_status.__name__ = 'change_status_status_%d' % status
    return change_status


change_status_actions = []
for status in (1, 210, 211):
    short_description = u'Сменить статус: %s' % dict(STATUS_CHOICES)[status]
    change_status_actions.append(change_status_factory(short_description, status))


def update_region(modeladmin, request, queryset):
    for ad in queryset:
        old_region = ad.region
        ad.process_address()
        if old_region != ad.region:
            ad.save()
update_region.short_description = u'Обновить присвоенный регион'


@admin.register(LayoutNameOption)
class LayoutNameOptionAdmin(admin.ModelAdmin):
    search_fields = ['name']
    fields = ['name_ru', 'name_uk']


@admin.register(Newhome)
class NewhomeAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_link', 'name', 'status', 'moderation_status')
    search_fields = ['id', 'name', 'developer', 'seller', 'content', 'user__email', 'priority_email']
    raw_id_fields = ['user', 'region', 'priority_phones']
    exclude = ['phones', 'created', 'newhome_type', 'geo_source', 'address', 'fields_for_moderation', 'name',
               'keywords', 'developer', 'seller']
    list_filter = (
        'status', 'moderation_status', fs.CityRegionFilter, fs.ProvinceRegionFilter
    )
    actions = [approve_ads, update_region] + change_status_actions + wrong_ad_actions
    date_hierarchy = 'created'

    def get_queryset(self, request):
        qs = super(NewhomeAdmin, self).get_queryset(request)
        return qs.select_related('region').prefetch_related('user', 'user__realtors__agency')

    def user_link(self, obj):
        if obj.user:
            html = get_user_filter_link(obj.user)
            return html
        else:
            o = urlparse(obj.source_url)
            return u'<nobr><a href="?source_url__icontains=%s" title="фильтровать по адресу сайта">%s %s</a></nobr>' % (o.netloc, icon_website, o.netloc)

    user_link.allow_tags = True
    user_link.short_description = u"Источник/Юзер"
    user_link.admin_order_field = 'source_url'


class LayoutFlatInline(admin.TabularInline):
    model = LayoutFlat
    raw_id_fields = ['floor', 'layout',]


class FloorAdmin(admin.ModelAdmin):
    search_fields = ['newhome__name']
    list_display = ('id', 'name', 'newhome')
    filter_horizontal = ['layouts']
    raw_id_fields = ['newhome', 'section', 'building', 'layouts']
    inlines = [LayoutFlatInline]


class RoomInline(admin.TabularInline):
    model = Room


class LayoutAdmin(admin.ModelAdmin):
    search_fields = ['newhome__name']
    list_display = ('id', 'name', 'newhome', 'area', 'rooms_total')
    inlines = [RoomInline]
    raw_id_fields = ['newhome', 'section', 'building', 'basead']



class LayoutFlatAdmin(admin.ModelAdmin):
    list_display = ('id',  'floor', 'layout', 'price')
    raw_id_fields = ['floor', 'layout',]


class FlatAdmin(admin.ModelAdmin):
    list_display = ('id', 'newhome', 'floor', 'layout', 'is_available')


class FlatInline(admin.TabularInline):
    model = Flat
    fields = ('floor', 'is_available', 'price')


class BuildingAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'newhome')


class ProgressPhotoAdmin(admin.ModelAdmin):
    list_display = ('id', 'progress')


class PhogressPhotoInline(admin.TabularInline):
    model = ProgressPhoto
    fields = ('image',)


class ProgressAdmin(admin.ModelAdmin):
    list_display = ('id', 'newhome', 'name', 'date')
    inlines = (PhogressPhotoInline,)


class DeveloperAdmin(admin.ModelAdmin):
    raw_id_fields = ['user', 'city']
    list_display = ['user_id', 'name', 'city']


admin.site.register(Floor, FloorAdmin)
admin.site.register(Layout, LayoutAdmin)
admin.site.register(LayoutFlat, LayoutFlatAdmin)
admin.site.register(Building, BuildingAdmin)
admin.site.register(Flat, FlatAdmin)
admin.site.register(Progress, ProgressAdmin)
admin.site.register(ProgressPhoto, ProgressPhotoAdmin)
admin.site.register(Developer, DeveloperAdmin)
