# -*- coding: utf-8 -*-
from django.db import models, IntegrityError
from django.db.models import F, Count, Sum, Avg, Q
from django.db.models.signals import post_save, pre_save, post_delete
from django.conf import settings
from django.dispatch import receiver
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.http.request import QueryDict
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from django.contrib.auth import login
from django.contrib.postgres.fields import ArrayField

from pytils.numeral import get_plural
from registration.signals import user_registered, user_activated
from bs4 import BeautifulSoup

from ad import choices as ad_choices
from ad.models import Region
from ad.forms import PROPERTY_TYPE_SEARCH_CHOICES
from ad import phones
from agency.models import Agency, Realtor, Lead, LeadHistoryEvent
from paid_services.models import Transaction, FILTER_USER_BY_PLAN_CHOICES, filter_user_by_plan
from custom_user.models import User

import re
import os
import json
import math
import hashlib
import random
import urllib
import datetime
from collections import defaultdict, Counter

# формат params должен быть аналогичен результату GET.lists(), т.е. [ (key, ['val1',]), ]
def get_sorted_urlencode(params):
    sorted_params = []
    for (key, values) in params:
        for v in values:
            if isinstance(v, unicode):
                v = v.encode('utf8')
            elif isinstance(v, str):
                v.decode('utf8')
            sorted_params.append( (key, v) )

    return urllib.urlencode(sorted(sorted_params))

def convert_dict_to_lists(dict_):
    lists = []

    for key, value in dict_.items():
        if isinstance(value, list):
            lists.append((key, value))
        else:
            lists.append((key, [value]))

    return lists


MESSAGE_SUBJECT_CHOICES = (
    ('details', _(u'Хочу узнать некоторые детали')),
    ('counteroffer', _(u'Хочу предложить другую цену')),
    # ('examination', _(u'Хочу посмотреть квартиру')),
)

TEXT_TYPE_CHOICES = (
    ('text', _(u'plain text') ),
    ('html', _(u'HTML') ),
)


class Message(models.Model):
    root_message = models.ForeignKey('self', verbose_name=_(u'первое сообщения для группирки в диалог'), null=True, blank=True)
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'отправитель'), db_index=True, related_name='messages_from')
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'получатель'), db_index=True, related_name='messages_to')
    title = models.CharField(u'заголовок', max_length=255)
    basead = models.ForeignKey('ad.BaseAd', verbose_name=_(u'объявление'), null=True, blank=True, on_delete=models.SET_NULL)
    message_list = models.ForeignKey('MessageList', verbose_name=_(u'рассылка'), null=True, blank=True, related_name='messages')
    text = models.TextField(_(u'текст сообщения'), null=True, blank=True)
    text_type = models.CharField(u'формат текста сообщения', max_length=5, default='text', choices=TEXT_TYPE_CHOICES)
    time = models.DateTimeField(_(u'время отправления'), auto_now=False, default=datetime.datetime.now)
    readed = models.BooleanField(_(u'прочитано'), default=False)
    link_clicked = models.BooleanField(_(u'переход по ссылке'), default=False)
    hidden_for_user = models.ManyToManyField(settings.AUTH_USER_MODEL, verbose_name=_(u'скрыть переписку для юзера'))
    subject = models.CharField(u'тема', max_length=50, null=True, choices=MESSAGE_SUBJECT_CHOICES)

    class Meta:
        verbose_name = u'внутреннее сообщение'
        verbose_name_plural = u'внутренние сообщения'

    def __unicode__(self):
        return u'%s - %s: %s' % (self.from_user, self.to_user, self.title)

    def send_email(self):
        if self.to_user.email:
            checks = [
                self.message_list and self.to_user.subscribe_news,  # Проверка на новостные рассылки
                not self.message_list and self.to_user.subscribe_info  # Проверка на уведомления
            ]
            if any(checks):
                from django_hosts.resolvers import reverse

                if self.to_user.get_own_agency():
                    message_url = '%s#dialogue/%d/%d' % (reverse('agency_admin:crm'), self.root_message_id, self.pk)
                else:
                    message_url = '%s#%s' % (
                        reverse('messages:inbox'),
                        reverse('messages:reply', kwargs={'dialog_id': self.root_message.id})
                    )

                translation.activate('ru')

                unsubscribe_hash = u'Unsubscribe %s, please' % self.to_user.email
                unsubscribe_hash = hashlib.md5(unsubscribe_hash.encode('utf-8')).hexdigest()[10:22]
                unsubscribe_url = '%s?email=%s&hash=%s' % (
                    reverse('messages:unsubscribe', args=[]),
                    self.to_user.email,
                    unsubscribe_hash
                )

                subject = u'Mesto.ua: у вас новое сообщение'
                content = render_to_string('profile/messages/email.jinja.html', {
                    'message': self,
                    'message_url': message_url,
                    'unsubscribe_url': unsubscribe_url
                })
                self.to_user.send_email(subject, content)


