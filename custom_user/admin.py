# coding: utf-8
from django.contrib import admin
from django.shortcuts import render, redirect
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.models import Group
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.conf.urls import url
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.templatetags.static import static
from django.utils.safestring import mark_safe
from django.db.models import Sum, Count, F, Q
from django.db import transaction
from django import forms

from custom_user.models import User, UserPhone
from profile.models import Manager
from agency.models import Agency, Realtor

from ad.phones import PhoneModelChoiceField, pprint_phone
from ad.filterspec import ProvinceRegionFilter, M2MPhoneFilter, IPAddressFilter
from profile.models import get_banned_users
from paid_services.models import Plan, UserPlan, Transaction, FILTER_USER_BY_PLAN_CHOICES, filter_user_by_plan
from utils.admin_filters import SumFilter
from admin_ext.filters import make_datetime_filter

import datetime

class UserField(forms.CharField):
    def clean(self, value):
        try:
            if value.isnumeric():
                return User.objects.get(pk=value)
            else:
                return User.objects.get(email__iexact=value)
        except User.DoesNotExist:
            raise forms.ValidationError(u'У нас нет такого пользователя')
        except User.MultipleObjectsReturned:
            raise forms.ValidationError(u'Два пользователя с таким e-mail')

class PhoneInlineForm(forms.ModelForm):
    # TODO: здесь нужно подключить новое форматирование номеров
    # class Media:
    #     js = ['js/libs/jquery-last.min.js'] + list(form_media_js)

    phone = PhoneModelChoiceField(label=u'Номер телефона', queryset=UserPhone.objects.none())

class PhoneInlineFormset(forms.models.BaseInlineFormSet):
    def clean(self):
        for form in self.forms:
            if 'phone' in form.cleaned_data:
                phone = form.cleaned_data['phone']
                same_phone_users = list(phone.users.exclude(id=self.instance.id))
                if same_phone_users:
                    form.add_error('phone', u'Номер телефона "%s" уже используется в другом аккаунте (%s)' % (
                            pprint_phone(phone.number),
                            ', '.join([unicode(user) for user in same_phone_users])
                        )
                    )


class PhoneInline(admin.TabularInline):
    form = PhoneInlineForm
    formset = PhoneInlineFormset
    model = UserPhone
    extra = 5
    max_num = 5


