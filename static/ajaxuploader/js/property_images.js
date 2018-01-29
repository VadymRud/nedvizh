(function($) {
    $.fn.toggleDisabled = function(){
        return this.each(function(){
            this.disabled = !this.disabled;
        });
    };
})(jQuery);
$(function(){
    function updateCountOfPhotos() {
        var $photos = $("#div_id_photos");
        var photosCount = $(".image-list li:visible img", $photos).not('.qq-upload-button').length;
        $photos.toggleClass("has-photos", photosCount > 0);
    }

    // прячет иконку с подсказкой о drag`n`drop
    function imageOrderUpdate() {
        // значение поля сортировки начинается с единицы, чтобы отличать фото без сортировки с order=0 или order=1000
        $('.image-list li:visible input.order').each(function(index, obj) {
            obj.value = index + 1;
        });
        updateCountOfPhotos();
    }

    // Обновляет фото в локальном хранилище при добавлении объекта.
    function updatePhotosOnStorage() {
        var location = window.location + '';
        if (location.indexOf('/account/developer/my_buildings/add/') != -1 ) {
            var storage = localStorage;
            for (var imageKey=0; imageKey <= 20; imageKey++)
                storage.removeItem('image' + imageKey);

            var imageCounter = 0;
            $('.attachments-upload li.qq-upload-success:not(.deleted) img').each(function() {
                if (imageCounter > 20)
                    return false;

                storage.setItem('image' + imageCounter, $(this).data('id') + '::' + $(this).attr('src'));
                imageCounter++;
            });
        }
    }

    // Восстанавливает фото из локального хранилища при добавлении объекта.
    function restorePhotosFromStorage() {
        var location = window.location + '';
        if (location.indexOf('/account/developer/my_buildings/add/') != -1 ) {
            var storage = localStorage;

            // Восстанавливаем фотки (ограничение 20 штук), если есть :)
            var $temporaryList = $('<ul></ul>');
            for (var imageKey=0; imageKey <= 20; imageKey++) {
                if (storage.getItem('image' + imageKey)) {
                    var imageString = storage.getItem('image' + imageKey).split('::');
                    $('<li class="pull-left relative qq-upload-success"></li>')
                            .html('<a title="удалить" data-target="parent" class="delete"></a>' +
                                    '<a title="повернуть" data-target="parent" class="rotate"></a>' +
                                    '<img title="" alt="" data-id="' + imageString[0] + '" src="' + imageString[1] + '" class="img-responsive">' +
                                    '<input type="hidden" value="' + imageString[0] + '" name="ajax_add_images">').appendTo($temporaryList);
                }
            }
            $temporaryList.find('li').prependTo('.qq-upload-list');
        }
    }

    if (!(window.navigator.userAgent.indexOf("MSIE ") > 0)) {
        var $uploadQS = $('.attachments-upload');
        if (uploader_mode != 'floors') {
            $uploadQS = $uploadQS.eq(0);
        }
        $uploadQS.each(function() {
            var $elem = $(this);
            var uploader = new qq.FileUploader({
                action: my_ajax_upload,
                element: $elem[0],
                allowedExtensions: ['jpeg', 'jpg', 'gif', 'png'],
                multiple: true,
                disableDefaultDropzone: true,
                onComplete: function(id, fileName, responseJSON) {
                    var item = $(uploader._getItemByFileId(id));
                    if(responseJSON.success && responseJSON.path) {
                        if (uploader_mode == 'flats' || uploader_mode == 'floors') {
                            item.append('<input type="hidden" name="ajax_add_images" value="' + responseJSON.fileName + '"/>');
                            $elem.parents('form').submit();
                        } else {
                            item.html('<a class="delete" data-target="parent" title="' + gettext('удалить') + '"></a>');
                            item.append('<a class="rotate" data-target="parent" title="' + gettext('повернуть') + '"></a>');
                            if (uploader_mode == 'workflow') {
                                item.append('<img width="240" height="160" class="img-responsive" src="'+responseJSON.path+'" data-id="'+responseJSON.fileName+'" alt="'+fileName+'" title=""/>');
                            } else if (uploader_mode == 'building') {
                                item.append('<img class="img-responsive" src="'+responseJSON.path+'" data-id="'+responseJSON.fileName+'" alt="'+fileName+'" title=""/>');
                                updatePhotosOnStorage();
                            } else {
                                item.append('<img width="240" height="160" class="img-responsive" src="'+responseJSON.path+'" data-id="'+responseJSON.fileName+'" alt="'+fileName+'" title="' + gettext('сделать главной фотографией объявления') + '"/>');
                                item.append('<textarea name="ajax_image_caption_' + responseJSON.fileName + '" class="form-control" placeholder="' + gettext('Описание') + '"/>');
                                item.append('<input type="hidden" name="ajax_image_order_' + responseJSON.fileName + '" class="order" value=""/>');
                            }
                            item.append('<input type="hidden" name="ajax_add_images" value="' + responseJSON.fileName + '"/>');
                        }
                    } else {
                        item.remove();
                        alert(gettext("Ошибка при обработке файла") + " " + fileName + "\n\n" + gettext("Проверьте является ли файл изображением."));
                    }
                },
                onProgress: function(id, fileName) {
                    // var button = $("#div_id_photos").find(".image-list .qq-upload-button").parent();
                    var button = $elem.find(".image-list .qq-upload-button").parent();
                    button.appendTo(button.parent());
                },
                onAllComplete: imageOrderUpdate,
                params: {
                    'csrf_token': csrf_token,
                    'csrf_name': 'csrfmiddlewaretoken',
                    'csrf_xname': 'X-CSRFToken'
                },
                template: '<div class="qq-uploader clearfix">' +
                        '<div class="qq-upload-drop-area"></div>' +
                        '<ul class="qq-upload-list image-list list-inline clearfix">' +
                            '<li class="pull-left relative">' +
                                '<div class="qq-upload-button" title="' + gettext('Выбрать файлы') + '"></div>' +
                            '</li>' +
                        '</ul>' +
                     '</div>',
                fileTemplate: '<li class="pull-left relative">' +
                        '<div class="qq-progress-bar">' +
                            '<span class="qq-upload-file"></span>' +
                            '<span class="qq-upload-spinner"></span>' +
                            '<span class="qq-upload-finished"></span>' +
                            '<span class="qq-upload-size"></span>' +
                            '<a class="qq-upload-cancel" href="#">' + gettext('Отмена') + '</a>' +
                            '<span class="qq-upload-failed-text">' + gettext('Ошибка') + '</span>' +
                        '</div>' +
                    '</li>'
            });
        });
        $('.already-uploaded li').prependTo('.qq-upload-list');
        restorePhotosFromStorage();
    }
    var $imageList = $('.image-list');
    var angles = [0, 90, 180, 270, 0];

    $imageList.on('click', '.delete', function() {
        $(this).siblings('input, textarea').toggleDisabled().parents('li').hide().addClass('deleted');
        updateCountOfPhotos();
        updatePhotosOnStorage();
    }).on('click', '.rotate', function() {
        var $rotateAnchor = $(this);
        if (!$rotateAnchor.hasClass('loading')) {
            var photoId = $(this).data('photoId');

            if (photoId) {
                var imageRotatedInput = $rotateAnchor.siblings('input[name^=image_rotated]');
                if (imageRotatedInput.length) {
                    var postData = {image_name: imageRotatedInput.val()};
                } else {
                    var postData = {photo_id: photoId};
                }
            } else {
                var postData = {image_name: $rotateAnchor.siblings('input[name=ajax_add_images]').val()};
            }

            $rotateAnchor.addClass('loading');
            $.ajax({
                method: 'post',
                url: ROTATE_AD_PHOTO_URL,
                data: postData
            }).success(
                function(data, textStatus, jqXHR) {
                    $rotateAnchor.siblings('img').attr('src', data['new_thumbnail_url']);
                    if (photoId) {
                        if (imageRotatedInput.length) {
                            imageRotatedInput.val(data['new_name']);
                        } else {
                            $rotateAnchor.parent().append('<input type="hidden" name="image_rotated_' + photoId + '" value="' + data['new_name'] + '" />');
                        }
                    } else {
                        $rotateAnchor.siblings('img').attr('data-id', data['new_name']);
                        $rotateAnchor.siblings('input[name=ajax_add_images]').val(data['new_name']);
                        $rotateAnchor.siblings('input[name^=ajax_image_order_]').attr('name', 'ajax_image_order_' + data['new_name']);
                        $rotateAnchor.siblings('textarea[name^=ajax_image_caption_]').attr('name', 'ajax_image_caption_' + data['new_name']);
                    }
                    $rotateAnchor.removeClass('loading');
                }
            ).error(
                function(jqXHR, textStatus, errorThrown) {
                    alert(gettext("Ошибка при повороте изображения"));
                }
            );
        }
    }).on('click', '.choose_main', function() {
        $('.image-list input[name=is_main]').attr('disabled', 'disabled');
        $(this).parent().find('input[name=is_main]').removeAttr('disabled');
        return false;
    });
    updateCountOfPhotos(); // прячет иконку с подсказкой о drag`n`drop

    // сортировка фото
    try {
        $imageList.sortable({
            cursor: "move",
            update: imageOrderUpdate
        });
    } catch (err) {}
});
