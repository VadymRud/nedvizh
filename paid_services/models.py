# coding: utf-8
import logging
import pynliner
import requests
from jsonfield import JSONField
from django.core.mail import EmailMessage
from django.db import models
from django.db.models.signals import post_save, post_delete, pre_save
from django.db import transaction as db_transaction
from django.http import QueryDict
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ungettext
from django.dispatch import receiver
from django.conf import settings
from django.core.cache import cache
from requests import RequestException
from requests import post

from ad.models import Ad
from paid_services.choices import VIP_TYPE_CHOICES

from dirtyfields import DirtyFieldsMixin
from dateutil import relativedelta

import datetime
import math
import json

from mail.models import Notification

TRANSACTION_TYPE_CHOICES = (
    (1, _(u'пополн: бонус')),
    (2, _(u'пополн: платежная система')),
    (31, _(u'возврат остатка за пакет обновлений')),
    (32, _(u'возврат при отмене тарифа')),
    (33, _(u'возврат остатка при остановке тарифа')),
    (4, _(u'пополн: новогодняя акция')),
    (5, _(u'пополн: через промо-код')),
    (6, _(u'пополн: бонус при регистрации')),
    (7, _(u'пополн: счет-фактура')),
    (9, _(u'пополн: бонус с ТВ рекламы')),
    (93, _(u'пополн: бонус по системе лояльности')),
    (8, _(u'перевод: к пользователю')),  # приходная операция. используется одновременно с типом 21
    (21, _(u'перевод: от пользователя')),  # расходная операция. используется одновременно с типом 8
    (11, _(u'тариф: покупка')),
    (12, _(u'тариф: улучшение')),
    (51, _(u'оплата премиум объявления')),
    (52, _(u'оплата эксклюзивного объявления')),
    (53, _(u'размещ: VIP')),
    (54, _(u'размещ: зарубеж mesto.ua')),
    (55, _(u'размещ: зарубеж партнеры')),
    (3,  _(u'размещ: возврат')),
    (61, _(u'оплата счета по посуточной аренде')),
    (62, _(u'оплата участия в тренинге')),
    (63, _(u'оплата 3D дизайна')),
    (71, _(u'оплата обновления объявлений')),
    (80, _(u'оплата за выделенный номер')),
    (81, _(u'оплата продления CRM')),
    (82, _(u'ппк: лид (устаревш)')),
    (83, _(u'ппк: заказ')),
    (84, _(u'ппк: звонок')),
    (85, _(u'ппк: звонок пропущ')),
    (34, _(u'ппк: возврат за звонок')),
    (91, _(u'оплата пакетного обновления')),
    (92, _(u'оплата автоматического обновления')),
    (100, _(u'коррекция транзакции')),
)


class InsufficientFundsError(Exception):
    def __init__(self, deficit):
        self.deficit = deficit


class CannotDeleteError(Exception):
    pass


class CannotDeleteQuerySet(models.QuerySet):
    def delete(self, *args, **kwargs):
        raise CannotDeleteError()


