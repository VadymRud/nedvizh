# coding: utf-8
from __future__ import unicode_literals

import datetime
import traceback

import pynliner
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management import BaseCommand
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from custom_user.models import User
from ppc.models import LeadGeneration

from utils.email import make_ga_pixel_dict, make_utm_dict


class Command(BaseCommand):
    leave_locale_alone = True
    help = 'Уведомление пользователей при работе с услугой Выделенный номер'

    def handle(self, *args, **options):
        users_id = LeadGeneration.objects.filter(
            dedicated_numbers=True, user__in=User.get_user_ids_with_active_ppk()).values_list('user', flat=True)

        # Уведомляем об окончании услуги Выделенный номер за день до окончания
        service_will_end_for_users = User.objects.filter(
            Q(transactions__type=80, receive_sms=True, id__in=users_id) & (
                Q(transactions__time__range=(
                    datetime.datetime.now() - datetime.timedelta(days=29),
                    datetime.datetime.now() - datetime.timedelta(days=28)
                ))
            )
        ).distinct().order_by('id')
        print '--> Start beforehand notification by sms', datetime.datetime.now()
        text = u'Завтра заканчивается срок действия услуги "Выделенный номер". Пополните баланс на 100 грн'
        for user in service_will_end_for_users:
            # если на балансе есть 100 грн, то за номер выделенный нлмер автоматически спишется
            if user.get_balance() < 100:
                print '  --> user #%d' % user.id
                user.send_notification(text)

        # Уведомляем об окончании услуги Выделенный номер за 7, 3 и в день окончания предоставления услуги
        service_will_end_for_users = User.objects.filter(
            Q(transactions__type=80, subscribe_info=True, id__in=users_id) & (
                Q(transactions__time__range=(
                    datetime.datetime.now() - datetime.timedelta(days=23),
                    datetime.datetime.now() - datetime.timedelta(days=22)
                )) |
                Q(transactions__time__range=(
                    datetime.datetime.now() - datetime.timedelta(days=27),
                    datetime.datetime.now() - datetime.timedelta(days=26)
                )) |
                Q(transactions__time__range=(
                    datetime.datetime.now() - datetime.timedelta(days=30),
                    datetime.datetime.now() - datetime.timedelta(days=29)
                ))
            )
        ).distinct().order_by('id')
        print '--> Start beforehand notification', datetime.datetime.now()

        utm = make_utm_dict(utm_campaign='ppc_notification')
        for user in service_will_end_for_users:
            print '  --> user #%d' % user.id

            translation.activate(user.language)

            # Количество дней до окончания тарифа
            days = 30 - (datetime.datetime.now() - user.transactions.filter(type=80).first().time).days
            content = render_to_string(
                'ppc/mail/ppc-notification-beforehand.jinja.html',
                {
                    'utm': utm,
                    'ga_pixel': make_ga_pixel_dict(user, utm),
                    'days': days
                }
            )
            content_with_inline_css = pynliner.fromString(content)

            message = EmailMessage(
                _('Заканчивается срок действия абон.платы услуги "Выделенный номер"'), content_with_inline_css,
                settings.DEFAULT_FROM_EMAIL, [user.email])
            message.content_subtype = 'html'
            message.send()

        # Уведомляем пользователей о неактивной услуге Выделенный номер
        # на следующий день после окончания услуги и через неделю
        print '--> Start afterward notification', datetime.datetime.now()
        service_ended_for_users = User.objects.filter(
            Q(transactions__type=80, subscribe_info=True) & (
                Q(transactions__time__range=(
                    datetime.datetime.now() - datetime.timedelta(days=32),
                    datetime.datetime.now() - datetime.timedelta(days=31)
                )) |
                Q(transactions__time__range=(
                    datetime.datetime.now() - datetime.timedelta(days=39),
                    datetime.datetime.now() - datetime.timedelta(days=38)
                ))
            )
        ).distinct().order_by('id')

        for user in service_ended_for_users:
            # Если у пользователя не было транзакций за Выделенный номер за последние 7 дней
            if not user.transactions.filter(
                    type=80, time__gte=(datetime.datetime.now() - datetime.timedelta(days=7))).exists():
                print '  --> user #%d' % user.id

                translation.activate(user.language)

                content = render_to_string(
                    'ppc/mail/ppc-notification-afterward.jinja.html',
                    {
                        'utm': utm,
                        'ga_pixel': make_ga_pixel_dict(user, utm)
                    }
                )
                content_with_inline_css = pynliner.fromString(content)

                message = EmailMessage(
                    _('Закончился срок действия абон.платы услуги "Выделенный номер"'), content_with_inline_css,
                    settings.DEFAULT_FROM_EMAIL, [user.email])
                message.content_subtype = 'html'
                message.send()

