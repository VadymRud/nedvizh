# coding: utf-8

from django.db import models
from django.conf import settings
from django.db.models import Sum
from django.db.models.signals import pre_save
from django.db.models.functions import Coalesce
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.utils import translation

from ad.models import Ad
from paid_services.models import InsufficientFundsError, PaidPlacement

from dirtyfields import DirtyFieldsMixin
from jsonfield import JSONField
from lxml import etree
import requests

import time
import datetime
import json

class ImportTaskError(Exception):
    pass

IMPORTTASK_STATUS_CHOICES = (
    ('waiting', u'ожидает'),
    ('processing', u'выполняется'),
    ('waiting_for_importadtasks', u'ожидает завершения подзадач'),
    ('completed', u'завершена'),
)

class ImportTask(models.Model, DirtyFieldsMixin):
    class Meta:
        verbose_name = u'задача импорта'
        verbose_name_plural = u'задачи импорта'

    agency = models.ForeignKey('agency.Agency', verbose_name=u'агентство', related_name='importtasks')
    url = models.URLField(u'ссылка на файл', max_length=100)
    created = models.DateTimeField(u'создана', auto_now_add=True)
    started = models.DateTimeField(u'стартовала', null=True, blank=True)
    completed = models.DateTimeField(u'завершена', null=True, blank=True)
    status = models.CharField(u'статус', max_length=30, default='waiting', choices=IMPORTTASK_STATUS_CHOICES)
    error = models.CharField(u'ошибка', max_length=100, null=True, blank=True)
    stats = JSONField(u'статистика', blank=True, default=dict)
    is_test = models.BooleanField(u'тест?', default=False)

    def perform(self):
        self.status = 'processing'
        self.save()

        try:
            content = self._download_file(self.url)
            root = self._parse(content)

        except ImportTaskError, message:
            self.error = message
            self.status = 'completed'
            self.save()
        else:
            if not self.is_test:
                raw_xml_ids = [tag.text.strip() for tag in root.iterfind('.//property//xml_id') if tag.text]
                ads_to_deactivate = Ad.objects.filter(user__in=self.agency.get_realtors().values('user'), xml_id__gt='').exclude(xml_id__in=raw_xml_ids)
                self.stats['delete'] = ads_to_deactivate.update(status=211, is_published=False)

            for property_tag in root.iter('property'):
                self._create_importadtask(property_tag)

            self.status = 'waiting_for_importadtasks'
            self.save()

    def make_report(self):
        return render_to_string('import_/importtask_report.jinja.xml', {
            'importtask': self,
            'importadtasks_joined_reports': u''.join(self.importadtasks.values_list('report', flat=True)), # при join в шаблоне не удалось убрать escape
        })

    def _download_file(self, url):
        file_size_limit = settings.IMPORT_FILE_SIZE_LIMIT * 1024 * 1024
        socket_timeout = settings.IMPORT_DOWNLOAD_TIMEOUT
        total_timeout = settings.IMPORT_DOWNLOAD_TIMEOUT

        timeout_exception_message = u'Превышен таймаут скачивания файла'

        start = time.time()

        try:
            r = requests.get(url, timeout=socket_timeout, stream=True, verify=False)
        except requests.exceptions.Timeout:
            raise ImportTaskError(timeout_exception_message)
        except requests.exceptions.RequestException:
            # в обход ImportTaskError, чтобы оригинальное исключение попадало в лог для отладки
            self.error = u'Ошибка при скачивании файла'
            self.status = 'completed'
            self.save()
            raise
        else:
            content = ''

            for chunk in r.iter_content(1024):
                if len(content) > file_size_limit:
                    raise ImportTaskError(u'Превышен максимальный размер файла')
                elif (time.time() - start) > total_timeout:
                    raise ImportTaskError(timeout_exception_message)
                else:
                    content += chunk

            return content

    def _parse(self, content):
        parser = etree.XMLParser(encoding='UTF-8')
        try:
            root = etree.XML(content, parser)
        except etree.XMLSyntaxError:
            raise ImportTaskError(u'Ошибка синтаксического анализа XML')
        else:
            if root.tag == 'properties':
                if (1 <= root.xpath('count(//property)') <= settings.IMPORT_SIZE_LIMIT):
                    return root
                else:
                    message = u'Элемент <properties> должен содержать от 1 до %s элементов <property>' % settings.IMPORT_SIZE_LIMIT
                    raise ImportTaskError(message)
            else:
                raise ImportTaskError(u'Не найден корневой элемент <properties>')

    def _create_importadtask(self, property_tag):
        importadtask = ImportAdTask(
            importtask=self, 
            xml=etree.tostring(property_tag, encoding='UTF-8', with_tail=False) # тег будет корневым, поэтому необходимо убрать "tail"
        )
        importadtask.save()

        import tasks
        tasks.perform_importadtask(importadtask.id)

    def complete(self):
        for action, count in self.importadtasks.filter(errors__isnull=True).values_list('action').annotate(models.Count('action')):
            self.stats[action] = count
        self.stats['errors'] = self.importadtasks.filter(errors__isnull=False).count()
        self.status = 'completed'
        self.save()

    @staticmethod
    def get_queryset_to_complete():
        return ImportTask.objects.filter(status='waiting_for_importadtasks').exclude(importadtasks__status__in=['waiting', 'processing'])

