# coding: utf-8
import collections

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import models
from django.db.models import Min
from django.db.models.signals import post_save, post_delete, pre_save
from django.utils.translation import ugettext_lazy as _
from django.contrib.humanize.templatetags.humanize import intcomma
from django.dispatch import receiver

import ad.choices as ad_choices
from ad.models import GeoObject, BaseModeration, Ad, Photo, BaseAd
from agency.models import city_region_filters
from utils.image_signals import post_save_clean_image_file, post_delete_clean_image_file
from utils.sms import clean_numbers_for_sms

from dirtyfields import DirtyFieldsMixin

import os
import uuid
import datetime


BUILDING_CLASS_CHOICES = (
    ('econom', _(u'эконом')),
    ('comfort', _(u'комфорт')),
    ('business', _(u'бизнес')),
    ('elite', _(u'премиум')),
)

HEATING_CHOICES = (
    ('auto', _(u'автономное')),
    ('central', _(u'централизованное')),
)

WALLS_CHOICES = (
    ('wall01', _(u'кирпич')),
    ('wall02', _(u'легкобетонные блоки')),
    ('wall03', _(u'керамоблок')),
    ('wall04', _(u'естественный камень')),
    ('wall05', _(u'дерево')),
    ('wall06', _(u'железобетон')),
)

INSULATION_CHOICES = (
    (1, _(u'минеральная вата')),
    (2, _(u'базальтовая вата')),
    (3, _(u'керамзитобетон')),
    (4, _(u'пенопласт')),
    (5, _(u'пенополистирол')),
)
YESNO_CHOICES = (
    ('yes', _(u'есть')),
    ('no', _(u'отсутствует')),
)

PARKING_CHOICES = (
    ('underground', _(u'подземный')),
    ('ground', _(u'наземный')),
    ('for_guests', _(u'гостевой')),
    ('none', _(u'отсутствует')),
)

NEWHOME_TYPE_CHOICES = (
    ('buildings', _(u'Жилищный комплекс')),
    ('home', _(u'Дом')),
)


class Developer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name=_(u'пользователь'), related_name='developer')
    name = models.CharField(_(u'название'), max_length=100)
    city = models.ForeignKey('ad.Region', verbose_name=_(u'город'), null=True, blank=True, limit_choices_to=city_region_filters)
    site = models.URLField(
        _(u'веб-сайт'), blank=True, null=True, max_length=100, help_text=_(u'адрес должен начинаться с http://')
    )
    is_cabinet_enabled = models.BooleanField(_(u'включен кабинет застройщика?'), default=True)

    class Meta:
        verbose_name = u'застройщик'
        verbose_name_plural = u'застройщики'


@receiver(post_save, sender=Developer)
@receiver(post_delete, sender=Developer)
def update_cache_developer_users(sender, instance, **kwargs):
    # При создании/удалении застройщика обновляем бесконечный кеш
    if kwargs.get('created') or kwargs.get('created') is None:
        developer_users = list(Developer.objects.all().values_list('user', flat=True))
        cache.set('developer_users', developer_users, None)


