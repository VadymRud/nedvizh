# coding: utf-8

"""
API для работы с СМС сервисом www.marafon.eu
Doc: https://trello-attachments.s3.amazonaws.com/546252266eaec96d88de8704/55fab572599a926e3daab317/526e1617e2548ae899d12e4a5f25a1a8/MARAFON_SMS_bulk_API.pdf
"""
from django.conf import settings
import requests
import phonenumbers

class MarafonNumberError(Exception):
    pass

class MarafonSMS(object):
    _auth_login = None
    _auth_pass = None
    _host_url = 'http://sms.marafon-ukraine.com.ua/api.php'
    _message_xml = None
    _headers = {
        'Content-Type': 'application/xml'
    }

    @staticmethod
    def translit(text):
        symbols = (u"абвгдеёжзиіїйклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
                   u"abvgdeejziiijklmnoprstufhzcss'y'euaABVGDEEJZIIIJKLMNOPRSTUFHZCSS'Y'EUA")

        tr = {ord(a): ord(b) for a, b in zip(*symbols)}
        return text.translate(tr)

    def __init__(self, *args, **kwargs):
        self._auth_login = settings.MESTO_SMS_MARAFON_LOGIN
        self._auth_pass = settings.MESTO_SMS_MARAFON_PASSWORD

    def check_and_format_number(self, phone):
        """
            Проверка номера на валидность, а так же что это не городской номер.
            Страна принудительно выставлена UA, т.к. СМС отправляем только по украине
        """
        parsed_phone = phonenumbers.parse(phone, 'UA')
        if not phonenumbers.is_valid_number(parsed_phone) or parsed_phone.country_code != 380 or \
                phonenumbers.phonenumberutil.number_type(parsed_phone) == phonenumbers.phonenumberutil.PhoneNumberType.FIXED_LINE:
            raise MarafonNumberError('Number %s is not valid or using fixed line' % phone)

        # возвращаем в формате +380ххххххххх
        return phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.E164)

    def _send_request(self):
        """
        Отправляем сообщение для API

        :return:
        """

        if settings.DEBUG and not getattr(settings, 'MESTO_SEND_SMS_IN_DEBUG', False):
            print u'Send sms\n{}  '.format(self._message_xml)
            return True
            
        response = requests.post(
            self._host_url,
            auth=(self._auth_login, self._auth_pass),
            headers=self._headers,
            data=self._message_xml.encode('utf-8')
        )

        # TODO: ну хоть какие-то ошибки выводить надо, иначе вообше шляпа
        if 'error' in response.text:
            raise Exception(response.text)

        if response.status_code == 200:
            # По идее нужно разбирать статусы при некорректной отправке
            return True

        else:
            return False

    def send_message(self, phone, message, translit=False):
        """
        Подготавливаем и отправляем сообщение

        :param phone: Номер телефона в международном формате
        :param message: СМС сообщение
        :return:
        """

        try:
            phone = self.check_and_format_number(phone)
        except MarafonNumberError as e:
            print 'Error while sending sms. %s' % e
            return False

        if translit and len(message) > 70:
            message = self.translit(message)

        self._message_xml = '<message><service id="single" source="mesto-ua"/><to>%s</to>' \
                            '<body content-type="text/plain">%s</body></message>' % (phone, message)

        return self._send_request()

    def send_bulk_message(self, phones, message, bulk_id, translit=False):
        """
        Подготавливаем и отправляем сообщение

        :param bulk_id: Уникальный код рассылки
        :param phones: Номера телефонов в международном формате
        :param message: СМС сообщение
        :return:
        """

        if translit and len(message) > 70:
            message = self.translit(message)

        phone = ''.join(['<to>%s</to>' % phone for phone in phones])
        self._message_xml = '<message><service id="bulk" uniq_key="%s" source="mesto-ua"/>%s' \
                            '<body content-type="text/plain">%s</body></message>' % (bulk_id, phone, message)

        return self._send_request()
