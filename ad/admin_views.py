# coding: utf-8
from django import forms
from django.shortcuts import render, redirect
from django.db import connection, transaction
from django.db.models import Count, Q, F
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse, Http404, HttpResponseForbidden
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings

from ad.models import Region, Ad, Photo, Moderation, RegionCounter
from ad.forms import PropertyForm
from ad.choices import MODERATION_STATUS_CHOICES
from utils.paginator import HandyPaginator

import datetime


@transaction.atomic
def merge(region_from, region_to, merging_list, delete):
    region_from.get_children().update(parent=region_to)
    region_to.update_descendants_tree_path()

    cursor = connection.cursor()
    moved_objects = []

    # обновляем static_url у потомков (не только у детей)
    children_ids = [str(region.id) for region in region_from.get_descendants(include_self=True)]
    cursor.execute("UPDATE %s SET static_url = REPLACE(static_url, '%s', '%s') WHERE id IN (%s);" % \
                   (Region._meta.db_table, region_from.static_url, region_to.static_url, ','.join(children_ids)))
    if cursor.rowcount:
        moved_objects.append([u'обновленных static_url', cursor.rowcount])

    # подменяем связи для объектов M2M
    m2m_related = [f for f in region_from._meta.get_fields(include_hidden=True) if f.many_to_many and f.auto_created]

    for link in m2m_related:
        table = link.field.m2m_db_table()
        column = link.field.m2m_reverse_name()
        cursor.execute("UPDATE %s SET %s = '%s' WHERE %s = '%s';" % (table, column, region_to.pk, column, region_from.pk))
        if cursor.rowcount:
            moved_objects.append(['%s - %s' % (link.model.__name__, link.model._meta.verbose_name), cursor.rowcount])

    # подменяем связи для объектов FK
    related = [
        f for f in region_from._meta.get_fields() if (f.one_to_many or f.one_to_one) and f.auto_created and not f.concrete
    ]

    for link in related:
        if link.related_model in [Region, RegionCounter]:
            continue

        table = link.related_model._meta.db_table
        column =  link.field.get_attname()
        cursor.execute("UPDATE %s SET %s = '%s' WHERE %s = '%s';" % (table, column, region_to.pk, column, region_from.pk))
        if cursor.rowcount:
            moved_objects.append(['%s - %s' % (link.model.__name__, link.model._meta.verbose_name), cursor.rowcount])

    merging_list.append(['#%d %s' % (region_from.id, region_from.text), '#%d %s' % (region_to.id, region_to.text), moved_objects])

    if delete:
        if region_from.subdomain:
            region_to.name = region_from.name
            region_to.subdomain = region_from.subdomain

            region_to.save()
        region_from.delete()

    return region_to


@transaction.atomic
def sync_fields(region_from, region_to):
    region_to.name = region_from.name
    region_to.text = region_from.text
    if settings.MESTO_USE_GEODJANGO:
        region_to.point = region_from.point
    else:
        region_to.coords_x = region_from.coords_x
        region_to.coords_y = region_from.coords_y
    region_to.save()


MERGE_TYPES = (
    ('name', u'одинаковому наименованию'),
    ('staticurl', u'одинаковому static url'),
    ('geo', u'одинаковым координатам'),
    ('geo-soft', u'похожим координатам'),
)
class MergeForm(forms.Form):
    type = forms.ChoiceField(label=u'Группировка по', choices=MERGE_TYPES, required=False)
    name = forms.CharField(label=u'Краткое наименование', max_length=100, required=False)
    text = forms.CharField(label=u'Полное наименование', max_length=100, required=False)
    parent = forms.IntegerField(label=u'ID родителя (напр., области)', required=False)
    reverse = forms.BooleanField(label=u'Обратный порядок', required=False)


