# coding=utf-8
import hashlib
import random
import re
import itertools

from collections import defaultdict
from urlparse import urlparse

from django.core.cache import cache
from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from utils import yandex_translator


class SEORule(models.Model):
    """
    Настройка правил для СЕОшников через web-интерфейс
    """

    seo_title = models.CharField(
        verbose_name=u'Внутреннее имя правила',
        max_length=255,
        blank=True
    )
    deal_type = models.CharField(
        verbose_name=u'Тип сделки',
        choices=(
            ('deafult', u'По умолчанию'),
            ('sale', u'Купить'),
            ('rent', u'Долгосрочная аренда'),
            ('rent_daily', u'Аренда посуточно'),
            ('newhomes', u'Новостройки'),
            ('index', u'Главная страница'),
        ),
        default='default',
        max_length=12
    )
    region_kind = models.CharField(
        verbose_name=u'Тип региона',
        choices=(
            ('default', u'По умолчанию'),
            ('country', u'Страна'),
            ('province', u'Провинция'),
            ('area', u'Область'),
            ('locality', u'Населенный пункт'),
            ('village', u'Село'),
            ('district', u'Район'),
            ('street', u'Улица'),
        ),
        default='default',
        max_length=12
    )
    subpage = models.CharField(
        verbose_name=u'Подстраницы  раздела',
        choices=(
            ('default', u'По умолчанию'),
            ('streets', u'Список улиц'),
            ('metro_stations', u'Список станций метро'),
        ),
        default='default',
        max_length=15
    )
    property_type = models.CharField(
        verbose_name=u'Тип объекта',
        choices=(
            ('default', u'По умолчанию (квартира)'),
            ('room', u'Комната'),
            ('house', u'Дом'),
            ('commercial', u'Коммерческая недвижимость'),
            ('plot', u'Участок'),
            ('garages', u'Гараж'),
            ('all-real-estate', u'Недвижимость'),
        ),
        default='default',
        max_length=20
    )
    check_rooms = models.BooleanField(
        verbose_name=u'Учитывать количество комнат при фильтрации?',
        help_text=u'Работает только для типов объекта: Квартира или Дом + указано количество комнат в поиске',
        default=False
    )
    check_subway = models.BooleanField(
        verbose_name=u'Учитывать метро при фильтрации?',
        default=False
    )
    check_not_main_city = models.BooleanField(
        verbose_name=u'Город, не областной центр, без субдомена',
        default=False
    )

    title = models.CharField(verbose_name=u'Title', max_length=255, blank=True, null=True)
    description = models.CharField(verbose_name=u'Description', max_length=255, blank=True, null=True)
    keywords = models.CharField(verbose_name=u'Keywords', max_length=255, blank=True, null=True)
    h1 = models.CharField(verbose_name=u'H1', max_length=255, blank=True, null=True)
    crosslink_header = models.CharField(verbose_name=u'Заголовок блока перелинковки', max_length=255, blank=True, null=True)

    def __unicode__(self):
        return u" | ".join(([
            self.get_deal_type_display(),
            self.get_subpage_display(),
            self.get_region_kind_display(),
            self.get_property_type_display() + (u', по комнатам' if self.check_rooms else '')
            + (u', по метро' if self.check_subway else '') + (u', небольшой город' if self.check_not_main_city else ''),
        ]))

    def get_priority_key(self):
        return '_'.join([self.deal_type, self.subpage, self.region_kind, self.property_type,
                         str(self.check_rooms), str(self.check_subway), str(self.check_not_main_city)])

    @staticmethod
    def get_suitable_rules(region, deal_type, property_type, subpage, rooms, subway):
        """
        Возвращает список подходящих правил и словарь метатегов из этих правил для текущего (!) языка

        :param region: Регион
        :param deal_type: Тип сделки
        :param property_type: Тип недвижимости
        :param subpage: Имя view страницы фильтра комнат из GET
        :param rooms: Значение фильтра комнат из GET
        :return: tuple
            rules (list) список правил в порядке приоритета в виде [правило, словарь взятых из правила метатегов], ...
            seo (dict) словарь с выбранными метатегами {имя метатега: фраза}
        """
        # Определяем приоритеты в выборе нужного правила для генерации SEO
        priority_keys = []
        best_match = [deal_type, subpage, region.kind, property_type]
        check_rooms_conditions = ['False']
        check_subway_conditions = ['False']
        check_town_conditions = ['False']

        # для домов/квартир на страницах с фильтрам по количеству комнат приоритетными будут правила с check_rooms=True
        if property_type in ['house', 'default', 'garages', 'commercial'] and rooms:
            check_rooms_conditions.insert(0, 'True')

        if subway:
            check_subway_conditions.insert(0, 'True')

        if region.kind in ['locality'] and (not region.subdomain):
            check_town_conditions.insert(0, 'True')

        # Формируем правила, добавляем к ним наличие комнат, метро, проверяем маленький город
        # Прохождение всего цикла от 8 до 32 раз (маленький город(town) не имеет метро)
        for check_town in check_town_conditions:
            for check_subway in check_subway_conditions:
                for check_rooms in check_rooms_conditions:
                    for x in xrange(0, 8):
                        case_in_binary = bin(0b11111 - x)[3:]
                        case_arr = []
                        for index, val in enumerate(best_match):
                            if int(case_in_binary[index]):
                                case_arr.append(val)
                            else:
                                case_arr.append('default')
                        case = '_'.join(case_arr + [check_rooms]+[check_subway]+[check_town])

                        if case not in priority_keys:
                            priority_keys.append(case)

        # получаем из базы список правил, которые могут нам подойдти
        seo_rules = SEORule.objects.filter(
            deal_type__in=[deal_type, 'default'],
            region_kind__in=[region.kind, 'default'],
            property_type__in=[property_type, 'default'],
            subpage__in=[subpage, 'default'],
        )

        # заполняем словарь с правилами, чтобы можно было получить к ним доступ по уникальному ключу
        seo_data = {}
        for seo_rule in seo_rules:
            seo_data[seo_rule.get_priority_key()] = seo_rule

        seo = {}
        rules = []

        # Выбираем нужное правило
        for pk in priority_keys:
            if pk in seo_data:
                rule = seo_data[pk]
                phrases_in_rule = {}
                for key in ['title', 'description', 'keywords', 'h1', 'crosslink_header']:
                    if getattr(rule, key) and key not in seo:
                        seo[key] = phrases_in_rule[key] = getattr(rule, key)

                rules.append([rule, phrases_in_rule])

        return rules, seo

    class Meta:
        verbose_name = u'SEO правило'
        verbose_name_plural = u'SEO правила'


