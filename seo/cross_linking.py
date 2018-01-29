# coding=utf-8
import random
import re
from django.core.cache import cache
from seo.models import SEOCachedPhrase

DEAL_TYPE_SYNONYMS = {
    'sale': ((u'Продажа', 1), (u'Покупка', 1), (u'Продать', 2), (u'Купить', 2), (u'На вторичном рынке', 0)),
    'rent': ((u'Долгосрочная аренда', 1), (u'Снять', 2), (u'Сдать', 2), (u'Арендовать', 2), (u'Снять долгосрочно', 2),
             (u'Сдать долгосрочно', 2), (u'Арендовать долгосрочно', 2), (u'Сниму', 2), (u'Сдам', 2)),
    'rent_daily': ((u'Посуточная аренда', 1), (u'Аренда посуточно', 1), (u'Снять на сутки', 0),
                   (u'Снять на час', 0), (u'Снять посуточно', 2), (u'Сдать посуточно', 2),
                   (u'Арендовать посуточно', 2), (u'Сниму посуточно', 2), (u'Сдам посуточно', 2)),
    'newhomes': ((u'в новостройке', 0), (u'новострой', 0), (u'от застройщика', 0),),
}

# Недорого    Продажа     Продать
# квартира    квартиры    квартиру
# офис        офиса       офис
# здание      здания      здание
PROPERTY_TYPE = {
    'all-real-estate': (u'недвижимость'),
    'flat': (u'квартиры'),
    'house': (u'дома'),
    'room': (u'комнаты'),
    'garages': (u'гаражи'),
    'plot': (u'земельные участки'),
    'commercial': (u'коммерческая недвижимость'),
}

PROPERTY_TYPE_SYNONYMS = {
    'all-real-estate': (u'недвижимость/недвижимости',),
    'flat': (u'квартира/квартир/квартиру', u'жилье/жилья'),
    'house': (u'дом/дома', u'частный дом/частного дома'),
    'room': (u'комната/комнат/комнату',),
    'garages': (u'гараж/гаража', u'подземный паркинг/подземного паркинга'),
    'plot': (u'участок/участка', u'земля/земли/землю', u'земельный участок/земельного участка',
             u'участок под застройку/участка под застройку',
             u'земля под коммерцию/земли под коммерцию/землю под коммерцию',
             u'дачный участок/дачного участок'),
    'commercial': (u'коммерческая недвижимость/коммерческой недвижимости/коммерческую недвижимость',
                   u'недвижимость для коммерции/недвижимости для коммерции', u'помещение/помещения',
                   u'складские помещения/складских помещений/складское помещение',
                   u'коммерческие помещения/коммерческого помещения',
                   u'торговая площадь/торговой площади/торговую площадь',
                   u'офисы/офиса/офис', u'офисное здание/офисного здания'),
}

ADDITIONAL_WORDS = [u'недорого', u'недорого', u'без посредников', ]


def check_uk_preposition(string):
    """
    Меняем русские предлоги на украинские по упрощенным правилам укр. языка
    """
    p = re.compile(u" в (?![іїиеєаяоОую])", re.IGNORECASE | re.UNICODE)
    return p.sub(u" у ", string)


def get_crosslinks(url, region, deal_type, property_type='all-real-estate', rooms=0, subway_station=0, detail=False,
                   current_language='ru', scp=None):

    # использовать кеш только на страницах поиска без параметров
    using_cache = not detail and '?' not in url
    if using_cache:
        blocks = cache.get('crosslinks_%s' % url)
        if blocks:
            return blocks

    random_by_url = random.Random()
    random_by_url.seed(url)

    # Подготавливаем класс с переводом фраз
    if current_language == 'uk' and scp is None:
        scp = SEOCachedPhrase()

    blocks = get_params_search(region, deal_type, property_type, rooms, detail, subway_station, current_language)
    for block in blocks:
        for pos, block_param in enumerate(block):
            # Заголовок блока
            if not pos:
                link_data = region.nameD
                link = ['', block_param]
            else:
                link_data = block_param[0].nameD
                if 'siblings' in block_param:
                    block_param = block_param[:-1]
                    link = generate_link_search(random_by_url, *block_param, siblings=True)
                else:
                    str_param = []
                    for param in block_param:
                        if isinstance(param, basestring):
                            str_param.append(param)
                    station = filter(lambda x: 'metro-' in x, str_param)
                    if len(station) > 0:
                        block_param = block_param[:-1]
                        link = generate_link_search(random_by_url, *block_param, metro=station[0])
                    else:
                        link = generate_link_search(random_by_url, *block_param)

            if current_language == 'uk':
                link[1] = scp.get_translated_phrase(link[1], set_cache=False)

            link[1] = link[1] % link_data

            if current_language == 'uk':
                link[1] = check_uk_preposition(link[1])

            block[pos] = link

    # Если нагенерировали перевод, то обновляем кеш одним запросом
    if scp is not None:
        scp.set_cache()

    if using_cache:
        cache.set('crosslinks_%s' % url, blocks, 60 * 60 * 3)

    return blocks


