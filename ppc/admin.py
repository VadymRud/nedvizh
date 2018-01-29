# coding: utf-8
from django.contrib import admin
from django.db.models import Q
from django.core.urlresolvers import reverse
from django.contrib.admin import SimpleListFilter

from ad.filterspec import ProvinceRegionFilter
from ppc.models import Call, CallRequest, ProxyNumber, LeadGeneration, Bonus, ActivityPeriod, Review
from profile.admin import get_user_filter_link, StatManagerFilter
from custom_user.admin import IPAddressFilter
from admin_ext.filters import make_datetime_filter
from utils.admin_filters import SumFilter

"""
    Filters
"""


class IsActiveFilter(SimpleListFilter):
    title = u'активность периодов'
    parameter_name = 'is_active'

    def lookups(self, request, model_admin):
        return (
            ('yes', u'активны'),
            ('no', u'завершены'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(end__isnull=True)
        if self.value() == 'no':
            return queryset.filter(end__isnull=False)
        return queryset

class NumberTypeFilter(SimpleListFilter):
    title = u'тип номеров'
    parameter_name = 'numbers'

    def lookups(self, request, model_admin):
        return (
            ('ringostat-dedicated', u'мобильные: выделенные'),
            ('ringostat-shared', u'мобильные: общие'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'ringostat-dedicated':
            return queryset.filter(user__leadgeneration__dedicated_numbers=True)
        elif self.value() == 'ringostat-shared':
            return queryset.filter(user__leadgeneration__dedicated_numbers=False)

class ProxyNumberStatusFilter(SimpleListFilter):
    title = u'статус'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (
            ('active', u'активны'),
            ('hold', u'заморожены'),
            ('free', u'свободны'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(Q(user__isnull=False, hold_until=None) | Q(is_shared=True))
        elif self.value() == 'hold':
            return queryset.filter(hold_until__isnull=False)
        elif self.value() == 'free':
            return queryset.filter(user=None, hold_until=None, is_shared=False)
        return queryset


class PaidRequestFilter(SimpleListFilter):
    title = u'платный'
    parameter_name = 'paid'

    def lookups(self, request, model_admin):
        return (
            ('yes', u'да'),
            ('no', u'нет'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(transaction__isnull=False)
        if self.value() == 'no':
            return queryset.filter(transaction__isnull=True)
        return queryset


class RequestTypeFilter(SimpleListFilter):
    title = u'тип объекта'
    parameter_name = 'type'

    def lookups(self, request, model_admin):
        return (
            ('ad', u'объявление'),
            ('newhome', u'новостройка'),
            ('search', u'поиск'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'ad':
            return queryset.filter(content_type__model='ad')
        elif self.value() == 'newhome':
            return queryset.filter(content_type__model='newhome')
        elif self.value() == 'search':
            return queryset.filter(content_type__model='savedsearch')
        return queryset


class CallRequestIPAddressFilter(IPAddressFilter):
    lookup = 'ip__in'


class CallProxyNumberFilter(SimpleListFilter):
    title = u'номер переадресации'
    parameter_name = 'provider'

    def lookups(self, request, model_admin):
        return [
            ('local', u'городские'),
            ('ringostat', u'мобильные все'),
            ('dedicated', u'мобильные выделенные'),
            ('shared', u'мобильные общие'),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value in ('local', 'ringostat'):
            queryset = queryset.filter(proxynumber__provider=value)
        elif value == 'dedicated':
            queryset = queryset.filter(proxynumber__provider='ringostat', proxynumber__is_shared=False)
        elif value == 'shared':
            queryset = queryset.filter(proxynumber__provider='ringostat', proxynumber__is_shared=True)

        return queryset


class PaidCallFilter(SimpleListFilter):
    title = u'тип звонка'
    parameter_name = 'type'

    def lookups(self, request, model_admin):
        return (
            ('unique', u'уникальные/платные'),
            ('noanswer', u'неотвеченные'),
            ('nouser', u'без ввода ID'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'unique':
            return queryset.filter(transaction__amount__lt=0)
        elif self.value() == 'noanswer':
            return queryset.filter(callerid2='')
        elif self.value() == 'nouser':
            return queryset.filter(user2__isnull=True)
        return queryset


def make_userprovince_filter(field_):
    class UserProvinceFilter(ProvinceRegionFilter):
        title = u'область пользователя'
        parameter_name = 'province'
        def queryset(self, request, queryset):
            if self.value():
                return queryset.filter(**{field_:self.value()})
    return UserProvinceFilter


class TransactionSumFilter(SumFilter):
    sum_field = 'transaction__amount'
    title = u'сумма, грн'


"""
    ModelAdmin
"""

class CallAdmin(admin.ModelAdmin):
    list_display = ('id', 'call_time', 'callerid1', 'callerid2', 'user2_link', 'transaction_display', 'deal_type', 'complaint', 'recordingfile_link')
    list_filter = ('complaint', 'deal_type', PaidCallFilter, make_datetime_filter('call_time'), CallProxyNumberFilter,
                  'proxynumber__mobile_operator','proxynumber__traffic_source', make_userprovince_filter('user2__region'),
                   TransactionSumFilter)
    raw_id_fields = ('user1', 'user2', 'transaction')
    date_hierarchy = 'call_time'
    actions = ('cancel',)

    def get_queryset(self, request):
        return super(CallAdmin, self).get_queryset(request)\
            .prefetch_related('user2__realtors__agency', 'user2__leadgenerationbonuses', 'transaction')

    def cancel(self, request, queryset):
        for call in queryset:
            call.cancel(request.user)
    cancel.short_description = u'Возврат денег за звонок'

    def user2_link(self, obj):
        return get_user_filter_link(obj.user2, 'user2__exact')
    user2_link.allow_tags = True
    user2_link.short_description = u'пользователь'

    def recordingfile_link(self, obj):
        if obj.duration:
            duration_str = u'%.1f мин' % (obj.duration/60.0)
        else:
            duration_str = u''

        if obj.recordingfile:
            return u'<a href="%s">%s</a>' % (obj.recordingfile.url, duration_str)
        else:
            return duration_str
    recordingfile_link.allow_tags = True
    recordingfile_link.short_description = u'Запись'

    def transaction_display(self, obj):
        if obj.transaction:
            if obj.transaction.amount == 0:
                for bonus in obj.user2.leadgenerationbonuses.all():
                    if bonus.start < obj.call_time and (not bonus.end or obj.call_time < bonus.end):
                        return u'бонус'
                return u'0 грн'
            else:
                return u'%s грн' % int(-obj.transaction.amount)
    transaction_display.short_description = u'цена'


class CallRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'time', 'get_user1', 'user2_link', 'transaction_display', 'get_object_display',
                    'name', 'email', 'phone', 'traffic_source')
    raw_id_fields = ('user1', 'user2', 'transaction')
    list_filter = (RequestTypeFilter, PaidRequestFilter, make_datetime_filter('time'), CallRequestIPAddressFilter,
                   'traffic_source', make_userprovince_filter('user2__region'), TransactionSumFilter)
    date_hierarchy = 'time'

    def get_queryset(self, request):
        return super(CallRequestAdmin, self).get_queryset(request)\
            .prefetch_related('transaction', 'user2__realtors__agency')

    def get_user1(self, obj):
        return u' '.join(map(unicode, filter(None, [obj.user1, obj.ip])))
    get_user1.allow_tags = True
    get_user1.short_description = u'отравитель'
    get_user1.admin_order_field = u'user1'

    def user2_link(self, obj):
        return get_user_filter_link(obj.user2, 'user2__exact')
    user2_link.allow_tags = True
    user2_link.short_description = u'получатель'
    user2_link.admin_order_field = u'user2'

    def get_object_display(self, obj):
        model_name = obj.content_type.model
        obj_type = {'ad':u'Объявл', 'newhome':u'Новостр', 'savedsearch':u'Поиск'}.get(model_name, 'прочее')
        if obj.object:
            if model_name in ['ad', 'newhome']:
                return '%s: <a href="%s">%s</a>' % (obj_type, obj.object.get_absolute_url(), obj.object)
            elif model_name == 'savedsearch':
                return '%s: <a href="%s">%s</a>' % (obj_type, obj.object.get_full_url(), obj.object)

        return '%s: %s' % (obj_type, obj.object)
    get_object_display.allow_tags = True
    get_object_display.short_description = u'объект'

    def transaction_display(self, obj):
        if obj.transaction:
            if obj.transaction.amount == 0:
                return u'бонус'
            else:
                return u'%s грн' % int(-obj.transaction.amount)
    transaction_display.short_description = u'цена'


class ProxyNumberAdmin(admin.ModelAdmin):
    list_display = ('id', 'number', 'provider', 'mobile_operator', 'is_shared', 'is_active', 'region', 'user_link', 'deal_type', 'hold_until')
    list_filter = ('deal_type', 'provider', 'mobile_operator', 'is_shared', ProxyNumberStatusFilter, 'traffic_source',
                   make_userprovince_filter('user__region'))
    raw_id_fields = ('user', )
    actions = ('release_number',)

    def release_number(self, request, queryset):
        for proxynumber in queryset:
            proxynumber.release()
    release_number.short_description = u'Освободить номер'

    def is_active(self, obj):
        return obj.is_shared or (
            obj.user is not None and not obj.hold_until and (
                (bool(obj.user.has_active_leadgeneration('newhomes')) and obj.deal_type == 'newhomes') or
                (bool(obj.user.has_active_leadgeneration('ads')) and obj.deal_type != 'newhomes')
            )
        )
    is_active.boolean = True
    is_active.allow_tags = True
    is_active.short_description = u'актвн'

    def user_link(self, obj):
        return get_user_filter_link(obj.user)
    user_link.allow_tags = True
    user_link.short_description = u'пользователь'


class LeadGenerationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_link', 'display_balance', 'is_active_ads', 'is_active_newhomes', 'periods', 'call',
                    'callrequest', 'phones', 'bonus')
    list_filter = ('is_active_ads', 'is_active_newhomes', StatManagerFilter)
    raw_id_fields = ('user', )
    readonly_fields = ('worktime', )

    def get_queryset(self, request):
        return super(LeadGenerationAdmin, self).get_queryset(request)\
            .prefetch_related('user__callrequests_to', 'user__answered_ppc_calls',  'user__leadgenerationbonuses',
                              'user__realtors__agency', 'user__activityperiods', 'user__proxynumbers')

    def display_balance(self, obj):
        # попытка использовать join с таблицей транзакций и sum кладет базу, поэтому так
        balance = obj.user.get_balance()
        return u'<a title="Показать транзакции пользователя" href="%s?userexact=%d">%s</a>' % (
            reverse('admin:paid_services_transaction_changelist'), obj.user.id, balance
        )
    display_balance.allow_tags = True
    display_balance.short_description = u'Баланс'

    def periods(self, obj):
        return u'<a href="{}?user={}">{}</a>'.format(
            reverse('admin:ppc_activityperiod_changelist'), obj.user_id,
            obj.user.activityperiods.count() or '')
    periods.allow_tags = True
    periods.short_description = u'периоды'

    def user_link(self, obj):
        return get_user_filter_link(obj.user)
    user_link.allow_tags = True
    user_link.short_description = u'пользователь'

    def bonus(self, obj):
        return u'<a href="{}?user={}">{}</a>'.format(
            reverse('admin:ppc_bonus_changelist'), obj.user_id,
            obj.user.leadgenerationbonuses.count() or '-')
    bonus.allow_tags = True
    bonus.short_description = u'бонусы'

    def call(self, obj):
        return '<a href="%s?user2=%d">%s</a>' % (
        reverse('admin:ppc_call_changelist'), obj.user_id, obj.user.answered_ppc_calls.count() or '-')
    call.short_description = u'звонков'
    call.allow_tags = True

    def callrequest(self, obj):
        return '<a href="%s?user2=%d">%s</a>' % (reverse('admin:ppc_callrequest_changelist'), obj.user_id, obj.user.callrequests_to.count() or '-')
    callrequest.short_description = u'лидов'
    callrequest.allow_tags = True

    def phones(self, obj):
        return '<a href="%s?user=%d">%s</a>' % (reverse('admin:ppc_proxynumber_changelist'), obj.user_id, obj.user.proxynumbers.count() or '-')
    phones.short_description = u'телефонов'
    phones.allow_tags = True


class ActivityPeriodAdmin(admin.ModelAdmin):
    list_display = ('id', 'lead_type', 'user_link', 'start', 'display_status', 'get_calls', 'get_requests', 'get_numbers')
    list_filter = ('lead_type', IsActiveFilter, make_datetime_filter('start'), make_datetime_filter('end'), NumberTypeFilter, StatManagerFilter,
                   make_userprovince_filter('user__region'))
    raw_id_fields = ('user', )

    def get_queryset(self, request):
        return super(ActivityPeriodAdmin, self).get_queryset(request)\
            .prefetch_related('user__callrequests_to', 'user__proxynumbers', 'user__answered_ppc_calls',
                              'user__realtors__agency', 'user__transactions', 'user__leadgeneration')

    def get_calls(self, obj):
        if obj.end:
            return obj.calls
        else:
            return len([call for call in obj.user.answered_ppc_calls.all() if call.call_time > obj.start])
    get_calls.short_description = u'звонков'

    def get_requests(self, obj):
        if obj.end:
            return obj.requests
        else:
            return len([callrequest for callrequest in obj.user.callrequests_to.all() if callrequest.time > obj.start])
    get_requests.short_description = u'запросов'

    def get_numbers(self, obj):
        if obj.end:
            return obj.numbers
        else:
            return obj.user.proxynumbers.count()
    get_numbers.short_description = u'телефонов'

    def user_link(self, obj):
        return get_user_filter_link(obj.user)
    user_link.allow_tags = True
    user_link.short_description = u'пользователь'

    def display_status(self, obj):
        if  obj.end:
            return u"завершено %s" % obj.end.strftime("%Y-%m-%d %H:%M")
        else:
            result = [u"мобильные"]
            if not obj.user.leadgeneration.dedicated_numbers:
                result.append(u"общий")
            else:
                result.append(u"выделенный" if obj.user.has_paid_dedicated_numbers() else u"нет оплаты за выделенный")

            balance = int(sum([t.amount for t in obj.user.transactions.all()]))
            result.append(u'баланс <a title="Показать транзакции пользователя" href="%s?user__exact=%d">%s грн</a>' % (
                reverse('admin:paid_services_transaction_changelist'), obj.user.id, balance
            ))
            return u" / ".join(result)
    display_status.allow_tags = True
    display_status.short_description = u'Статус'


class BonusAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_link', 'start', 'end')
    raw_id_fields = ('user', )

    def user_link(self, obj):
        return get_user_filter_link(obj.user)
    user_link.allow_tags = True
    user_link.short_description = u'пользователь'


class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'company')


admin.site.register(Call, CallAdmin)
admin.site.register(CallRequest, CallRequestAdmin)
admin.site.register(ProxyNumber, ProxyNumberAdmin)
admin.site.register(LeadGeneration, LeadGenerationAdmin)
admin.site.register(ActivityPeriod, ActivityPeriodAdmin)
admin.site.register(Bonus, BonusAdmin)
admin.site.register(Review, ReviewAdmin)
