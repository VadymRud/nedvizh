# coding: utf-8
import datetime
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
import pynliner

from custom_user.models import User
from utils.email import make_ga_pixel_dict, make_utm_dict
from webinars.models import Webinar


class Command(BaseCommand):
    leave_locale_alone = True
    help = u'Приглашение на вебинар/семинар'

    def add_arguments(self, parser):
        parser.add_argument(
            '--invitation', action='store_const', dest='notification_type', const='invitation',
            help=u'Разослать первое приглашение на мероприятие'
        )
        parser.add_argument(
            '--first-webinar-notification', action='store_const', dest='notification_type',
            const='first-webinar-notification',
            help=u'Разослать первое напоминание о вебинаре проходящих в день запуска команды'
        )
        parser.add_argument(
            '--second-webinar-notification', action='store_const', dest='notification_type',
            const='second-webinar-notification',
            help=u'Разослать второе напоминание о вебинаре проходящих в день запуска команды'
        )
        parser.add_argument(
            '--seminar-notification', action='store_const', dest='notification_type',
            const='seminar-notification',
            help=u'Выслать напоминание о семинаре проходящем на следующий день после запуска команды'
        )

    @staticmethod
    def _send_campaign(users, event, subject, template):
        emails_sent = 0
        utm = make_utm_dict(utm_campaign=event.type, utm_term=event.slug)
        for user in users:
            print 'user #%d' % user.id

            translation.activate(user.language)

            content = render_to_string(
                template,
                {
                    'utm': utm,
                    'ga_pixel': make_ga_pixel_dict(user if not hasattr(user, 'user') else user.user, utm),
                    'event': event
                }
            )
            content_with_inline_css = pynliner.fromString(content)

            message = EmailMessage(subject, content_with_inline_css, settings.DEFAULT_FROM_EMAIL, [user.email])
            message.content_subtype = 'html'
            message.send()

            emails_sent += 1

        return emails_sent

    def handle(self, *args, **options):
        # Выбираем события
        events = Webinar.objects.all()

        if options.get('notification_type', None) == 'invitation':
            # Рассылка приглашений на мероприятие
            events = events.filter(status__in=['ready', 'ready_for_test'])

            last_action_date = datetime.datetime.now() - datetime.timedelta(days=365)
            users = User.objects.filter(email__gt='', subscribe_news=True).distinct().order_by('id')

            for event in events:
                if event.status == 'ready_for_test':
                    users = users.filter(id__in=[59441, 10821, 136150, 77247])

                elif event.region_id:
                    users = users.filter(region=event.region)

                    # Для региона разрешаем последнюю активность/покупку 2 года назад
                    last_action_date = datetime.datetime.now() - datetime.timedelta(days=730)

                users = users.filter(
                    Q(realtors__is_active=True, last_action__gt=last_action_date) |
                    Q(transactions__amount__gt=0, transactions__time__gt=last_action_date)
                )

                event.status = 'process'
                event.emails_sent = 0
                event.save()

                if event.type == 'webinar':
                    subject = _(u'Бесплатный вебинар Mesto School')
                else:
                    subject = _(u'Бесплатный семинар Mesto School')

                print 'Start mailing for event #%d' % event.id
                event.emails_sent = self._send_campaign(
                    users, event, subject, 'webinars/mail/event-invitation.jinja.html')
                event.status = 'done'
                event.save()
                print 'End of mailing for event #%d' % event.id

        elif options.get('notification_type', None) == 'first-webinar-notification':
            # Рассылка первого напоминания о вебинаре проходящих в день запуска команды
            events = events.filter(type='webinar', start_at__range=(
                datetime.datetime.now(), datetime.datetime.combine(datetime.datetime.today(), datetime.time.max)))

            for event in events:
                subject = _(u'Бесплатный вебинар Mesto School')

                print 'Start first webinar notification for event #%d' % event.id
                self._send_campaign(
                    event.reminders.all(), event, subject, 'webinars/mail/event-first-webinar-notification.jinja.html')
                print 'End of first webinar notification for event #%d' % event.id

        elif options.get('notification_type', None) == 'second-webinar-notification':
            # Рассылка второго напоминания о мероприятиях проходящих в день запуска команды
            events = events.filter(type='webinar', start_at__range=(
                datetime.datetime.now(), datetime.datetime.combine(datetime.datetime.today(), datetime.time.max))
            ).exclude(external_url__isnull=True).exclude(external_url='')

            for event in events:
                subject = _(u'Бесплатный вебинар Mesto School')

                print 'Start second webinar notification for event #%d' % event.id
                self._send_campaign(
                    event.reminders.all(), event, subject, 'webinars/mail/event-second-webinar-notification.jinja.html')
                print 'End of second webinar notification for event #%d' % event.id

        elif options.get('notification_type', None) == 'seminar-notification':
            # Рассылка напоминания о семинаре проходящем на следующий день после запуска команды

            # Завтрешний день
            base_time = datetime.datetime.now() + datetime.timedelta(days=+1)

            events = events.filter(type='seminar', start_at__range=(
                datetime.datetime.combine(base_time, datetime.time.min),
                datetime.datetime.combine(base_time, datetime.time.max)
            )).exclude(address__isnull=True).exclude(address='')

            last_action_date = datetime.datetime.now() - datetime.timedelta(days=365)
            users = User.objects.filter(
                (
                    Q(realtors__is_active=True, last_action__gt=last_action_date) |
                    Q(transactions__amount__gt=0, transactions__time__gt=last_action_date)
                ) & Q(email__gt='', subscribe_news=True)).distinct().order_by('id')

            for event in events:
                if event.region_id:
                    users = users.filter(region=event.region)

                subject = _(u'Ваше приглашение на семинар "%s"') % event.get_title()

                print 'Start seminar notification for event #%d' % event.id
                self._send_campaign(users, event, subject, 'webinars/mail/event-seminar-notification.jinja.html')
                print 'End of seminar notification for event #%d' % event.id
