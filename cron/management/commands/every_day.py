from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q, F, Sum
import time, datetime, re


class Command(BaseCommand):
    help = 'run functions every day'

    def handle(self, *args, **options):
        clear_views_stats() # перенос данных по просмотрам из записей за день в записи за месяц

        collect_profiles_statistics() # наполнение моделей Stat/StatGrouped

        from utils.currency import update_properties_price
        update_properties_price(True)


@transaction.atomic
def clear_views_stats():
    from ad.models import ViewsCount

    start = time.time()
    two_months_ago = (datetime.date.today() - datetime.timedelta(days=60))

    old_views = ViewsCount.objects.filter(date__lte=two_months_ago).extra(where=["extract(day from date) > 1"])

    # достаем данные кликов за все дни, кроме первых дней месяца
    rows = list(old_views.extra(
        select={'year':"extract(year from date)", 'month':"extract(month from date)", }
    ).values('basead', 'year', 'month', 'is_fake').annotate(
        detail_views_sum=Sum('detail_views'),
        contacts_views_sum=Sum('contacts_views')
    ))

    total = len(rows)
    print 'Group old ViewsCount records. Total %s rows.' % total

    # сохраняем сгруппированные данные в статистику за первый день месяца
    for index, row in enumerate(rows):
        filter = {'date':datetime.date(int(row['year']), int(row['month']), 1), 'basead_id':row['basead'], 'is_fake': row['is_fake']}
        try:
            viewscount, created = ViewsCount.objects.get_or_create(**filter)
        except ViewsCount.MultipleObjectsReturned:
            viewscounts = ViewsCount.objects.filter(**filter)
            viewscount = viewscounts[0]
            for duplicate in viewscounts[1:]:
                duplicate.delete()

        viewscount.detail_views += row['detail_views_sum']
        viewscount.contacts_views += row['contacts_views_sum']
        viewscount.save()

        if index % 1000 == 0:
            print '%s/%s' % (index, total),

    # удаляем данные, которые перенесли в записи за 1 число месяца
    old_views.delete()

    print 'Elapsed time: %0.2f sec' % (time.time() - start)


def collect_profiles_statistics():
    from profile.models import Stat, StatGrouped

    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    print 'Update profile stats for yesterday (%s)' % yesterday,
    Stat.collect_day_data(yesterday)
    print '- OK'

    print 'Grouping daily statistics',
    StatGrouped.group_statistics(yesterday)
    print '- OK'


def update_properties_price(force_update=False):
    from django.db.models import F
    from ad.models import Ad

    for currCode, rate in get_currency_rates(force_update).iteritems():
        print 'Currency update:', Ad.objects.filter(currency=currCode).update(price_uah=F('price') * rate ), 'rows for', currCode
