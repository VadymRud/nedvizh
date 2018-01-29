# coding: utf-8
from django.contrib import admin
from django.core.urlresolvers import reverse
from django.db.models import Sum, Q
from django.core.cache import cache

from modeltranslation.admin import TranslationAdmin

from ad.filterspec import ProvinceRegionFilter
from ad.models import Region
from profile.admin import get_user_filter_link, StatManagerFilter
from paid_services.models import VipPlacement, CatalogPlacement, Transaction, TRANSACTION_TYPE_CHOICES, Plan, UserPlan, Order
from utils.admin_filters import SumFilter
from admin_ext.filters import make_datetime_filter

import datetime


class RegionFilter(ProvinceRegionFilter):
    parameter_name = 'user__region'

    def queryset(self, request, queryset):
        if self.value():
            region = Region.objects.get(pk=self.value())
            return queryset.filter(user__region__in=region.get_descendants(True))


# фильтр транзакций по пользователю
class UserFilter(admin.SimpleListFilter):
    title = u'по пользователю'
    parameter_name = 'user'

    def lookups(self, request, model_admin):
        return (
            ('person', u'частники'),
            ('agency', u'агентства'),
            ('developer', u'застройщики'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'person':
            return queryset.filter(user__agencies__isnull=True, user__developer__isnull=True)
        elif self.value() == 'agency':
            return queryset.filter(user__agencies__isnull=False, user__developer__isnull=True)
        elif self.value() == 'developer':
            return queryset.filter(user__agencies__isnull=True, user__developer__isnull=False)
        return queryset


class TypeFilter(admin.SimpleListFilter):
    title = u'по типу'
    parameter_name = 'type'
    plans_types = [11, 12, 32, 33]

    def lookups(self, request, model_admin):
        hidden_types = [5, 6, 9, 31, 51, 52, 61, 71, 81, 82, 91, 92] + self.plans_types
        return [type_
                for type_ in TRANSACTION_TYPE_CHOICES
                if (type_[0] not in hidden_types and u'возврат' not in type_[1])
                ] + [('plans', u'тарифы')]

    def queryset(self, request, queryset):

        if self.value():
            if self.value() == 'plans':
                return queryset.filter(Q(type__in=self.plans_types) | Q(corrected_transaction__type__in=self.plans_types))
            else:
                return queryset.filter( Q(type=self.value()) | Q(corrected_transaction__type=self.value()))


class RevertTypeFilter(admin.SimpleListFilter):
    title = u'транзакции'
    parameter_name = 'with_correction'

    def lookups(self, request, model_admin):
        return (
            ('yes', u'только возвраты'),
            ('no', u'спрятать возвраты'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(corrected_transaction__isnull=False)
        elif self.value() == 'no':
            return queryset.filter(corrected_transaction__isnull=True)


class MoneySumFilter(SumFilter):
    sum_field = 'amount'
    title = u'сумма, грн'


class PlanFilter(admin.SimpleListFilter):
    title = u'по тарифу'
    parameter_name = 'plan'

    def lookups(self, request, model_admin):
        cache_key = 'admin_plan_filter_lookups'
        items = cache.get(cache_key)
        if items is None:
            items = [(plan.id, plan.name) for plan in Plan.objects.all()]
            cache.set(cache_key, items, 3600 * 24)
        return items

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(user_plan__plan=self.value())


class ManagerFilter(StatManagerFilter):
    pass


class TransactionAdmin(admin.ModelAdmin):
    raw_id_fields = ('user', 'order', 'user_plan', 'corrected_transaction')
    list_display = ('id', 'time', 'user_link', 'amount', 'display_type', 'purchased', 'display_order', 'comment')
    list_display_links = ['id']
    readonly_fields = ('user', 'type', 'amount', 'time')
    list_filter = (ManagerFilter, TypeFilter, RevertTypeFilter, make_datetime_filter('time'), UserFilter, PlanFilter, RegionFilter, MoneySumFilter)
    actions = ('cancel',)

    def cancel(self, request, queryset):
        for transaction in queryset:
            if transaction.type == 11:
                transaction.user_plan.cancel(request.user)
            elif transaction.type in [53,54,55]:
                for placement in list(obj.vipplacements.all()) + list(obj.catalogplacements.all()):
                    placement.cancel(request.user)
            elif transaction.type in [84,85]:
                for call in transaction.paidcalls.all():
                    call.cancel(request.user)
            else:
                transaction.revert(comment=u'транзакция отменена %s' % request.user)
    cancel.short_description = u'Вернуть деньги'

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return []
        else:
            return super(TransactionAdmin, self).get_readonly_fields(request, obj)

    def get_queryset(self, request):
        qs = super(TransactionAdmin, self).get_queryset(request)
        return qs.prefetch_related('vipplacements', 'catalogplacements', 'order', 'user_plan', 'user', 'user__realtors__agency')

    def user_link(self, obj):
        return get_user_filter_link(obj.user)
    user_link.allow_tags = True
    user_link.short_description = u'пользователь'

    def display_type(self, obj):
        if obj.type == 100 and obj.corrected_transaction:
            return u'%s (коррекция)' % (obj.corrected_transaction.get_type_display())
        else:
            return obj.get_type_display()
    display_type.admin_order_field = 'type'
    display_type.short_description = u'тип'

    def purchased(self, obj):
        links = []
        related = list(obj.vipplacements.all()) + list(obj.catalogplacements.all())
        if obj.user_plan:
            related.append(obj.user_plan)

        for rel in related:
            url = reverse(
                'admin:paid_services_%s_changelist' % rel._meta.model_name) + '?id=%s' % rel.id
            links.append(u'<a href="%s">%s #%s</a>' % (url, rel._meta.verbose_name, rel.id))
        return u', '.join(links)

    purchased.allow_tags = True
    purchased.short_description = u'покупки'

    def display_order(self, obj):
        if obj.order:
            return '<a href="%s?id=%d">%d</a>' % (reverse('admin:paid_services_order_changelist'), obj.order_id, obj.order_id)
        else:
            return ''
    display_order.allow_tags = True
    display_order.short_description = u'заказ'


class ReadOnlyModelAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return []
        else:
            fields = [f.name for f in self.model._meta.local_fields]
            fields.remove('id')
            return fields


class VipPlacementAdmin(ReadOnlyModelAdmin):
    raw_id_fields = ('transaction', 'basead')
    list_display = ('id', 'user_link', 'property_link', 'days', 'since', 'until', 'transaction_link', 'is_active')
    list_filter = (make_datetime_filter('since'), make_datetime_filter('until'))
    actions = ('cancel',)

    def is_active(self, obj):
        return obj.is_active
    is_active.boolean = True

    def get_actions(self, request):
        actions = super(VipPlacementAdmin, self).get_actions(request)
        if not request.user.has_perm('paid_services.cancel_vipplacement'):
            del actions['cancel']
        return actions

    def get_queryset(self, request):
        qs = super(VipPlacementAdmin, self).get_queryset(request)
        return qs.prefetch_related('basead', 'basead__ad__user', 'basead__ad__user__realtors__agency', 'transaction')

    def user_link(self, obj):
        if obj.basead_id:
            return get_user_filter_link(obj.basead.ad.user, lookup='basead__ad__user__exact')
        else:
            return u'нет объявления'
    user_link.allow_tags = True
    user_link.short_description = u"Пользователь"
    user_link.admin_order_field = 'ad__user'

    def transaction_link(self, obj):
        return u'<a href="%s">#%s</a>' % (
        reverse('admin:paid_services_transaction_change', args=[obj.transaction_id]), obj.transaction_id)
    transaction_link.allow_tags = True
    transaction_link.short_description = u'транзакция'

    def lookup_allowed(self, key, value):
        if key in ('basead__ad__user', 'basead__ad__user__exact'):
            return True
        return super(VipPlacementAdmin, self).lookup_allowed(key, value)

    def property_link(self, obj):
        if obj.basead:
            return u'<a href="%s">#%s</a>' % (reverse('admin:ad_ad_change', args=[obj.basead_id]), obj.basead_id)
        else:
            return u'нет объявления'
    property_link.allow_tags = True
    property_link.short_description = u"Объявление"
    property_link.admin_order_field = 'ad'

    def cancel(self, request, queryset):
        cancelled = []
        errors = []
        for vip_placement in queryset.all():
            if datetime.datetime.now() < vip_placement.until:
                vip_placement.cancel(request.user)
                cancelled.append('#%d' % vip_placement.id)
            else:
                errors.append('#%d' % vip_placement.id)
        message = u'Отменено %d платных размещений %s' % (len(cancelled), ', '.join(cancelled))
        if errors:
            message += u', невозможно отменить %d платных размещений %s (уже закончились)' % (
                len(errors),
                ', '.join(errors)
            )
        self.message_user(request, message)
    cancel.short_description = u'Отмена платного размещения, возврат полной суммы на баланс'


class CatalogPlacementAdmin(VipPlacementAdmin):
    list_display = ('id', 'user_link', 'property_link', 'catalog', 'since', 'until', 'transaction_link', 'is_active')


class PlanAdmin(TranslationAdmin):
    list_display = ('name', 'ads_limit', 'update_interval', 'is_active')

class ActivePlanFilter(admin.SimpleListFilter):
    title = u'по пользователю'
    parameter_name = 'user'

    def lookups(self, request, model_admin):
        return [
            ('without-plans', u'без активого плана'),
            ('with-plans', u'с активным планом'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'without-plans':
            return queryset.exclude(user__in=UserPlan.objects.filter(end__gt=datetime.datetime.now(), is_active=True).values('user'))
        elif self.value() == 'with-plans':
            return queryset.filter(end__gt=datetime.datetime.now(), is_active=True)


class UserPlanAdmin(ReadOnlyModelAdmin):
    list_display = ('user_link', 'plan', 'display_used_limit', 'region', 'start', 'end')
    list_filter = ('plan', ManagerFilter, ActivePlanFilter, 'start', 'end', 'region')
    raw_id_fields = ('user', 'region')
    actions = ('cancel_with_payback', 'cancel')
    ordering = ['-id']

    def get_actions(self, request):
        actions = super(UserPlanAdmin, self).get_actions(request)
        if not request.user.has_perm('paid_services.cancel_userplan'):
            del actions['cancel_with_payback']
            del actions['cancel']
        return actions

    def get_list_display(self, request):
        list_display = list(super(UserPlanAdmin, self).get_list_display(request))
        if request.user.has_perm('paid_services.change_transaction'):
            list_display.append('transactions_link')
        if request.user.is_superuser:
            list_display.insert(0, 'id')
        return list_display

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return super(UserPlanAdmin, self).get_readonly_fields(request, obj)
        else:
            return list(set(
                [field.name for field in self.opts.local_fields] +
                [field.name for field in self.opts.local_many_to_many]
            ))

    def lookup_allowed(self, key, value):
        if key in ('transactions__amount',):
            return True
        return super(UserPlanAdmin, self).lookup_allowed(key, value)

    def get_queryset(self, request):
        return super(UserPlanAdmin, self).get_queryset(request).prefetch_related('region', 'user__realtors__agency', 'transactions')

    def user_link(self, obj):
        if obj.user:
            return get_user_filter_link(obj.user)
    user_link.allow_tags = True
    user_link.short_description = u'пользователь'

    def display_used_limit(self, obj):
        if not obj.ads_limit:
            return ''
        else:
            return '%s / %s' % (obj.user.ads_count, obj.ads_limit)
    display_used_limit.short_description = u'использовано'

    def transactions_link(self, obj):
        return u'<a href="%s?user_plan=%d">посмотреть</a>' % (reverse('admin:paid_services_transaction_changelist'), obj.id)
    transactions_link.allow_tags = True
    transactions_link.short_description = u'транзакции'

    def cancel(self, request, queryset, payback='partial'):
        cancelled = []
        errors = []
        for user_plan in queryset.all():
            if user_plan.is_active:
                user_plan.cancel(request.user, payback)
                cancelled.append('#%d' % user_plan.id)
            else:
                errors.append('#%d' % user_plan.id)
        message = u'Отменено %d тарифов %s' % (len(cancelled), ', '.join(cancelled))
        if errors:
            message += u', невозможно отменить %d тарифов %s (неактивны)' % (
                len(errors),
                ', '.join(errors)
            )
        self.message_user(request, message)
    cancel.short_description = u'Отмена тарифа с пересчетом денег'

    def cancel_with_payback(self, request, queryset):
        return self.cancel(request, queryset, payback='full')
    cancel_with_payback.short_description = u'Отмена тарифа с полным возвратом денег'


class OrderAdmin(ReadOnlyModelAdmin):
    list_display = ('id', 'time', 'user_link', 'amount', 'is_paid', 'transactions')
    list_filter = ('time', 'is_paid')
    raw_id_fields = ('user',)
    actions = ('execute',)

    def execute(self, request, queryset):
        for order in queryset.filter(is_paid=False):
            if order.user.get_balance(force=True) >= order.amount:
                order.execute()
    execute.short_description = u'Выполнить заказ'

    def get_queryset(self, request):
        qs = super(OrderAdmin, self).get_queryset(request)
        return qs.prefetch_related('transactions', 'user__realtors__agency')

    def user_link(self, obj):
        return get_user_filter_link(obj.user)
    user_link.allow_tags = True
    user_link.short_description = u'пользователь'


    def transactions(self, obj):
        if obj.transactions.all():
            return '<a href="%s?order=%d">%d</a>' % (reverse('admin:paid_services_transaction_changelist'),
                                                     obj.id, len(obj.transactions.all()))
        else:
            return ''
    transactions.allow_tags = True
    transactions.short_description = u'транзакции'


admin.site.register(Transaction, TransactionAdmin)
admin.site.register(VipPlacement, VipPlacementAdmin)
admin.site.register(CatalogPlacement, CatalogPlacementAdmin)
admin.site.register(Plan, PlanAdmin)
admin.site.register(UserPlan, UserPlanAdmin)
admin.site.register(Order, OrderAdmin)