class Transaction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'пользователь'), db_index=True, related_name='transactions')
    type = models.PositiveIntegerField(_(u'тип'), choices=TRANSACTION_TYPE_CHOICES, default=0, db_index=True)
    amount = models.DecimalField(_(u'сумма грн'), max_digits=7, decimal_places=2)
    time = models.DateTimeField(_(u'время события'), auto_now=False, auto_now_add=True)
    comment = models.CharField(_(u'комментарий'), max_length=255, blank=True)
    note = models.CharField(_(u'заметка пользователя'), max_length=255, blank=True)
    user_plan = models.ForeignKey('paid_services.UserPlan', verbose_name=u'тариф пользователя', related_name='transactions', null=True, blank=True, on_delete=models.PROTECT)
    order = models.ForeignKey('paid_services.Order', verbose_name=u'заказ', related_name='transactions', null=True, blank=True)
    # если запрещать повторную коррекцию одной и той же транзакции, можно сделать OneToOne
    corrected_transaction = models.ForeignKey('self', verbose_name=u'отмененная транзакция', null=True, blank=True)

    objects = CannotDeleteQuerySet.as_manager()

    class Meta:
        verbose_name = u'транзакция пользователя'
        verbose_name_plural = u'транзакции пользователя'
        ordering = ['-time']

    def delete(self, *args, **kwargs):
        raise CannotDeleteError()

    def __unicode__(self):
        return u'%s: %s %s грн' % (self.user, self.get_type_display(), self.amount)

    def get_amount_with_corrections(self):
        return self.amount + sum(
            t.get_amount_with_corrections() for t in Transaction.objects.filter(corrected_transaction=self)
        )

    @staticmethod
    @db_transaction.atomic
    def move_money(from_user, to_user, amount, reason):
        transaction_from = Transaction(
            user=from_user,
            type=21,
            amount=-amount,
            comment=u'перевод на счет пользователю #%d (%s)' % (to_user.id, reason),
        )
        transaction_from.save()
        transaction_to = Transaction(
            user=to_user,
            type=8,
            amount=amount,
            comment=u'перевод со счета пользователя #%d (%s)' % (from_user.id, reason),
        )
        transaction_to.save()
        return [transaction_from, transaction_to]

    def revert(self, comment, note=''):
        if self.transaction_set.exists():
            raise Exception('Correction transaction already exists', list(self.transaction_set.values_list('id', flat=True)))

        Transaction.objects.create(
            user=self.user,
            corrected_transaction=self,
            amount=-self.get_amount_with_corrections(),
            type=100,
            comment=comment,
            note=note,
        )


@receiver(post_save, sender=Transaction)
def loyalty_bonus(sender, instance, created, **kwargs):
    if created and instance.type == 2:
        loyalty_bonus_amount = instance.user.get_loyalty_bonus() * instance.amount

        if loyalty_bonus_amount:
            comment = _(u'Программа лояльности - пополнение баланса для транзакции #%d') % instance.id
            Transaction.objects.create(user=instance.user, type=93, amount=loyalty_bonus_amount, comment=comment)

            logger = logging.getLogger('loyalty')
            logger.info('Loyalty',
                        extra={
                            'user_id': instance.user.id,
                            'action': 'Create loyalty transaction based on incoming transaction #%d' % instance.id
                        })


@receiver(post_save, sender=Transaction)
def payed_interior3d_notification(sender, instance, created, **kwargs):
    if created and instance.type == 63:
        from custom_user.models import User
        for service in json.loads(instance.order.services):
            responsible_user = User.objects.filter(email='sergey@mesto.ua').first() or User.objects.get(id=1)
            if 'test' not in service:
                responsible_user.send_email(u'Оплата услуги 3D дизайна', u'Получена оплата услуги 3D дизайна. Номер заказа - %s\n'
                                            u'Данные заявки: %s' % (instance.order_id, service['request_info']))
                responsible_user.send_notification(u'Получена оплата заказа #%d' % instance.order_id)


