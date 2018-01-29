# coding: utf-8
from django.db import models
from django.db.models import Q
from django.db import transaction as db_transaction
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete, pre_save
from django.db.utils import OperationalError
from django.utils.translation import ugettext_lazy as _
from django.dispatch import receiver
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.postgres.fields import ArrayField

from ad.models import Ad
from newhome.models import Newhome
from agency.models import Lead, LeadHistoryEvent
from paid_services.models import Transaction
from callcenter.models import BaseCall, BaseCallRequest
from utils.sms import clean_numbers_for_sms
from ppc import choices
from dirtyfields import DirtyFieldsMixin

import re
import os
import uuid
import datetime


class LeadGeneration(DirtyFieldsMixin, models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name=_(u'пользователь'))
    is_active_ads = models.BooleanField(_(u'включено для объявлений'), default=False)
    is_active_newhomes = models.BooleanField(_(u'включено для новостроек'), default=False)
    is_shown_users_phone = models.BooleanField(_(u'выводить телефон пользователя'), default=False)
    ads_limit = models.PositiveIntegerField(_(u'лимит объявлений по ППК'), default=40)
    dedicated_numbers = models.BooleanField(_(u'выделенные номера'), default=False)

    worktime = ArrayField(
        ArrayField(
            models.DurationField(default=datetime.timedelta, blank=True),
            size=2
        ),
        verbose_name=u'рабочие дни', size=7, blank=True, null=True)

    class Meta:
        verbose_name = u'настройка'
        verbose_name_plural = u'настройки'

    # проверка наличие оплаты за выделенный номер и оплата, если есть средства на счете
    def check_dedicated_numbers(self):
        if self.dedicated_numbers and self.user.has_active_leadgeneration() and not self.user.has_paid_dedicated_numbers():
            if not self.is_shown_users_phone and self.user.get_balance(force=True) >= 100:
                Transaction.objects.create(user=self.user, type=80, amount=-100)

            elif self.is_shown_users_phone and self.user.get_balance(force=True) >= 0:
                # Пока услуга предоставляется бесплатно (sic!), транзакция для застройщика заводится вручную
                # todo: Выставить сумму за собственный выделенный номер для Застройщика и снять False
                Transaction.objects.create(user=self.user, type=80, amount=0)

            else:
                for proxynumber in self.user.proxynumbers.filter(hold_until=None):
                    proxynumber.deactivate()

    def is_working_time(self, time=None):
        if not time:
            time = datetime.datetime.now()

        # не указано рабочее время, значит всегда готовы работать
        if not self.worktime or not [hour for day in self.worktime for hour in day if hour]:
            return True

        start, end = self.worktime[time.weekday()]
        current_timedelta = datetime.timedelta(hours=time.hour, minutes=time.minute)

        # смещаем период на день вперед, если дата окончания дня указана после 00:00
        if end < start:
            end += datetime.timedelta(hours=24)

            # так же иногда нужно текущее время сдвинуть
            if current_timedelta < start:
                current_timedelta += datetime.timedelta(hours=24)

        if start < current_timedelta < end:
            return True

        return False

    # запуск и остановка периодов лидогенерации с учетом настроек лидогенерации
    def stop_or_start_periods(self):
        balance = self.user.get_balance(True)
        active_leadgeneration = self.user.has_active_leadgeneration()
        balance_limit_for_activation = 200

        # если лидогенерация для объявлений выключена в настройках
        if not self.is_active_ads:
            if 'ads' in active_leadgeneration:
                ActivityPeriod.objects.get(user=self.user, end=None, lead_type='ads').stop()
        else:
            active_plan = self.user.get_active_plan_using_prefetch()
            plan_payback = 0
            if active_plan:
                plan_payback = active_plan.get_payback()
            if balance + plan_payback >= balance_limit_for_activation:
                # обязательная остановка тарифа перед запуском нового периода ППК
                if active_plan:
                    active_plan.cancel(self.user)
                period, created = ActivityPeriod.objects.get_or_create(user=self.user, end=None, lead_type='ads')

        # если лидогенерация для новостроек выключена в настройках
        if not self.is_active_newhomes:
            if 'newhomes' in active_leadgeneration:
                ActivityPeriod.objects.get(user=self.user, end=None, lead_type='newhomes').stop()
        else:
            if balance >= balance_limit_for_activation:
                period, created = ActivityPeriod.objects.get_or_create(user=self.user, end=None, lead_type='newhomes')


@receiver(post_save, sender=LeadGeneration)
def check_leadgeneration_status(sender, instance, **kwargs):
    instance.stop_or_start_periods()

    if 'dedicated_numbers' in instance.get_dirty_fields():
        instance.check_dedicated_numbers()


