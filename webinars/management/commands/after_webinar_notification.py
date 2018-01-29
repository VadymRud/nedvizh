# coding: utf-8
import time
import datetime
import pynliner
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from webinars.models import WebinarReminder


class Command(BaseCommand):
    help = u'Отправка уведомлений с сылкой на прошедший вебинар'

    def handle(self, *args, **options):
        script_start = time.time()
        start_at = datetime.datetime.now() - datetime.timedelta(days=1)
        users = WebinarReminder.objects.filter(
            webinar__type='webinar', webinar__start_at__gt=start_at, webinar__finish_at__lte=datetime.datetime.now()
        ).select_related('webinar')

        for user in users:
            translation.activate(user.language)
            subject = _(u'Запись вебинара %s' % user.webinar.get_title())
            content = render_to_string(
                'mail/webinars/after_webinar_notification_{:s}.jinja.html'.format(user.language),
                {'user': user, 'webinar': user.webinar}
            )
            content_with_inline_css = pynliner.fromString(content)
            message = EmailMessage(subject, content_with_inline_css, settings.DEFAULT_FROM_EMAIL, [user.email])
            message.content_subtype = 'html'
            message.send()
            print 'Sending email (%s) was successful' % user.email

        print '%.2f sec' % (time.time() - script_start)
