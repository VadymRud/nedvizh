# coding: utf-8
from __future__ import unicode_literals

from django.db import models

from ad.choices import DEAL_TYPE_CHOICES
from custom_user.models import LANGUAGE_CHOICES


class FacebookAutoposting(models.Model):
    name = models.CharField(verbose_name='Название настройки/группы', max_length=255)
    page_id = models.CharField(verbose_name='ID страницы в Facebook', max_length=255)
    region = models.ForeignKey(
        'ad.Region', verbose_name='Регион', limit_choices_to={'kind__in': ['locality', 'district', 'province']})
    deal_type = models.CharField(verbose_name='Тип сделки', max_length=12, choices=DEAL_TYPE_CHOICES)
    min_price = models.PositiveIntegerField(verbose_name='Минимальная цена объявления, грн', default=0)
    is_active = models.BooleanField(verbose_name='Активно?', default=True)
    last_posting_at = models.DateTimeField(verbose_name='Дата последней публикации', blank=True, null=True)
    access_token = models.CharField(verbose_name='Long Term Access Token', max_length=255, blank=True, null=True)
    access_token_expires_at = models.DateTimeField(verbose_name='Дата окончания действия токена', blank=True, null=True)
    language = models.CharField('язык', choices=LANGUAGE_CHOICES[:2], default='ru', max_length=2)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = 'настройку'
        verbose_name_plural = 'настройки автопостинга для Facebook'


class FacebookAutopostingAd(models.Model):
    facebook_autoposting = models.ForeignKey('autoposting.FacebookAutoposting')
    basead = models.ForeignKey('ad.BaseAd', related_name='facebook_autoposting_ads')
    page_id = models.CharField(verbose_name='Facebook page id', max_length=100)


class VkAutoposting(models.Model):
    name = models.CharField(verbose_name='Название настройки/группы', max_length=255)
    page_id = models.CharField(verbose_name='ID страницы в VK', max_length=255)
    region = models.ForeignKey(
        'ad.Region', verbose_name='Регион', limit_choices_to={'kind__in': ['locality', 'district']})
    deal_type = models.CharField(verbose_name='Тип сделки', max_length=12, choices=DEAL_TYPE_CHOICES)
    is_active = models.BooleanField(verbose_name='Активно?', default=True)
    last_posting_at = models.DateTimeField(verbose_name='Дата последней публикации', blank=True, null=True)
    language = models.CharField('язык', choices=LANGUAGE_CHOICES[:2], default='ru', max_length=2)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = 'настройку'
        verbose_name_plural = 'настройки автопостинга для Vk'


class VkAutopostingAd(models.Model):
    vk_autoposting = models.ForeignKey('autoposting.VkAutoposting')
    basead = models.ForeignKey('ad.BaseAd', related_name='vk_autoposting_ads')
    page_id = models.CharField(verbose_name='Vk page id', max_length=100)
