# coding: utf-8

# альтернатива команде makemessages и ее надстройке из django-jinja, использует
# библиотеки babel (полноценно извлекает фразы из jinja-шаблонов) и django-babel
# (для извлечения фраз из стандартных django-шаблонов)

# причина использования альтернативы: makemessages из django-jinja в силу костыльной
# реализации (замена регулярками jinja-тегов на django-теги) работает неполноценно:
# - при наличии нескольких _() в одной строке извлекается только первый
# - не работает извлечение внутри многострочных тегов
#   {% ...
#   ... _() ...
#   ... %}
# - не работает извлечение из gettext()

# стандартный скрипт .buildout/bin/pybabel использовать не удастся, так как прописываемые
# в babel.cfg расширения jinja из django-jinja (без которых извлечение фраз из файлов,
# содержащих теги из расширений, не будет выполняться) содержат импорт настроек
# django.conf.settings, которые невозможно импортировать во внешних скриптах,
# поэтому используется низкоуровневое API библиотеки babel

from django.core.management.base import BaseCommand
from django.conf import settings
from django.apps import apps

from babel.messages.extract import extract_from_dir
from babel.messages.catalog import Catalog
from babel.messages.pofile import read_po, write_po
from babel.core import Locale

import os
import copy

class Command(BaseCommand):
    def handle(self, **options):
        for app_config in get_apps_to_translate():
            print 'processing "%s" app' % app_config.name
            update_po_in_app(app_config)

        print 'processing root'
        update_po_in_root()

def get_apps_to_translate():
    for app_config in apps.get_app_configs():
        if os.path.dirname(app_config.path) == settings.BASE_DIR:
            yield app_config

jinja_extensions = settings.TEMPLATES[0]['OPTIONS']['extensions']
jinja_options = {'extensions': '%s' % ','.join(jinja_extensions)}

base_mapping = {
    'djangojs': {
        'method_map': [ # порядок обязателен
            ('static/**/libs/**.js', 'ignore'),
            ('static/**/vendor/**.js', 'ignore'),
            ('static/**.js', 'javascript'),
        ],
        'options_map': {},
    },
    'django': {
        'method_map': [
            ('templates/**.jinja.*', 'jinja2'),
            ('templates/**.*', 'django'),
            # сюда добавляется mapping для питона
        ],
        'options_map': {'templates/**.jinja.*': jinja_options},
    }
}

def update_po_in_app(app_config):
    mapping = copy.deepcopy(base_mapping)
    mapping['django']['method_map'].append(('**.py', 'python'))
    extract_and_update_locale_dir(app_config.path, mapping)

def update_po_in_root():
    mapping = copy.deepcopy(base_mapping)
    mapping['django']['method_map'].append(('_site/**.py', 'python'))
    extract_and_update_locale_dir(settings.BASE_DIR, mapping)

def extract_and_update_locale_dir(dirname, mapping):
    locale_dir = os.path.join(dirname, 'locale')

    for domain in ('django', 'djangojs'):
        extracted_catalog = Catalog()
        extracted = extract_from_dir(
            dirname=dirname,
            method_map=mapping[domain]['method_map'],
            options_map=mapping[domain]['options_map']
        )
        for filename, lineno, message, comments, context in extracted:
            extracted_catalog.add(message, None, [(filename, lineno)], auto_comments=comments, context=context)

        for locale, language in settings.LANGUAGES:
            po_path = os.path.join(locale_dir, locale, 'LC_MESSAGES', '%s.po' % domain)

            if os.path.exists(po_path):
                with open(po_path, 'rb') as po_fileobj:
                    catalog = read_po(po_fileobj, locale=locale, domain=domain)
                if catalog._messages != extracted_catalog._messages:
                    catalog.update(extracted_catalog, no_fuzzy_matching=True, update_header_comment=False)
                    with open(po_path, 'wb') as po_fileobj:
                        write_po(po_fileobj, catalog, ignore_obsolete=True)

            elif extracted_catalog._messages:
                extracted_catalog.locale = Locale(locale)
                extracted_catalog.domain = domain
                extracted_catalog.project = 'Mesto.UA'
                extracted_catalog.copyright_holder = 'Mesto.UA'
                extracted_catalog.fuzzy = False
                touch_directory(po_path)
                with open(po_path, 'wb') as po_fileobj:
                    write_po(po_fileobj, extracted_catalog)


def touch_directory(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)

