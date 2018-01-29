# coding=utf-8
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models import Q

from ad.models import Ad
from agency.models import Realtor
from newhome.models import Developer, Newhome
from custom_user.models import User
from paid_services.models import CatalogPlacement, filter_user_by_plan

import datetime
import time


class Command(BaseCommand):
    help = u'Проверка условий публикации объявлений и деактивация объявлений, если условия не выполняются'

    def add_arguments(self, parser):
        parser.add_argument('--dry', dest='dry', action='store_true', help='only count ads')

    def handle(self, *args, **options):
        self.start = time.time()
        self.dry = options['dry']

        print datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), ('' if not self.dry else '[DRY RUN]')

        self.check_is_published()
        self.deactivate_UA_ads()
        self.deactivate_international_ads()
        self.deactivate_newhomes()

        self.update_ads_counter()

        print 'Elapsed time: %.2f' % (time.time() - self.start)

    # проверка корректности поля is_published
    def check_is_published(self):
        wrong_is_published = Ad.objects.filter(is_published=True).exclude(status=1, moderation_status=None)
        print '%s ads with wrong is_published field' % wrong_is_published.count()

        if not self.dry:
            wrong_is_published.update(is_published=False)

    # объявления, размещенных по тарифу или лидогенератору
    def deactivate_UA_ads(self):
        # Работа с обычными объявлениями
        users = User.objects.filter(ads_count__gt=0).prefetch_related('leadgeneration', 'user_plans')
        for user in users:
            ads_limit = user.get_user_limits()['ads_limit']
            active_ads = list(user.ads.filter(
                status=1, is_published=True, addr_country='UA').exclude(
                newhome_layouts__isnull=False).order_by('-modified'))
            if ads_limit < len(active_ads):
                illegal_ads = active_ads[ads_limit:]
                print '[uid %s] %s of %s' % (user.id, len(active_ads), ads_limit),

                if not self.dry:
                    print ', %s illegal ads deactivated' % len(illegal_ads)
                    Ad.objects.filter(pk__in=[ad.id for ad in illegal_ads]).update(status=210, is_published=False)
                    user.update_ads_count()
                else:
                    print

    # зарубежная недвижимость
    def deactivate_international_ads(self):
        ads = Ad.objects.filter(status=1, user__isnull=False).exclude(addr_country='UA').exclude(pk__in=CatalogPlacement.get_active_user_ads())
        print '%s international ads without active catalog placement' % ads.count()

        if not self.dry:
            ads.update(is_published=False, status=210)

    # новостройки
    def deactivate_newhomes(self):
        # Работа с новостройками
        illegal_users = set(User.objects.filter(
            developer__isnull=False, leadgeneration__is_active_newhomes=False).values_list('id', flat=True))

        newhomes = Newhome.objects.filter(status=1, addr_country='UA', user__in=illegal_users)
        print '%s ukranian newhomes without enabled lead-gen deactivated. [ids %s]' % (
            newhomes.count(), ', '.join([str(newhome_id) for newhome_id in newhomes.values_list('pk', flat=True)])
        )
        if not self.dry:
            newhomes.update(status=210)

        # Отключение объявлений на основе планировок новостройки
        illegal_ads = Ad.objects.filter(user__in=illegal_users, newhome_layouts__isnull=False)
        print '%s illegal ads (newhome layouts) deactivated' % len(illegal_ads)
        if not self.dry:
            illegal_ads.update(status=210)

    # обновление поля ads_count у пользователей
    def update_ads_counter(self):
        print 'Update ads_count fields:'
        users = Ad.objects.filter(user__isnull=False, status=1, addr_country='UA').values_list('user').annotate(count=Count('user')).order_by()
        for user_id, count in users:
            user = User.objects.get(id=user_id)
            if user.ads_count != count:
                print '  [user %s] %s -> %s (diff: %s)' % (user_id, user.ads_count, count, count - user.ads_count)
                user.ads_count = count
                user.save()

        user_without_ads = User.objects.filter(ads_count__gt=0).exclude(id__in=[user_id for user_id, count in users])
        for user in user_without_ads:
            print '  [user %s] %s -> 0 (diff: %s)' % (user.id, user.ads_count,  -user.ads_count)
        user_without_ads.update(ads_count=0)