@receiver(pre_save, sender=Message)
def find_root_message_for_messsage_list(instance, **kwargs):
    if instance.message_list and not instance.root_message:
        instance.root_message = Message.objects.filter(to_user=instance.to_user, message_list__isnull=False).first()


@receiver(post_save, sender=Message)
def new_message(sender, instance, created, **kwargs):
    if created:

        # root_message используется для последующей группировке по диалогам
        if not instance.root_message:

            instance.root_message = instance
            instance.save()

            if instance.basead:
                ad_user = instance.basead.ad.user
                realtors = instance.basead.ad.user.realtors.all()
                if len(realtors) > 1:
                    raise Exception('Cannot create a lead, ad owner (user #%d) has %d agencies' % (instance.basead.ad.user.id, len(realtors)))
                elif len(realtors) == 1:
                    lead = ad_user.find_lead(client=instance.from_user)
                    if not lead:
                        lead = Lead.objects.create(client=instance.from_user, user=instance.basead.ad.user,
                                                            name=instance.from_user.get_public_name(),
                                                            basead=instance.basead)

                        # передавать id сообщения будет сложно и некрасиво, поэтому тут, а не в post_save :(
                        # time=now - для правильной хронологии, ведь сообщение приходит раньше, чем создается лид
                        LeadHistoryEvent(lead=lead, event={'receive_first_message': instance.id}).save()

        else:
            # Снимаем метку о скрытом диалоге для участников диалога
            instance.root_message.hidden_for_user.remove(instance.from_user)
            instance.root_message.hidden_for_user.remove(instance.to_user)

        cache.delete('new_messages_for_user%d' % instance.to_user.id)
        instance.send_email()

        # отправка смс и пуш уведомлений
        if not instance.message_list:
            text = u'У Вас новое сообщение! Для того, чтобы прочесть его - перейдите в Ваш личный кабинет на сайте www.mesto.ua'
            instance.to_user.send_notification(text, sms_numbers_limit=1)


FILTER_USER_BY_TYPE_CHOICES = (
    ('person', u'Только частные лица'),
    ('agency', u'Только агентства'),
)


class UserFilterModel(models.Model):
    class Meta:
        abstract = True

    filter_user_by_type = models.CharField(u'фильтр юзеров по типу', max_length=20, blank=True, null=True, choices=FILTER_USER_BY_TYPE_CHOICES)
    filter_user_by_region = models.ForeignKey('ad.Region', verbose_name=u'фильтр юзеров по региону', blank=True, null=True, limit_choices_to={'kind': 'province', 'parent_id': 1})
    filter_user_by_ads_min = models.PositiveIntegerField(u'фильтр юзеров по объяв. - мин.', blank=True, null=True)
    filter_user_by_ads_max = models.PositiveIntegerField(u'фильтр юзеров по объяв. - макс.', blank=True, null=True)
    filter_user_by_plan = models.CharField(u'фильтр юзеров по тарифам', max_length=20, blank=True, null=True, choices=FILTER_USER_BY_PLAN_CHOICES)
    filter_user_by_email = ArrayField(models.EmailField(), verbose_name=u'фильтр юзеров по e-mail', blank=True, null=True)
    filter_user_by_id = ArrayField(models.PositiveIntegerField(), verbose_name=u'фильтр юзеров по ID', blank=True, null=True)

    def get_user_queryset(self):
        queryset = User.objects.filter(is_active=True)
        if self.filter_user_by_type == 'person':
            queryset = queryset.exclude(realtors__is_active=True)
        if self.filter_user_by_type == 'agency':
            queryset = queryset.filter(realtors__is_active=True)
        if self.filter_user_by_region:
            queryset = queryset.filter(region=self.filter_user_by_region)
        if self.filter_user_by_ads_min is not None:
            queryset = queryset.filter(ads_count__gte=self.filter_user_by_ads_min)
        if self.filter_user_by_ads_max is not None:
            queryset = queryset.filter(ads_count__lte=self.filter_user_by_ads_max)
        if self.filter_user_by_email:
            queryset = queryset.filter(email__in=self.filter_user_by_email)
        if self.filter_user_by_plan:
            queryset = filter_user_by_plan(queryset, self.filter_user_by_plan)
        if self.filter_user_by_id:
            queryset = queryset.filter(id__in=self.filter_user_by_id)
        return queryset


