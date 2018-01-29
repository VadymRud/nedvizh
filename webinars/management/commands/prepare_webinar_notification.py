# coding: utf-8
import datetime
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.template.loader import render_to_string
import pynliner
from webinars.models import WebinarReminder, Webinar
from utils.marafon_api import MarafonSMS


class Command(BaseCommand):
    leave_locale_alone = True
    help = u'Проведение СМС рассылки'

    def handle(self, *args, **options):
        # Рассылаем СМС уведомление, при необходимости
        webinar_start_at = datetime.datetime.now() + datetime.timedelta(hours=+1)
        webinar_finish_at = webinar_start_at + datetime.timedelta(hours=+1)

        seminar_start_at = datetime.datetime.now() + datetime.timedelta(hours=+24)
        seminar_finish_at = seminar_start_at + datetime.timedelta(hours=+1)

        webinars = Webinar.objects.filter(
            Q(is_published=True) & (
                Q(start_at__range=(webinar_start_at, webinar_finish_at), type='webinar') |
                Q(start_at__range=(seminar_start_at, seminar_finish_at), type='seminar')
            )
        )

        for webinar in webinars:
            phone_reminder_list = WebinarReminder.objects.filter(
                webinar=webinar, is_sent_sms=False, phone__isnull=False
            ).exclude(phone='').values_list('phone', flat=True)

            if phone_reminder_list.exists():
                if webinar.type == 'seminar':
                    message = 'Zavtra v %s sostoitsya seminar MESTO.UA. ' \
                              'Podrobnosti otpravleni na vash E-mail. ' \
                              'Prihodite, budet interesno.' % webinar.start_at.strftime('%H:%M')
                else:
                    message = 'Segodnya v %s sostoitsya besplatnyiy webinar MESTO.UA. ' \
                              'Ssyilka dlya uchastiya na vashem E-mail. ' \
                              'Podklyuchaytes, budet interesno.' % webinar.start_at.strftime('%H:%M')

                phones = set(phone_reminder_list)
                sms_api = MarafonSMS()
                if len(phones) == 1:
                    result = sms_api.send_message(list(phones)[0], message)
                    WebinarReminder.objects.filter(webinar=webinar, phone=list(phones)[0]).update(is_sent_sms=result)

                else:
                    for phone in phones:
                        result = sms_api.send_message(phone, message)
                        WebinarReminder.objects.filter(webinar=webinar, phone=phone).update(is_sent_sms=result)

                print 'Messages have sent to %s' % ' '.join(phones)