class Newhome(DirtyFieldsMixin, GeoObject):
    updated = models.DateTimeField(_(u'время обновления'), db_index=True, auto_now_add=True, null=True, blank=True)
    created = models.DateTimeField(verbose_name=_(u'время создания'), auto_now=False, default=datetime.datetime.now)
    modified = models.DateTimeField(_(u'время изменения'), auto_now=True)
    is_published = models.BooleanField(_(u'опубликовано на сайте'), default=False)
    status = models.PositiveIntegerField(_(u'статус'), choices=ad_choices.STATUS_CHOICES, default=210)
    moderation_status = models.PositiveIntegerField(
        _(u'статус модерации'), null=True, blank=True, choices=ad_choices.MODERATION_STATUS_CHOICES
    )
    fields_for_moderation = models.CharField(
        _(u'поля, требующие проверки модератором'), max_length=100, null=True, blank=True
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_(u'пользователь'), db_index=True, blank=True, null=True,
        related_name='newhomes'
    )
    priority_email = models.EmailField(
        verbose_name=_(u'Приоритетный контактный e-mail, если отличается от основного'), blank=True, default=u''
    )
    priority_phones = models.ManyToManyField(
        'ad.Phone', verbose_name=_(u'Приоритетный контактный телефон, если отличается от основного'), blank=True,
        related_name='priority_phones'
    )
    name = models.CharField(verbose_name=_(u'название жк'), help_text=_(u'Введите название'), max_length=100)
    keywords = models.TextField(verbose_name=_(u'Ключевые слова'),
                                help_text=_(u'Используются для улучшения качества поиска. Указывать через запятую'),
                                blank=True)

    newhome_type = models.CharField(_(u'тип'), max_length=20, choices=NEWHOME_TYPE_CHOICES, default='buildings')
    price_at = models.PositiveIntegerField(_(u'цена за м<sup>2</sup>, от (в гривнах)'), default=0)

    building_class = models.CharField(_(u'класс'), choices=BUILDING_CLASS_CHOICES, max_length=10)
    developer = models.CharField(_(u'застройщик'), max_length=50, blank=True)
    seller = models.CharField(_(u'реализует'), max_length=50)
    website = models.URLField(_(u'подробнее на сайте'), blank=True, max_length=100, help_text=_(u'Введите сайт ЖК'))
    content = models.TextField(_(u'описание'), blank=True)

    ceiling_height = models.DecimalField(_(u'высота потолков'), help_text=_(u'в метрах'), max_digits=4, decimal_places=2, null=True, blank=True)
    buildings_total = models.PositiveSmallIntegerField(_(u'домов'), help_text=_(u'кол-во домов в ЖК'), null=True, blank=True)
    flats_total = models.PositiveSmallIntegerField(_(u'квартир в ЖК'), help_text=_(u'сумма по всем домам'), null=True, blank=True)
    heating = models.CharField(_(u'отопление'), max_length=255, default=u'central', choices=HEATING_CHOICES)
    phases = models.PositiveSmallIntegerField(_(u'очередей'), help_text=_(u'всего очередей по ЖК'), null=True, blank=True)
    parking_info = models.CharField(_(u'паркинг'), max_length=255, default=u'none', choices=PARKING_CHOICES)
    walls = models.CharField(_(u'стены'), max_length=255, blank=True, choices=WALLS_CHOICES)
    building_insulation = models.CharField(_(u'утепление'), max_length=255, blank=True, choices=YESNO_CHOICES)
    number_of_floors = models.CharField(_(u'этажность'), max_length=255, help_text=_(u'этажей в доме'), blank=True)

    class Meta:
        verbose_name = u'новостройка'
        verbose_name_plural = u'новостройки'
        permissions = (
            ('newhome_admin', _(u'Расширенные права администрирования новостроек')),
            ('newhome_moderation', _(u'Модерирование новостроек')),
            ('newhome_notification', _(u'Уведомления о профилях застройщиков / лидов')),
        )

    # TODO: скорее всего нужно будет выводить диапазон цен из модели Flat. Например, "от ... до ... грн"
    def get_price_range(self, show_range=True):
        price_range = LayoutFlat.objects.filter(
            layout__newhome=self, price__gt=0
        ).aggregate(price_from=models.Min('price'), price_to=models.Max('price'))
        currency = LayoutFlat.objects.filter(layout__newhome=self).first()

        if (
            price_range.get('price_from') is not None and
            price_range.get('price_to') is not None and
            show_range
        ):
            return u'от %s до %s %s' % (
                intcomma(price_range['price_from']), intcomma(price_range['price_to']), currency.get_currency_display()
            )

        elif price_range.get('price_from') is not None:
            return u'от %s %s' % (
                intcomma(price_range['price_from']), currency.get_currency_display()
            )

        elif self.price_at:
            return u'от %s грн' % self.price_at

        else:
            return u''

    def get_first_photo(self):
        return self.newhome_photos.all().first()

    def get_full_title(self):
        words = [u'Новостройка', self.name, self.addr_street, self.addr_house, '-', self.get_price_range()]

        return ' '.join(map(unicode, filter(None, words)))

    # получает все подходящие укранский сотовый номер для отправки смс
    def get_numbers_for_sms(self):
        priority_phones = self.priority_phones.all()
        if priority_phones:
            return clean_numbers_for_sms(phone.number for phone in priority_phones)
        else:
            return self.user.get_numbers_for_sms()

    def __unicode__(self):
        return u'%s: %s' % (self.pk, self.name)

    def get_aggregation_floors_info(self, request):
        # Подготавливаем разбивку по этажам
        floors = self.floors.all().order_by('number')

        flats_available = collections.defaultdict(dict)
        flats_prices_by_floor = collections.defaultdict(list)
        flats_prices_by_rooms = collections.defaultdict(list)

        # Применяем фильтр по секции
        if request.GET.get('section'):
            floors = floors.filter(section__id=request.GET.get('section'))

        currency = u'грн.'
        for floor in floors:
            unavailable_layouts = list(self.flats.filter(
                floor__id=floor.id, is_available=False
            ).values_list('layout__id', flat=True))

            for layout in floor.layouts.filter(rooms_total__gt=0):
                if flats_available[floor].get(layout.rooms_total) is None:
                    flats_available[floor][layout.rooms_total] = 0

                flats_available[floor][layout.rooms_total] += int(layout.id not in unavailable_layouts)
                prices = layout.layout_flats.all()
                for price in prices:
                    currency = price.get_currency_display()
                    flats_prices_by_floor[floor].append(price.price)
                    flats_prices_by_rooms[layout.rooms_total].append(price.price)

        flats_info_exists = len(flats_available.keys())
        flats_rooms_options = sorted(set(flats_prices_by_rooms.keys()))
        flats_floor_options = sorted(set(flats_prices_by_floor.keys()))

        for prices in [flats_prices_by_rooms, flats_prices_by_floor]:
            for key in prices:
                prices[key] = min(prices[key])

        # площадь квартир по количеству комнат
        flats_area_by_rooms = dict(self.layouts.values_list('rooms_total').annotate(area=Min('area')))

        return (flats_rooms_options, flats_available, flats_prices_by_floor, flats_info_exists, flats_floor_options,
                flats_area_by_rooms, flats_prices_by_rooms, currency)

    def get_progress(self, process_id=None):
        # Ход строительства новостройки

        progress = self.progress.filter(pk=process_id).first() if process_id else self.progress.last()
        progress_next = None
        progress_prev = None

        if progress:
            try:
                progress_next = progress.get_next_by_date(**{'newhome': self})
            except Progress.DoesNotExist:
                pass

            try:
                progress_prev = progress.get_previous_by_date(**{'newhome': self})
            except Progress.DoesNotExist:
                pass

        return progress, progress_next, progress_prev

    def get_absolute_url(self):
        if not self.pk:
            return "#not-saved"

        if not self.region_id:
            return "#region-error"

        view_kwargs = {'deal_type': 'newhomes', 'id': self.pk}
        region_slug = self.region.get_region_slug()
        if region_slug:
            view_kwargs['region_slug'] = region_slug

        return self.region.get_host_url('ad-detail', kwargs=view_kwargs)

    def moderate(self, action, reject_status, moderator):
        now = datetime.datetime.now()
        open_moderations = self.newhome_moderations.filter(moderator__isnull=True)

        if open_moderations.exists():
            moderation = open_moderations[0]
        else:
            moderation = Moderation(newhome=self, start_time=now)

        # выходим, если не был указана причина отклонения или подтверждается объявление, у которого и так всё хорошо
        checks = [
            action == 'reject' and not reject_status,
            action == 'accept' and not self.moderation_status and not moderation.id and not self.fields_for_moderation
        ]
        if any(checks):
            return

        self.fields_for_moderation = None
        moderation.moderator = moderator
        moderation.end_time = now

        # объявление отклоняется, только если указывается новый статус
        if action == 'reject':
            moderation.new_status = self.moderation_status = int(reject_status)
            if reject_status >= 20:
                self.status = 210

        # если объявления было принято очищаем статус модерации и ставим разрешение на публикацию
        if action == 'accept':
            self.is_published = True
            self.moderation_status = None

        moderation.save()
        self.save()


