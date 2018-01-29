# coding: utf-8

from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from django.utils import translation
from django.conf import settings
from django.core.mail import EmailMessage

from custom_user.models import User
from ppc.models import ActivityPeriod

import pynliner

import datetime

from utils.email import make_ga_pixel_dict, make_utm_dict


class Command(BaseCommand):
    def handle(self, *args, **options):
        now = datetime.datetime.now()
        print 'start', now

        # интервал запуска команды (должен совпадать с кроном), если потребуется чаще, можно будет сделать опцию --interval
        interval = datetime.timedelta(days=1)

        for expiration_days_delta in (-7, -3, -1, 0, +3, +7, +15):
            userplan_end_range = [
                now - datetime.timedelta(days=expiration_days_delta) - interval,
                now - datetime.timedelta(days=expiration_days_delta),
            ]

            users_to_mail = User.objects.filter(
                is_active=True,
                email__gt='',
                subscribe_info=True,
                user_plans__end__range=userplan_end_range,
            ).exclude(
                user_plans__end__gt=userplan_end_range[1],  # для продленных тарифов
            ).exclude(
                id__in=ActivityPeriod.objects.filter(end=None).values('user')
            )

            utm = make_utm_dict(utm_campaign='Prodolzhenie_paketa', utm_term='Uslugi')
            for user in users_to_mail:
                print 'mail: user #%d, expiration_days_delta=%d' % (user.id, expiration_days_delta)

                translation.activate(user.language)
                subject = _(u'Напоминание об окончании тарифного плана')

                if expiration_days_delta < 0:
                    content = render_to_string('paid_services/mail/plan_expired_before.jinja.html', {'days_before': -expiration_days_delta})
                elif expiration_days_delta == 0:
                    content = render_to_string(
                        'paid_services/mail/plan_expired.jinja.html',
                        {
                            'utm': utm,
                            'ga_pixel': make_ga_pixel_dict(user, utm)
                        }
                    )

                elif expiration_days_delta > 0:
                    content = render_to_string('paid_services/mail/plan_expired_after.jinja.html', {'days_after': expiration_days_delta})
                    subject = _(u'Ваш аккаунт неактивен')

                content_with_inline_css = pynliner.fromString(content)

                message = EmailMessage(subject, content_with_inline_css, settings.DEFAULT_FROM_EMAIL, [user.email])
                message.content_subtype = 'html'
                message.send()
