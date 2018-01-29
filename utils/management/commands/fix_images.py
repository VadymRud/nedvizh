# coding: utf-8
from django.core.management.base import BaseCommand, CommandError
from django.core.files.storage import default_storage
from django.core.files import File

from newhome.models import NewhomePhoto, ProgressPhoto, Layout, Floor
from ad.models import PHOTO_THUMBNAILS
from webinars.models import SeminarPhoto
from utils.new_thumbnails import Thumbnailer

import traceback

class Command(BaseCommand):
    def handle(self, *args, **options):
        for model in (NewhomePhoto, ProgressPhoto, Layout, Floor):
            for obj in model.objects.filter(image__gt='').order_by('pk'):
                print model._meta.model_name, obj.pk
                old_name = obj.image.name
                Thumbnailer(old_name, PHOTO_THUMBNAILS).delete()
                try:
                    with default_storage.open(old_name) as f:
                        obj.image.save(old_name, File(f))
                        # см. utils.image_signals.post_save_clean_image_file
                        default_storage.delete(old_name)
                except:
                    print traceback.format_exc(3)
                else:
                    print '%s -> %s' % (old_name, obj.image.name)

        for obj in SeminarPhoto.objects.filter(image__gt=''):
            Thumbnailer(obj.image.name, PHOTO_THUMBNAILS).delete()
            try:
                old_name = obj.image.name
                with default_storage.open(old_name) as f:
                    obj.image.save(old_name, File(f))
                # см. utils.image_signals.post_save_clean_image_file
                default_storage.delete(old_name)
            except:
                print traceback.format_exc(3)
            else:
                print u'%s -> %s' % (old_name, obj.image.name)