@staff_member_required
def region_merge(request):
    main_order = 'id'
    type = 'name'

    form = MergeForm(request.GET)
    filter = Q()
    if form.is_valid():
        if form.cleaned_data['name']:
            filter.add(Q(name_ru__icontains=form.cleaned_data['name']), Q.AND)
        if form.cleaned_data['text']:
            filter.add(Q(text__icontains=form.cleaned_data['text']), Q.AND)
        if form.cleaned_data['parent']:
            parent = Region.objects.get(id=form.cleaned_data['parent'])
            filter.add(Q(pk__in=parent.get_descendants(True)), Q.AND)
        if form.cleaned_data['reverse']:
            main_order = '-id'
        if form.cleaned_data['type']:
            type = form.cleaned_data['type']

    regions_selected = Region.objects.filter(pk__in=request.POST.getlist('regions', [])).order_by(main_order)
    if regions_selected.count() == 2:
        merging_list = []
        if 'sync_fields' in request.POST:
            sync_fields(regions_selected[0], regions_selected[1])
        else:
            survivor_region = merge(regions_selected[0], regions_selected[1], merging_list, request.POST.get('delete', False))

    if type == 'geo-soft':
        if settings.MESTO_USE_GEODJANGO:
            alike_regions = Region.objects.snap_to_grid(0.001).values('kind', 'parent', 'snap_to_grid').annotate(count=Count('*')).filter(count__gt=1)

            where_conditions = []
            for values in alike_regions:
                where_conditions.append(u"""
                    (ad_region.kind = '%(kind)s' AND ad_region.parent_id = %(parent)s AND ST_SnapToGrid(ad_region.centroid, 0.001) ~= ST_GeomFromText('%(snap_to_grid)s'))
                """ % values)
            where_sql = u' OR '.join(where_conditions)

            regions = Region.objects.snap_to_grid(0.001).filter(filter).extra(where=[where_sql]).prefetch_related('region_counter').select_related('parent').order_by('parent', main_order)
            for region in regions:
                region.group = region.parent.text
        else:
            threshold = 1000
            threshold_pow = len(str(1000))-1
            cursor = connection.cursor()
            cursor.execute("""SELECT kind, parent_id, (ROUND(coords_x*%(threshold)s)/%(threshold)s) as coords_x_soft, (ROUND(coords_y*%(threshold)s)/%(threshold)s) as coords_y_soft, COUNT(*) as cnt
                FROM ad_region GROUP BY kind, parent_id, coords_x_soft, coords_y_soft HAVING COUNT(*) > 1""" % {'threshold': threshold});

            coords_filter = Q()
            for row in cursor.fetchall():
                coords_filter.add(Q(kind=row[0]) & Q(parent=row[1]) & Q(coords_x__range=[row[2]-0.5/threshold, row[2]+0.5/threshold]) & Q(coords_y__range=[row[3]-0.5/threshold, row[3]+0.5/threshold]), Q.OR)
            filter.add(coords_filter, Q.AND)

            regions = Region.objects.filter(filter).prefetch_related('region_counter').select_related('parent').order_by('parent', main_order)
            for region in regions:
                # region.group = '%s [%s, %s]' % (region.parent.name, round(float(region.coords_x), threshold_pow), round(float(region.coords_y), threshold_pow))
                region.group = region.parent.text
    elif type == 'geo':
        if settings.MESTO_USE_GEODJANGO:
            repeated_centroids = Region.objects.values_list('centroid', flat=True).annotate(count=Count('centroid')).filter(count__gt=1)
            for point in repeated_centroids:
                filter.add(Q(centroid=point), Q.OR)

            regions = Region.objects.filter(filter).prefetch_related('region_counter').order_by('centroid', main_order)
            for region in regions:
                region.group = region.centroid.coords
        else:
            cursor = connection.cursor()
            cursor.execute("SELECT coords_x, coords_y FROM ad_region GROUP BY coords_x, coords_y HAVING COUNT(*) > 1");
            coords = cursor.fetchall()
            coords_x = [ row[0] for row in coords ]
            coords_y = [ row[1] for row in coords ]

            filter.add(Q(coords_x__in=coords_x, coords_y__in=coords_y), Q.AND)

            regions = Region.objects.filter(filter).prefetch_related('region_counter').order_by('coords_x', main_order)
            for region in regions:
                region.group = '%s, %s' % (region.coords_x, region.coords_y)
    elif type == 'name':
        cursor = connection.cursor()
        cursor.execute("SELECT name_ru, parent_id FROM ad_region GROUP BY parent_id, name_ru HAVING COUNT(*) > 1");
        subfilter = Q()
        for row in cursor.fetchall():
            subfilter.add(Q(name_ru=row[0]) & Q(parent=row[1]), Q.OR)
        filter.add(subfilter, Q.AND)

        regions = Region.objects.filter(filter).prefetch_related('region_counter').select_related('parent').order_by('parent', 'name_ru', main_order)
        for region in regions:
            region.group = '%s, %s' % (region.parent.name_ru, region.name_ru)
    elif type == 'staticurl':
        cursor = connection.cursor()
        cursor.execute("SELECT static_url FROM ad_region GROUP BY static_url HAVING COUNT(*) > 1");
        subfilter = Q()
        for row in cursor.fetchall():
            subfilter.add(Q(static_url=row[0]), Q.OR)
        filter.add(subfilter, Q.AND)

        regions = Region.objects.filter(filter).prefetch_related('region_counter').order_by('static_url', main_order)
        for region in regions:
            region.group = region.static_url

    for region in regions:
        if region in regions_selected: region.selected = True
        region.properties_count = sum([r.count for r in region.region_counter.all()])

    return render(request, "admin/region_merge.html", locals())

