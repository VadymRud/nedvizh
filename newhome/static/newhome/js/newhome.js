var forbidden_fields_name = ['csrfmiddlewaretoken'];
var storage = localStorage;
var flatTimer = null;

function addRoom(layout) {
    var lastNum = layout.find('.room-row:not(.hidden) .image-num').last().val();
    var newRow = layout.find('.room-row.hidden').eq(0);

    newRow.removeClass('hidden').find('.image-num').val(parseInt(lastNum ? lastNum:0) + 1);
    newRow.appendTo(layout.find('.rooms-content > .row').eq(0));
    return false;
}

function availableFlatsProcess() {
    var $available_flats = $('#available-flats');
    $available_flats.on("click", ".toggleHidden", function(e) {
        $(this).closest('table').find('.toggleHidden').removeClass('toggleHidden').toggleClass('hidden');
        e.stopImmediatePropagation();
    }).on("click", "tr.floor", function() {
        var $form = $(this).closest('form');
        $form.find('input[name=floor]').val($(this).data('floor'));
        $form.submit();
    });
    $available_flats.find('select[name=section]').change(function() {
        var section_id = parseInt($available_flats.find('select[name=section]').val());
        $('tr.floor').addClass('hidden');

        if (section_id && section_id > 0) {
            $('tr.floor[data-section=' + section_id + ']').removeClass('hidden');
            if ($('tr.floor[data-section=' + section_id + ']').length == 0) {
                $('tr.floor[data-section=0]').eq(0).removeClass('hidden');
            } else {
                $('tr.floor[data-section=0]').addClass('hidden');
            }
        } else {
            $('tr.floor:not([data-section=0])').removeClass('hidden');
            $('tr.floor:gt(5)').not('.hidden').addClass('hidden');
        }
    });
}

function changeLocation(xpath) {
    $(xpath).change(function() {
        window.location = $(this).val();
    })
}

function cleanLocalStorage() {
    $(".newhomes-object form").serializeArray().forEach(function(item, position, arr) {
        if (forbidden_fields_name.indexOf(item.name) == -1) {
            storage.removeItem(item.name);

            for (var imageKey=0; imageKey <= 20; imageKey++)
                storage.removeItem('image' + imageKey);
        }
    });
}

function profileNewhomeMyBuildingsInit() {
    $('.my-building').on('change', '.localnumber', function () {
        fieldChanged = true;
    }).on('blur', '.localnumber', function () {
        if (fieldChanged) {
            var $cb = $(this).parents('.row').find('input[type=checkbox]').not(':checked').eq(0);
            $cb.prop('checked', true);
            showActionMenu();
        }
    });

    $('.my-building input[type=email]').change(function () {
        fieldChanged = true;
    }).blur(function () {
        if (fieldChanged) {
            var $cb = $(this).parents('.row').find('input[type=checkbox]').not(':checked').eq(0);
            $cb.prop('checked', true);
            showActionMenu();
        }
    });
}

function profileNewhomeFlatsInit() {
    $('#flats-edit-popup').on('show.bs.modal', function (event) {
        var flat = $(event.relatedTarget);
        var modal_form = flat.data('layout');
        var modal = $(this);
        modal.find('.modal-body, .modal-header').addClass('hidden');
        modal.find('.modal-body.' + modal_form + ', .modal-header.' + modal_form).removeClass('hidden');
    });

    $('.flat-name input').each(function() {
        if ($(this).val().indexOf('Не указано') != -1)
            $(this).val('');
    });

    $('.flat-remove').click(function(e) {
        if (!e.isDefaultPrevented()) {
            window.location = $(this).data('url');
        }
        return false;
    });

    $('.room-name').each(function () {
        $(this).bind({
            focus: function () {
                clearTimeout(flatTimer);
                $(this).parents('.modal-content').find('.available-layout-options, .available-layout-options + .fog')
                    .removeClass('hidden').end().find('.available-layout-options a').data('target', '#' + $(this).attr('id'));

            },
            blur: function () {
                var hideOptions = function(e) {
                    e.parents('.modal-content').find('.available-layout-options, .available-layout-options + .fog')
                        .addClass('hidden');
                };
                flatTimer = setTimeout(hideOptions.bind(null, $(this)), 150);
            }
        })
    });

    $('body').on('click', '.available-layout-options a', function () {
        $($(this).data('target')).val($(this).data('name')).focus();
        return false
    });

    changeLocation('#copy-changer');
}

