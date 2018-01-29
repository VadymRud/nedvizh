# coding: utf-8

from django.templatetags.static import static
from django.core.cache import cache
from django.http import Http404
from django.shortcuts import redirect
from django.conf import settings

from django_hosts.resolvers import reverse
from sorl.thumbnail import get_thumbnail


WATERMARK = {
    'image': 'static/img/watermark.png',
    'opacity': 0.4,
    'scale': '40%',
}

def get_options(size, nocrop=False):
    options = {}
    x, y = [int(dim) for dim in size.split('x')]
    if max(x, y) > 300:
        options['quality'] = 75
        options['watermark'] = WATERMARK
    else:
        options['quality'] = 90
    if not nocrop:
        options['crop'] = 'center'
    return options


cache_key_pattern = 'lazy_thumbnail_%s'
cache_timeout = 3600 * 24 * 7

def get_lazy_thumbnail(file, size, **options):
    thumb = get_thumbnail(file, size, lazy=True, **options)
    if isinstance(thumb, LazyImageFile):
        if not cache.get(cache_key_pattern % thumb.key):
            cached_data = {
                'name': file.name,
                'size': size,
                'options': options,
            }
            cache.set(cache_key_pattern % thumb.key, cached_data, cache_timeout)
        url = reverse('thumbnail', args=[thumb.key])
    else:
        url = thumb.url
    return url


def get_thumbnail_safe(*args, **kwargs):
    try:
        thumb = get_thumbnail(*args, **kwargs)
        return thumb.url
    except IOError, exception:
        if 'image file is truncated' in exception.message:
            return static('img/no-photo.png')
        else:
            raise exception


class FakeFile(object):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


def view(request, key):
    thumb_params = cache.get(cache_key_pattern % key)
    if thumb_params:
        fake_file = FakeFile(thumb_params['name'])
        url = get_thumbnail_safe(fake_file, thumb_params['size'], **thumb_params['options'])
        return redirect(url)
    else:
        raise Http404

from sorl.thumbnail.base import ThumbnailBackend, logger
from sorl.thumbnail.images import BaseImageFile, DummyImageFile, ImageFile
from sorl.thumbnail.conf import settings, defaults as default_settings
from sorl.thumbnail.compat import text_type
from sorl.thumbnail import default
from sorl.thumbnail.helpers import tokey, serialize

class LazyImageFile(BaseImageFile):
    def __init__(self, key):
        self.key = key

def create_sorl_key(source, geometry_string, options):
    return tokey(source.key, geometry_string, serialize(options))

class CachedImageFile(ImageFile):
    def __init__(self, *args, **kwargs):
        super(CachedImageFile, self).__init__(*args, **kwargs)
        self._exists = ImageFile.exists(self)
        try:
            self._content = ImageFile.read(self)
        except Exception as exception:
            self._exception = exception
        else:
            self._exception = None

    def read(self):
        if self._exception:
            raise self._exception
        else:
            return self._content

    def exists(self):
        return self._exists


class LazyThumbnailBackend(ThumbnailBackend):
    def get_thumbnail(self, file_, geometry_string, **options):

        # PATCHED
        lazy = options.pop('lazy', False)


        """
        Returns thumbnail as an ImageFile instance for file with geometry and
        options given. First it will try to get it from the key value store,
        secondly it will create it.
        """
        logger.debug(text_type('Getting thumbnail for file [%s] at [%s]'), file_,
                     geometry_string)

        if isinstance(file_, CachedImageFile):
            source = file_
        else:

            if file_:
                source = ImageFile(file_)
            elif settings.THUMBNAIL_DUMMY:
                return DummyImageFile(geometry_string)
            else:
                return None

        #preserve image filetype
        if settings.THUMBNAIL_PRESERVE_FORMAT:
            options.setdefault('format', self._get_format(file_))

        for key, value in self.default_options.items():
            options.setdefault(key, value)


        # For the future I think it is better to add options only if they
        # differ from the default settings as below. This will ensure the same
        # filenames being generated for new options at default.
        for key, attr in self.extra_options:
            value = getattr(settings, attr)
            if value != getattr(default_settings, attr):
                options.setdefault(key, value)
        name = self._get_thumbnail_filename(source, geometry_string, options)
        thumbnail = ImageFile(name, default.storage)
        cached = default.kvstore.get(thumbnail)
        if cached:
            return cached
        else:


            # PATCHED
            if lazy:
                key = create_sorl_key(source, geometry_string, options)
                return LazyImageFile(key)
            else:
                if default.storage.exists(name):
                    default.kvstore.get_or_set(source)
                    default.kvstore.set(thumbnail, source)
                    return thumbnail


            # We have to check exists() because the Storage backend does not
            # overwrite in some implementations.
            # so we make the assumption that if the thumbnail is not cached, it doesn't exist
            try:
                source_image = default.engine.get_image(source)
            except IOError:
                if settings.THUMBNAIL_DUMMY:
                    return DummyImageFile(geometry_string)
                else:
                    # if S3Storage says file doesn't exist remotely, don't try to
                    # create it and exit early.
                    # Will return working empty image type; 404'd image
                    logger.warn(text_type('Remote file [%s] at [%s] does not exist'), file_, geometry_string)
                    return thumbnail

            # We might as well set the size since we have the image in memory
            image_info = default.engine.get_image_info(source_image)
            options['image_info'] = image_info
            size = default.engine.get_image_size(source_image)
            source.set_size(size)
            try:
                self._create_thumbnail(source_image, geometry_string, options,
                                       thumbnail)
                self._create_alternative_resolutions(source_image, geometry_string,
                                                     options, thumbnail.name)
            finally:
                default.engine.cleanup(source_image)

        # If the thumbnail exists we don't create it, the other option is
        # to delete and write but this could lead to race conditions so I
        # will just leave that out for now.
        default.kvstore.get_or_set(source)
        default.kvstore.set(thumbnail, source)
        return thumbnail


from sorl.thumbnail.engines.pil_engine import Engine
from utils.new_watermark import watermark_processor

# ранее использовался https://github.com/originell/sorl-watermark
# но он уже давно не поддерживается
class WatermarkEngine(Engine):
    name = 'PIL/Pillow'

    def create(self, image, geometry, options):
        image = super(WatermarkEngine, self).create(image, geometry,
                                                        options)
        watermark = options.pop('watermark', None)
        if watermark:
            image = watermark_processor(image, watermark)
        return image