@receiver(post_save, sender=Transaction)
def trening_ticket(sender, instance, created, **kwargs):
    if created and instance.type == 62:
        from custom_user.models import User
        from django.template.loader import get_template
        from django.core.mail import EmailMessage
        import pdfkit
        import os

        for service in json.loads(instance.order.services):
            if service['type'] == 'training':
                ticket_template = get_template("email-ticket/email-ticket.jinja.html")
                ticket_html = ticket_template.render({
                    'name': service['form_data']["name"],
                    'order_id': instance.order_id,
                    'order_date': str(instance.order.time),
                    'static_path': os.path.join(settings.BASE_DIR, 'promo/static')
                })

                pdf_content = pdfkit.from_string(ticket_html, False, options={'page-size': 'A2', 'encoding': "UTF-8"})
                message = EmailMessage(
                    'Ваш билет на семинар-интенсив.', 'Факторы умножения продаж риэлтора.',
                    settings.DEFAULT_FROM_EMAIL, [service['form_data']["email"]]
                )
                message.attach('ticket.pdf', pdf_content, 'application/pdf')
                message.send()

                responsible_user = User.objects.get(email='d.yarik@gmail.com', is_staff=True)

                if 'test' not in service:
                    customer_info = ' / '.join(service['form_data'].values())
                    responsible_user.send_email(u'Оплата билета', u'Получена оплата за билет. Номер заказа - %s\n'
                                                u'Участник: %s' % (instance.order_id, customer_info))
                    responsible_user.send_notification(u'Оплата билета: %s' % customer_info)


# лид, заказ звонка, принятый и пропущенный звонок
TRANSACTION_TYPES_FOR_LEADGENERATION = [82, 83, 84, 85]


@receiver(pre_save, sender=Transaction)
def leadgeneration_bonus(sender, instance, **kwargs):
    """В рамках бонуса пользователю предоставляется 10 бесплатных звонков и лидов"""

    if instance.type in TRANSACTION_TYPES_FOR_LEADGENERATION:
        bonus = instance.user.leadgenerationbonuses.filter(end=None).first()
        if bonus:
            instance.amount = 0

            # эта транзакция будет 10й, поэтому надо отключить лидогенерацию
            if not instance.pk and instance.user.transactions.filter(time__gt=bonus.start, type__in=TRANSACTION_TYPES_FOR_LEADGENERATION).count() >= 9:
                bonus.end = datetime.datetime.now()
                bonus.save()

                for period in instance.user.activityperiods.filter(lead_type='ads', end=None):
                    period.stop()


@receiver(pre_save, sender=Transaction)
def check_balance(sender, instance, **kwargs):
    if instance.type not in TRANSACTION_TYPES_FOR_LEADGENERATION:  # 81-85 оплата за лиды/звонки
        if instance.amount < 0:
            old_balance = instance.user.get_balance(force=True)
            new_balance = old_balance + instance.amount
            if new_balance < 0:
                raise InsufficientFundsError(deficit=(-new_balance))


@receiver(post_delete, sender=Transaction)
@receiver(post_save, sender=Transaction)
def clear_profile_balance_cache(sender, instance, **kwargs):
    cache.delete('user%d_balance' % instance.user_id)


# отправка уведомления о низком балансе для пользователей с лидогенерации
@receiver(post_delete, sender=Transaction)
@receiver(post_save, sender=Transaction)
def notification_leadgeneration_user_on_low_balance(sender, instance, **kwargs):
    # проверка type нужна для случая, когда покупается тариф при включенной лидогенерации,
    # транзакция создается перед созданием тарифа, и has_active_leadgeneration() вернет True
    if instance.type != 11 and instance.user.has_active_leadgeneration() and instance.user.get_balance(force=True) < 100:
        Notification.objects.create(
            user=instance.user, type='leadgeneration_balance', object=instance.user.leadgeneration
        )


@receiver(post_save, sender=Transaction)
def activate_leadgeneration_period_on_topup(sender, instance, **kwargs):
    """ Проверка периодов лидогенерации при пополнении баланса. """
    if instance.amount > 0 and hasattr(instance.user, 'leadgeneration'):
        instance.user.leadgeneration.stop_or_start_periods()
        instance.user.leadgeneration.check_dedicated_numbers()


@receiver(post_save, sender=Transaction)
def send_event_to_ga_on_top_up(sender, instance, created, **kwargs):
    """
    Отправляем событие в Google Analytics при поступлении денег.
    Оборачиваем в try/except т.к. никакой отчет/событие не смеет ломать нам сайт!
    """
    if created and instance.type in [1, 2, 7]:
        data = {
            'v': 1,
            'tid': 'UA-24628616-30',
            't': 'event',
            'ec': 'balance',
            'ea': 'top_up',
            'el': 'transaction',
            'ev': instance.amount,
            'cd1': instance.user_id,
            'cid': instance.user.uuid
        }

        try:
            post('https://www.google-analytics.com/collect', data)

        except RequestException:
            pass


