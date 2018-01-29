# coding: utf-8
import collections

from django import forms
from django.db.models import Q
from django.forms import BaseFormSet
from django.utils.translation import ugettext_lazy as _

from ad import choices as ad_choices
from ad.models import Region, SubwayStation
from agency.forms import CityTypeaheadField
from newhome.models import Newhome, Layout, Room, BuildingQueue, BuildingSection, Developer
from ad import choices as ad_choices


class ProgressForm(forms.Form):
    """todo: избавится от классов"""
    date = forms.DateField(widget=forms.TextInput(attrs={
        'class': 'date calendar'
    }), input_formats=['%d-%m-%Y'])


class NewhomeForm(forms.ModelForm):
    class Meta:
        model = Newhome
        fields = [
            'name', 'price_at', 'building_class', 'seller', 'developer', 'website', 'content', 'ceiling_height',
            'buildings_total', 'flats_total', 'heating', 'phases', 'parking_info', 'walls', 'building_insulation',
            'number_of_floors', 'addr_country', 'addr_city', 'addr_street', 'addr_house'
        ]


class LayoutForm(forms.ModelForm):
    class Meta:
        model = Layout
        fields = ['name', 'rooms_total']


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        exclude = ['layout']


class BuildingEditForm(forms.Form):
    """Форма редактирования здания и секций к зданию"""
    name = forms.CharField()
    positions = forms.CharField(max_length=255)


class BuildingQueueForm(forms.ModelForm):
    """Форма добавления/редактирования очереди"""

    class Meta:
        model = BuildingQueue
        exclude = ['newhome', 'sections']


class QueueSectionForm(forms.Form):
    section = forms.ModelChoiceField(queryset=BuildingSection.objects.none(), required=False)


class QueueSectionFormSet(BaseFormSet):
    def __init__(self, *args, **kwargs):
        newhome_id = kwargs.pop('newhome_id')
        super(QueueSectionFormSet, self).__init__(*args, **kwargs)

        if newhome_id:
            for form in self.forms:
                form.fields['section'].queryset = BuildingSection.objects.filter(building__newhome__id=newhome_id)


class DeveloperForm(forms.ModelForm):
    city = CityTypeaheadField(label=_(u'Город'), required=False)

    class Meta:
        model = Developer
        fields = ('name', 'city', 'site')


class NewhomeFilterForm(forms.Form):
    status = forms.ChoiceField(required=False, choices=(
        ('', _(u'Все объявления')),
        ('active', _(u'Активные')),
        ('inactive', _(u'Неактивные')),
        ('removed', _(u'Удаленные')),
    ))
    search = forms.CharField(required=False)


class NewhomeSearchForm(forms.Form):
    region_search = forms.BooleanField(label=_(u'искать в регионах'), required=False, widget=forms.HiddenInput())
    region_city_id = forms.IntegerField(label=_(u'ID города'), required=False, widget=forms.HiddenInput())
    district = forms.ModelMultipleChoiceField(
        label=_(u'Район'), queryset=Region.objects.filter(kind='district'), required=False
    )

    price_from = forms.IntegerField(
        label=_(u'Цена от'), required=False,
        widget=forms.TextInput(attrs={'size': '4', 'placeholder': _(u'от'), 'type': 'number'})
    )
    price_to = forms.IntegerField(
        label=_(u'до'), required=False,
        widget=forms.TextInput(attrs={'size': '4', 'placeholder': _(u'до'), 'type': 'number'})
    )
    currency = forms.ChoiceField(label=_(u'Валюта'), choices=ad_choices.CURRENCY_CHOICES, required=False, )
    rooms = forms.MultipleChoiceField(label=_(u'Комнат'), required=False, choices=ad_choices.ROOMS_CHOICES)
    subway_stations = forms.ModelMultipleChoiceField(
        label=_(u'Ближайшая станция метро'), queryset=SubwayStation.objects.all(), required=False,
        widget=forms.widgets.SelectMultiple(attrs={'rows': 1})
    )
    addr_street_id = forms.IntegerField(required=False)
    addr_street = forms.CharField(
        label=_(u'Улица'), max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _(u'Начните вводить название улицы')})
    )
    name = forms.CharField(
        label=_(u'Название'), max_length=100, required=False,
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': _(u'Название новостройки')})
    )
    developer = forms.CharField(
        label=_(u'Застройщик'), max_length=100, required=False,
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': _(u'Наименование застройщика')})
    )

    # подготавливаем список дочерних регионов имеющие актуальные объявления,
    # а так же список удобств/услуг по выбранному типу сделки
    def prepare_choices(self, region):
        deal_type = 'newhomes'
        parents = {region.kind: region for region in region.get_parents()}
        locality = parents.get('village', None) or parents.get('locality', None)
        filters_with_properties = {'region_counter__deal_type': deal_type, 'region_counter__count__gt': 0}

        if region.kind in ['district', 'village', 'locality']:
            self.streets = list(region.get_descendants().filter(kind='street').exclude(parent__kind='village').values('id', 'name'))

        else:
            self.streets = []

        self.subway_lines = []

        if locality:
            # Подготавливаем красивые станции метро
            self.subway_lines = locality.subwayline_set.prefetch_related('stations')
            self.fields['subway_stations'].choices = [
                (
                    subway_line.name,
                    [(subway_station.id, subway_station.name) for subway_station in subway_line.stations.all()]
                ) for subway_line in self.subway_lines
                ]
            self.subway_url = '%ssubway.html' % region.get_deal_url(deal_type)

            street_filter = Q(kind='street', region_counter__deal_type=deal_type, region_counter__count__gt=0)
            if region.get_descendants().filter(street_filter).exists():
                self.streets_url = '%sstreets.html' % region.get_deal_url(deal_type)
            elif locality.get_descendants().filter(street_filter).exists():
                self.streets_url = '%sstreets.html' % locality.get_deal_url(deal_type)

            # районы города
            districts_groups = collections.defaultdict(list)
            districts = locality.get_children().filter(kind='district', **filters_with_properties).order_by('name')
            for district in districts:
                group = _(u'Микрорайоны')
                if u' район' in district.name:
                    group = _(u'Районы')
                short_name = district.name.replace(u"микрорайон", "").replace(u"мікрорайон", "").replace(u" район",
                                                                                                         "").strip()
                districts_groups[group].append([district.pk, short_name])
            self.district_url = '%sdistricts.html' % region.get_deal_url(deal_type)

            # сортирвока районов по имени
            for group in districts_groups:
                districts_groups[group] = sorted(districts_groups[group], key=lambda district: district[1])

            if districts_groups:
                self.fields['district'].choices = districts_groups.items()
            else:
                self.fields['district'].queryset = Region.objects.none()
        else:
            self.fields['district'].queryset = Region.objects.none()

    def clean_rooms(self):
        if self.cleaned_data.get('property_type', 'flat') == 'room' and self.cleaned_data.get('rooms'):
            raise forms.ValidationError(_(u'Недопустимое значение при указанном типе недвижимости'))
        return self.cleaned_data['rooms']

    def clean_price_from(self):
        data = self.cleaned_data
        if data['price_from'] and data['price_from'] < 0:
            raise forms.ValidationError(_(u'Цена не может быть отрицательной'))
        return data['price_from']

    def clean_price_to(self):
        data = self.cleaned_data
        if data['price_to'] and data['price_to'] < 0:
            raise forms.ValidationError(_(u'Цена не может быть отрицательной'))
        return data['price_to']
