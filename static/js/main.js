var $body;
$(function () {
    $body = $('body');
//    Добавление CSRF-токена к ajax-запросу
    if ('cookie' in jQuery)
        addCSRFTokenToAjaxRequest();
    initRegionChooser();
    initPhoneMask();

    initSliders();
    initColorbox();
    initPhotoSwipeFromDOM('.pswp-gallery');
    initDeleteConfirm();
    initAdSearchForm();

    //initCityAutocomplete();
    initCityAutocompleteTypeahead();
    initToFavoriteAjax();

    initCityTypeahead();
    initHiddenToggle();
    initMainmenuDropdowns();

    initScrollToTop();

    initProfessionalsHiddenContacts();
    initProfessionalsPreviewsHeights();

    $('.form-control').attr('spellcheck', true);
    $('.logo-with-tooltip, .default-tooltip').tooltip({animation:false, placement: 'bottom'});
    $('a.default-tooltip[data-target="#login-popup"]').click(function() {
        $('#login-popup .nav-tabs a:last').tab('show');
    })

});

function initStreetFilter(streets) {
    var $hidden_street_id = $('#id_addr_street_id');
    var $input = $('#id_addr_street');
    var input_clearing_timeout = false;

    $input.typeahead({
        source: streets,
        autoSelect: false,
        minLength: 3,
        items: 'all'
    }).change(function(e) {
        var current = $input.typeahead("getActive");
        if (current && current.name == $input.val()) {
            $hidden_street_id.val(current.id);
            clearTimeout(input_clearing_timeout);
        } else {
            $hidden_street_id.val('');

            // задержка нужна, т.к. при выборе из списка typeahead поле сначала очищается,
            // а потом заполняется выбранным значением и в итоге поле мограет
            input_clearing_timeout = setTimeout(function() {$input.val('');}, 300);
        }
    });
}

function initDeleteConfirm() {
    // библиотеки с модальными окнами подтверждения работают через callback-и, и все равно потребуют костылей с искусственным submit-ом формы
    // используется модальное окно bootstrap и те же самые костыли

    var $modal = $('#confirm-delete-modal');

    $modal.find('button').click(function(e) {
        $modal.modal('hide');
        if ($(this).attr('name') == 'delete') {
            var button = $modal.data('sender');
            $(button).unbind('click').click();
        }
    });

    $('.confirm-delete').click(function(e) {
        if ($modal.length) {
            e.preventDefault();
            $modal.data('sender', this);
            $modal.modal('show');
        } else {
            if (!confirm("Вы уверены?")) {
                e.preventDefault();
            }
        }
    });
}

function initSubwayFilter(){
    // Обработчик метро
    var active_stations = $('#id_subway_stations').val();
    var active_stations_list = [];
    if (active_stations && active_stations.length) {
        active_stations.forEach(function(value, pos, arr) {
            var $li = $('.subway-popup ul li[data-subway-id=' + value + ']');
            $li.addClass('active');
            active_stations_list.push($li.text());
        });
        $('#subway').val(active_stations_list.join(', '));
    }

    $('.subway-popup ul li').click(function(e) {
        e.stopPropagation();
        var active_stations = [];
        var active_stations_list = [];
        var $subway_stations = $('#id_subway_stations');
        $(this).toggleClass('active');

        $('.subway-popup ul li.active').each(function() {
            active_stations.push($(this).data('subwayId'));
            active_stations_list.push($(this).text());
        });
        $subway_stations.val(active_stations);
        $('#subway').val(active_stations_list.join(', '));
    })
}

function formatNumber(number) {
    number = number.toString();
    var rgx = /(\d+)(\d{3})/;
    while (rgx.test(number)) {
        number = number.replace(rgx, '$1' + ' ' + '$2');
    }
    return number;
}

function initAdSearchForm() {
    var $form = $('#search-property');
    if ($form.length == 0) return;

    initRangeFilter();
    initSubwayFilter();

    var property_type_rules = {
        'newhomes': ['flat', 'room'],
        'rent_daily': ['flat', 'room', 'house']
    };

    $('#id_deal_type', $form).change(function() {
        var value = $(this).val();
        $('#id_property_type option', $form).prop("disabled", false);
        $.each(property_type_rules, function(deal_type, property_types) {
            if (value == deal_type) {
                $('#id_property_type option', $form).each(function() {
                    var $option = $(this);
                    $option.prop("disabled", $.inArray($option.val(), property_types) == -1);
                });
            }
        });
        $('#id_property_type', $form).selectpicker('render');
    });
    $('#id_property_type', $form).change(function() {
        if ($(this).val() == 'room') {
            $('#id_rooms', $form).multiselect('disable');
        } else {
            $('#id_rooms', $form).multiselect('enable');
        }
    });
}