def translate_python_formatted_text(text):
    # алгоритм: вырезаем куски текста без форматтеров, переводим их и склеиваем в одну строку с форматтерами
    #
    # если переводить целую строку вместе с форматтерами (как было в прежнем алгоритме),
    # то в некоторых случаях теряется часть форматтера перед точкой:
    #   [ru] Снять %(prop_room_chto)s - %(city)s, %(province)s. Аренда %(prop_room_chego_short)s
    #   [uk] Зняти %(prop_room_chto)s - %(city)s, %(province). Оренда %(prop_room_chego_short)s
    #
    # предлог "в", стоящий перед форматтером также не переводим, включаем его в кусок с форматтером,
    # в противном случае иногда он может перевестись как "у"
    #   [ru] Снять %(prop_room_chto)s в %(city_gde)s. Аренда %(prop_room_chego_short)s
    #   [uk] Зняти %(prop_room_chto)s у %(city_gde)s. Оренда %(prop_room_chego_short)s
    # или потеряться при переводе куска, который был перед форматтером и оканчивается предлогом "в"
    #   [ru] Аренда недвижимости в
    #   [uk] Оренда нерухомості

    formatter_with_preposition_re = u'(?: в )?%\(.*?\)s'

    plaintext_chunks = re.split(formatter_with_preposition_re, text)
    formatted_chunks = re.findall(formatter_with_preposition_re, text)

    translated_plaintext_chunks = yandex_translator.translate(plaintext_chunks, 'ru-uk')
    zipped = itertools.izip_longest(translated_plaintext_chunks, formatted_chunks, fillvalue='')

    return u''.join(itertools.chain(*zipped))


