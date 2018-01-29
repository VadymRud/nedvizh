# coding: utf-8
from django.conf import settings

from ad.models import Ad, Photo
from task_queues import task, close_db

import traceback
import logging

task_logger = logging.getLogger('task_queues')

@task(queue='process_address')
@close_db
def process_address(ad_id):
    message = ''
    try:
        message = '#%d ' % ad_id
        ad = Ad.objects.get(id=ad_id)
        ad.process_address()
        if ad.region:
            ad.save()
            task_logger.debug(message + 'ok')
        else:
            # TODO перенести в Ad.process_adress()
            if settings.MESTO_USE_GEODJANGO:
                ad.point = None
            else:
                ad.coords_x = ad.coords_y = None

            ad.moderation_status = 11
            ad.save()
            task_logger.debug(message + 'no region')
    except:
        task_logger.debug(message + 'exception ' + traceback.format_exc(8).encode('utf-8'))

@task(queue='photo_download')
@close_db
def download_photo(photo_id, attempt):
    message = ''
    try:
        message = '#%d %d ' % (photo_id, attempt)
        photo = Photo.objects.get(id=photo_id)
        message += '%s ' % photo.source_url.encode('utf-8')
        try:
            photo.download()
        except:
            if attempt < 3:
                task_logger.debug(message + 'download error ' + traceback.format_exc(8).encode('utf-8'))
                download_photo.schedule(args=(photo_id, attempt + 1), delay=30*60)
            else:
                photo.delete()
                task_logger.debug(message + 'delete')
        else:
            task_logger.debug(message + 'ok')
            process_photo(photo_id)
    except:
        task_logger.debug(message + 'exception ' + traceback.format_exc(8).encode('utf-8'))


def process_photo_function(photo_id):
    message = ''
    try:
        message = '#%d ' % photo_id
        photo = Photo.objects.get(id=photo_id)
        photo.image.thumbnailer.create()
        photo.update_hash()
        task_logger.debug(message + 'ok')
    except:
        task_logger.debug(message + 'exception ' + traceback.format_exc(8).encode('utf-8'))

process_photo = task(queue='process_photo')(close_db(process_photo_function))
process_photo_priority = task(queue='important')(close_db(process_photo_function))

