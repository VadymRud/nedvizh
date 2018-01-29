/*
    Используется функционал libphonenumber
    https://github.com/googlei18n/libphonenumber
 */

function cleanPhone(phone) {
        phone = phone.replace(/[^\d\+]/g,'');
        if (phone.substr(0, 1) == "+") {
                phone = "+" + phone.replace(/[^\d]/g,'');
        } else {
                phone = phone.replace(/[^\d]/g,'');
        }
        return phone;
}

function formatInternational(country, phone) {
    try {
        phone = cleanPhone(phone);
        var formatter = new i18n.phonenumbers.AsYouTypeFormatter(country);
        var output = new goog.string.StringBuffer();
        for (var i = 0; i < phone.length; ++i) {
            var inputChar = phone.charAt(i);
            output = (formatter.inputDigit(inputChar));
        }
        return output.toString();
    } catch (e) {
        return phone;
    }
}

// сгенерировано из ad.choices.COUNTRY_CODE_CHOICES
var COUNTRY_NAMES = {'AU': "Австралия", 'AT': "Австрия", 'AZ': "Азербайджан", 'AL': "Албания", 'DZ': "Алжир", 'AI': "Ангилья о. (GB)", 'AO': "Ангола", 'AD': "Андорра", 'AQ': "Антарктика", 'AG': "Антигуа и Барбуда", 'AN': "Антильские о-ва (NL)", 'AR': "Аргентина", 'AM': "Армения", 'AW': "Аруба", 'AF': "Афганистан", 'BS': "Багамы", 'BD': "Бангладеш", 'BB': "Барбадос", 'BH': "Бахрейн", 'BY': "Беларусь", 'BZ': "Белиз", 'BE': "Бельгия", 'BJ': "Бенин", 'BM': "Бермуды", 'BV': "Бове о. (NO)", 'BG': "Болгария", 'BO': "Боливия", 'BA': "Босния и Герцеговина", 'BW': "Ботсвана", 'BR': "Бразилия", 'BN': "Бруней Дарассалам", 'BF': "Буркина-Фасо", 'BI': "Бурунди", 'BT': "Бутан", 'VU': "Вануату", 'VA': "Ватикан", 'GB': "Великобритания", 'HU': "Венгрия", 'VE': "Венесуэла", 'VG': "Виргинские о-ва (GB)", 'VI': "Виргинские о-ва (US)", 'AS': "Восточное Самоа (US)", 'TP': "Восточный Тимор", 'VN': "Вьетнам", 'GA': "Габон", 'HT': "Гаити", 'GY': "Гайана", 'GM': "Гамбия", 'GH': "Гана", 'GP': "Гваделупа", 'GT': "Гватемала", 'GN': "Гвинея", 'GW': "Гвинея-Бисау", 'DE': "Германия", 'GI': "Гибралтар", 'HN': "Гондурас", 'HK': "Гонконг (CN)", 'GD': "Гренада", 'GL': "Гренландия (DK)", 'GR': "Греция", 'GE': "Грузия", 'GU': "Гуам", 'DK': "Дания", 'CD': "Демократическая Республика Конго", 'DJ': "Джибути", 'DM': "Доминика", 'DO': "Доминиканская Республика", 'EG': "Египет", 'ZM': "Замбия", 'EH': "Западная Сахара", 'ZW': "Зимбабве", 'IL': "Израиль", 'IN': "Индия", 'ID': "Индонезия", 'JO': "Иордания", 'IQ': "Ирак", 'IR': "Иран", 'IE': "Ирландия", 'IS': "Исландия", 'ES': "Испания", 'IT': "Италия", 'YE': "Йемен", 'CV': "Кабо-Верде", 'KZ': "Казахстан", 'KY': "Каймановы о-ва (GB)", 'KH': "Камбоджа", 'CM': "Камерун", 'CA': "Канада", 'QA': "Катар", 'KE': "Кения", 'CY': "Кипр", 'KG': "Киргизстан", 'KI': "Кирибати", 'CN': "Китай", 'CC': "Кокосовые (Киилинг) о-ва (AU)", 'CO': "Колумбия", 'KM': "Коморские о-ва", 'CG': "Конго", 'CR': "Коста-Рика", 'CI': "Кот-д'Ивуар", 'CU': "Куба", 'KW': "Кувейт", 'CK': "Кука о-ва (NZ)", 'LA': "Лаос", 'LV': "Латвия", 'LS': "Лесото", 'LR': "Либерия", 'LB': "Ливан", 'LY': "Ливия", 'LT': "Литва", 'LI': "Лихтенштейн", 'LU': "Люксембург", 'MU': "Маврикий", 'MR': "Мавритания", 'MG': "Мадагаскар", 'YT': "Майотта о. (KM)", 'MO': "Макао (PT)", 'MK': "Македония", 'MW': "Малави", 'MY': "Малайзия", 'ML': "Мали", 'MV': "Мальдивы", 'MT': "Мальта", 'MA': "Марокко", 'MQ': "Мартиника", 'MH': "Маршалловы о-ва", 'MX': "Мексика", 'FM': "Микронезия (US)", 'MZ': "Мозамбик", 'MD': "Молдова", 'MC': "Монако", 'MN': "Монголия", 'MS': "Монсеррат о. (GB)", 'MM': "Мьянма", 'NA': "Намибия", 'NR': "Науру", 'NP': "Непал", 'NE': "Нигер", 'NG': "Нигерия", 'NL': "Нидерланды", 'NI': "Никарагуа", 'NU': "Ниуэ о. (NZ)", 'NZ': "Новая Зеландия", 'NC': "Новая Каледония о. (FR)", 'NO': "Норвегия", 'NF': "Норфолк о. (AU)", 'AE': "Объединенные Арабские Эмираты", 'OM': "Оман", 'PK': "Пакистан", 'PW': "Палау (US)", 'PS': "Палестинская автономия", 'PA': "Панама", 'PG': "Папуа-Новая Гвинея", 'PY': "Парагвай", 'PE': "Перу", 'PN': "Питкэрн о-ва (GB)", 'PL': "Польша", 'PT': "Португалия", 'PR': "Пуэрто-Рико (US)", 'RE': "Реюньон о. (FR)", 'CX': "Рождества о. (AU)", 'RU': "Россия", 'RW': "Руанда", 'RO': "Румыния", 'SV': "Сальвадор", 'WS': "Самоа", 'SM': "Сан Марино", 'ST': "Сан-Томе и Принсипи", 'SA': "Саудовская Аравия", 'SZ': "Свазиленд", 'SJ': "Свалбард и Ян Мейен о-ва (NO)", 'SH': "Святой Елены о. (GB)", 'KP': "Северная Корея (КНДР)", 'MP': "Северные Марианские о-ва (US)", 'SC': "Сейшелы", 'VC': "Сен-Винсент и Гренадины", 'PM': "Сен-Пьер и Микелон (FR)", 'SN': "Сенегал", 'KN': "Сент-Кристофер и Невис", 'LC': "Сент-Люсия", 'RS': "Сербия", 'SG': "Сингапур", 'SY': "Сирия", 'SK': "Словакия", 'SI': "Словения", 'US': "Соединенные Штаты Америки", 'SB': "Соломоновы о-ва", 'SO': "Сомали", 'SD': "Судан", 'SR': "Суринам", 'SL': "Сьерра-Леоне", 'TJ': "Таджикистан", 'TH': "Таиланд", 'TW': "Тайвань", 'TZ': "Танзания", 'TC': "Теркс и Кайкос о-ва (GB)", 'TG': "Того", 'TK': "Токелау о-ва (NZ)", 'TO': "Тонга", 'TT': "Тринидад и Тобаго", 'TV': "Тувалу", 'TN': "Тунис", 'TM': "Туркменистан", 'TR': "Турция", 'UG': "Уганда", 'UZ': "Узбекистан", 'UA': "Украина", 'WF': "Уоллис и Футуна о-ва (FR)", 'UY': "Уругвай", 'FO': "Фарерские о-ва (DK)", 'FJ': "Фиджи", 'PH': "Филиппины", 'FI': "Финляндия", 'FK': "Фолклендские (Мальвинские) о-ва (GB/AR)", 'FR': "Франция", 'GF': "Французская Гвиана (FR)", 'PF': "Французская Полинезия", 'HM': "Херд и Макдональд о-ва (AU)", 'HR': "Хорватия", 'CF': "Центрально-африканская Республика", 'TD': "Чад", 'CZ': "Чехия", 'CL': "Чили", 'CH': "Швейцария", 'SE': "Швеция", 'LK': "Шри-Ланка", 'EC': "Эквадор", 'GQ': "Экваториальная Гвинея", 'ER': "Эритрия", 'EE': "Эстония", 'ET': "Эфиопия", 'YU': "Югославия", 'ZA': "Южная Африка", 'GS': "Южная Георгия и Южные Сандвичевы о-ва", 'KR': "Южная Корея (Республика Корея)", 'JM': "Ямайка", 'JP': "Япония"}