# возвращает что-то типа "трехкомнатный " для "купить дом" или "двухкомнатная" для "недорого квартира" и т.п.
def get_property_rooms(property_type_str, rooms, declension):
    room_suffix = (
        ([u'квартир', u'недвижимост', u'комнат', u'площад'], [u'ая', u'ой', u'ую']),
        ([u'дом', u'паркинг', u'гараж', u'участ', u'офис', ], [u'ый', u'ого', u'ый']),
        ([u'жиль', u'помещени', u'на стоянке', ], [u'ое', u'ого', u'ое']),
    )
    room_word = u'комнатн'

    for (gender_parts, suffix) in room_suffix:
        for gender_part in gender_parts:
            if gender_part in property_type_str:
                return ['', u'одно', u'двух', u'трех', u'четырех', u'пяти'][rooms] + room_word + suffix[
                    declension] + u' '

    return ''

# возвращает что-то типа "трехкомнатный " для "купить дом" или "двухкомнатная" для "недорого квартира" и т.п.
def get_property_rooms_search(property_type_str, rooms, declension):
    room_suffix = (
        ([u'квартир'], [u'ые']),
        ([u'дом'], [u'ые']),
    )
    room_word = u'комнатн'

    for (gender_parts, suffix) in room_suffix:
        for gender_part in gender_parts:
            if gender_part in property_type_str:
                return ['', u'одно', u'двух', u'трех', u'четырех', u'пяти'][rooms] + room_word + suffix[
                    0] + u' '

    return ''


def get_base_anchor(random_by_url, deal_type, property_type, rooms=None, use_random=True):
    def get_first(seq):
        return seq[0] if seq else None

    # функция выбирающая синоним из нескольких вариантов
    get_func = random_by_url.choice if use_random else get_first

    deal_type_variant = get_func(DEAL_TYPE_SYNONYMS[deal_type])
    deal_type_str = deal_type_variant[0]
    declension = deal_type_variant[1]

    property_type_variant = get_func(PROPERTY_TYPE_SYNONYMS[property_type or 'flat']).split(u'/')
    if declension == 2 and len(property_type_variant) == 2:
        property_type_str = property_type_variant[0]
    else:
        property_type_str = property_type_variant[declension]

    if 0 < rooms < 6 and property_type not in ['room', 'plot']:
        property_type_str = get_property_rooms(property_type_str, rooms, declension) + property_type_str

    if deal_type == 'newhomes':
        return [property_type_str.capitalize(), deal_type_str, u'в %(gde)s']
    else:
        return [deal_type_str.capitalize(), property_type_str, u'в %(gde)s']


def get_base_anchor_search(random_by_url, deal_type, property_type, region, rooms=None, use_random=True, siblings=None):
    def get_first(seq):
        return seq[0] if seq else None

    # функция выбирающая синоним из нескольких вариантов
    get_func = random_by_url.choice if use_random else get_first

    deal_type_variant = get_func(DEAL_TYPE_SYNONYMS[deal_type])
    declension = deal_type_variant[1]

    property_type_variant = PROPERTY_TYPE[property_type or 'flat']
    property_type_str = property_type_variant

    if 0 < rooms < 6 and property_type not in ['room', 'plot']:
        property_type_str = get_property_rooms_search(property_type_str, rooms, declension) + property_type_str

    if siblings is not None:
        property_type_str = region.name
        if u' район' in property_type_str:
            property_type_str = property_type_str.replace(u" район", "")

    return [property_type_str.capitalize()]