AD_TYPES = (
    ('all', 'все объявления'),
    ('person', 'частники'),
    ('agency', 'агентства'),
    ('export', 'платный экспорт'),
    ('import', 'импорт'),
)


class ModerationFilter(forms.Form):
    ad_type = forms.ChoiceField(label=u'Тип объявлений', choices=AD_TYPES)


# страница модерирования объявления - /admin/ad/moderation/
@staff_member_required
def moderation(request, moderation_id=None):
    if not request.user.has_perm("%s.%s_%s" % ('ad', 'change', 'moderation')):
        return HttpResponseForbidden(u'У вас нет доступа к этой странице')

    # выбор типа пользователя для фильтрации объявлений
    if 'ad_type' in request.POST or 'ad_type' in request.GET:
        ad_filter_form = ModerationFilter(data=request.POST or request.GET)
    else:
        ad_filter_form = ModerationFilter({'ad_type': request.session.get('moderation_filter')})

    if ad_filter_form.is_valid():
        request.session['moderation_filter'] = ad_filter_form.cleaned_data['ad_type']

    # закрываем заявку на модерацию
    if 'ad_id' in request.POST:
        ad = Ad.objects.get(pk=request.POST['ad_id'])
        ad.moderate(action=request.POST['action'], reject_status=request.POST.get('reject_status'), moderator=request.user)

        if 'next' in request.POST:
            return redirect(request.POST['next'])

    # отклоняем объявление по причине "дубликат объявления" и восстанавливаем старое объявление
    if 'reject_duplicate' in request.GET:
        week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        ad = Ad.objects.get(pk=request.GET['reject_duplicate'])
        own_duplicated_ads = list(ad.get_duplicates_queryset().filter(created__gt=week_ago, user=ad.user).order_by('updated'))

        if own_duplicated_ads:
            # отклоняем текущее объявление и все дубли, кроме первого
            for ad in [ad] + own_duplicated_ads[1:]:
                if ad.moderation_status != 22:
                    ad.moderate(action='reject', reject_status=22, moderator=request.user)

            # активируем первое за последнюю неделю объявление из всех дублей
            first_ad_in_week = own_duplicated_ads[0]
            first_ad_in_week.status = 1
            first_ad_in_week.save()
            first_ad_in_week.moderate(action='accept', reject_status=None, moderator=request.user)

            # для проданных объектов отмечаем, что объявление возвращено к публикации
            first_ad_in_week.deactivations.filter(returning_time=None).update(returning_time=datetime.datetime.now())

    # на модерацию попадают объявления с заявками на модерацию (Moderation) и со статусом пре-модерация
    base_qs = Ad.objects.filter(moderations__isnull=False, moderations__moderator__isnull=True)
    new_ads_qs = base_qs.filter(xml_id=None)

    # фильтр по частникам/агентствам
    if request.session.get('moderation_filter') == 'person':
        new_ads_qs = new_ads_qs.filter(user__agencies__isnull=True)
    elif request.session.get('moderation_filter') == 'agency':
        new_ads_qs = new_ads_qs.filter(user__agencies__isnull=False)
    elif request.session.get('moderation_filter') == 'import':
        new_ads_qs = base_qs.filter(user__isnull=False, xml_id__isnull=False)
    elif request.session.get('moderation_filter') == 'export':
        new_ads_qs = base_qs.filter(international_catalog__isnull=False)

    new_ads_count = new_ads_qs.count()

    # находим Moderation или создаем, на тот случай если объявление попало на модерацию еще при старом алгоритме через status=4
    moderation = None
    if moderation_id:
        moderation = Moderation.objects.get(pk=moderation_id)
    else:
        ads = new_ads_qs.order_by('moderations__start_time')[:10]
        for ad in ads:
            # проверяем флаг блокировки объявления, если объявление уже открыто другим менеджером, то его следует пропустить
            cache_key_for_blocking = 'ad%d_moderation_block' % ad.pk
            if cache.get(cache_key_for_blocking, request.user.id) == request.user.id:
                cache.set(cache_key_for_blocking, request.user.id, 60)
                try:
                    moderation, created = Moderation.objects.get_or_create(basead=ad, moderator__isnull=True)
                except Moderation.MultipleObjectsReturned:
                    moderations = Moderation.objects.filter(basead=ad, moderator__isnull=True).order_by('id')
                    moderation = moderations[0]
                    moderations.exclude(pk=moderation.pk).delete()
                break

    if not moderation:
        # нет объявлений на модерацию
        text = u'<br/><br/><h1 align="center"><i class="glyphicon glyphicon-thumbs-up"></i> &nbsp; Поздравляем, вам нечего модерировать!</h1>'
        if request.session.get('moderation_filter'):
            text += u'<br/><br/><p align="center"><a href="?ad_type=all">все объявления пользователей</a></p>'
        return render(request, "blank.jinja.html", {'debug': text})

    # форма создается для вывода названия полей, хотя самой формы там нет
    form = PropertyForm(instance=moderation.basead.ad)

    # удаляем поля, которые не нужно выводить
    for field in ['promotion', 'international', 'uk_to_international']:
        if field in form.fields:
            del form.fields[field]

    # другие объявлений пользователя на модерации
    user_ads_on_moderation = moderation.basead.ad.user.ads.filter(moderations__isnull=False,
                                                           moderations__moderator__isnull=True).exclude(id=moderation.basead_id)
    user_stats = Moderation.get_stats_by_user(moderation.basead.ad.user_id)

    # поиск дубликатов по фотографиям
    duplicate_ads_qs = moderation.basead.ad.get_duplicates_queryset()

    # интересуют только дубли за последнюю неделю
    week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
    duplicate_ads_qs = duplicate_ads_qs.filter(created__gt=week_ago).select_related('user', 'region').prefetch_related('photos').order_by('user', '-updated')

    import collections
    duplicate_ads_by_user = collections.defaultdict(list)
    for ad in duplicate_ads_qs:
        duplicate_ads_by_user[ad.user].append(ad)

    # посдчет данных для статистики
    # проверка start_time__lt=F('end_time') используется, чтобы отсечь модерации без заявок (когда модератор просто отклоняет опубликованное объявление, которые не изменялось)
    moderations_today = Moderation.objects.filter(end_time__gt=datetime.datetime.today().date(), start_time__lt=F('end_time')).order_by('-end_time')
    moderations_by_you_today = filter(lambda moderation: moderation.moderator_id == request.user.id, moderations_today)
    stats = {
        'moderated_total': len(moderations_today),
        'moderated_by_you': len(moderations_by_you_today),
        'last_10_moderation': moderations_by_you_today[:10]
    }

    return render(request, "admin/moderation.jinja.html", {
        'moderation': moderation,
        'stats': stats,
        'ad': moderation.basead.ad,
        'duplicate_ads': duplicate_ads_qs,
        'duplicate_ads_by_user': duplicate_ads_by_user,
        'moderation_queue': not moderation_id,
        'user_ads_on_moderation': user_ads_on_moderation,
        'user_stats': user_stats,
        'form': form,
        'statuses': MODERATION_STATUS_CHOICES,
        'new_ads_count': new_ads_count,
        'ad_filter_form': ad_filter_form,
    })

