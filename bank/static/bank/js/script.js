$(function(){
//    Добавление CSRF-токена к ajax-запросу
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
            (url == sr_origin || url.slice(0, sr_origin.length + 1) == sr_origin + '/') ||
            !(/^(\/\/|http:|https:).*/.test(url));
    }

    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!csrfSafeMethod(settings.type) && sameOrigin(settings.url)) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        }
    });

    if ('colorbox' in $.fn) {
        InstallGallery();
        IntsallProfile();
    }

    if ($('#login-popup .errorlist').length) $('#login-popup').show();
    
    InstallShowPanel('#subdomain-list');
    InstallShowPanel('#login-popup');
    InstallNeedAuth();
    InstallDeleteConfirm();
    InstallStarred();
    InstallHomepageSearch();
    InstallPropertyForm();
    InstallMiniHotelForm();
    InstallCalendars();
    InstallRegistrationAdPanel();
    InstallRegistrationForm();

    //if ('reserved_json' in window)
    //    InstallReadOnlyCalendars(reserved_json);
        
    if(!Modernizr.input.placeholder){
        $("input").each(
            function(){
                if($(this).val()=="" && $(this).attr("placeholder")!=""){
                    $(this).val($(this).attr("placeholder"));
                    $(this).focus(function(){
                        if($(this).val()==$(this).attr("placeholder")) $(this).val("");
                    });
                    $(this).blur(function(){
                        if($(this).val()=="") $(this).val($(this).attr("placeholder"));
                    });
                }
        });
    }
    
    if($('#fb_floatingbox').length > 0) {
        
        $(".side_social_icon_cont").hover(
            function() { 
                $(this).stop();
                $(this).parent().nextAll('div.side_social_icon').hide();
                $(this).parent().animate({right: "-5"}, "medium"); 
            },
            function() { 
                //
            }, 500);
        
        $(".side_social_icon").hover(
            function() { 
                //
            }, function() { 
                $(this).animate({right: "-265"}, "medium");
                $('div.side_social_icon').show();
            }, 500);
        
        window.setTimeout(function() { 
            $('#twitter-widget-0').attr('width','260'); 
            //VK.Widgets.Group("vk_groups", {mode: 0, width: "260", height: "270"}, 22073049);
        }, 2000);
    }
    
    if($('.field-property_commercial_type').length > 0 && $('#id_property_type').length > 0) {
        
        $("#id_property_type").change(
            function() {
                if($(this).val() == 'commercial') {
                    $('.field-property_commercial_type').show();
                } else {
                    $('#id_property_commercial_type').get(0).selectedIndex = 0;
                    $('.field-property_commercial_type').hide();
                }
            }
        );
        $("#id_property_type").change();
        
        $('.errorlist').parent().show();
    }
    
});

function InstallDeleteConfirm() {
    $('.confirm-delete').click(function() {
        return confirm("Действительно удалить?");
    });
}

function InstallGallery() {
    $.fn.colorbox.settings.opacity = 0.6;
    $('.register-popup').colorbox({iframe:true, overlayClose:false, width:"490", height:"250", scrolling:false, open:false});
    $('.fancybox').colorbox({rel:'gallery', transition:"none", width:"85%", height:"85%", photo:true});
    $('.view-graph-popup').colorbox({transition:"none", iframe:true,  width:"610", height:"270", scrolling:false});
    $('.payment-popup').colorbox({iframe:true, overlayClose:false, width:"490", height:"420", scrolling:false});
    $('.need-paid-placement').colorbox({iframe:true, overlayClose:false, width:"490", height:"420", scrolling:false, open:true, onLoad:function(){$('#cboxClose').hide();}});
    $('.invoice-payment-popup').colorbox({iframe:true, overlayClose:false, width:"450", height:"220", scrolling:false, open:false});
    $('.calculator-popup').colorbox({iframe:true, overlayClose:false, width:"750", height:"350", scrolling:false, open:false});
    $('.crm-payment-popup').colorbox({iframe:true, overlayClose:false, width:"450", height:"220", scrolling:false, open:false});
}

