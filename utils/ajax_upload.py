# coding: utf-8
from django.conf import settings
from django.core.files.storage import default_storage

from ajaxuploader.backends.default_storage import DefaultStorageUploadBackend

from utils.new_thumbnails import Thumbnailer, save_to_jpeg_content
from utils.storage import overwrite
from ad.models import normalize_image

from PIL import Image

import hashlib
import uuid
import os


class UploadThumbnailer(Thumbnailer):
    def get_path(self, alias):
        hash_ = hashlib.md5(self.path).hexdigest()
        return '%s/%s.jpg' % (settings.AJAX_UPLOAD_DIR, hash_)


AD_THUMBNAILER_PARAMETERS = {
    'prefix': None,
    'aliases': {None: {'size': (288, 192), 'crop': True}},
}

class StorageBackend(DefaultStorageUploadBackend):
    BUFFER_SIZE = 2097152
    thumbnailer_parameters = AD_THUMBNAILER_PARAMETERS

    def update_filename(self, request, filename):
        return 'u%d_%s%s' % (request.user.id, uuid.uuid4().hex, os.path.splitext(filename)[-1])

    def upload_complete(self, request, filename):
        original_image_path = super(StorageBackend, self).upload_complete(request, filename)['path']
        image = Image.open(default_storage.open(original_image_path))

        # ранее, "нормализованное" изображение перезаписывалось в первоначальный файл
        # для формата изображений MPO на Windows в таком случае генерировалось WindowsError: [Error 32]
        # кроме того, после "нормализации" меняется формат (логично поменять и расширение),
        # а оригинал пусть хранится на случай отладки
        normalized_image_path = '%s.normalized.jpg' % original_image_path
        overwrite(normalized_image_path, save_to_jpeg_content(normalize_image(image)))

        thumbnailer = UploadThumbnailer(normalized_image_path, self.thumbnailer_parameters)
        thumbnailer.create()

        # if you want to "try/except" exceptions, return {"success": None}
        return {
            "path": thumbnailer.get_url(None),
            "fileName": os.path.basename(normalized_image_path)
        }


class NewhomeStorageBackend(StorageBackend):
    thumbnailer_parameters = {
        'prefix': None,
        'aliases': {None: {'size': (740, 425), 'crop': True}},
    }