@receiver(pre_save, sender=Newhome)
def dirty_newhome(instance, **kwargs):
    dirty_fields_dict = instance.get_dirty_fields()
    dirty_fields = set(dirty_fields_dict.keys())

    add_address_to_dirty_fields = False
    for key in dirty_fields:
        if key.startswith('addr_') and getattr(instance, key):
            instance.address = instance.build_address()
            add_address_to_dirty_fields = True

    if add_address_to_dirty_fields:
        dirty_fields.add('address')

    if (
        ('address' in dirty_fields or 'addr_country' in dirty_fields or not instance.region) and
        not instance.process_address()
    ):
        instance.moderation_status = 11  # не найден регион

    fields_to_check = {
        'price_at', 'addr_city', 'addr_street', 'addr_house', 'developer', 'content', 'ceiling_height',
        'buildings_total', 'flats_total', 'phases', 'number_of_floors'
    }

    if instance.pk:
        # Актуально только для опубликованных объектов и полей для внесения информации
        fields_for_moderation = dirty_fields & fields_to_check
        fields_for_moderation |= set(instance.fields_for_moderation.split(',') if instance.fields_for_moderation else [])
        if fields_for_moderation:
            instance.is_published = False
            instance.moderation_status = None
            instance.fields_for_moderation = ','.join(list(fields_for_moderation))

    else:
        instance.fields_for_moderation = '__all__'

    # Обновляем адреса у всех доступных объявлений новостроек на вторичке
    address_fields = {'addr_city', 'addr_street', 'addr_house', 'address', 'addr_country'}
    if instance.pk and dirty_fields & address_fields:
        Ad.objects.filter(newhome_layouts__newhome=instance).update(
            addr_city=instance.addr_city, addr_street=instance.addr_street, addr_house=instance.addr_house,
            address=instance.address, addr_country=instance.addr_country, region=instance.region
        )

    # Данный костыль поставлен из-за особенностей библиотеки django-modeltranslation иметь только один основной язык
    # Если заполнен только русский язык, то на любом языке подставится русский вариант
    # Если заполнен только украинский язык данных полей, то на других языках значение этих полей пустое
    # Реализована логика, когда в наличии только украинское значение поля, то данные дублируются в русское поле
    # Остальные языки не тронуты.
    for field in ['name', 'developer', 'seller']:
        field_ru = '%s_ru' % field
        field_uk = '%s_uk' % field
        if (
            (field_uk in dirty_fields and getattr(instance, field_uk)) or
            (not getattr(instance, field_ru) and getattr(instance, field_uk)) or
            (
                field_uk in dirty_fields and getattr(instance, field_uk) and
                getattr(instance, field_ru) == dirty_fields_dict[field_uk]
            )
        ):
            setattr(instance, field_ru, getattr(instance, field_uk))