// обработчики для фильтра по диапазону значений
function initRangeFilter() {
    $('.range-filter input').focus(function(e) {
        var $filter = $(this).closest('.range-filter');
        var $active_input = $(this);
        var $inactive_input = $('input', $filter).not(this);

        $('input', $filter).removeClass('active').filter(this).addClass('active');
        $('.options', $filter).toggleClass('text-right', $(this).is('.to'));

        $(".options li", $filter).each(function(i, option) {
            var value = parseInt($(option).data('value'));

            var enabled = !$inactive_input.val() ||
                            $inactive_input.is('.from') && value > $inactive_input.val() ||
                            $inactive_input.is('.to') && value < $inactive_input.val();
            $(option).toggleClass("hidden", !enabled);
            $(option).toggleClass("active", value == parseInt($active_input.val()));
        });
    }).change(function(e) {
        var $filter = $(this).closest('.range-filter');
        var from = parseInt($filter.find('input.from').val());
        var to = parseInt($filter.find('input.to').val());

        if (from && to) {
            var as_text = formatNumber(from) + ' &mdash; ' + formatNumber(to);
        } else if (from) {
            var as_text = 'от ' + formatNumber(from);
        } else if (to) {
            var as_text = 'до ' + formatNumber(to);
        } else {
            var as_text = '';
        }
        $('.as_text', $filter).html(as_text);
    }).filter('.active').change();

    var presets = {
        area: [20, 30, 50, 70, 100],
        area_living: [10, 20, 30, 50, 70, 100],
        price_sale: [500000, 750000, 1000000, 1500000, 2000000],
        price_rent: [4000, 6000, 8000, 10000, 12000, 14000],
        price_rent_daily: [250, 350, 500, 1000, 1500],
        price_newhome: [4000, 6000, 8000, 10000, 15000, 20000, 30000, 40000, 60000, 80000, 100000, 150000, 200000]
    };

    $('.range-filter').on('show.bs.dropdown', function (e) {
        var $options = $(this).find('.options');
        $options.empty();

        var preset_name = $(this).data('field');
        if (preset_name == 'price') {preset_name += '_' + $(this).closest('form').data('deal_type')}
        if (preset_name in presets) {
            $.each(presets[preset_name], function(i, value) {
                $options.append('<li data-value="' + value + '">' + formatNumber(value) + '</li>');
            });
        }

    }).on('shown.bs.dropdown', function (e) {
        $(this).find('input.from').focus();

    }).on("click", ".options li", function(e) {
        var $filter = $(this).closest('.range-filter');
        var $input = $('input.active', $filter);
        $input.val($(this).data('value')).change();
        if ($input.is('.from')) {
            $('input.to', $filter).focus();
        } else {
            $('.dropdown-toggle', $filter).dropdown('toggle');
        }
        e.stopPropagation();
    });
}

function addCSRFTokenToAjaxRequest() {
    var csrftoken = $.cookie('csrftoken');

    function csrfSafeMethod(method) {
        return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
    }

    function sameOrigin(url) {
        var host = document.location.host; // host + port
        var protocol = document.location.protocol;
        var sr_origin = '//' + host;
        var origin = protocol + sr_origin;
        // Allow absolute or scheme relative URLs to same origin
        return (url == origin || url.slice(0, origin.length + 1) == origin + '/') ||
            (url == sr_origin || url.slice(0, sr_origin.length + 1) == sr_origin + '/') || !(/^(\/\/|http:|https:).*/.test(url));
    }

    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
            if (!csrfSafeMethod(settings.type) && sameOrigin(settings.url)) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        }
    });
}

function initRegionChooser() {
    var $popup = $('#cities-choose-dropdown'); // сам блок dropdown/popup, который появляется когда нужны выбирать регион

    $popup.on('show.bs.modal', function(e) {
        $popup.data('sender', $(e.relatedTarget));
    });

    // выставляется активность города, относящегося к текущему поддомену
    $('a.city[data-id="' + $('.subdomain-region-choose').data('id') + '"]', $popup).addClass('active');

    // событие выбора города для шапки
    $('.l-header .subdomain-region-choose').on("region-choose", function(e, id, name, static_url) {
        window.location = getRegionURL(static_url, 'sale', '');
    });

    function updateSearchFormAction($form) {
        var url = getRegionURL($form.data('static_url'), $form.data('deal_type'), $form.data('property_type'));
        $form.attr("action", url );
        return url;
    }

    // изменение типов сделки ведут к смене адреса формы
    $('.l-property-search .affecting-selects select').change(function(e) {
        var $form = $(this).closest('form');
        if (this.name == 'section') {
            $form.data('deal_type', $(this).val().split(';')[0]);
            $form.data('property_type', $(this).val().split(';')[1]);
        } else {
            $form.data(this.name, $(this).val());
        }
        updateSearchFormAction($form);
    }).first().change();

    // событие выбора города для формы поиска
    $('.l-property-search .city-chooser').on("region-choose", function(e, id, name, static_url) {
        var $form = $(this).closest('form').data('static_url', static_url);
        $(".region-name", this).text(name);
        $popup.modal('hide'); // закрываем popup

        // отключаем активные поля в ожидании ajax-ответа с новыми полями
        $('#subway-district-street input, #subway-district-street select', $form).prop('disabled', true);

        var url = updateSearchFormAction($form);
        document.location = url;
        /*
        // AJAX обновление полей
        $('#subway-district-street', $form).load(url + "?no_ads #subway-district-street .form-group", function( response, status, xhr ) {
            $('#subway-district-street #id_district').multiselect({buttonWidth: '100%', allSelectedText: 'Все выбрано', nonSelectedText: 'Выберите район', numberDisplayed: 100});
            $('#subway-district-street select[multiple]').multiselect({buttonWidth: '100%', allSelectedText: 'Все выбрано', nonSelectedText: '', numberDisplayed: 100});

            // активируем первую вкладку фильтров районов/метро/улиц
            var $first_tab = $('#subway-district-street .nav li:not(.disabled)').first().addClass('active');
            $('#subway-district-street ' + $first_tab.find('a').attr('href')).addClass('active');
        });*/
    });

    function getRegionURL(static_url, deal_type, property_type) {
        static_url = static_url.replace(/\/$/, '').split(";"); // убирает последний слеш и разбивает на два части
        var url;
        var root_domain = $popup.data('root-domain') ;
        var lang_code = $popup.data('lang-code') ;

        // собираем url по частям
        url = "//" + ( static_url[0] ? static_url[0] + '.' : '' ) + root_domain + '/';

        if (lang_code != 'ru')
            url += lang_code + '/';

        url += deal_type + '/';

        if (static_url[1]) {
            url += static_url[1] + '/';
        }
        if (property_type && property_type != 'flat') {
            url = url.slice(0, -1) + '-' + property_type + '/';
        }
        return url;
    }

    function getRegionDataFromObj(obj) {
        return [$(obj).data('id'), $(obj).attr('title') || $(obj).text().trim(), $(obj).data('static_url') ];
    }

    $popup.on('click','a.city', function(e) {
        $popup.data('sender').trigger("region-choose", getRegionDataFromObj(this));
        e.preventDefault();
    });

    $popup.on('click','a.province', function(e) {
        e.preventDefault();
        var $this = $(this);

        $.get($this.data('cities_url'), {}, function(response, status){
            if (status == 'success'){
                $("#extra_cities_list").html(response);
                $(".js_in_region_caption").tab('show');
            }
        });
    });
}

