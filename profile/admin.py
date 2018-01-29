#-*- coding: utf-8 -*-
from django import forms
from django.contrib import admin
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.utils.http import urlencode
from django.db.models import Q, Count
from django.templatetags.static import static
from django.utils.translation import ugettext as _
from django.contrib.postgres.forms import SimpleArrayField

from ad.models import Ad, Moderation
from ad import filterspec
from profile.models import Ban, EmailChange, Stat, StatGrouped, Message, MessageList, Notification, Manager
from custom_user import admin as custom_user_admin
from admin_ext.filters import make_datetime_filter

from modeltranslation.admin import TranslationAdmin
from ckeditor.widgets import CKEditorWidget
from ckeditor_uploader.widgets import CKEditorUploadingWidget

import datetime
import calendar


def get_user_filter_link(user, lookup='user__exact'):
    if not user:
        return ''

    realtor = user.get_realtor()

    if realtor:
        icon_path = 'admin/img/icon-agency.gif'
        user_repr = realtor.agency.name
    else:
        icon_path = 'admin/img/icon-user.gif'
        user_repr = unicode(user)

    return u'''
        <nobr><a href="?%(lookup)s=%(id)d" title="фильтровать">%(user_icon)s %(user_repr)s</a>
        <a href="%(changelist_url)s?id=%(id)d" title="смотреть профиль">%(edit_icon)s</a></nobr>
        <br><small>%(user_email)s</small>
        ''' % {
            'changelist_url': reverse('admin:custom_user_user_changelist'),
            'lookup': lookup,
            'id': user.id,
            'edit_icon': '<img src="%s" alt=""/>' % static('admin/img/icon-edit-small.gif'),
            'user_icon': '<img src="%s" alt="" />' % static(icon_path),
            'user_repr': user_repr,
            'user_email': user.email
        }

class StatManagerFilter(custom_user_admin.ManagerFilter):
    def queryset(self, request, queryset):
        if self.value() == 'none':
            return queryset.filter(user__manager__isnull=True)
        elif self.value():
            return queryset.filter(user__manager_id=self.value())

class MessageManagerFilter(custom_user_admin.ManagerFilter):
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(Q(from_user=self.value()) | Q(to_user=self.value()))

class PeriodFilter(admin.SimpleListFilter):
    title = u'Период'
    field = 'date'
    parameter_name = 'month'

    def lookups(self, request, model_admin):
        lookups = []

        now = datetime.date.today().replace(day=20)
        filter_date = now - datetime.timedelta(days=365)

        while (filter_date < now):
            lookups.append((filter_date.strftime('%Y-%m'), filter_date.strftime('%b %Y')))
            filter_date = filter_date + datetime.timedelta(days=30)

        return reversed(lookups)

    def queryset(self, request, queryset):
        if self.value():
            date = [int(x) for x in self.value().split('-')]
            day_in_month = calendar.monthrange(date[0],date[1])[1]
            period_start = datetime.date(day=1, month=date[1], year=date[0])
            period_end = period_start + datetime.timedelta(days=day_in_month, minutes=-1)
            queryset = queryset.filter(**{'%s__range' % self.field: (period_start,period_end)})

        return queryset

