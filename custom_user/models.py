# coding: utf-8
import logging
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q, Count
from django.db import transaction as db_transaction
from django.contrib.auth.models import AbstractUser
from django.utils import translation
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.dispatch import receiver
from django.db.models.signals import post_delete, post_save, m2m_changed
from django.conf import settings

from ad.phones import pprint_phones
from ad.models import Region, Ad
from newhome.models import Flat
from paid_services.models import Transaction, UserPlan, Plan, InsufficientFundsError
from ppc.models import send_user_proxynumbers_to_asterisk
from utils.email import make_utm_dict, make_ga_pixel_dict
from utils.image_signals import post_save_clean_image_file, post_delete_clean_image_file
from utils.sms import clean_numbers_for_sms
from utils.currency import get_currency_rates

from dirtyfields import DirtyFieldsMixin

import collections
import os.path
import uuid
import datetime
import random
import string
import re


def make_upload_path(user, filename):
    (root, ext) = os.path.splitext(filename)
    return 'upload/user/%s%s' % (uuid.uuid4().hex, ext)

# должно совпадать с settings.MODELTRANSLATION_LANGUAGES
LANGUAGE_CHOICES = (
    ('ru', _(u'Русский')),
    ('uk', _(u'Украинский')),
    ('hu', _(u'Венгерский')),
)


def update_region(user=None):
    # для областей get_children_ids() возвращает большие списки - нужна оптимизация с set()
    provinces_children = {province.id: set(province.get_children_ids()) for province in Region.get_provinces()}

    counters = collections.defaultdict(collections.Counter)

    if user:
        query = Ad.objects.filter(user=user)
    else:
        query = Ad.objects.filter(user__isnull=False)

    for row in query.values('user', 'region').annotate(ads_count=Count('region')).order_by():
        for province_id, children in provinces_children.iteritems():
            if row['region'] in children:
                counters[row['user']][province_id] += row['ads_count']

    updated = 0
    for user in User.objects.filter(id__in=counters.keys()):
        common_region = counters[user.id].most_common(1)[0][0]
        if user.region_id != common_region:
            user.region_id = common_region
            user.save()
            updated += 1

    return updated

PROFILE_TYPES = (
    ('user_profile', _(u'Частное лицо')),
    ('realtor', _(u'Риелтор')),
    ('developer', _(u'Застройщик'))
)

GENDER_CHOICES = (
    (None, _(u'Не определен')),
    ('male', _(u'Мужской')),
    ('female', _(u'Женский')),
)

SPCRM_CATEGORY_CHOICES = [(category,) * 2 for category in ['A', 'B', 'C', 'D']]

def get_default_language():
    return settings.LANGUAGE_CODE


