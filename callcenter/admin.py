# coding: utf-8
from django.contrib import admin
from django.core.urlresolvers import reverse
from django.core.cache import cache

from callcenter.models import Call, ManagerCallRequest
from profile.admin import get_user_filter_link

class CustomerRelatedAdmin(admin.ModelAdmin):
    def display_user(self, obj):
        if obj.user1:
            html = get_user_filter_link(obj.user1)
            return html
        return ''
    display_user.allow_tags = True
    display_user.short_description = u"Пользователь"
    display_user.admin_order_field = 'user1'

    def display_user_services(self, obj):
        if not obj.user1:
            return ''

        info = []
        balance = sum([transaction.amount for transaction in obj.user1.transactions.all()])
        if balance:
            transactions_link =  '%s?user__exact=%s' % (reverse('admin:paid_services_transaction_changelist'), obj.user1_id)
            info.append(u'<a href="%s">остаток <b>%s</b> грн</a>' % (transactions_link, balance))

        plan = obj.user1.get_active_plan()
        if plan:
            plan_info_link = '%s?id=%s' % (reverse('admin:custom_user_user_changelist'), plan.id)
            info.append(u'<a href="%s" title="окончание %s">план <b>%s/%s</b> объявлений</abbr>'
                        % (plan_info_link, plan.end.strftime('%Y-%m-%d'), obj.user1.ads_count, plan.ads_limit))
        else:
            info.append(u'<abbr title="без активного плана"><b>%s/0</b> объявлений</abbr>' % obj.user1.ads_count)

        return ', '.join(info)
    display_user_services.allow_tags = True
    display_user_services.short_description = u'Услуги'

    def display_duration(self, obj):
        if obj.hang_up_time :
            return u'%.1f мин' % ((obj.hang_up_time - obj.call_time).seconds/60.0)
        else:
            return ''
    display_duration.short_description = u'длительность'


class CallAdmin(CustomerRelatedAdmin):
    list_display = ('id', 'call_time', 'callerid1', 'display_duration', 'display_user', 'display_user_services', )
    search_fields = ('callerid1', 'callerid2',)
    readonly_fields = ('call_time', 'answer_time', 'hang_up_time', 'callerid1', 'callerid2', 'uniqueid1', 'uniqueid2')
    date_hierarchy = 'call_time'
    raw_id_fields = ('user1', 'user2', )

    def get_queryset(self, request):
        return super(CallAdmin, self).get_queryset(request).prefetch_related('user1__transactions')


class ManagerFilter(admin.SimpleListFilter):
    title = u'менеджер'
    parameter_name = 'manager'
    # template = 'admin/filter_select.html'

    def lookups(self, request, model_admin):
        key = 'admin_filter_by_manager_in_callrequest'
        lookups_ = cache.get(key)
        if lookups_ is None:
            from profile.models import Manager
            lookups_ = [(manager.user_ptr_id, manager.get_public_name()) for manager in Manager.objects.all()]
            cache.set(key, lookups_, 3600*24)
        return lookups_

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(user2_id=self.value())

class ManagerCallRequestAdmin(CustomerRelatedAdmin):
    list_display = ('id', 'time', 'display_user', 'display_user_services', 'user2')
    readonly_fields = ('time', 'user1', 'user2')
    date_hierarchy = 'time'
    raw_id_fields = ('user1','user2')
    list_filter = (ManagerFilter,)

    def get_queryset(self, request):
        return super(ManagerCallRequestAdmin, self).get_queryset(request).prefetch_related('user1__transactions')


admin.site.register(Call, CallAdmin)
admin.site.register(ManagerCallRequest, ManagerCallRequestAdmin)
