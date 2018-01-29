# coding: utf-8
import re
from django.core.cache import cache
from django.utils.translation import ugettext_lazy as _
from seo.cross_linking import check_uk_preposition
from seo.models import SEORule, SEOCachedPhrase


PROPERTY_TYPE_ASSOC = {
    # ..., аренда, купить
    # именительный, родительный (кого,чего), винительный (кого/что)
    'default': (u'недвижимость', u'недвижимости', u'недвижимость', u'недвижимости', u'недвижимости'),
    'flat': (u'квартира', u'квартиры', u'квартиру', u'квартиры', u'квартир'),
    'room': (u'комната', u'комнаты', u'комнату', u'комнаты', u'комнат'),
    'house': (u'дом', u'дома', u'дом', u'дома', u'домов'),
    'plot': (u'участок', u'участка', u'участок', u'участки', u'участков'),
    'commercial': (u'коммерческая недвижимость', u'коммерческой недвижимости', u'коммерческую недвижимость',
                   u'коммерческие недвижимости', u'коммерческой недвижимости'),
    'property': (u'недвижимость', u'недвижимости', u'недвижимость', u'недвижимости', u'недвижимости'),
    'garages': (u'гараж', u'гаража', u'гараж', u'гаражи', u'гаражей'),
    'other': (u'другое', u'другого', u'другое', u'', u''),
}

DEAL_TYPE_SYNONYMS = {
    'sale': (u'Продажа', u'Покупка', u'Продать', u'Купить', u'На вторичном рынке'),
    'rent': (u'Долгосрочная аренда', u'Снять', u'Сдать', u'Арендовать', u'Снять долгосрочно',
             u'Сдать долгосрочно', u'Арендовать долгосрочно', u'Сниму', u'Сдам'),
    'rent_daily': (u'Посуточная аренда', u'Аренда посуточно', u'Снять на сутки',
                   u'Снять посуточно', u'Сдать посуточно', u'Снять на час',
                   u'Арендовать посуточно', u'Сниму посуточно', u'Сдам посуточно'),
    'newhomes': (u'Продажа в новостройке', u'Покупка новострой', u'Продажа от застройщика', u'Купить в новостройке'),
}


def ifexist(yep, nope):
    return yep if yep else nope


def get_details_newhome_metatags(region, item):
    city = region.get_parents(kind='locality')
    if not city:
        city = region.get_parents(kind='village')

    if not city:
        addr_city = item.addr_city
    else:
        addr_city = city[0].name

    name = item.name.replace(u"ЖК ", "").replace(u"Жилой комплекс", "")
    context = {'addr_street': item.addr_street,
               'addr_city': addr_city,
               'price': item.price_at,
               'name': name}

    title = u'Жилой комплекс %(name)s - %(addr_city)s Mesto.ua' % context
    description = (
                      u'Продажа квартир в жилом комплексе %(name)s %(addr_street)s %(addr_city)s. '
                      u'Купить новую квартиру в ЖК %(name)s от застройщика – новостройки от Mesto.ua'
                  ) % context

    return title, description