@receiver(post_save, sender=Newhome)
def on_status_change(sender, instance, **kwargs):
    # оптравляем на модерацию, если объявление не скрыто и у него есть непроверенные поля
    # заблокированнные объявлений (moderation_status=20) на модерацию не возвращаются
    if instance.status == 1 and instance.fields_for_moderation and instance.moderation_status != 20:
        try:
            moderation, create = Moderation.objects.get_or_create(newhome=instance, moderator=None)

        except Moderation.MultipleObjectsReturned:
            moderations = Moderation.objects.filter(newhome=instance, moderator__isnull=True).order_by('id')
            moderation = moderations[0]
            moderations.exclude(pk=moderation.pk).delete()

    # при снятии объявления с пубилкации удаляем открытые заявки на модерацию
    if 'status' in instance.get_dirty_fields() and instance.status != 1:
        instance.newhome_moderations.filter(moderator=None).delete()

    # Проверка на включенную лидогенерацию
    if instance.status == 1 and not instance.fields_for_moderation and instance.is_published:
        if not hasattr(instance.user, 'leadgeneration') or not instance.user.leadgeneration.is_active_newhomes:
            from ppc.models import LeadGeneration
            leadgeneration, created = LeadGeneration.objects.get_or_create(user=instance.user)
            leadgeneration.is_active_newhomes = True
            leadgeneration.save()


def make_floor_image_upload_path(floor, filename):
    root, ext = os.path.splitext(filename)
    return 'upload/newhome/floor/%d_%s%s' % (floor.newhome_id, uuid.uuid4().hex, ext)


class Moderation(BaseModeration):
    class Meta:
        verbose_name = u'новостройка на модерации'
        verbose_name_plural = u'новостройки на модерации'
        ordering = ['-start_time']

    newhome = models.ForeignKey('newhome.Newhome', verbose_name=_(u'новостройка'), related_name='newhome_moderations')

    def __unicode__(self):
        return u'ID %s от %s' % (self.newhome_id, self.start_time)

    @classmethod
    def get_stats_by_user(cls, user_id, **qs):
        return super(Moderation, cls).get_stats_by_user(user_id, **{'newhome__user_id': user_id})


