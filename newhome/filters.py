# coding: utf-8
import django_filters
from django.conf import settings
from django.contrib.gis.measure import Distance
from django.db.models import Q

from django.utils.translation import ugettext_lazy as _

from ad.models import make_coords_ranges_filters, make_sphere_distance_filters
from newhome.models import Newhome
from utils.currency import get_currency_rates


class NewhomePropertyFilter(django_filters.FilterSet):
    currency = django_filters.MethodFilter()
    price_from = django_filters.NumberFilter(name="price_at", lookup_type='gte')
    price_to = django_filters.NumberFilter(name="price_at", lookup_type='lte')

    name = django_filters.CharFilter()
    developer = django_filters.CharFilter()

    rooms = django_filters.MethodFilter()
    district = django_filters.MethodFilter()
    subway_stations = django_filters.MethodFilter()
    addr_street_id = django_filters.MethodFilter()

    class Meta:
        model = Newhome
        fields = ['id']
        order_by = (
            ('-updated', _(u'по дате')),
            ('price_uah', _(u'по возрастанию цены')),
            ('-price_uah', _(u'по убыванию цены')),
        )

    def filter_currency(self, qs, value):
        """
        Хак, конвертирующий исходные значения фильтра по цене из ин. валюты в гривны,
        т.к. поиск происходит по price_uah
        """
        if value and value != 'UAH':
            from decimal import Decimal
            curr_rate = get_currency_rates()[value]

            if self.form.cleaned_data['price_from']:
                self.form.cleaned_data['price_from'] *= Decimal(curr_rate * 0.998)
            if self.form.cleaned_data['price_to']:
                self.form.cleaned_data['price_to'] *= Decimal(curr_rate * 1.002)

        return qs

    @staticmethod
    def filter_name(qs, value):
        if value:
            return qs.filter(
                Q(name__icontains=value) | Q(keywords__icontains=value) | Q(developer__icontains=value) |
                Q(seller__icontains=value)
            )

        return qs

    @staticmethod
    def filter_developer(qs, value):
        if value:
            return qs.filter(developer__icontains=value)

        return qs

    @staticmethod
    def filter_rooms(qs, values):
        q_rooms = Q()
        for room in values:
            q_rooms |= Q(layouts__rooms_total__gte=room) if int(room) >= 5 else Q(layouts__rooms_total=room)

        return qs.filter(q_rooms)

    @staticmethod
    def filter_district(qs, values):
        district_filter = Q()
        for district in values:
            district_children = district.get_descendants(True)
            district_filter.add(Q(region__in=district_children), Q.OR)

        if district_filter:
            qs = qs.filter(district_filter)

        return qs

    # Фильтруем по ближайшим станциям метро, расстояние выбрано эксперементальным методом тыка
    @staticmethod
    def filter_subway_stations(qs, values):
        if values:
            q = Q()
            for subway_station in values:
                if settings.MESTO_USE_GEODJANGO:
                    distance_filters = make_sphere_distance_filters('point', subway_station.point, Distance(m=1000))

                else:
                    coords = (subway_station.coords_x, subway_station.coords_y)
                    distance_filters = make_coords_ranges_filters(coords, Distance(m=1000))
                q |= Q(**distance_filters)
            qs = qs.filter(q)

        return qs

    @staticmethod
    def filter_addr_street_id(qs, value):
        if value:
            qs = qs.filter(region_id=value)

        return qs