def get_details_metatags(region, item):
    area = item.area
    if area is None:
        area = 0
    area = int(area)

    # Получаем список от страны ... к улице
    full_addr_array = region.get_parents()
    full_addr_array.reverse()
    full_addr = u''

    # Превращаем в строку, отбросив страну и область, если есть добавляем номер дома
    for i in xrange(len(full_addr_array) - 2):
        full_addr += full_addr_array[i].nameD['original']
        if i == 0 and item.addr_house != u'':
            full_addr += " %s" % item.addr_house
        if i != (len(full_addr_array) - 3):
            full_addr += ', '
        else:
            pass

    # Если геосервис не нашел улицу, выводим то что написал пользователь
    if len(full_addr_array) == 3:
        full_addr = item.address

    deal_type_variant_1 = DEAL_TYPE_SYNONYMS[item.deal_type][3]
    deal_type_variant_2 = DEAL_TYPE_SYNONYMS[item.deal_type][0]
    property_type_variant_1 = PROPERTY_TYPE_ASSOC[item.property_type][2]
    property_type_variant_2 = PROPERTY_TYPE_ASSOC[item.property_type][1]
    property_type_variant_3 = PROPERTY_TYPE_ASSOC[item.property_type][4]
    context = {'addr_house': item.addr_house,
               'addr_city': item.addr_city,
               'deal1': deal_type_variant_1,
               'deal2': deal_type_variant_2,
               'property1': property_type_variant_1,
               'property2': property_type_variant_2,
               'property3': property_type_variant_3,
               'price': item.price,
               'rooms': item.rooms,
               'area': area,
               'currency': item.currency,
               'full_addr': full_addr}

    title = _(u'%(deal1)s %(property1)s %(full_addr)s - Mesto.ua') % context
    if item.property_type == "flat" or item.property_type == "house":
        title = _(u'%(deal1)s %(property1)s %(full_addr)s - Mesto.ua') % context
        description = _(u'%(deal2)s %(rooms)s комн. %(property2)s, %(full_addr)s, %(area)s кв.м. Стоимость - %(price)s %(currency)s. '
                        u'%(deal1)s %(property1)s %(addr_city)s. '
                        u'Большая база объявлений продажи %(property3)s на портале Mesto.ua') % context
    elif item.property_type == "plot":
        description = _(u'%(deal2)s %(property2)s, %(full_addr)s, %(area)s соток. Стоимость - %(price)s %(currency)s. '
                        u'%(deal1)s %(property1)s %(addr_city)s. '
                        u'Большая база объявлений продажи %(property3)s на портале Mesto.ua') % context
    else:
        description = _(u'%(deal2)s %(property2)s, %(full_addr)s, %(area)s кв.м. Стоимость - %(price)s %(currency)s. '
                        u'%(deal1)s %(property1)s %(addr_city)s. '
                        u'Большая база объявлений продажи %(property3)s на портале Mesto.ua') % context

    return title, description


def get_professionals_search_metatags(region, type):
    context = {'chego': region.nameD['chego'], 'gde': region.nameD['gde']}
    if type == 'agency':
        title = _(u'Все агентства недвижимости %(chego)s – Mesto.ua') % context
        description = _(u'Ищите агентство недвижимости в %(chego)s? Портал недвижимости Mesto.ua предоставляет список агентств недвижимости и лучших риэлторских агентств %(chego)s') % context
    elif type == 'realtor':
        title = _(u'Риелторы %(chego)s - Mesto.ua') % context
        description = _(u'Ищите риелтора в %(gde)s? Список лучших частных риэлторов и риэлтерских компаний %(chego)s собрано на портале надвижимости Mesto.ua') % context
    else:
        title = _(u'Профессионалы недвижимости %(chego)s – Mesto.ua') % context
        description = _(u'Лучшие профессионалы, агентства недвижимости и риэлтерские компании %(chego)s на портале недвижимости Mesto.ua') % context
    return title, description

def get_professionals_agency_metatags(region, agency):
    context = {'agency_name' : agency.name, 'gde': region.nameD['gde']}
    title = _(u'Агентство недвижимости %(agency_name)s - Mesto.ua') % context
    description = _(u'Агентство недвижимости %(agency_name)s в %(gde)s. Все объявления агентства недвижимости %(agency_name)s на портале Mesto.ua') % context
    return title, description

def get_professionals_realtor_metatags(region, realtor):
    context = {'realtor_name' : realtor.user.get_full_name(), 'chego': region.nameD['chego']}
    title = _(u'Риелтор %(chego)s %(realtor_name)s – Mesto.ua') % context
    description = _(u'Риелтор %(chego)s %(realtor_name)s специалист в сфере аренды и продаже всех типов недвижимости') % context
    return title, description

def get_meta_for_guide(region, category):
    titles = {
        'news': _(u'Новости недвижимости %(city_chego)s'),
        'events': _(u'Последние события в %(city_gde)s'),
        'places': _(u'Интересные места %(city_chego)s'),
        'must_know': _(u'Стоит знать - %(city_original)s Mesto.ua'),
        'school': _(u'Новости Mesto School'),
    }
    descriptions = {
        'news': _(u'Последние новости рынка недвижимости %(city_chego)s на портале Mesto.ua. Всегда свежие и актуальные новости недвижимости города %(city_original)s и %(province_chego)s читайте на нашем сайте'),
        'events': _(u'Перечень и расписание самых интересных событий %(city_chego)s на Mesto.ua. Обзор последних событий %(city_chego)s и %(province_chego)s смотрите на нашем портале недвижимости'),
        'places': _(u'Самые интересные места города %(city_original)s можно найти на нашем портале недвижимости Mesto.ua. Обзор достопримечательностей и интересных мест %(city_chego)s доступен на нашем сайте'),
        'must_know': _(u'Новости дизайна и интерьера на портале недвижимости %(city_original)s Mesto.ua. Последние тенденции в ремонте квартир и домов, готовые решения для разных типов жилья'),
        'school': _(u''),
    }

    data = {'city_%s' % question: declension for question, declension in region.nameD.items()}
    try:
        province = region.get_parents(kind='province')[0]
        data.update({'province_%s' % question: declension for question, declension in province.nameD.items()})
    except IndexError:
        data.update({'province_%s' % question: '' for question, declension in region.nameD.items()})

    title = titles.get(category, _(u'Новости рынка')) % data
    description = descriptions.get(category, u'') % data
    return title, description


