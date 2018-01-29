# coding: utf-8

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
from django.apps import apps

from i18n.management.commands.update_po import get_apps_to_translate

import os
import datetime


class Command(BaseCommand):
    help = u'Проверяет наличие устаревших файлов *.mo и обновляет их'

    def handle(self, **options):
        print datetime.datetime.now()

        locale_dirs = [os.path.join(settings.BASE_DIR, 'locale')]

        for app_config in get_apps_to_translate():
            locale_dirs.append(os.path.join(app_config.path, 'locale'))

        locales = [locale for locale, language in settings.LANGUAGES]

        for locale_dir in locale_dirs:
            for locale in locales:
                for domain in ('django', 'djangojs'):
                    path_template = os.path.join(locale_dir, locale, 'LC_MESSAGES', '%s.%%s' % domain)
                    po_path = path_template % 'po'

                    if os.path.exists(po_path):
                        mo_path = path_template % 'mo'

                        if not os.path.exists(mo_path) or os.stat(mo_path).st_mtime < os.stat(po_path).st_mtime:
                            print '"%s" is older than "%s"!' % (mo_path, po_path)
                            call_command('compilemessages', locale=locales, verbosity=0)
                            os.system(settings.MESTO_TRANSLATIONS_RESTART_COMMAND)
                            return
                            