function InstallHomepageSearch() {
    var $homesearch = $('#homesearch'),
        $items = $('.homesearch__type__item', $homesearch),
        $subdomain = $('.homesearch__subdomain', $homesearch);
        
    function generateActionURL($form) {
        $form.attr('action',
            'http://' +
            ($form.data('subdomain') ? $form.data('subdomain') + '.' : '') +
            $form.data('domain') +
            '/'+ $form.data('type') + '/result.html'
        );
    }
    $items.click(function() {
        var $this = $(this);
        var tab = $this.data('tab');

        $this.addClass('homesearch__type__item-active').siblings().removeClass('homesearch__type__item-active');
        $('.tab-pane', $homesearch).removeClass('active').filter($(this).data('tab')).addClass('active');

        if (tab == '#hs-properties') {
            $form = $('form', $(tab));
            $form.data('type', $this.data('type'));
            generateActionURL($form);
        }
    });
    $subdomain.change(function() {
        var $form = $(this).parents('form');
        $form.data('subdomain', $(this).val());
        generateActionURL($form);
    });
    $('.property_type', $homesearch).change(function() {
        var $form = $(this).parents('form');
        $form.data('type', $(this).val());
        generateActionURL($form);
    });
}

/**
  * Выражаем благодарность разработчикам сайта natarelochke.ru за функцию InstallCitiesList
  */