def generate_link(random_by_url, region, deal_type, property_type=None, rooms=None, force_anchor=None, use_random=True):
    anchor = get_base_anchor(random_by_url, deal_type, property_type, rooms=rooms, use_random=use_random)
    link = region.get_deal_url(deal_type, property_type)

    # if region.kind in ['street', 'district']:
    #     anchor[2] = anchor[2].replace(u'в ', u'на ')

    if rooms:
        link += "?rooms=%d" % rooms

    # добавляем еще случайных слов для блока с перелинковкой (в нем use_random=True)
    if use_random and random_by_url and random_by_url.randint(0, 3) == 0:
        anchor.insert(2, random_by_url.choice(ADDITIONAL_WORDS))

    if force_anchor:
        anchor = [force_anchor, anchor[-1]]

    return [link, ' '.join(anchor)]


def generate_link_search(random_by_url, region, deal_type, property_type=None, rooms=None, force_anchor=None, use_random=True, siblings=None, metro=0):

    if metro:
        station = metro[6:]

    anchor = get_base_anchor_search(random_by_url, deal_type, property_type, region, rooms=rooms, use_random=use_random, siblings=siblings)
    if metro:
        link = region.get_deal_url(deal_type, property_type, station)
    else:
        link = region.get_deal_url(deal_type, property_type)

    if rooms:
        link += "?rooms=%d" % rooms

    if force_anchor:
        anchor = [force_anchor, anchor[-1]]

    return [link, ' '.join(anchor)]


