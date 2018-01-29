# coding: utf-8
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.core.cache import cache
from django.core.urlresolvers import reverse

from custom_user.models import User
from agency.models import Agency, Realtor, Lead, Task, LeadHistoryEvent


class RealtorInline(admin.TabularInline):
    model = Realtor
    fields = ('user_link', 'is_admin', 'is_active')
    readonly_fields = fields

    def get_queryset(self, request):
        return super(RealtorInline, self).get_queryset(request).prefetch_related('user', 'user__agencies')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def user_link(self, obj):
        return u'<a href="%s?id=%d">%s</a>' % (
            reverse('admin:custom_user_user_changelist'),
            obj.user.id,
            obj.user
        )
    user_link.allow_tags = True
    user_link.short_description = u'пользователь'


class PublishingTypeFilter(SimpleListFilter):
    title = u'вид размещения'
    parameter_name = 'publishing'

    def lookups(self, request, model_admin):
        return (
            ('plan_ppk', u'тариф или ППК'),
            ('plan', u'тариф'),
            ('ppk', u'ППК'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'plan':
            return queryset.filter(users__in=User.get_user_ids_with_active_plan())
        elif self.value() == 'ppk':
            return queryset.filter(users__in=User.get_user_ids_with_active_ppk()).distinct()
        elif self.value() == 'plan_ppk':
            ids = set(User.get_user_ids_with_active_plan()) | set(User.get_user_ids_with_active_ppk())
            return queryset.filter(users__in=ids).distinct()

        return queryset


class RealtorAdmin(admin.ModelAdmin):
    raw_id_fields = ('user', 'agency')
    list_display = ('user', 'agency', 'is_active', 'is_admin')
    list_filter = ('is_active', 'is_admin')


class AgencyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'display_asnu_number', 'display_publishing_type',  'display_realtors', 'display_import')
    list_filter = (PublishingTypeFilter,)
    raw_id_fields = ('city',)
    search_fields = ('name',)
    show_full_result_count = False
    inlines = (RealtorInline,)
    readonly_fields = ('city_text',)

    def get_queryset(self, request):
        return super(AgencyAdmin, self).get_queryset(request).prefetch_related('realtors__user', 'realtors__user__user_plans',
                                                                               'realtors__user__activityperiods',)

    def display_asnu_number(self, obj):
        result = obj.asnu_number
        if obj.asnu_number:
            valid_asnu_numbers = cache.get('valid_asnu_numbers')
            if valid_asnu_numbers is not None and obj.asnu_number.replace('-', '') in valid_asnu_numbers:
                result += u' (проверен)'
            return result
    display_asnu_number.allow_tags = True
    display_asnu_number.short_description = u'в базе АСНУ'

    def display_publishing_type(self, obj):
        links = []
        for realtor in obj.get_realtors_using_prefetch():
            active_plan = realtor.user.get_active_plan_using_prefetch()
            if active_plan:
                links.append(u'<a href="%s?id=%d">тариф-%d</a>' %  (
                    reverse('admin:paid_services_userplan_changelist'),
                    active_plan.pk, active_plan.ads_limit)
                )

            ppc_periods = [period for period in realtor.user.activityperiods.all() if not period.end]
            if ppc_periods:
                links.append(u'<a href="%s?user=%d">ППК-%d</a>' %  (
                    reverse('admin:ppc_activityperiod_changelist'),
                    realtor.user.id, ppc_periods[0].user.leadgeneration.ads_limit)
                )

        return u' / '.join(links)
    display_publishing_type.allow_tags = True
    display_publishing_type.short_description = u'размещение'

    def display_realtors(self, obj):
        return u'<a href="%s?agencies=%s">%s шт</a>' % (reverse('admin:custom_user_user_changelist'), obj.id, obj.realtors.count())
    display_realtors.allow_tags = True
    display_realtors.short_description = u'Риелторы'

    def display_import(self, obj):
        if obj.import_url:
            return u'<a href="%s" target="_blank">фид</a>, <a href="%s?agency=%d">логи</a>' % \
                   (obj.import_url, reverse('admin:import__importtask_changelist'), obj.id)
        return ''
    display_import.allow_tags = True
    display_import.short_description = u'Импорт'

class LeadAdmin(admin.ModelAdmin):
    list_display = ('id', '__unicode__', 'client', 'user', 'label', 'basead')
    raw_id_fields = ('client', 'user', 'basead')
    list_filter = ('label',)

class LeadHistoryEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'time', 'user_link', 'lead', 'event', 'object')
    raw_id_fields = ('lead',)

    def lookup_allowed(self, key, value):
        if key in ('lead__user',):
            return True
        return super(LeadHistoryEventAdmin, self).lookup_allowed(key, value)

    def get_queryset(self, request):
        return super(LeadHistoryEventAdmin, self).get_queryset(request).prefetch_related('lead')

    def user_link(self, obj):
        return u'<a href="?lead__user={}">{}</a>'.format(obj.lead.user.id, obj.lead.user)
    user_link.allow_tags = True
    user_link.short_description = u'пользователь'

class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'lead', 'start', 'user', 'basead')
    raw_id_fields = ('user', 'basead')
    date_hierarchy = 'start'

    def get_queryset(self, request):
        return super(TaskAdmin, self).get_queryset(request).select_related('lead__user', 'basead', 'user')


admin.site.register(Agency, AgencyAdmin)
admin.site.register(Realtor, RealtorAdmin)
admin.site.register(Lead, LeadAdmin)
admin.site.register(LeadHistoryEvent, LeadHistoryEventAdmin)
admin.site.register(Task, TaskAdmin)