def get_property_type(property_type, case):
    try:
        return PROPERTY_TYPE_ASSOC[property_type][case-1]

    except:
        return PROPERTY_TYPE_ASSOC['default'][case-1]


def get_relation_links(region):
    from django.template.loader import render_to_string

    property_type = getattr(region, 'property_type')
    cache_key = 'relation_links_reg%s_%s_%s' % (region.pk, region.deal_type, ifexist(region.property_type, 'all'))
    relation_links = cache.get(cache_key)
    if not relation_links:
        data = {
            'prop': get_property_type(region.property_type, 4),
            'prop_chego': get_property_type(region.property_type, 5),
        }
        blocks_templates = [
            ['sale', u'Продажа %(prop_chego)s', u'Продажа %(prop_chego)s в %(region_gde)s'],
            ['rent', u'Аренда %(prop_chego)s', u'Аренда %(prop_chego)s в %(region_gde)s'],
            ['rent_daily', u'Посуточно %(prop)s', u'Посуточно %(prop)s в %(region_gde)s'],
            ['newhomes', u'Новостройки %(prop)s', u'Новостройки %(prop)s в %(region_gde)s'],
        ]
        siblings = region.get_siblings()
        blocks = []
        for template in blocks_templates:
            block = {'title': template[1] % data, 'links': []}
            for region in siblings:
                data['region_gde'] = region.nameD['gde']
                block['links'].append({'link':region.get_deal_url(template[0], check_property_type(property_type, template[0])), 'text': template[2] % data})
            blocks.append(block)

        relation_links = render_to_string('property/search_links.html', locals())
        cache.set(cache_key, relation_links, 3600*24*365)

    return relation_links


def check_property_type(property_type=None, deal_type=None):
    if property_type in PROPERTY_TYPE_ASSOC:
        return property_type
    return None


def image_title(property):
    from ad.choices import DEAL_TYPE_CHOICES
    deal_type_name = [row[1].title() for row in DEAL_TYPE_CHOICES if row[0] == property.deal_type][0]
    last_path = property.region.get_parents()[2:]
    try:
        text = u'раздел %s в %s %s' % (deal_type_name.lower(), last_path[0].nameD['gde'], last_path[1].name )

    except:
        text = u'раздел %s в %s' % (deal_type_name.lower(), property.region.nameD['gde'] )

    return u'%s - %s' % (property.title, text)


class BulkRegion(object):
    name = ''
    old_name = ''
    nameD = {'original': '', 'chego': '', 'chemu': '', 'chto': '', 'chem': '', 'gde': ''}


