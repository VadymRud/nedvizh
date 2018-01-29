# coding: utf-8
import xlwt
import StringIO
import datetime
import collections

from django import forms
from django.core.files.storage import default_storage
from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.db.models import Count, Sum

from ad.models import Ad, Region, ViewsCount
from custom_user.models import User
from profile.models import Stat, StatGrouped, Manager
from paid_services.models import Transaction, UserPlan


class WeekForm(forms.Form):
     since = forms.DateField(label=u'дата начала')
     end = forms.DateField(label=u'дата окончания')


@staff_member_required
def statistics_weekly(request):
    if not request.user.has_perm("%s.%s_%s" % ('profile', 'change', 'statgrouped')):
        raise Http404
    
    today = datetime.date.today()
    friday = today + datetime.timedelta( (4-today.weekday()) % 7 )

    since = friday - datetime.timedelta(days=7)
    end = friday

    form = WeekForm(request.GET or {'since':since, 'end':end})
    if form.is_valid():
        since = form.cleaned_data['since']
        end = form.cleaned_data['end']

    date_range = [since, end]

    ads_stats = collections.Counter()
    for user, agency, bank in Ad.objects.filter(is_published=True, created__range=date_range).values_list('user_id', 'user__agencies', 'bank_id'):
        if bank:     ads_stats['bank'] += 1
        elif agency: ads_stats['agency'] += 1
        elif user:   ads_stats['person'] += 1
        else:        ads_stats['feed'] += 1
    ads_stats['user'] = ads_stats['bank'] + ads_stats['agency'] + ads_stats['person']
    ads_stats['total'] = sum(ads_stats.values())

    users_stats = {'agency':collections.Counter(), 'person':collections.Counter()}
    for agency, date_joined, last_login in User.objects.filter(date_joined__lt=end).values_list('agencies', 'date_joined', 'last_login'):
        type = 'agency' if agency else 'person'
        users_stats[type]['total'] += 1
        if last_login and since < last_login.date() < end:
            users_stats[type]['active'] += 1
        if since < date_joined.date() < end:
            users_stats[type]['new'] += 1

    # вот так криво считаем активность
    last_login_range = [end - datetime.timedelta(days=30), end]
    users_stats['agency']['active'] = User.objects.filter(agencies__isnull=False, last_login__range=last_login_range).count()
    users_stats['person']['active'] = User.objects.filter(agencies__isnull=True, last_login__range=last_login_range).count()

    return render(request, "admin/statistics_weekly.html", locals())

STAT_TYPES = (
    ('contacts', u'просмотренных контактов'),
    ('ads', u'созданных объявления'),
    ('photos', u'количества объявлений с фото'),
)

from ad.choices import DEAL_TYPE_CHOICES

class ByProvinceForm(WeekForm):
    group = forms.ChoiceField(label=u'Группировка по', choices=STAT_TYPES, required=False)
    deal_type = forms.ChoiceField(label=u'Тип сделки', choices=[['', u'все']] + list(DEAL_TYPE_CHOICES), required=False)