class Floor(models.Model, DirtyFieldsMixin):
    name = models.CharField(_(u'название'), help_text=_(u'например: 3-9 этажи'), max_length=50)
    number = models.SmallIntegerField(_(u'Номер этажа'), default=1)
    newhome = models.ForeignKey(Newhome, verbose_name=_(u'новостройка'), related_name='floors')
    section = models.ForeignKey('newhome.BuildingSection', verbose_name=_(u'секция'))
    building = models.ForeignKey('newhome.Building', verbose_name=_(u'дом'))
    image = models.ImageField(verbose_name="изображение", upload_to=make_floor_image_upload_path, blank=True)
    layouts = models.ManyToManyField('newhome.Layout', verbose_name=_(u'Квартира'))

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = u'планировка этажа'
        verbose_name_plural = u'планировки этажей'
        ordering = ('number',)

receiver(post_save, sender=Floor)(post_save_clean_image_file)
receiver(post_delete, sender=Floor)(post_delete_clean_image_file)


def make_layout_image_upload_path(layout, filename):
    root, ext = os.path.splitext(filename)
    return 'upload/newhome/layout/%d_%s%s' % (layout.newhome_id, uuid.uuid4().hex, ext)


class Layout(models.Model, DirtyFieldsMixin):
    """Планировки квартир"""
    name = models.CharField(_(u'название'), max_length=50, help_text=_(u'Введите название планировки'))
    newhome = models.ForeignKey(Newhome, verbose_name=_(u'новостройка'), related_name='layouts')
    section = models.ForeignKey('newhome.BuildingSection', verbose_name=_(u'секция'))
    building = models.ForeignKey('newhome.Building', verbose_name=_(u'дом'))
    rooms_total = models.PositiveSmallIntegerField(_(u'жилых комнат'), blank=True, null=True)
    image = models.ImageField(verbose_name="изображение", upload_to=make_layout_image_upload_path, blank=True)
    area = models.DecimalField(_(u'общая площадь'), help_text=_(u'м2'), max_digits=5, decimal_places=2)

    basead = models.ForeignKey(BaseAd, verbose_name=_(u'недвижимость'), related_name='newhome_layouts', null=True,
                               blank=True, on_delete=models.SET_NULL)

    def get_similar_layouts_id(self):
        return list(self.newhome.layouts.filter(rooms_total=self.rooms_total).values_list('id', flat=True))

    @property
    def has_available_flats(self):
        similar_layouts = self.get_similar_layouts_id()
        unavailable_on_floor = list(Flat.objects.filter(
            layout__in=similar_layouts, is_available=False).values_list('floor', flat=True))
        return Floor.objects.filter(layouts__in=similar_layouts).exclude(id__in=unavailable_on_floor).exists()

    @property
    def available_floors(self):
        similar_layouts = self.get_similar_layouts_id()
        unavailable_on_floor = list(Flat.objects.filter(
            layout__in=similar_layouts, is_available=False).values_list('floor', flat=True))
        floors = set(Floor.objects.filter(
            layouts__in=similar_layouts).exclude(id__in=unavailable_on_floor).values_list('number', flat=True))

        return u', '.join(map(str, floors))

    def get_available_areas(self):
        areas = self.newhome.layouts.filter(
            area__gt=0).aggregate(area_from=models.Min('area'), area_to=models.Max('area'))

        if areas.get('area_from') and areas.get('area_to'):
            return u'от %s до %s' % (areas.get('area_from'), areas.get('area_to'))

        return ''

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = u'планировка'
        verbose_name_plural = u'планировки'

receiver(post_save, sender=Layout)(post_save_clean_image_file)
receiver(post_delete, sender=Layout)(post_delete_clean_image_file)


@receiver(post_save, sender=Layout)
def update_layout_ad(sender, instance, **kwargs):
    """
    Добавляем привязку к объявлению, если у нас доступны: площадь, кол-во комнат, изображение и какая-то из планировок
    с таким же количеством комнат уже есть в наличии
    """

    dirty_fields = set(instance.get_dirty_fields().keys())
    fields = {'image', 'area', 'rooms_total'}
    if fields & dirty_fields and not instance.basead:
        fields_prepared = True
        for field in fields:
            if not getattr(instance, field):
                fields_prepared = False
                break

        similar_layouts = instance.newhome.layouts.filter(
            rooms_total=instance.rooms_total, basead__isnull=False).first()
        if similar_layouts is not None and fields_prepared:
            instance.basead = similar_layouts.basead
            instance.save()