class GroupFilter(admin.SimpleListFilter):
    title = u'Группировка'
    parameter_name = 'group'

    def lookups(self, request, model_admin):
        return (
            ('months','по месяцам по всем пользователям'),
            ('users','по пользователям за всё время'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'months':
            queryset = queryset.filter(user__isnull=True)
        elif self.value() == 'users':
            queryset = queryset.filter(date__isnull=True)
        else:
            queryset = queryset.filter(user__isnull=False, date__isnull=False)

        return queryset

class MessageListFilter(admin.SimpleListFilter):
    title = u'по рассылке'
    parameter_name = 'message_list'
    template = 'admin/filter_select.html'

    def lookups(self, request, model_admin):
        return [('none', u'(без рассылки)')] + [(m.id, m.name) for m in MessageList.objects.order_by('-id')]

    def queryset(self, request, queryset):
        if self.value() == 'none':
            return queryset.filter(message_list__isnull=True)
        elif self.value():
            return queryset.filter(message_list__id=self.value())

class AgencyFilter(custom_user_admin.AgencyFilter):
    def queryset(self, request, queryset):
        if self.value() == 'no':
            return queryset.filter(user__agencies__isnull=True)
        elif self.value() == 'yes':
            return queryset.filter(user__agencies__isnull=False)


BAN_EXPIRE_CHOICES = (
    (7, u'1 неделю'),
    (14, u'2 недели'),
    (30, u'1 месяц'),
    (30*2, u'2 месяца'),
    (30*6, u'6 месяцев'),
    (30*12*10, u'10 лет'),
)

class BanForm(forms.ModelForm):
    expire_date = forms.ChoiceField(label='Бан истекает через', choices=BAN_EXPIRE_CHOICES, required=False, widget=forms.Select(attrs={}))

    class Meta:
        model = Ban
        fields = ('reason', 'expire_date', 'user',)

    def clean_expire_date(self):
        expire = int(self.cleaned_data['expire_date'])
        if expire:
            return datetime.date.today() + datetime.timedelta(days=expire)

class BanAdmin(admin.ModelAdmin):
    form = BanForm
    list_display = ('__unicode__', 'expire_date')
    search_fields = ('user__email',)
    raw_id_fields = ('user',)

    def save_model(self, request, obj, form, change):
        now = datetime.datetime.now()
        if obj.expire_date > now.date():
            Ad.objects.filter(user=obj.user, is_published=True).update(moderation_status=20, is_published=False, fields_for_moderation=None)
            Moderation.objects.filter(basead__ad__user=obj.user, moderator__isnull=True)\
                .update(new_status=20, end_time=now, moderator=request.user)

            # TODO: можно еще добавить отправку письма, о том что юзер забанен

        super(BanAdmin, self).save_model(request, obj, form, change)

class EmailChangeAdmin(admin.ModelAdmin):
    list_display = ('created', 'user', 'old_email', 'new_email', 'status')
    search_fields = ('old_email', 'new_email')


class SmartArrayField(SimpleArrayField):
    def to_python(self, value):
        cleaned_lines = []
        for raw_line in value.split(self.delimiter):
            cleaned_line = raw_line.strip()
            if cleaned_line:
                cleaned_lines.append(cleaned_line)
        cleaned_value = self.delimiter.join(cleaned_lines)
        return super(SmartArrayField, self).to_python(cleaned_value)


class UserFilterModelForm(forms.ModelForm):
    filter_user_by_email = SmartArrayField(
        forms.EmailField(), required=False, label=u'фильтр юзеров по e-mail', delimiter=u'\n', widget=forms.Textarea(),
        help_text=u'список e-mail адресов, каждый адрес в отдельной строке'
    )
    filter_user_by_id = SmartArrayField(
        forms.IntegerField(), required=False, label=u'фильтр юзеров по ID', delimiter=u',', widget=forms.Textarea(),
        help_text=u'список ID, через запятую'
    )


# для того чтобы поля-фильтры отображались в форме после других полей модели
class UserFilterAdmin(admin.ModelAdmin):
    # get_fields не сработает, как минимум, с наследованием от TranslationAdmin, в котором переопределен get_fieldsets
    def get_fieldsets(self, request, obj=None):
        fieldsets = super(UserFilterAdmin, self).get_fieldsets(request, obj)
        for fieldset_name, fieldset_dict in fieldsets:
            filter_user_fields = []
            other_fields = []
            for field in fieldset_dict['fields']:
                if field.startswith('filter_user_by_'):
                    filter_user_fields.append(field)
                else:
                    other_fields.append(field)
            fieldset_dict['fields'] = other_fields + filter_user_fields
        return fieldsets

class NotificationAdminForm(UserFilterModelForm):
    class Meta:
        widgets = {
            'text_ru': CKEditorWidget(config_name='only_links'),
            'text_uk': CKEditorWidget(config_name='only_links'),
        }

class NotificationAdmin(UserFilterAdmin, TranslationAdmin):
    list_display = ('__unicode__', 'start', 'end', 'link_clicks')
    form = NotificationAdminForm
    readonly_fields = ('link_clicks',)

class MessageAdmin(admin.ModelAdmin):
    fields = ('from_user', 'to_user', 'title', 'text')
    raw_id_fields = ("from_user","to_user")
    list_display = ('id', 'from_user_link', 'to_user_link', 'title', 'reply_link', 'time','readed', 'link_clicked')
    list_display_links = ['id']
    readonly_fields = ('from_user',)
    search_fields = ('title',)
    list_filter = ('time', MessageManagerFilter, 'readed', 'link_clicked', MessageListFilter)
    date_hierarchy = 'time'

    def get_queryset(self, request):
        return super(MessageAdmin, self).get_queryset(request).prefetch_related('from_user', 'to_user')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.from_user = request.user
        obj.save()

    def reply_link(self, obj):
        query_dict = {'to_user': obj.from_user_id, 'title': obj.title}
        icon_reply = u'<img src="%s" title="ответить автору по этой теме"/>' % static('admin/img/icon-reply.png')
        return u'<a href="add/?%s">%s</a>' % (urlencode(query_dict), icon_reply)
    reply_link.allow_tags = True
    reply_link.short_description = u"Ответить"

    def from_user_link(self, obj):
        return u'<a href="?from_user__id=%d" title="фильтровать по %s">%s</a>' % (obj.from_user_id, obj.from_user, obj.from_user)
    from_user_link.allow_tags = True
    from_user_link.short_description = u"Отправитель"
    from_user_link.admin_order_field = 'from_user'

    def to_user_link(self, obj):
        return u'<a href="?to_user__id=%d" title="фильтровать по %s">%s</a>' % (obj.to_user_id, obj.to_user, obj.to_user)
    to_user_link.allow_tags = True
    to_user_link.short_description = u"Получатель"
    to_user_link.admin_order_field = 'to_user'

class MessageListAdminForm(UserFilterModelForm):
    users_count = forms.CharField(label=u'Подходящих пользователей',
                                  help_text=u'количество пользователей, соответсвующих фильтрам. значение обновляются после сохранения настроек рассылки',
                                  widget=forms.TextInput(attrs={'readonly':'readonly'}), required=False)

    class Meta:
        widgets = {
            'content': CKEditorUploadingWidget(),
        }

    def __init__(self, *args, **kwargs):
        if kwargs.get('instance'):
            initial = kwargs.get('initial', {})
            initial.update({'users_count':kwargs['instance'].get_user_queryset().count()})
            kwargs.update(initial=initial)
        super(MessageListAdminForm, self).__init__(*args, **kwargs)
        

class MessageListAdmin(UserFilterAdmin):
    form = MessageListAdminForm
    list_display = ('id', 'name', 'status', 'time', 'display_messages', 'preview')
    readonly_fields = ('status', 'time', 'from_user', 'messages_count')
    list_filter = ('status',)
    actions = ('start_real', 'start_test', 'restart')

    def get_actions(self, request):
        actions = super(MessageListAdmin, self).get_actions(request)
        if not request.user.is_superuser:
            del actions['restart']
        return actions

    def preview(self, obj):
        return u'<a href="%s">предпросмотр</a>' % reverse('admin_message_list_preview', args=[obj.id])
    preview.short_description = u'предпросмотр'
    preview.allow_tags = True

    def display_messages(self, obj):
        return u'<a href="%s?message_list=%d">%s</a>' % (reverse('admin:profile_message_changelist'), obj.id, obj.messages_count)
    display_messages.short_description = u'Отправлено сообщений'
    display_messages.allow_tags = True

    def start_real(self, request, queryset):
        self.start(request, queryset, test=False)
    start_real.short_description = u'Запустить рассылку'

    def start_test(self, request, queryset):
        self.start(request, queryset, test=True)
    start_test.short_description = u'Протестировать рассылку'

    def restart(self, request, queryset):
        message_list = queryset.get()
        if message_list.status == 'in_progress':
            import tasks
            tasks.start_message_list(message_list, message_list.from_user)
        else:
            self.message_user(request, u'Непохоже, чтобы эта рассылка зависла', level=messages.ERROR)

    restart.short_description = u'Рестартовать рассылку (использовать только для зависших рассылок!)'

    def start(self, request, queryset, test):
        message_list = queryset.get()

        if test or message_list.status == 'not_sent':
            if test:
                message_list.perform(request.user, True)
                self.message_user(request, u'Рассылка "%s" выполнена в тестовом режиме. Проверьте почту (%s) или сообщения в личном кабинете' % (message_list.name, request.user.email))
            else:
                import tasks
                tasks.start_message_list(message_list, request.user)
                self.message_user(request, u'Рассылка "%s" запущена. Чтобы узнать ее актуальное состояние, обновите страницу' % message_list.name)
        else:
            self.message_user(request, u'Нельзя запускать рассылку повторно', level=messages.ERROR)


class StatByProvince(filterspec.ProvinceRegionFilter):
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(user__region=self.value())


class StatDataFilter(admin.SimpleListFilter):
    title = u'Пользователи'
    parameter_name = 'userdata'

    def lookups(self, request, model_admin):
        return (
            ('active_ads','с автивными объявлениями'),
            ('with_plan','с тарифным планом'),
            ('money_spent','тратившие деньги'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'active_ads':
            queryset = queryset.filter(active_properties__gt=0)
        if self.value() == 'with_plan':
            queryset = queryset.filter(Q(plan_first__gt=0) | Q(plan_other__gt=0))
        if self.value() == 'money_spent':
            queryset = queryset.filter(money_spent__gt=0)

        return queryset



class StatAdmin(admin.ModelAdmin):
    raw_id_fields = ('user', )
    list_display = ('display_user', 'user_email', 'new_properties','active_properties', 'paid_properties', 'money_spent',
                    'entrances', 'ad_views', 'ad_contacts_views', 'plan_first', 'plan_other', 'time_period')
    list_filter = [StatManagerFilter, make_datetime_filter('date'), AgencyFilter, StatDataFilter, StatByProvince]
    search_fields = ('user__email', 'user__agencies__name', 'user__first_name', 'user__last_name',)
    date_hierarchy = 'date'
    list_display_links = None

    def get_queryset(self, request):
        return super(StatAdmin, self).get_queryset(request).prefetch_related('user', 'user__agencies')

    def display_user(self, obj):
        if obj.user:
            return get_user_filter_link(obj.user)
        else:
            return u'все пользователи'
    display_user.allow_tags = True
    display_user.short_description = u'Пользователь'
    display_user.admin_order_field = 'user'

    def user_email(self, obj):
        if obj.user:
            return obj.user.email
    user_email.short_description = u"E-mail"

    def time_period(self, obj):
        return obj.date.strftime('%Y.%m.%d')
    time_period.short_description = u"День"
    time_period.admin_order_field = 'date'


class StatGroupedAdmin(StatAdmin):
    list_filter = [StatManagerFilter, GroupFilter, PeriodFilter, AgencyFilter, StatDataFilter, StatByProvince]

    def time_period(self, obj):
        return obj.date.strftime('%b %Y') if obj.date else u'всё время'
    time_period.short_description = u"Месяц"
    time_period.admin_order_field = 'date'


class ManagerAdmin(admin.ModelAdmin):
    list_display = ('user_ptr', 'id', 'display_user', 'is_available_for_new_users', 'display_users_count')
    fields = ('email', 'internal_number', 'image_big', 'image_small', 'is_available_for_new_users')
    readonly_fields = ('email',)

    def display_user(self, obj):
        return get_user_filter_link(obj.user_ptr)
    display_user.allow_tags = True
    display_user.short_description = u'Пользователь менеджера'

    def display_users_count(self, obj):
        return obj.users_count
    display_users_count.short_description = u'Кол-во пользователей'

    def get_queryset(self, request):
        return super(ManagerAdmin, self).get_queryset(request).annotate(users_count=Count('managed_users')).prefetch_related(
            'user_ptr', 'user_ptr__realtors', 'user_ptr__realtors__agency'
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

admin.site.register(Ban, BanAdmin)
admin.site.register(Stat, StatAdmin)
admin.site.register(StatGrouped, StatGroupedAdmin)
admin.site.register(EmailChange, EmailChangeAdmin)
admin.site.register(Message, MessageAdmin)
admin.site.register(MessageList, MessageListAdmin)
admin.site.register(Notification, NotificationAdmin)
admin.site.register(Manager, ManagerAdmin)