# coding: utf-8
import pynliner
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import translation

from paid_services.models import Transaction, UserPlan
from custom_user.models import User
from utils.email import make_ga_pixel_dict, make_utm_dict


class Command(BaseCommand):
    help = 'Sends specific email'

    def add_arguments(self, parser):
        parser.add_argument('--test-users', dest='test_users', nargs='+', type=int)
        parser.add_argument('--start-from-user', dest='start_from_user', nargs='?', type=int)

    def handle(self, **options):

        if 'test_users' in options and options['test_users']:
            users_query = User.objects.filter(id__in=options['test_users'])
        else:
            users_query = User.objects.filter(realtors__is_active=True, last_action__gt='2016-02-28',
                email__gt='', subscribe_news=True
            ).distinct().order_by('id')

            if options['start_from_user']:
                users_query = users_query.filter(id__gte=options['start_from_user'])

        print 'Total users: ', users_query.count()

        utm = make_utm_dict(utm_campaign='valion')
        for user in users_query:
            print 'user #%d' % user.id
            translation.activate(user.language)
            template = 'mail/mailing/valion_franchise.jinja.html'
            subject = u'Франшиза для частных риэлторов от Valion'
            
            content = render_to_string(
                template, {
                    'utm': utm,
                    'ga_pixel': make_ga_pixel_dict(user, utm)
                }
            )
            content_with_inline_css = pynliner.fromString(content)

            message = EmailMessage(subject, content_with_inline_css, settings.DEFAULT_FROM_EMAIL, [user.email])
            message.content_subtype = 'html'
            message.send()