// вся эта замута из-за того, что phoneformat.min.js весит почти 0.5 мегабайта
function initPhoneMask() {
    function loadCssJs() {
        // загрузка css
        $.each(['libs/bootstrap-select/bootstrap-select.min.css', 'libs/country-flags/flags.css'], function(i, link) {
            $('head').append("<link rel='stylesheet' type='text/css' href='" + STATIC_URL + link + "'/>");
        });

        // запуск функции только после полной загрузки js
        $.when(
            $.getScript(STATIC_URL + "js/libs/phoneformat.min.js" ),
            $.getScript(STATIC_URL + "libs/bootstrap-select/bootstrap-select.min.js" ),
            $.getScript(STATIC_URL + "js/masked_phone.js" ),
            $.Deferred(function( deferred ){ $( deferred.resolve );})
        ).done(function(){
            maskPhoneInputs();
        });
    }

    if ($('.masked-phone:visible').length) {
        loadCssJs();
    }
    else if ($('.modal .masked-phone').length) {
        $('.modal .masked-phone').closest('.modal').one('show.bs.modal', loadCssJs);
    }
}


function checkYM($target) {
    if ($target.length) {
        $target.removeClass('show-yandex-map');
        $.getScript('//api-maps.yandex.ru/2.0/?coordorder=longlat&load=package.full&wizard=constructor&lang=' + $target.data('lang-code'), function (data, textStatus, jqxhr) {
            ymaps.ready(function () {
                var x = $target.data('lon'), y = $target.data('lat'),
                    content = $target.find('.content').html();
                $target.empty();
                var myMap = new ymaps.Map("embed_map", { center: [x, y], zoom: 15, type: "yandex#map"});
                myMap.controls.add("zoomControl").add("mapTools").add(new ymaps.control.TypeSelector(["yandex#map", "yandex#satellite", "yandex#hybrid", "yandex#publicMap"]));
                myMap.behaviors.enable("ruler");

                var myPlacemark = new ymaps.Placemark([x, y], { balloonContent: content}, {hideIconOnBalloonOpen: true});
                myMap.geoObjects.add(myPlacemark);
                $target.data('map', myMap);
            });
        });
    }
}

function checkOSM($target) {
    if ($target.length) {
        $target.removeClass('show-osm-map');
        $.getScript($target.data('js'), function (data, textStatus, jqxhr) {
            var lat = $target.data('lat'), lon = $target.data('lon'),
                content = $target.find('.content').html(),
                map = L.map($target[0]).setView([lat, lon], 15);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }).addTo(map);

            L.marker([lat, lon]).addTo(map).bindPopup(content).openPopup();
            $target.data('map', map);
        });
    }
}

function InstallPropertyPage() {
    var $propertyDetail = $('#property-detail, #property-detail-small');
    $propertyDetail.on('click', '.show-contacts', function(e) {
        var $form = $(this).parents('form');
        $form.find('.show-contacts-button').addClass('loading');

        $.ajax({
            type: "POST",
            url:  $form.attr('action'),
            data: $form.serialize()
        }).done(function (data) {
            $.each(data, function (key, value) {
                if (key == 'skype') value = '<a href="skype:' + value + '?call" rel="nofollow">' + value + '</a>';
                if (key == 'email') value = '<a href="mailto:' + value + '" rel="nofollow">' + value + '</a>';
                if (value) $propertyDetail.find('.usercard .' + key + ' span').each(function() {$(this).html(value);});
            });
            $propertyDetail.find('.contacts .note').removeClass('hidden');
            $propertyDetail.find('.show-contacts').remove();
            $propertyDetail.find(".show-contacts").unbind('click');
        });

        yaCounter19774096.reachGoal('contacts');
    });

    $('a.send-message').click(function(e) {
        e.preventDefault();
        $("#message-modal .modal-body").html('<iframe width="100%" height="290" frameborder="0" scrolling="auto" src="' + this.href + '"></iframe>');
        $('#message-modal').modal({show:true})
    });

    checkYM($('.show-yandex-map'));
    checkOSM($('.show-osm-map'));
}

function initPropertyGallery() {
    var $gallery = $('.property-detail .gallery');

    // открытие первой вкладки в галерее
    $('.nav a', $gallery).on('shown.bs.tab', function (e) {
        $('.status-bar .name', $gallery).text($(e.target).data('status-bar') || '');
        $('.status-bar .photo-counter', $gallery).text('');
    });

    // при открытии вкладки подгружать карту
    $('.nav .btn-map a', $gallery).one('shown.bs.tab', function(e) {
       checkOSM($('#embed_map'));
    });

    //  повторная инициализация первого фото, т.к. оно может иметь неверную высоту, если вкладка со слайдером скрыта
    $('.nav .btn-photos a', $gallery).one('shown.bs.tab', function(e) {
        $('.js_scroll_big_image').get(0).slick.setPosition();
    });

    $('.status-bar .show-in-fullscreen', $gallery).click(function() {
        var $active_tab = $('.tab-pane.active', $gallery),
            active_tab_name = $active_tab.attr('id');

        if (active_tab_name  == 'tab-photos') {
            $('.slick-current a', $gallery).click();
        } else {
            $('#modal-fullscreen').data('return-to', $active_tab).modal('show');
            $active_tab.children().appendTo($('#modal-fullscreen .modal-content'));
        }
    });
    $('#modal-fullscreen').on('shown.bs.modal', function (e) {
        $('#embed_map:visible').data('map').invalidateSize();
        // $('#embed_map:visible').data('map').container.fitToViewport(); // for yandex map
    }).on('hidden.bs.modal', function (e) {
        $('#modal-fullscreen .modal-content').children().appendTo($(e.target).data('return-to'));
        $('#embed_map:visible').data('map').invalidateSize();
        // $('#embed_map:visible').data('map').container.fitToViewport(); // for yandex map
    });

    // важно: не перепутать порядок назначения обработчика событий.
    // сначала назначается общий shown.bs.tab, потом это же событие для .btn-photos, а потом вызывается tab('show')
    function updateStatusBarForGallery() {
        var title = $('.js_scroll_big_image .slick-current a', $gallery).attr('title'),
            index = $('.js_scroll_big_image').slick('slickCurrentSlide'),
            total = $('.js_scroll_big_image .slick-slide').length;
        $('.status-bar .name', $gallery).text(title);
        $('.status-bar .photo-counter', $gallery).text(index+1 + ' / ' + total);
    }
    $('.nav .btn-photos a', $gallery).on('shown.bs.tab', updateStatusBarForGallery);
    $('.js_scroll_big_image', $gallery).on('afterChange', updateStatusBarForGallery);

    $('.nav a:first', $gallery).tab('show');
}