MESSAGE_LIST_STATUS_CHOICES = (
    ('not_sent', _(u'не отправлена')),
    ('in_progress', _(u'выполняется')),
    ('done', _(u'завершена')),
)


class MessageList(UserFilterModel):
    name = models.CharField(u'название рассылки', max_length=100)
    title = models.CharField(u'заголовок', max_length=255)
    content = models.TextField(u'текст сообщения')
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=u'отправитель', blank=True, null=True)
    status = models.CharField(u'статус', max_length=20, choices=MESSAGE_LIST_STATUS_CHOICES, default='not_sent')
    time = models.DateTimeField(u'время рассылки', blank=True, null=True)
    messages_count = models.PositiveIntegerField(_(u'отправленных сообщений'), default=0)

    filter_user_active_for_last_months = models.PositiveIntegerField(u'фильтр юзеров активных за последние Х месяцев', blank=True, null=True)

    class Meta:
        verbose_name = u'рассылка сообщений'
        verbose_name_plural = u'рассылки сообщений'

    def __unicode__(self):
        return self.name

    def perform(self, from_user, test):
        message_content_parameters = {'title': self.title, 'text': self.content, 'text_type': 'html'}
        if test:
            recipients = [from_user]
            Message.objects.create(message_list=self, from_user=from_user, to_user=from_user, **message_content_parameters)
            self.update_messages_count()
        else:
            self.from_user = from_user
            self.time = datetime.datetime.now()
            self.status = 'in_progress'
            self.save()

            recipients = self.get_user_queryset().exclude(id__in=self.messages.values('to_user'))

            for count, to_user in enumerate(recipients, start=1):
                # может быть get_or_create и не спасет при параллельном запуске
                Message.objects.get_or_create(message_list=self, from_user=from_user, to_user=to_user,
                                              defaults=message_content_parameters)
                if count % 50 == 0 or count == len(recipients):
                    self.update_messages_count()

            self.status = 'done'
            self.save()

    def update_messages_count(self):
        self.messages_count = self.messages.count()
        self.save()

    def get_user_queryset(self):
        queryset = super(MessageList, self).get_user_queryset()
        if self.filter_user_active_for_last_months:
            queryset = queryset.filter(last_action__gt=datetime.datetime.now() - datetime.timedelta(days=30*self.filter_user_active_for_last_months))
        return queryset


class SavedAd(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=('User'), db_index=True, related_name='saved_ads')
    basead = models.ForeignKey('ad.BaseAd', verbose_name=_(u'недвижимость'), related_name='saved_ads')
    created = models.DateTimeField(_(u'время создания'), auto_now_add=True)
    
    class Meta:
        verbose_name = u'сохр. объявление'
        verbose_name_plural = u'сохр. объявления'

# хранит в кеше id сохраненных объявлений, чтобы отображать активность иконки favorite
@receiver(post_save, sender=SavedAd)
@receiver(post_delete, sender=SavedAd)
def update_saved_properties_for_user(sender=None, instance=None, user_id=None, **kwargs):
    if not user_id and instance:
        user_id = instance.user_id
    saved_properties_ids = SavedAd.objects.filter(user=user_id).values_list('basead_id', flat=True)
    cache.set('saved_properties_for_user%d' % user_id, saved_properties_ids, None)


from jsonfield import JSONField