@receiver(pre_save, sender=SEORule)
def translate_seorule(instance, **kwargs):
    if not instance.crosslink_header_uk and instance.crosslink_header_ru:
        instance.crosslink_header_uk = translate_python_formatted_text(instance.crosslink_header_ru)

    if not instance.h1_uk and instance.h1_ru:
        instance.h1_uk = translate_python_formatted_text(instance.h1_ru)

    if not instance.title_uk and instance.title_ru:
        instance.title_uk = translate_python_formatted_text(instance.title_ru)

    if not instance.keywords_uk and instance.keywords_ru:
        instance.keywords_uk = translate_python_formatted_text(instance.keywords_ru)

    if not instance.description_uk and instance.description_ru:
        instance.description_uk = translate_python_formatted_text(instance.description_ru)


@receiver(post_save, sender=SEORule)
def clear_cache(instance, **kwargs):
    for lang, name in settings.LANGUAGES:
        cache.delete('translated_rules_02_%s_%s' % (instance.get_priority_key(), lang))


class SEOCachedPhrase(models.Model):
    """
    Кешированные фразы
    """

    cached_phrases = None
    is_cache_changed = False
    _cache_time = 60 * 60
    _cache_key = 'seo_cached_phrase'

    phrase = models.CharField(
        verbose_name=u'Кешированная фраза',
        max_length=255
    )
    hash_string = models.CharField(
        verbose_name=u'Хэш русской строки',
        max_length=32,
        blank=True,
        null=True
    )

    def set_cache(self):
        """
        Вспомогательная функция на обновление кеша одним запросом, вместа множества
        """
        if self.is_cache_changed:
            cache.set(self._cache_key, self.cached_phrases, self._cache_time)

    def get_translated_phrase(self, phrase, set_cache=True):
        """
        Получаем переведенную фразу
        """

        if self.cached_phrases is None:
            self.cached_phrases = self.get_cached_phrases()

        hs = hashlib.md5()
        hs.update(phrase.encode('utf-8'))
        hash_string = hs.hexdigest()

        if hash_string not in self.cached_phrases:
            # Добавляем новую фразу для перевода
            scp = SEOCachedPhrase()
            scp.phrase_ru = phrase
            scp.hash_string = hash_string
            scp.save()

            # Расширяем кеш переведенных фраз
            self.is_cache_changed = True
            self.cached_phrases[hash_string] = scp.phrase_uk
            if set_cache:
                cache.set(self._cache_key, self.cached_phrases, self._cache_time)

            phrase = scp.phrase_uk

        else:
            phrase = self.cached_phrases[hash_string]

        return phrase

    def get_cached_phrases(self):
        """
        Получаем список закешированных фраз, либо готовим новые
        """

        phrases = cache.get(self._cache_key, None)
        if phrases is None:
            scp_list = SEOCachedPhrase.objects.all()
            phrases = {}

            for scp in scp_list:
                phrases[scp.hash_string] = scp.phrase_uk

            cache.set(self._cache_key, phrases, 60 * 60)

        return phrases


@receiver(pre_save, sender=SEOCachedPhrase)
def seo_phrase_pre_save(instance, **kwargs):
    if not instance.phrase_uk:
        instance.phrase_uk = translate_python_formatted_text(instance.phrase_ru)

    if not instance.hash_string:
        md5 = hashlib.md5(instance.phrase_ru.encode('utf-8'))
        instance.hash_string = md5.hexdigest()