@receiver(post_delete, sender=Transaction)
@receiver(post_save, sender=Transaction)
def activate_developer_newhomes(sender, instance, **kwargs):
    """При положительном балансе застройщика и отключенной лидогенерации новостроек
    включаем лидогенерацию для застройщика.
    При включении лидогенерации для застройщика, активируются все новостройки застройщика (в сигнале LeadGeneration)"""

    if hasattr(instance.user, 'developer') and instance.user.get_balance(force=True) > 0:
        leadgeneration = instance.user.get_leadgeneration()
        if leadgeneration is None:
            from ppc.models import LeadGeneration
            leadgeneration, created = LeadGeneration.objects.get_or_create(user=instance.user)

        leadgeneration.is_active_newhomes = True
        leadgeneration.save()


class IsActiveAnnotatedManager(models.Manager):
    def get_queryset(self):
        now = datetime.datetime.now()
        return super(IsActiveAnnotatedManager, self).get_queryset().annotate(
            is_active=models.Case(
                models.When(since__lte=now, until__gte=now, then=models.Value(True)),
                default=models.Value(False),
                output_field=models.BooleanField(),
            )
        )

class PaidPlacement(models.Model, DirtyFieldsMixin):
    basead = models.ForeignKey('ad.BaseAd', null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_(u'объявление'), related_name='%(class)ss')
    since = models.DateTimeField(_(u'время начала'), default=datetime.datetime.now)
    until = models.DateTimeField(_(u'время окончания'))
    transaction = models.ForeignKey('paid_services.Transaction', verbose_name=_(u'транзакция оплаты'), related_name='%(class)ss')

    objects = IsActiveAnnotatedManager()

    class AlreadyExistError(Exception):
        pass

    class Meta:
        abstract = True
        verbose_name = u'платное размещение'
        verbose_name_plural = u'платные размещения'

    def __unicode__(self):
        return u'#%d' % self.id

    def get_remain_days(self):
        return (self.until - datetime.datetime.now()).days + 1

    @db_transaction.atomic
    def cancel(self, user_who_cancel):
        self.until = datetime.datetime.now()
        self.save()
        self.transaction.revert(comment=u'Возврат при отмене платного размещения #%d. Отменил пользователь #%d' % (self.id, user_who_cancel.id))


CATALOG_CHOICES = (
    ('intl_mesto', u'зарубежная недвижимость mesto.ua'),
    ('worldwide', u'зарубежные каталоги'),
)


class CatalogPlacement(PaidPlacement):
    catalog = models.CharField(_(u'каталог недвижимости'), max_length=30, choices=CATALOG_CHOICES)

    class Meta:
        verbose_name = u'размещение в каталогах'
        verbose_name_plural = u'размещения в каталогах'

    @staticmethod
    def get_price(catalog=None):
        from utils.currency import get_currency_rates
        one_euro_in_uah = int(get_currency_rates()['EUR'])

        if catalog == 'intl_mesto':
            return one_euro_in_uah # international.mesto.ua: 1 euro
        elif catalog == 'worldwide':
            return 2 * one_euro_in_uah # partners: 2 euro
        else:
            raise Exception('Wrong international catalog: %s' % catalog)

    @staticmethod
    def get_active_user_ads(catalog=None):
        queryset = CatalogPlacement.objects.filter(is_active=True, basead__isnull=False)

        if catalog:
            queryset = queryset.filter(catalog=catalog)

        return list(queryset.values_list('basead', flat=True))