@staff_member_required
def statistics_by_province(request):
    if not request.user.has_perm("%s.%s_%s" % ('profile', 'change', 'statgrouped')):
        raise Http404
    
    today = datetime.date.today()
    month_1st_day = today.replace(day=1)

    data = request.GET or {'since':month_1st_day, 'end':today, 'group':'contacts'}
    form = ByProvinceForm(data)
    if form.is_valid():
        data = form.cleaned_data

    date_range = [data['since'], data['end']]
    counter = collections.Counter()
    total = 0

    ads = Ad.objects.filter(created__range=date_range)
    if data['deal_type']:
        ads = ads.filter(deal_type=data['deal_type'])

    if data['group'] == 'photos':
        provincies = Region.get_provinces()
        for province in provincies:
            province.stats = {'with_photo':0, 'total':0}
            province.value = 0

        rows = ads.order_by('region__tree_path')\
            .values('region__tree_path', 'has_photos').order_by().annotate(count=Count('region__tree_path'))
        for row in rows:
            for province in provincies:
                if row['region__tree_path'] and row['region__tree_path'].startswith('%s.' % province.tree_path):
                    if row['has_photos']:
                        province.stats['with_photo'] += row['count']
                    province.stats['total'] += row['count']

        for province in provincies:
            province.value = '%s of %s' % (province.stats['with_photo'], province.stats['total'])
            if province.stats['total']:
                province.percent = province.stats['with_photo'] * 100 / province.stats['total']
                total += province.percent
        total = '%s %%' % (total / len(provincies))
    else:
        if data['group'] == 'contacts':
            for contacts_views, region_id, deal_type in ViewsCount.objects.filter(date__range=date_range).values_list('contacts_views', 'basead__ad__region_id', 'basead__ad__deal_type'):
                if not data['deal_type'] or data['deal_type'] == deal_type:
                    counter[region_id] += contacts_views
        elif data['group'] == 'ads':
            counter = dict(ads.order_by('region').values_list('region').annotate(count=Count('region')))

        # инициируем список областей и получаем список ID дочерних регионов
        provincies = Region.get_provinces()
        for province in provincies:
            province._children_ids = set(province.get_descendants(include_self=True).values_list('id', flat=True))
            province.value = 0

        # переносим данные по просмотрам из регионов в области
        for region_id, value in counter.items():
            for province in provincies:
                if region_id in province._children_ids:
                    province.value += value
                    total += value
                    break

        # подсчет процентов
        for province in provincies:
            if total:
                province.percent = float(province.value) * 100 / total

    return render(request, "admin/statistics_by_province.html", locals())


@staff_member_required
def statistics_ads_by_region(request):
    if not request.user.has_perm("%s.%s_%s" % ('profile', 'change', 'statgrouped')):
        raise Http404
    
    groups = {
        'cities': {'subdomain': True},
        'provincies': {'kind': 'province'}
    }
    stats = collections.defaultdict(list)
    for gpoup_name, filter in groups.items():
        for region in Region.objects.filter(**filter).order_by('name'):
            count = Ad.objects.filter(is_published=True, region__in=region.get_descendants(True)).count()
            stats[gpoup_name].append([region, count])

    return render(request, "admin/statistics_ads_by_region.html", locals())


@staff_member_required
def statistics(request):
    if not request.user.has_perm("%s.%s_%s" % ('profile', 'change', 'statgrouped')):
        raise Http404

    month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
    active_users = collections.Counter()
    for agency_id in User.objects.filter(last_login__gt=month_ago).values_list('agencies', flat=True):
        if agency_id:
            active_users['agency'] += 1
        else:
            active_users['person'] += 1

    # данные обновляются по крону в crons.views.calculate_data_for_graphs
    properties_stats = cache.get('global_properties_statistics', [])
    users_stats = cache.get('global_users_statistics', [])
    viewscount_stats = cache.get('viewscount_per_month_statistics', [])

    parser_chart = cache.get('graph_feeds_properties', {'values': [0]})
    user_ads_chart = cache.get('graph_users_properties', {})
    new_users = cache.get('graph_users', {})

    return render(request, "admin/statistics.html", locals())