class SavedSearch(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=('User'), db_index=True, related_name='saved_searches')
    created = models.DateTimeField(_(u'время создания'), auto_now=False, auto_now_add=True)
    subscribe = models.BooleanField(_(u'подписка '), default=False)
    region = models.ForeignKey('ad.Region', verbose_name=u'город')
    deal_type = models.CharField(u'тип операции', choices=ad_choices.DEAL_TYPE_CHOICES, max_length=20)
    property_type = models.CharField(u'тип недвижимости', choices=PROPERTY_TYPE_SEARCH_CHOICES, max_length=20)
    query_parameters = JSONField(u'GET-параметры', default=dict)

    class Meta:
        verbose_name = u'сохр. поиск'
        verbose_name_plural = u'сохр. поиски'

    @staticmethod
    def extract_query_parameters_from_querydict(querydict):
        from ad.forms import PropertySearchForm

        searchform_fields = PropertySearchForm.base_fields.keys()
        searchform_multiple_fields = PropertySearchForm.get_multiple_fields()

        query_parameters = {}

        for name, list_ in querydict.lists():
            if name in searchform_fields and name not in ['deal_type', 'property_type']:
                if name in searchform_multiple_fields:
                    query_parameters[name] = list_
                else:
                    query_parameters[name] = list_[0]

        return query_parameters

    def get_room_filter(self):
        rooms = self.query_parameters.get('rooms') or []
        if len(rooms) == 1:
            return get_plural(int(rooms[0]), (_(u"комната"), _(u"комнаты"), _(u"комнат")), u'')
        elif rooms:
            return _(u'%s комнат') % u'-'.join(rooms)

    def get_price_filter(self):
        price_filter_text_parts = []
        if 'price_from' in self.query_parameters or 'price_to' in self.query_parameters:
            if 'price_from' in self.query_parameters:
                price_filter_text_parts.append(u'от %s' % self.query_parameters['price_from'])
            if 'price_to' in self.query_parameters:
                price_filter_text_parts.append(u'до %s' % self.query_parameters['price_to'])
            currency = self.query_parameters.get('currency', 'UAH').upper()
            currency_label = dict(ad_choices.CURRENCY_CHOICES).get(currency)
            price_filter_text_parts.append(currency_label)
        return u' '.join(price_filter_text_parts)

    def __unicode__(self):
        name = u'%s' % self.region.text.replace(u'Украина, ', '')
        if 'with_image' in self.query_parameters:
            name += u', только с фото'
        if 'without_commission' in self.query_parameters:
            name += u', без комиссии'
        return mark_safe(name)

    def get_full_title(self):
        parts = [self.get_deal_type_display(), self.get_property_type_display(), self.get_room_filter(),
                 self.get_price_filter(), self.region.text.replace(u"Украина, ", "")]
        return u', '.join(map(unicode, filter(None, parts)))

    def get_full_url(self):
        query_string = get_sorted_urlencode(convert_dict_to_lists(self.query_parameters))
        return self.region.get_deal_url(self.deal_type, self.property_type) + ('?'+query_string if query_string else '')


@receiver(post_save, sender=SavedSearch)
@receiver(post_delete, sender=SavedSearch)
def delete_cached_savedsearch_urls(sender, instance, **kwargs):
    cache.delete('saved_searches_for_user%d' % instance.user.id)


class Ban(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'юзер'), db_index=True, related_name='bans')
    reason = models.TextField(_(u'причина бана, которую видит пользователь'))
    expire_date = models.DateField(_(u'бан истекает'), auto_now=False, auto_now_add=False)
    
    class Meta:
        verbose_name = u'бан пользователей'
        verbose_name_plural = u'баны пользователей'
        
    def __unicode__(self):
        return _(u'%(email)s до %(expire_date)s') % {'email': self.user.email, 'expire_date': str(self.expire_date)[:10]}


@receiver(post_save, sender=Ban)
@receiver(post_delete, sender=Ban)
def clear_ban_cache(sender, instance, **kwargs):
    cache.delete('banned_users')

        
CHANGE_STATUS_CHOICES = (
    ('inactive', _(u'неактивно')),
    ('confirmed', _(u'подтверждено')),
    ('cancelled', _(u'отменено')),
)

class EmailChange(models.Model):
    created = models.DateTimeField(_(u'создано'), auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'Пользователь'))
    old_email = models.EmailField(_(u'старый email'), blank=True, null=True)
    new_email = models.EmailField(_(u'новый email'))
    confirmation_key = models.CharField(_(u'код подтверждения'), max_length=40)
    status = models.CharField(_(u'статус'), max_length=20, default='inactive', choices=CHANGE_STATUS_CHOICES)
    
    class Meta:
        verbose_name = u'изменение email'
        verbose_name_plural = u'изменения email'
        
    def __unicode__(self):
        return u'%s, %s -> %s' % (self.user, self.old_email, self.new_email)

    def create_key(self):
        salt = hashlib.sha1(str(random.random())).hexdigest()[:5]
        self.confirmation_key = hashlib.sha1(salt + self.new_email).hexdigest()
        
    def send_mail(self, site):
        context = {'site': site, 'change': self}
        subject = render_to_string('profile/change_email_subject.txt', context)
        subject = ''.join(subject.splitlines())
        message = render_to_string('profile/change_email.txt', context)
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [self.new_email])


