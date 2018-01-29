from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Update user`s count  of properties'

    def handle(self, *args, **options):
        from ad.models import Ad
        from custom_user.models import User
        from django.db.models import Count
        import time, datetime

        start = time.time()

        print '%s, %s:' % (self.help, datetime.datetime.now())

        users = Ad.objects.filter(user__isnull=False, status=1, addr_country='UA').values_list('user').annotate(count=Count('user')).order_by()
        for user_id, count in users:
            user = User.objects.get(id=user_id)
            if user.ads_count != count:
                print '[user %s] %s -> %s (diff: %s)' % (user_id, user.ads_count, count, count - user.ads_count)
                user.ads_count = count
                user.save()

        user_without_ads = User.objects.filter(ads_count__gt=0).exclude(id__in=[user_id for user_id, count in users])
        for user in user_without_ads:
            print '[user %s] %s -> 0 (diff: %s)' % (user.id, user.ads_count,  -user.ads_count)
        user_without_ads.update(ads_count=0)

        print 'Time:', round(time.time() - start, 2)
