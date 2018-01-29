# coding: utf-8
from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_save, post_delete
from django.core.urlresolvers import reverse
from django.core.files import File
from django.template.defaultfilters import slugify

from dirtyfields import DirtyFieldsMixin
from pytils.translit import translify
import datetime
import urllib
import string
import os

class Video(models.Model):
    class Meta:
        verbose_name = u'видео'
        verbose_name_plural = u'видео'
        ordering = ('name',)

    youtube_id = models.CharField(u'Youtube ID', max_length=50)
    name = models.CharField(u'название', max_length=200)
    views_count = models.PositiveIntegerField(u'просмотры', default=0)
    image = models.ImageField(u'изображение', upload_to='upload/guide/video/')

    def __unicode__(self):
        return self.name

@receiver(post_save, sender=Video)
def set_video_image(sender, instance, **kwargs):
    if not instance.image:
        url = urllib.urlretrieve('http://img.youtube.com/vi/%s/mqdefault.jpg' % instance.youtube_id)
        instance.image.save('video_%s.jpg' % instance.id, File(open(url[0], 'rb')))

class Photo(models.Model):
    class Meta:
        verbose_name = u'фотография'
        verbose_name_plural = u'фотографии'

    added = models.DateTimeField(u'добавлена', auto_now_add=True)
    image = models.ImageField(u'изображение', upload_to='upload/guide/photo/')
    subdomain = models.ForeignKey('ad.Region', verbose_name=u'поддомен', related_name='guide_photos')
    description = models.TextField(u'описание', null=True, blank=True)
    likes = models.PositiveIntegerField(u'лайки', default=0)
 
    def __unicode__(self):
        return u'#%d' % self.id

CINEMA_TYPE_CHOICES = (
    ('cinema', u'кинотеатр'),
    ('theatre', u'театр'),
    ('opera', u'опера'),
)

class Cinema(models.Model):
    class Meta:
        verbose_name = u'кинотеатр'
        verbose_name_plural = u'кинотеатры'
    
    type = models.CharField(u'тип', choices=CINEMA_TYPE_CHOICES, max_length=20)
    name = models.CharField(u'название', max_length=200)
    subdomain = models.ForeignKey('ad.Region', verbose_name=u'город/поддомен', related_name='guide_cinema')
    relative_address = models.CharField(u'адрес', max_length=100, help_text=u'улица, дом')
    phone1 = models.CharField(u'телефон', max_length=200, null=True, blank=True)
    phone2 = models.CharField(u'доп. телефон', max_length=200, null=True, blank=True)
 
    def __unicode__(self):
        return self.name

def make_taxi_upload_path(instance, filename):
    basename, extension = os.path.splitext(filename)
    return u'upload/guide/taxi/%s_%s%s' % (instance.subdomain.slug, slugify(translify(instance.name)), extension)

class Taxi(models.Model):
    class Meta:
        verbose_name = u'такси'
        verbose_name_plural = u'такси'
    
    name = models.CharField(u'название', max_length=200)
    subdomain = models.ForeignKey('ad.Region', verbose_name=u'город/поддомен', related_name='guide_taxi')
    image = models.ImageField(u'изображение', upload_to=make_taxi_upload_path, null=True, blank=True)
    description = models.TextField(u'описание', null=True, blank=True)
    phone = models.CharField(u'телефон', max_length=200, blank=True)
    short_phone = models.CharField(u'короткий номер', max_length=10, null=True, blank=True)
    min_charge = models.PositiveIntegerField(u'минимальный тариф, грн.', null=True, blank=True)
    services = models.TextField(u'услуги', null=True, blank=True)
    site = models.CharField(u'сайт', max_length=50, blank=True, null=True)
    likes = models.PositiveIntegerField(u'лайки', default=0)
 
    def __unicode__(self):
        return self.name

class RestaurantType(models.Model):
    class Meta:
        verbose_name = u'тип ресторана'
        verbose_name_plural = u'типы ресторанов'

    name = models.CharField(u'название', max_length=50)

    def __unicode__(self):
        return self.name

class Cookery(models.Model):
    class Meta:
        verbose_name = u'кухня'
        verbose_name_plural = u'кухни'

    name = models.CharField(u'название', max_length=50)

    def __unicode__(self):
        return self.name

def make_upload_path(directory, instance, filename):
    basename, extension = os.path.splitext(filename)
    try:
        name = translify(instance.name)
    except ValueError:
        name = instance.name
    name = slugify(name) or 'bad_filename'
    return u'upload/guide/%s/%s%s' % (directory, name, extension)

