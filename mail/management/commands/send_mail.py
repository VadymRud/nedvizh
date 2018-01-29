# coding: utf-8

from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import translation

from mail.models import Notification, TYPE_CHOICES

import pynliner

from collections import defaultdict
import datetime

# TODO рассмотреть необходимость ведения лога через settings.LOGGING

types = [notification_type for notification_type, verbose in TYPE_CHOICES]

class Command(BaseCommand):
    help = 'Sends email notification groupped by user and type, stored in Notification model'

    def add_arguments(self, parser):
        parser.add_argument('--type', '-t', action='append', choices=types, help='notification type (all types by default)')
        parser.add_argument('--interval', '-i', type=int, required=True, help='restart interval from crontab')

    def handle(self, *args, **options):
        now = datetime.datetime.now()
        one_interval_ago = now - datetime.timedelta(seconds=60*options['interval'])

        for notification_type in (options['type'] or types):
            print 'start "%s", %s' % (notification_type, now)

            notifications = list(
                Notification.objects.filter(type=notification_type).prefetch_related('user', 'object').order_by('created')
            )

            if notifications:
                groupped_by_user = defaultdict(list)
                notification_id_to_delete = []
                while notifications:
                    notification = notifications.pop(0)
                    if notification.object is None:
                        notification_id_to_delete.append(notification.id)

                    else:
                        groupped_by_user[notification.user].append(notification)

                if notification_id_to_delete:
                    # Если объект удален, а уведомление осталось - удаляем уведомление
                    print '  delete notifications with id: %s' % ', '.join(map(str, notification_id_to_delete))
                    Notification.objects.filter(id__in=notification_id_to_delete).delete()

                for user, notifications in groupped_by_user.iteritems():
                    message = '  user_id=%d, ' % user.id

                    if notifications[-1].created > one_interval_ago:
                        message += 'fresh notification is found - suspended'
                    else:
                        if user.email:
                            if user.subscribe_info:
                                translation.activate(user.language)

                                send_mail(notification_type, user, notifications)
                                message += ('object_ids=%s' % [notification.object.id for notification in notifications])
                            else:
                                message += 'isn`t subscribed'
                        else:
                            message += 'hasn`t email'

                        # если копить id и удалять все сразу, есть риск повторной рассылки в случае ошибки
                        # поэтому удаляется после отправки каждого письма
                        Notification.objects.filter(id__in=[notification.id for notification in notifications]).delete()

                    print message
                    
            print 'end'
            print


def send_mail(notification_type, user, notifications):
    content = render_to_string('mail/%s.jinja.html' % notification_type, {
        'user': user,
        'notifications': notifications,
    })
    content_with_inline_css = pynliner.fromString(content)
    message = EmailMessage(u'Уведомление от Mesto.UA', content_with_inline_css, settings.DEFAULT_FROM_EMAIL, [user.email])
    message.content_subtype = 'html'
    message.send()