class StatBase(models.Model):
    date = models.DateField(_(u'период'), auto_now=False, auto_now_add=False, blank=True, null=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'пользователь'), blank=True, null=True)
    new_properties = models.PositiveIntegerField(_(u'новых объяв.'),default=0)
    active_properties = models.PositiveIntegerField(_(u'активных объяв.'),default=0)
    paid_properties = models.PositiveIntegerField(_(u'VIP-размещ.'),default=0)
    money_spent = models.PositiveIntegerField(_(u'потрачено гривен'),default=0)
    entrances = models.PositiveIntegerField(_(u'входов на сайт'),default=0)
    ad_views = models.PositiveIntegerField(_(u'просмотров объявлений'), default=0)
    ad_contacts_views = models.PositiveIntegerField(_(u'просмотров контактов'), default=0)
    plan_first = models.PositiveIntegerField(_(u'план Первый'), default=0)
    plan_other = models.PositiveIntegerField(_(u'прочие планы'), default=0)

    class Meta:
        abstract = True
        verbose_name = u'статистика пользователя'
        verbose_name_plural = u'статистика пользователей'


class Stat(StatBase):
    class Meta:
        unique_together = (("date", "user"),)
        verbose_name = u'статистика пользователя за сутки'
        verbose_name_plural = u'статистика пользователей за сутки'

    @classmethod
    def write_stat(cls, user, name):
        """ Учет события в статистике пользователя

        Keyword arguments:
        name -- наименование поля в котором подсчитываем значения

        """
        today = datetime.date.today()
        updated = cls.objects.filter(user=user, date=today).update( **{name:F(name)+1} )
        if not updated:
            try:
                cls(**{'user':user, 'date':today, name:1}).save()
            except IntegrityError:
                pass

    @classmethod
    def collect_day_data(cls, period_start):
        from django.db.models import Q
        from ad.models import Ad, ViewsCount
        from paid_services.models import VipPlacement, UserPlan
        import collections

        if isinstance(period_start, datetime.datetime):
            period_start = period_start.date()

        period_end = period_start + datetime.timedelta(days=1)
        time_range = (period_start, period_end)

        users_stat = collections.defaultdict(dict)
        period_stats = collections.Counter()
        fields = {
            'new_properties': [Ad, 'user', {'created__range':time_range}],
            'active_properties': [Ad, 'user', {'status':1}],
            'paid_properties': [VipPlacement, 'basead__ad__user', {'since__lte':period_end, 'until__gte':period_start}],
            'money_spent': [Transaction, 'user', {'time__range':time_range}, Sum('amount')],
            'ad_views': [ViewsCount, 'basead__ad__user', {'date__range':time_range}, Sum('detail_views')],
            'ad_contacts_views': [ViewsCount, 'basead__ad__user', {'date__range':time_range}, Sum('contacts_views')],
            'plan_first': [UserPlan, 'user', {'start__lte':period_end, 'end__gte':period_start, 'plan_id':1}],
            'plan_other': [UserPlan, 'user', {'start__lte':period_end, 'end__gte':period_start, 'plan_id__gt':1}],
        }

        # если подсчет идет не для ближайшего времени
        if (datetime.date.today() - period_start).days > 5:
            # лучше вообще пропускать подсчет активных объявлений в таких случаях
            del fields['active_properties']
            # но в крайнем случае:
            # fields['active_properties'][2].update({'expired__range':time_range})

        for key, field in fields.items():
            filter = field[2]
            filter['%s__isnull' % field[1]] = False

            objects = field[0].objects.filter(**filter).values(field[1]).order_by()

            # TODO: навести порядок в TRANSACTION_TYPE_CHOICES
            if field[0] == Transaction:
                objects = objects.filter(Q(amount__lt=0) | Q(type__in=[3,31,32]))

            if len(field) > 3:
                cnts = objects.annotate(count=field[3])
            else:
                cnts = objects.annotate(count=Count(field[1]))

            for cnt in cnts:
                user_id = cnt[field[1]]
                users_stat[user_id][key] = math.fabs(cnt['count'])

                period_stats[key] += math.fabs(cnt['count'])

        # обновляем статистику по пользователям за выбранный день
        for user_id, fields in users_stat.items():
            try:
                stat, create = Stat.objects.get_or_create(user_id=user_id, date=period_start)
            except Stat.MultipleObjectsReturned:
                stats = Stat.objects.filter(user_id=user_id, date=period_start)
                stat = stats[0]
                stats.exclude(pk=stat.pk).delete()

            for key, value in fields.items():
                setattr(stat, key, value)
            stat.save()


