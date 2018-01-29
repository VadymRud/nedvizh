# coding: utf-8
import pynliner
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import translation

from ad.models import Region
from custom_user.models import User
from django.utils.translation import ugettext_lazy as _


class Command(BaseCommand):
    help = 'Sends mails about specific webinar (to all users with one or more ad)'

    def add_arguments(self, parser):
        parser.add_argument('--test-users', dest='test_users', nargs='+', type=int)
        parser.add_argument('--start-from-user', dest='start_from_user', nargs='?', type=int)

    def handle(self, **options):
        # translation.activate('uk')
        translation.activate('ru')

        if 'test_users' in options and options['test_users']:
            users_query = User.objects.filter(id__in=options['test_users'])

        else:
            # regions_id = Region.objects.get(id=55).get_children_ids()
            users_id = User.get_user_ids_with_active_plan() | set(User.get_user_ids_with_active_ppk())
            users_query = User.objects.filter(
                # email__gt='', subscribe_news=True, ads__region__in=regions_id
                # email__gt='', subscribe_news=True, ads_count__gt=0
                email__gt='', subscribe_news=True, id__in=users_id
            ).distinct().order_by('id')

            if options['start_from_user']:
                users_query = users_query.filter(id__gte=options['start_from_user'])

        # pynliner - тормоз, лучше внутрь цикла его не класть
        content = render_to_string('mail/mailing/mail_about_new_services.jinja.html', {})
        content_with_inline_css = pynliner.fromString(content)

        for user in users_query:
            print 'user #%d' % user.id

            message = EmailMessage(
                u'Обновленный раздел "Услуги" + мобильные номера телефонов', content_with_inline_css,
                settings.DEFAULT_FROM_EMAIL, [user.email]
            )
            message.content_subtype = 'html'
            message.send()