function initSliders() {
    /*var $ads_slider = $('.js_scroll_ads'); // блок с последними объявлениями на главной
    if ($ads_slider.length) {
        $ads_slider.slick({
            dots: false,
            infinite: false,
            speed: 300,
            slidesToShow: 4,
            touchMove: true,
            slidesToScroll: 1,
            responsive: [
                {breakpoint: 1024, settings: {slidesToShow: 3}},
                {breakpoint: 600, settings: {slidesToShow: 2}},
                {breakpoint: 480, settings: {slidesToShow: 1}}
            ]
        });
    }*/

    var $big_img = $('.js_scroll_big_image'),
        $img_slider = $('.js_scroll_ad_images'),
        big_img_opts = {
                dots: false,
                infinite: false,
                adaptiveHeight: true,
                touchMove: true,
                slidesToShow: 1,
                slidesToScroll: 1
        },
        img_slider_opts = {
                dots: false,
                infinite: false,
                speed: 300,
                slidesToShow: slidesToShow,
                touchMove: true,
                slidesToScroll: 1,
                focusOnSelect: true
        },
        slidesToShow = $img_slider.data('slides-to-show') || 4;

    if ($img_slider.length) {
        if ($img_slider.children().length <= slidesToShow) {
            $body.on('click', ".js_scroll_ad_images .mst_preview_img", function (e) {
                var i = $(this).index();
                $big_img.slick('slickGoTo', i);
            });
        } else {
            big_img_opts.asNavFor = '.js_scroll_ad_images';
            img_slider_opts.asNavFor = '.js_scroll_big_image';
        }
        $img_slider.slick(img_slider_opts);
    }

    if ($big_img.length) {
        $big_img.slick(big_img_opts);
    }

}


function initColorbox() {
    var $big_box = $('.js_big_image_wrap');
    if ($big_box.length){
        $big_box.colorbox({
            photo: true,
            maxWidth: '95%',
            maxHeight: '95%',
            // internationalization
            current: "{current} из {total}",
            previous: "назад",
            next: "дальше",
            close: "закрыть",
            xhrError: "Ошибка загрузки.",
            imgError: "Ошибка загрузки."
        });
    }
}

// функция, которая скрывает и показывает услуги в зависимости от типа сделки
function updateFacilities(deal_type) {
    var $facilities_container = $('#div_id_facilities');
    var $checkboxes = $('input[name=facilities]', $facilities_container);

    // фкнкция вынимает элементы из DOM, очищает родителя, делит элементы на 4 колонки и возвращает к первоначальному родителю
    function breakIntoColumn(list){
        var listLength = list.size();
        var numOfLists = 4;
        var numInRow = Math.ceil(listLength / numOfLists);
        var container = list.parent();

        list.detach();
        container.empty();
        for (var i=0;i<numOfLists;i++){
            var listItems = list.slice(numInRow*i, numInRow*i+numInRow);
            var newList = $('<div class="checkbox col-sm-'+(20/numOfLists)+'"/>').append(listItems);
            container.append(newList);
        }
    }

    if ("facilities_by_deal_type" in window) {
        // добавляем блоки для скрытия ненужных элементов
        if (!$facilities_container.find('.hidden').length) {
            $('.controls .row', $facilities_container).addClass('hidden').after('<div class="row visible"/>');
        }

        $checkboxes.parent().parent().appendTo($('.controls .hidden', $facilities_container));
        var $visible_facilities = $checkboxes.filter(function( index ) {
            return $.inArray(parseInt(this.value), facilities_by_deal_type[deal_type]) > -1;
        }).parent().parent();
        if ($visible_facilities.length) {
            $visible_facilities.appendTo($('.controls .visible', $facilities_container));
            breakIntoColumn($visible_facilities);
        }
        $facilities_container.toggle($visible_facilities.length > 0);
    }
}

function updateFirstLabelWidth() {
    var $first_label = $('.form-horizontal .control-label:first-child');

    $('.form-inline .form-group .control-label').css({'width':'auto', 'text-align':'left'});
    if ($first_label.css('display') == 'block') {
        $('.form-inline .form-group:visible').each(function() {
            if (this.offsetLeft == this.parentNode.offsetLeft) {
                $(this).find('.control-label').css({'width':$first_label.width()+15, 'text-align':'right'});
            }
        });
    }
}

