# coding: utf-8
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.utils import translation

from custom_user.models import User
from agency.models import Agency

import pynliner

class Command(BaseCommand):
    help = 'Performs a mailing about renovated "professionals"'

    def add_arguments(self, parser):
        parser.add_argument('--test-users', dest='test_users', nargs='+', type=int)
        parser.add_argument('--start-from-user', dest='start_from_user', nargs='?', type=int)

    def handle(self, **options):
        translation.activate('ru')

        if 'test_users' in options and options['test_users']:
            users_query = User.objects.filter(id__in=options['test_users'])
        else:
            users_query = User.objects.filter(
                realtors__agency__in=Agency.objects.filter(realtors__user__ads__is_published=True),
                realtors__is_admin=True,
                realtors__is_active=True,
                is_active=True,
                email__gt='',
                subscribe_info=True,
            ).order_by('id')

            if options['start_from_user']:
                users_query = users_query.filter(id__gte=options['start_from_user'])

        for user in users_query:
            print 'user #%d' % user.id
            content = render_to_string('mail/mailing/mail_about_professionals.jinja.html', {})
            content_with_inline_css = pynliner.fromString(content)
            message = EmailMessage(u'Уведомление от Mesto.UA', content_with_inline_css, settings.DEFAULT_FROM_EMAIL, [user.email])
            message.content_subtype = 'html'
            message.send()