@receiver(post_save, sender=Layout)
def update_ad_images(sender, instance, **kwargs):
    """
    Обновляем изображения у объявления, если у планировки появилась привязка к объявлению
    """

    dirty_fields = instance.get_dirty_fields(check_relationship=True)

    if 'basead' in dirty_fields and not dirty_fields['basead']:
        last_photo = Photo.objects.filter(basead=instance.basead).last()
        position = last_photo.order + 1 if last_photo else 0

        if default_storage.exists(instance.image.name):
            content = default_storage.open(instance.image.name).read()
            img = Photo(basead=instance.basead, order=position, caption='')
            img.image.save('temporary_name', ContentFile(content))


class LayoutNameOption(models.Model):
    name = models.CharField(_(u'название'), max_length=50, help_text=_(u'Введите название планировки'))

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = u'вариант'
        verbose_name_plural = u'варианты названий планировки'


@receiver(post_delete, sender=Layout)
def remove_ad(sender, instance, **kwargs):
    """При удалении планировки - удаляем объявления, чтобы обработались сигналы - по одному"""

    from ad.models import Ad
    for ad in Ad.objects.filter(newhome_layouts=instance):
        ad.delete()


class LayoutFlat(models.Model):
    """
    Координаты планировок квартир
    Вынесено в отдельную модель, т.к. на этаже может быть более одной одинаковой планировки
    """
    layout = models.ForeignKey('newhome.Layout', verbose_name=_(u'планировка квартиры'), related_name='layout_flats')
    floor = models.ForeignKey('newhome.Floor', verbose_name=_(u'этаж'), related_name='floor_flats', null=True)
    coordinates = models.TextField(_(u'Координаты'), blank=True, help_text=_(u'Для выделения на изображении этажа'))
    price = models.BigIntegerField(_(u'цена'), default=0)
    currency = models.CharField(_(u'валюта цены'), choices=ad_choices.CURRENCY_CHOICES, default='UAH', max_length=3)


class Room(models.Model):
    """Комнаты планировок квартир"""
    layout = models.ForeignKey(Layout, verbose_name=_(u'планировка'), related_name='rooms')
    image_num = models.CharField(_(u'позиция'), help_text=_(u'Позиция на изображении'), max_length=5, blank=True)
    name = models.CharField(_(u'название'), help_text=_(u'Введите название комнаты'), max_length=50, blank=True)
    area = models.DecimalField(_(u'площадь'), help_text=_(u'кв. м'), max_digits=5, decimal_places=2, blank=True)

    class Meta:
        ordering = ('id', )
        verbose_name = u'помещение'
        verbose_name_plural = u'помещения'


class Building(models.Model):
    name = models.CharField(_(u'название дома'), help_text=_(u'например: дом 1'), max_length=50)
    newhome = models.ForeignKey(Newhome, verbose_name=_(u'новостройка'), related_name='buildings')

    class Meta:
        verbose_name = u'дом'
        verbose_name_plural = u'дома'
        ordering = ('name',)

    def __unicode__(self):
        return u'%s: %s' % (self.newhome, self.name)


class BuildingSection(models.Model):
    building = models.ForeignKey('newhome.Building', verbose_name=_(u'Дом'), related_name='sections')
    position = models.PositiveIntegerField(_(u'Номер секции'), default=1)

    class Meta:
        verbose_name = u'секция'
        verbose_name_plural = u'секции'
        ordering = ('building__name', 'position')

    def __unicode__(self):
        return u'%s, секция %s' % (self.building.name, self.position)


class BuildingQueue(models.Model):
    newhome = models.ForeignKey(Newhome, verbose_name=_(u'новостройка'), related_name='queues')
    name = models.CharField(_(u'Название очереди'), max_length=50)
    finish_at = models.CharField(_(u'Окончание строительства'), max_length=20)
    sections = models.ManyToManyField('newhome.BuildingSection', verbose_name=_(u'Дома и секции для очереди'))
    comment = models.TextField(
        _(u'Комментарий'), blank=True, help_text=_(u'Опишите в вольной форме статус строительства, '
                                                   u'например: дом 1 сдан, в доме 3 — ведутся кладочные работы. ')
    )


