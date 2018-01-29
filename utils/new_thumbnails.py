# coding: utf-8
from django.db import models
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from new_watermark import watermark_processor
from utils.storage import overwrite

from PIL import Image, ImageOps
from io import BytesIO
import hashlib
import os


def save_to_jpeg_content(image):
    buffer = BytesIO()
    image.save(buffer, 'JPEG')
    return ContentFile(buffer.getvalue())


def resize_image(image, size, crop):
    if crop:
        return ImageOps.fit(image, size, method=Image.LANCZOS)
    else:
        image.thumbnail(size, Image.LANCZOS)
        return image


class Engine(object):
    def __init__(self, origin_file):
        self.origin_image = Image.open(origin_file)

    def create(self, options):
        options = dict(options)

        size = options.pop('size')
        crop = options.pop('crop', False)

        image = resize_image(self.origin_image, size, crop)
        
        watermark = options.pop('watermark', None)
        if watermark:
            image = watermark_processor(image, watermark)

        return image


class Thumbnailer(object):
    def __init__(self, path, parameters):
        self.path = path
        self.prefix = parameters['prefix']
        self.aliases = parameters['aliases']

    def get_path(self, alias):
        hash = hashlib.md5(self.path + alias).hexdigest()
        return 'thumbnails/%s/%s/%s.jpg' % (self.prefix, alias, hash)

    def create(self, aliases=None):
        engine = Engine(default_storage.open(self.path))

        for alias in (aliases or self.aliases.keys()):
            options = self.aliases[alias]
            image = engine.create(options)
            overwrite(self.get_path(alias), save_to_jpeg_content(image))

    def delete(self):
        old_name, old_ext = os.path.splitext(self.path)
        for alias in self.aliases.keys():
            new_path = self.get_path(alias)
            new_name, new_ext = os.path.splitext(new_path)
            old_path = ''.join([new_name, old_ext])
            default_storage.delete(new_path)
            default_storage.delete(old_path)

    def get_url(self, alias):
        return default_storage.url(self.get_path(alias))


class ThumbnailedImageFieldFile(models.ImageField.attr_class):
    def __init__(self, *args, **kwargs):
        super(ThumbnailedImageFieldFile, self).__init__(*args, **kwargs)
        if self.name:
            self.thumbnailer = Thumbnailer(self.name, self.field.thumbnails_settings)


class ThumbnailedImageField(models.ImageField):
    attr_class = ThumbnailedImageFieldFile

    def __init__(self, *args, **kwargs):
        self.thumbnails_settings = kwargs.pop('thumbnails', None) # значение по умолчанию необходимо для работы миграций
        super(ThumbnailedImageField, self).__init__(*args, **kwargs)