@receiver(pre_save, sender=CatalogPlacement)
def set_catalog_placement_until(sender, instance, **kwargs):
    if instance.until is None:
        instance.until = instance.since + datetime.timedelta(days=30)

@receiver(post_save, sender=CatalogPlacement)
def post_save_catalog_placement(sender, instance, created, **kwargs):
    # после оплаты международного каталога можно опубликовать объявление
    if created:
        ad = instance.basead.ad
        ad.international_catalog = 1
        if instance.basead.ad.addr_country != 'UA':
            ad.status = 1
        ad.save()


class VipPlacement(PaidPlacement):
    days = models.PositiveIntegerField(u'срок, дней', default=7)
    type = models.PositiveIntegerField(u'тип', choices=VIP_TYPE_CHOICES, default=VIP_TYPE_CHOICES[0][0])

    class Meta:
        verbose_name = u'VIP размещение'
        verbose_name_plural = u'VIP размещения'
        permissions = (
            ('cancel_vipplacement', u'Отмена VIP размещения'),
        )


@receiver(pre_save, sender=VipPlacement)
def set_vip_placement_until(sender, instance, **kwargs):
    if instance.until is None:
        instance.until = instance.since + datetime.timedelta(days=instance.days)


@receiver(post_delete, sender=VipPlacement)
def post_delete_vip_placement(sender, instance, **kwargs):
    instance.basead.ad.update_vip()


@receiver(post_save, sender=VipPlacement)
def post_save_vip_placement(sender, instance, created, **kwargs):
    instance.basead.ad.update_vip()
    if created:
        now = datetime.datetime.now()
        expired = now + datetime.timedelta(days=settings.EXPIRE_DAYS)
        Ad.objects.filter(id=instance.basead_id).update(updated=now, expired=expired)


UPDATE_RATE_CHOICES = (
    (3, 3),
    (7, 7),
)

class Plan(models.Model):
    name = models.CharField(_(u'название'), max_length=50)
    ads_limit = models.PositiveIntegerField(_(u'лимит объявлений'), null=True, blank=True)
    update_interval = models.PositiveIntegerField(_(u'интервал обновления, дней'), choices=UPDATE_RATE_CHOICES)
    duration = models.PositiveIntegerField(_(u'продолжительность, дней'), default=31)
    is_popular = models.BooleanField(u'популярный?', default=False)
    is_active = models.BooleanField(u'действующий?', default=False)

    class Meta:
        verbose_name = _(u'тариф')
        verbose_name_plural = _(u'тарифы')

    def __unicode__(self):
        return self.name

    def get_pretty_name(self):
        return u'%s «%s»' % (self._meta.verbose_name, self.name)

    def get_verbose_ads_limits(self):
        return ungettext(u'%d объявление', u'%d объявлений', self.ads_limit) % self.ads_limit

    @staticmethod
    def get_price(price_level, ads_limit, extra_discount=0):
        base_price_per_1_ad = 15
        price_level_coefficient = {'low': 0.5, 'medium': 0.75, 'high': 1}[price_level]

        if ads_limit in (1, 2):
            ads_limit_discount = -1  # наценка 100%
        else:
            ads_limit_discount = 0

        price_per_1_ad = base_price_per_1_ad * price_level_coefficient * (1 - ads_limit_discount) * (1 - extra_discount)
        return int(math.ceil(price_per_1_ad * ads_limit))


def get_plan_end(start):
    return start + relativedelta.relativedelta(months=1)


