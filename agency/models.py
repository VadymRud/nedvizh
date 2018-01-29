# coding: utf-8
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.core.cache import cache
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

import os
import uuid
import json
import datetime

import pynliner


class Realtor(models.Model):
    agency = models.ForeignKey('agency.Agency', verbose_name=_(u'агентство'), related_name='realtors')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'пользователь'), related_name='realtors')
    is_admin = models.BooleanField(u'админ агентства?', default=False)
    is_active = models.NullBooleanField(u'активный?', default=False)
    confirmation_key = models.CharField(u'код для ссылки активации', max_length=32, null=True, blank=True)

    class Meta:
        verbose_name = u'риелтор'
        verbose_name_plural = u'риелторы'
        unique_together = (('agency', 'user'),)

    def __unicode__(self):
        return unicode(self.user)

    def send_mail(self, password=None):
        content = render_to_string('agency/email_add_realtor.jinja.html', {'realtor': self, 'password': password})
        content_with_inline_css = pynliner.fromString(content)
        message = EmailMessage(
            _(u'Уведомление от Mesto.UA'), content_with_inline_css, settings.DEFAULT_FROM_EMAIL, [self.user.email]
        )
        message.content_subtype = 'html'
        message.send()

    def send_message(self):
        from profile.models import Message

        from_user = self.agency.realtors.filter(is_admin=True).first().user
        content = render_to_string('agency/message_add_realtor.jinja.html', {'realtor': self})
        content_with_inline_css = pynliner.fromString(content)

        new_message = Message(
            to_user=self.user, from_user=from_user, title=_(u'Уведомление от Mesto.UA'),
            text=content_with_inline_css, text_type='html'
        )
        new_message.save()
        new_message.hidden_for_user.add(from_user)


class Note(models.Model):
    realtor = models.ForeignKey(Realtor, verbose_name=_(u'риелтор'), related_name='notes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'владелец заметки'), related_name='realtor_notes')
    text = models.CharField(_(u'текст заметки'), blank=True, max_length=255)

    class Meta:
        verbose_name = u'заметка к риелтору'
        verbose_name_plural = u'заметки к риелтору'

def make_agency_upload_path(instance, original_file_name):
    extension = os.path.splitext(original_file_name)[1]
    safe_file_name = ''.join([uuid.uuid4().hex, extension])
    return 'upload/agency/%s' % safe_file_name


def make_uuid_hex():
    return uuid.uuid4().hex


LEAD_TYPES = (
    ('call', _(u'Телефон')),
    ('callrequest', _(u'Заказ звонка')),
    ('call_and_callrequest', _(u'И одно и другое')),
)

city_region_filters = {
    'kind': 'locality',
    'tree_path__gt': '1.',
    'tree_path__lt': '1.a',
}


class Agency(models.Model):
    name = models.CharField(_(u'название'), max_length=100)
    logo = models.ImageField(_(u'логотип'), upload_to=make_agency_upload_path, blank=True, null=True)
    city_text = models.CharField(_(u'город (старое поле)'), blank=True, null=True, max_length=50)
    city = models.ForeignKey('ad.Region', verbose_name=_(u'город'), null=True, blank=True, limit_choices_to=city_region_filters)
    address = models.CharField(_(u'адрес'), blank=True, null=True, max_length=100)
    deal_types = models.ManyToManyField('ad.DealType', verbose_name=_(u'типы сделки'), blank=True, related_name='agencies')
    show_in_agencies = models.BooleanField(_(u'показывать агентство в разделе сайта "Профессионалы"'), default=True)
    description = models.TextField(_(u'описание'), blank=True, null=True)
    working_hours = models.CharField(_(u'время работы'), blank=True, null=True, max_length=200)
    site = models.URLField(_(u'веб-сайт'), blank=True, null=True, max_length=100,
                           help_text=_(u'адрес должен начинаться с http://'))
    import_url = models.URLField(_(u'ссылка для импорта'), blank=True, null=True, max_length=100)
    asnu_number = models.CharField(_(u'Номер свидетельства АСНУ'), max_length=6, blank=True, null=True)
    import_report_access_code = models.CharField(u'код доступа к отчетам импорта', max_length=32, unique=True, default=make_uuid_hex)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, through='agency.Realtor', related_name='agencies')

    class Meta:
        verbose_name = u'агентство'
        verbose_name_plural = u'агентства'

    def __unicode__(self):
        return self.name

    def get_realtors(self):
        return self.realtors.filter(is_active=True)

    def get_realtors_using_prefetch(self):
        return [realtor for realtor in self.realtors.all() if realtor.is_active]

    def get_admin_user(self):
        return [realtor.user for realtor in self.realtors.all() if realtor.is_active and realtor.is_admin][0]


@receiver(post_save, sender=Agency)
def clear_asnu_users_cache(sender, instance, **kwargs):
    if instance.asnu_number:
        cache.delete('asnu_users')


LEAD_LABELS = (
    ('new', _(u'Первичный контакт')),
    ('in_progress', _(u'В работе')),
    ('awaiting', _(u'Принимает решение')),
    ('success', _(u'Сделка завершена')),
    ('fail', _(u'Сделка не состоялась')),
)


