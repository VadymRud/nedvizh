# coding: utf-8
import pynliner
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.utils import translation

from ad.models import *
from custom_user.models import User

import datetime

class Command(BaseCommand):
    help = 'Sends mails about new area rules'

    def add_arguments(self, parser):
        parser.add_argument('--test-users', dest='test_users', nargs='+', type=int)
        parser.add_argument('--start-from-user', dest='start_from_user', nargs='?', type=int)

    def handle(self, **options):
        translation.activate('ru')
        last_action_time = datetime.datetime.now() - datetime.timedelta(days=31)

        if 'test_users' in options and options['test_users']:
            users_query = User.objects.filter(id__in=options['test_users'])
        else:
            user_ids = set(Ad.objects.filter(deal_type='newhomes', is_published=True).values_list('user_id', flat=True))
            users_query = User.objects.filter(id__in=user_ids, email__gt='')

            if options['start_from_user']:
                users_query = users_query.filter(id__gte=options['start_from_user'])

        for user in users_query:
            print 'user #%d' % user.id
            content = render_to_string('mail/mailing/mail_about_newhomes_area.jinja.html', {})
            content_with_inline_css = pynliner.fromString(content)
            message = EmailMessage(u'Уведомление от Mesto.UA', content_with_inline_css, settings.DEFAULT_FROM_EMAIL, [user.email])
            message.content_subtype = 'html'
            message.send()