class UserPlan(models.Model, DirtyFieldsMixin):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'пользователь'), related_name='user_plans')
    plan = models.ForeignKey(Plan, verbose_name=_(u'тариф'), related_name='user_plans')
    ads_limit = models.PositiveIntegerField(_(u'лимит объявлений'), null=True, blank=True)
    region = models.ForeignKey('ad.Region', verbose_name=_(u'регион'), null=True, blank=True, limit_choices_to={'kind': 'province', 'parent_id': 1})
    start = models.DateTimeField(_(u'начало'), default=datetime.datetime.now)
    end = models.DateTimeField(_(u'окончание'), null=True, blank=True)
    is_active = models.BooleanField(u'активно?', default=True)
    not_affect_to_discount = models.BooleanField(u'не учитывать при расчете скидки', default=False)
    bonus2016 = models.BooleanField(u'бонусный 2х недельный тариф на 10 объявлений', default=False)

    class Meta:
        verbose_name = u'тариф пользователя'
        verbose_name_plural = u'тарифы пользователей'
        ordering = ['start']
        permissions = (
            ('cancel_userplan', u'Отмена тарифа пользователя'), # удалить?
        )

    def __unicode__(self):
        return u'#%s' % self.id

    def valid_until(self):
        # Функция, которая возвращает дату окончания самого крайнего тарифа пользователя (включая все продления)
        return self.user.get_unexpired_plans().last().end

    def get_days_to_finish(self):
        # Количество дней до окончания оплаченного тарифного плана (включая все продления)
        last_available_plan = self.user.get_unexpired_plans().last()
        return (last_available_plan.end - datetime.datetime.now()).days if last_available_plan else 0

    def cancel(self, user_who_cancel, payback_type='partial'):
        with db_transaction.atomic():
            self.end = datetime.datetime.now()
            self.is_active = False
            self.save()

            if payback_type is not None:
                origin_transaction = self.get_origin_transaction()
                Transaction.objects.create(
                    user=origin_transaction.user,
                    corrected_transaction=origin_transaction,
                    amount=self.get_payback(payback_type),
                    type=100,
                    comment=u'Возврат остатка при отмене тарифа #%d. Отменил пользователь #%d' % (self.id, user_who_cancel.id)
                )

    # TODO: теперь юзеры могут отменять свои тарифы через кабинет, переключаясь на лидогенерацию. поэтому надо сделать защиту, чтобы они не переключали на тафир и обратно в течении дня
    def get_payback(self, type='partial'):
        full_amount = sum([t.get_amount_with_corrections() for t in self.transactions.all()])

        # полный возврат для неначатого тарифа (TODO: в теории не потребуется после перехода на новые тарифы)
        if self.start > datetime.datetime.now():
            type = 'full'

        if type == 'partial':
            elapsed_days = (datetime.datetime.now() - self.start).days
            proportion = float(self.plan.duration - elapsed_days) / self.plan.duration
            return -int(float(full_amount) * proportion)
        elif type == 'full':
            return -full_amount
        else:
            raise Exception('Wrong payback type')

    def get_origin_transaction(self):
        return self.transactions.get(type=11)


@receiver(pre_save, sender=UserPlan)
def pre_save_user_plan(sender, instance, **kwargs):
    if instance.end is None:
        instance.end = get_plan_end(instance.start)


@receiver(post_save, sender=UserPlan)
def post_save_user_plan(sender, instance, created, **kwargs):
    if created:
        # в настройках отключаем услугу Оплата за звонок, т.к. юзер перешел на тариф
        if hasattr(instance.user, 'leadgeneration'):
            # все ProxyNumber пользователя отключаются в сигналах через цепочку check_leadgeneration_status -> Leadgeneration.stop_or_start_periods -> Period.stop()
            instance.user.leadgeneration.is_active_ads = False
            instance.user.leadgeneration.save()

        if instance.is_active:
            # активируем объявления, если есть такая возможность
            instance.user.activate_ads()


VIP_PRICE_RENT_DAILY = 150
VIP_PRICES = {'high': 61, 'medium': 45, 'low': 31}

