# coding: utf-8

import os
from datetime import datetime
from django.utils.translation import ugettext_lazy as _
from jinja2 import StrictUndefined

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
VAR_ROOT = os.path.join(BASE_DIR, 'var')
LOG_ROOT = os.path.join(VAR_ROOT, 'logs')

AUTH_USER_MODEL = 'custom_user.User'
DEBUG = False
DEFAULT_FROM_EMAIL = 'Mesto UA <no-reply@mesto.ua>'
EMAIL_BACKEND = 'django_ses.SESBackend'
INSTALLED_APPS = [
    'i18n', # должно идти раньше django-jinja, чтобы перекрыть команду makemessages

    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.sitemaps',
    'django.contrib.messages',
    'django.contrib.staticfiles',  
    'django.contrib.humanize',
    'django.contrib.gis',

    'ajaxuploader',
    'chart_tools',
    'ckeditor',
    'compressor',
    'debug_toolbar',
    'django_csv_exports',
    'django_hosts',
    'django_jinja',
    'django_jinja.contrib._humanize',
    'corsheaders',
    'googlecharts',
    'modeltranslation',
    'pytils',
    'push_notifications',
    'raven.contrib.django.raven_compat', # sentry
    'registration', 
    'rest_framework',
    'rest_framework.authtoken',
    'social_django',
    'sorl.thumbnail',
    'storages',
    
    'ad',
    'agency',
    'admin_ext',
    'autoposting',
    'bank',
    'banner',
    'callcenter',
    'cron',
    'custom_user',
    'guide',
    'import_',
    'task_queues',
    'newhome',
    'mail',
    'mobile_api',
    'paid_services',
    'ppc',
    'professionals',
    'profile',
    'promo',
    'seo',
    'staticpages',
    'utils',
    'webinars',

    # локальная копия приложения django.contrib.flatpages, но с удаленной моделью FlatPage
    # и соотвествующей миграцией 0002, чтобы удалились неиспользуемые таблицы и объекты из базы;
    # после того, как повсеместно будет применена миграция 0002, можно удалить это приложение и перегенерировать миграции локальных приложений
    'flatpages',

    'django.contrib.admin',
    'django.contrib.admindocs',
]
INTERNAL_IPS = ('127.0.0.1', '37.113.156.203', '46.147.210.50', '37.113.132.105')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'time': {
            'format': '[%(asctime)s] %(message)s'
        },
        'user_action': {
            'format': '[%(asctime)-15s] [ip:%(ip)s|user_id:%(user)s] %(message)s'
        },
        'geocoder': {
            'format': '[%(asctime)s] %(requests_settings)s %(status_code)s %(url)s %(message)s'
        },
        'loyalty': {
            'format': '[%(asctime)s] UID: #%(user_id)s Action: %(action)s'
        }
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'time',
        },
        'user_action': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_ROOT, 'user_action.log'),
            'formatter': 'user_action'
        },
        'common': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_ROOT, 'common.log'),
            'formatter': 'time'
        },
        'geocoder': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_ROOT, 'geocoder.log'),
            'formatter': 'geocoder'
        },
        'loyalty': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_ROOT, 'loyalty.log'),
            'formatter': 'loyalty'
        }
    },
    'loggers': {
        'task_queues': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'user_action': {
            'handlers': ['user_action'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'common': {
            'handlers': ['common'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'geocoder': {
            'handlers': ['geocoder'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'loyalty': {
            'handlers': ['loyalty'],
            'level': 'INFO',
            'propagate': True
        }
    },
}
LOCALE_PATHS = (
    os.path.join(BASE_DIR, 'locale'),
)
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = ''
MIDDLEWARE_CLASSES = (
    'django_hosts.middleware.HostsRequestMiddleware',

    'django.middleware.gzip.GZipMiddleware',
    'htmlmin.middleware.HtmlMinifyMiddleware',
    'htmlmin.middleware.MarkRequestMiddleware',

    # 'utils.shieldsquare.shieldsquare.ShieldSquareMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    # должно стоять перед CommonMiddleware по аналогии с django.middleware.locale.LocaleMiddleware
    'utils.middleware.CustomLocaleMiddleware',

    'corsheaders.middleware.CorsMiddleware',

    # должно стоять раньше всех middleware с редиректами;
    # можно попробовать переделать, чтобы когда не отработал process_request (в случае редиректа из стоящей ранее мидлвари)
    # в process_response тоже определялся traffic_source и записывался в кукисы
    'utils.middleware.TrafficSourceMiddleware',

    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'debug_toolbar.middleware.DebugToolbarMiddleware',

    'utils.middleware.SubdomainMiddleware',
    'utils.middleware.ProfileMiddleware',
    'utils.middleware.CustomerMiddleware',
    # 'utils.middleware.MobileMiddleware',

    'django_hosts.middleware.HostsResponseMiddleware',
)
ROOT_URLCONF = '_site.urls'
SECRET_KEY = '=su^z4gqu=$vc^*uf*k+9b7%hkb8sz@w=s9rp4v6b=w78jenc*'

from django_jinja.builtins import DEFAULT_EXTENSIONS

context_processors = [
    'django.template.context_processors.debug',
    'django.template.context_processors.i18n',
    'django.template.context_processors.media',
    'django.template.context_processors.static',
    'django.template.context_processors.tz',
    'django.template.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
    'utils.context_processors.django_settings',
    #'utils.context_processors.banners',
]

TEMPLATES = [
    {
        "BACKEND": "django_jinja.backend.Jinja2",
        "APP_DIRS": True,
        "DIRS": [
            os.path.join(BASE_DIR, 'templates'),
        ],
        "OPTIONS": {
            "context_processors": context_processors,
            "match_extension": None,
            "match_regex": r'.*jinja\.(html|xml|txt|css)',
            "undefined": 'jinja2.StrictUndefined',
            "extensions": DEFAULT_EXTENSIONS + [
                # 'django_jinja.builtins.extensions.DjangoExtraFiltersExtension',
                'compressor.contrib.jinja2ext.CompressorExtension',
            ],
        }
    },
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(BASE_DIR, 'templates'),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            'context_processors': context_processors,
        },
    },
]

TIME_ZONE = 'Asia/Yekaterinburg'

USE_I18N = True
USE_L10N = True
LANGUAGE_CODE = 'ru'
LANGUAGES = (
    ('ru', 'Russian'),
    ('uk', 'Ukrainian'),
    ('hu', 'Hungarian'),
)

WSGI_APPLICATION = '_site.wsgi.application'

MESTO_PARENT_HOST = 'mesto.ua'

### Django contrib settings

# auth
AUTHENTICATION_BACKENDS = (
    #'social_core.backends.vk.VKOAuth2',
    'social_core.backends.google.GoogleOAuth2',
    'social_core.backends.facebook.FacebookOAuth2',
    'social_core.backends.twitter.TwitterOAuth',
    "profile.emailauth.EmailBackend",
    "django.contrib.auth.backends.ModelBackend", 
) 
LOGIN_URL = '/auth/login/' 
LOGIN_REDIRECT_URL = '/'

# sessions
SESSION_COOKIE_DOMAIN = '.%s' % MESTO_PARENT_HOST

# sites
SITE_ID = 1

# staticfiles
STATIC_ROOT = os.path.join(MEDIA_ROOT, 'static')
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

from django.conf.locale.ru import formats as ru_formats
ru_formats.DATETIME_FORMAT = "d.m.Y H:i:s"

# Third-party libraries

# ajaxuploader
AJAX_UPLOAD_DIR = 'upload_ajax'

# boto
AWS_ACCESS_KEY_ID = 'AKIAIZJUPDYY5SRKMWAA'
AWS_SECRET_ACCESS_KEY = '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'
AWS_SQS_REGION_NAME = 'us-east-1'
AWS_SQS_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/787213931777/EmailComplainsAndBounces'

# ckeditor
CKEDITOR_CONFIGS = {
    'default': {
        'toolbar_Full_Anchors': [
            ['Styles', 'Format', 'Bold', 'Italic', 'Underline', 'Strike', 'SpellChecker', 'Undo', 'Redo'],
            ['JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock', '-', 'NumberedList', 'BulletedList'],
            ['Cut', 'Copy', 'Paste', 'PasteText', 'PasteFromWord'],
            ['Link','Unlink', 'Anchor'], # customize
            ['Image', 'Table', 'HorizontalRule', 'SpecialChar', 'Iframe'],
            ['TextColor', 'BGColor'], ['Source'],
        ],
        'toolbar': 'Full_Anchors',
        'height': 300,
        'width': '100%' ,
        "removePlugins": "stylesheetparser",
        'extraAllowedContent': 'iframe[*]',
        'allowedContent': True,
    },
    'only_links': {
        'toolbar': 'only_links',
        'toolbar_only_links': [['Link','Unlink'], ['Source']],
        'allowedContent': True,
    }
}
CKEDITOR_MEDIA_PREFIX = "/static/ckeditor/"
CKEDITOR_UPLOAD_PATH = 'upload_flatpages' #relative path (django-ckeditor-updated, not django-ckeditor)
CKEDITOR_JQUERY_URL = '//ajax.googleapis.com/ajax/libs/jquery/2.1.1/jquery.min.js'
CKEDITOR_IMAGE_BACKEND = 'pillow'

# compressor
COMPRESS_OUTPUT_DIR = 'compress'
def COMPRESS_JINJA2_GET_ENVIRONMENT():
    from django_jinja.base import env
    return env

# Cross-origin resource sharing
CORS_ORIGIN_REGEX_WHITELIST = ( '^(https?://)?(\w+\.)?mesto(ua\.ru|\.ua|\.loc:8000)$', )

# debugtoolbar
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_COLLAPSED': True,
    'SHOW_TOOLBAR_CALLBACK': 'utils.debug_toolbar.show_toolbar',
}
# решение проблемы сочетания django-jinja и django-debug-toolbar
# см. http://stackoverflow.com/questions/38569760/django-debug-toolbar-template-object-has-no-attribute-engine
# в следующей версии django-debug-toolbar (текущая - 1.6) должно быть исправлено, и можно будет все это убрать
from debug_toolbar.settings import PANELS_DEFAULTS
DEBUG_TOOLBAR_PANELS = PANELS_DEFAULTS
DEBUG_TOOLBAR_PANELS.remove('debug_toolbar.panels.templates.TemplatesPanel')

# django-csv-export
DJANGO_EXPORTS_REQUIRE_PERM = False
DJANGO_CSV_GLOBAL_EXPORTS_ENABLED = True

# django-hosts
DEFAULT_HOST = 'default'
ROOT_HOSTCONF = '_site.hosts'

# django-modeltranslation
# для украинского и венгерского сайтов используемые языки задаются через LANGUAGES локально;
# чтобы при переключении сайтов не создавались новые миграции нужно зафиксировать языки для modeltranslation
MODELTRANSLATION_LANGUAGES = ('ru', 'uk', 'hu')

# htmlmin
KEEP_COMMENTS_ON_MINIFYING = True

# rest framework
REST_FRAMEWORK = {
    # 'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer',),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly',),
    'DEFAULT_FILTER_BACKENDS': ('rest_framework.filters.DjangoFilterBackend',),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10
}

# Facebook SDK
FACEBOOK_APP_ID = '102257043625767'
FACEBOOK_APP_NAME = 'Mesto.ua'
FACEBOOK_APP_SECRET = 'c960cdb783b8ac316c48299d2a24508d'

# Vk SDK
VK_APP_LOGIN = '+380730922570'
VK_APP_PASSWORD = 'mesto.ua123'
VK_APP_ID = '5924243'
VK_APP_SECRET_KEY = 'kPXQuAjReH0bgq07NMYx'

# social auth
SOCIAL_AUTH_FACEBOOK_KEY = '341252865886446'
SOCIAL_AUTH_FACEBOOK_SECRET = 'e9b8e366868e4cc19ff405000bf4af11'
SOCIAL_AUTH_FACEBOOK_API_VERSION = '2.3'
SOCIAL_AUTH_FACEBOOK_SCOPE = ['email']
SOCIAL_AUTH_FACEBOOK_PROFILE_EXTRA_PARAMS = {'fields': 'id,name,email',}

SOCIAL_AUTH_TWITTER_KEY = 'gy0G8Fzfeg3c1cTi9lQA'
SOCIAL_AUTH_TWITTER_SECRET = 'MDTitXWmTFc163hMkxmYUVaRhD9pDLmOfuaDW98oe90'

SOCIAL_AUTH_VK_OAUTH2_KEY = '2749476'
SOCIAL_AUTH_VK_OAUTH2_SECRET = 'ZFvGavv1HN3RS7ace7Iq'

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = '731113506701.apps.googleusercontent.com'
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = '65OHTd0jcSkBIXKriaq-9dWU'
SOCIAL_AUTH_GOOGLE_OAUTH2_USE_UNIQUE_USER_ID = True

SOCIAL_AUTH_SANITIZE_REDIRECTS = True

SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    #'utils.social_auth.disallow_new_vk_users',
    'social_core.pipeline.user.get_username',
    #'social_core.pipeline.mail.mail_validation',
    'social_core.pipeline.social_auth.associate_by_email',
    'social_core.pipeline.user.create_user',
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
)

# sorl thumbnail
THUMBNAIL_DEBUG = True
THUMBNAIL_DUMMY = True
THUMBNAIL_DUMMY_SOURCE = STATIC_URL + 'img/no-photo.png'
THUMBNAIL_ENGINE = 'utils.thumbnail.WatermarkEngine'
THUMBNAIL_BACKEND = 'utils.thumbnail.LazyThumbnailBackend'
THUMBNAIL_PRESERVE_FORMAT = True


### Mesto settings

ACCOUNT_ACTIVATION_DAYS = 7 #registration
BANK_EMAIL = 'bank@mesto.ua'
DEFAULT_AGENCY_RATING = -1 # crm
EXPIRE_DAYS = 30
GUIDE_BUTTONS_REGIONS = (
    'alushta', 'borispol', 'brovaryi', 'vinnitsa', 'dnepropetrovsk', 'donetsk', 'evpatoriya',
    'zhitomir', 'zaporozhe', 'karpaty', 'kiev', 'kirovograd', 'krivoj-rog', 'lugansk',
    'lvov', 'mariupol', 'mukachevo', 'nikolaev', 'odessa', 'poltava', 'sevastopol', 'simferopol',
    'sudak', 'uzhgorod', 'feodosiya', 'harkov', 'hmelnitskij', 'chernovtsyi', 'yalta',
)
IMAGE_MAX_SIZE = 1200
IMPORT_DOWNLOAD_TIMEOUT = 30
IMPORT_SIZE_LIMIT = 50000
IMPORT_FILE_SIZE_LIMIT = 100
MESTO_BRANCH = 'master' 

MESTO_CAPITAL_SLUG = 'kiev'
MESTO_SITE = 'mesto'  # mesto, nesto

# Заполнять или нет поля с размерами исходной картинки у ad.Photo
MESTO_UPDATE_DIMENSION_FIELDS_FOR_PHOTOS = True
MESTO_DOMRIA_IGNORE_USERS = None
MESTO_DOMRIA_IGNORE_ADS = None
MESTO_DOMRIA_PRIORITY_ADS = None
MESTO_USE_GEODJANGO = False
MESTO_SUSPICIOUS_IP = [] # подозрительные IP, при регистрации с которых высылается уведомление на info@mesto.ua

MESTO_TASK_QUEUES = [
    'important',
    'photo_download',
    'process_photo',
    'process_address',
    'import_',
]
MESTO_TASK_QUEUES_SYNCRONOUS_EXECUTION = True
MESTO_TASK_QUEUES_REDIS_CONNECTION = {}

MESTO_ASTERISK_SETTINGS = {
    'host':'93.183.214.156',
    'port':5038,
    'username':'mestoua_site',
    'secret':'K,hOd+Fr!jHA3SNw'
}
MESTO_PROXIES = []
NEED_SEO_BLOCK = True
NEWS_CATEGORIES = ('news', 'events', 'places', 'must_know')
PAYMENT_SYSTEM_DEFAULT = 'liqpay'
PAYMENT_SYSTEMS = {
    'interkassa_old': {
        'SHOP_ID': '5326e40fbf4efc4903dd23c3',
        'SECRET': 'SyNE6sVZhmInrsa6',
    },
    'interkassa2': {
        'SHOP_ID': '573ad3613d1eaf80548b4571',
        'SECRET': 'pupW6iBsuZp3Enj8',
    },
    'copayco': {
        'SHOP_ID': '5033196d',
        'SECRET': '40FADDBA0C13F91854574EB227375428DEDDC8CC2D66864466B2DA63ADC75177',
    },
    'pelipay': {
        'HOST': 'mesto.ua',
        'SECRET_KEY': 'cg1frONUd8SHyfET8rAtiSs0Thx1Rlie',
        'API_URL': 'http://api.pelipay.com/',
    },
    'liqpay': {
        'PUBLIC_KEY': 'i79389434675',
        'PRIVATE_KEY': 'Zc8HCUGH4UyssSjI1Hx1sDbjubXNICNnW7zwHQR1',
    },
    'liqpay2': {
        'PUBLIC_KEY': 'i41452220204',
        'PRIVATE_KEY': '9z2OjUG3Jio9sZ5d9EyZryfJccYuSadTxCNoUtac',
    }
}
PROPERTY_SEARCH_AUTOCOMPLETE = False


PUSH_NOTIFICATIONS_SETTINGS = {
    # на самом деле FCM_API_KEY
    "GCM_API_KEY": "AAAAqjnCx40:APA91bErt3GHFsiQ5QRKLQmuXJx7P3gredu526xo_cC9kPRBKuS-ADdHXvpJOooP8J3wz4dbcZUzg5pLeZp6U0cwhKHd7sf_WgRsiVGUlKFzBZOKM03mP75x_7NccBWNikGsl_yAV99A",
    "GCM_POST_URL": 'https://fcm.googleapis.com/fcm/send',
}


# ShieldSquare - защита от ботов
SHIELDSQUARE = {
    'sid': 'ea12368c-f965-4c70-9f4e-918e270aef03', # указан sid для песочницы, для продакшена нужно переоределить в settings_local
    'mode': 'Monitor', # 'Active'/'Monitor';
    'ss2_domain': 'ss_ew.shieldsquare.net',
    'logger': True,
    'timeout': 1.0,
}

# UPD 28.07.2015: В сентябре для пользователей HTTP Геокодера, отправляющих запросы без ключа, а также для пользователей JS Геокодера, не передающих реферер или ключ, вступят в силу территориальные ограничения. Геокодирование будет доступно в пределах России, Украины, Беларуси, Казахстана, Грузии, Абхазии, Южной Осетии, Армении, Азербайджана, Молдовы, Туркмении, Таджикистана, Узбекистана, Киргизии и Турции. Если вам нужен поиск за границами этих стран, необходимо получить ключ и отправлять запросы с ним.
YANDEX_MAPS_API_KEYS = [
    'ACPQOU4BAAAASoUEMQIA1a-zlbTMMxrUAQStCACQcIL9NfkAAAAAAAAAAAA86G_LZM7F26mk0A6IiG9f7IVhDg==',
    'APRXB04BAAAABSpEfQMAmZWikwwmAe_j45O_sKDu01jRPqQAAAAAAAAAAAA6b-x3-Xlc611Pt4ZrRHHjUs3yDQ==',
    'AEey0E0BAAAAy-IjJQUA3zNAB8-PafLhdmbVmt3DYm6EZUIAAAAAAAAAAAC9izjNAb9QSVB3xK7dtCjZFyswwg==',
]

YANDEX_TRANSLATOR_KEYS = [
    'trnsl.1.1.20150430T050543Z.51f92ae06e5703e4.998ca769e03cf37dbdeb15900b196f787398a49b',
    'trnsl.1.1.20150813T074112Z.43852008ace10c00.d76f3f75dcd4ab3a5cb902fbd38e3a7d1bd1a2ab',
    'trnsl.1.1.20160302T162708Z.a0e7b80b34585471.bb8fef97f6c5f6f41f639a04e6b1d87da197a046',
]

GOOGLE_API_KEY = 'AIzaSyAzCakiPuD2-mV67bUOn4oItsC7jB4Hk9g'
GOOGLE_API_HOST = 'https://www.googleapis.com'

from settings_local import *

