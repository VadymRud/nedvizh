# coding: utf-8

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.conf import settings

TYPE_CHOICES = (
    ('vip_expired', u'Истек срок VIP-размещения'),
    ('ad_rejected', u'Объявление отклонено'),
    ('webinar_reminder', u'Напоминание о вебинаре'),
    ('leadgeneration_balance', u'Уведомление о заканчивающемся балансе при ППК')
)


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=u'получатель', related_name='notifications')
    type = models.CharField(u'тип уведомления', max_length=30, choices=TYPE_CHOICES)
    created = models.DateTimeField(u'создано', auto_now_add=True)

    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        verbose_name = u'уведомление'
        verbose_name_plural = u'уведомления'

## можно использовать в случае необходимости подготовки каких-то дополнительных данных для шаблонов
## (если данные нельзя получить из моделей), оптимизации запросов (prefetch) или других усложнений
#class BaseNotificationType(object):
    #name = None

    #def get_queryset(self):
        #return Notification.objects.filter(name=self.name)...

    #def set_extra_data(self, user, notifications):
        #pass

    #def get_extra_context(self, **kwargs):
        #pass

#notification_types = [FirstNotificationType, SecondNotificationType, ...]
