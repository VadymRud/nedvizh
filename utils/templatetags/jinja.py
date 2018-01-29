# coding: utf-8
from django_jinja import library
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe
from django.utils.timezone import get_current_timezone
from django import forms
from django.urls import translate_url

from django_hosts.resolvers import reverse

from pytils.numeral import get_plural
from jinja2 import Markup, escape

from utils.thumbnail import get_lazy_thumbnail, get_options
from utils import gtm
from ad import phones
from banner.models import Banner
from profile.forms import RegistrationForm

import pytils
import re
import json
import datetime

TAG_RE = re.compile(r'<[^>]+>')


@library.global_function
def make_gtm_data(request):
    return json.dumps(gtm.make_gtm_data(request))


@library.filter
def thumbnail(file_, size, nocrop=False, **options):
    if not options:
        options = get_options(size, nocrop, **options)
    return get_lazy_thumbnail(file_, size, **options)


@library.filter
def pluralize(*args):
    return get_plural(*args)


@library.filter
def time_ago(value, accuracy=1):
    return pytils.dt.distance_of_time_in_words(value, accuracy)


@library.global_function
def host_url(*args, **kwargs):
    return reverse(*args, **kwargs)


@library.global_function
def get_parent_host():
    return settings.MESTO_PARENT_HOST


@library.filter
def hide_contacts(string, target=''):
    string = TAG_RE.sub('', string)  # вырезание тегов
    return mark_safe(
        u'<a title="Узнать номер" class="show-contacts" data-target="%s">%s%s</a>' % (
            target, string[:3], re.sub(r"[\da-zA-Z]", "*", string[3:])
        )
    )


@library.filter
def nl2br(value):
    _paragraph_re = re.compile(r'(?:\r\n|\r(?!\n)|\n){2,}')
    result = u'\n\n'.join(u'<p>%s</p>' % p.replace('\n', Markup('<br>\n')) \
                          for p in _paragraph_re.split(escape(value)))
    return Markup(result)


@library.filter
def to_json(value):
    return mark_safe(json.dumps(value))


@library.filter
def remove_control_chars(text):
    if text:
        return text.translate(dict(dict.fromkeys(set(range(32)) - set([10, 13])), **{9: u' '}))


@library.filter
def split(string, separator=' '):
    return string.strip(separator).split(separator)


@library.filter
def isoformat(time):
    return get_current_timezone().localize(time.replace(microsecond=0), is_dst=True).isoformat()


# Forms

@library.filter
def add_class(field, *new_classes):
    widget = field.field.widget
    if isinstance(widget, forms.MultiWidget):
        widgets = widget.widgets
    else:
        widgets = [widget]
    for widget in widgets:
        classes = widget.attrs.pop('class', '').split(' ')
        classes.extend(new_classes)
        widget.attrs['class'] = ' '.join(classes)
    return field


@library.filter
def add_attrs(field, **attrs):
    field.field.widget.attrs.update(attrs)
    return field


@library.filter
def add_data(field, **attrs):
    field.field.widget.attrs.update({'data-%s' % key: value for key, value in attrs.items()})
    return field


@library.global_function
def merge_forms_with_formsets(form, formsets):
    formsets = formsets or []
    forms = [form]
    for formset in formsets:
        forms.extend(formset)
    return forms


@library.filter
def check_forms_errors(forms):
    return any(form.errors for form in forms)


@library.filter
def pprint_phone(raw_phone):
    return phones.pprint_phone(raw_phone)


@library.global_function
def get_language_menu(request):
    from django.core.urlresolvers import reverse

    menu = []
    for language_code, language_name in settings.LANGUAGES:
        if settings.MESTO_SITE == 'mesto' and language_code == 'hu':
            continue
        else:
            translated_url = translate_url(request.get_full_path(), language_code)

            if request.user.is_authenticated():
                url = '%s?next=%s' % (
                    reverse('profile_set_language', args=[language_code]),
                    translated_url
                )
            else:
                url = translated_url

            item = (language_name, url)

            if language_code == request.LANGUAGE_CODE:
                menu.insert(0, item)
            else:
                menu.append(item)
    return menu


@library.global_function
def get_registration_form():
    return RegistrationForm()


@library.global_function
def is_mesto_office_open():
    ''' поддержка работает с 9:00 до 18:00 в будние дни '''
    now = datetime.datetime.now()

    return (9 <= now.hour < 18) and (now.weekday() < 6)


