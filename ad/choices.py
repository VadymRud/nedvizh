# coding=utf-8

from django.utils.translation import ugettext_lazy as _

DEAL_TYPE_CHOICES = (
    ('rent', _(u'аренда')),
    ('rent_daily', _(u'посуточная аренда')),
    ('sale', _(u'продажа')),
    # ('newhomes', _(u'новостройки')),
)
PROPERTY_TYPE_CHOICES = (
    ('flat', _(u'квартира')),
    ('room', _(u'комната')),
    ('house', _(u'дом')),
    ('plot', _(u'участок')),
    ('commercial', _(u'коммерческая недвижимость')),
    ('garages', _(u'гаражи')),
)
CURRENCY_CHOICES = (
    ('UAH', u'грн.'),
    ('EUR', u'€'),
    ('USD', u'$'),
    ('RUR', u'руб.'),
)

FLOOR_CHOICES = [(floor, floor) for floor in range(1,50)]
STATUS_CHOICES = (
    (1, _(u'опубликовано')),
    (210, u'неактивно'),
    (211, u'удалено'),
)

DEACTIVATION_REASON_CHOICES = (
    (1, _(u'объект продан на Mesto.ua')),
    (2, _(u'объект продан на другом сайте')),
    (3, _(u'объект продал коллега')),
    (4, _(u'владелец передумал')),
    (5, _(u'другая причина')),
)

MODERATION_STATUS_CHOICES = (
    # (4, u'требует постмодерации'),
    (10, _(u'нет телефона')),
    (11, _(u'неверный адрес')),
    (12, _(u'неверная цена')),
    (13, _(u'контактные данные или ссылки в описании')),
    (14, _(u'контактные данные или ссылки в фотографиях')),
    (15, _(u'фото не имеет отношение к объекту недвижимости')),
    (16, _(u'некорректная площадь')),
    (17, _(u'отсутствует описание объекта')),
    (19, _(u'реклама')),
    (20, _(u'заблокировано')),
    (22, _(u'дубликат объявления')),
    (23, _(u'неверное название ЖК')),
    (24, _(u'объект вторичного рынка')),
    (21, u'робот'),
    (200, _(u'исключено (бан)')),
    (220, _(u'фиды без картинок')),
)

BUILDING_TYPE_CHOICES = (
    (6, _(u'дореволюционное')),
    (1, _(u'сталинка')),
    (2, _(u'хрущевка')),
    (4, _(u'чешка')),
    (7, _(u'брежневка')),
    (8, _(u'екатерининка')),
    (9, _(u'немка')),
    (10, _(u'гостинка')),
    (11, _(u'малосемейка')),
    (14, _(u'панельный')),
    (5, _(u'новострой')),
    (12, _(u'элитный новострой')),
    (13, _(u'высотка')),
    (200, _(u'другое:')),
)

WALLS_CHOICES = (
    (1, _(u'кирпичный')),
    (2, _(u'панельный')),
    (3, _(u'монолитный')),
    (4, _(u'блочный')),
    (5, _(u'деревянный')),
    (6, _(u'ракушняк')),
    (7, _(u'саман')),
)
WINDOWS_CHOICES = (
    (1, _(u'пластиковые')),
    (2, _(u'деревянные')),
)
HEATING_CHOICES = (
    (1, _(u'центральное')),
    (2, _(u'индивидуальное')),
)
LAYOUT_CHOICES = (
    (1, _(u'раздельные комнаты')),
    (2, _(u'проходные комнаты')),
    (3, _(u'студия')),
    (4, _(u'свободная планировка')),
)

CONTENT_PROVIDER_CHOICES = (
    (1, 'Fornova'),
    (2, 'ListGlobally'),
    (3, 'WorldPosting'),
)