function profileNewhomeFloorsInit() {
    $('.floor-remove').click(function(e) {
        if (!e.isDefaultPrevented()) {
            window.location = $(this).data('url');
        }
        return false;
    });

    $('#floor-edit-popup').on('show.bs.modal', function (event) {
        var floor = $(event.relatedTarget);
        var modal_form = floor.data('floor');
        var modal = $(this);
        var $addMapInput = $('#add-map-coords');
        var $availableLayouts = $('#available-layouts');
        var $priceInput = $('#price');
        var $priceCurrencyInput = $('#price-currency');
        var layout_coordinates = null;
        modal.find('.modal-body, .modal-header').addClass('hidden');
        modal.find('.modal-body.' + modal_form + ', .modal-header.' + modal_form).removeClass('hidden');
        addPen = false;
        eraserPen = false;
        modal.find('.modal-body.' + modal_form + ' .active').removeClass('active');

        var $mapsterImg = $('.modal-body.' + modal_form + ' .img-responsive');
        if ($mapsterImg.length == 1) {
            mapsters[modal_form] = [];
            mapsters[modal_form]['image'] = $mapsterImg;
            mapsters[modal_form]['mapster'] = $mapsterImg.mapster(mapsterOptions);

            $('#floor-edit-popup').on('click', '.modal-body.' + modal_form + ' area', function (e) {
                var layoutId = $(this).data('layoutId');
                var coords = $(this).attr('coords');
                var price = $(this).data('price');
                var priceCurrency = $(this).data('priceCurrency');
                var $thisArea = $(this);
                var $form = mapsters[modal_form]['image'].parents('form');

                if (eraserPen) {
                    // Удаляем выделенную область и связанные данные
                    layout_coordinates = JSON.parse($form.find('textarea').val());
                    layout_coordinates.layouts_coordinates = layout_coordinates.layouts_coordinates.filter(
                        function(obj) {
                            return obj.coordinates != coords
                        });
                    $form.find('textarea').val(JSON.stringify(layout_coordinates));

                    $(this).remove();
                    mapsters[modal_form]['mapster'].mapster('unbind').mapster(mapsterOptions);
                    $('.modal-body.' + modal_form + ' area').mapster('set', true);
                } else {
                    var parentOffset = $(this).parents('.modal-content').offset();
                    $priceInput.val(parseInt(price) || '');
                    $priceCurrencyInput.selectpicker('val', priceCurrency);
                    $availableLayouts.css({
                        left: (e.pageX - parentOffset.left),
                        top: (e.pageY - parentOffset.top)
                    }).find('.layout-wrap').each(function () {

                        if ($(this).data('layoutId') == layoutId) {
                            $(this).addClass('bordered');
                        } else {
                            $(this).removeClass('bordered');
                        }

                        // Обновляю/добавляю даные по выбранному выделению
                        $(this).unbind('click').click(function () {
                            $availableLayouts.addClass('hidden');
                            layoutId = $(this).data('layoutId');

                            $thisArea.data('layoutId', layoutId);
                            $thisArea.data('price', $priceInput.val().replace(' ', ''));
                            $thisArea.data('priceCurrency', $priceCurrencyInput.val());

                            layout_coordinates = JSON.parse($form.find('textarea').val());
                            layout_coordinates.layouts_coordinates = layout_coordinates.layouts_coordinates.filter(
                                function(obj) {
                                    return obj.coordinates != coords
                                });
                            layout_coordinates.layouts_coordinates.push({
                                layout_id: layoutId,
                                coordinates: $thisArea.attr('coords'),
                                price: parseInt($priceInput.val().replace(' ', '')),
                                currency: $priceCurrencyInput.val()
                            });
                            $form.find('textarea').val(JSON.stringify(layout_coordinates));

                            return false;
                        });
                    }).end().removeClass('hidden');
                }
                return false;
            }).on('click', '.modal-body.' + modal_form + ' a.add-pen', function() {
                $(this).parent().toggleClass('active', '');
                addPen = !addPen;
                eraserPen = false;
                $(this).parent().next().removeClass('active');
                if (addPen) {
                    $addMapInput.canvasAreaDraw({
                        imageObj: mapsters[modal_form]['image']
                    });
                } else if ($addMapInput.val()) {
                    // Добавляем новую область на карту
                    $('<area href="" data-selected="true" shape="poly" coords="' + $addMapInput.val() + '" data-price="0" data-price-currency="UAH">')
                            .appendTo($(mapsters[modal_form]['image'].attr('usemap')));
                    mapsters[modal_form]['mapster'].mapster('unbind').mapster(mapsterOptions);
                    $('.modal-body.' + modal_form + ' area').mapster('set', true);

                    $addMapInput.val('');
                    $('#draw-canvas').remove();
                }
                return false;
            }).on('click', '.modal-body.' + modal_form + ' a.eraser-pen', function() {
                $(this).parent().toggleClass('active', '');
                eraserPen = !eraserPen;
                addPen = false;
                $(this).parent().prev().removeClass('active');

                // Очищаем что нарисовали
                if (eraserPen) {
                    $('#draw-canvas').remove();
                    $addMapInput.val('');
                }
                $('.modal-body.' + modal_form + ' area').mapster('set', true);
                return false;
            });
            $('.modal-body.' + modal_form + ' area').mapster('set', true);
        }
    });
}