ad_attrs = [
    'xml_id',
    'source_url',
    'deal_type', 'property_type',
    'description',
    'rooms',
    'addr_country', 'addr_city', 'addr_street', 'addr_house',
    'price', 'currency',
    'area', 'area_living', 'area_kitchen',
    'floor', 'floors_total',
    'building_type', 'building_type_other', 'building_layout', 'building_walls', 'building_windows', 'building_heating',
    'guests_limit',
    'contact_person',
    'without_commission',
]

IMPORTADTASK_STATUS_CHOICES = (
    ('waiting', u'ожидает'),
    ('processing', u'выполняется'),
    ('completed', u'завершена'),
)

IMPORTADTASK_ACTION_CHOICES = (
    ('add', u'добавление'),
    ('update', u'обновление'),
)

class ImportAdTask(models.Model, DirtyFieldsMixin):
    class Meta:
        verbose_name = u'задача импорта объявления'
        verbose_name_plural = u'задачи импорта объявления'

    importtask = models.ForeignKey('import_.ImportTask', verbose_name=u'задача импорта', related_name='importadtasks')
    created = models.DateTimeField(u'создана', auto_now_add=True)
    started = models.DateTimeField(u'стартовала', null=True, blank=True)
    completed = models.DateTimeField(u'завершена', null=True, blank=True)
    xml = models.TextField(u'фрагмент файла')
    raw_xml_id = models.CharField(u'индентификатор в файле', max_length=50, null=True, blank=True)
    status = models.CharField(u'статус', max_length=20, default='waiting', choices=IMPORTADTASK_STATUS_CHOICES)
    basead = models.ForeignKey('ad.BaseAd', verbose_name=u'объявление', null=True, blank=True, related_name='importadtasks')
    errors = models.TextField(u'ошибки', null=True, blank=True)
    action = models.CharField(u'действие', max_length=20, null=True, blank=True, choices=IMPORTADTASK_ACTION_CHOICES)
    report = models.TextField(u'фрагмент отчета', null=True)

    def perform(self):
        self.status = 'processing'
        self.save()

        raw_values = self._parse(self.xml)
        
        raw_xml_id = raw_values.get('xml_id')
        if raw_xml_id and len(raw_xml_id) > 50:
            self.raw_xml_id = raw_xml_id[:47] + '...'
        else:
            self.raw_xml_id = raw_xml_id

        agency = self.importtask.agency
        agency_admin_user = agency.get_admin_user()
        translation.activate(agency_admin_user.language)

        ad = Ad.objects.filter(user__in=agency.get_realtors().values('user'), xml_id__gt='', xml_id=raw_xml_id).first()

        if ad:
            self.action = 'update'
        else:
            ad = Ad(status=210)
            self.action = 'add'

        from forms import (ImportAdForm,
            create_import_facilities_formset,
            create_import_photos_formset,
            create_import_paidplacements_formset)

        from ad.forms import create_ad_phones_formset

        ad_form = ImportAdForm(raw_values, instance=ad)

        formsets = {
            'facilities': create_import_facilities_formset(raw_values['facilities']),
            'photos': create_import_photos_formset(raw_values['photos']),
            'phones': create_ad_phones_formset(raw_values['phones']),
            'paidplacements': create_import_paidplacements_formset(raw_values['paidplacements'])
        }

        if ad_form.is_valid() and all([formset.is_valid() for formset in formsets.values()]):
            ad_phones = filter(None, [form.cleaned_data['phone'] for form in formsets['phones']])
            realtors_having_ad_phones = agency.get_realtors().filter(user__phones__in=ad_phones).all()
            admin_user = agency.get_admin_user()
            if realtors_having_ad_phones:
                ad.user = realtors_having_ad_phones[0].user
            else:
                ad.user = agency_admin_user
            
            if not self.importtask.is_test:
                ad = ad_form.save()
                formsets['facilities'].update_ad(ad)
                formsets['photos'].update_ad(ad)
                formsets['phones'].update_phones_m2m(ad.phones_in_ad)

                if ad.region is None:
                    ad_form.add_error(None, u'Не удалось выполнить геокодирование адреса')
                else:
                    formsets['paidplacements'].clean_according_with_ad(ad)

                    for form in formsets['paidplacements']:
                        if form.is_valid():
                            paidplacement_type = form.cleaned_data['paidplacement']
                            if paidplacement_type == 'vip7':  # TODO: предупредить клиентов с импортом, сделать рассылку, потом через какое-то время убрать
                                paidplacement_type = 'vip'
                            try:
                                if ad.user == admin_user:
                                    ad.user.purchase_paidplacement(paidplacement_type)
                                else:
                                    ad.user.purchase_paidplacement(paidplacement_type, move_money_from_user=admin_user)
                            except InsufficientFundsError:
                                form.add_error('paidplacement', u'Недостаточно средств на счете')
                            except PaidPlacement.AlreadyExistError:
                                pass

        errors = self._extract_errors(ad_form, formsets)

        if errors:
            self.errors = json.dumps(errors, ensure_ascii=False)

            if not self.importtask.is_test and ad.status == 1:
                Ad.objects.filter(pk=ad.pk).update(status=210, is_published=False)
        else:
            if not self.importtask.is_test:
                if ad.status == 211:
                    Ad.objects.filter(pk=ad.pk).update(status=210, is_published=False)

                ad.user.activate_ads(pk=ad.pk)
                self.basead = ad

        if not self.importtask.is_test:
            self.report = self._make_report()

        self.status = 'completed'
        self.save()

    def get_ad_views(self):
        return self.basead.ad.viewscounts.aggregate(
            detail_views=Coalesce(Sum('detail_views'), 0),
            contacts_views=Coalesce(Sum('contacts_views'), 0),
        )

    def _make_report(self):
        return render_to_string('import_/importadtask_report.jinja.xml', {'importadtask': self})

    def _extract_errors(self, ad_form, formsets):
        errors = self._extract_form_errors(ad_form.errors)
        for formset_name, formset in formsets.iteritems():
            formset_errors = {}
            for order, formset_form_errors in enumerate(formset.errors, start=1):
                if formset_form_errors:
                    formset_errors[order] = self._extract_form_errors(formset_form_errors)
            if formset_errors:
                errors[formset_name] = formset_errors
        return errors

    def _extract_form_errors(self, form_errors):
        extracted_errors = {}
        for attr, errors in form_errors.as_data().items():
            extracted_errors[attr] = u'\n'.join([u'; '.join(error.messages) for error in errors])
        return extracted_errors

    def _parse(self, xml):
        parser = etree.XMLParser(encoding='UTF-8')
        property_tag = etree.XML(xml, parser)
        raw_values = {'addr_country': 'UA'}

        for attr in ad_attrs:
            tag = property_tag.find(attr)
            if tag is not None:
                if tag.text is None:
                    raw_values[attr] = None
                else:
                    raw_values[attr] = tag.text.strip()

        for many_attr, many_subattr in (
            ('facilities', 'facility_id'),
            ('phones', 'phone'),
            ('photos', 'photo_url'),
            ('paidplacements', 'paidplacement')):

            many_values = []
            for tag in property_tag.iterfind('.//%s//%s' % (many_attr, many_subattr)):
                if tag.text is None:
                    many_values.append(None)
                else:
                    many_values.append(tag.text.strip())
            raw_values[many_attr] = many_values

        return raw_values


@receiver(pre_save, sender=ImportTask)
@receiver(pre_save, sender=ImportAdTask)
def fix_status_change(sender, instance, **kwargs):
    if 'status' in instance.get_dirty_fields():
        if instance.status == 'processing':
            instance.started = datetime.datetime.now()
        elif instance.status == 'completed':
            instance.completed = datetime.datetime.now()