# ISO 3166
COUNTRY_CODE_CHOICES = (
    ('AU', "Австралия"),
    ('AT', "Австрия"),
    ('AZ', "Азербайджан"),
    ('AL', "Албания"),
    ('DZ', "Алжир"),
    ('AI', "Ангилья о. (GB)"),
    ('AO', "Ангола"),
    ('AD', "Андорра"),
    ('AQ', "Антарктика"),
    ('AG', "Антигуа и Барбуда"),
    ('AN', "Антильские о-ва (NL)"),
    ('AR', "Аргентина"),
    ('AM', "Армения"),
    ('AW', "Аруба"),
    ('AF', "Афганистан"),
    ('BS', "Багамы"),
    ('BD', "Бангладеш"),
    ('BB', "Барбадос"),
    ('BH', "Бахрейн"),
    ('BY', "Беларусь"),
    ('BZ', "Белиз"),
    ('BE', "Бельгия"),
    ('BJ', "Бенин"),
    ('BM', "Бермуды"),
    ('BV', "Бове о. (NO)"),
    ('BG', "Болгария"),
    ('BO', "Боливия"),
    ('BA', "Босния и Герцеговина"),
    ('BW', "Ботсвана"),
    ('BR', "Бразилия"),
    ('BN', "Бруней Дарассалам"),
    ('BF', "Буркина-Фасо"),
    ('BI', "Бурунди"),
    ('BT', "Бутан"),
    ('VU', "Вануату"),
    ('VA', "Ватикан"),
    ('GB', "Великобритания"),
    ('HU', "Венгрия"),
    ('VE', "Венесуэла"),
    ('VG', "Виргинские о-ва (GB)"),
    ('VI', "Виргинские о-ва (US)"),
    ('AS', "Восточное Самоа (US)"),
    ('TP', "Восточный Тимор"),
    ('VN', "Вьетнам"),
    ('GA', "Габон"),
    ('HT', "Гаити"),
    ('GY', "Гайана"),
    ('GM', "Гамбия"),
    ('GH', "Гана"),
    ('GP', "Гваделупа"),
    ('GT', "Гватемала"),
    ('GN', "Гвинея"),
    ('GW', "Гвинея-Бисау"),
    ('DE', "Германия"),
    ('GI', "Гибралтар"),
    ('HN', "Гондурас"),
    ('HK', "Гонконг (CN)"),
    ('GD', "Гренада"),
    ('GL', "Гренландия (DK)"),
    ('GR', "Греция"),
    ('GE', "Грузия"),
    ('GU', "Гуам"),
    ('DK', "Дания"),
    ('CD', "Демократическая Республика Конго"),
    ('DJ', "Джибути"),
    ('DM', "Доминика"),
    ('DO', "Доминиканская Республика"),
    ('EG', "Египет"),
    ('ZM', "Замбия"),
    ('EH', "Западная Сахара"),
    ('ZW', "Зимбабве"),
    ('IL', "Израиль"),
    ('IN', "Индия"),
    ('ID', "Индонезия"),
    ('JO', "Иордания"),
    ('IQ', "Ирак"),
    ('IR', "Иран"),
    ('IE', "Ирландия"),
    ('IS', "Исландия"),
    ('ES', "Испания"),
    ('IT', "Италия"),
    ('YE', "Йемен"),
    ('CV', "Кабо-Верде"),
    ('KZ', "Казахстан"),
    ('KY', "Каймановы о-ва (GB)"),
    ('KH', "Камбоджа"),
    ('CM', "Камерун"),
    ('CA', "Канада"),
    ('QA', "Катар"),
    ('KE', "Кения"),
    ('CY', "Кипр"),
    ('KG', "Киргизстан"),
    ('KI', "Кирибати"),
    ('CN', "Китай"),
    ('CC', "Кокосовые (Киилинг) о-ва (AU)"),
    ('CO', "Колумбия"),
    ('KM', "Коморские о-ва"),
    ('CG', "Конго"),
    ('CR', "Коста-Рика"),
    ('CI', "Кот-д'Ивуар"),
    ('CU', "Куба"),
    ('KW', "Кувейт"),
    ('CK', "Кука о-ва (NZ)"),
    ('LA', "Лаос"),
    ('LV', "Латвия"),
    ('LS', "Лесото"),
    ('LR', "Либерия"),
    ('LB', "Ливан"),
    ('LY', "Ливия"),
    ('LT', "Литва"),
    ('LI', "Лихтенштейн"),
    ('LU', "Люксембург"),
    ('MU', "Маврикий"),
    ('MR', "Мавритания"),
    ('MG', "Мадагаскар"),
    ('YT', "Майотта о. (KM)"),
    ('MO', "Макао (PT)"),
    ('MK', "Македония"),
    ('MW', "Малави"),
    ('MY', "Малайзия"),
    ('ML', "Мали"),
    ('MV', "Мальдивы"),
    ('MT', "Мальта"),
    ('MA', "Марокко"),
    ('MQ', "Мартиника"),
    ('MH', "Маршалловы о-ва"),
    ('MX', "Мексика"),
    ('FM', "Микронезия (US)"),
    ('MZ', "Мозамбик"),
    ('MD', "Молдова"),
    ('MC', "Монако"),
    ('MN', "Монголия"),
    ('MS', "Монсеррат о. (GB)"),
    ('MM', "Мьянма"),
    ('NA', "Намибия"),
    ('NR', "Науру"),
    ('NP', "Непал"),
    ('NE', "Нигер"),
    ('NG', "Нигерия"),
    ('NL', "Нидерланды"),
    ('NI', "Никарагуа"),
    ('NU', "Ниуэ о. (NZ)"),
    ('NZ', "Новая Зеландия"),
    ('NC', "Новая Каледония о. (FR)"),
    ('NO', "Норвегия"),
    ('NF', "Норфолк о. (AU)"),
    ('AE', "Объединенные Арабские Эмираты"),
    ('OM', "Оман"),
    ('PK', "Пакистан"),
    ('PW', "Палау (US)"),
    ('PS', "Палестинская автономия"),
    ('PA', "Панама"),
    ('PG', "Папуа-Новая Гвинея"),
    ('PY', "Парагвай"),
    ('PE', "Перу"),
    ('PN', "Питкэрн о-ва (GB)"),
    ('PL', "Польша"),
    ('PT', "Португалия"),
    ('PR', "Пуэрто-Рико (US)"),
    ('RE', "Реюньон о. (FR)"),
    ('CX', "Рождества о. (AU)"),
    ('RU', "Россия"),
    ('RW', "Руанда"),
    ('RO', "Румыния"),
    ('SV', "Сальвадор"),
    ('WS', "Самоа"),
    ('SM', "Сан Марино"),
    ('ST', "Сан-Томе и Принсипи"),
    ('SX', "Синт-Мартен"),
    ('SA', "Саудовская Аравия"),
    ('SZ', "Свазиленд"),
    ('SJ', "Свалбард и Ян Мейен о-ва (NO)"),
    ('SH', "Святой Елены о. (GB)"),
    ('KP', "Северная Корея (КНДР)"),
    ('MP', "Северные Марианские о-ва (US)"),
    ('SC', "Сейшелы"),
    ('VC', "Сен-Винсент и Гренадины"),
    ('PM', "Сен-Пьер и Микелон (FR)"),
    ('SN', "Сенегал"),
    ('KN', "Сент-Кристофер и Невис"),
    ('LC', "Сент-Люсия"),
    ('RS', "Сербия"),
    ('SG', "Сингапур"),
    ('SY', "Сирия"),
    ('SK', "Словакия"),
    ('SI', "Словения"),
    ('US', "Соединенные Штаты Америки"),
    ('SB', "Соломоновы о-ва"),
    ('SO', "Сомали"),
    ('SD', "Судан"),
    ('SR', "Суринам"),
    ('SL', "Сьерра-Леоне"),
    ('TJ', "Таджикистан"),
    ('TH', "Таиланд"),
    ('TW', "Тайвань"),
    ('TZ', "Танзания"),
    ('TC', "Теркс и Кайкос о-ва (GB)"),
    ('TG', "Того"),
    ('TK', "Токелау о-ва (NZ)"),
    ('TO', "Тонга"),
    ('TT', "Тринидад и Тобаго"),
    ('TV', "Тувалу"),
    ('TN', "Тунис"),
    ('TM', "Туркменистан"),
    ('TR', "Турция"),
    ('UG', "Уганда"),
    ('UZ', "Узбекистан"),
    ('UA', "Украина"),
    ('WF', "Уоллис и Футуна о-ва (FR)"),
    ('UY', "Уругвай"),
    ('FO', "Фарерские о-ва (DK)"),
    ('FJ', "Фиджи"),
    ('PH', "Филиппины"),
    ('FI', "Финляндия"),
    ('FK', "Фолклендские (Мальвинские) о-ва (GB/AR)"),
    ('FR', "Франция"),
    ('GF', "Французская Гвиана (FR)"),
    ('PF', "Французская Полинезия"),
    ('HM', "Херд и Макдональд о-ва (AU)"),
    ('HR', "Хорватия"),
    ('CF', "Центрально-африканская Республика"),
    ('TD', "Чад"),
    ('ME', "Черногория"),
    ('CZ', "Чехия"),
    ('CL', "Чили"),
    ('CH', "Швейцария"),
    ('SE', "Швеция"),
    ('LK', "Шри-Ланка"),
    ('EC', "Эквадор"),
    ('GQ', "Экваториальная Гвинея"),
    ('ER', "Эритрия"),
    ('EE', "Эстония"),
    ('ET', "Эфиопия"),
    ('YU', "Югославия"),
    ('ZA', "Южная Африка"),
    ('GS', "Южная Георгия и Южные Сандвичевы о-ва"),
    ('KR', "Южная Корея (Республика Корея)"),
    ('JM', "Ямайка"),
    ('JP', "Япония"),
)

GEO_SOURCE_CHOICES = (
    ('addr', u'поля адреса'),
    ('coords', u'координаты'),
    ('addr_coords', u'поля адреса и координаты'),
)

INTERNATIONAL_CATALOG_CHOICES = (
    (1, u'только mesto.ua'),
    (2, u'mesto.ua и международные каталоги'),
)

ROOMS_CHOICES = (
    (1, '1'),
    (2, '2'),
    (3, '3'),
    (4, '4'),
    (5, '5+'),
)