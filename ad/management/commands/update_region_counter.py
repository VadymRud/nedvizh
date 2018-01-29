# coding: utf-8
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Update number of properties in regions with separation by deal type'

    def handle(self, *args, **options):
        from ad.models import Region, RegionCounter, Ad
        from django.db.models import Count
        import time
        import datetime

        print self.help + ':'
        now = datetime.datetime.now()
        regioncounter_ids_for_update = []

        for deal_type in Ad.objects.order_by().values_list('deal_type', flat=True).distinct():
            counter_by_region = {}
            start = time.time()
            total = 0

            queryset = Ad.objects.filter(is_published=True, region__isnull=False, deal_type=deal_type).\
                values_list('region').annotate(count=Count('region')).order_by('-count')

            for region_id, count in queryset:
                total += count
                counter_by_region[region_id] = count + counter_by_region.get(region_id, 0)

                # добавляем к счетчикам родительких регионов
                for parent_id in Region.objects.get(id=region_id).get_ancestors(ascending=False).values_list('id', flat=True):
                    counter_by_region[parent_id] = count + counter_by_region.get(parent_id, 0)

            for region_id, count in counter_by_region.items():
                region = Region.objects.get(pk=region_id)
                regioncounter, created = RegionCounter.objects.get_or_create(region=region, deal_type=deal_type, defaults={'count':count})

                # если счетчик уже существовал, то обновляем поле с количеством, если оно изменилось
                if not created:
                    if regioncounter.count != count:
                        regioncounter.count = count
                        regioncounter.modified = now
                        regioncounter.save()
                    else:
                        regioncounter_ids_for_update.append(regioncounter.pk)

            print u' [%s] %s sec, total %s' % (deal_type, round(time.time() - start, 2), total)

        # обновляем дату изменения для всех регинов, где были найдены объявления, чтобы далее они не очистились
        RegionCounter.objects.filter(pk__in=regioncounter_ids_for_update).update(modified=now)

        print 'RegionCounter total:',  RegionCounter.objects.count()

        counter_to_clear = RegionCounter.objects.filter(modified__lt=now - datetime.timedelta(hours=1))
        print 'RegionCounter without modifying in 1 days to clear counts:', counter_to_clear.count()
        counter_to_clear.update(count=0)

        counter_to_delete = RegionCounter.objects.filter(modified__lt=now - datetime.timedelta(days=7))
        print 'RegionCounter without modifying in 7 days to delete', counter_to_delete.count()
        counter_to_delete.delete()