@library.global_function
def get_mainmenu(request, region_slug, region):
    menu = []

    if request.subdomain and request.subdomain != 'international':
        host_args = guide_host_args = [request.subdomain]
    else:
        host_args = []
        guide_host_args = [settings.MESTO_CAPITAL_SLUG]
    international_host_args = ['international']

    # основные разделы с объявлениями
    ad_sections = (
        ('sale', _(u'Продажа')),
        ('rent', _(u'Аренда')),
        ('rent_daily', _(u'Посуточно')),
    )
    kwargs = dict(region_slug=region_slug) if region_slug and request.subdomain != 'international' else {}
    dealtype_menu = []
    for section_deal_type, label in ad_sections:
        kwargs['deal_type'] = section_deal_type
        dealtype_menu.append((reverse('ad-search', kwargs=kwargs, host_args=host_args), label))
    menu.append(('#', _(u'Тип сделки'), {'submenu': dealtype_menu, 'check_active': False}))

    # новостройки
    menu.append((reverse('ad-search', kwargs={'deal_type': 'newhomes'}, host_args=host_args), _(u'Новостройки')))

    # Новости рынка (Путеводитель
    guide_item = (reverse('guide:category_list', kwargs={'category': 'news'}, host_args=host_args), _(u'Новости рынка'), {})

    guide_sections = (
        ('news', _(u'Новости')), ('events', _(u'События')), ('places', _(u'Места')), ('must_know', _(u'Стоит знать')))

    guide_item[2]['submenu'] = [
        (reverse('guide:category_list', kwargs={'category': key}, host_args=guide_host_args), name) for key, name in guide_sections
    ]
    guide_item[2]['submenu'].append((reverse('school:index'), _(u'Mesto School')))

    menu.append(guide_item)

    # Профессионалы
    professionals_item = [reverse('professionals:search', host_args=host_args), _(u'Профессионалы')]
    if region and region.kind == 'province':
        professionals_item[0] += '?users__region=%s' % region.id
    menu.append(professionals_item)

    international_item = (reverse('index', host_args=international_host_args), _(u'За рубежом'), {'js_link': 1, 'submenu': [
        (reverse('ad-search', kwargs={'deal_type': 'sale'}, host_args=international_host_args), _(u'Продажа')),
        (reverse('ad-search', kwargs={'deal_type': 'rent'}, host_args=international_host_args), _(u'Аренда')),
    ], 'classes': ['active'] if request.subdomain == 'international' else []})
    menu.insert(4, international_item)

    # Услуги
    menu.append((reverse('services:legal_services'), _(u'Полезные услуги'), {'submenu':
        [
            (reverse('services:tour360'), _(u'Панорама 360'), {'target': '_blank'}), 
            # (reverse('services:analysis'), _(u'Экспертная проверка жилья')),
            (reverse('services:ocenka_nedvizh'), _(u'Оценка недвижимости')),
            (reverse('services:notary'), _(u'Услуги нотариуса')),
            ('http://promo.mesto.ua/brochure-design/', _(u'Дизайн брошюр для недвижимости'), {'target':'_blank', 'classes':['label-new']}),
            ('http://promo.mesto.ua/banner_prodaz/', _(u'Печать баннера'), {'target':'_blank', 'classes':['label-new']}),
            ('http://promo.mesto.ua/lending-osmo-mobile/', _(u'Стабилизатор для видео'), {'target':'_blank', 'classes':['label-new']}),
            ('http://promo.mesto.ua/professional-video-photo-shoot/', _(u'Фото-видео съемка'), {'target':'_blank', 'classes':['label-new']}),
            (reverse('services:interior3d'), _(u'3D визуализация'), {'classes':['label-new']}),
        ]
    }))

    return menu


@library.global_function
def get_alternate(request):
    if request.LANGUAGE_CODE == 'uk':
        alternate_language = 'ru'
    elif request.LANGUAGE_CODE == 'ru':
        alternate_language = 'uk'

    original_url = request.build_absolute_uri()
    alternate_url = translate_url(original_url, alternate_language)

    if alternate_url == original_url:
        # из-за неудачной реализации блока "seo" и остальных метатегов для сео в базовом шаблоне
        # (нужно рефакторить, чтобы удалять все это в шаблонах для страниц-ошибок)
        # приходится обрабатывать и такую ситуацию
        # TODO: разобраться с шаблонами чтобы get_alternate не вызывалсь где не нужно
        return None
    else:
        return {'url': alternate_url, 'language': alternate_language}


@library.global_function
def get_banner(request, place):
    for banner in Banner.active_banners.filter(place=place):
        if not banner.targeting_pages:
            return banner
        else:
            for url in banner.targeting_pages.split('\n'):
                if url.strip() in request.build_absolute_uri():
                    return banner