@receiver(post_save, sender=LeadGeneration)
def release_proxynumbers(sender, instance, **kwargs):
    if 'dedicated_numbers' in instance.get_dirty_fields() and instance.dedicated_numbers == False:
        for proxynumber in instance.user.proxynumbers.all():
            proxynumber.release()


@receiver(post_save, sender=LeadGeneration)
def send_user_proxynumbers_to_asterisk(sender, instance, **kwargs):
    """Обновляются при сохранении LeadGeneration, т.к. в нем могут быть изменены часы и дни приема звонков."""
    for proxynumber in instance.user.proxynumbers.filter(provider='local'):
        proxynumber.send_to_asterisk()


class ActivityPeriod(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'пользователь'), related_name='activityperiods')
    lead_type = models.CharField(_(u'тип лидогенерации'), choices=choices.LEAD_GENERATION_CHOICES, default='ads',
                                 max_length=15)
    start = models.DateTimeField(_(u'подключение'), default=datetime.datetime.now)
    end = models.DateTimeField(_(u'отключение'), blank=True, null=True)

    calls = models.PositiveIntegerField(_(u'звонков'), default=0)
    requests = models.PositiveIntegerField(_(u'звонков'), default=0)
    numbers = models.PositiveIntegerField(_(u'номеров'), default=0)

    class Meta:
        verbose_name = u'период'
        verbose_name_plural = u'периоды'

    # вызывается при отключении лидогенерации и при низком балансе
    def stop(self):
        user = self.user

        self.end = datetime.datetime.now()
        self.calls = self.user.answered_ppc_calls.filter(call_time__range=[self.start, self.end]).count()
        self.requests = self.user.callrequests_to.filter(time__range=[self.start, self.end]).count()
        self.numbers = self.user.proxynumbers.count()
        self.save()

        # отключаем номера и объявления/новостройки
        if self.lead_type == 'newhomes':
            user.deactivate_newhomes()
            for proxynumber in user.proxynumbers.filter(deal_type='newhomes'):
                proxynumber.deactivate()
        else:
            user.deactivate_ads()
            for proxynumber in user.proxynumbers.exclude(deal_type='newhomes'):
                proxynumber.deactivate()


@receiver(post_save, sender=ActivityPeriod)
def activate_ads_or_newhomes(sender, instance, created, **kwargs):
    """ Активация объявлений/новостроек после старта периода лидогенерации, а так же остановка активных тарифов """
    if created:
        if instance.lead_type == 'ads':
            instance.user.activate_ads()
        if instance.lead_type == 'hewhomes':
            instance.user.activate_newhomes()


class Bonus(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'пользователь'), related_name='leadgenerationbonuses')
    start = models.DateTimeField(_(u'начало'), auto_now_add=True)
    end = models.DateTimeField(_(u'конец'), blank=True, null=True, help_text=u'дата окончания выставляется после получения 10 звонков/лидов')

    class Meta:
        verbose_name = u'бонусы'
        verbose_name_plural = u'бонусы'

PROXYNUMBER_PROVIDER_CHOICES = (
    ('local', u'офисная телефония'),
    ('ringostat', u'RingoStat'),
)

PROXYNUMBER_MOBILE_OPERATOR_CHOICES = (
    ('kievstar', u'КиевСтар'),
    ('mts', u'МТС'),
    ('life', u'Лайф'),
)

subdomains_pattern = r'(.*\.)?'

REFERER_TRAFFIC_SOURCE = [
    ('seo', u'поисковые системы', r'^%s(google|yandex)\.\w{2,3}$' % subdomains_pattern),
    ('lun', 'lun.ua', r'^%slun\.ua$' % subdomains_pattern),
    ('trovit', 'trovit', r'^%strovit\.com$' % subdomains_pattern),
    ('mitula', 'mitula', r'^%smitula\.(com\.ua|com|ru)$' % subdomains_pattern),
    ('krysha', 'krysha', r'^%skrysha\.ua$' % subdomains_pattern),
    ('facebook', 'facebook', r'^%sfacebook\.com$' % subdomains_pattern),
    ('vk.com', u'вконтакте', r'^%svk\.com$' % subdomains_pattern),
]

PROXYNUMBER_TRAFFIC_SOURCE_CHOICES = [
    ('direct', u'прямые переходы'),
    ('yandex-cpc', u'яндекс директ'),
    ('google-cpc', u'adwords'),
    ('other', u'другое'),
] + [(name, description) for name, description, hostname_pattern in REFERER_TRAFFIC_SOURCE]