class SEO(object):
    """
    Основной класс управления СЕО
    """
    scp = None
    _instance = None
    _current_language = 'ru'
    _data = {}
    _region = None
    _deal_type = 'default'
    _region_kind = 'default'
    _property_type = ''
    _rooms = 0
    _cache_key_rules = ''
    _cache_key_rules_prefix = 'translated_rules_02'
    _cache_time = 60 * 60
    _car_count = [u'одну', u'две', u'три', u'четыре', u'пять']
    _room_count = [u'одно', u'двух', u'трех', u'четырех', u'пяти']
    _room_count_short = [u'1', u'2-х', u'3-х', u'4-х', u'5-и']
    _room_cases = [
        (u'комнатная', u'комнатный'),
        (u'комнатную', u'комнатный'),
        (u'комнатных', u'комнатных'),
        (u'комнатные', u'комнатные'),
        (u'комнатное', u'комнатное'),
        (u'комнатной', u'комнатные'),
    ]

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SEO, cls).__new__(cls, *args, **kwargs)

        return cls._instance

    def __init__(self, *args, **kwargs):
        self.province = BulkRegion()
        self.city = BulkRegion()
        self.district = BulkRegion()

        self._current_language = kwargs.pop('current_language', 'ru')
        if self._current_language == 'uk':
            self.scp = SEOCachedPhrase()

    def _get_property_type(self, case):
        try:
            return PROPERTY_TYPE_ASSOC[self._property_type][case-1]

        except:
            return PROPERTY_TYPE_ASSOC['default'][case-1]

    def _prepare_translated_data(self):
        """
        Достаем заготовленные фразы для украинского языка
        """

        if self._current_language == 'uk':
            # Проводим замену фраз на переведенные, у выбранных ключей
            keys_for_replace = [
                'prop', 'prop_room_short', 'prop_m', 'prop_chego', 'prop_chego_m', 'prop_chto', 'prop_room',
                'prop_room_chto', 'prop_room_chto_short', 'prop_room_chego', 'prop_room_chego_short',
                'prop_room_chego_singular', 'commercial_room', 'commercial_room_short'
            ]

            for key in keys_for_replace:
                self._data[key] = self.scp.get_translated_phrase(self._data[key])

    def get_data(self):
        for region_in_path in self._region.get_parents():
            if region_in_path.kind in ['province', 'group', 'group2']:
                self.province = region_in_path

            if region_in_path.kind in ['locality', 'village', 'group', 'group2']:
                self.city = region_in_path

            if region_in_path.kind == 'district':
                self.district = region_in_path

        # TODO: надо бы привести это всё к нормальному вижу, в том числе переделать этот nameD
        self._data = {
            'region': self._region.name,
            'region_gde': self._region.nameD['gde'],
            'region_chego': self._region.nameD['chego'],
            'prop': self._get_property_type(1),
            'prop_m': self._get_property_type(4),
            'prop_chego': self._get_property_type(2),
            'prop_chego_m': self._get_property_type(5),
            'prop_chto': self._get_property_type(3),
            'province': self.province.name,
            'province_gde': self.province.nameD['gde'],
            'province_chego': self.province.nameD['chego'],
            'city': self.city.name,
            'city_gde': self.city.nameD['gde'],
            'city_chem': self.city.nameD['chem'],
            'city_chego': self.city.nameD['chego'],
            'district': self.district.name,
            'district_gde': self.district.nameD['gde'],
            'district_chego': self.district.nameD['chego'],
            'subway': self._subway,
            'main_city': self._main_city,
            'old_city': '',
            'old_city_gde':'',
            'old_city_chem': '',
            'old_city_chego': '',
        }

        if self.city.old_name != '':
            declensions_assoc = ['original', 'chego', 'chemu', 'chto', 'chem', 'gde']
            old_nameD = {declensions_assoc[index]: word for (index, word) in enumerate(self.city.old_name_declension.split(';'))}

            self._data.update({
                'old_city': '(%s)' % (old_nameD['original']),
                'old_city_gde': '(%s)' % (old_nameD['gde']),
                'old_city_chem': '(%s)' % (old_nameD['chem']),
                'old_city_chego': '(%s)' % (old_nameD['chego']),
            })

        self._data.update({
            'prop_room': self._data['prop'],
            'prop_room_short': self._data['prop'],
            'prop_room_chto': self._data['prop_chto'],
            'prop_room_chto_short': self._data['prop_chto'],
            'prop_room_chego': self._data['prop_chego'],
            'prop_room_chego_short': self._data['prop_chego'],
            'prop_room_chego_singular': self._data['prop_chego'],
            'commercial_room': self._data['prop'],
            'commercial_room_short':  self._data['prop'],
        })

        if 0 < self._rooms < 6 and self._property_type not in ['room', 'plot']:
            # Выбираем текстовое описание слов
            room_count = self._room_count[self._rooms - 1]
            room_count_short = self._room_count_short[self._rooms - 1]

            feminine = int(self._property_type not in ('flat', 'commercial',  None))

            self._data.update({
                'prop_room': u' '.join([room_count + self._room_cases[0][feminine], self._get_property_type(1)]),
                'prop_room_short': u' '.join([room_count_short, self._room_cases[0][feminine], self._get_property_type(1)]),
                'prop_room_m': u' '.join([room_count + self._room_cases[3][feminine], self._get_property_type(4)]),
                'prop_room_chto': u' '.join([room_count + self._room_cases[1][feminine], self._get_property_type(3)]),
                'prop_room_chto_short': u' '.join([room_count_short, self._room_cases[1][feminine], self._get_property_type(3)]),
                'prop_room_chego': u' '.join([room_count + self._room_cases[2][feminine], self._get_property_type(5)]),
                'prop_room_chego_short': u' '.join([room_count_short, self._room_cases[2][feminine], self._get_property_type(5)]),
                'prop_room_chego_singular': u' '.join([room_count + self._room_cases[5][feminine], self._get_property_type(2)]),
                'commercial_room': (room_count + self._room_cases[4][feminine]),
                'commercial_room_short': u' '.join([room_count_short, self._room_cases[4][feminine]]),
            })

        if self._property_type == 'garages':
            car_count = self._car_count[self._rooms - 1]
            if self._rooms == 1:
                cars = u' машину'
            elif self._rooms < 5:
                cars = u' машины'
            else:
                cars = u' машин'
            self._data.update({
                'numb_cars': (car_count + cars)
            })

        # todo: убрать это безобразие каким-нибудь немыслемым способом
        for key in self._data.keys():
            key_checks = key in ['prop_room', 'prop_room_chto', 'prop_room_chego', 'prop_room_chego_short']
            if key_checks and u'недвижимости' in self._data[key]:
                self._data[key] = self._data[key].replace(u'комнатных', u'комнатной')

            if key_checks and u'гараж' in self._data[key]:
                self._data[key] = self._data[key].replace(u'комнатны', u'местны')

        # Переводим избранные части фраз
        self._prepare_translated_data()

    def get_seo(self, region, region_kind='default', subpage='default', deal_type='default', property_type='default', rooms=0, subway_stations=0):
        """
        Подготавливаем все нужные блоки
        todo: проверить Карпаты
        """

        # Подготавливаем данные
        self._region = region
        self._region_kind = region_kind if region_kind != 'default' else self._region.kind

        # Исторический фикс регионов (для Карпат + разделения населеного пункта и чего-то поменьше)
        if self._region_kind in ['village', 'group', 'group2']:
            self._region_kind = 'locality' if self._region.subdomain else 'village'

        # более главный город вычисляется по полю main_city
        main_city = ''
        if region.kind in ['locality'] and (not region.subdomain):
            try:
                province = region.get_parents(kind='province')[0]
                main_city = province.get_descendants().filter(main_city=True).order_by('id')[0]
            except IndexError:  # случается только для регионов с поддомена Карпаты, т.к. там потеряна связь с областью
                pass

        self._deal_type = deal_type
        self._subpage = subpage
        self._property_type = property_type
        self._rooms = int(rooms)
        self._subway = subway_stations
        self._main_city = main_city

        self.get_data()

        # Меняем с flat на default, как историческая фишка
        property_type = 'default' if property_type == 'flat' else property_type
        self._property_type = property_type

        # Получаем возможные правила + cache
        self._cache_key_rules = u'_'.join([
            self._cache_key_rules_prefix, self._deal_type, self._subpage, self._region_kind, self._property_type,
            unicode(bool(self._rooms)), unicode(bool(self._subway)), unicode(bool(self._main_city)), self._current_language
        ])
        seo = cache.get(self._cache_key_rules, None)
        if seo is None:
            rules, seo = SEORule.get_suitable_rules(self._region, self._deal_type, self._property_type, self._subpage, self._rooms, self._subway)
            cache.set(self._cache_key_rules, seo, self._cache_time)

        for key in ['title', 'description', 'keywords', 'h1', 'crosslink_header']:
            if key in seo:
                if seo[key] is None:
                    seo[key] = u''

                seo[key] = seo[key] % self._data

                if self._current_language == 'uk':
                    seo[key] = check_uk_preposition(seo[key])

        # Добавление названия сайта в title
        if 'title' in seo:
            seo['title'] = seo['title'][:1].capitalize() + seo['title'][1:]
            if u"Mesto.ua" in seo['title']:
                pass
            else:
                seo['title'] += u' - Mesto.ua'

        # todo: перенести в шаблон first letter uppercase without other letters downcase
        if 'h1' in seo:
            seo['h1'] = seo['h1'][:1].capitalize() + seo['h1'][1:]

        # Правки СЕО от 03.02.2017
        if 'keywords' in seo:
            seo['keywords'] = u''

        return seo
