# coding: utf-8
from django.core.management.base import BaseCommand, CommandError

from ad.models import Photo

import sys

class Command(BaseCommand):
    help = u'Удаляет фотографии без объявлений'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', dest='dry_run', action='store_true')

    def handle(self, *args, **options):
        orphan_photos = Photo.objects.filter(basead__isnull=True)
        count = orphan_photos.count()
        print '%d photos to delete' % count

        if not options['dry_run']:
            deleted = 0
            while True:
                chunk = orphan_photos[:500]
                if chunk:
                    for photo in chunk:
                        photo.delete()
                        deleted += 1
                        if deleted % 100 == 0:
                            sys.stdout.write('\r%d/%d' % (deleted, count))
                            sys.stdout.flush()
                else:
                    break
        
