# coding: utf-8

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.conf import settings
from django.http import HttpResponseForbidden
from django import forms
from django.apps import apps

from babel.messages.pofile import read_po, write_po

from i18n.management.commands.update_po import get_apps_to_translate

import os

languages_to_translate = [
    language_code for language_code, language_name in settings.LANGUAGES if language_code != settings.LANGUAGE_CODE
]

def can_translate(view_func):
    def wrapped_view_func(request, *args, **kwargs):
        if request.user.is_superuser or request.user.groups.filter(id=13).exists():
            return view_func(request, *args, **kwargs)
        else:
            return HttpResponseForbidden(u'Доступ запрещен')
    return wrapped_view_func

def get_po_path(directory, language, domain):
    return os.path.join(directory, 'locale', language, 'LC_MESSAGES', '%s.po' % domain)

@staff_member_required
@can_translate
def translate_index(request):
    pofiles_table = []

    for app_label, directory in [(None, settings.BASE_DIR)] + [(app_config.label, app_config.path) for app_config in get_apps_to_translate()]:
        for domain in ('django', 'djangojs'):
            pofiles = []
            for language_code, language_verbose in settings.LANGUAGES:
                if language_code != settings.LANGUAGE_CODE:
                    pofile_path = get_po_path(directory, language_code, domain)
                    if os.path.exists(pofile_path):
                        link = reverse('admin:translate:edit', kwargs={'app_label': app_label, 'language': language_code, 'domain': domain, 'filter': 'all'})
                        with open(pofile_path, 'rb') as po_fileobj:
                            catalog = read_po(po_fileobj, locale=language_code)
                        stats = get_stats(catalog)
                        pofiles.append({'language': language_code, 'link': link, 'stats': stats})
                    else:
                        pofiles.append(None)
            if any(pofiles):
                pofiles_table.append({'app_label': app_label, 'domain': domain, 'pofiles': pofiles})

    context = dict(
        admin.site.each_context(request),
        pofiles_table=pofiles_table,
    )
    return render(request, 'i18n/admin/translate_index.html', context)

class MessageForm(forms.Form):
    string = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': '4'}))

def make_pluralizable_form_class(num_plurals):
    base_attrs = {'required': False, 'widget': forms.Textarea(attrs={'rows': '4'})}

    if num_plurals == 3:
        class PluralizableMessageForm(forms.Form):
            string_0 = forms.CharField(label='1', **base_attrs)
            string_1 = forms.CharField(label='2-4', **base_attrs)
            string_2 = forms.CharField(label=u'5-20...', **base_attrs)
    elif num_plurals == 2:
        class PluralizableMessageForm(forms.Form):
            string_0 = forms.CharField(label='1', **base_attrs)
            string_1 = forms.CharField(label='>1', **base_attrs)
    elif num_plurals == 1:
        class PluralizableMessageForm(forms.Form):
            string_0 = forms.CharField(label='', **base_attrs)
    else:
        raise Exception('Unexpected num_plurals=%s' % num_plurals)
    return PluralizableMessageForm


def get_stats(catalog):
    stats = {'total': 0, 'translated': 0}
    for message in catalog:
        if message.id != '':
            stats['total'] += 1
            if (message.pluralizable and any(message.string)) or (not message.pluralizable and message.string):
                stats['translated'] += 1
    stats['translated_rate'] = (float(stats['translated']) / stats['total']) * 100
    return stats


@staff_member_required
@can_translate
def translate_edit(request, language, app_label, domain, filter):
    if app_label is None:
        po_path = get_po_path(settings.BASE_DIR, language, domain)
    else:
        app_config = apps.get_app_config(app_label)
        po_path = get_po_path(app_config.path, language, domain)

    with open(po_path, 'rb') as po_fileobj:
        catalog = read_po(po_fileobj, locale=language)

    forms = []

    for index, message in enumerate(catalog):
        if filter == 'untranslated':
            if (message.pluralizable and any(message.string)) or (not message.pluralizable and message.string):
                continue

        if message.id == '':
            continue

        prefix = 'form-%d' % index
        initial = {'message': message}
        if message.pluralizable:
            for i in xrange(catalog.num_plurals):
                initial['string_%d' % i] = message.string[i]
            form_class = make_pluralizable_form_class(catalog.num_plurals)
        else:
            initial['string'] = message.string
            form_class = MessageForm

        if request.method == 'POST':
            form = form_class(request.POST, initial=initial, prefix=prefix)
        else:
            form = form_class(initial=initial, prefix=prefix)

        forms.append((index, form))

    if request.method == 'POST':
        for index, form in forms:
            if not form.is_valid():
                raise Exception('Invalid form: %s' % form.errors)

        changed = False

        for index, form in forms:
            if form.has_changed():
                changed = True
                message = form.initial['message']

                if message.pluralizable:
                    message.string = [clean_string(form.cleaned_data['string_%d' % i]) for i in xrange(catalog.num_plurals)]
                else:
                    message.string = clean_string(form.cleaned_data['string'])

        if changed:
            with open(po_path, 'wb') as po_fileobj:
                write_po(po_fileobj, catalog)

        kwargs = {'language': language, 'domain': domain, 'filter': filter}
        if app_label:
            kwargs['app_label'] = app_label
        return redirect(reverse('admin:translate:edit', kwargs=kwargs))

    base_kwargs = {'language': language, 'domain': domain}
    if app_label:
        base_kwargs['app_label'] = app_label

    context = dict(
        admin.site.each_context(request),
        forms=forms,
        po_file_repr=make_po_file_repr(language, app_label, domain),
        stats=get_stats(catalog),
        filter=filter,
        filter_urls = {
            'all': reverse('admin:translate:edit', kwargs=dict(base_kwargs, filter='all')),
            'untranslated': reverse('admin:translate:edit', kwargs=dict(base_kwargs, filter='untranslated')),
        },
    )

    return render(request, 'i18n/admin/translate_edit.html', context)

def clean_string(s):
    return s.replace('\r\n', '\n')

def make_po_file_repr(language, app_label, domain):
    if app_label:
        return '%s:%s-%s' % (language, app_label, domain)
    else:
        return '%s:%s' % (language, domain)
