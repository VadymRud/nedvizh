# coding: utf-8
from django.contrib.admin import SimpleListFilter, ListFilter
from django.db.models import Q
from django.utils.translation import ugettext as _
from django.core.cache import cache
import re

from ad.models import Region, Ad, Facility
from ad.choices import CONTENT_PROVIDER_CHOICES, ROOMS_CHOICES
from admin_ext.filters import InputFilter


# фильтр объявлений по источнику: из фидов или от пользователей
class PropertyBySource(SimpleListFilter):
    title = _(u'по владельцу')
    parameter_name = 'source'

    def lookups(self, request, model_admin):
        return (
            ('parser', _(u'парсер')),
            ('user', _(u'все пользователи')),
            ('person', _(u'частники')),
            ('agency', _(u'агентства')),
            ('import', _(u'импорт')),
            ('bank', _(u'банки')),
            ('export', _(u'платный экспорт')),
            ('plan', _(u'с тарифом')),
            ('ppk', _(u'с ППК')),
            ('ppk_shared', _(u'с ППК (общие)')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'bank':
            return queryset.filter(bank__isnull=False)
        if self.value() == 'import':
            return queryset.filter(user__isnull=False, xml_id__gt=0)
        elif self.value() == 'parser':
            return queryset.filter(user__isnull=True)
        elif self.value() == 'user':
            return queryset.filter(bank__isnull=True, user__isnull=False)
        elif self.value() == 'person':
            return queryset.filter(user__isnull=False, user__agencies__isnull=True)
        elif self.value() == 'agency':
            return queryset.filter(user__agencies__isnull=False)
        elif self.value() == 'export':
            return queryset.filter(international_catalog__isnull=False)
        elif self.value() == 'plan':
            from custom_user.models import User
            return queryset.filter(user__in=User.get_user_ids_with_active_plan(), addr_country='UA')
        elif self.value() == 'ppk':
            return queryset.filter(user__activityperiods__isnull=False, user__activityperiods__end=None)
        elif self.value() == 'ppk_shared':
            return queryset.filter(user__activityperiods__isnull=False, user__activityperiods__end=None, user__leadgeneration__dedicated_numbers=False)

        return queryset


class PropertyByContentProvider(SimpleListFilter):
    title = _(u'контент провайдер')
    parameter_name = 'cont_prov'

    def lookups(self, request, model_admin):
        return [('', u'объявления пользователей')] + list(CONTENT_PROVIDER_CHOICES)

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(content_provider=self.value())
        elif self.value() == '':
            return queryset.filter(content_provider=None)
        return queryset


# фильтр по основным городам
class CityRegionFilter(SimpleListFilter):
    title = u'город'
    parameter_name = 'city'
    template = 'admin/filter_select.html'

    def queryset(self, request, queryset):
        if self.value():
            region = Region.objects.get(pk=self.value())
            return queryset.filter(region__in=region.get_descendants(True))

    def lookups(self, request, model_admin):
        values = cache.get('filter_bycity')
        if not values:
            values = [[str(value[0]), value[1]] for value in
                      Region.objects.filter(subdomain=True).values_list('pk', 'name').order_by('name')]
            cache.set('filter_bycity', values, 3600 * 24)
        return values

class ProvinceRegionFilter(CityRegionFilter):
    title = u'область'
    parameter_name = 'province'

    def lookups(self, request, model_admin):
        values = cache.get('filter_byprovince')
        if not values:
            values = [(str(region.pk), region.name) for region in Region.get_provinces()]
            cache.set('filter_byprovince', values, 3600 * 24)
        return values

class DistrictFilter(CityRegionFilter):
    title = u'район'
    parameter_name = 'district'

    def lookups(self, request, model_admin):
        city_value = request.GET.get('city')
        if city_value:
            city = Region.objects.get(id=city_value, kind='locality')
            return city.get_descendants().filter(kind='district').values_list('id', 'name').order_by('name')

class PhoneByCity(CityRegionFilter):
    def queryset(self, request, queryset):
        if self.value():
            region = Region.objects.get(pk=self.value())
            phones = Ad.objects.filter(region__in=region.get_descendants(True)).values_list('phones__number', flat=True)
            return queryset.filter(number__in=phones)


class PropertyById(ListFilter):
    title = _(u'по ID')
    template = 'admin/filter_property_id.html'

    def has_output(self):
        return True

    def queryset(self, request, queryset):
        return None

    def choices(self, cl):
        return []


class PhoneNumberFilter(InputFilter):
    title = u'по номеру'
    parameter_name = 'number'
    queryset_lookup = 'number__contains'

    def clean_value(self, value):
        return re.sub(r'[^0-9]*', '', self.value)


class M2MPhoneFilter(PhoneNumberFilter):
    title = u'по номеру телефона'
    parameter_name = 'phone'
    queryset_lookup = 'phones__number__contains'


class IPAddressFilter(InputFilter):
    title = u'по IP-адресу'
    parameter_name = 'ip'
    queryset_lookup = 'ip_addresses__contains'

    def clean_value(self, value):
        return self.value.split(',')


# фильтр объявлений с заявкой на модерацию
class PropertyWithModeration(SimpleListFilter):
    title = u'на модерации'
    parameter_name = 'moderation'

    def lookups(self, request, model_admin):
        return [('yes', u'Да')]

    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(moderations__isnull=False, moderations__moderator__isnull=True)
        return queryset


class RoomsFilter(SimpleListFilter):
    title = u'количество комнат'
    parameter_name = 'rooms'

    def lookups(self, request, model_admin):
        return ROOMS_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(rooms__contains=[self.value()])
        return queryset


class PriceFromFilter(InputFilter):
    title = u'цена от'
    parameter_name = 'price_from'
    queryset_lookup = 'price_from__gte'
    input_type = 'number'


class PriceToFilter(InputFilter):
    title = u'цена до'
    parameter_name = 'price_to'
    queryset_lookup = 'price_to__lte'
    input_type = 'number'


class AreaFromFilter(InputFilter):
    title = u'площадь от'
    parameter_name = 'area_from'
    queryset_lookup = 'area_from__gte'
    input_type = 'number'


class AreaToFilter(InputFilter):
    title = u'площадь до'
    parameter_name = 'area_to'
    queryset_lookup = 'area_to__lte'
    input_type = 'number'


class FacilitiesFilter(SimpleListFilter):
    title = u'удобства'
    parameter_name = 'facilities'

    def lookups(self, request, model_admin):
        return [(facility.id, u'%s (%d)' % (facility.name, facility.id)) for facility in Facility.objects.all()]

    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(facilities__contains=[self.value()])
        return queryset

