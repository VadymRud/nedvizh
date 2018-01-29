# coding: utf-8
import pynliner
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import translation

from custom_user.models import User


class Command(BaseCommand):
    help = 'Sends mails about conference'

    def add_arguments(self, parser):
        parser.add_argument('--test-users', dest='test_users', nargs='+', type=int)
        parser.add_argument('--start-from-user', dest='start_from_user', nargs='?', type=int)

    def handle(self, **options):
        translation.activate('ru')

        if 'test_users' in options and options['test_users']:
            users_query = User.objects.filter(id__in=options['test_users'])

        else:
            users_query = User.objects.filter(
                subscribe_news=True, is_active=True, email__gt='', transactions__amount__gt=0,
                transactions__time__gt='2016-04-01 00:00:00'
            ).distinct().order_by('id')

            if options['start_from_user']:
                users_query = users_query.filter(id__gte=options['start_from_user'])

        for user in users_query:
            print 'user #%d' % user.id

            content = render_to_string('mail/mailing/mail_about_conference.jinja.html', {})
            content_with_inline_css = pynliner.fromString(content)

            message = EmailMessage(
                u'19-21 мая 2016г. в Киеве портал недвижимости Mesto.ua принимает участие в международной '
                u'выставке-форуме. Приходите и принимайте участие и Вы!', content_with_inline_css,
                settings.DEFAULT_FROM_EMAIL, to=[user.email]
            )
            message.content_subtype = 'html'
            message.send()