class User(AbstractUser, DirtyFieldsMixin):
    image = models.ImageField(_(u'изображение'), upload_to=make_upload_path, blank=True, null=True)
    city = models.CharField(_(u'город'), blank=True, max_length=50)
    phones = models.ManyToManyField('ad.Phone', through='custom_user.UserPhone', verbose_name=_(u'телефоны'), related_name='users')
    region = models.ForeignKey('ad.Region', verbose_name=_(u'регион'), blank=True, null=True, limit_choices_to = {'parent':1, 'kind': 'province'})
    manager = models.ForeignKey(
        'profile.Manager', verbose_name=_(u'менеджер'),
        related_name='managed_users', blank=True, null=True,
        help_text=_(u'менеджер, зарегистрировавший этого пользователя')
    )
    ads_count = models.PositiveIntegerField(_(u'количество активных объявлений'), default=0, db_index=True)
    show_email = models.BooleanField(_(u'публиковать e-mail'), default=False)
    show_message_button = models.BooleanField(_(u'принимать сообщения со страницы объявлений'), default=True)
    subscribe_info = models.BooleanField(_(u'получать служебные сообщения (рекомендуется)'), default=True)
    subscribe_news = models.BooleanField(_(u'читать новости сайта'), default=True)
    receive_sms = models.BooleanField(_(u'получать SMS-уведомления'), default=True)
    language = models.CharField(_(u'язык'), choices=LANGUAGE_CHOICES, default=get_default_language, max_length=2)
    gender = models.CharField(_(u'пол'), choices=GENDER_CHOICES, max_length=6, blank=True, null=True)

    loyalty_started = models.DateField(_(u'дата начала программы лояльности'), blank=True, null=True)

    ip_addresses = ArrayField(models.GenericIPAddressField(_(u'последние IP адреса')), size=10, blank=True, default=[])
    last_action = models.DateTimeField(_(u'последняя активность'), blank=True, null=True)

    spcrm_category = models.CharField(u'категория в SalesPlatform CRM', max_length=1, choices=SPCRM_CATEGORY_CHOICES, blank=True, null=True)

    def get_loyalty_bonus(self, loyalty_date=None):
        """
        Возвращаем размер в процентах дополнительного бонуса по программе лояльности
        :return:
        """

        if not self.loyalty_started:
            return 0

        if loyalty_date is None:
            loyalty_date = datetime.date.today()

        months = (loyalty_date - self.loyalty_started).days / 30
        if months < 0:
            return 0

        elif months <= 6:
            return 0.05

        elif months <= 12:
            return 0.1

        return 0.15

    @property
    def uuid(self):
        """
        Генерация UUID для Google Analytics.
        При необходимости конвертации UUID -> User.ID данную функцию заменить на UUIDField
        """
        return uuid.uuid3(uuid.NAMESPACE_OID, str(self.id))

    # Переопределение метода, чтобы метод get_users() из django.contrib.auth.forms.PasswordResetForm мог вернуть
    # пользователей с неюзабельными паролями. Например тех, кто регался через соцсети без пароля
    def has_usable_password(self):
        return True

    def get_region_host(self):
        if self.region_id:
            return self.region.get_main_city().get_host()

    @staticmethod
    def get_user_ids_with_active_plan():
        user_ids = cache.get('user_ids_with_active_plan')
        if not user_ids:
            user_ids = set(UserPlan.objects.filter(end__gt=datetime.datetime.now(), is_active=True).values_list('user', flat=True))
            cache.get('user_ids_with_active_plan', user_ids, 60)
        return user_ids

    def has_active_plan(self):
        return self.id in User.get_user_ids_with_active_plan()

    def __unicode__(self):
        return self.get_full_name() or self.email or ('#%d' % self.id)

    def get_public_name(self):
        return self.get_full_name() or self.masked_email() or (u'%s #%d' % (_(u'Пользователь'), self.id))

    # возвращает email в виде an***ov@gmail.com
    def masked_email(self):
        if self.email:
            parts = self.email.split('@')
            return '%s***%s@%s' % (parts[0][:2], parts[0][-2:], parts[1])

    def get_balance(self, force=False):
        # получаем баланс пользователя, кеш хранится бесконечно, т.к. сбрасывается в
        # сигналах Transaction post_save/post_delete
        cache_key = 'user%d_balance' % self.id
        balance = cache.get(cache_key)
        if balance is None or force:
            balance = sum([t.amount for t in self.transactions.all()])
            cache.set(cache_key, balance, None)
        return balance

    def get_realtor(self):
        for realtor in self.realtors.all():
            if realtor.is_active:
                return realtor

    def get_realtor_admin(self):
        for realtor in self.realtors.all():
            if realtor.is_active and realtor.is_admin:
                return realtor

    def get_own_agency(self):
        return self.agencies.filter(realtors__is_active=True, realtors__is_admin=True).first()

    def get_agency(self):
        realtor = self.get_realtor()
        if realtor:
            return realtor.agency

    @db_transaction.atomic
    def create_agency(self):
        if self.is_developer():
            raise Exception('Cannot create agency: user #%d is developer' % self.id)
        elif self.get_agency():
            raise Exception('Cannot create agency: user #%d has an agency already' % self.id)
        else:
            from agency.models import Realtor, Agency
            agency = Agency.objects.create(name=unicode(self))
            self.realtors.create(agency=agency, is_active=True, is_admin=True)

    def create_developer(self):
        if self.is_developer():
            raise Exception('Cannot create developer: user #%d is developer already' % self.id)
        elif self.get_agency():
            raise Exception('Cannot create developer: user #%d has an agency' % self.id)
        else:
            from newhome.models import Developer
            Developer.objects.create(user=self, name=unicode(self), is_cabinet_enabled=True)

            # код от А.Миленко (ранее вызывался при *регистрации* юзера-застройщика), немного упрощенный:

            # При создании нового застройщика, отправляю письмо ответственному лицу
            # Данный функционал НЕ вынесен в сигнал, т.к. нужно чтобы при возможности был телефон нового застройщика
            # todo: вынести в Notification и сигналы
            from django.core.mail import EmailMessage, send_mail
            from django.contrib.auth.models import Permission
            from django.template.loader import render_to_string

            import pynliner

            perm = Permission.objects.get(codename='newhome_notification')
            emails = User.objects.filter(
                Q(groups__permissions=perm) | Q(user_permissions=perm)
            ).values_list('email', flat=True)

            for email in emails:
                send_mail(
                    u'Mesto.UA: Регистрация застройщика',
                    u'Зарегестрирован новый застройщик %s' % self.email,
                    settings.DEFAULT_FROM_EMAIL,
                    [email]
                )

            # Отпраялвяем письмо-инструкцию застройщику
            translation.activate(self.language)
            subject = _(u'Письмо-инструкция по работе с сайтом mesto.ua')
            content = render_to_string('mail/newhome/new_developer_%s.jinja.html' % self.language, {'user': self})
            content_with_inline_css = pynliner.fromString(content)
            message = EmailMessage(subject, content_with_inline_css, settings.DEFAULT_FROM_EMAIL, [self.email])
            message.content_subtype = 'html'
            message.send()


    def get_ads_page(self):
        if self.get_own_agency:
            return reverse('agency_admin:ads')
        else:
            return reverse('profile_my_properties')

    # получаем id-юзеров, к объектам которых имеем доступ
    def get_owned_users(self, request=None):
        agency = request.own_agency if (request and request.own_agency) else self.get_own_agency()

        if agency:
            return set(agency.get_realtors().values_list('user_id', flat=True))
        else:
            return [self.id]

    # поиск лида (для CRM агентств)
    def find_lead(self, **kwargs):
        lead_filter = Q()
        for key, value in kwargs.items():
            if value:
                if isinstance(value, basestring):
                    lead_filter |= Q(('{}__contains'.format(key), value))
                else:
                    lead_filter |= Q((key, value))

        return self.leads.filter(lead_filter).first()

    # получение количества активных объявления
    def get_ads_count(self):
        return self.ads.filter(status=1, addr_country='UA').exclude(newhome_layouts__isnull=False).count()

    # Пользователь застройщик или нет
    def is_developer(self, force=False):
        # Кеш бесконечный и обновляется в сигналах Developer или принудительно
        if force or cache.get('developer_users') is None:
            from newhome.models import Developer
            developer_users = list(Developer.objects.all().values_list('user', flat=True))
            cache.set('developer_users', developer_users, None)

            return self.id in developer_users

        return self.id in cache.get('developer_users', [])

    @staticmethod
    def get_asnu_members():
        asnu_users = cache.get('asnu_users')
        if asnu_users is None:
            valid_asnu_numbers = cache.get('valid_asnu_numbers', [])  # обновляется в команде update_asnu_numbers_cache
            asnu_users = [user_id for user_id, asnu_number in User.objects.filter(agencies__asnu_number__gt='').values_list('id', 'agencies__asnu_number')
                          if asnu_number.replace('-', '') in valid_asnu_numbers]
            cache.set('asnu_users', asnu_users, 60*15)
        return asnu_users

    # член ассоциации по недвижимости Украины. Этим юзерам дается +10% скидки к текущим предложениям и везде добавляется логотип АСНУ.
    # TODO: лучше хранить эту информацию в поле агентства, но тогда придется делать дополнительные запросы к агентству юзера (например, на страницах поиска)
    def is_asnu_member(self, asnu_users=None):
        asnu_users = asnu_users or User.get_asnu_members()
        return self.id in asnu_users

    # обновление поля с количеством активных объявления (привет, денормализция!)
    def update_ads_count(self):
        ads_count = self.get_ads_count()
        if self.ads_count != ads_count:
            self.ads_count = ads_count
            self.save()
        return ads_count

    def get_unread_messages(self):
        from profile.models import Message
        unread_messages = cache.get('new_messages_for_user%d' % self.id)
        if unread_messages is None:
            unread_messages = Message.objects.filter(to_user=self, readed=False)\
                .exclude(Q(root_message__hidden_for_user=self) | (Q(from_user=self) & ~Q(to_user=self))).count()
            cache.set('new_messages_for_user%d' % self.id, unread_messages, None)  # бесконечный кеш
        return unread_messages

    def get_phone_display(self, with_link=True):
        return pprint_phones([phone.number for phone in self.phones.all()], with_link)

    @classmethod
    def make_unique_username(self, email):
        return '%s%s' % (email.split('@', 1)[0][:20], User.objects.count())

    def update_ads_phones(self, numbers):
        from ad.models import PhoneInAd, Phone
        from ad.phones import validate

        cleaned_numbers = [validate(number) for number in numbers]

        with db_transaction.atomic():
            for number in cleaned_numbers:
                Phone.objects.get_or_create(number=number)

            PhoneInAd.objects.filter(basead__ad__user=self).delete()

            for ad in self.ads.all():
                for order, number in enumerate(cleaned_numbers, start=1):
                    ad.phones_in_ad.create(phone_id=number, order=order)

    def get_available_plans(self):
        available_plans = Plan.objects.filter(is_active=True, ads_limit__isnull=False).order_by('ads_limit')
        if self.get_realtor():
            return available_plans.exclude(ads_limit=2)
        else:
            return available_plans.exclude(ads_limit=40)

    def get_active_plan(self):
        return self.get_unexpired_plans().order_by('start').first()

    def get_active_plan_using_prefetch(self):
        for plan in self.user_plans.all():
            if plan.end > datetime.datetime.now():
                return plan

    def get_unexpired_plans(self):
        return self.user_plans.filter(end__gt=datetime.datetime.now())

    def get_leadgeneration(self, type=None):
        """
        Возвращает настройки лидогенерации.
        ктивную лидогенерацию можно проверить через ActivityPeriod или метод has_active_leadgeneration()
        """
        if type not in ['ads', 'newhomes', None]:  # временно, пока будет оставаться вредная привычка с both
            raise Exception('Wrong leadgeneration type!')

        if hasattr(self, 'leadgeneration') and (
            type is None or
            (type == 'ads' and self.leadgeneration.is_active_ads) or
            (type == 'newhomes' and self.leadgeneration.is_active_newhomes)
        ):
            return self.leadgeneration
        else:
            return None

    @staticmethod
    def get_user_ids_with_active_ppk():
        user_ids = cache.get('user_ids_with_active_ppk')
        if not user_ids:
            from ppc.models import ActivityPeriod
            user_ids = ActivityPeriod.objects.filter(end=None).values_list('user', flat=True)
            cache.get('user_ids_with_active_ppk', user_ids, 60)
        return user_ids

    def has_active_leadgeneration(self, lead_type=None):
        """
            Возвращает текущий статус для лидогенерации.
            Можно уточнять тип объявлений, передавая в аргументе lead_type значение ads или newhomes
        """
        result = [period.lead_type
                  for period in self.activityperiods.all()
                  if not period.end and (lead_type is None or lead_type == period.lead_type)]

        return result

    def get_transaction_for_dedicated_number(self):
        return self.transactions.filter(time__gt=datetime.datetime.now()-datetime.timedelta(days=30), type=80).first()

    def get_expire_date_of_dedicated_number(self):
        transaction = self.get_transaction_for_dedicated_number()
        if transaction:
            return transaction.time + datetime.timedelta(days=30)

    def has_paid_dedicated_numbers(self):
        return self.get_transaction_for_dedicated_number() is not None

    # возвращает количество объявлений, которые можно разместить в Украине
    # количество объявлений получается через get_ads_count, а не через update_ads_count,
    # т.к. эта функция может запускаться внутри циклов/импорта и породить кучу .save() у юзера
    def get_user_limits(self, force=False):
        limits = {'ads_limit': 0, 'remaining_ads': 0}

        if self.get_leadgeneration('ads') and self.has_active_leadgeneration('ads'):
            limits['ads_limit'] = self.leadgeneration.ads_limit

        else:
            active_plan = self.get_active_plan_using_prefetch()
            if active_plan:
                limits['ads_limit'] = active_plan.ads_limit
        limits['remaining_ads'] = limits['ads_limit'] - (self.ads_count if not force else self.get_ads_count())

        return limits

    def get_user_limits_as_string(self):
        limits = self.get_user_limits()
        if limits['ads_limit']:
            return u'(%s %s %s %s)' % (_(u'доступно'), limits['remaining_ads'], _(u'из'), limits['ads_limit'])
        else:
            return ''

    def can_activate_ad(self, force=False):
        return self.get_user_limits(force=force)['remaining_ads'] > 0

    def get_publishing_type(self, lead_for='ads'):
        if lead_for == 'both' and self.has_active_leadgeneration():
            return 'leadgeneration'

        if lead_for == 'ads' and self.pk in User.get_user_ids_with_active_plan():
            return 'plan'

        if self.has_active_leadgeneration(lead_for):
            return 'leadgeneration'

    def get_publishing_warning_status(self):
        if not self.ads_count:
            if self.get_leadgeneration('ads'):
                if not self.has_active_leadgeneration():
                    return _(u'Недостаточно денег на балансе')
            else:
                now = datetime.datetime.now()
                last_userplan = self.user_plans.last()
                if not last_userplan:
                    return _(u'Выберите способ размещения')
                elif (now - datetime.timedelta(days=7)) < last_userplan.end < now:
                    return _(u'Ваш тариф завершен %s') % last_userplan.end.strftime('%d.%m.%Y %H:%M')

    # публикуем неактивные объявления пользователя, если их количество меньше оставшегося лимита по плану
    def activate_ads(self, **kwargs):
        inactive_ads = self.ads.filter(status=210, moderation_status=None, addr_country='UA')
        if kwargs:
            inactive_ads = inactive_ads.filter(**kwargs)

        inactive_ads_count = inactive_ads.count()
        if inactive_ads_count <= self.get_user_limits(force=True)['remaining_ads']:
            # хак для проверки модераций, т.к. публиковать через обычный цикл может быть очень медленно
            from ad.models import on_status_change
            for ad in inactive_ads.filter(fields_for_moderation__isnull=False):
                ad.status = 1
                on_status_change(Ad, ad)

            inactive_ads.update(status=1, is_published=True)

            # обновить количество объявлений юзеров, т.к. выше была публикация объявлений через update()
            self.update_ads_count()

            # подсчет количества объявлений вынесено в переменную, т.к. update() не возвращает количество обновленных строк из-за партицирования
            return inactive_ads_count

        return 0

    def deactivate_ads(self):
        self.ads.exclude(newhome_layouts__isnull=False).filter(
            status=1, addr_country='UA').update(status=210, is_published=False)

        # обновить количество объявлений юзеров, т.к. выше была публикация объявлений через update()
        self.update_ads_count()

    def deactivate_newhomes(self):
        # Деактивируем опубликованные новостройки и объявления на основе планировок объектов
        self.newhomes.update(status=210)
        self.ads.filter(newhome_layouts__isnull=False).update(status=210)

    def activate_newhomes(self):
        # Активируем опубликованные новостройки и объявления на основе планировок объектов, которые есть в наличии
        self.newhomes.filter(status=210, is_published=True).update(status=1)

        layouts_id = list(Flat.objects.filter(newhome__user=self, is_available=True).values_list('layout', flat=True))
        self.ads.filter(newhome_layouts__id__in=layouts_id, status=210, is_published=True).update(status=1)

    def get_region_plan_discount(self, purchase_time=None):
        if purchase_time is None:
            purchase_time = datetime.datetime.now()

        if datetime.datetime(2017, 6, 15) <= purchase_time:
            if self.region and self.region.plan_discount:
                return float(self.region.plan_discount)
        return 0

    def get_plan_discount(self, purchase_time=None):
        if purchase_time is None:
            purchase_time = datetime.datetime.now()

        region_plan_discount = self.get_region_plan_discount(purchase_time)

        if region_plan_discount:
            return region_plan_discount
        else:
            discount = 0.2  # всесезонная 20% скидка

            if self.is_asnu_member():
                discount += 0.1

            return discount

    def get_notification(self):
        from profile.models import Notification, InterruptedCheckoutNotification
        # уведомление для юзеров, которые с платежной системы не перешли на страницу success с редиректом для покупки услуг
        interrupted_checkout_url = cache.get('interrupted_checkout_url_for_user%s' % self.id)
        if interrupted_checkout_url and Transaction.objects.filter(type=2, time__gt=datetime.datetime.now() - datetime.timedelta(minutes=10)).exists():
            return InterruptedCheckoutNotification(interrupted_checkout_url)

        now = datetime.datetime.now()
        notifications = Notification.objects.filter(Q(start__lte=now, end__gte=now) | Q(start__lte=now, end__isnull=True))

        for notification in notifications:
            cache_key = 'notification_%d_users' % notification.id
            users_to_notify = cache.get(cache_key)
            if users_to_notify is None:
                users_to_notify = set(notification.get_user_queryset().values_list('id', flat=True))
                cache.set(cache_key, users_to_notify, 3600)

            if self.id in users_to_notify:
                return notification

        return None

    def get_numbers_for_sms(self):
        return clean_numbers_for_sms(phone.number for phone in self.phones.all())

    def send_email(self, subject, content, template='mail/base_2017.04.jinja.html', **kwargs):
        if self.email and self.subscribe_info:
            import pynliner
            from django.core.mail import EmailMessage
            from django.template.loader import render_to_string
            from django.conf import settings

            translation.activate(self.language)
            kwargs.update({'user': self, 'content': mark_safe(content)})
            body = render_to_string(template, kwargs)
            message = EmailMessage(
                subject, pynliner.fromString(body), from_email=settings.DEFAULT_FROM_EMAIL, to=[self.email]
            )
            message.content_subtype = 'html'
            if 'attach' in kwargs:
                message.attach(*kwargs['attach'])
            message.send()

    def send_notification(self, content, sms_numbers=None, sms_numbers_limit=None):
        result = {}

        # удаление двойных пробелов
        content = re.sub(r' +', ' ', content)

        # отправка пуш на все устройства пользователя (работает через firebase)
        for device in self.gcmdevice_set.all():
            device.send_message(content)
            result.setdefault('push_devices', []).append(device.pk)

        # отправка смс
        if self.receive_sms:
            from utils.sms import clean_numbers_for_sms, send_sms, transliterate_for_sms, MarafonException

            if not sms_numbers:
                sms_numbers = self.get_numbers_for_sms()

            if sms_numbers_limit:
                sms_numbers = sms_numbers[:sms_numbers_limit]

            try:
                send_sms(sms_numbers, transliterate_for_sms(content))
                result['sms_to'] = sms_numbers
            except MarafonException:
                import traceback
                result['sms_errors'] = traceback.format_exc(3).encode('utf-8')

        return result


    @db_transaction.atomic
    def purchase_plan(self, plan, move_money_from_user=None, order=None):
        from paid_services.views import get_plan_action # TODO: надо избавиться от этого, но мешают хаки с подменой active_plan, например, в profile.views_plans.plan
        active_plan = self.get_active_plan()
        action = get_plan_action(plan, active_plan)
        region = self.region or Region.get_capital_province()
        price = Plan.get_price(region.price_level, plan.ads_limit, self.get_plan_discount())
        unexpired_plans = self.get_unexpired_plans().order_by('-end')

        try:
            if action:
                if action == 'purchase':
                    transaction = Transaction.objects.create(user=self, type=11, amount=-price, order=order)
                    purchased_userplan = UserPlan.objects.create(user=self, plan=plan, ads_limit=plan.ads_limit, region=region)
                if action == 'prolong':
                    transaction = Transaction.objects.create(user=self, type=11, amount=-price, order=order,
                                                             comment=u'продление для тарифа #%d' % active_plan.id)
                    purchased_userplan = UserPlan.objects.create(user=self, plan=plan, ads_limit=plan.ads_limit, region=region,
                                                                 start=unexpired_plans[0].end, is_active=False)
                if action == 'upgrade':
                    for unexpired_plan in unexpired_plans:
                        unexpired_plan.cancel(self)

                    active_plan.cancel(self)
                    transaction = Transaction.objects.create(user=self, type=11, amount=-price, order=order)
                    purchased_userplan = UserPlan.objects.create(user=self, plan=plan, ads_limit=plan.ads_limit, region=region)

                Transaction.objects.filter(id=transaction.id).update(user_plan=purchased_userplan)
            else:
                raise Exception('User #%d can not buy plan #%d' % (self.id, plan.id))

        except InsufficientFundsError as insufficient_funds_error:
            if move_money_from_user:
                Transaction.move_money(move_money_from_user, self, insufficient_funds_error.deficit, u'для покупки тарифа риелтором')
                self.purchase_plan(plan)
            else:
                raise

    @db_transaction.atomic
    def purchase_paidplacement(self, ad, paidplacement_type, move_money_from_user=None, order=None):
        from paid_services.models import VipPlacement, Transaction, InsufficientFundsError, PaidPlacement, CatalogPlacement

        if ad.user != self:
            raise Exception('User #%d has not an Ad #%d' % (self.id, ad.pk))

        price = self.get_paidplacement_price(ad, paidplacement_type)

        try:
            if paidplacement_type == 'vip':
                if VipPlacement.objects.filter(is_active=True, basead=ad).exists():
                    raise PaidPlacement.AlreadyExistError()

                transaction = Transaction(user=self, type=53, amount=-price, order=order)
                transaction.save()
                VipPlacement(basead=ad, transaction=transaction).save()

            elif paidplacement_type in ('intl_mesto', 'worldwide'):
                if CatalogPlacement.objects.filter(is_active=True, basead=ad, catalog=paidplacement_type).exists():
                    raise PaidPlacement.AlreadyExistError()

                if paidplacement_type == 'worldwide':
                    transaction = Transaction.objects.create(user=self, type=55, amount=-price, order=order)
                elif paidplacement_type == 'intl_mesto':
                    transaction = Transaction.objects.create(user=self, type=54, amount=-price, order=order)

                CatalogPlacement(basead=ad, catalog=paidplacement_type, transaction=transaction).save()

        except InsufficientFundsError as insufficient_funds_error:
            if move_money_from_user:
                Transaction.move_money(move_money_from_user, self, insufficient_funds_error.deficit, u'для покупки платного размещения риелтором')
                self.purchase_paidplacement(ad, paidplacement_type)
            else:
                raise

    def get_paidplacement_price(self, ad, paidplacement_type):
        from paid_services.models import VIP_PRICE_RENT_DAILY, VIP_PRICES, CatalogPlacement

        if ad.user != self:
            raise Exception('User #%d has not ad #%d' % (self.id, ad.pk))

        if paidplacement_type == 'vip':
            if ad.addr_country != 'UA':
                return int(3 * get_currency_rates()['EUR']) # 3 евро в зарубежном каталоге
            if ad.deal_type == 'rent_daily':
                return VIP_PRICE_RENT_DAILY
            else:
                return VIP_PRICES[self.region.price_level if self.region else 'high']

        elif paidplacement_type in ('intl_mesto', 'worldwide'):
            if ad.addr_country == 'UA' and paidplacement_type == 'intl_mesto':
                raise Exception('"intl_mesto" paid placement cannot be used for ukranian properties')
            if ad.addr_country != 'UA' and paidplacement_type == 'worldwide':
                raise Exception('"worldwide" paid placement cannot be used for international properties')

            # Специальные условия для компании Grekodom Development (user ID 136807):
            # Размещение в нашем каталоге для них стоит 0.2 EUR
            if ad.user_id == 136807 and paidplacement_type == 'intl_mesto':
                return int(0.2 * get_currency_rates()['EUR'])

            return CatalogPlacement.get_price(paidplacement_type)

    def get_savedsearch_urls(self):
        # заглушка, т.к. заявки на подбор по параметрам привязаны к сохраненному поиску, который создается для юзера с id=1 и под этим юзером сайт тормозит :)
        if self.id == 1:
            return []

        cache_key = 'saved_searches_for_user%d' % self.id
        urls = cache.get(cache_key)

        if urls is None:
            urls = [search.get_full_url() for search in self.saved_searches.all()]
            cache.set(cache_key, urls)

        return urls

    @staticmethod
    def fast_register(email):
        user = User.objects.create_user(username=User.make_unique_username(email), email=email,
                                                      subscribe_info=False, subscribe_news=False)
        password = ''.join(random.choice(string.digits) for i in xrange(8))
        user.set_password(password)
        user.subscribe_info = True
        user.save()
        message = u'Ваш пароль:<b> %s  </b>. Вы его можете изменить в личном кабинете. Спасибо за регистрацию!' % password
        user.send_email(u'Регистрация на портале mesto.ua', message)
        return user


