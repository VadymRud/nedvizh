# coding: utf-8
from django.core.management.base import BaseCommand, CommandError
from django.core.files.storage import default_storage
from django.conf import settings

import datetime


class Command(BaseCommand):
    help = 'Removes out-of-date files in settings.AJAX_UPLOAD_DIR'

    def handle(self, *args, **options):
        try:
            dirs, files = default_storage.listdir(settings.AJAX_UPLOAD_DIR)
        except OSError: # no directory exception for FileSystemStorage
            files = []
        deleted = 0
        utc_now = datetime.datetime.utcnow()
        now = datetime.datetime.now()
        for name in files:
            path = '%s/%s' % (settings.AJAX_UPLOAD_DIR, name)
            file_mtime = default_storage.get_modified_time(path)
            if (utc_now - file_mtime).seconds > 3600 * 6:
                default_storage.delete(path)
                print 'remove %s' % path
                deleted += 1

        print '%s: %d out-of-date files removed' % (now, deleted)
