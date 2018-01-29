from django.core.management.base import BaseCommand
from django.conf import settings
from django.apps import apps
from django.db.migrations.recorder import MigrationRecorder

import os

class Command(BaseCommand):
    help = 'Emulates a sequence of commands "manage.py migrate * zero --fake" (deletes rows from "django_migrations" table for local apps)'

    def handle(self, *args, **options):
        local_apps = []
        for app_config in apps.get_app_configs():
            if os.path.dirname(app_config.path) == settings.BASE_DIR:
                local_apps.append(app_config.name)

        MigrationRecorder.Migration.objects.filter(app__in=local_apps).delete()