class Lead(models.Model):
    class Meta:
        verbose_name = u'лид'
        verbose_name_plural = u'лиды'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=u'владелец лида', null=True, related_name='leads')
    basead = models.ForeignKey('ad.BaseAd', verbose_name=u'объект (объявление)', null=True, blank=True, on_delete=models.SET_NULL)
    label = models.CharField(u'метка', max_length=50, choices=LEAD_LABELS, default='new')
    name = models.CharField(max_length=61, verbose_name=u'имя', blank=True, null=True)
    phone = models.CharField(u'телефон', max_length=12, blank=True, null=True)
    email = models.EmailField(max_length=254, verbose_name=u'e-mail', blank=True, null=True)
    client = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=u'пользователь', null=True, blank=True)
    is_readed = models.BooleanField(_(u'прочитано'), default=False)

    def __unicode__(self):
        return u' '.join(filter(None, [self.phone, self.name, self.email]))


# необходимо проверять ForignKey, поэтому dirtyfields пока не подойдет
@receiver(pre_save, sender=Lead)
def pre_save_lead(sender, instance, **kwargs):
    if instance.id:
        old_instance = Lead.objects.get(id=instance.id)
        instance.old_values = {'label': old_instance.label, 'basead_id': old_instance.basead_id}
    else:
        instance.old_values = {'label': None, 'basead_id': None}


@receiver(post_save, sender=Lead)
def post_save_lead(sender, instance, created, **kwargs):
    if instance.old_values['label'] != instance.label:
        LeadHistoryEvent(lead=instance, event={'set_label': instance.label}).save()
    if instance.old_values['basead_id'] != instance.basead_id:
        LeadHistoryEvent(lead=instance, event={'set_ad': instance.basead_id}).save()


class Task(models.Model):
    class Meta:
        verbose_name = u'задача'
        verbose_name_plural = u'задачи'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=u'владелец', null=True, related_name='tasks')
    basead = models.ForeignKey('ad.BaseAd', verbose_name=u'объект (объявление)', null=True, blank=True, on_delete=models.SET_NULL)
    lead = models.ForeignKey(Lead, verbose_name=u'лид', null=True, blank=True)
    start = models.DateTimeField(u'время начала')
    end = models.DateTimeField(u'время окончания')
    name = models.CharField(u'название', max_length=50)
    note = models.CharField(u'заметка', max_length=300, blank=True)


@receiver(pre_save, sender=Task)
def check_task_start_time(sender, instance, **kwargs):
    # поиск свободное времени в календаре
    while True:
        tasks_in_same_time = instance.user.tasks.filter(start__lte=instance.start, end__gt=instance.start).order_by('-end')
        if not tasks_in_same_time.exists():
            break
        else:
            instance.start = tasks_in_same_time[0].end

    if instance.end <= instance.start:
        instance.end = instance.start + datetime.timedelta(hours=1)


@receiver(post_save, sender=Task)
def post_save_task(sender, instance, created, **kwargs):
    if created and instance.lead:
        LeadHistoryEvent(lead=instance.lead, event={'create_meeting': instance.id}).save()


class JSONField(models.TextField):
    def from_db_value(self, value, *args):
        return json.loads(value)

    def get_prep_value(self, value):
        return json.dumps(value)


class LeadHistoryEvent(models.Model):
    class Meta:
        verbose_name = u'событие лида'
        verbose_name_plural = u'события лида'
        ordering = ('-time',)

    time = models.DateTimeField(u'время события', default=datetime.datetime.now)
    lead = models.ForeignKey(Lead, verbose_name=u'лид', related_name='history')
    event = JSONField(u'событие', blank=True)
    is_readed = models.BooleanField(_(u'прочитано'), default=False)
    
    content_type = models.ForeignKey(ContentType, null=True)
    object_id = models.PositiveIntegerField(null=True)
    object = GenericForeignKey('content_type', 'object_id')

    def get_event_message(self):
        if self.event and len(self.event.keys()) == 1:
            key, value = self.event.items()[0]

            if key == 'receive_first_message':
                link = u'<a href="#dialogue/%d">%s</a>' % (value, _(u'сообщение'))
                return _(u'пришло первое %s от клиента') % link
            elif key == 'set_label':
                return _(u'присвоена метка "%s"') % dict(LEAD_LABELS).get(value)
            elif key == 'set_ad':
                link = u'<a class="object_id" data-id="%d">ID %d</a>' % (value, value)
                return _(u'присвоен объект %s') % link
            elif key == 'create_meeting':
                return _(u'назначена встреча')
            raise Exception('Bad JSON of event')
        elif self.object:
            if self.object._meta.model_name == 'call':
                if self.object.duration:
                    return _(u'принят звонок длительностью %d сек' % self.object.duration)
                else:
                    return _(u'пропущенный звонок')
            elif self.object._meta.model_name == 'callrequest':
                return _(u'получен запрос звонка от %s') % self.object


@receiver(post_save, sender=LeadHistoryEvent)
def new_lead_history_event(sender, instance, created, **kwargs):
    if created:
        new_lead_cache_key = 'user{}_notified_about_new_lead'.format(instance.lead.user_id)
        cache.delete(new_lead_cache_key)


class ViewsCount(models.Model):
    date = models.DateField(u'дата')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=u'пользователь', related_name='viewscounts')
    professionals_contacts_views = models.PositiveIntegerField(u'просмотры контактов в профессионалах', default=0)

    class Meta:
        verbose_name = u'счетчик просмотров пользователя'
        verbose_name_plural = u'счетчики просмотров пользователей'