class StatGrouped(StatBase):
    class Meta:
        unique_together = (("date", "user"),)
        verbose_name = u'статистика пользователя по периодам'
        verbose_name_plural = u'статистики пользователей по периодам'
        ordering = ('-date',)

    @classmethod
    def group_statistics(cls, day):
        import calendar

        day_in_month = calendar.monthrange(day.year,day.month)[1]
        period_start = datetime.date(day=1, month=day.month, year=day.year)
        period_end = period_start + datetime.timedelta(days=day_in_month - 1)
        date_range = (period_start, period_end)

        sum_fields = ['new_properties', 'active_properties', 'paid_properties', 'money_spent', 'entrances',
                      'ad_views', 'ad_contacts_views',  'plan_first', 'plan_other']
        avg_fields = ['active_properties', 'paid_properties']

        fields = {field: Sum(field) for field in sum_fields}
        fields.update({field: Avg(field) for field in avg_fields})

        # объединяем сырые данные в сгруппированные данные по месяцам
        # т.е. беремся данные с Stat за каждый день, и перекидываем их в StatGrouped за первым день месяца
        all_user_month_stat = Counter()
        results = Stat.objects.filter(date__range=date_range).values('user_id').annotate(**fields)
        for row in results:
            StatGrouped.objects.update_or_create(user_id=row['user_id'], date=period_start, defaults=row)
            for field in fields.keys():
                all_user_month_stat[field] += row[field]

        StatGrouped.objects.update_or_create(user=None, date=period_start, defaults=all_user_month_stat)

        # объединяем сгруппированные ежемесячные данные
        # т.е. беремся данные StatGrouped за каждый месяц, и перекидываем их в StatGrouped с date=None
        results = StatGrouped.objects.filter(user__isnull=False, date__isnull=False).values('user_id').annotate(**fields)
        for row in results:
            StatGrouped.objects.update_or_create(user_id=row['user_id'], date=None, defaults=row)

    # обновление статистики за предыдущие месяца, запускать можно вручную из консоли
    @classmethod
    def update_outdated_stats(cls, day):
        import calendar
        import time
        from ad.models import ViewsCount

        start = time.time()

        day_in_month = calendar.monthrange(day.year,day.month)[1]
        period_start = datetime.date(day=1, month=day.month, year=day.year)
        period_end = period_start + datetime.timedelta(days=day_in_month - 1)
        date_range = (period_start, period_end)
        print 'update outdates stats from %s to %s' % (period_start.strftime('%Y-%m-%d'), period_end.strftime('%Y-%m-%d'))

        # сбрысываем старые данные просмотров в статистике
        updated_rows = Stat.objects.filter(date__range=date_range).update(ad_views=0, ad_contacts_views=0)
        print '  clear outdated stats, %d rows - %.2f' % (updated_rows, time.time() - start)

        # подсчитываем просмотры объявлений и контактов
        data = ViewsCount.objects.filter(date__range=date_range).values('basead__ad__user').annotate(
            detail_views=Sum('detail_views'),
            contacts_views=Sum('contacts_views'),
        )
        for i, row in enumerate(data):
            Stat.objects.update_or_create(date=period_start, user_id=row['basead__ad__user'], ad_views=row['detail_views'])
            Stat.objects.update_or_create(date=period_start, user_id=row['basead__ad__user'], ad_contacts_views=row['contacts_views'])
        print '  processed %s row of grouped ViewsCount - %.2f' % (len(data), time.time() - start)

        # обновляем сгруппированные данные из ежедневных
        cls.group_statistics(day)
        print '  new everyday stats have been grouped - %.2f' % (time.time() - start)