# страница модерирования объявления - /admin/ad/moderation/stats/
@staff_member_required
def moderation_stats(request):
    from qsstats import QuerySetStats
    today = datetime.datetime.today()
    date_list = [today - datetime.timedelta(days=x) for x in range(0, 40)]
    start = date_list[-1]

    moderators = dict(set(Moderation.objects.filter(end_time__gt=start, moderator__isnull=False).values_list('moderator__email', 'moderator_id')))
    for moderator_email, moderator_id in moderators.items():
        # проверка start_time__lt=F('end_time') используется, чтобы отсечь модерации без заявок (когда модератор просто отклоняет опубликованное объявление, которые не изменялось)
        qs = Moderation.objects.filter(moderator_id=moderator_id, start_time__lt=F('end_time')).only('end_time')
        data = QuerySetStats(qs, 'end_time').time_series(start, today)
        if max([x[1] for x in data]) > 15:
            moderators[moderator_email] = data
        else:
            del moderators[moderator_email]

    return render(request, 'admin/moderation_stats.jinja.html', locals())


# статистика по источникам фидов - /admin/ad/ad/feed_sources/
@staff_member_required
def feed_sources(request):
    key = 'feed-sources-in-admin'
    sites = cache.get(key)
    if not sites:
        sites = {}
        ads = Ad.objects.extra(select={'domain': "substring(source_url from '.*://([^/]*)')"})\
                  .filter(user__isnull=True, source_url__gt='').values('domain')
        for ad in ads:
            domain = ad['domain']
            sites.setdefault(domain, 0)
            sites[domain] += 1
        sites = sites.items()
        sites.sort(key=lambda x: x[1], reverse=True)
        cache.set(key, sites, 60*60*3)

    return render(request, "admin/ad/feed_sources.html", {'sites': sites})