def get_params_search(region, deal_type, property_type, rooms, detail, subway_station, current_language):
    kind = region.kind
    blocks = [[], [], [], []]  # максимум 4 блока
    children_regions = region.get_descendants().filter(region_counter__deal_type=deal_type, region_counter__count__gt=0)
    main_city = None

    property_types_variants = ['flat', 'room', 'all-real-estate', 'house', 'garages', 'plot', 'commercial']
    property_types_without_rooms = ['room', 'all-real-estate', 'garages', 'plot', 'commercial']

    if deal_type == 'rent_daily':
        new_list = []

        for prop_type in property_types_variants:
            if prop_type in ['flat', 'room', 'house']:
                new_list.append(prop_type)

        property_types_variants = new_list

    property_types_variants_filtered = [val for val in property_types_variants if val != property_type]

    all_room_variants = [1, 2, 3, 4, 5]
    if rooms and int(rooms) in all_room_variants:
        all_room_variants.remove(int(rooms))

    # более главный город вычисляется по полю main_city
    if kind in ['district', 'locality', 'village', 'street'] and (not region.subdomain or region.slug == 'irpen'):
        try:
            province = region.get_parents(kind='province')[0]
            main_city = province.get_descendants().filter(main_city=True).order_by('id')[0]
        except IndexError:  # случается только для регионов с поддомена Карпаты, т.к. там потеряна связь с областью
            pass

    # Начинаем формировать пресеты
    # Тип недвижимости
    blocks_names_property_types = {
        'all-real-estate': u'недвижимости', 'flat': u'квартир', 'house': u'домов', 'room': u'комнат',
        'garages': u'гаражей', 'plot': u'участков', 'commercial': u'коммерческой недвижимости',
    }

    # Префикс
    blocks_names_deal_types = {
        'sale': u'Продажа %s' % blocks_names_property_types[property_type],
        'rent': u'Аренда %s' % blocks_names_property_types[property_type],
        'rent_daily': u'Посуточная аренда %s' % blocks_names_property_types[property_type],
        'newhomes': u'Квартиры от застройщиков '
    }
    block_prefix = blocks_names_deal_types[deal_type]

    blocks_deal_types = {
        'sale': u'о продаже',
        'rent': u'долгосрочной аренды',
        'rent_daily': u'посуточной аренды',
        'newhomes': u'о продаже'
    }
    block_ending = blocks_deal_types[deal_type]

    # Приставка по комнатам
    blocks_names_rooms_name = u'комнат'

    # Подготавливаем заголовки блоков для перелинковки
    blocks_names_preset_country = [
        [u'Популярные объявления %(chego)s'],
        [block_prefix + u' по областям %(chego)s']
    ]
    blocks_names_preset_province = [
        [u'%s по количеству %s' % (block_prefix, blocks_names_rooms_name)],
        [u'Популярные объявления %s' % (block_ending)],
        [block_prefix + u' по городам %(chego)s']
    ]
    blocks_names_preset_locality = [
        [u'%s по количеству %s' % (block_prefix, blocks_names_rooms_name)],
        [u'Популярные объявления %s' % (block_ending)],
        [block_prefix + u' в районах %(chego)s']
    ]
    blocks_names_preset_district = [
        [u'%s по количеству %s' % (block_prefix, blocks_names_rooms_name)],
        [u'Популярные объявления в %(gde)s'],
        [block_prefix + u' в районах %(chego)s']
    ]

    # страны
    if kind == 'country' and deal_type == 'sale':
        blocks = blocks_names_preset_country

        blocks[0] += [(region, deal_type, pt_key) for pt_key in property_types_variants_filtered]
        blocks[1] += [(province, deal_type, property_type, 'siblings') for province in
                      region.get_descendants().filter(kind='province')]

    if kind == 'country' and deal_type == 'rent':
        blocks = blocks_names_preset_country

        blocks[0] += [(region, deal_type, pt_key) for pt_key in property_types_variants_filtered]
        blocks[1] += [(province, deal_type, property_type, 'siblings') for province in
                      region.get_descendants().filter(kind='province')]

    if kind == 'country' and deal_type == 'rent_daily':
        blocks = blocks_names_preset_country

        blocks[0] += [(region, deal_type, pt_key) for pt_key in property_types_variants_filtered]
        blocks[1] += [(province, deal_type, property_type, 'siblings') for province in
                      region.get_descendants().filter(kind='province')]

    if kind == 'country' and deal_type == 'newhomes':
        blocks = blocks_names_preset_country

    # города, деревни
    if kind in ['locality', 'village']:
        blocks = blocks_names_preset_locality

        if subway_station:
            station = 'metro-' + subway_station.slug

        if property_type not in property_types_without_rooms:
            if subway_station:
                blocks[0] += [(region, deal_type, property_type, rooms, station) for rooms in all_room_variants]
            else:
                blocks[0] += [(region, deal_type, property_type, rooms) for rooms in all_room_variants]

        if subway_station and deal_type != 'newhomes':
            blocks[1][0] = u'Популярные объявления %s на метро %s' % (block_ending, subway_station.name)
            blocks[1] += [(region, deal_type, pt_key, station) for pt_key in property_types_variants_filtered]
        elif deal_type == 'newhomes':
            blocks[1] += [(region, 'sale', pt_key) for pt_key in property_types_variants]
        else:
            blocks[1] += [(region, deal_type, pt_key) for pt_key in property_types_variants_filtered]

        all_districts = children_regions.filter(kind='district', parent_id=region.id)
        for district in all_districts:
            if u' район' in district.name:
                blocks[2] += [(district, deal_type, property_type, 'siblings')]

        # если есть более крупный главный город в области
        if main_city:
            blocks.insert(2,
                          [u'Популярные объявления %s недвижимости в %s' % (block_ending, main_city.nameD['gde'])] +
                          [(main_city, deal_type, pt_key) for pt_key in property_types_variants])
            blocks.pop()

    if kind == 'province':
        blocks = blocks_names_preset_province

        main_city = region.get_descendants().filter(main_city=True).order_by('id').first()
        if property_type not in property_types_without_rooms:
            blocks[0] += [(region, deal_type, property_type, rooms) for rooms in all_room_variants]

        blocks[1] += [(region, deal_type, pt_key) for pt_key in property_types_variants_filtered]
        if main_city:
            blocks[2][0] = u'Популярные объявления %s недвижимости в %s' % (block_ending, main_city.nameD['gde'])
            blocks[2] += [(main_city, deal_type, pt_key) for pt_key in property_types_variants]

    # группа регионов
    if kind == 'group2':
        blocks = blocks_names_preset_province
        if property_type not in property_types_without_rooms:
            blocks[0] += [(region, deal_type, property_type, rooms) for rooms in all_room_variants]

        blocks[1] += [(region, deal_type, pt_key) for pt_key in property_types_variants_filtered]
        blocks[2] += [(child, deal_type, property_type) for child in region.get_children()]

    # район города
    if kind in ['district', 'area', 'street']:
        blocks = blocks_names_preset_district

        other_districts = region.get_siblings().filter(
            region_counter__deal_type=deal_type, region_counter__count__gt=0, kind='district'
       ).exclude(name=region.name)

        if property_type not in property_types_without_rooms and not detail:
            blocks[0] += [(region, deal_type, property_type, rooms) for rooms in all_room_variants]

        if deal_type == 'newhomes':
            if kind == 'district':
                if main_city:
                    blocks[1][0] = u'Новостройки в районах %(chego)s' % main_city.nameD
                for district in other_districts:
                    if u' район' in district.name:
                        blocks[1] += [(district, deal_type, property_type, 'siblings')]

            if kind == 'street':
                main_district = region.parent
                blocks[1][0] = u'Новостройки в %(gde)s' % main_district.nameD
                if current_language == 'ru':
                    blocks[1] += [(street, deal_type, property_type, 'siblings') for street in region.get_siblings().filter(kind='street')]
                else:
                    blocks[1] += [(street, deal_type, property_type, 'siblings') for street in region.get_siblings().filter(kind='street')][:12]

            if main_city:
                blocks.insert(1, [u'Популярные объявления %s' % (block_ending)] +
                              [(main_city, 'sale', pt_key) for pt_key in property_types_variants])

        else:
            if kind == 'district':
                blocks[1] += [(region, deal_type, pt_key) for pt_key in property_types_variants_filtered]
                if main_city:
                    blocks[2][0] = block_prefix + u' в районах %(chego)s' % main_city.nameD
                for district in other_districts:
                    if u' район' in district.name:
                         blocks[2] += [(district, deal_type, property_type, 'siblings')]
            if kind == 'street':
                main_district = region.parent
                blocks[1][0] = blocks[1][0].replace(u' в ', u' на ')
                if detail and main_city:
                    blocks[1] += [(region, deal_type, pt_key) for pt_key in property_types_variants]
                    blocks[0] += [(main_city, deal_type, property_type, rooms) for rooms in all_room_variants]
                    blocks[2][0] = block_prefix + u' в районах %(chego)s' % main_city.nameD
                    all_districts = main_city.get_children()
                    for district in all_districts:
                        if u' район' in district.name:
                            blocks[2] += [(district, deal_type, property_type, 'siblings')]
                else:
                    blocks[1] += [(region, deal_type, pt_key) for pt_key in property_types_variants_filtered]
                    blocks[2][0] = block_prefix + u' в %(gde)s' % main_district.nameD
                    if current_language == 'ru':
                        blocks[2] += [(street, deal_type, property_type, 'siblings') for street in region.get_siblings().filter(kind='street')]
                    else:
                        blocks[2] += [(street, deal_type, property_type, 'siblings') for street in region.get_siblings().filter(kind='street')][:12]

            # если есть более крупный главный город в области
            if main_city:
                blocks.insert(1, [u'Популярные объявления %s' % (block_ending)] +
                              [(main_city, deal_type, pt_key) for pt_key in property_types_variants])

    if kind in ['locality'] and deal_type == 'newhomes':
        blocks[2][0] = u'Новостройки в районах %(chego)s' % region.nameD

    # На страницах с типом «Новостройки» и с типами недвижимости «вся недвижимость» первый блок линковки будет
    # иметь название «Недвижимость в новостройках» в котором будут отображаться все типы недвижимости кроме данного.
    if blocks[0] and deal_type == 'newhomes' and property_type == 'all-real-estate':
        blocks[0] = [u'Недвижимость в новостройках']
        blocks[0] += [(region, deal_type, pt_key) for pt_key in ['flat', 'house', 'commercial', 'garages']]

    if property_type in property_types_without_rooms and kind in ['street', 'district',  'area', 'province', 'locality', 'village', 'group2']:
        blocks.pop(0)

    return blocks
