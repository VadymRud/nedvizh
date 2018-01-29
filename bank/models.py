# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import ugettext_lazy as _

import os
import uuid

def make_upload_path(instance, original_file_name):
    extension = os.path.splitext(original_file_name)[1]
    safe_file_name = ''.join([uuid.uuid4().hex, extension])
    return 'upload/bank/%s' % safe_file_name

class Bank(models.Model):
    class Meta:
        verbose_name = u'банк'
        verbose_name_plural = u'банки'

    name = models.CharField(_(u'название банка'), max_length=100)
    logo = models.ImageField(_(u'логотип'), upload_to=make_upload_path, blank=True, null=True)
    financing_conditions = models.TextField(_(u'условия финансирования'), null=True, blank=True)
    is_active = models.BooleanField(_(u'активный?'), default=True)

    def __unicode__(self):
        return self.name

def convert_to_bank(property_type):
    if property_type in ['flat', 'house']:
        return 'residential'
    if property_type == 'plot':
        return 'land'
    if property_type == 'commercial':
        return 'commercial'
    raise Exception('Cannot convert property_type "%s" to bank property type' % property_type)

def convert_to_ad(bank_property_type):
    if bank_property_type == 'residential':
        return ['flat','house']
    if bank_property_type == 'land':
        return ['plot']
    if bank_property_type == 'commercial':
        return ['commercial']
    raise Exception('Cannot convert bank_property_type "%s" to ad property types' % bank_property_type)