@staff_member_required
def export_profiles_stats(request):
    if not request.user.has_perm("%s.%s_%s" % ('profile', 'change', 'statgrouped')):
        raise Http404
    
    if request.method == 'POST':
        book = xlwt.Workbook(encoding='cp1251')
        header = [u'email', u'область', u'количество активных объявлений']
        usertypes = {
            2: u'агентства (активные)',
            1: u'частники (активные)',
        }

        sheets = {}
        for usertype, name in usertypes.items():
            sheet = book.add_sheet(name)
            [sheet.write(0, k, v) for k, v in enumerate(header)]
            sheets[usertype] = {'sheet': sheet, 'current_row': 0}

        properties = list(Ad.objects.filter(is_published=True).values_list('user').annotate(properties=Count('id')).order_by('user'))
        properties_dict = {}
        while properties:
            user_id, count = properties.pop(0)
            properties_dict[user_id] = count

        users = list(User.objects.filter(is_active=True).values_list('email', 'agencies', 'region').order_by('id'))
        regions = dict(Region.objects.filter(kind='province').values_list('id', 'name'))

        while users:
            user_id, email, user_agencies, region_id = users.pop(0)
            count = properties_dict.pop(user_id, 0)
            region = regions.get(region_id, '')
            if user_agencies:
                usertype = 2
            else:
                usertype = 1
            sheets[usertype]['current_row'] += 1
            [sheets[usertype]['sheet'].write(sheets[usertype]['current_row'], k, v) for k, v in enumerate([email or ('ID: %d' % user_id), region, count])]

        buffer = StringIO.StringIO()
        book.save(buffer)
        response = HttpResponse(buffer.getvalue(), content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename=MestoUA_export_%s.xls' % datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
        return response
    else:
        return render(request, 'admin/export_profiles_stats.html', locals())


def export_entrances_stats(request):
    if not request.user.has_perm("%s.%s_%s" % ('profile', 'change', 'statgrouped')):
        raise Http404
    
    now = datetime.datetime.today().replace(day=15)
    months = int(request.GET.get('months', 3))
    month_start = 0 if 'with_today' in request.GET else 1
    dates = [now - datetime.timedelta(days=i*30) for i in range(month_start, months+1)[::-1]]
    date_columns = [ date.strftime("%b %Y") for date in dates ]
    data_template = { date:0 for date in date_columns }

    book = xlwt.Workbook(encoding='utf8')
    usertypes = (
        (1, u'частники', {'user__agencies__isnull':True}),
        (2, u'агентства', {'user__agencies__isnull':False}),
    )

    font = xlwt.Font()
    font.bold = True
    bold_style = xlwt.XFStyle()
    bold_style.font = font

    # индивидуальная статистика по каждому юзеру за последние 4 месяца
    user_columns = [u'User ID', u'Пользователь', u'Город']
    header1 = ['']*len(user_columns) + [u'Объявления'] + ['']*(len(date_columns)-1) + [u'Заходы'] + ['']*(len(date_columns)-1)
    header2 = user_columns + date_columns*2

    for usertype, name, user_filter in usertypes:
        sheet = book.add_sheet(u'детальная статис-ка (%s)' % name)
        sheet.col(1).width = 10000
        sheet.col(2).width = 6000

        [sheet.write(0, k, v, style=bold_style) for k, v in enumerate(header1)]
        [sheet.write(1, k, v, style=bold_style) for k, v in enumerate(header2)]

        collect_data = {}
        for date in dates:
            date_str = date.strftime("%b %Y")
            users = StatGrouped.objects.filter(date__year=date.year, date__month=date.month, user__isnull=False)\
                .filter(**user_filter).values('user', 'entrances', 'active_properties')
            for user in users:
                user_id = user['user']
                if user_id not in collect_data:
                    collect_data[user_id] = {
                        'properties': data_template.copy(),
                        'entrances': data_template.copy()
                    }
                collect_data[user_id]['properties'][date_str] = user['active_properties']
                collect_data[user_id]['entrances'][date_str] = user['entrances']

        users = User.objects.filter(pk__in=collect_data.keys()).prefetch_related('region')
        for user in users:
            collect_data[user.id]['name'] = " ".join([user.email, user.first_name, user.last_name])
            collect_data[user.id]['city'] = user.city # user.region.name if user.region else ''

        row_index = 2
        for user_id, stats in collect_data.items():
            if 'name' not in stats:
                del collect_data[user_id]
                continue
            row = [user_id, stats['name'], stats['city']]
            for field in ['properties', 'entrances']:
                for date in date_columns:
                    row.append(stats[field][date])
            [sheet.write(row_index, k, v) for k, v in enumerate(row)]
            row_index += 1

    # сводная статистика по всем юзерам за последние 4 месяца
    for usertype, name, user_filter in usertypes:
        sheet = book.add_sheet(u'сводная статистика (%s)' % name)
        sheet.col(0).width = 3000
        [sheet.write(0, k, v, style=bold_style) for k, v in enumerate([u''] + date_columns)]

        rows_labels = {
            'entrances': (u'Заходы', ('1', '2', '3', '4', '5', u'более 5')),
            'properties': (u'Объявления', (u'до 30', u'31-100', u'больше 100')),
        }
        collect_data = {key: {} for key in rows_labels.keys() }
        for key, labels in rows_labels.items():
            for label in labels[1]:
                collect_data[key][label] = data_template.copy()

        for date in dates:
            date_str = date.strftime("%b %Y")

            users = StatGrouped.objects.filter(date__year=date.year, date__month=date.month, user__isnull=False)\
                .filter(**user_filter).values('user', 'entrances', 'active_properties')

            for user in users:
                if 0 < user['entrances'] <= 5:
                    collect_data['entrances'][str(user['entrances'])][date_str] += 1
                elif user['entrances'] > 5:
                    collect_data['entrances'][u'более 5'][date_str] += 1

                if 0 < user['active_properties'] <= 30:
                    collect_data['properties'][u'до 30'][date_str] += 1
                elif 30 < user['active_properties'] <= 100:
                    collect_data['properties'][u'31-100'][date_str] += 1
                elif user['active_properties'] > 100:
                    collect_data['properties'][u'больше 100'][date_str] += 1

        row_index = 1
        for key, labels in rows_labels.items():
            sheet.write(row_index, 0, labels[0], style=bold_style)
            row_index += 1

            for label in labels[1]:
                row = [label] + [collect_data[key][label][date] for date in date_columns]
                [sheet.write(row_index, k, v) for k, v in enumerate(row)]
                row_index += 1

            row_index += 1

    buffer = StringIO.StringIO()
    book.save(buffer)

    response = HttpResponse(buffer.getvalue(), content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename=MestoUA_export_entrances_%s.xls' % datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
    return response


def export_ads_by_region_stats(request=None):
    if not request.user.has_perm("%s.%s_%s" % ('profile', 'change', 'statgrouped')):
        raise Http404
    
    regions = {region.id: region for region in Region.get_provinces()}
    regions_children = {region.id: set(region.get_children_ids()) for region in regions.values()}
    managers = {manager.id: manager for manager in Manager.objects.all()}

    book = xlwt.Workbook(encoding='utf8')
    usertypes = (
        (1, u'частники', {'agencies__isnull':True}),
        (2, u'агентства', {'agencies__isnull':False}),
    )

    font = xlwt.Font()
    font.bold = True
    bold_style = xlwt.XFStyle()
    bold_style.font = font

    collect_data = collections.defaultdict(dict)

    import time
    start = time.time()

    now = datetime.datetime.now()
    periods = {
        'p1': [now - datetime.timedelta(days=7), now],
        'p2': [now - datetime.timedelta(days=1*30), now - datetime.timedelta(days=7)],
        'p3': [now - datetime.timedelta(days=3*30), now - datetime.timedelta(days=1*30)],
        'p4': [now - datetime.timedelta(days=6*30), now - datetime.timedelta(days=3*30)],
        'p5': [now - datetime.timedelta(days=9*30), now - datetime.timedelta(days=6*30)],
        'p6': [now - datetime.timedelta(days=12*30), now - datetime.timedelta(days=9*30)],
        'p7': [now - datetime.timedelta(days=5*12*30), now - datetime.timedelta(days=12*30)],
    }
    for period_id, date_range in periods.items():
        data = Ad.objects.filter(is_published=True, created__range=date_range).values('user', 'deal_type', 'region').annotate(count=Count('user')).order_by()
        for row in data:
            user = row['user']
            if user not in collect_data['ads']:
                collect_data['ads'][user] = collections.defaultdict(collections.Counter)

            for region_id, children in regions_children.items():
                if row['region'] in children:
                    user_data = collect_data['ads'][user][region_id]
                    user_data[period_id] += row['count']
                    user_data[row['deal_type']] += row['count']

    # подсчет количество простров контактов в срезе юзер + регион объявления
    for period_id, date_range in periods.items():
        data = ViewsCount.objects.filter(basead__ad__is_published=True, date__range=date_range).values('basead__ad__user', 'basead__ad__region', 'basead__ad__deal_type').annotate(count=Sum('contacts_views')).order_by()
        for row in data:
            user = row['basead__ad__user']
            if user not in collect_data['views']:
                collect_data['views'][user] = collections.defaultdict(collections.Counter)

            for region_id, children in regions_children.items():
                if row['basead__ad__region'] in children:
                    user_data = collect_data['views'][user][region_id]
                    user_data[period_id] += row['count']
                    user_data[row['basead__ad__deal_type']] += row['count']

    print time.time() - start

    # заголовки таблицы
    user_columns = [u'User ID', u'Ссылка в админке', u'Пользователь', u'Город', u'Менеджер', u'Оборот', u'Область', u'',
                    u'до 1 недели', u'1-4 нед.', u'1-3 мес.', u'3-6 мес.', u'6-9 мес.', u'9-12 мес.', u'более года', '',
                    u'Продажа', u'Аренда', u'Посуточная', u'Новостройки']

    for key, group in collect_data.items():
        basename = {'ads':u'объявлений', 'views':u'просмотры'}[key]
        user_ids = set(group.keys())
        for usertype, name, user_filter in usertypes:
            print 'start sheet', time.time() - start
            sheet = book.add_sheet(u'%s (%s)' % (basename, name))
            sheet.col(1).width = 12000
            sheet.col(2).width = 12000
            sheet.col(3).width = 6000
            sheet.col(4).width = 6000

            [sheet.write(0, k, v, style=bold_style) for k, v in enumerate(user_columns)]

            row_index = 1
            users = User.objects.filter(**user_filter).values('id', 'city', 'email', 'first_name', 'last_name', 'manager').order_by('-ads_count')
            print 'after user query', time.time() - start
            for user in users:
                if user['id'] not in user_ids:
                    continue

                name = " ".join([user['email'], user['first_name'], user['last_name']])
                # entranses = Stat.objects.filter(user=user['id'], date=datetime.datetime.now() - datetime.timedelta(days=30)).values('user').aggregate(entrances=Sum('entrances'))['entrances']
                revenue = Transaction.objects.filter(user_id=user['id'], amount__gt=0).values('user').aggregate(amount=Sum('amount'))['amount']
                manager = unicode(managers.get(user['manager'], ''))
                user_data = [user['id'], 'http://mesto.ua/admin/custom_user/user/?id=%s' % user['id'], name, user['city'], manager, revenue]

                for region_id, stats in group[user['id']].items():
                    row = user_data +  \
                          [regions[region_id].name.replace(u' область', '')] + [u''] + \
                          [stats['p%s' % period] for period in xrange(1, 8)] + [u''] + \
                          [stats[deal_type] for deal_type in ['sale', 'rent', 'rent_daily', 'newhomes']]

                    [sheet.write(row_index, k, v) for k, v in enumerate(row)]
                    row_index += 1
            print 'end sheet', time.time() - start

    filename = 'export_ads_by_region_stats%s.xls' % datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
    book.save(filename)

    buffer_io = StringIO.StringIO()
    book.save(buffer_io)

    response = HttpResponse(buffer_io.getvalue(), content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    return response


@staff_member_required
def add_transaction(request):
    from django import forms
    from django.http import HttpResponseForbidden
    from paid_services.models import Transaction, TRANSACTION_TYPE_CHOICES

    if request.user.groups.filter(id=12).count() == 0 and not request.user.is_superuser:
        return HttpResponseForbidden(u'У вас нет доступа к этой странице')

    type_choices = []
    for transaction_type, type_display in TRANSACTION_TYPE_CHOICES:
        if transaction_type in (1, 7):
            type_choices.append((transaction_type, type_display))

    class Form(forms.Form):
        email = forms.EmailField(label=u'E-mail пользователя')
        type = forms.ChoiceField(label=u'Тип транзакции', choices=type_choices)
        amount = forms.IntegerField(label=u'Сумма', min_value=1)

        def clean_email(self):
            email = self.cleaned_data['email']

            try:
                User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                raise forms.ValidationError(u'У нас нет такого пользователя')
            except User.MultipleObjectsReturned:
                raise forms.ValidationError(u'Два пользователя с таким e-mail')
            else:
                return email

    if request.POST:
        form = Form(request.POST)
        if form.is_valid():
            type = int(form.cleaned_data['type'])
            user = User.objects.get(email__iexact=form.cleaned_data['email'])
            comment = u'%s, внес %s' % (dict(type_choices)[type], request.user.email)
            transaction = Transaction(user=user, amount=form.cleaned_data['amount'], type=type, comment=comment)
            transaction.save()
            return redirect(reverse('admin:paid_services_transaction_changelist') + ('?user=%d' % user.id))
    else:
        form = Form()

    return render(request, 'admin/add_transaction.html', locals())


@staff_member_required
def statistics_monthly(request):
    # Number of customers at month end - всего юзеров на конец месяца на конец месяца
    # Including number of realtors at month end - всего риелторов на конец месяца
    # Number of listings at month end - активных листингов на конец месяца
    # Number of leads for the month - открытые контакты за месяц

    periods = []

    def date(y, m, d):
        return datetime.date(year + (m-1)//12, (m-1) % 12 + 1, 1)

    year = 2016
    start_month = 4 if 'show_me_past' not in request.GET else 1
    for m in xrange(start_month, 13):
        if m > 12:
            m = 1
            year += 1

        start = date(year, m, 1)
        end = date(year, m+1, 1) - datetime.timedelta(days=1)
        periods.append([start, end, ['-', '-', '-', '-']])

    print periods

    for period in periods:
        start, end, data = period

        if end < datetime.date.today() or 'show_me_future' in request.GET:
            user_ids = UserPlan.objects.filter(start__lt=end, end__gt=end).values_list('user', flat=True)
            customers = User.objects.filter(pk__in=user_ids).count()
            realtors = User.objects.filter(pk__in=user_ids, realtors__isnull=False).count()
            listings = Stat.objects.filter(date=end).aggregate(sum=Sum('active_properties'))['sum'] or 0
            stat = StatGrouped.objects.filter(date=start, user=None).first()
            opened_contacts = stat.ad_contacts_views if stat else 0
            leads = Transaction.objects.filter(time__range=[start, end], type=82).count()

            period[2] = [customers, realtors, listings, opened_contacts, leads]

    return render(request, "admin/statistics_monthly.html", locals())


@staff_member_required
def statistics_analysis_disclosed_contacts(request):
    class AnalysisDisclosedContactsForm(WeekForm):
        google_analytics_file = forms.FileField(required=True, label=u'Файл выгрузки из GA')

    is_job_created = False
    if request.method == 'POST':
        form = AnalysisDisclosedContactsForm(request.POST, request.FILES)
        if form.is_valid():
            default_storage.save('statistics_analysis_disclosed_contacts.csv', request.FILES['google_analytics_file'])

            import tasks
            tasks.statistics_analysis_disclosed_contacts(
                request.user.email, form.cleaned_data['since'], form.cleaned_data['end'])
            is_job_created = True

    else:
        form = AnalysisDisclosedContactsForm(initial={
            'since': datetime.date.today() - datetime.timedelta(days=14),
            'end': datetime.date.today()})

    return render(request, "admin/statistics_looking_through.html", locals())