class ProxyNumber(models.Model):
    number = models.CharField(u'номер кол-центра', max_length=14)
    region = models.ForeignKey('ad.Region', verbose_name=_(u'регион'), blank=True, null=True, limit_choices_to = {'parent':1, 'kind': 'province'})
    provider = models.CharField(u'провайдер номера', choices=PROXYNUMBER_PROVIDER_CHOICES, max_length=10)
    mobile_operator = models.CharField(u'оператор', choices=PROXYNUMBER_MOBILE_OPERATOR_CHOICES, max_length=10, null=True, blank=True)

    is_shared = models.BooleanField(u'общий номер', default=False)
    traffic_source = models.CharField(u'источник трафика', choices=PROXYNUMBER_TRAFFIC_SOURCE_CHOICES, blank=True, max_length=10)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, verbose_name=_(u'пользователь'), related_name='proxynumbers')
    deal_type = models.CharField(u'тип сделки', choices=choices.DEAL_TYPE_CHOICES, blank=True, null=True, max_length=15)
    hold_until = models.DateTimeField(u'занят до', blank=True, null=True, help_text=u'до какого времени этот номер будет недоступен для выдачи новым пользователям')

    class Meta:
        verbose_name = u'номер переадресации'
        verbose_name_plural = u'номера переадресации'

    def __unicode__(self):
        return self.number

    # отключения номер от пользователя и замораживание на 10 дней, но это время номер остаюется за юзером на тот случай,
    # если он включит лидогенерацию опять (номера в хонде не синхронизируются с телефонием)
    def deactivate(self):
        self.hold_until = datetime.datetime.now() + datetime.timedelta(days=14)
        self.save()

    # освобождение номера от привязки к пользователю
    def release(self):
        if not self.is_shared:
            self.user = None
            self.deal_type = None
            self.hold_until = None
            self.save()

    @staticmethod
    def get_numbers(user, deal_type, traffic_source=None, newhome=None):
        use_shared_number = not (user.leadgeneration.dedicated_numbers and user.has_paid_dedicated_numbers())
        try:
            proxy_number = ProxyNumber.objects.get(user=user, deal_type=deal_type)

            # если номер был с холде, но нужно его снять, т.к. номера в холде не синхронизируются с телефонием
            if proxy_number.hold_until:
                if not use_shared_number:
                    proxy_number.hold_until = None
                    proxy_number.save()
                else:
                    # TODO: нет оплаченного выделенного номера
                    raise ProxyNumber.DoesNotExist

            return [proxy_number.number]
        except ProxyNumber.DoesNotExist:
            available_proxy_numbers = ProxyNumber.objects.filter(user=None, provider='ringostat')

            # Застройщики имеют возможность использовать свои телефоны при показе объектов
            if not use_shared_number and user.leadgeneration.is_shown_users_phone and newhome:
                users_phone = newhome.priority_phones.order_by(
                    newhome.priority_phones.through._meta.db_table + '.id').first()
                if users_phone:
                    return [users_phone.number]

                else:
                    users_phone = user.phones.first()
                    if users_phone:
                        return [users_phone.number]

            # нет свободных выделенных номеров
            if not use_shared_number and not available_proxy_numbers.filter(is_shared=False, user__isnull=True).exists():
                use_shared_number = True
                print 'We dont have free proxynumbers for user %d' % user.id

            # выбираем выделенный или общий номер
            available_proxy_numbers = available_proxy_numbers.filter(is_shared=use_shared_number)

            # для общего номер проверяем только тип сделки
            if use_shared_number:
                if deal_type == 'newhomes':
                    available_proxy_numbers = available_proxy_numbers.filter(deal_type='newhomes').order_by('mobile_operator')
                else:
                    available_proxy_numbers = available_proxy_numbers.exclude(deal_type='newhomes').order_by('mobile_operator')

                    if traffic_source:
                        available_proxy_numbers_by_traffic_source = available_proxy_numbers.filter(traffic_source=traffic_source)

                        # если нет подходящих номеров с указанным источником трафика, то используем номера для прямых переходов
                        if available_proxy_numbers_by_traffic_source.exists():
                            available_proxy_numbers = available_proxy_numbers_by_traffic_source
                        else:
                            available_proxy_numbers = available_proxy_numbers.filter(traffic_source__in=[None, 'direct'])

                return [available_proxy_number.number for available_proxy_number in available_proxy_numbers]
            else:
                # пытаемся найти номера в регионе пользователя
                if user.region and available_proxy_numbers.filter(region=user.region).exists():
                    available_proxy_numbers = available_proxy_numbers.filter(region=user.region)
                else:
                    # если номеров не нашлось, то выдаем номера без привязки к региону
                    available_proxy_numbers = available_proxy_numbers.filter(region=None)

            # выбираем первый подходяший номер
            proxy_number = available_proxy_numbers.order_by('?').first()
            if not proxy_number:
                raise Exception('Proxy numbers queue is empty :(')

            if not proxy_number.is_shared:
                proxy_number.user = user
                proxy_number.deal_type = deal_type
                proxy_number.hold_until = None
                proxy_number.save()

        return [proxy_number.number]

    # синхронизация данных о номере с удаленной ип-телефонией
    def send_to_asterisk(self):
        # не синхронизировать, если не указаны настройки БД астериска
        if 'asterisk' not in settings.DATABASES:
            return

        try:
            leadnumber = AsteriskLeadNumber.objects.using('asterisk').get(number=re.sub(r'^380', '', self.number))
        except (TypeError, OperationalError): # почему-то TypeError кидается при выключенном сервере, а OperationalError при выключенной базе
            return

        attrs = {field: '0' for field in ['dstnumber1', 'dstnumber2', 'dstnumber3', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']}

        if not self.hold_until and self.user and self.user.has_active_leadgeneration():
            dstnumbers = dict(zip(
                ['dstnumber1', 'dstnumber2', 'dstnumber3'],
                [re.sub(r'^38', '', number) for number in self.user.phones.values_list('number', flat=True)[:3]],
            ))
            attrs.update(dstnumbers)

            # по дефолту звонки принимаются 24/7
            worktime = self.user.leadgeneration.worktime
            if not worktime:
                worktime = [[datetime.timedelta(), datetime.timedelta()]] * 7

            day_fields = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
            for day, working_hours in enumerate(worktime):
                formatter = lambda delta: '%.2d:%.2d' % (delta.seconds // 3600, delta.seconds % 3600 / 60)
                attrs[day_fields[day]] = '%s-%s' % (formatter(working_hours[0]), formatter(working_hours[1]))
                attrs[day_fields[day]] = attrs[day_fields[day]].replace('-00:00', '-24:00')

        leadnumber.__dict__.update(attrs)
        leadnumber.save()


@receiver(post_save, sender=ProxyNumber)
@receiver(post_delete, sender=ProxyNumber)
def check_free_numbers_amount(sender, instance, **kwargs):
    if kwargs.get('created', False):
        return

    free_numbers_amount = ProxyNumber.objects.filter(is_shared=False, user__isnull=True).count()

    if free_numbers_amount in [40, 30, 20, 10, 5, 2, 0]:
        from django.core.mail import EmailMessage
        emails = [
            'ivo@mesto.ua', 'oksana@mesto.ua', 'am@mesto.ua', 'marina@mesto.ua', 'sergey@mesto.ua', 'zeratul268@gmail.com'
        ]

        for email in emails:
            message = EmailMessage(
                u'Внимание! Заканчивается пул свободных номеров',
                u'Осталось {} свободных номеров для риэлторов/застройщиков'.format(free_numbers_amount),
                settings.DEFAULT_FROM_EMAIL,
                [email]
            )
            message.send()


# pre_save используется, чтобы иметь возможность отменить назначение номера при обрыве связи с астериском
@receiver(pre_save, sender=ProxyNumber)
def send_proxynumber_to_asterisk(sender, instance, **kwargs):
    if instance.provider == 'local':
        instance.send_to_asterisk()


def get_lead_price(model, deal_type='other', price_level='high'):
    prices = choices.LEAD_PRICES[model].get(deal_type, choices.LEAD_PRICES[model]['other'])
    return prices.get(price_level, prices['high'])


def make_call_upload_path(instance, original_file_name):
    extension = os.path.splitext(original_file_name)[-1]
    safe_file_name = ''.join([uuid.uuid4().hex, extension])
    return 'upload/paidcalls/%s' % safe_file_name


class Call(BaseCall):
    proxynumber = models.ForeignKey(ProxyNumber, verbose_name=_(u'номер переадресации'), null=True, blank=True, related_name='calls', on_delete=models.SET_NULL)
    deal_type = models.CharField(_(u'тип сделки'), choices=choices.DEAL_TYPE_CHOICES, blank=True, max_length=15)
    object_id = models.PositiveIntegerField(u'ID объекта', null=True, blank=True)

    complaint = models.CharField(_(u'жалоба'), choices=choices.COMPLAINT_CHOICES, blank=True, null=True, max_length=10)
    transaction = models.ForeignKey('paid_services.Transaction', verbose_name=_(u'транзакция оплаты'), null=True, related_name='paidcalls')
    recordingfile = models.FileField(_(u'запись разговора'), upload_to=make_call_upload_path, blank=True, null=True)

    leadhistory = GenericRelation(LeadHistoryEvent)

    class Meta:
        verbose_name = u'звонок'
        verbose_name_plural = u'звонки'

    def is_received(self):
        return self.duration > 5

    def __unicode__(self):
        return u'%s %s' % (self.callerid1, self.call_time.strftime('%Y-%m-%d %H:%M'))

    @db_transaction.atomic
    def cancel(self, user_who_cancel=None):
        if self.complaint != 'accepted':
            # обновление через update() из-за сигнала accept_complaint
            Call.objects.filter(pk=self.id).update(complaint='accepted')

        comment = u'Возврат за звонок.'
        if user_who_cancel:
            comment += u'Отменил пользователь #%d' % user_who_cancel.id

        self.transaction.revert(comment=comment, note=u'возврат за звонок от %s' % self)

    def download_record(self, record_url):
        from django.core.files.base import ContentFile
        from urlparse import urlparse
        import requests

        response = requests.get(record_url)
        if response.headers['content-type'] == 'audio/ogg':
            name = urlparse(record_url).path.split('/')[-1]
            self.recordingfile.save(name, ContentFile(response.content), save=True)
            cache.delete('call%d-record' % self.pk)

            return True

    @staticmethod
    def sync_data_from_ringostat(hours=1):
        import requests
        import urllib

        day_ago = datetime.datetime.now() - datetime.timedelta(hours=hours)
        print '%s: sync data from ringostat' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

        url = 'https://api.ringostat.com/calls/export?' + urllib.urlencode({
            'project_id': 38466,
            'token': 'b368e2e33740f669cf9ee7be6a5fef12',
            'from': day_ago.strftime('%Y-%m-%d %H:%M'),
            'fields': 'caller,n_alias,disposition,duration,billsec,connected_with,recording,uniqueid,calldate',
        })
        r = requests.get(url)
        for row in r.json():
            Call.create_call_from_ringostat_json(row)

    @staticmethod
    def create_call_from_ringostat_json(data):
        from django.utils.dateparse import parse_datetime

        print ' call from %s to proxy %s at %s:' % (data['caller'], data['n_alias'], data['calldate'][:19]),
        call_time = parse_datetime(data['calldate']).replace(tzinfo=None)
        call = Call.objects.filter(uniqueid1=data['uniqueid'], call_time=call_time).first()
        if call:
            print 'already existed: Call #%d' % call.pk
            return call

        numbers = [data['n_alias']]
        if data['n_alias'][0] == '0':
            numbers.append('38%s' % data['n_alias'])

        try:
            proxynumber = ProxyNumber.objects.get(number__in=numbers)
        except ProxyNumber.DoesNotExist:
            print 'proxynumber not found'
            return
        else:
            user = proxynumber.user

        object_id = cache.get('additional_number_for_call_%s' % data['uniqueid'])
        deal_type = proxynumber.deal_type

        # для создания звонка, даже если не определили куда переадресовывать
        # Иногда номер звонившего в формате '7908578862079085788620;79085788620', а иногда anonymous
        call = Call(proxynumber=proxynumber, uniqueid1=data['uniqueid'], call_time=call_time,
                    callerid1 = '38000000000' if 'anonymous' in data['caller'] else data['caller'].split(';')[-1])
                    
        # определяем пользователя и тип сделки
        if object_id:
            print 'object id: %s |' % object_id,
            try:
                if proxynumber.deal_type == 'newhomes':
                    user = Newhome.objects.get(pk=object_id).user
                    deal_type = proxynumber.deal_type
                else:
                    ad = Ad.objects.get(pk=object_id)
                    deal_type = ad.deal_type
                    user = ad.user
            except (Newhome.DoesNotExist, Ad.DoesNotExist):
                print '%s %s not found |' % (proxynumber.deal_type or 'ad', object_id),

        elif not user and proxynumber.is_shared and data['connected_with']:
            '''
                Попытка найти пользователя по номеру с которым соединили, наприммер когда модератор вручную переадресовал
                А так же берем тип сделки судя по большинству объявлений пользователя
            '''
            from custom_user.models import User
            from collections import Counter
            connected_with = data['connected_with'].split('@')[0]
            user = User.objects.filter(phones=connected_with, id__in=User.get_user_ids_with_active_ppk()).first()
            if user:
                deal_type = Counter(user.ads.filter(is_published=True).values_list('deal_type', flat=True)).most_common(1)[0][0]

        if not user:
            if proxynumber.is_shared:
                print 'no object id for shared number |',
            else:
                print 'dedicated number doesnt have attached user |',
        elif not user.has_active_leadgeneration():
            print 'user doesnt have active leadgeneration |',
        else:
            call.user2=user
            call.deal_type=deal_type
            call.object_id=object_id
            call.callerid2 = data['connected_with'].split('@')[0] # номер в формате '79068701187@billing/n'

            if data['disposition'] not in ['NO ANSWER', 'BUSY'] and call.callerid2 and data['billsec']:
                call.duration = data['billsec']

        call.save()
        print 'call #%s created' % call.pk,

        if call.duration and data.get('recording'):
            if call.download_record(data['recording']):
                print '| call record download sucessfully'
            else:
                print '|  save url of call record in cache:', data['recording']
                cache.set('call%d-record' % call.pk, data['recording'], 60*30)
        else:
            print

        return call


# TODO: не знаю как еще правильно сделать удаление, если сначала удаляется заявка на звонок, а не транзакция
@receiver(post_delete, sender=Call)
def call_delete(sender, instance, **kwargs):
    if instance.transaction:
        instance.transaction.revert(comment=u'Возврат при удалении звонка #%d' % instance.id)


@receiver(post_save, sender=Call)
def call_create_lead(sender, instance, created, **kwargs):
    """
    Отправка уведомлений о заказе звонка на телефон и емейл
    Напоминание: instance.user1 - отправитель заявки, instance.user2 - получатель
    """
    if created and instance.user2:
        from agency.models import Lead

        object = None
        if instance.object_id:

            if instance.deal_type == 'newhomes':
                object = Newhome.objects.filter(pk=instance.object_id).first()
            else:
                object = Ad.objects.filter(pk=instance.object_id).first()

        clean_phone = instance.callerid1
        if clean_phone == '+':
            clean_phone = clean_phone[1:]
        if clean_phone[0] == '0':
            clean_phone = '38' + clean_phone

        # здесь не добавляется код 38, т.к. в find_lead поиск идет через contains
        lead = instance.user2.find_lead(phone=clean_phone)
        if not lead:
            lead = Lead.objects.create(user=instance.user2, client=instance.user1, phone=clean_phone,
                                       basead=object if isinstance(object, Ad) else None)

        about_object_str = u' по объявлению %s' % object.get_full_title() if object else ''

        # здесь же уведомляем пользователя, раз уж получили связанный Lead
        if instance.is_received():
            notification_content = u'Вы приняли звонок%s от клиента с mesto.ua: %s' % (about_object_str, lead)
        else:
            notification_content = u'Вы пропустили звонок%s от клиента с mesto.ua: %s. Перезвоните!' % (about_object_str, lead)

        # создание события в истории лида
        LeadHistoryEvent.objects.create(lead=lead, object=instance, time=instance.call_time)

        # смс отправляется для пропущенных звонок или для всех звоноков за последние 30 минут
        if instance.duration == 0 or (datetime.datetime.now() - instance.call_time).seconds < 60*30:
            instance.user2.send_notification(notification_content, sms_numbers_limit=1)


@receiver(post_save, sender=Call)
def accept_complaint(sender, instance, created, **kwargs):
    if instance.complaint == 'accepted':
        instance.cancel()


@receiver(pre_save, sender=Call)
def call_invoicing(sender, instance, **kwargs):
    """
    Билинд для звонков через нашу телефонию
    Напоминание: instance.user1 - отправитель заявки, instance.user2 - получатель
    """
    if not instance.pk and instance.user2:
        transaction = Transaction(user=instance.user2, note=u'звонок от %s' % instance)

        # юзеры без региона должны страдать
        price_level = instance.user2.region.price_level if instance.user2.region else 'high'

        # пропущенный звонок тарифицируется как заказ звонка
        if instance.is_received():
            transaction.type = 84
            transaction.amount = -get_lead_price('call', instance.deal_type, price_level)
        else:
            transaction.type = 85
            transaction.amount = -get_lead_price('callrequest', instance.deal_type, price_level)

        # повторные звонки в течение 24 часов не тарифицируеются
        day_ago = instance.call_time - datetime.timedelta(days=1)
        if Call.objects.filter(user2=instance.user2, callerid1=instance.callerid1, call_time__gt=day_ago).exists():
            transaction.amount = 0

        transaction.save()
        instance.transaction = transaction


class CallRequest(BaseCallRequest):
    name = models.CharField(_(u'имя'), max_length=100, null=True, blank=True)
    email = models.EmailField(_(u'e-mail'), blank=True, null=True)
    phone = models.CharField(_(u'телефон'), max_length=14, null=True, blank=True)

    referer = models.URLField('страница объекта', blank=True, max_length=512)
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    object = GenericForeignKey('content_type', 'object_id')
    traffic_source = models.CharField(u'источник трафика', choices=PROXYNUMBER_TRAFFIC_SOURCE_CHOICES, blank=True, max_length=10)

    transaction = models.ForeignKey('paid_services.Transaction', verbose_name=_(u'транзакция оплаты'), null=True, related_name='paidcallrequests')

    leadhistory = GenericRelation(LeadHistoryEvent)

    class Meta:
        verbose_name = u'заявка на обратный звонок'
        verbose_name_plural = u'заявки на обратный звонок'

    class DuplicationException(Exception):
        pass

    def __unicode__(self):
        return u' '.join(filter(None, [self.name, self.email, self.phone]))


# TODO: не знаю как еще правильно сделать удаление, если сначала удаляется заявка на звонок, а не транзакция
@receiver(post_delete, sender=CallRequest)
def callrequest_delete(sender, instance, **kwargs):
    if instance.transaction:
        instance.transaction.revert(comment=u'Возврат при удалении заявки на обратный звонок #%d' % instance.id)


@receiver(pre_save, sender=CallRequest)
def callrequest_say_hello(sender, instance, **kwargs):
    """
    Перед отправкой первого заказа звонка высылаем приветственную смс, чтобы клиент был готов.
    """
    if not instance.user2.callrequests_to.exists() and instance.user2.receive_sms:
        try:
            owner_phones = instance.object.get_numbers_for_sms()
        except AttributeError:  # конечно можно все типы объекта проверять, но я слишком стар для этого дерьма
            owner_phones = None

        notification_content = u'%s, теперь вы будете бесплатно получать смс с номерами клиентов, ' \
            u'которые хотят чтобы Вы им перезвонили! Удачных Вам продаж!' % instance.user2
        instance.user2.send_notification(notification_content, sms_numbers=owner_phones)


@receiver(pre_save, sender=CallRequest)
def callrequest_invoicing(sender, instance, **kwargs):
    """
    Билинд для заявок на обратный звонок, а так же проверка на уникальность
    Напоминание: instance.user1 - отправитель заявки, instance.user2 - получатель
    """
    deal_type = 'newhomes' if instance.object._meta.model_name == 'newhome' else instance.object.deal_type
    if deal_type == 'sale' and instance.object.newhome_layouts.exists():
        deal_type = 'newhomes'
    
    publishing_type = instance.user2.get_publishing_type(
        lead_for=('newhomes' if deal_type == 'newhomes' else 'ads')
    )

    if not publishing_type:
        raise Exception("User don't have active plan or PPC")

    # защита от дублей
    halfhour_ago = datetime.datetime.now() - datetime.timedelta(hours=0.5)
    if CallRequest.objects.filter(name=instance.name, email=instance.email, phone=instance.phone,
                                  object_id=instance.object_id, content_type=instance.content_type,
                                  user2=instance.user2, time__gt=halfhour_ago).exists():
        raise CallRequest.DuplicationException("CallRequest duplicate")

    if not instance.pk and instance.object and publishing_type == 'leadgeneration':
        price_level = instance.user2.region.price_level if instance.user2.region else 'high'
        price = get_lead_price('callrequest', deal_type, price_level)

        instance.transaction = Transaction.objects.create(user=instance.user2, type=83, amount=-price,
                                                          note=u'заказ звонка от %s' % instance)


@receiver(post_save, sender=CallRequest)
def callrequest_create_lead(sender, instance, created, **kwargs):
    """
    Отправка уведомлений о заказе звонка на телефон и емейл
    Напоминание: instance.user1 - отправитель заявки, instance.user2 - получатель
    """
    if created:
        lead = instance.user2.find_lead(phone=instance.phone, email=instance.email)
        if not lead:
            lead = Lead(user=instance.user2, client=instance.user1, name=instance.name, phone=instance.phone, email=instance.email)
            if isinstance(instance.object, Ad):
                lead.basead = instance.object
            lead.save()

        # создание события в истории лида
        LeadHistoryEvent.objects.create(lead=lead, object=instance)


@receiver(post_save, sender=CallRequest)
def callrequest_notifying(sender, instance, created, **kwargs):
    """
    Отправка уведомлений о заказе звонка на телефон и емейл
    Напоминание: instance.user1 - отправитель заявки, instance.user2 - получатель
    """
    if not created:
        return

    from custom_user.models import User
    from django.template.loader import render_to_string
    from django.contrib.auth.models import Permission
    from django.core.mail import EmailMessage
    import json
    import re
    import requests
    import pynliner

    # дефолту считается, что запрос на звонок оставлен со страницы обычного объявления
    referer_type = 0
    emails_for_notifying = [instance.user2.email]

    try:
        owner_phones = instance.object.get_numbers_for_sms()

    except AttributeError:  # конечно можно все типы объекта проверять, но я слишком стар для этого дерьма
        owner_phones = None

    # обработка запроса на обратный звонок со страницы новостройки
    if instance.object._meta.model_name == 'newhome':
        newhome = instance.object
        object_title = newhome.name

        if re.search(r'(?P<newhome_id>\d+)-layouts.html', instance.referer):
            referer_type = 3
        elif re.search(r'(?P<newhome_id>\d+)-layout(?P<layout_id>\d+).html', instance.referer):
            referer_type = 1
        elif re.search(r'(?P<newhome_id>\d+)-floors.html', instance.referer):
            referer_type = 2

        if newhome.priority_phones.exists():
            owner_phones = clean_numbers_for_sms(
                newhome.priority_phones.distinct().values_list('number', flat=True)
            )

        if newhome.priority_email:
            emails_for_notifying = [newhome.priority_email]

        perm = Permission.objects.get(codename='newhome_notification')
        emails_for_notifying += list(User.objects.filter(
            Q(groups__permissions=perm) | Q(user_permissions=perm)
        ).distinct().values_list('email', flat=True))

    else:
        object_title = instance.object.get_full_title()

    # уведомление владельцу
    url = ''
    if instance.referer != '/':
        response = requests.post(
            'https://www.googleapis.com/urlshortener/v1/url?key={}'.format(settings.GOOGLE_API_KEY),
            data=json.dumps({'longUrl': instance.referer}), headers={'content-type': 'application/json'}
        )
        url = response.json().get(u'id', '')

    # обработка запроса на обратный звонок со страницы новостройки
    if instance.object._meta.model_name == 'savedsearch':
        notification_content = u'Поступила заявка на подбор по параметрам: %s. Клиент: %s, %s %s %s' % (
            object_title, instance.name or '', instance.phone or '', instance.email or '', url
        )
    else:
        notification_content = u'Вашим объявлением %s интересуется клиент %s. Перезвоните ему %s %s %s' % (
            object_title, instance.name or '', instance.phone or '', instance.email or '', url
        )

    # уведомление на емейл или пуш
    instance.user2.send_notification(notification_content, sms_numbers=owner_phones)

    # уведомление на email для владельца объявления
    content = render_to_string('ppc/callrequest_email.jinja.html', {
        'object': instance.object,
        'object_title': object_title,
        'from_email': instance.email or '',
        'name': instance.name or '',
        'phone': instance.phone or '',
        'referer_type': referer_type,
        'referer': instance.referer
    })
    content_with_inline_css = pynliner.fromString(content)

    for email in emails_for_notifying:
        message = EmailMessage(
            u'Заявка от нового клиента с портала Mesto.ua', content_with_inline_css, settings.DEFAULT_FROM_EMAIL,
            [email]
        )
        message.content_subtype = 'html'
        message.send()

    # уведомление на email для отправителя
    content = render_to_string('ppc/callrequest_email_to_requester.jinja.html', {
        'object_title': object_title,
        'referer': instance.referer
    })
    content_with_inline_css = pynliner.fromString(content)

    if instance.email:
        message = EmailMessage(
            u'Ваша заявка с портала Mesto.ua', content_with_inline_css, settings.DEFAULT_FROM_EMAIL,
            [instance.email]
        )
        message.content_subtype = 'html'
        message.send()


class AsteriskLeadNumber(models.Model):
    number = models.CharField(u'номер АТС', max_length=12, primary_key=True, help_text=u'формат без +380, т.е. 443376001')
    dstnumber1 = models.CharField(u'номер клиента 1', max_length=12, help_text=u'формат без +38, т.е. 0443376001')
    dstnumber2 = models.CharField(u'номер клиента 2', max_length=12)
    dstnumber3 = models.CharField(u'номер клиента 3', max_length=12)
    mon = models.CharField(u'пн', max_length=12)
    tue = models.CharField(u'вт', max_length=12)
    wed = models.CharField(u'ср', max_length=12)
    thu = models.CharField(u'чт', max_length=12)
    fri = models.CharField(u'пт', max_length=12)
    sat = models.CharField(u'сб', max_length=12)
    sun = models.CharField(u'вс', max_length=12)

    class Meta:
        verbose_name = u'правило переадреации и время работы'
        verbose_name_plural = u'правила переадреации и время работы'
        managed = False
        db_table = 'lead_numbers'


class ViewsCount(models.Model):
    date = models.DateField(u'дата')
    basead = models.ForeignKey('ad.BaseAd', verbose_name=u'объявление', related_name='ppc_viewscounts')
    detail_views = models.PositiveIntegerField(u'просмотры страницы объявления', default=0)
    traffic_source = models.CharField(u'источник трафика', choices=PROXYNUMBER_TRAFFIC_SOURCE_CHOICES, max_length=10)

    class Meta:
        verbose_name = u'просмотр объявления c ППК'
        verbose_name_plural = u'просмотры объявлений с ППК'


def make_upload_path(review, filename):
    (root, ext) = os.path.splitext(filename)
    return 'upload/ppc_reviews/%s%s' % (uuid.uuid4().hex, ext)


class Review(models.Model):
    name = models.CharField(_(u'имя'), max_length=50)
    company = models.CharField(_(u'компания'), max_length=50)
    text = models.TextField(_(u'текст отзыва'))
    image = models.ImageField(_(u'изображение'), upload_to=make_upload_path, blank=True, null=True)

    time = models.DateTimeField(_(u'время создания'), auto_now=False, default=datetime.datetime.now)

    class Meta:
        verbose_name = u'отзыв'
        verbose_name_plural = u'отзывы'