var $widget = $('<div class="input-group widget"><select class="countries"></select>' +
            '<input class="localnumber form-control" type="text"/></div>');

// обновление значения поля с телефоном после изменения виджетов
function checkKeyDownPhoneInput(e) {
    if ((e.keyCode >= 48 && e.keyCode <= 57) || (e.keyCode >= 96 && e.keyCode <= 105)) {
        updatePhoneInput(e);
        if ($(e.target).closest('.widget').data('input').data('valid')) {
            e.preventDefault();
        }
    }
}

// обновление значения поля с телефоном после изменения виджетов
function updatePhoneInput(e) {
    var phoneUtil = i18n.phonenumbers.PhoneNumberUtil.getInstance();
    var PNF = i18n.phonenumbers.PhoneNumberFormat;

    var $input = $(e.target).closest('.widget').data('input');
    var country =  $input.data('widget').find('select.countries').val();
    var country_code = i18n.phonenumbers.metadata.countryToMetadata[country][10];
    var number =  cleanPhone($input.data('widget').find('input.localnumber').val());

    if (number && number.search('\\+') == -1) {
        number = '+' + country_code + number;
    }

    try {
        number_data = phoneUtil.parseAndKeepRawInput(number, country);
    } catch (e) {
        // number может быть пустым, если пользователь хочет удалить телефон
        if (!number) {$input.val('');}

        $input.data('valid', false);
        return;
    }

    // если номер валидный, но страна отличается
    if (phoneUtil.isValidNumber(number_data) && phoneUtil.getRegionCodeForNumber(number_data) != country) {
        country = phoneUtil.getRegionCodeForNumber(number_data);
        country_code = i18n.phonenumbers.metadata.countryToMetadata[country][10];
        $input.data('widget').find('select.countries').selectpicker('val', country);
    }

    var int_number = formatInternational(country, number);
    $input.data('valid', phoneUtil.isValidNumber(number_data));
    $input.data('widget').find('input.localnumber').val(int_number.replace('+' + country_code, '').trim());

    // если номер не валидный, то оставляем старый без изменений
    if (phoneUtil.isValidNumber(number_data)) {
        $input.val(phoneUtil.format(number_data, PNF.E164));
    } else {
        $input.val(number);
    }
}

