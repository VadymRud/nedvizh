# coding: utf-8
import pynliner
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.utils import translation

from custom_user.models import User

import datetime

class Command(BaseCommand):
    help = 'Sends mails about landing for april'

    def add_arguments(self, parser):
        parser.add_argument('--test-users', dest='test_users', nargs='+', type=int)
        parser.add_argument('--start-from-user', dest='start_from_user', nargs='?', type=int)

    def handle(self, **options):
        translation.activate('ru')

        if 'test_users' in options and options['test_users']:
            users_query = User.objects.filter(id__in=options['test_users'])
        else:
            users_query = User.objects.filter(
                subscribe_info=True, is_active=True, email__gt='', transactions__type__in=[3, 32],
                transactions__time__gt=datetime.datetime(2016, 4, 1)
            ).distinct().order_by('id')
            if options['start_from_user']:
                users_query = users_query.filter(id__gte=options['start_from_user'])

        content = render_to_string('mail/mailing/mail_about_money.jinja.html', {})
        content_with_inline_css = pynliner.fromString(content)

        for user in users_query:
            print 'user #%d' % user.id
            message = EmailMessage(
                u'Ваши деньги на балансе в Личном кабинете', content_with_inline_css,
                settings.DEFAULT_FROM_EMAIL, to=[user.email]
            )
            message.content_subtype = 'html'
            message.send()