function updateAdFormFieldsVisibility(e) {
    var $form = $('form.property-form');
    var $deal_type = $('#div_id_deal_type input', $form);
    var $property_type = $('#div_id_property_type input', $form);

    var deal_type = $deal_type.filter(':checked').val();
    var daily = (deal_type == 'rent_daily');
    var newhomes = (deal_type == 'newhomes');
    var rent_daily = (deal_type == 'rent_daily');

    var property_type = $property_type.filter(':checked').val();
    var commercial = ( property_type == 'commercial' );
    var is_building = ( $.inArray(property_type, ['plot', 'garages']) == -1 );

    var international_mode = ($('#id_addr_country').val() != 'UA');

    // убираем из типа недвижимости комнаты, участнки и новостройки, если выбран тип сделки Новостройки
    // а так же участки, если выбран тип сделки Посуточная
    // а так же гаражи, коммерческие, если публикация в зарубежном каталоге
    $('#div_id_property_type .controls label').each(function (i) {
        $(this).toggleClass('hidden',
            (newhomes && ($.inArray($('input', this).val(), ['room', 'plot', 'newhomes']) > -1))
            || (rent_daily && ($.inArray($('input', this).val(), ['plot', 'garages', 'commercial']) > -1))
            || (international_mode && ($.inArray($('input', this).val(), ['room', 'garages', 'commercial']) > -1))
        );
    });


    // Балуемся с названиями к формам + обязательными полями
    var $price_label = $('#div_id_price').find('label');
    var $area_label = $('#div_id_area').find('label');
    var label_html = $price_label.html();
    if (newhomes) {
        label_html = label_html.replace('Цена', 'Цена за м<sup>2</sup>');
        $area_label.addClass('requiredField').html('Площадь<span class="asteriskField">*</span>');
    } else {
        label_html = label_html.replace('Цена за м<sup>2</sup>', 'Цена');
        $area_label.removeClass('requiredField').text('Площадь');
    }
    $price_label.html(label_html);

    $('#div_id_reserved, #div_id_guests_limit, #div_id_rules').toggleClass('hidden', !daily);
    $('#div_id_expire').toggleClass('hidden', daily);

    // фильтруем список удобств и перерисовываем
    updateFacilities(deal_type);

    // Для посуточной аренды нет возможности указать "без комиссии"
    $('#id_without_commission').parent().toggleClass('hidden', daily);

    /// property type
    $('#div_id_property_commercial_type').toggleClass('hidden', !commercial);
    $("#div_id_property_commercial_type select").prop('disabled', !commercial);
    $("#div_id_rooms, #div_id_floor, #div_id_floors_total").toggleClass('hidden', !is_building);
    $("#div_id_floor").toggleClass('hidden', !(is_building && property_type != 'house'));

    $('#div_id_building_type, #div_id_building_walls').toggleClass('hidden', !is_building);
    $('#div_id_building_layout').toggleClass('hidden', !(is_building && property_type != 'room'));

    $(".for-living-property").toggleClass('hidden', $.inArray(property_type, ['flat', 'house']) == -1);
    $("#id_area input").attr('placeholder', property_type != "plot" ? "общая" : "в сотках");

    /// international
    $('#div_id_addr_country').toggleClass('hidden', !international_mode);
    $('#id_submit_intl').toggleClass('hidden', !international_mode);
    $('#id_submit').toggleClass('hidden', international_mode);
    $('#div_id_deal_type').find('.radio-deal_type-newhomes, .radio-deal_type-rent_daily').toggleClass('hidden', international_mode);

    // обновление ширины первого label в строке
    updateFirstLabelWidth();
}

function initAdFormEvents() {
    var $form = $('form.property-form');
    var $deal_type = $('#div_id_deal_type input', $form);
    var $property_type = $('#div_id_property_type input', $form);
    var $types_container = $deal_type.add($property_type).parents('.btn-group');

    $deal_type.add($property_type).change(function () {
        $(this).filter(':checked').parents('.btn-group').addClass('choosed');
    });

    $types_container.click(function (e) {
        if ($(this).is('.choosed')) {
            $(this).removeClass('choosed').find('label').removeClass('active').find("input").prop('checked', false);
            return false;
        }
    });
    $("#div_id_deal_type .helptext").addClass('hidden-xs hidden-sm').appendTo("#div_id_deal_type .btn-group");
    $("#div_id_property_type .helptext").addClass('hidden-xs hidden-sm').appendTo("#div_id_property_type .btn-group");

    $('#div_id_reserved, #div_id_guests_limit, #div_id_expire, #div_id_property_commercial_type').addClass('hidden');
    $('#div_id_building_layout, #div_id_building_type, #div_id_building_walls').addClass('hidden');

    $(window).resize(updateFirstLabelWidth);

    $deal_type.change(updateAdFormFieldsVisibility);
    $property_type.change(updateAdFormFieldsVisibility);
    $('#id_addr_country').change(updateAdFormFieldsVisibility);

    $('#div_id_international input').change(function() {
        if ($(this).val() == 'yes') {
            if ($('#id_addr_country').val() == 'UA') {
                $('#id_addr_country').selectpicker('val', '');
            }
            $('.radio-promotion-no').click();
        } else {
            $('#id_addr_country').selectpicker('val', 'UA');
        }
        $('#id_international2').prop("checked", $(this).val() == 'yes');
        updateAdFormFieldsVisibility();
    }).filter(':checked').change();

    $("#id_building_type").change(function () {
        $('#div_id_building_type_other').toggleClass('hidden', $(this).val() != '200');
    }).change();

    // Перекидываем helptext в placeholder
    $('#div_id_area, #div_id_area_living, #div_id_area_kitchen, #div_id_building_type_other').find('.helptext').each(function () {
        $(this).parents('.controls').find('input').attr('placeholder', $(this).text());
        $(this).remove();
    });

    // Изменение порядка полей внутри формы
    $('#div_id_tos', $form).insertBefore($('#div_id_submit', $form));
    $('#div_id_phones', $form).parent().appendTo($('.fieldset-2', $form));
    $('#div_id_promotion', $form).parents('.fieldset').insertAfter($('.fieldset-photos', $form));

    //$address_block = $('#id_address').parents('p').hide();
    $('#id_city2address', $form).change(function () {
        var city_name = $(this).find('option:selected').text(),
            $target = $('#id_address'),
            is_full = ($target.val().length > 30);

        if (!is_full) {
            if ($(this).val()) {
                $target.val('Украина, ' + city_name + ', ');
            } else {
                //alert('other city');
            }
            //$address_block.slideDown();
        }
    });
}