class TextBlock(models.Model):
    url = models.URLField(_(u'ссылка на страницу'), max_length=255, unique=True)
    title = models.CharField(_(u'заголовок блока'), max_length=255, blank=True)
    region = models.ForeignKey('ad.Region', verbose_name=_(u'регион'), null=True, related_name='textblocks')
    text = models.TextField(_(u'текст блока'), blank=True, default='')

    class Meta:
        verbose_name = u'текстовый блок'
        verbose_name_plural = u'текстовые блоки'

    @staticmethod
    def find_by_request(request, region=None):
        production_url = request.build_absolute_uri().replace(settings.MESTO_PARENT_HOST, "mesto.ua")
        try:
            return TextBlock.objects.get(region=region, url=production_url)
        except TextBlock.DoesNotExist:
            return None

    @staticmethod
    def generate_text_block(request, deal_type, property_type, region=None):
        # выбор шаблона текста
        text = None
        if region.kind == 'street' and property_type == 'flat' and request.LANGUAGE_CODE == 'ru':
            if deal_type == 'sale' :
                if not request.META['QUERY_STRING']:
                    text = u'''
                        Купить квартиру %(full_name)s без посредников можно в несколько кликов. Для этого необходимо
                        [посетить портал|зайти на сайт|зайти на онлайн портал] недвижимости %(domain)s и выбрать раздел сайта "Продажа".
                        Чтобы не тратить время на использование системы сортировки, советуем нажать на cписок улиц и выбрать в нем подходящую.
                        [Такая фильтрация|Функционал|Данная опция|Подбор по параметрам] понравится соискателям жилья на вторичном рынке,
                        потому что экономит время на поиски и моментально отображает [объекты|объявления|предложения|варианты] продажи, которые располагаются по указанному адресу.
                        Перед потенциальным покупателям появятся [объявления|объекты|предложения|варианты] о продаже квартир %(full_name)s,
                        с которыми можно ознакомиться в предварительном порядке. Для большего удобства [рекомендуем|советуем|предлагаем] посмотреть карту местности:
                        она позволит оценить достоинства и недостатки места расположения [недвижимости|квартиры|жилья |недвижимого имущества] и сделать окончательный выбор.
                        '''
                elif len(request.GET.getlist('rooms')) == 1 and len(request.GET) == 3:
                    text = u'''
                        Купить %(rooms_str)sкомнатную квартиру %(full_name)s без посредников на вторичном рынке не составит большого труда.
                        Необходимо просто [посетить портал|зайти на сайт|зайти на онлайн портал|открыть ресурс о|зайти на ресурс о|сделать запрос на портале|открыть портал|перейти по ссылке портала] недвижимости %(domain)s в соответствующий раздел с объявлениями.
                        Разобраться в огромной базе данных можно благодаря системе сортировки выгодных предложений продавцов.
                        [Такую фильтрацию|Функционал|Данную опцию|Подбор по параметрам|Сортировку|Возможность ускорить поиск|Простой и понятный инструментарий] высоко оценят потенциальные покупатели %(rooms)s  комнатных квартир.
                        Благодаря ей клиенты значительно экономят время, поскольку сразу видят подходящие [объекты|объявления|предложения|варианты] продажи жилья и таким же адресным размещением.
                        Желающим стать владельцами %(rooms_str)sкомнатных квартир %(full_name)s предоставляется возможность ознакомиться с ними до личного визита.
                        Сделать это можно как с помощью непосредственного изучения объекта, так и при задействовании интерактивной карты местности.
                        [Рекомендуем|Советуем|Предлагаем|Напоминаем] использовать эту функцию по максимуму: ее возможности проявляются в изучении геолокации [недвижимости|объекта|жилья|недвижимого имущества|понравившегося предложения|подходящего недвижимого объекта] оценке преимуществ от такого расположения и помощи в принятии окончательного решения.
                        '''

        if not text:
            return None

        random_by_url = random.Random()
        random_by_url.seed(request.build_absolute_uri())

        # выбор фраз из синонимов
        for token in re.findall(r'\[[^\[]*\]', text):
            word = random_by_url.choice(token.strip('[]').split('|')).strip()
            text = text.replace(token, word)

        data = {
            'domain': request.META['HTTP_HOST'],
            'full_name': u'на %s' % region.nameD['gde'],
            'title': u'Продажа квартир на %s' % region.nameD['gde'],
            'rooms': [u'', u'1-но', u'2-х', u'3-х', u'4-х', u'5-ти'][int(request.GET.get('rooms', 0))],
            'rooms_str': [u'', u'одно', u'двух', u'трех', u'четырех', u'пяти'][int(request.GET.get('rooms', 0))],
        }

        for region_in_path in region.get_parents()[::-1]:
            if region_in_path.kind == 'district':
                data['full_name'] += u' в %s' % region_in_path.nameD['gde']
            if region_in_path.kind in ['locality', 'village', 'group', 'group2']:
                data['full_name'] += u' %s' % region_in_path.nameD['chego']

        text_block = TextBlock(title=data['title'], text=text % data)
        return text_block


    def __unicode__(self):
        return self.url

# TODO: эта х..нь работает только для регионов с поддоменами, нужно как-то переделать с использованием стандартного URL dispatcher
@receiver(pre_save, sender=TextBlock)
def set_region_from_url(sender, instance, **kwargs):
    from ad.models import Region
    instance.region = Region.get_region_and_params_from_url(instance.url).get('region')
