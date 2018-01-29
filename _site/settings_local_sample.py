# Sample local settings for development

import os
from settings import INSTALLED_APPS, VAR_ROOT

DEBUG = True

ALLOWED_HOSTS = ['*']

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.path.join(VAR_ROOT, 'cache'),
        'OPTIONS': {
            'MAX_ENTRIES': 100000
        },
    }
}

DATABASES_MYSQL = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'mesto',
        'USER': 'root',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'PORT': '',
        'OPTIONS': {"init_command": "SET storage_engine=INNODB, SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED",}
    }
}

DATABASES_PGSQL = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mesto',
        'USER': 'mesto',
        'HOST': '127.0.0.1',
        'PASSWORD': 'qwerty',
    }
}

DATABASES = DATABASES_PGSQL

# for windows
# GEOS_LIBRARY_PATH = 'C:/OSGeo4W64/bin/geos_c.dll'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

MEDIA_URL = '/media/'

MESTO_PARENT_HOST = 'mesto.loc:8000'
SESSION_COOKIE_DOMAIN = '.%s' % MESTO_PARENT_HOST.split(":")[0]

INSTALLED_APPS = list(INSTALLED_APPS)
INSTALLED_APPS.remove('raven.contrib.django.raven_compat') # no sentry in development process

DEBUG_TOOLBAR_PANELS = [
    # 'debug_toolbar.panels.versions.VersionsPanel',
    'debug_toolbar.panels.timer.TimerPanel',
    # 'debug_toolbar.panels.settings.SettingsPanel',
    # 'debug_toolbar.panels.headers.HeadersPanel',
    # 'debug_toolbar.panels.request.RequestPanel',
    'debug_toolbar.panels.sql.SQLPanel',
    # 'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    # 'debug_toolbar.panels.templates.TemplatesPanel',
    'debug_toolbar.panels.cache.CachePanel',
    #'debug_toolbar.panels.profiling.ProfilingPanel',
    # 'debug_toolbar.panels.signals.SignalsPanel',
    # 'debug_toolbar.panels.logging.LoggingPanel',
    # 'debug_toolbar.panels.redirects.RedirectsPanel',
]
