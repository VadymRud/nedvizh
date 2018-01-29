#coding=utf-8
from django import forms
from django.utils.translation import ugettext_lazy as _

import models
import phonenumbers

import re

class InvalidPhoneException(Exception):
    pass

def validate(value):
    try:
        phone = phonenumbers.parse(value, "UA")
    except phonenumbers.NumberParseException:
        raise InvalidPhoneException()
    else:
        if not phonenumbers.is_valid_number(phone):
            raise InvalidPhoneException()
        return phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164)[1:]


class PhoneField(forms.CharField):
    widget = forms.TextInput(attrs={'class': 'masked-phone'})

    # ВАЖНО: на входе номер должен быть в международом формате (начинаться со знака плюс), либо такой номер
    # будет пытаться парситься как украинский
    def clean(self, value):
        value = super(PhoneField, self).clean(value)

        if not value:
            return None
        try:
            # TODO: этот хак нужно убрать,  изначально выводя в поле номер с плюсом
            if '+' not in value:
                value = '+' + value

            phone = validate(value)
        except InvalidPhoneException:
            raise forms.ValidationError(_(u"Некорректный номер %s") % value)
        else:
            return phone

class PhoneModelChoiceField(PhoneField, forms.ModelChoiceField):
    def clean(self, value):
        value = super(PhoneModelChoiceField, self).clean(value)
        phone, created = models.Phone.objects.get_or_create(number=value)
        return phone


def pprint_phone(number):
    if number.startswith('38'):
        number_re = number_regexps['ua']
        parts = number_re.match(number).groupdict()
        r = parts['remainder']
        parts['remainder'] = '-'.join((r[:-4], r[-4:-2], r[-2:]))
        return u'+%(country)s (%(code)s) %(remainder)s' % parts
    else:
        try:
            phone = phonenumbers.parse('+%s' % number, None)
            return phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        except phonenumbers.NumberParseException:
            return number

def pprint_phones(phones, with_link=True, delimiter=u', ', extension=''):
    if with_link:
        return delimiter.join(['<a href="tel:+%s%s">%s</a>' % (number, extension, pprint_phone(number)) for number in phones])
    else:
        return delimiter.join([pprint_phone(number) for number in phones])
        
inner_number_re = re.sub(r'\s*', '', 
    r'''
        03[1-8] (2 | [^2]\d) |
        04[13] (2 | [^2]\d) |
        045\d{2} |
        04[67] (2 | [^2]\d) |
        048 ([456]\d)? |
        05[1-5] (2 | [^2]\d) |
        056 ([35]\d | 4 | 6[35678]? | 9[0-3]?) |
        057 ([456]\d)? |
        061 (9 | [3-7]\d) |
        062 (3[679]? | [457]\d | 6[1279]? | 9[67]?) |
        064 (2 | [3467]\d | 5[3-6]?) |
        065 (2 | 4 | [56]\d) |
        069 2? |
        \d{3}
    '''
)
# uncomment next line to copy this regexp to phones_form.js
#print inner_number_re.encode('string-escape')

number_regexps = {
    'ua': re.compile(r'^(?P<country>38)(?P<code>%s)(?P<remainder>.*)$' % inner_number_re),
    'ru': re.compile(r'^(?P<country>7)(?P<code>\d{3})(?P<remainder>.*)$'),
}