class AgencyFilter(admin.SimpleListFilter):
    title = u'агентство?'
    parameter_name = 'agency'

    def lookups(self, request, model_admin):
        return [
            ('yes', u'да'),
            ('no', u'нет'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'no':
            return queryset.filter(agencies__isnull=True).distinct()
        elif self.value() == 'yes':
            return queryset.filter(agencies__isnull=False).distinct()


class DeveloperFilter(admin.SimpleListFilter):
    title = u'застройщик?'
    parameter_name = 'developer'

    def lookups(self, request, model_admin):
        return [
            ('yes', u'да'),
            ('no', u'нет'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'no':
            return queryset.filter(newhomes__isnull=True).distinct()
        elif self.value() == 'yes':
            return queryset.filter(newhomes__isnull=False).distinct()


class TestPlanFilter(admin.SimpleListFilter):
    title = u'бесплатные планы'
    parameter_name = 'freeplan'

    def lookups(self, request, model_admin):
        return [
            ('experiment', u'эксперимент'),
            ('bonus', u'бонус'),
            ('no', u'нет'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'experiment':
            users = UserPlan.objects.filter(transactions__amount=0, start__lt='2016-05-19').values_list('user', flat=True)
            return queryset.filter(id__in=users)
        if self.value() == 'bonus':
            users = UserPlan.objects.filter(bonus2016=True).values_list('user', flat=True)
            return queryset.filter(id__in=users)
        elif self.value() == 'no':
            users = UserPlan.objects.filter(transactions__amount=0).values_list('user', flat=True)
            return queryset.exclude(id__in=users)


class RegionFilter(ProvinceRegionFilter):
    title = u'регион'
    parameter_name = 'region'


class ManagerFilter(admin.SimpleListFilter):
    title = u'менеджер'
    parameter_name = 'manager'
    template = 'admin/filter_select.html'

    def lookups(self, request, model_admin):
        key = 'admin_filter_by_manager'
        lookups_ = cache.get(key)
        if lookups_ is None:
            lookups_ = [(manager.user_ptr_id, manager.get_public_name()) for manager in Manager.objects.all()] + [('none', u'(без менеджера)')]
            cache.set(key, lookups_, 3600*24)
        return lookups_

    def queryset(self, request, queryset):
        if self.value() == 'none':
            return queryset.filter(manager__isnull=True)
        elif self.value():
            return queryset.filter(manager_id=self.value())


class BannedPhonesFilter(admin.SimpleListFilter):
    title = u'забанненые телефоны (в т.ч. аферисты в Харькове)'
    parameter_name = 'banned_phones'

    def lookups(self, request, model_admin):
        return [('yes', u'Да'), ('no', u'Нет')]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(ads__phones__is_banned=True).distinct()
        elif self.value() == 'no':
            return queryset.exclude(ads__phones__is_banned=True).distinct()


class LoyaltyFilter(admin.SimpleListFilter):
    title = u'программа лояльности?'
    parameter_name = 'loyalty'

    def lookups(self, request, model_admin):
        return [('yes', u'Да'), ('no', u'Нет')]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(loyalty_started__isnull=False)
        elif self.value() == 'no':
            return queryset.exclude(loyalty_started__isnull=True)


class BanFilter(admin.SimpleListFilter):
    title = u'бан?'
    parameter_name = 'ban'

    def lookups(self, request, model_admin):
        return [('yes', u'Да'), ('no', u'Нет')]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(id__in=get_banned_users())
        elif self.value() == 'no':
            return queryset.exclude(id__in=get_banned_users())


class NewPlanFilter(admin.SimpleListFilter):
    title = u'по новым тарифам'
    parameter_name = 'user'

    def lookups(self, request, model_admin):
        return FILTER_USER_BY_PLAN_CHOICES

    def queryset(self, request, queryset):
        return filter_user_by_plan(queryset, self.value())


class AdsSumFilter(SumFilter):
    sum_field = 'ads_count'
    title = u'активных объявлений'


class CustomUserAdmin(UserAdmin):
    list_display = ('__unicode__', 'display_info', 'id', 'display_email', 'display_phones', 'display_is_active',
                    'region', 'display_ads_count', 'display_date_joined', 'display_last_action', 'display_balance',
                    'display_ban',)
    inlines = [PhoneInline]
    actions = ['move_to_managers', 'remove_from_managers', 'create_agency', 'activate', 'deactivate',
               'update_phones', 'give_leadgeneration_bonus']
    search_fields = ('id', 'agencies__name', 'first_name', 'last_name')
    list_filter = (ManagerFilter, RegionFilter, M2MPhoneFilter, make_datetime_filter('date_joined'), 'is_active',
                   AgencyFilter, DeveloperFilter, NewPlanFilter, make_datetime_filter('last_action'),
                   LoyaltyFilter, BanFilter, 'is_staff', 'is_superuser', IPAddressFilter, BannedPhonesFilter,
                   AdsSumFilter)
    show_full_result_count = False

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super(CustomUserAdmin, self).get_search_results(request, queryset, search_term)
        filter = Q()
        for word in search_term.split():
            if '@' in word:
                filter.add(Q(email__iexact=word), Q.OR)
        if filter:
             queryset |= self.model.objects.filter(filter)
        return queryset, use_distinct

    def get_list_filter(self, request):
        list_filter = list(super(CustomUserAdmin, self).get_list_filter(request))
        if not request.user.groups.filter(name__icontains=u'комитет').exists():
            list_filter.insert(-1, TestPlanFilter)
        return list_filter

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super(CustomUserAdmin, self).get_fieldsets(request, obj))

        if not request.user.is_superuser:
            fieldsets.pop(2) # поля с правами

        fieldsets.append(
            (None, {'fields': (
                'manager', 'region', 'city', 'image', 'loyalty_started',
                'show_email', 'show_message_button', 'subscribe_info', 'subscribe_news', 'receive_sms',
                'language', 'gender', 'ip_addresses'
            )})
        )

        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            readonly_fields = []
        else:
            readonly_fields = ['username', 'last_login', 'last_action', 'date_joined', 'ads_count']
            if not request.user.groups.filter(id=12).exists():
                readonly_fields.append('manager')
        return readonly_fields

    def get_queryset(self, request):
        return super(CustomUserAdmin, self).get_queryset(request)\
            .prefetch_related('leadgeneration', 'developer', 'phones', 'realtors__agency', 'region', 'transactions',
                              'user_plans', 'activityperiods', 'bans', 'stat_set', 'social_auth')

    def lookup_allowed(self, key, value):
        if key in ('transactions__amount',):
            return True
        return super(CustomUserAdmin, self).lookup_allowed(key, value)

    def get_actions(self, request):
        actions = super(CustomUserAdmin, self).get_actions(request)
        if not request.user.has_perm('ad.change_phoneinad'):
            del actions['update_phones']

        # group ID 12 - руководитель отдела менеджеров
        if not (request.user.is_superuser or request.user.groups.filter(id=12).exists()):
            if 'move_to_managers' in actions:
                del actions['move_to_managers']

            if 'remove_from_managers' in actions:
                del actions['remove_from_managers']

        return actions

    def display_email(self, obj):
        if obj.email:
            items = [obj.email]
        else:
            items = []

        website_icon = u'<img src="%s" alt=""/>' % static('admin/img/icon-website.gif')
        for social in obj.social_auth.all():
            # TODO добавить гугл+
            link = None
            if social.provider == 'facebook':
                link = "http://facebook.com/%s" % social.uid
            elif social.provider in ['vkontakte-oauth2','vkontakte', 'vk-oauth', 'vk-oauth2']:
                link = "http://vk.com/id%s" % social.uid
            elif social.provider == 'twitter':
                link = "https://twitter.com/intent/user?user_id=%s" % social.uid
            if link:
                items.append(u'<a href="%s" target="_blank">%s %s</a>' % (link, website_icon, social.provider))
                
        return ' '.join(items)
    display_email.short_description = u'E-mail/соцсеть'
    display_email.allow_tags = True

    def display_phones(self, obj):
        return u'<br/>'.join([p.number for p in obj.phones.all()])
    display_phones.short_description = u'телефоны'
    display_phones.allow_tags = True

    def display_date_joined(self, obj):
        return (obj.date_joined.strftime('%d.%m.%Y') if obj.date_joined else None)
    display_date_joined.short_description = u'Регистрация'
    display_date_joined.admin_order_field = 'date_joined'

    def display_last_action(self, obj):
        return (obj.last_action.strftime('%d.%m.%Y') if obj.last_action else None)
    display_last_action.short_description = u'Активн.'
    display_last_action.admin_order_field = 'last_action'

    def display_ads_count(self, obj):
        result = u'<a href="%s?user__exact=%d">%s</a>' % (
            reverse('admin:ad_ad_changelist'), obj.id, obj.ads_count or '-'
        )
        newhomes_amount = obj.newhomes.all().count() if obj.is_developer() else 0
        if newhomes_amount:
            result += u' / <a href="%s?user__exact=%d">%d</a>' % (
                reverse('admin:newhome_newhome_changelist'), obj.id, newhomes_amount
            )
        return result
    display_ads_count.allow_tags = True
    display_ads_count.short_description = u'Объявл'
    display_ads_count.admin_order_field = 'ads_count'

    def display_is_active(self, obj):
        return obj.is_active
    display_is_active.boolean = True
    display_is_active.short_description = u'Акт'
    display_is_active.admin_order_field = 'is_active'

    def get_urls(self):
        urls = [
            url(r'^buy_plan/$', self.admin_site.admin_view(self.buy_plan), name="buy_plan"),
            url(r'^buy_vip/$', self.admin_site.admin_view(self.buy_vip), name="buy_vip"),
            url(r'^move_money/$', self.admin_site.admin_view(self.move_money), name="move_money"),
            url(r'^login_as/(?P<user_id>\d+)/$', self.admin_site.admin_view(self.login_as), name='login_as'),
            url(r'^(?P<user_id>.+)/info/$', self.admin_site.admin_view(self.info_view), name='custom_user_user_info')
        ]
        return urls + super(CustomUserAdmin, self).get_urls()

    def info_view(self, request, user_id):
        obj = User.objects.get(id=user_id)
        unexpired_plans = obj.get_unexpired_plans()
        prolonged_plans = unexpired_plans.exclude(is_active=True)
        leadgeneration = obj.get_leadgeneration()
        has_leadgeneration_ads = obj.has_active_leadgeneration('ads')
        recently_ppc_period = obj.activityperiods.filter(end__gt=datetime.datetime.now()-datetime.timedelta(days=7)).last()
        realtor = obj.get_realtor()

        if request.method == 'GET' and request.GET:
            # модераторы или руководитель отдела менеджеров
            if request.user.is_superuser or request.user.groups.filter(id__in=[1, 12]).exists():
                if 'cancel_prolonged_plans' in request.GET:
                    if prolonged_plans:
                        for prolonged_plan in prolonged_plans:
                            prolonged_plan.cancel(request.user, 'full')
                    else:
                        raise Exception('No prolonged plans')
                elif 'set_ads_limit' in request.GET or 'cancel_dedicated_numbers' in request.GET:
                    if has_leadgeneration_ads:
                        if 'set_ads_limit' in request.GET:
                            leadgeneration.ads_limit = int(request.GET['set_ads_limit'])
                        if 'cancel_dedicated_numbers' in request.GET:
                            # TODO: добавить related_name для corrected_transaction и заменить transaction__isnull на какой-нибудь corrections__isnull
                            for transaction in obj.transactions.filter(type=80, time__gt=datetime.datetime.now() - datetime.timedelta(days=3), transaction__isnull=True): 
                                transaction.revert(comment=u'Возврат при отмене выделенного номера. Отменил пользователь #%d' % request.user.id)

                            leadgeneration.dedicated_numbers = False
                        leadgeneration.save()
                    else:
                        raise Exception('PPC for ads isn`t active')
                elif 'remove_from_agency' in request.GET:
                    if realtor:
                        if realtor.is_admin and realtor.agency.realtors.count() == 1:
                            realtor.agency.delete()
                        else:
                            realtor.delete()
                    else:
                        raise Exception('Cannot remove user from agency')
                elif 'restore_ppc' in request.GET:
                    recently_ppc_period.end = None
                    recently_ppc_period.calls = 0
                    recently_ppc_period.requests = 0
                    recently_ppc_period.numbers = 0
                    recently_ppc_period.save()
                elif 'add_to_agency' in request.GET:
                    agency_admin = Realtor.objects.filter(user__email=request.GET['add_to_agency'], is_admin=True).first()
                    if agency_admin:
                        obj.realtors.all().delete() # старые связи в печь
                        Realtor.objects.create(user=obj, agency=agency_admin.agency, is_active=True, is_admin=False)
                    else:
                        self.message_user(request, u'Агентство не найдено', level=messages.ERROR)
                elif 'move_ads_to_user' in request.GET:
                    new_user = User.objects.get(email=request.GET['user_email'])
                    obj.ads.update(user=new_user)
                    # обновление счетчиков объявлений
                    for user in [obj, new_user]:
                        user.update_ads_count()
                elif 'change_manager' in request.GET:
                    new_manager = Manager.objects.get(id=request.GET['manager_id'])
                    obj.manager_ptr.managed_users.update(manager=new_manager)
                elif 'remove_developer' in request.GET:
                    obj.developer.delete()

                return redirect(reverse('admin:custom_user_user_info', args=[obj.id]))
            else:
                raise PermissionDenied
        else:
            context = self.admin_site.each_context(request)
            context.update(
                obj=obj,
                unexpired_plans=unexpired_plans,
                prolonged_plans=prolonged_plans,
                leadgeneration=leadgeneration,
                recently_ppc_period=recently_ppc_period,
                has_leadgeneration_ads=has_leadgeneration_ads,
                realtor=realtor,
                opts=User._meta,
                title=u'Информация о пользователе',
                has_change_permission=self.has_change_permission(request, obj),
                managers=Manager.objects.all(),
                managed_users_count=obj.manager_ptr.managed_users.count() if hasattr(obj, 'manager_ptr') else 0,
                all_ads_count=obj.ads.count()
            )
            return render(request, 'admin/custom_user/user_info.html', context)

    def display_info(self, obj):
        result = u''

        result += u'<a title="Информация о пользователе" href="%s"><img src="%s"/></a> ' % (
            reverse('admin:custom_user_user_info', args=[obj.id]),
            static('admin/img/icon-info.png')
        )

        if obj.stat_set.exists():
            result += u'<a title="Показать статистику пользователя" href="%s?user__exact=%d"><img src="%s"/></a> ' % (
                reverse('admin:profile_statgrouped_changelist'), obj.id, static('admin/img/icon-stats.gif'))

        for realtor in obj.realtors.all():
            result += u'<a href="%s?id=%d" title="%s"%s><img src="%s"/></a> ' % \
                      (reverse('admin:agency_agency_changelist'), realtor.agency_id, realtor.agency.name,
                       ' style="opacity:0.3"' if not realtor.is_active else '',
                       static('admin/img/icon-agency.gif') if realtor.is_admin else static('admin/img/icon-user.gif'))

            if realtor.is_admin and realtor.agency.import_url:
                result += u'<a title="Показать статистику импорта" href="%s?agency=%d"><img src="%s"/></a> ' % (
                    reverse('admin:import__importtask_changelist'), realtor.agency.id, static('admin/img/icon-feed.png'))

        if hasattr(obj, 'developer'):
            result += u'<a href="%s?user_id=%d" title="%s"><img src="%s"/></a> ' % \
                      (reverse('admin:newhome_developer_changelist'), obj.id, obj.developer.name,
                       static('admin/img/icon-developer.gif'))

        active_plan = obj.get_active_plan_using_prefetch()
        if active_plan:
            result += u'<a href="{}?id={}" title="{}"><img src="{}" style="background-color:{}"/></a> '.format(
                        reverse('admin:paid_services_userplan_changelist'), active_plan.id,
                        u'Тариф до {:%d.%m.%Y}. Лимит объявлений - {}'.format(active_plan.end, active_plan.ads_limit),
                        static('admin/img/icon-dollar.png'), '#ecb310')

        active_leadgeneration = obj.has_active_leadgeneration()
        if active_leadgeneration:
            active_for = filter(None, [u'объявлений' if 'ads' in active_leadgeneration else '', u'новостроек' if 'newhomes' in active_leadgeneration else ''])
            result += u'<a href="{}?id={}" title="включена для {}"><img src="{}" style="background-color:{}"/></a> '.format(
                        reverse('admin:ppc_leadgeneration_changelist'), obj.leadgeneration.id, u' и '.join(active_for),
                        static('admin/img/icon-dollar.png'), '#31c500')

        if not obj.is_staff and obj.is_active:
            result += u'<a title="Войти под этим пользователем" href="%s" onClick="return confirm(\'%s\')"><img src="%s" style="opacity:0.3"/></a> ' % (
                reverse('admin:login_as', args=[obj.id]),
                u'ВНИМАНИЕ! Произойдет выход из текущего аккаунта.         '
                u'Рекомендуется открывать ссылку в режиме инкогнито с последующим повторным вводом вашего логина/пароля.',
                static('admin/img/icon-login.svg'))

        return result

    display_info.allow_tags = True
    display_info.short_description = u'Инфо'

    def display_ban(self, obj):
        if obj.id in get_banned_users():
            sorted_bans = sorted(obj.bans.all(), key=lambda v: v.expire_date)
            return u'до %s' % sorted_bans[-1].expire_date.strftime('%d.%m.%Y')
        else:
            return u'<a href="%s?user=%d" title="Отправить в бан"><img src="%s" alt=""/></a>' % (
                reverse('admin:profile_ban_add'), obj.id, static('admin/img/icon-ban.png'),
            )
    display_ban.short_description = u'Бан'
    display_ban.allow_tags = True

    def display_balance(self, obj):
        # попытка использовать join с таблицей транзакций и sum кладет базу, поэтому так
        balance = int(sum([t.amount for t in obj.transactions.all()]))
        return u'<a title="Показать транзакции пользователя" href="%s?user__exact=%d">%s</a>' % (
            reverse('admin:paid_services_transaction_changelist'), obj.id, balance
        )
    display_balance.allow_tags = True
    display_balance.short_description = u'Баланс'

    def display_plans(self, obj):
        active_plan = obj.get_active_plan_using_prefetch()
        if active_plan:
            return u'<a title="Показать планы пользователя" href="%s?user__exact=%d">до %s</a>' % (
                reverse('admin:paid_services_userplan_changelist'), obj.id, active_plan.end.strftime('%Y-%m-%d')
            )
        return ''
    display_plans.allow_tags = True
    display_plans.short_description = u'План'

    @transaction.atomic
    def move_to_managers(self, request, queryset):
        moved = []
        for user in queryset:
            user_str = user.email or unicode(user)
            if hasattr(user, 'manager_ptr'):
                self.message_user(request, u'Ошибка: пользователь %s уже является менеджером' % user_str, level=messages.ERROR)
                return
            else:
                Manager.create_from_user(user)
                user.is_staff = True
                user.save()
                user.groups.add(Group.objects.get(id=2))
                moved.append(user_str)
        self.message_user(request, u'Переведены в менеджеры: %s' % u', '.join(moved), level=messages.WARNING)
    move_to_managers.short_description = u'Перевести в менеджеры'

    @transaction.atomic
    def remove_from_managers(self, request, queryset):
        removed = []
        for user in queryset:
            user_str = user.email or unicode(user)
            if hasattr(user, 'manager_ptr'):
                # запрет удаления из менеджеров, если у менеджера есть пользователи
                # внимание! если захочется все равно удалять, то перед удалением нужно разорвать связи - manager_ptr.managed_users.update(manager=None),
                # иначе из базы вместе с менеджером удалятся все его пользователи (из-за on_delete)
                if user.manager_ptr.managed_users.exists():
                    self.message_user(request, u'Ошибка: невозможно удалить менеджера %s - у него есть пользователи' % user_str, level=messages.ERROR)
                    return
                else:
                    user.manager_ptr.delete(keep_parents=True)

                user.is_staff = False
                user.save()
                user.groups.remove(Group.objects.get(id=2))
                removed.append(user_str)
            else:
                self.message_user(request, u'Ошибка: пользователь %s не является менеджером' % user_str, level=messages.ERROR)
                return
        self.message_user(request, u'Удалены из менеджеров: %s' % u', '.join(removed), level=messages.WARNING)
    remove_from_managers.short_description = u'Удалить из менеджеров'

    @transaction.atomic
    def create_agency(self, request, queryset):
        for user in queryset:
            user.create_agency()
        self.message_user(request,
                          u'Созданы агентства для пользователей: %s' % [unicode(user) for user in queryset],
                          level=messages.INFO)
    create_agency.short_description = u'Создать агентство'

    def activate(self, request, queryset):
        for user in queryset:
            user.is_active = True
            user.save()
    activate.short_description = u'Активировать'

    def update_phones(self, request, queryset):
        for user in queryset:
            numbers = user.phones.order_by('users_m2m').values_list('number', flat=True)
            user.update_ads_phones(numbers)
    update_phones.short_description = u'Заменить телефоны в объявлениях телефонами из профиля'

    def deactivate(self, request, queryset):
        for user in queryset:
            user.is_active = False
            user.save()
    deactivate.short_description = u'Деактивировать'

    def give_leadgeneration_bonus(self, request, queryset):
        from ppc.models import LeadGeneration, Bonus, ActivityPeriod
        for user in queryset:
            leadgeneration, created = LeadGeneration.objects.get_or_create(user=user)
            leadgeneration.is_active_ads = True
            leadgeneration.weekdays = []
            leadgeneration.save()

            bonus = Bonus.objects.create(user=user, start=datetime.datetime.now())
            ActivityPeriod.objects.get_or_create(user=user, end=None, lead_type='ads')
    give_leadgeneration_bonus.short_description = u'Включить лидогенерацию (объявл.) с 10 бесплатными звонками/лидами'

    def login_as(self, request, user_id=None):
        from django.contrib.auth import login, logout
        user = User.objects.get(pk=user_id)
        if request.user.is_superuser or (not user.is_staff and request.user.groups.filter(id__in=[1,2,12]).exists()):
            logout(request)
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            return redirect('/')
        else:
            self.message_user(request,  u'Недостаточно прав.', level=messages.ERROR)
            return redirect(request.META.get('HTTP_REFERER', '/admin/custom_user/user/'))

    def move_money(self, request):
        class Form(forms.Form):
            from_user = UserField(label=u'От кого', help_text=u'e-mail или ID')
            to_user = UserField(label=u'Кому', help_text=u'e-mail или ID')
            amount = forms.IntegerField(label=u'Сумма перевода', min_value=1)

            def clean(self):
                if self.cleaned_data['from_user'].get_balance(force=True) < self.cleaned_data['amount']:
                    raise forms.ValidationError(u'Недостаточно средств у пользователя %s' % self.cleaned_data['from_user'])


        if request.POST:
            from ad.models import Ad
            from paid_services.models import VipPlacement, InsufficientFundsError

            form = Form(request.POST)
            if form.is_valid():
                from_user = form.cleaned_data['from_user']
                to_user = form.cleaned_data['to_user']
                if request.user.is_superuser or request.user.groups.filter(id__in=[1, 12]).exists()\
                        or (from_user.get_agency() and from_user.get_agency() == to_user.get_agency()):
                    Transaction.move_money(from_user, to_user,
                                           form.cleaned_data['amount'], u'перевел %s' % request.user)
                    self.message_user(request,  u'Деньги переведены. Баланс пользователя %s: %d грн' %
                                      (to_user, to_user.get_balance(force=True)),
                                      level=messages.SUCCESS)
                    return redirect(request.POST.get('next', '.'))
                else:
                    self.message_user(request,  u'Пользователи не находятся в одном агентстве', level=messages.ERROR)
        else:
            form = Form()
        return render(request, 'admin/move_money.html', locals())

    def buy_vip(self, request):
        vip_discounts_choices = (
            (0, 'без скидки'),
            (10, 'от 10 до 20 объяв - 10%'),
            (18, 'от 21 до 50 объяв - 18%'),
            (26, 'от 51 объяв - 26%'),
        )
        weeks_choices = ( (1, 1), (2, 2), (4, 4), )

        class Form(forms.Form):
            ids = forms.CharField(label=u'ID объявлений', widget=forms.Textarea(attrs={'rows':4}))
            discount = forms.IntegerField(label=u'Скидка по объему', widget=forms.Select(choices=vip_discounts_choices))
            weeks = forms.IntegerField(label=u'Длительность, недель', widget=forms.Select(choices=weeks_choices))
            bonus = forms.BooleanField(label=u'Бонус', required=False)

        if request.POST:
            from ad.models import Ad
            from paid_services.models import VipPlacement, InsufficientFundsError

            now = datetime.datetime.now()
            form = Form(request.POST)
            if form.is_valid():
                ad_ids = form.cleaned_data['ids'].replace(',', ' ').split()
                ads = Ad.objects.filter(pk__in=ad_ids)
                discount = form.cleaned_data['discount']
                weeks = form.cleaned_data['weeks']
                sum = 0

                bonus_comment = u'бонус от менеджера #%d %s' % (request.user.id, request.user.email)
                bonus_vips_in_month = Transaction.objects.filter(type=53, time__year=now.year, time__month=now.month, comment=bonus_comment).count()

                for ad in ads:
                    user = ad.user
                    price = user.get_paidplacement_price(ad, 'vip') * weeks * (100 - discount) / 100
                    transaction = Transaction(user=user, type=53, amount=-price)

                    # бесплатные ВИПы, один менеджер может дарить не большее 30 випов в месяц
                    if form.cleaned_data['bonus']:
                        if bonus_vips_in_month < 30:
                            transaction.comment = bonus_comment
                            transaction.amount = price = 0
                            bonus_vips_in_month += 1
                            weeks = 1

                    sum += price

                    message = u'[%s, объявление #%s] VIP на %d дней, стоимость %d грн - ' % (user, ad.pk, weeks * 7, price)

                    if ad.vip_type:
                        self.message_user(request,  u'%s уже VIP' % message, level=messages.ERROR)
                        continue

                    if 'buy' in request.POST:
                        try:
                            if price > user.get_balance(force=True):
                                agency_admin = user.get_realtor().agency.get_admin_user()
                                Transaction.move_money(agency_admin, user, price, u'покупка VIP для объявления #%s' % ad.id)
                                message += u'(перевод денег с главного аккаунта)'

                            transaction.save()
                        except InsufficientFundsError:
                            self.message_user(request, u'%s недостаточно средств. Баланс %s' % (message, user.get_balance()), level=messages.ERROR)
                        else:
                            vip = VipPlacement.objects.create(basead=ad, days=weeks * 7, transaction=transaction)
                            self.message_user(request, u'%s КУПЛЕН' % message, level=messages.SUCCESS)
                    else:
                        self.message_user(request,  u'%s ОЦЕНЕН, еще не куплен' % message, level=messages.WARNING)

                if not ads:
                    self.message_user(request,  u'Объявления не найдены', level=messages.ERROR)

                if len(ads) > 1:
                    self.message_user(request,  u'Итого по всем объявлениям: %s грн' % sum, level=messages.WARNING)
        else:
            form = Form()

        return render(request, 'admin/buy_vip.html', locals())

    def buy_plan(self, request):
        class Form(forms.Form):
            user = UserField(label=u'Пользователь', help_text=u'email или ID')
            ads_limit = forms.IntegerField(label=u'Лимит по плану', min_value=1)
            price = forms.IntegerField(label=u'Цена тарифного плана', min_value=1, required=False)
            stop_active_plan = forms.BooleanField(label=u'Останавливать текущий', required=False)

        if request.POST:
            form = Form(request.POST)
            if form.is_valid():
                user = form.cleaned_data['user']
                ads_limit = form.cleaned_data['ads_limit']

                if not user.region:
                    from django.utils.safestring import mark_safe
                    self.message_user(request, mark_safe(u'У пользователя отсутствует регион. <a href="%s">Указать регион</a>.' %
                                      reverse('admin:custom_user_user_change', args=[user.id])), level=messages.ERROR)
                    return render(request, 'admin/buy_plan.html', locals())

                try:
                    plan = Plan.objects.get(is_active=True, ads_limit=ads_limit)
                    discount = user.get_plan_discount()
                    suggest_plan_price = Plan.get_price(user.region.price_level, ads_limit, discount)
                except Plan.DoesNotExist:
                    plan = Plan.objects.get(pk=18)

                    realtor = user.get_realtor()
                    if realtor:
                        agency_users = realtor.agency.get_realtors().exclude(user=user).values_list('user', flat=True)
                        agency_ads_limits = (UserPlan.objects.filter(end__gt=datetime.datetime.now(), user__in=agency_users).aggregate(sum=Sum('ads_limit'))['sum'] or 0) \
                                            + ads_limit
                    else:
                        agency_ads_limits = ads_limit

                    if agency_ads_limits < 100:
                        discount = 0.2
                    elif agency_ads_limits < 200:
                        discount = 0.3
                    elif agency_ads_limits < 500:
                        discount = 0.4
                    elif agency_ads_limits < 1000:
                        discount = 0.45
                    else:
                        discount = 0.5
                    suggest_plan_price = Plan.get_price(user.region.price_level, ads_limit, discount)

                if 'calculate' in request.POST:
                    form.data._mutable = True
                    form.data['price'] = suggest_plan_price

                    self.message_user(request, u'%s лимит объявлений в агентстве, %s%% скидка. Цена за план %s грн. Баланс пользователя %s грн' %
                                      (ads_limit, int(discount*100), suggest_plan_price, user.get_balance()), level=messages.WARNING)

                if 'buy' in request.POST:
                    new_plan = UserPlan(user=user, plan=plan, ads_limit=ads_limit, region=user.region)

                    active_plan = user.get_active_plan_using_prefetch()
                    if active_plan:
                        if form.cleaned_data['stop_active_plan']:
                            active_plan.cancel(request.user)
                            self.message_user(request, u'Предыдущий тариф #%s был отменен с возвратом средств' % active_plan.pk, level=messages.ERROR)
                        else:
                            new_plan.start = user.get_unexpired_plans().order_by('-end').first().end
                            new_plan.is_active = False

                    plan_price = form.cleaned_data['price'] or suggest_plan_price
                    if not (1 < (plan_price/ads_limit) < 30):
                        self.message_user(request, u'Недопустимая цена за одно объявение: %.02f грн' % (plan_price/float(ads_limit)), level=messages.ERROR)
                    elif user.get_balance(force=True) < plan_price:
                        self.message_user(request, u'Недостаточно средств на счете. Тариф оценен в %s грн, баланс пользователя - %s'
                                          % (plan_price, user.get_balance()), level=messages.ERROR)
                    else:
                        # только здесь создается новый план
                        new_plan.save()
                        transaction = Transaction(user=user, type=11, amount=-plan_price, user_plan=new_plan)
                        transaction.save()

                        self.message_user(request, u'Тариф на %s объявлений c %s до %s куплен. Стоимость %s грн.' %
                                          (ads_limit, new_plan.start.strftime('%d.%m.%Y %H:%M'), new_plan.end.strftime('%d.%m.%Y %H:%M'), plan_price))
                        return redirect('.')
        else:
            form = Form()

        return render(request, 'admin/buy_plan.html', locals())


class CustomGroupAdmin(GroupAdmin):
    list_display = ('name', 'display_users')

    def display_users(self, obj):
        users = obj.user_set.all()
        if users:
            items = []
            for user in users:
                link = reverse('admin:custom_user_user_change', args=[user.id])
                items.append(u'<li><a href="%s">%s</a></li>' % (link, user.email or unicode(user)))
            return u'<ul style="margin:0 0 0 5px;">%s</ul>' % u''.join(items)
        else:
            return ''
    display_users.allow_tags = True
    display_users.short_description = u'Пользователи'


admin.site.register(User, CustomUserAdmin)

admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)
