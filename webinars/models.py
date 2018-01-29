# coding: utf-8
from django.conf import settings
from django.db import models
from django_hosts.resolvers import reverse
from django.dispatch import receiver
from django.db.models.signals import pre_save, post_save, post_delete
from django.utils.translation import ugettext_lazy as _

from dirtyfields import DirtyFieldsMixin
from pytils.translit import slugify

from ad.models import truncate_slug
from utils.image_signals import post_save_clean_image_file, post_delete_clean_image_file

import os
import uuid
from datetime import datetime

class Speaker(models.Model):
    name = models.CharField(verbose_name=u'ФИО спикера', max_length=150)
    title = models.TextField(verbose_name=u'Должность спикера')
    image = models.ImageField(
        verbose_name=u'Фото спикера (105x105)', upload_to='upload/speaker/', help_text=u'Внимание! Фото не пережимается'
    )

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = u'Ведущий'
        verbose_name_plural = u'Ведущие'


TRAINING_TYPE_CHOICES = (
    ('webinar', _(u'вебинар')),
    ('seminar', _(u'семинар')),
)

TRAINING_STATUS_CHOICES = (
    ('preparing', u'Наполнение/Подготовка к отправке'),
    ('ready_for_test', u'Готово к тестовой отправке'),
    ('ready', u'Готово к отправке'),
    ('process', u'В процессе отправки'),
    ('done', u'Приглашения разосланы'),
)


class Webinar(models.Model):
    title = models.CharField(
        verbose_name=u'Название', max_length=255,
        help_text=u'Используйте символ # для переноса названия на странице регистрации вебинара'
    )
    city = models.CharField(verbose_name=u'Город проведения семинара', max_length=50, blank=True)
    slug = models.SlugField(verbose_name=u'часть URL-а', blank=True, db_index=True, max_length=50, unique=True)
    video = models.CharField(
        verbose_name=u'Код вставки плеера', max_length=255, blank=True, null=True,
        help_text=u'При добавлении кода - вебинар считается начавшимся'
    )
    type = models.CharField(u'тип тренинга', choices=TRAINING_TYPE_CHOICES, max_length=10, default='webinar')
    status = models.CharField(
        u'статус рассылки приглашения', choices=TRAINING_STATUS_CHOICES, max_length=15, default='preparing')
    link_for_email = models.URLField(
        verbose_name=u'Ссылка на страницу семинара для рассылки', blank=True, null=True, max_length=255)
    region = models.ForeignKey(
        'ad.Region', verbose_name=u'Регион', limit_choices_to={'parent': 1, 'kind': 'province'}, blank=True, null=True)
    emails_sent = models.PositiveIntegerField(verbose_name=u'Отправленно писем', default=0)
    is_published = models.BooleanField(verbose_name=u'Опубликован?', default=False)
    is_registration_available = models.BooleanField(verbose_name=u'Регистрация доступна?', default=True)
    external_url = models.URLField(
        verbose_name=u'Ссылка на комнату проведения семинара', blank=True, null=True, max_length=255)
    address = models.CharField(
        verbose_name=u'Адрес проведения семинара', max_length=255, blank=True, null=True,
        help_text=u'Используется для рассылки приглашения на семинар.'
    )
    teaser = models.TextField(verbose_name=u'Краткий обзор', help_text=u'Отображается при просмотре активного вебинара')
    description = models.TextField(verbose_name=u'Описание вебинара')
    image = models.ImageField(
        verbose_name=u'Изображение в шапку (1200x260)', upload_to='upload/webinar/',
        help_text=u'Отображается на странице регистрации на вебинар', blank=True, null=True
    )
    youtube_image = models.CharField(
        verbose_name=u'URL изображения архивного вебинара', blank=True, null=True, max_length=255,
        help_text=u'Отображается на странице вебинаров, в архивной ветке. Загружается автоматически',
    )
    youtube_duration = models.CharField(
        verbose_name=u'Продолжительность вебинара', blank=True, null=True, max_length=10,
        help_text=u'Продолжительность видео вебинара. Загружается автоматически'
    )
    youtube_views_count = models.PositiveIntegerField(
        verbose_name=u'Количество просмотров', default=0, blank=True, null=True,
        help_text=u'Количество просмотров видео на YouTube. Обновляется автоматически'
    )
    start_at = models.DateTimeField(verbose_name=u'Дата начала')
    finish_at = models.DateTimeField(verbose_name=u'Дата окончания')
    speakers = models.ManyToManyField(Speaker, verbose_name=u'Спикеры', blank=True)
    seo_title = models.CharField(
        verbose_name=u'(SEO) Title', max_length=255, blank=True, null=True,
        help_text=u'Title при просмотре страницы вебинара'
    )
    seo_description = models.CharField(
        verbose_name=u'(SEO) Description', max_length=255, blank=True, null=True,
        help_text=u'Description при просмотре страницы вебинара'
    )
    seo_keywords = models.CharField(
        verbose_name=u'(SEO) Keywords', max_length=255, blank=True, null=True,
        help_text=u'Keywords при просмотре страницы вебинара'
    )

    @property
    def is_active(self):
        now_date = datetime.now()
        return True if now_date <= self.finish_at and self.video else False

    @property
    def is_future(self):
        now_date = datetime.now()
        return True if not self.video and self.start_at >= now_date else False

    @property
    def is_archived(self):
        now_date = datetime.now()
        return True if now_date >= self.finish_at else False

    def get_player(self):
        if not self.video:
            return ''

        else:
            from utils.google_api import GoogleAPI
            gapi = GoogleAPI()
            return gapi.youtube_get_player(embed=self.video)

    def get_title(self):
        return u'%s' % self.title.replace(u'#', u' ')

    def get_title_with_linebreak(self):
        return u'</p><br><p>'.join(self.title.split('#'))

    def __unicode__(self):
        return u'%s «%s»' % (self.get_type_display().capitalize(), self.get_title())

    def get_absolute_url(self):
        return self.link_for_email or reverse('school:webinar_detail', args=[self.type, self.slug])

    class Meta:
        verbose_name = u'Вебинар'
        verbose_name_plural = u'Вебинары'
        ordering = ('start_at', )