@receiver(user_registered)
def create_profile(sender, user, request, **kwargs):
    # Присваиваем пользователю язык, который был активен на момент создания профиля
    # не вынесено в отдельный метод, т.к. необходимо присваивать язык до отправки писем
    user.language = translation.get_language()
    user.save()


@receiver(user_activated)
def login_on_activation(sender, user, request, **kwargs):
    user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, user)

    # После логина, показываем приветственный попап для застройщика
    request.session['show_welcome_popup_for_developer'] = False

    if hasattr(user, 'developer'):
        request.session['show_welcome_popup_for_developer'] = True


# функционал реализован по просьбе Виталии от 09.09.2015 из-за юзеров с емейлами *unital*
@receiver(user_registered)
def check_annoing_user(sender, user, request, **kwargs):
    if request.META['REMOTE_ADDR'] in settings.MESTO_SUSPICIOUS_IP:
        from utils.templatetags.domain_url import domain_url

        message = u'Зарегистрирован новый пользователь %(user)s с IP-адреса %(ip)s.\n\n' \
                  u'%(link)s' % {
            'user': user,
            'ip': request.META['REMOTE_ADDR'],
            'link': '%s?id=%s' % (domain_url('admin:custom_user_user_changelist'), user.pk)
        }
        send_mail('Mesto.UA: Регистрация подозрительного пользователя', message, settings.DEFAULT_FROM_EMAIL,
                  ['zeratul268@gmail.com', 'info@mesto.ua'], fail_silently=False)


def get_banned_users():
    banned_users = cache.get('banned_users')
    if banned_users is None:
        banned_users = list(set(Ban.objects.filter(expire_date__gte=datetime.date.today()).values_list('user', flat=True)))
        cache.set('banned_users', banned_users, 3600)  # бан обновляется каждый час
    return banned_users


class Notification(UserFilterModel):
    class Meta:
        verbose_name = u'настраиваемое уведомление'
        verbose_name_plural = u'настраиваемые уведомления'

    name = models.CharField(u'название', max_length=100, help_text=u'отображается только в админке')
    text = models.TextField(u'текст')
    start = models.DateTimeField(u'начало', default=datetime.datetime.now)
    end = models.DateTimeField(u'окончание', null=True, blank=True)
    link_clicks = models.PositiveIntegerField(u'клики по ссылкам', default=0)
    show_timer = models.BooleanField(_(u'выводить таймер обратного отсчета'), default=False)

    def __unicode__(self):
        return self.name

    def get_cookie_to_close(self):
        return 'notification_%d_closed' % self.id

    def render_text(self):
        soup = BeautifulSoup(self.text, 'html.parser')
        for a in soup.find_all('a'):
            if 'href' in a.attrs:
                querydict = QueryDict(mutable=True)
                querydict.update(notification=self.id, url=a['href'])
                wrapped_url = '%s?%s' % (reverse('notification_link_click'), querydict.urlencode())
                a['href'] = wrapped_url
        return unicode(soup)

@receiver(post_save, sender=Notification)
def clear_notification_cached_users(sender, instance, **kwargs):
    cache.delete('notification_%d_users' % instance.id)

class InterruptedCheckoutNotification(object):
    def __init__(self, url):
        self.url = url

    def render_text(self):
        return u'Только что был пополнен ваш баланс. <a href="%s">Завершите процесс покупки услуг</a>.' % self.url

    def get_cookie_to_close(self):
        return 'notification_interrupted_checkout_closed'


class Manager(User):
    class Meta:
        verbose_name = u'менеджер'
        verbose_name_plural = u'менеджеры'

    # добавляем это поле вручную, чтобы указать related_name='manager_ptr',
    # иначе по умолчанию будет related_name='manager' и возникнет конфликт с User.manager
    user_ptr = models.OneToOneField(settings.AUTH_USER_MODEL, parent_link=True, primary_key=True, related_name='manager_ptr')
    internal_number = models.CharField(u'внутренний номер', max_length=10, blank=True, null=True)
    image_big = models.ImageField(u'большое изображение', upload_to='upload/manager', blank=True, null=True)
    image_small = models.ImageField(u'малое изображение', upload_to='upload/manager', blank=True, null=True)
    is_available_for_new_users = models.BooleanField(u'используется для новых пользователей', default=True)

    @staticmethod
    def create_from_user(user):
        manager = Manager(user_ptr=user)
        manager.__dict__.update(user.__dict__)
        manager.save()
        return manager

