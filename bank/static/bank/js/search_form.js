// вынесено в отдельный файл, т.к. функции требует запуска перед окончанием загрузки страницы, чтобы избежать морганий при замене элементов форм

function roundToBig(num, up) {
    mult = Math.pow(10, String(num).length-2);
    
    if (up)
        return Math.ceil(num/mult) * mult;
    else
        return Math.floor(num/mult) * mult;
}

function InstallPropertySearchForm() {
    $('.property-search select').ufd(); 
    $('.search-switcher-link').click(function() {
        $('.search-switcher-content').toggleClass('hidden');
    });
    $('select#id_added_days, select#id_sort').change(function() {
        $(this).parents('form').find('input:submit').click();
    });
    if (!$.browser.msie ) {
        $('#id_with_image').wrap("<span class='btn btn-mini btn-checkbox'/>").before("<i class='icon-ok icon-white'/>");
        $('.checkbox-inline label').addClass('btn btn-mini btn-checkbox');
        $('.btn-checkbox input').change(function() {
            $(this).parent().toggleClass('btn-active', $(this).is(':checked'));
        }).change();
        InstallPriceSlider();
    }    
}
function InstallPropertySearchOnMapForm() {
    if (!$.browser.msie ) {
        $('#id_with_image').wrap("<span class='btn btn-mini btn-checkbox'/>").before("<i class='icon-ok icon-white'/>");
        $('.checkbox-inline label').addClass('btn btn-mini btn-checkbox');
        $('.btn-checkbox input').change(function() {
            $(this).parent().toggleClass('btn-active', $(this).is(':checked'));
        }).change();
        InstallPriceSlider();
    }

    ymaps.ready(function () {
        var map, clusterer, timer, obj_count = objects.length;

        map = new ymaps.Map("yandex_maps_api", {center: center_coords, zoom: 12, type: "yandex#map"}, {maxZoom:14});
        map.controls.add("zoomControl").add("mapTools").add(new ymaps.control.TypeSelector(["yandex#map", "yandex#satellite", "yandex#hybrid", "yandex#publicMap"]));

        function addPoints() {
            clusterer = new ymaps.Clusterer({synchAdd: true});
            $.each(objects, function(key, obj) {
                
                balloonContent_str = "<p><a href='" + obj.link + "'>" + obj.name + "</a></p>Адрес: "+obj.address+"<br/>Цена: " + obj.price+"<br />"+Truncate(obj.description,200,'...');
                if(typeof(obj.image) != 'undefined') {
                    balloonContent_str += "<br /><br /><a href='" + obj.link + "'><table><tr>";
                    balloonContent_str += "<img style='margin: 2px;' src='"+obj.image+"'></td>"
                    balloonContent_str += '</a>';
                }
                
                var placemark = new ymaps.Placemark(
                    obj.coords, {
                        clusterCaption: obj.name,
                        balloonContent: balloonContent_str
                    }, {
                        preset: 'twirl#houseIcon'
                    }
                );
                obj.placemark = placemark;
                obj.visible = true;
                clusterer.add(placemark);
            });
            map.geoObjects.add(clusterer);
            $('.result-count').removeClass('hidden').find('b').text(obj_count);
        }

        function updatePoints() {
            var price_from = ($('#id_price_from').val()),
                price_to = $('#id_price_to').val(),
                with_images = $('#id_with_image').is(':checked'),
                rooms = $.map($("input[name='rooms']:checked"), function(obj, i) {return $(obj).val()});

            $.each(objects, function(key, obj) {
                var new_status = (!with_images || obj.image)
                    && (!price_from || (price_from <= obj.price_uah))
                    && (!rooms.length || (obj.rooms < 4 ? $.inArray(String(obj.rooms), rooms) > -1 : $.inArray('4+', rooms) > -1 ) )
                    && (!price_to || (price_to >= obj.price_uah));
                if (!new_status && obj.visible) {
                    clusterer.remove(obj.placemark); // hide
                    obj_count--;
                }
                if (new_status && !obj.visible) {
                    clusterer.add(obj.placemark); //show
                    obj_count++;
                }
                obj.visible = new_status;
            });
            clusterer.refresh();
            $('.result-count b').text(obj_count);
        }
        addPoints();
        $('.property-search input').change(function() {
            $('.result-count b').text('подсчет');
            if (timer) clearTimeout(timer);
            timer = setTimeout(updatePoints, 250);
        });

    });
}
function InstallPropertyBankSearchForm() {
    $('.property-search select').ufd(); 
    $('select#id_sort').change(function() {
        $(this).parents('form').find('input:submit').click();
    });
    if (!$.browser.msie ) {
        $('#id_with_image').wrap("<span class='btn btn-mini btn-checkbox'/>").before("<i class='icon-ok icon-white'/>");
        $('.checkbox-inline label').addClass('btn btn-mini btn-checkbox');
        $('.btn-checkbox input').change(function() {
            $(this).parent().toggleClass('btn-active', $(this).is(':checked'));
        }).change();
        InstallPriceSlider();
    }
    $('form.property-search').submit(function() {
        $(this).find('input[name^=ufd],*[value=],input[type=submit]').attr('disabled', 'disabled');
    });
}

function InstallPriceSlider() {
    function expon(val){
        var minv = Math.log(min_price);
        var maxv = Math.log(max_price);
        var scale = (maxv-minv) / (max_price-min_price);
        return Number(Math.exp(minv + scale*(val-min_price))).toFixed(0);

    }
    function logposition(val){
        var minv = Math.log(min_price);
        var maxv = Math.log(max_price);
        var scale = (maxv-minv) / (max_price-min_price);
        return Number((Math.log(val)-minv) / scale + min_price).toFixed(0);
    }

    function setPriceRange(event, ui) {
        var bottom = roundToBig(expon(ui.values[0]), 0);
        var top = roundToBig(expon(ui.values[1]), 1);
        $('#id_price_from').val(bottom).change().prop("disabled", bottom == min_price);
        $('#id_price_to').val(top).change().prop("disabled", top == max_price);
        $('.f-price .label-from').text(Humanize.intword(bottom) + ' грн.');
        $('.f-price .label-to').text(Humanize.intword(top) + ' грн.');
    }

    min_price = roundToBig(min_price);
    max_price = roundToBig(max_price);
    $( "#price-range" ).slider({
        range: true,
        min: min_price,
        max: max_price,
        values: [logposition(price_from ? price_from : min_price), logposition(price_to ? price_to : max_price)],
        slide: setPriceRange
    });
    setPriceRange(false, {values: $( "#price-range" ).slider("values")});
}

function Truncate(str, maxLength, suffix) {
    if(str.length > maxLength)
    {
        str = str.substring(0, maxLength + 1);
        str = str.substring(0, Math.min(str.length, str.lastIndexOf(" ")));
        str = str + suffix;
    }
    return str;
}
