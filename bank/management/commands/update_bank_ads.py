# coding: utf-8

from django.core.management.base import BaseCommand
from django.conf import settings

from ad.models import Ad

import datetime

class Command(BaseCommand):
    help = 'Updates banks ads'

    def handle(self, *args, **options):
        now = datetime.datetime.now()
        expired = now + datetime.timedelta(days=settings.EXPIRE_DAYS)
        Ad.objects.filter(bank__isnull=False, is_published=True).update(updated=now, expired=expired)

