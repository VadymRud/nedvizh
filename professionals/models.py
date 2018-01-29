# coding: utf-8

from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

class Review(models.Model):
    class Meta:
        verbose_name = u'отзыв'
        verbose_name_plural = u'отзывы'

    RATING_CHOICES = zip(range(1, 6), range(1, 6))

    created = models.DateTimeField(u'создан', auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=u'пользователь')
    agency = models.ForeignKey('agency.Agency', verbose_name=u'агентство', related_name='reviews')
    title = models.CharField(u'тема', max_length=100)
    text = models.TextField(u'текст')
    rating = models.PositiveIntegerField(u'оценка', null=True, blank=True, choices=RATING_CHOICES)

class Reply(models.Model):
    class Meta:
        verbose_name = u'ответ на отзыв'
        verbose_name_plural = u'ответы на отзывы'

    review = models.ForeignKey(Review, verbose_name=u'отзыв', related_name='replies')
    created = models.DateTimeField(u'создан', auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=u'пользователь')
    text = models.TextField(u'текст')