# используется для фильтра в админке и модели Notification из profile
FILTER_USER_BY_PLAN_CHOICES = (
    ('w-plan', u'с тарифом'),
    ('w-money-wo-plan', u'с деньгами, но без тарифа'),
    ('wo-ads-w-plan', u'без объявления, но с тарифом'),
    ('w-ads-wo-plan', u'с объявления, но без тарифа'),
    ('w-overlimit', u'с превышением по тарифу'),
    ('w-expired-plan', u'с истекшим планом'),
    ('w-plan-first-time', u'с планом впервые'),
    ('wo-any', u'без денег, объявлений и услуг'),
    ('w-ppk', u'с ППК'),
)


def filter_user_by_plan(queryset, parameter):
    from custom_user.models import User
    if parameter == 'w-plan':
        return queryset.filter(pk__in=User.get_user_ids_with_active_plan())
    elif parameter == 'w-money-wo-plan':
        users_with_money = [transaction['user'] for transaction in Transaction.objects.values('user').annotate(balance=models.Sum('amount')).order_by('user') if transaction['balance'] > 0]
        return queryset.filter(pk__in=users_with_money).exclude(pk__in=User.get_user_ids_with_active_plan())
    elif parameter == 'wo-ads-w-plan':
        return queryset.filter(pk__in=User.get_user_ids_with_active_plan(), ads_count=0)
    elif parameter == 'w-ads-wo-plan':
        return queryset.filter(ads_count__gt=0).exclude(pk__in=User.get_user_ids_with_active_plan())
    elif parameter == 'w-overlimit':
        users_with_overlimit = UserPlan.objects.filter(end__gt=datetime.datetime.now(), user__ads_count__gt=models.F('plan__ads_limit')).values_list('user', flat=True).order_by('user')
        return queryset.filter(pk__in=users_with_overlimit)
    elif parameter == 'w-expired-plan':
        prev_month_end = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)
        users_with_plan_in_prev_month = UserPlan.objects.filter(start__lt=prev_month_end, end__gt=prev_month_start).exclude(transactions__amount=0).values_list('user', flat=True)
        user_ids_w_expired_plan = set(users_with_plan_in_prev_month) - set(User.get_user_ids_with_active_plan())
        return queryset.filter(pk__in=user_ids_w_expired_plan)
    elif parameter == 'w-plan-first-time':
        user_ids_w_plan_first_time = set(UserPlan.objects.filter(plan__is_active=True, user__in=User.get_user_ids_with_active_plan()).values('user').annotate(cnt=models.Count('user')).filter(cnt=1).values_list('user', flat=True))
        return queryset.filter(pk__in=user_ids_w_plan_first_time)
    elif parameter == 'wo-any':
        return queryset.filter(transactions__isnull=True, ads__isnull=True)
    elif parameter == 'w-ppk':
        return queryset.filter(pk__in=User.get_user_ids_with_active_ppk())