@receiver(post_save, sender=User)
def dirty_loyalty(sender, instance, **kwargs):
    if 'loyalty_started' in instance.get_dirty_fields().keys():
        logger = logging.getLogger('loyalty')

        loyalty_bonus = instance.get_loyalty_bonus()
        utm = make_utm_dict(utm_campaign='loyalty')
        ga_pixel = make_ga_pixel_dict(instance, utm)
        translation.activate(instance.language)

        if loyalty_bonus:
            # Подключили программу лояльности
            loyalty_bonus = int(loyalty_bonus * 100.0)
            instance.send_email(
                subject=_(u'Поздравляем, Вы стали участником программы лояльности'),
                content=_(u'Вы стали участником программы лояльности портала mesto.ua\n'
                          u'Теперь при пополнении баланса, %(loyalty_bonus)s%% от суммы будут начислены Вам бонусом!\n'
                          u'При условии постоянного пополнения баланса процент начисляемого бонуса будет увеличиваться.'
                          ) % {'loyalty_bonus': loyalty_bonus},
                template='paid_services/mail/loyalty-balance.jinja.html', utm=utm, ga_pixel=ga_pixel)

            logger.info('Loyalty',
                        extra={
                            'user_id': instance.id,
                            'action': 'Send loyalty notification after apply value: %s (current bonus is %d%%)' % (
                                instance.loyalty_started, loyalty_bonus)
                        })

        else:
            # Отключили программу лояльности
            instance.send_email(
                subject=_(u'Программа лояльности клиентов была приостановлена'),
                content=_(u'Нам очень жаль, но мы были вынуждены отключить Вашу программу лояльности, потому как Вы '
                          u'приостановили использование услуг на mesto.ua\n'
                          u'Свяжитесь со своим личным менеджером – и он подумает, что можно сделать для того, чтобы '
                          u'восстановить действие программы.'),
                template='paid_services/mail/loyalty-manager.jinja.html', utm=utm, ga_pixel=ga_pixel)

            logger.info('Loyalty',
                        extra={
                            'user_id': instance.id,
                            'action': 'Send loyalty notification about disable action'
                        })