class Flat(DirtyFieldsMixin, models.Model):
    newhome = models.ForeignKey(Newhome, verbose_name=_(u'новостройка'), related_name='flats')
    floor = models.ForeignKey(Floor, verbose_name=_(u'этаж'))
    layout = models.ForeignKey(Layout, verbose_name=_(u'планировка'))
    is_available = models.BooleanField(verbose_name=_(u'наличие'), default=True)
    price = models.PositiveIntegerField(_(u'цена за квадратный метр'), default=0)

    class Meta:
        verbose_name = u'квартира в наличии'
        verbose_name_plural = u'квартиры в наличии'

    def __unicode__(self):
        return u'%s' % self.id


@receiver(post_save, sender=Flat)
def dirty_flat(instance, **kwargs):
    dirty_fields = instance.get_dirty_fields().keys()

    # Если изменилось наличие, то публикуем или снимаем с публикации обычные объявления
    if 'is_available' in dirty_fields and instance.layout.basead:
        if instance.is_available and instance.layout.basead.status == 210:
            instance.layout.basead.status = 1
            instance.layout.basead.save()

        elif not instance.layout.has_available_flats and instance.layout.basead.status == 1:
            instance.layout.basead.status.status = 210
            instance.layout.basead.save()


class Progress(models.Model):
    newhome = models.ForeignKey(Newhome, verbose_name=_(u'новостройка'), related_name='progress')
    date = models.DateField(_(u'дата'))
    name = models.CharField(_(u'название очереди/дома'), max_length=100, blank=True)

    class Meta:
        verbose_name = u'отчет о ходе строительства'
        verbose_name_plural = u'отчеты о ходе строительства'
        ordering = ('date',)

    def __unicode__(self):
        return (u'%s, %s' % (self.date, self.name)).strip(u', ')


def make_progressphoto_image_upload_path(progress_photo, filename):
    root, ext = os.path.splitext(filename)
    return 'upload/newhome/progressphoto/%d_%s%s' % (progress_photo.progress.newhome_id, uuid.uuid4().hex, ext)


class ProgressPhoto(models.Model, DirtyFieldsMixin):
    progress = models.ForeignKey(Progress, verbose_name=_(u'отчет о ходе строительства'), related_name='photos')
    image = models.ImageField(_(u'изображение'), upload_to=make_progressphoto_image_upload_path)

    class Meta:
        verbose_name = u'фото для отчетов'
        verbose_name_plural = u'фото для отчетов'

receiver(post_save, sender=ProgressPhoto)(post_save_clean_image_file)
receiver(post_delete, sender=ProgressPhoto)(post_delete_clean_image_file)


def make_newhomephoto_image_upload_path(newhome_photo, filename):
    root, ext = os.path.splitext(filename)
    return 'upload/newhome/photo/%d_%s%s' % (newhome_photo.newhome_id, uuid.uuid4().hex, ext)


class NewhomePhoto(models.Model, DirtyFieldsMixin):
    newhome = models.ForeignKey(Newhome, verbose_name=_(u'жк'), related_name='newhome_photos')
    image = models.ImageField(_(u'изображение'), upload_to=make_newhomephoto_image_upload_path)
    is_main = models.BooleanField(verbose_name=_(u'основная?'), default=False)

    class Meta:
        verbose_name = u'фото жк'
        verbose_name_plural = u'фото жк'
        ordering = ('-is_main', 'id')

receiver(post_save, sender=NewhomePhoto)(post_save_clean_image_file)
receiver(post_delete, sender=NewhomePhoto)(post_delete_clean_image_file)


VIEWSCOUNT_CHOICES = (
    (0, u'просмотр объявления'),
    (1, u'просмотр контактов'),
    (2, u'форма наличия квартиры новостройки'),
)


class ViewsCount(models.Model):
    date = models.DateField(u'дата')
    newhome = models.ForeignKey(Newhome, verbose_name=u'новостройка', related_name='viewscounts')
    type = models.PositiveIntegerField(u'тип счетчика', choices=VIEWSCOUNT_CHOICES, default=0, db_index=True)
    views = models.PositiveIntegerField(u'просмотров', default=1)

    class Meta:
        verbose_name = u'просмотр объекта'
        verbose_name_plural = u'просмотры объектов'
