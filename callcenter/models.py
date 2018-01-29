# coding: utf-8
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from django.core.mail import EmailMessage
from django.conf import settings


SUBJECT_CHOICES = (
    (1, u'общие вопросы'),
    (2, u'вопросы по оплате'),
    (3, u'вопросы по услугам'),
    (4, u'модерация объявлений'),
    (5, u'банковская недвижимость'),
)

class BaseCall(models.Model):
    call_time = models.DateTimeField(u'время звонка', db_index=True)
    answer_time = models.DateTimeField(u'время ответа на звонок', null=True, blank=True)
    hang_up_time = models.DateTimeField(u'время завершение звонка', null=True, blank=True)
    duration = models.PositiveIntegerField(u'время разговора', default=0)

    callerid1 = models.CharField(u'номер звонившего', default='', max_length=14)
    uniqueid1 = models.CharField(u'идентификатор звонившего', default='', max_length=40, db_index=True)
    user1 = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'звонивший пользователь'), null=True, blank=True, related_name='made_%(app_label)s_%(class)ss')

    callerid2 = models.CharField(u'номер ответившего', blank=True, default='', max_length=14)
    uniqueid2 = models.CharField(u'идентификатор ответившего', blank=True, default='', max_length=40, db_index=True)
    user2 = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'ответивший пользователь'), null=True, blank=True, related_name='answered_%(app_label)s_%(class)ss')

    class Meta:
        abstract = True

    def __unicode__(self):
        return unicode(self.user1)


class Call(BaseCall):
    subject = models.PositiveIntegerField(u'тема обращения', choices=SUBJECT_CHOICES, blank=True, null=True)

    class Meta:
        verbose_name = u'звонок'
        verbose_name_plural = u'звонки'


class BaseCallRequest(models.Model):
    time = models.DateTimeField(u'время заявки', auto_now_add=True)
    user1 = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'отправитель заявки'), null=True, blank=True, default=None, related_name='%(class)ss_from')
    user2 = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_(u'получатель заявки'), null=True, blank=True, default=None, related_name='%(class)ss_to')
    ip = models.GenericIPAddressField(u'IP адрес отправителя', protocol='IPv4', blank=True, null=True)

    class Meta:
        abstract = True


class ManagerCallRequest(BaseCallRequest):
    phone = models.CharField(u'телефон', max_length=12, null=True, blank=True)

    class Meta:
        verbose_name = u'запрос звонка'
        verbose_name_plural = u'запросы звонка'

    def __unicode__(self):
        return self.user1.get_public_name()


@receiver(pre_save, sender=ManagerCallRequest)
def set_callrequest_manager(instance, **kwargs):
    if not instance.user2:
        instance.user2 = instance.user1.manager.user_ptr

@receiver(post_save, sender=ManagerCallRequest)
def send_notification_to_manager(instance, created, **kwargs):
    if created and instance.user2:
        user = instance.user1
        from django_hosts.resolvers import reverse
        content = u'''Пользователь %s (ID %s, %s) оставил заявку на обратный звонок.\nТелефон: %s\nВсе ваши заявки: %s''' % (
            user.get_public_name(),
            user.id,
            user.email,
            instance.phone,
            '%s?manager=%s' % (reverse('admin:callcenter_managercallrequest_changelist'), instance.user2_id),
        )
        email = EmailMessage(_(u"Запрос на перезвон!"), content, settings.DEFAULT_FROM_EMAIL, [instance.user2.email])
        email.content_subtype = "html"
        email.send()


class AsteriskCdr(models.Model):
    calldate = models.DateTimeField(u'время')
    clid = models.CharField(u'Caller ID вызывающего абонента', max_length=80)
    src = models.CharField(u'идентификатор вызывающего абонента', max_length=80)
    dst = models.CharField(u'пункт назначения вызова', max_length=80)
    duration = models.PositiveIntegerField(u'продолжительность вызова', default=0)
    billsec = models.PositiveIntegerField(u'продолжительность соединения с момента ответа', default=0)
    disposition = models.CharField(u'состояние обработки вызова', max_length=45)
    # accountcode = models.CharField(u'номер ответившего', max_length=20)
    uniqueid = models.CharField(u'unique ID', max_length=32, primary_key=True)
    userfield = models.CharField(u'дополнительные данные', max_length=255)
    # recordingfile = models.CharField(u'номер ответившего', max_length=255)

    class Meta:
        verbose_name = u'запись астериска'
        verbose_name_plural = u'записи астериска'
        managed = False
        db_table = 'cdr'