function profileNewhomeObjectInit() {
    var $form = $(".newhomes-object form");
    var fields = $form.serializeArray();
    fields.forEach(function(item, position, arr) {
        if (forbidden_fields_name.indexOf(item.name) == -1) {
            // Вешаем событие на сохранение заполняемых данных
            $form.find('input[name=' + item.name + '], textarea[name=' + item.name + ']').blur(function() {
                storage.setItem(item.name, $(this).val());
            }).end().find('select[name=' + item.name + ']').change(function() {
                storage.setItem(item.name, $(this).val());
            });

            // Смотрим, а нет ли ничего уже сохраненного? и восстанавливаем :)
            if (storage.getItem(item.name) && storage.getItem(item.name).length) {
                $form.find('[name=' + item.name + ']').val(storage.getItem(item.name));
            }
        }
    });

    // Очистка данных
    $('.clean-local-storage a').click(function () {
        cleanLocalStorage();
        window.location = window.location;
        return false;
    });
}

function profileNewhomeSection() {
    $('.btn-add-section').click(function() {
        var $positionField = $('#id_positions');
        var sectionPosition = Math.max.apply(null, $positionField.val().split(',').map(Number)) + 1;
        $('<li>секция ' + sectionPosition + ' <span class="glyphicon glyphicon-minus-sign"></span></li>')
            .data('sectionPosition', sectionPosition).appendTo($(this).next());
        $positionField.val($positionField.val() + ',' + sectionPosition);

        return false;
    });

    $('.building').on('click', '.glyphicon-minus-sign', function() {
        var $ul = $(this).closest('ul');
        var availableSections = [];
        $(this).closest('li').remove();
        $ul.find('li').each(function() {
            availableSections.push($(this).data('sectionPosition'));
        });
        $('#id_positions').val(availableSections.join(','));
        return false;
    });
}