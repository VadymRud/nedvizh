# coding: utf-8

import os
from datetime import datetime
from pytils.translit import slugify
from django.db import models
from django.core.urlresolvers import reverse
from django.conf import settings
from django.db.models.signals import pre_save
from django.dispatch import receiver

from django.utils.translation import ugettext_lazy as _
from django.utils.html import strip_tags

from ad.models import Region, truncate_slug


SIMPLEPAGE_URLCONF_CHOICES = [(urlconf, urlconf) for urlconf in ('_site.urls', 'bank.urls')]


class SimplePage(models.Model):
    class Meta:
        verbose_name = u'простая страница'
        verbose_name_plural = u'простые страницы'

    urlconf = models.CharField(max_length=50, choices=SIMPLEPAGE_URLCONF_CHOICES)
    url = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    seo_title = models.CharField(max_length=255, blank=True, null=True)
    seo_description = models.CharField(max_length=255, blank=True, null=True)


class ContentBlock(models.Model):
    class Meta:
        verbose_name = u'блок контента'
        verbose_name_plural = u'блоки контента'

    name = models.CharField(max_length=50)
    content = models.TextField(blank=True)


CATEGORY_CHOICES = (
    ('news', _(u'Новости')),
    ('events', _(u'События')),
    ('places', _(u'Места')),
    ('must_know', _(u'Стоит знать')),
    ('school', _(u'Mesto School')),
)


def make_upload_path(instance, filename):
    basename, extension = os.path.splitext(filename)
    return u'upload/articles/%s/%s%s' % (datetime.now().strftime('%Y/%m'), instance.slug, extension)


def get_unique_slug(from_string, model_name, slug_length=40):
    """
    Создаем уникальный slug для объекта
    :param from_string: unicode
    :param model_name: instance models.Model
    :return: slug
    """

    slug = truncate_slug(slugify(from_string), slug_length)

    # Убираем дефис в конце slug, если фраза закончилась на знак препинания
    if slug.endswith('-'):
        slug = slug[:-1]

    if model_name.filter(slug__iexact=slug).exists():
        slug += datetime.now().strftime('_%d%H%M')

    return slug


class Article(models.Model):
    category = models.CharField('категория', choices=CATEGORY_CHOICES, default='news', db_index=True, max_length=15)
    name = models.CharField('название', max_length=255)
    slug = models.SlugField('часть URL-а', blank=True, db_index=True, max_length=50)
    external_link = models.URLField('внешняя ссылка', blank=True, max_length=255)

    description = models.TextField('текст анонса', blank=True)
    image = models.ImageField(verbose_name="изображение для анонса", upload_to=make_upload_path, blank=True)
    content = models.TextField('текст статьи', blank=True)
    related = models.ManyToManyField("self", blank=True, verbose_name="связанные статьи")
    visible = models.BooleanField('отображать на сайте', default=1)
    subdomains = models.ManyToManyField(
        'ad.Region', verbose_name=u'показывать только на поддоменах', blank=True, related_name='articles',
        limit_choices_to={'subdomain': True}
    )
    xml_id = models.PositiveIntegerField('индентификатор в XML', blank=True, null=True)
    published = models.DateTimeField('опубликована', blank=True, null=True)
    title = models.CharField('заголовок браузера', blank=True, max_length=255)

    class Meta:
        verbose_name = 'статья'
        verbose_name_plural = 'статьи'
        ordering = ['-published', '-id']

    def __unicode__(self):
        return self.name

    def get_absolute_url(self, subdomain_region=None):
        if self.external_link:
            return self.external_link

        if (subdomain_region is None) or (subdomain_region.static_url == ';'):
            subdomain_region = self.subdomains.first() or Region.objects.get(slug=settings.MESTO_CAPITAL_SLUG)

        if self.category == 'school':
            return subdomain_region.get_host_url('school:article_detail', args=[self.slug])
        else:
            return subdomain_region.get_host_url('guide:article_detail', args=[self.category, self.slug])

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = get_unique_slug(self.name, Article.objects.all())

        if not self.description:
            self.description = strip_tags(self.content[:300]) + '...'
        super(Article, self).save(*args, **kwargs)


class FAQBase(models.Model):
    title = models.CharField(verbose_name=u'Название', max_length=255)
    slug = models.SlugField(verbose_name=u'часть URL-а', blank=True, db_index=True, max_length=50)
    order = models.IntegerField(
        verbose_name=u'Порядок отображения', default=0, help_text=u'Чем выше число, тем ниже отображается запись'
    )
    is_published = models.BooleanField(verbose_name=u'Опубликован?', default=False)
    seo_title = models.CharField(
        verbose_name=u'(SEO) Title', max_length=255, blank=True, null=True,
        help_text=u'Title при просмотре всех вопросов одной категории'
    )
    seo_description = models.CharField(
        verbose_name=u'(SEO) Description', max_length=255, blank=True, null=True,
        help_text=u'Description при просмотре всех вопросов одной категории'
    )
    seo_keywords = models.CharField(
        verbose_name=u'(SEO) Keywords', max_length=255, blank=True, null=True,
        help_text=u'Keywords при просмотре всех вопросов одной категории'
    )

    def __unicode__(self):
        return self.title

    class Meta:
        abstract = True


class FAQCategory(FAQBase):
    def get_absolute_url(self):
        return reverse('faq_category_articles', args=[self.slug])

    class Meta:
        verbose_name_plural = u'список разделов для FAQ'
        verbose_name = u'раздел для FAQ'
        ordering = ('order',)


@receiver(pre_save, sender=FAQCategory)
def translate_faqcategory_fields(instance, **kwargs):
    obj = instance

    # Проверяем на заполненный slug
    if not obj.slug:
        obj.slug = get_unique_slug(obj.title_ru, FAQCategory.objects.all())


class FAQArticle(FAQBase):
    category = models.ForeignKey('staticpages.FAQCategory', verbose_name=u'Раздел с вопросами', related_name='category')
    content = models.TextField(verbose_name=u'Текст статьи', blank=True)
    video = models.CharField(verbose_name=u'Код вставки плеера', blank=True, max_length=255)

    def get_absolute_url(self):
        return reverse('faq_article', args=[self.category.slug, self.slug])

    class Meta:
        verbose_name_plural = u'список статей для FAQ'
        verbose_name = u'статью для FAQ'
        ordering = ('order',)


@receiver(pre_save, sender=FAQArticle)
def faqarticle_pre_save(instance, **kwargs):
    if not instance.slug:
        instance.slug = get_unique_slug(instance.title_ru, FAQArticle.objects.all())