function initAdForm() {
    var $form = $('form.property-form');

    // добавляется через JS, т.к. это поле необязательно для типа недвижимости "дом"
    $('#div_id_addr_street label', $form).append('<span class="asteriskField">*</span>');

    $form.submit(function(event) {
        event.preventDefault();

        var $submit = $('[type=submit]', this);
        $submit.prop('disabled', true);

        function showErrors(errors) {
            for (var fieldName in errors) {
                var elementsToMark = $('#div_id_' + fieldName).find('.btn-group, .form-control, #id_tos, input').filter(':visible').first();
                if (elementsToMark.length == 0) {
                    elementsToMark = $('#id_' + fieldName).first();
                }

                elementsToMark.closest('.form-group').addClass('has-error').one('click mousedown', function() {
                    $(this).removeClass('has-error').find('.popover').popover('destroy');
                });

                elementsToMark.popover({'viewport':{ "selector": ".property-form"}, 'trigger':'manual', 'placement':'right', 'content':errors[fieldName]})
                    .popover('show');
            }
            if ($('.popover').length) {
                $('html, body').animate({
                    scrollTop: $('.popover').last().offset().top - 10
                }, 500); // скроллим до блока с ошибками
            }
        }

        $.ajax({
            type: 'post',
            data: $form.serialize(),
            error: function(jqXHR, textStatus, errorThrown) {
                var errors = {'submit': [gettext('Ошибка при выполнении запроса')]};
                showErrors(errors);
                $submit.removeProp('disabled');
            },
            success: function(data) {
                if (data['success']) {
                    window.location.href = data['redirect_url'];
                } else {
                    var nonFieldErrors = data['errors']['__all__'];
                    if (nonFieldErrors) {
                        data['errors']['submit'] = nonFieldErrors;
                    }
                    showErrors(data['errors']);
                    $submit.removeProp('disabled');
                }
            }
        });
    });
}