@receiver(pre_save, sender=Webinar)
def get_unique_slug(instance, **kwargs):
    if not instance.slug:
        instance.slug = truncate_slug(slugify(instance.title), 40)

        if Webinar.objects.filter(slug__iexact=instance.slug).exists():
            instance.slug += datetime.now().strftime('_%d%H%M')


def make_upload_path(instance, filename):
    basename, extension = os.path.splitext(filename)
    return u'upload/seminar/photo/%s_%s%s' % (instance.webinar.id, uuid.uuid4().hex, extension)


class SeminarPhoto(models.Model, DirtyFieldsMixin):
    webinar = models.ForeignKey(Webinar, verbose_name=u'Вебинар', related_name='photos')
    image = models.ImageField(verbose_name=u"изображение", upload_to=make_upload_path, blank=True)
    order = models.IntegerField(
        verbose_name=u'Порядок отображения фото', default=0, help_text=u'Чем ниже число, тем раньше отобразится фото'
    )

    class Meta:
        verbose_name = u'Фото'
        verbose_name_plural = u'Фото с семинаров'
        ordering = ('order',)

receiver(post_save, sender=SeminarPhoto)(post_save_clean_image_file)
receiver(post_delete, sender=SeminarPhoto)(post_delete_clean_image_file)


class SeminarVideo(models.Model):
    webinar = models.ForeignKey(Webinar, verbose_name=u'Вебинар', related_name='videos')
    video = models.TextField(verbose_name=u"код видео", blank=False)
    order = models.IntegerField(
        verbose_name=u'Порядок отображения видео', default=0, help_text=u'Чем ниже число, тем раньше отобразится фото'
    )

    class Meta:
        verbose_name = u'Видео'
        verbose_name_plural = u'Видео с семинаров'
        ordering = ('order',)


class WebinarReminder(models.Model):
    webinar = models.ForeignKey(Webinar, verbose_name=u'Вебинар', related_name='reminders')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=u'пользователь', blank=True, null=True,
                             related_name='webinar_reminder')
    language = models.CharField(verbose_name=u'язык при регистрации', default=u'ru', max_length=5)
    name = models.CharField(verbose_name=u'имя', blank=True, null=True, max_length=255)
    email = models.EmailField(verbose_name=u'e-mail', max_length=255)
    phone = models.CharField(verbose_name=u'телефон', max_length=12, blank=True, null=True)
    city = models.CharField(verbose_name=u'Город', max_length=100)
    is_sent_email = models.BooleanField(verbose_name=u'Отправлено письмо?', default=False)
    is_sent_sms = models.BooleanField(verbose_name=u'Отправлено СМС?', default=False)

    class Meta:
        verbose_name = u'Регистрацию на вебинар'
        verbose_name_plural = u'Участники'
