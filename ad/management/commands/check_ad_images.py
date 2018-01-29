from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage

from ad.models import Photo

import os
import re


class Command(BaseCommand):
    help = 'Checks ad image files from s3cmd ls log'

    def add_arguments(self, parser):
        parser.add_argument('s3cmd_log_file')
        parser.add_argument('alias', choices=['xs', 'md', 'lg', 'full', 'origin'])
        parser.add_argument('batch_size', type=int)
        parser.add_argument('--delete', '-d', action='store_true', help='delete files no having photo')

    def handle(self, *args, **options):
        alias = options['alias']

        if alias == 'origin':
            regexp = re.compile(r'^.*?s3\://s\.mesto\.ua/(upload/ad/photo/(?:u|r)\d+/.*?\.jpg)')
        else:
            regexp = re.compile(r'^.*?s3\://s\.mesto\.ua/thumbnails/ad/photo/%s/(.*?)\.jpg' % alias)

        def get_path(entry):
            if alias == 'origin':
                return entry
            else:
                return 'thumbnails/ad/photo/%s/%s.jpg' % (alias, entry)

        def get_attr(photo):
            if alias == 'origin':
                return photo.image.name
            else:
                return photo.hash

        def process(batch):
            if alias == 'origin':
                query = Photo.objects.only('image').filter(image__in=batch)
            else:
                where = "md5(concat(image, '%s')) in (%s)" % (alias, ','.join(["'%s'" % hash for hash in batch]))
                query = Photo.objects.only('image').extra(select={'hash': "md5(concat(image, '%s'))" % alias}, where=[where])

            for photo in query:
                batch.remove(get_attr(photo))
                print 'good:', get_path(get_attr(photo))
            for entry in batch:
                path = get_path(entry)
                if options['delete']:
                    default_storage.delete(path)
                    print 'deleted:', path
                else:
                    print 'to delete:', path

        batch = []

        with open(options['s3cmd_log_file']) as file:
            for line in file:
                match = regexp.match(line)
                if match is not None:
                    entry = match.group(1)
                    batch.append(entry)
                    if len(batch) >= options['batch_size']:
                        process(batch)
                        batch = []
                else:
                    print 'no match: "%s"' % line.strip()

        process(batch)