class Place(models.Model):
    class Meta:
        abstract = True

    name = models.CharField(u'название', max_length=200)
    address = models.CharField('полный адрес', max_length=255, help_text='Например: Киев, ул. Крещатик, 24')
    description = models.TextField(u'описание', blank=True, null=True)
    phone = models.CharField(u'телефон', max_length=200, blank=True, null=True)
    parking = models.NullBooleanField(u'парковка', blank=True, null=True)
    payment = models.CharField(u'тип оплаты', max_length=200, blank=True, null=True)
    notes = models.TextField(u'примечания', blank=True, null=True)
    region = models.ForeignKey('ad.Region', verbose_name='присвоенный регион', null=True, related_name='region_%(class)ss')
    coords_x = models.CharField('координаты по X', max_length=12, null=True, blank=True)
    coords_y = models.CharField('координаты по Y', max_length=12, null=True, blank=True)
    likes = models.PositiveIntegerField(u'лайки', default=0)

    def __unicode__(self):
        return self.name

def restaurant_upload_path(*args):
    return make_upload_path('restaurant', *args)

def shop_upload_path(*args):
    return make_upload_path('shop', *args)

class Restaurant(Place, DirtyFieldsMixin):
    class Meta:
        verbose_name = u'ресторан'
        verbose_name_plural = u'рестораны'
    
    types = models.ManyToManyField(RestaurantType, verbose_name=u'типы')
    image = models.ImageField(u'изображение', upload_to=restaurant_upload_path, null=True, blank=True)
    cookeries = models.ManyToManyField(Cookery, verbose_name=u'кухни')
    working_hours = models.CharField(u'время работы', max_length=200, blank=True, null=True)
    rooms = models.PositiveIntegerField(u'количество залов', blank=True, null=True)
    music = models.CharField(u'музыка', max_length=200, blank=True, null=True)
    entrance_fee = models.CharField(u'плата за вход', max_length=200, blank=True, null=True)
    site = models.CharField(u'сайт', max_length=50, blank=True, null=True)
    
SHOP_TYPE_CHOICES = (
    ('supermarket', u'супермаркет'),
    ('building_materials', u'стройматериалы'),
    ('auto_parts', u'авто-магазин'),
    ('household_appliances', u'бытовая техника'),
    ('shopping_centre', u'торговый центр'),
    ('for_children', u'товары для детей'),
    ('flower_shop', u'цветочный магазин'),
)

class Shop(Place, DirtyFieldsMixin):
    class Meta:
        verbose_name = u'магазин'
        verbose_name_plural = u'магазины'
    
    type = models.CharField(u'тип', max_length=50, choices=SHOP_TYPE_CHOICES)
    image = models.ImageField(u'изображение', upload_to=shop_upload_path, null=True, blank=True)

    def get_working_hours_display(self):
        time_groups = []
        for w in self.workinghours_set.order_by('weekday'):
            interval = (w.open, w.close)
            if time_groups and time_groups[-1][0] == interval:
                time_groups[-1][1].append(w.weekday)
            else:
                time_groups.append((interval, [w.weekday]))
        if len(time_groups) == 1:
            interval, weekdays = time_groups[0]
            if set(weekdays) == set(range(1, 8)) and interval == (datetime.time(0, 0, 0), datetime.time(23, 59, 59)):
                return u'круглосуточно'
        text = []
        format = '%H:%M'
        abbreviations = dict(zip(range(1, 8), (u'пн', u'вт', u'ср', u'чт', u'пт', u'сб', u'вс')))
        for interval, weekdays in time_groups:
            if len(weekdays) > 1:
                weekdays_text = u'%s-%s' % (abbreviations[weekdays[0]], abbreviations[weekdays[-1]])
            else:
                weekdays_text = abbreviations[weekdays[0]]
            time_text = u'с %s до %s' % (interval[0].strftime(format), interval[1].strftime(format))
            text.append(weekdays_text + u' ' + time_text)
        return string.join(text, ', ')

@receiver(pre_save, sender=Restaurant)
@receiver(pre_save, sender=Shop)
def update_location(sender, instance, **kwargs):
    # при оживлении моделей здесь нужно сделать обновление координат и region при изменении address
    pass

WORKING_HOURS_CHOICES = (
    (1, u'понедельник'),
    (2, u'вторник'),
    (3, u'среда'),
    (4, u'четверг'),
    (5, u'пятница'),
    (6, u'суббота'),
    (7, u'воскресенье'),
)

class WorkingHours(models.Model):
    class Meta:
        verbose_name = u'время работы'
        verbose_name_plural = u'время работы'
    
    shop = models.ForeignKey(Shop, verbose_name=u'магазин')
    weekday = models.IntegerField(u'день недели', choices=WORKING_HOURS_CHOICES)
    open = models.TimeField(u'открытие')
    close = models.TimeField(u'закрытие', help_text=u'вместо 24:00 используйте 23:59:59')

    def __unicode__(self):
        time_format = '%H:%M'
        return u'%s - %s с %s до %s' % (
            self.shop, self.get_weekday_display(), 
            self.open.strftime(time_format), 
            self.close.strftime(time_format)
        )

