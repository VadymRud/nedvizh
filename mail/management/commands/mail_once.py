# coding: utf-8
import datetime
import pynliner
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.db.models import *
from django.template.loader import render_to_string
from django.utils import translation

from custom_user.models import User
from utils.email import make_utm_dict, make_ga_pixel_dict


class Command(BaseCommand):
    help = 'Sends specific email'

    def add_arguments(self, parser):
        parser.add_argument('--test-users', dest='test_users', nargs='+', type=int)
        parser.add_argument('--start-from-user', dest='start_from_user', nargs='?', type=int)

    def handle(self, **options):
        translation.activate('uk')
        # translation.activate('ru')

        if 'test_users' in options and options['test_users']:
            users_query = User.objects.filter(id__in=options['test_users'])

        else:
            date_range = [
                datetime.datetime.now() - datetime.timedelta(days=30*3),
                datetime.datetime.now() - datetime.timedelta(days=0)
            ]
            users_query = User.objects.filter(email__gt='', subscribe_news=True, last_action__range=date_range) \
                .distinct().order_by('id')
                
            #users_query = users_query.filter(region__slug='kievskaya-oblast')

            if options['start_from_user']:
                users_query = users_query.filter(id__gte=options['start_from_user'])
                
        print 'total users', users_query.count()
        
        utm = make_utm_dict(utm_campaign='new_services')
        for user in users_query:
            print 'user #%d' % user.id
            template = 'mail/mailing/mail_saint_mykholay.jinja.html' 
            subject = u'З днем Святого Миколая!'

            content = render_to_string(template, {
                'utm': utm,
                'ga_pixel': make_ga_pixel_dict(user, utm),
            })
            content_with_inline_css = pynliner.fromString(content)
            content_with_inline_css = content
            message = EmailMessage(subject, content_with_inline_css, settings.DEFAULT_FROM_EMAIL, [user.email])
            message.content_subtype = 'html'
            message.send()