function initCityAutocompleteTypeahead() {
    var $el = $("input.js_city_search"),
        action_url = $el.data('action'),
        req = null;

    if (!$el.hasClass('international')) {
        $el.closest('form').submit(function(e) {e.preventDefault();});
    }
    $el.typeahead({
        minLength: 2,
        items: 'all',
        matcher: function (item) {return true;},
        highlighter: function (item) {
            var query = this.query.replace(/[\-\[\]{}()*+?.,\\\^$|#\s]/g, '\\$&');
            return item.replace(new RegExp('(' + query + ')', 'ig'), function ($1, match) {
                return '<strong>' + match + '</strong>'
            });
        },
        updater: function (item) {
            var $dropdown = this.$element.closest('#cities-choose-dropdown');
            if ($dropdown.length) {
                $dropdown.data('sender').trigger("region-choose", [item.id, item.value, item.static_url]);
            } else {
                this.$element.trigger("region-choose", [item.id, item.value, item.static_url]);
            }
            return item.value;
        },
        source: function (query, process) {
            if (req) {req.abort();}
            req = $.get(action_url, { term: query}, function (data) {req = null;return process(data);});
            return req;
        },
        async: true
    });
}

function initToFavoriteAjax() {
    $('.to-favorite').on("click", function(e) {
        e.preventDefault();

        var $obj = $(this);
        $.ajax({
            url: this.href,
            crossDomain: true,
            xhrFields: { withCredentials: true },
            data:{"ajax":"1"}
        }).done(function(data) {
            $(e.currentTarget).find('.icon-favorite').toggleClass('icon-favorite-active', data == 'add');
        });
    });
}


function initHomepageSlider() {
    // Banner slider
}

// расстановка точек с объявлениями на карте в левой части страницы результатов поиска (OpenStreetMaps)
function initPropertySearchOSMMaps(staticUrl) {
    var $target = $('#embed_map'),
        lat = $target.data('lat') || 0, lon = $target.data('lon') || 0,
        map = L.map($target[0]).setView([lat, lon], 15);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    var markers = L.markerClusterGroup();
    $.each($(".properties-search-result-list .property"), function(index, value) {
        var p = $(value),
            data = {
                'long': p.find('meta[itemprop="longitude"]').attr('content'),
                'lat': p.find('meta[itemprop="latitude"]').attr('content'),
                'id': p.data('id'), 'name': p.find('[itemprop="name"]').text(),
                'url': p.find('[itemprop="url"]').attr('href'),
                'img': p.find('img').attr('src'),
                'price': p.find('[itemprop="lowPrice"]').text()
            },
            popupContent = '<a href="' + data.url + '"><img src="'+ data.img +'" width="262" height="159"></a>'+
                    '<div class="price-map">'+ data.price +'</div>' + '<div>' +  data.name + '</div>',
            marker = L.marker([data.lat, data.long], {'icon': L.icon({iconUrl: staticUrl + '/map-point.svg',iconSize: [15, 15]})}).bindPopup(popupContent);
        markers.addLayer(marker);
    });
    map.addLayer(markers);
    map.fitBounds(markers.getBounds(), {padding: [20, 20]});
}

// расстановка точек с объявлениями на карте в левой части страницы результатов поиска
function initPropertySearchYMaps(staticUrl) {
    ymaps.ready(function () {
        var center_coords = [$('#maps_api').data('lat'), $('#maps_api').data('lon')];
        var map = new ymaps.Map("maps_api", {center: center_coords, zoom: 11, type: "yandex#map"}, {maxZoom:16});
        $('#maps_api').data('map', map);

        //Настройка кластера
        var clusterer = new ymaps.Clusterer({ 
            gridSize: 64, 
            groupByCoordinates: false,
            hasBalloon: true,
            margin: 20,
            maxZoom: 14,
            minClusterSize: 2,
            showInAlphabeticalOrder: false,
            viewportMargin: 64,
            preset: 'islands#redClusterIcons',
            clusterDisableClickZoom: false
        });
        
        //Настройка всплывающей подсказки
        function hintTemplate(price){
            HintLayout = ymaps.templateLayoutFactory.createClass( '<div class="price-map-hint">'+price+'</div>', {
                    // Определяем метод getShape, который
                    // будет возвращать размеры макета хинта.
                    // Это необходимо для того, чтобы хинт автоматически
                    // сдвигал позицию при выходе за пределы карты.
                    getShape: function () {
                        var el = this.getElement(),
                            result = null;
                        if (el) {
                            var firstChild = el.firstChild;
                            result = new ymaps.shape.Rectangle(
                                new ymaps.geometry.pixel.Rectangle([
                                    [0, 0],
                                    [firstChild.offsetWidth, firstChild.offsetHeight]
                                ])
                            );
                        }
                        return result;
                    }
                }
            );
            return HintLayout;
        }

        // Настройка метки и балуна 
        function crPl(coords, object) { 
            var placemark = new ymaps.Placemark(
                [coords[0],coords[1]], {
                    id: object.id, 
                    clusterCaption: object.name,
                    balloonContent: '<a href="' + object.link + '"><img src="'+ object.img +'" width="262" height="159"></a>'+
                    '<div class="price-map">'+ object.price +'</div>' + '<div>' +  object.name + '</div>'
                }, {
                    iconLayout: 'default#image',
                    iconImageHref: staticUrl + '/map-point.svg', // картинка иконки
                    iconImageSize: [15, 15], 
                    iconImageOffset: [-8, -15],
                    openHintOnHover: true,
                    balloonShadow: false,
                    balloonCloseButton: false,
                    balloonMaxWidth:262,
                    balloonPanelMaxMapArea: 0,
                    // Не скрываем иконку при открытом балуне.
                    hideIconOnBalloonOpen: false,
                    // И дополнительно смещаем балун, для открытия над иконкой.
                    balloonOffset: [0, -20],
                    hintPane: 'hint',
                    hintFitPane: true,
                    hintLayout: hintTemplate(object.price)
                }
            );

            $('#map-pointer-'+object.id).click(function() {
                var zoom = map.getZoom() ;
                map.setCenter(placemark.geometry.getCoordinates(), (zoom < 12) ? 12 : zoom, {checkZoomRange:true, duration:500, callback:function() {placemark.balloon.open();}} );
            });
            return placemark;
        }

        var myCollection = [];

        $.each($(".properties-search-result-list .property"), function(index, value) {
            var p = $(value);
            data = {
                'long': p.find('meta[itemprop="longitude"]').attr('content'), 
                'lat': p.find('meta[itemprop="latitude"]').attr('content'),
                'id': p.data('id'), 'name': p.find('[itemprop="name"]').text(),
                'url': p.find('[itemprop="url"]').attr('href'), 
                'img': p.find('img').attr('src'),
                'price': p.find('[itemprop="lowPrice"]').text()
            };
            // Добавляем метку
            myCollection[index] = crPl([data.long, data.lat], {id: data.id, name: data.name, link:data.url, price:data.price, img:data.img });
        });


        if (myCollection.length > 0) {

            clusterer.add(myCollection);

            clusterer.events.once('objectsaddtomap', function () {
                map.setBounds(clusterer.getBounds(), {checkZoomRange: true});
            });

            //При наведении перемещаем на первый план
            clusterer.events
            .add(['mouseenter', 'mouseleave'], function (e) {
                var target = e.get('target'), // Геообъект - источник события.
                    eType = e.get('type'); // Тип события.
                if (typeof target.getGeoObjects != 'undefined') {
                    zIndex = (eType === 'mouseenter') ? 1000 : 0; // 1000 или 0 в зависимости от типа события.
                    target.options.set('zIndex', zIndex);
                } 
            });
            
            var centerAndZoom = ymaps.util.bounds.getCenterAndZoom(
                clusterer.getBounds(),
                map.container.getSize(),
                map.options.get('projection')
            );

            // Центрируем карту в зависимости от расположения кластеров (точек)
            map.setCenter(centerAndZoom.center, centerAndZoom.zoom);

            map.geoObjects.add(clusterer);

            // Закрываем балун по клику на карте
            map.events.add('click', function (e) {  
                map.balloon.close();
            });

        }

    });
}

function initMyProperties() {
    var $form = $('#my-properties-form');

    // костыль, убирающий из POST лишние данные
    $('.my-properties select').filter("[name=status],[name=desired-vip]").each(function() {
        var name = $(this).attr('name');
        var $input = $("<input type='hidden'/>").attr("name", name).prop('disabled', true).insertAfter(this);

        $(this).removeAttr('name').removeAttr('onchange').change(function(e) {
            $input.prop('disabled', false).val($(this).val());
            this.form.submit();
        });
    });

    $('.property-short .address', $form).each(function() {
        $(this).css('margin-top', (($(this).parent().height() - $(this).height()) / 2) - 10);
    });


    $form.on('click', '.tick-checkbox-and-group-action', function() {
        $('.ad-checkbox', $form).prop('checked', false);
        $(this).closest('.property-short').find('.ad-checkbox').prop('checked', true).change();
        $('.group-actions', $form).find($(this).data('group-button')).click();
    });


    // клик по кнопкой группового действия, при которых может потребоваться спросить причину деактивации
    $form.on('click', '.group-actions button.check_deactivation_reason', function(e, params) {
        // пропускаем, если вызов был из этого же метода
        if ('skip_check_deactivation_reason' in (params || {})) {return;}

        var ids = $('.properties-list .need_reason_for_deactivation .checkbox-in-list:checked').map(function () { return $(this).val(); }).get();
        if (ids.length) {
            $("#deactivate-reason-modal .hide_for_action_sold").toggle(e.target.value != 'sold');
            $("#deactivate-reason-modal #confirm_action").data('sender', $(e.target));
            $('#deactivate-reason-modal').modal('show');

            // для остановки других событий,  например по .confirm-delete
            e.stopImmediatePropagation();
            e.preventDefault();
        }
    });

    // клик по ссылке "Снять с публикации" продолжит выплоняемое действие (деактивация/удаление)
    $("#deactivate-reason-modal #confirm_action").click(function(e) {
        $('#deactivate-reason-modal').modal('hide');
        $(this).data('sender').trigger('click', {skip_check_deactivation_reason:true});
    });
}

// смена риелтора
function initAdOwnerChange() {
    if (typeof $chooser != "undefined") {
        $('.owner .choose-realtor').click(function(e) {
            $('.realtor-snippet', $chooser).removeClass('active')
                .filter('[data-user="' + $(this).data('value') + '"]').addClass('active');
            $(this).parent().append($chooser);
            $(this).dropdown();
            e.preventDefault();
        });
        $('.owner .remove-realtor').click(function(e) {
            var $link = $(this);
            $.post('.', {ad:$link.data('pk'), action:'change_owner', user:$link.data('value')}).done(function( data ) {
                $link.closest('.owner').addClass('mine').find('.realtor-name').data('value', $link.data('value'));
            });
            e.preventDefault();
        });
        $chooser.on("click", '.realtor-snippet', function() {
            var ad_id = $chooser.prev().data('pk');
            var $link = $(this);

            $.post('.', {ad:ad_id, action:'change_owner', user:$link.data('user')}).done(function( data ) {
                $chooser.closest('.owner').find('.realtor-name')
                    .text($link.find('.name').text())
                    .data('value', $link.data('user'));
                $chooser.closest('.owner').removeClass('mine');
            });
        });
    }
}

function highlight(highlight_selector) {
    var $target = $(highlight_selector).addClass('highlight');
    var $overlay = $('<div class="modal-backdrop"></div>').appendTo('body');
    var timer = setTimeout(hide, 4000);
    $(document).bind('keydown click', hide).find('body');

    function hide(event) {
        clearTimeout(timer);
        $(document).unbind('keydown click', hide);
        $overlay.fadeOut(300, function() {$overlay.remove();$target.removeClass('highlight');});
    }
}

function initCityTypeahead() {
    $('input.city-typeahead-widget-1').each(function () {
        var $input = $(this);
        var $hiddenInput = $input.parents('form').find('input.city-typeahead-widget-0');
        var url = $input.attr('data-url');

        $input.typeahead({
            minLength: 2,
            source: function(query, process) {
                return $.get(url, {q: query}, function (data) {return process(data);});
            }
        });
        $input.change(function() {
            var current = $input.typeahead('getActive');
            if (current) {
                if (current.name == $input.val()) {
                    $hiddenInput.val(current.id);
                } else {
                    if ($input.val()) {
                        $input.val('');
                    }
                    $hiddenInput.val('');
                }
            }
        });
    });
}

function initHiddenToggle() {
    $('.hidden-toggle-link').click(function(event) {
        $($(this).attr('href')).find('.hidden-toggle').toggleClass('hidden');
        event.preventDefault();
    });
}

function initMainmenuDropdowns() {
    var timerId = false;

    function dropdownShow(e) {
        if ($(window).width() < 1200) {return;} // на мобильных дропдаун выводится по клику
        if (timerId) {clearTimeout(timerId);timerId = false;}
        var $active = $(e.currentTarget).siblings('.dropdown').find('> ul:visible');
        var $target = $(e.currentTarget).addClass('open').find('>ul');
        if ($active.length) {
            $active.stop(true, true).hide().parent().removeClass('open');
            $target.show();
        } else {
            $target.slideDown();
        }
    }
    function dropdownHide(e) {
        if ($(window).width() < 1200) {return;} // на мобильных дропдаун выводится по клику
        $(e.currentTarget).find('>ul').stop(true).slideUp(function() {
            $(this).parent().removeClass('open');
        });
    }

    function dropdownToggle(e) {
        if ($(window).width() >= 1200) {return;} // на десктопах дропдаун выводится по ховеру
        var $menu = $(e.currentTarget).parent();
        if ($menu.hasClass('open')) {
            $menu.removeClass('open').find('> ul').hide();
        } else {
            $menu.addClass('open').find('> ul').show();
        }
        e.preventDefault();
    }

    $('.l-mainmenu li.dropdown, .l-submenu li.dropdown').hover(dropdownShow, function(e) {timerId = setTimeout(dropdownHide, 200, e);})
        .find('> a').click(dropdownToggle);

    function hideMainmenuAsSidebar(e) {
        if (!$(e.target).closest('.navbar-nav').length) { $('#mesto-navbar-collapse').collapse('hide'); }
    }
    $('#mesto-navbar-collapse').on('shown.bs.collapse', function () {
        $(document).on('click ', hideMainmenuAsSidebar);
    }).on('hide.bs.collapse', function () {
        $(document).off('click ', hideMainmenuAsSidebar);
    });
}

function initScrollToTop() {
    if ($('.scroll-to-top:visible').length) {
        $(window).scroll(function() {
            $('.scroll-to-top').toggleClass('hidden', $(this).scrollTop() < 100);
        }).scroll();
    }
}

function initProfessionalsHiddenContacts() {
    $('body').on('click', '.professional-hidden-contacts .show-contacts', function(e) {
        $(this).unbind('click');
        var $form = $(this).parents('form');
        $form.find('.show-contacts-button').addClass('loading');

        $.ajax({
            type: "POST",
            url:  $form.attr('action'),
            data: $form.serialize()
        }).done(function (data) {
            $form.find('.phones span').html(data.phones);
            $form.find('.show-contacts').remove();
        });
        
        yaCounter19774096.reachGoal('contacts');
    });
}

function initProfessionalsPreviewsHeights() {
    var context = $('.professional-preview');
    $.each(['.name', '.address', '.contacts'], function(index, selector) {
        $(selector, context).equalHeights();
    });
}


$(function () {
    $('.banner_wrapper_bottom').click(function () {
        $('.banner_wrapper_bottom').hide();
        var domain = '.' + window.location.hostname.split('.').slice(-2).join('.');
        $.cookie("hide_cat_fish_banner", true, { path: '/', domain: domain }); 
    });

});
