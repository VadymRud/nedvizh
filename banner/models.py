# coding: utf-8
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse
import os
import uuid
import datetime

PLACE_CHOICES = (
    ('slider', u'слайдер на главной'),
    ('topline', u'topline'),
    ('catfish', u'catfish'),
)


def make_call_upload_path(instance, original_file_name):
    extension = os.path.splitext(original_file_name)[-1]
    safe_file_name = ''.join([uuid.uuid4().hex, extension])
    return 'upload/bananers/%s' % safe_file_name # banAners - adblock protection


class ActiveBannerManager(models.Manager):
    def get_queryset(self):
        now = datetime.datetime.now()
        end_filter = models.Q(end__gte=now) | models.Q(end__isnull=True)
        return super(ActiveBannerManager, self).get_queryset().filter(end_filter).filter(start__lte=now, is_active=True)

class Banner(models.Model):
    name = models.CharField(u'название', max_length=50)
    place = models.CharField(u'баннерное место', choices=PLACE_CHOICES, max_length=10)
    is_active = models.BooleanField(_(u'активно'), default=False)
    image = models.FileField(_(u'изображение'), upload_to=make_call_upload_path, blank=True, null=True)
    image_bg = models.FileField(_(u'изображение для фона'), upload_to=make_call_upload_path, blank=True, null=True)
    url = models.URLField('ссылка', blank=True, max_length=512)
    order = models.PositiveIntegerField(_(u'порядок'), default=10)

    link_clicks = models.PositiveIntegerField(u'клики по ссылкам', default=0)

    start = models.DateTimeField(u'начало показа', default=datetime.datetime.now)
    end = models.DateTimeField(u'окончание показа', null=True, blank=True)
    targeting_pages = models.TextField(u'показ только на страницах', blank=True, null=True)

    objects = models.Manager()
    active_banners = ActiveBannerManager()

    class Meta:
        verbose_name = u'баннер'
        verbose_name_plural = u'баннеры'

    def get_absolute_url(self):
        return reverse('banner_link_click', args=[self.id])


class BannerClick(models.Model):
    date = models.DateField(u'дата')
    banner = models.ForeignKey(Banner, verbose_name=u'баннер', related_name='clicks')
    clicks = models.PositiveIntegerField(u'количество кликов', default=0)

    class Meta:
        verbose_name = u'клик по баннеру'
        verbose_name_plural = u'клики по баннеру'
