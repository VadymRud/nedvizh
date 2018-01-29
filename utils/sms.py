# coding: utf-8
from django.conf import settings
from django.conf import settings

import phonenumbers
import requests
import transliterate


class MarafonException(Exception):
    pass


def transliterate_for_sms(original_text):
    transliterated_as_ru = transliterate.translit(original_text, 'ru', reversed=True)
    transliterated_as_ru_with_fixed_uk_symbols = transliterate.translit(transliterated_as_ru, 'uk', reversed=True)
    return transliterated_as_ru_with_fixed_uk_symbols


def send_sms(phone_numbers, text):
    for phone_number in phone_numbers:
        if settings.DEBUG:
            print 'SMS to %s: %s' % (phone_number, text)
            continue

        xml = u'''
            <message>
                <service id="single" source="mesto-ua"/>
                <to>%s</to>
                <body content-type="text/plain">%s</body>
            </message>''' % (phone_number, text)

        r = requests.post(
            'http://sms.marafon-ukraine.com.ua/api.php',
            auth=(settings.MESTO_SMS_MARAFON_LOGIN, settings.MESTO_SMS_MARAFON_PASSWORD),
            headers={'Content-Type': 'application/xml'},
            data=xml
        )

        if r.status_code == 200:
            if 'error' in r.text:
                raise MarafonException('Internal Marafon error "%s"' % r.text)
        else:
            raise MarafonException('Bad Marafon response, status_code=%s' % r.status_code)


def clean_numbers_for_sms(raw_numbers):
    cleaned_numbers = []
    for raw_number in raw_numbers:
        parsed_phone = phonenumbers.parse(raw_number, 'UA')
        if (
            phonenumbers.is_valid_number(parsed_phone) and
            parsed_phone.country_code == 380 and
            phonenumbers.phonenumberutil.number_type(parsed_phone) != phonenumbers.phonenumberutil.PhoneNumberType.FIXED_LINE
        ):
            cleaned_number = phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.E164)
            cleaned_numbers.append(cleaned_number)
    return cleaned_numbers