# назначение менеджера после регистрации пользователя
@receiver(post_save, sender=User)
def set_manager_for_user(sender, instance, created, **kwargs):
    user = instance
    if created and not user.manager:
        from profile.models import Manager

        today = datetime.date.today()
        available_managers = Manager.objects.filter(is_available_for_new_users=True)
        user.manager = available_managers.exclude(managed_users__date_joined__gt=today).order_by('id').first()
        if not user.manager:
            user.manager = available_managers.filter(managed_users__date_joined__gt=today).annotate(users=Count('managed_users')).order_by('users').first()
        user.save()

receiver(post_save, sender=User)(post_save_clean_image_file)
receiver(post_delete, sender=User)(post_delete_clean_image_file)


class UserPhone(models.Model):
    class Meta:
        verbose_name = u'телефон пользователя'
        verbose_name_plural = u'телефоны пользователя'
        unique_together = (('phone', 'user'),)
        ordering = ['order']

    phone = models.ForeignKey('ad.Phone', verbose_name=u'телефон', related_name='users_m2m')
    user = models.ForeignKey(User, verbose_name=u'пользователь', related_name='phones_m2m')
    order = models.PositiveIntegerField(u'порядковый номер')

receiver(post_delete, sender=UserPhone)(send_user_proxynumbers_to_asterisk)
receiver(post_save, sender=UserPhone)(send_user_proxynumbers_to_asterisk)