function InstallShowPanel(prefix) {
	var $target = $(prefix);
	var target_timer = false;
    var event_name = 'mousedown.' + prefix.replace(/[#\.\-_]/g, '');

	$target
		.bind('show', function(e, data) {
			if (target_timer) {
				clearTimeout(target_timer);
				target_timer = false;
			}
			if ($.browser.msie && $.browser.version < 9) {
				$target.show();
			} else {
				$target.stop(true, true).fadeIn(100);
			}
			$(document).bind(event_name, function(e) {
				if ( ! $(e.target).parents().andSelf().filter($target).length ){
					$target.triggerHandler('hide');
				}
			})
		})
		.bind('hide', function(e, data) {
			if (target_timer) {
				clearTimeout(target_timer);
				target_timer = false;
			}
			if ($.browser.msie && $.browser.version < 9) {
				$target.hide();
			} else {
				$target.stop(true, true).fadeOut(300);
			}
			$(document).unbind(event_name);
		})
		.mouseenter(function(){
			if (target_timer) {
				clearTimeout(target_timer);
				target_timer = false;
			}
		})
		.mouseleave(function(){
			target_timer = setTimeout(function(){
				target_timer = false;
				$target.triggerHandler('hide');
			}, 5000);
		});
	
	$(prefix + '-show').click(function(e) {
		$target.triggerHandler('show', {'source':this});
		//e.preventDefault();
        return false;
	});
	
	$(prefix + '-hide').click(function(e) {
		$target.triggerHandler('hide', {'source':this});
		//e.preventDefault();
        return false;
	});
}

function InstallNeedAuth() {
    var $link = $('.check-auth');
    var $login_popup = $('#login-popup');
    if ($link.length && $login_popup.length) {
        $link.addClass('content-login-popup-show');
        $login_popup = $login_popup.clone().insertAfter($link);
        $login_popup.addClass('content-login-popup').find('.login-popup-hide').addClass('content-login-popup-hide');
        InstallShowPanel('.content-login-popup');
    }
}

function InstallStarred() {
    var $star = $('#save-property'),
        $star_text = $('span', $star);
    
    $star.click(function() {
        var $this = $(this),
            url = $this.attr('href');
            
        $star_text.html('&nbsp; обработка&nbsp;');
        $.ajax({
            url: url,
            crossDomain: true,
            xhrFields: { withCredentials: true },
            data:{"ajax":"1"}
        }).done(function(data) {
            $star.toggleClass('active', data == 'add');
            $star_text.text(data == 'add' ? 'в избранном' : 'в избранное');
        }).fail(function() {
            $star_text.text('ошибка :(');
        });
        return false;
    });
}


function InstallPropertyForm() {
    var $form = $('form.property-form');
    if($form.length == 0) return;
    
    var $container = $('#id_currency, #id_euro_currency', $form).parents('.field');
    $('#id_currency', $form).insertAfter('#id_price');
    $('#id_euro_currency', $form).insertAfter('#id_euro_price');
    $container.remove();
    
    $('select#id_deal_type').change(function() {
        var deal_type = $(this).val();
        var daily = (deal_type == 'rent_daily');
        $('div.field-reserved, div.field-euro_price').toggle(daily);
        $('div.field-guests_limit').toggle(daily);
        $('div.field-expire').toggle(!daily);
        $('div.field-facilities').toggle(!$.inArray(deal_type, ['rent','rent_daily']));
    }).change();

    $('.field-tos', $form).insertBefore($('.field-submit', $form));

    //$address_block = $('#id_address').parents('p').hide();
    $('#id_city2address', $form).change(function() {
        var city_name = $(this).find('option:selected').text(),
            $target = $('#id_address'),
            is_full = ($target.val().length > 30);
            
        if (!is_full) {
            if ($(this).val()) {
                $target.val('Украина, ' + city_name + ', ' );
            } else {
                //alert('other city');
            }
            //$address_block.slideDown();
        }
    });    
    
}

function InstallMiniHotelForm() {
    var $form = $('form.minihotel-form');
    if($form.length == 0) return;
    
    var $container = $('#id_currency, #id_euro_currency', $form).parents('.field');
    $('#id_currency', $form).insertAfter('#id_price');
    $('#id_euro_currency', $form).insertAfter('#id_euro_price');
    $container.remove();
}

function InstallPropertyPage() {
    var $propertyDetail = $('#property-detail, #property-detail-small');
    $('body').on('click', ".show-contacts", function(e) {
        //$propertyDetail.find(".show-contacts").unbind('click');
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
            $propertyDetail.find('.show-contacts').remove();
        });
    });

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
            });
        }
    }

    $('#tabs').tabs({ 
        activate: function(event, ui) {
            checkOSM($(ui.newPanel).find('.show-osm-map'));
            $(ui.newTab).addClass('active');
            $(ui.oldTab).removeClass('active');
        },
        create: function(event, ui) {
            checkOSM($(ui.panel).find('.show-osm-map'));
        }
    });

    $.datepicker.regional.ru={closeText:"Закрыть",prevText:"&#x3C;Пред",nextText:"След&#x3E;",currentText:"Сегодня",monthNames:["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"],monthNamesShort:["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"],dayNames:["воскресенье","понедельник","вторник","среда","четверг","пятница","суббота"],dayNamesShort:["вск","пнд","втр","срд","чтв","птн","сбт"],dayNamesMin:["Вс","Пн","Вт","Ср","Чт","Пт","Сб"],weekHeader:"Нед",dateFormat:"dd.mm.yy",firstDay:1,isRTL:!1,showMonthAfterYear:!1,yearSuffix:""},$.datepicker.setDefaults($.datepicker.regional.ru);
    $.datepicker.dateFormat = 'dd.mm.yy';
    
    function getDifferentDay(date, day) {
        var diff_day = new Date(date.getTime() + 86400000 * day);
        return $.datepicker.formatDate($.datepicker.dateFormat, diff_day);
    }
    
    $( ".datepicker" ).datepicker({
        firstDay: 1,
        minDate: 0,
        numberOfMonths: 2,
        showOtherMonths: true,
        //selectOtherMonths: true,
        beforeShowDay: function(date) {
            var date_str = date.getFullYear() + '-' + zeroPad(date.getMonth()+1) + '-' + zeroPad(date.getDate());
            if($.inArray(date_str, reserved_json) != -1) {
                return [false, 'ui-state-block ui-state-busy', 'занято'];
            }
            if (calend_from && calend_from.getTime() == date.getTime())
                return [true, 'ui-state-block ui-state-selected', 'въезд'];
            if (calend_to && calend_to.getTime() == date.getTime())
                return [true, 'ui-state-block ui-state-selected', 'выезд'];
            if (calend_from && calend_to && date > calend_from && date < calend_to)
                return [true, 'ui-state-block ui-state-between', false];
            return [true];
        },
        onClose: function( selectedDate ) {
            if (selectedDate && this.name == 'from') {
                calend_from = parseDate(selectedDate);
                $( "#calend-to" ).datepicker( "option", "minDate", getDifferentDay(calend_from, 1) );
            }
            if (selectedDate && this.name == 'to') {
                calend_to = parseDate(selectedDate);
                $( "#calend-from" ).datepicker( "option", "maxDate", getDifferentDay(calend_to, -1) );
            }
            if (calend_from && calend_to) {
                days = (calend_to - calend_from)/(1000*60*60*24);
                sum = days * parseInt($('.price-block .value').data('price'));
                $('.price-block .value').text(Humanize.intword(sum));
                $('.price-block .period').text(days + ' ' + declOfNum(days, ['сутки','суток','суток']));
                $.each(reserved_json, function(key, value) {
                    var date = new Date(value.replace(/(\d+)-(\d+)-(\d+)/, '$2/$3/$1'));
                    if (date > calend_from && date < calend_to) {
                        $('.search-result .error').removeClass('hidden').siblings().addClass('hidden');
                        return false;
                    } 
                    $('.search-result .ok').removeClass('hidden').siblings().addClass('hidden');
                });
            }
        }
    }, $.datepicker.regional['ru']);
}

