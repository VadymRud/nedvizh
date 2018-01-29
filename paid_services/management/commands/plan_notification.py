# coding: utf-8
from __future__ import unicode_literals

import datetime

import pynliner
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management import BaseCommand
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from custom_user.models import User
from utils.email import make_ga_pixel_dict, make_utm_dict


class Command(BaseCommand):
    leave_locale_alone = True
    help = 'Напоминание о купленном тарифном плане и отсуствующих объявлений'

    def handle(self, *args, **options):
        start_time_range = (datetime.datetime.now() - datetime.timedelta(days=6),
                            datetime.datetime.now() - datetime.timedelta(days=5))
        users = User.objects.filter(user_plans__is_active=True, user_plans__ads_limit__gt=0,
                                    user_plans__start__range=start_time_range, ads_count=0, subscribe_info=True,
                                    email__gt='').distinct().order_by('id')

        print '--> Start to send notification', datetime.datetime.now()
        utm = make_utm_dict(utm_campaign='plan_notification')
        for user in users:
            print '  --> user #%d' % user.id

            translation.activate(user.language)

            content = render_to_string(
                'paid_services/mail/plan-notification.jinja.html',
                {
                    'utm': utm,
                    'ga_pixel': make_ga_pixel_dict(user, utm),
                    'plan': user.get_active_plan()
                }
            )
            content_with_inline_css = pynliner.fromString(content)

            message = EmailMessage(
                _('Активируйте свои объявления'), content_with_inline_css,
                settings.DEFAULT_FROM_EMAIL, [user.email])
            message.content_subtype = 'html'
            message.send()

        print '--> Finish to send notification', datetime.datetime.now()
