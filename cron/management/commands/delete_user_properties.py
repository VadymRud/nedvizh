# coding: utf-8
from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage
from django.conf import settings
from django.db.models import Sum
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import translation

from ad.models import Ad, ViewsCount
from custom_user.models import User

from operator import itemgetter
import time, datetime, re
import sys

from newhome.models import Newhome


class Command(BaseCommand):
    help = 'notify users about deleted properties and delete'
    leave_locale_alone = True

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', dest='dry_run', action='store_true')

    def handle(self, *args, **options):
        # выбираем целевые объявления, которые попадают в рассылку, и которые удаляются по сроку хранения
        # объявления созданные на основе планировок новостроек не попадают по данный выбор
        target_properties = Ad.objects.filter(user__isnull=False, newhome_layouts__isnull=True).order_by('id')

        delete(target_properties, options)

        # объявления теперь бессрочные и с публикации не снимаются по истечению 30 дней
        # notify_and_hide(target_properties)


def delete(target_properties, options):
    _14_days_ago = datetime.datetime.now() - datetime.timedelta(days=14)
    query = target_properties.filter(modified__lt=_14_days_ago, status=211)
    count = query.count()
    print '%d ads to delete' % query.count()

    if not options['dry_run']:
        deleted = 0
        while True:
            chunk = query[:500]
            if chunk:
                for ad in chunk:
                    ad.delete()

                    deleted += 1
                    if deleted % 100 == 0:
                        sys.stdout.write('\r%d/%d' % (deleted, count))
                        sys.stdout.flush()
            else:
                break


'''
def notify_and_hide(target_properties):
    target_properties = target_properties.filter(expired__lt=datetime.datetime.now().date()).exclude(status__in=(210, 211))
    users_ids = set(target_properties.values_list('user_id', flat=True))

    print 'We have %s users for notifying:' % len(users_ids)
    for user_id in users_ids:
        user_properties = target_properties.filter(user_id=user_id)
        user = User.objects.get(id=user_id)

        print '  user #%d' % user_id,
        if user.subscribe_info and user.email:
            subject = u'Mesto.UA: Истекает срок публикации ваших объявлений'
            content =  get_expire_message(user, user_properties.prefetch_related('photos'))

            message = EmailMessage(subject, content, settings.DEFAULT_FROM_EMAIL, [user.email])
            message.content_subtype = 'html'
            message.send()
            print '- sent email to %s' % user.email,
        else:
            print '- no email/no subscribe',

        print '- %d properties was deactivated' % user_properties.update(status=210)

        # обновляем количество активных объявлений пользователя
        user.update_ads_count()


def get_expire_message(user, properties):
    views = ViewsCount.objects.filter(basead__ad__user_id=user.id, basead__in=properties).values('basead_id').annotate(views=Sum('detail_views'))
    views_top3 = sorted(views, key=itemgetter('views'), reverse=True)[:3]
    for view in views_top3:
        view['property'] = Ad.objects.get(pk=view['basead_id'])
        try:
            view['views_contact'] = ViewsCount.objects.filter(basead_id=view['basead_id']).values('basead_id').annotate(views=Sum('contacts_views'))[0]['views']
        except IndexError:
            view['views_contact'] = 0

    context = {'user': user, 'top_properties': views_top3}

    translation.activate(user.language)

    return render_to_string('mail/expire_ads.html', context)
'''