// обновление виджетов при изменении значения поля с телефоном (на самом деле это только для инициализации)
function updatePhoneWidgets(e) {
    var phoneUtil = i18n.phonenumbers.PhoneNumberUtil.getInstance();
    var PNF = i18n.phonenumbers.PhoneNumberFormat;

    var $input = $(e.target);

    // вот это лучше бы перенести в python, чтобы в форме номера начинались с символа "+"
    if ($(e.target).val().trim() && $(e.target).val().search('\\+') == -1) {
        $(e.target).val( '+' + $(e.target).val() );
    }

    try {
        number_data = phoneUtil.parseAndKeepRawInput($input.val(), 'US');
        var country = phoneUtil.getRegionCodeForNumber(number_data);
        var country_code = number_data.getCountryCode();
        var int_number = formatInternational(country, $input.val());
        $input.data('valid', phoneUtil.isValidNumber(number_data));
        $input.data('widget').find('select.countries').val(country || 'UA');
        $input.data('widget').find('input.localnumber').val(int_number.replace('+' + country_code, '').trim());
    } catch (e) {
        $input.data('widget').find('select.countries').val('UA');
        $input.data('widget').find('input.localnumber').val('');
    }
}

function maskPhoneInputs() {
    // заполнение виджета со списком стран
    for(var iso_code in i18n.phonenumbers.metadata.countryToMetadata) {
        if (iso_code.length == 2 && iso_code in COUNTRY_NAMES) {
            var phone_code = i18n.phonenumbers.metadata.countryToMetadata[iso_code][10];
            var flag = '<img src=\''+STATIC_URL+'img/null.gif\' class=\'flag flag-'+iso_code.toLowerCase()+'\'/>&nbsp; ';
            var short_title = flag + iso_code + ' +' + phone_code;
            var full_title  = flag + COUNTRY_NAMES[iso_code] + ' +' + phone_code;
            $widget.find('.countries').append('<option title="'+short_title+'" data-content="'+full_title+'" value="'+iso_code+'">'+short_title+'</option>');
        }
    }

    $('input.masked-phone').each(function(i, val) {
        var $input = $(this);

        if ($input.data('widget')) return;

        // инициализируем виджеты и связываем с основным полем
        var $w = $widget.clone();
        $w.data('input', $input).find('.localnumber').attr('placeholder', $input.attr('placeholder'));

        // вставляем виждеты после основного поля, а поле прячем
        $input.data('widget', $w).addClass("hidden").after($w);
    });

    $('select.countries').change(updatePhoneInput);
    $('input.localnumber').keydown(checkKeyDownPhoneInput).keyup(updatePhoneInput);
    $('input.masked-phone').change(updatePhoneWidgets).change();
    $('.input-group.widget').on('paste input propertychange', 'input.localnumber', updatePhoneInput);

    $('.masked-phone + .widget .countries').selectpicker({size:6, liveSearch:true}).on('hidden.bs.select', function (e) {
        $(e.target).change();
    });
}