# поиск дублей по фотографиям - /admin/ad/ad/duplicates/
@staff_member_required
def show_photo_duplicates(request):
    from utils.paginator import HandyPaginator

    groups = Photo.find_ads_duplicates()
    paginator = HandyPaginator(groups, 10, request=request)

    groups = paginator.current_page.object_list
    for group in groups:
        group['photos'] = Photo.objects.filter(hash__in=group['hashes']).order_by('hash').distinct('hash')
        group['ads'] = Ad.objects.filter(user__isnull=False, pk__in=group['ad_ids']).order_by('user', 'created').select_related('user', 'region')

    return render(request, "admin/ad/show_photo_duplicates.html", {'paginator': paginator, 'groups': groups})


class RegionForm(forms.Form):
    region = forms.ModelChoiceField(label=u'регион', queryset=Region.objects.none(), empty_label=None)

    def __init__(self, *args, **kwargs):
        super(RegionForm, self).__init__(*args, **kwargs)
        region_filter = Q(subdomain=True) | Q(kind='province', parent__static_url=';')
        self.fields['region'].queryset = Region.objects.filter(region_filter).order_by('kind', 'name_ru')

@staff_member_required
def stats_by_propertytype(request):
    cols = (('sale', u'Продажа'), ('rent', u'Аренда долгосрочная'), ('rent_daily', u'Посуточно'),
            ('newhomes', u'Новостройки'), )
    rows = (({'property_type':'flat'}, u'Все квартиры'),
            ({'rooms': 1, 'property_type':'flat'}, u'1 к. квартира'), ({'rooms': 2, 'property_type':'flat'}, u'2 к. квартира'),
            ({'rooms': 3, 'property_type':'flat'}, u'3 к. квартира'), ({'rooms__gt': 3, 'property_type':'flat'}, u'>3 к. квартира '),
            ({'property_type': 'room'}, u'Комната'), ({'property_type': 'house'}, u'Дом'), ({'property_type': 'commercial'}, u'Коммерческая'),
            ({}, u'Вся недвижимость'),
    )
    queryset = Ad.objects.filter(is_published=True)

    form = RegionForm(request.GET or {'region':1})
    if form.is_valid():
        if form.cleaned_data['region']:
            queryset = queryset.filter(region__in=form.cleaned_data['region'].get_descendants(include_self=True))

    stats = []
    for filter, label in rows:
        stats.append([label, []])
        for deal_type, label2 in cols:
            stats[-1][1].append(queryset.filter(deal_type=deal_type, **filter).count())

    return render(request, "admin/ad/stats_by_propertytype.html", locals())


@staff_member_required
def is_agency_phones_ajax_task(request):
    task = cache.get('is_agency_phones_task', {})
    data = {
        'status': task.pop('status', u'no status'),
        'done': task.pop('done', '')
    }
    return JsonResponse(data)


# страница для проверки корректности базы регионов и юзеров
@staff_member_required
def fastcheck(request):

    # дубли поддоменов
    subdomain_errors = []
    for subdomain in Region.get_subdomains():
        similar_regions = Region.objects.filter(name=subdomain.name, kind=subdomain.kind).exclude(id=subdomain.id)
        for region in similar_regions:
            # ID 11244 - Львовская область, Николаевский район, Николаев
            if region.id != 11244:
                subdomain_errors.append((subdomain, region))

    return render(request, "admin/fastcheck.html", locals())