// добавление ведущего нуля в число (для дней и месяцев в датах)
function zeroPad(num) {
    var s = num+"";
    while (s.length < 2) s = "0" + s;
    return s;
}

// парсит дату формата dd.mm.yyyy
function parseDate(str) { 
    var dateParts = str.split(".");
    return new Date(dateParts[2], (dateParts[1] - 1), dateParts[0]);
}
// склонение существительных
function declOfNum(number, titles){  
    cases = [2, 0, 1, 1, 1, 2];  
    return titles[ (number%100>4 && number%100<20)? 2 : cases[(number%10<5)?number%10:5] ];  
}

function InstallCalendars() {
    if($.datepicker !== undefined) {
        $.datepicker.regional.ru={closeText:"Закрыть",prevText:"&#x3C;Пред",nextText:"След&#x3E;",currentText:"Сегодня",monthNames:["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"],monthNamesShort:["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"],dayNames:["воскресенье","понедельник","вторник","среда","четверг","пятница","суббота"],dayNamesShort:["вск","пнд","втр","срд","чтв","птн","сбт"],dayNamesMin:["Вс","Пн","Вт","Ср","Чт","Пт","Сб"],weekHeader:"Нед",dateFormat:"dd.mm.yy",firstDay:1,isRTL:!1,showMonthAfterYear:!1,yearSuffix:""},$.datepicker.setDefaults($.datepicker.regional.ru);
        $.datepicker.dateFormat = 'dd.mm.yy';
        $( ".datepicker" ).datepicker({
            firstDay: 1,
            minDate: 0,
            numberOfMonths: 2,
            showOtherMonths: false,
            selectOtherMonths: false,
            onClose: function( selectedDate ) {
                if (selectedDate && this.name == 'free_from') {
                    $('#id_free_to').focus();
                }
            }
        }, $.datepicker.regional['ru']);
    }    
}

function InstallRegistrationAdPanel() {
    function UpdateRegistrationAdPanel() {
        var $target = $(".ad-panel-dynamic:visible").hide().next(".ad-panel-dynamic");
        if (!$target.length) $target = $(".ad-panel-dynamic").first(); 
        $target.show()
    }
    if($(".ad-panel-dynamic").length) {
        window.setInterval(UpdateRegistrationAdPanel, 6000);
    }
}

function InstallRegistrationForm() {
    $("form.agency-form #id_usertype").change(function() {
        var $working_hours = $("form.agency-form p.field-working_hours");
        if($("form.agency-form #id_usertype>option:selected").val() == '3') $working_hours.hide();
        else $working_hours.show();
    });
}

function IntsallProfile() {
    // checkedProperties and baseUpdateUrl is defined in template
    var $context = $('.my-properties .property-list');

    $.fn.colorbox.settings.opacity = 0.6;
    $('.update-all', $context).colorbox({iframe:true, width:440, height:180, overlayClose:false, scrolling:false});

    function updateColorbox() {
        checkedProperties = [];
        $('input.checkbox:checked', $context).each(
            function(index, obj) {
                checkedProperties.push(obj.name.split('-')[1]);
            }
        );

        var $colorbox = $('.update-checked', $context);
        $colorbox.unbind('click');
        if(checkedProperties.length > 0) {
            var href = baseUpdateUrl + '&id=' + checkedProperties.join(',');
            $colorbox.colorbox({href:href, iframe:true, width:440, height:180, overlayClose:false, scrolling:false});
        } else {
            $colorbox.removeAttr('href').removeClass('colorbox cboxElement').click(
                function(eventObj) {alert('Отметьте галочками одно или несколько объявлений');}
            );
        }
    }

    $('input.checkbox-all', $context).change(
        function () {
            if(this.checked) {
                $('input.checkbox', $context).attr('checked', 'checked');
            } else {
                $('input.checkbox', $context).removeAttr('checked');
            }
            updateColorbox();
        }
    );
    $('input.checkbox', $context).change(updateColorbox);
    updateColorbox();

    $('.property-form .popup-duplicate').colorbox({iframe:true, width:400, height:230, overlayClose:false, scrolling:false, open:true});
}