class Order(models.Model, DirtyFieldsMixin):
    class Meta:
        verbose_name = u'заказ'
        verbose_name_plural = u'заказы'

    time = models.DateTimeField(u'время', default=datetime.datetime.now)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=u'пользователь', related_name='orders')
    services = models.TextField(u'услуги')
    amount = models.DecimalField(u'сумма, грн', max_digits=7, decimal_places=2)
    is_paid = models.BooleanField(u'оплачен?', default=False)
    is_reminder_sent = models.BooleanField(u'напоминание о незавершенном заказе отправлено', default=False)

    def __unicode__(self):
        strings = []
        for service in json.loads(self.services):
            str_ = service.get('name')

            if service['type'] == 'plan':
                plan = Plan.objects.get(id=service['id'])
                str_ = u'План на %s объявлений' % plan.ads_limit
            elif service['type'] == 'training':
                str_ = u'Участие в тренинге: %s' % service['participant']
            elif 'ad' in service:
                ad = Ad.objects.filter(pk=service['ad']).first()
                if ad:
                    str_ = u'Услуга %s для объявления #%d, %s' % (service['type'], ad.id, ad.address)
                else:
                    str_ = u'Услуга %s для объявления #%d (объявление удалено)' % (service['type'], service['ad'])

            if 'user_recipient' in service and self.user_id != service['user_recipient']:
                from custom_user.models import User
                user_recipient = User.objects.get(id=service['user_recipient'])
                str_ += u' для пользователя %s' % user_recipient.get_public_name()

            strings.append(str_)

        return u',\n '.join(strings)

    @db_transaction.atomic
    def execute(self):
        from custom_user.models import User
        for service in json.loads(self.services):
            user_recipient = User.objects.get(id=service['user_recipient'])
            if self.user == user_recipient:
                move_money_from_user = None
            else:
                move_money_from_user = self.user

            if service['type'] == 'plan':
                plan = Plan.objects.get(id=service['id'])
                user_recipient.purchase_plan(plan, move_money_from_user=move_money_from_user, order=self)
            elif service['type'] == 'training':
                Transaction.objects.create(user=user_recipient, type=62, amount=-self.amount, order=self, comment=(u'участие в тренинге: %s' % service['participant'])[:255])
            elif service['type'] == 'interior3d':
                Transaction.objects.create(user=user_recipient, type=63, amount=-self.amount, order=self)
            else:
                ad = Ad.objects.get(pk=service['ad'])
                user_recipient.purchase_paidplacement(ad, service['type'], move_money_from_user=move_money_from_user, order=self)
        self.is_paid = True
        self.save()

    def get_liqpay_payment_form(self, description=None):
        payment_description = u'Оплата счета #%s' % self.id

        services_str = u', '.join(filter(None, [service.get('name') for service in json.loads(self.services)]))
        if services_str:
            payment_description += u': %s' % services_str

        from utils.liqpay import LiqPay
        shop = settings.PAYMENT_SYSTEMS['liqpay']
        liqpay = LiqPay(shop['PUBLIC_KEY'], shop['PRIVATE_KEY'])
        form = liqpay.cnb_form({
            "action": "pay",
            "amount": self.amount,
            "currency": "UAH",
            "description": payment_description,
            "order_id": self.id,
            "customer": self.user.id,
            "version": "3"
        })
        return form

    def can_be_paid_again(self):
        import datetime
        return self.time > datetime.datetime.now() - datetime.timedelta(days=3)


@receiver(post_save, sender=Order)
def dirty_order(sender, instance, **kwargs):
    dirty_fields = instance.get_dirty_fields().keys()

    # отправка письма при оплате заказа
    if 'is_paid' in dirty_fields:
        if instance.is_paid and instance.user.email:
            translation.activate(instance.user.language)

            transactions = instance.transactions.filter(amount__lt=0)
            content = render_to_string(
                'paid_services/mail/send_email_on_paid.jinja.html',
                {
                    'order': instance,
                    'execute_time': datetime.datetime.now(),
                    'transactions': transactions,
                }
            )
            content_with_inline_css = pynliner.fromString(content)

            message = EmailMessage(
                _(u'Квитанция об оплате с сайта Mesto.UA'), content_with_inline_css,
                settings.DEFAULT_FROM_EMAIL, [instance.user.email]
            )
            message.content_subtype = 'html'
            message.send()


class AzureMLEntry(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    transaction = models.OneToOneField('paid_services.Transaction', related_name='azureml')
    request = JSONField()
    scored_probabilities = models.PositiveSmallIntegerField(default=0, blank=True)

    def get_or_receive_probability(self):
        if not self.scored_probabilities:
            response = requests.post(
                getattr(settings, 'MESTO_AZUREML_URL'), json=self.request,
                headers={'Authorization': ('Bearer %s' % getattr(settings, 'MESTO_AZUREML_API_KEY'))})

            if response.status_code == 200:
                user_response = response.json()
                scored_probabilities = user_response['Results']['output1']['value']['Values'][0][-1]
                self.scored_probabilities = int(float(scored_probabilities) * 100.0)
                self.save()

        return self.scored_probabilities
