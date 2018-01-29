# coding: utf-8

from django import forms
from django.db.models import Q
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.template.loader import get_template
from django.template.defaultfilters import floatformat
from django.core.cache import cache
from django.conf import settings
from django.core.urlresolvers import reverse

from ad import choices as ad_choices
from ad.models import Ad, ReservedDate, Region, Facility, Rules, PROPERTY_COMMERCIAL_TYPE_CHOICES, SubwayStation, \
    SubwayLine
from phones import PhoneField, pprint_phone
from utils.calendars import get_calendar
from custom_user.models import User

import collections

class CalendarsWidget(forms.TextInput):
    def _media(self):
        return forms.Media(js=('js/libs/jquery.json-2.3.min.js', 'js/calendars_widget.js',))
    media = property(_media)

    def render(self, name, value, attrs=None):
        attrs['class'] = 'calendars ' + getattr(attrs, 'class', '')
        attrs['style'] = 'display:none;' + getattr(attrs, 'style', '')
        field_html = super(CalendarsWidget, self).render(name, value, attrs=attrs)
        calendar_html = mark_safe(get_template('ad/calendars_widget.jinja.html').render({'name': name, 'calendar': get_calendar()}))
        return field_html + calendar_html

class BootstrapRadioSelect(forms.RadioSelect):
    pass

class AreaInput(forms.TextInput):
    input_type = 'number'

    def _format_value(self, value):
        return floatformat(value).replace(",", ".") # поле numbers поддерживает только разделитель "."

from django.forms import formset_factory, BaseFormSet
from ad.phones import PhoneField
from ad.models import Phone

from collections import Counter

class BasePhonesFormSet(BaseFormSet):
    def clean(self):
        phones = [form.cleaned_data['phone'] for form in self.forms if form.is_valid()]

        if any(phones):
            for index, phone in enumerate(phones):
                if phone and (phone in phones[:index] + phones[index + 1:]):
                    self.forms[index].add_error('phone', u'Повторяющийся номер')

    def update_phones_m2m(self, m2m_manager):
        phones = []
        for form in self.forms:
            phone = form.cleaned_data.get('phone', None)
            if phone:
                phones.append(Phone.objects.get_or_create(number=phone)[0])
        
        m2m_objects = list(m2m_manager.all())

        for order, phone in enumerate(phones, start=1):
            phone_is_founded = False
            for m2m_obj in m2m_objects:
                if m2m_obj.phone_id.strip() == phone.number.strip():
                    if m2m_obj.order != order:
                        m2m_obj.order = order
                        m2m_obj.save()
                    phone_is_founded = True
                    m2m_objects.remove(m2m_obj) # в списке останутся только связи, которые нужно удалить
            if not phone_is_founded:
                m2m_manager.create(phone=phone, order=order)

        for m2m_obj in m2m_objects:
            m2m_obj.delete()

class BaseAdPhonesFormSet(BasePhonesFormSet):
    def __init__(self, *args, **kwargs):
        super(BaseAdPhonesFormSet, self).__init__(*args, **kwargs)

        for order, form in enumerate(self.forms, start=1):
            form.fields['phone'].label += ' #%d' % order

    def clean(self):
        super(BaseAdPhonesFormSet, self).clean()
        phones = [form.cleaned_data.get('phone', None) for form in self.forms]
        if not any(phones):
            self.forms[0].add_error('phone', u'Необходимо указать хотя бы один телефон')

class BaseUserPhonesFormSet(BasePhonesFormSet):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super(BaseUserPhonesFormSet, self).__init__(*args, **kwargs)

    def clean(self):
        super(BaseUserPhonesFormSet, self).clean()

        for form in self.forms:
            number = form.cleaned_data.get('phone', None)
            if number:
                if User.objects.filter(phones__number=number).exclude(id=self.user.id).exists():
                    form.add_error('phone', _(u'Номер телефона "%s" уже используется в другом аккаунте, укажите другой номер') % pprint_phone(number))


class PhoneForm(forms.Form):
    '''
        Всё это закомментировано, т.к. эти файлы загружаются в main.js в функции initPhoneMask()
    '''
    # class Media:
    #     js = ('js/libs/phoneformat.min.js', 'libs/bootstrap-select/bootstrap-select.min.js', 'js/phones_form_v2.js')
    #     css = {'all': ['libs/bootstrap-select/bootstrap-select.min.css', 'libs/country-flags/flags.css']}

    phone = PhoneField(required=False, label=u'Телефон')

AdPhonesFormSet = formset_factory(PhoneForm, formset=BaseAdPhonesFormSet, max_num=3, min_num=3)
UserPhonesFormSet = formset_factory(PhoneForm, formset=BaseUserPhonesFormSet, min_num=5, max_num=5)

# используется при импорте, в парсере, в mobile_api и т.д. для единой схемы работы с телефонами в объялениях
def create_ad_phones_formset(raw_phones):
    formset_data = {
        'form-TOTAL_FORMS': 3,
        'form-INITIAL_FORMS': 3,
    }
    for index, phone in enumerate(raw_phones):
        formset_data['form-%d-phone' % index] = phone
    return AdPhonesFormSet(formset_data)


replaced_labels = (
    ('area', _(u'Площадь')),
    ('floor', _(u'Этаж')),
    ('building_walls', _(u'Энергоэффективность')),
)


class PropertyForm(forms.ModelForm):
    description = forms.CharField(label=_(u'Описание'), required=True, widget=forms.Textarea(attrs={'rows': 7}))

    international = forms.ChoiceField(label=_(u'Каталог для размещения'), widget=BootstrapRadioSelect(), initial='no',
                                      required=False, choices=(('no', _(u'Mesto.ua')), ('yes', _(u'Зарубежная недвижимость'))))

    deal_type = forms.ChoiceField(label=_(u'Тип сделки'), choices=ad_choices.DEAL_TYPE_CHOICES,
                                  widget=BootstrapRadioSelect(),
                                  help_text=_(u'Путешественникам Mesto.ua нравится выбирать из множества разных типов жилья'),)
    property_type = forms.ChoiceField(label=_(u'Тип недвижимости'), choices=ad_choices.PROPERTY_TYPE_CHOICES,
                                  widget=BootstrapRadioSelect(),
                                  help_text=_(u'Тип размещения &mdash; один из самых важных критериев для путешественников на Mesto.ua'),)

    price = forms.IntegerField(label=_(u'Цена'), widget=forms.NumberInput(attrs={'min':10}))
    facilities = forms.ModelMultipleChoiceField(label=_(u'Удобства'), required=False, widget=forms.CheckboxSelectMultiple(), queryset=Facility.objects.all())
    rules = forms.ModelMultipleChoiceField(label=_(u'Правила размещения'), required=False, widget=forms.CheckboxSelectMultiple(), queryset=Rules.objects.all())

    reserved = forms.CharField(label=_(u'Занятые дни'), widget=CalendarsWidget(), required=False, help_text=_(u'Сэкономьте ваше время и деньги с помощью календаря'))

    promotion = forms.ChoiceField(label=_(u'Продвижение объявления'), widget=BootstrapRadioSelect(), initial='', required=False,
                             choices=(('no', _(u'Обычное объявление')), ('vip', _(u'VIP объявление (7 дней)'))))
    uk_to_international = forms.BooleanField(label=u'%s (<a href="%s" target="_blank">%s</a>)<br/><small>%s</small>' %
                                                   (_(u'Добавить объявление в международные каталоги'), '/faq/zarubezhnaya-nedvizhimost/razmeschenie-v-mezhdunarodnyih-katalogah/',
                                                    _(u'посмотреть список каталогов'),
                                                    _(u'действует только для обьектов недвижимости, которые территориально находятся в Украине')),
                                              widget=forms.CheckboxInput(), required=False, help_text=_(u'Узнайте больше о <a href="/account/services/publication/vips/" target="_blank">возможностях продвижения</a> \
                                                                                                          вашего объявления, заполненные поля сохраняются <br/> <br/> \
                                                                                                          <span class="ad_mark_new">New!</span><span class="ad_draw_banner"> \
                                                                                                          Закажите печатный баннер на балкон от 150 грн и продавайте объект еще быстрее \
                                                                                                           <a target="_blank" href="http://promo.mesto.ua/banner_prodaz/">подробнее здесь</a></span>'))

    tos = forms.BooleanField(widget=forms.CheckboxInput(), error_messages={ 'required': _(u"Вы должны согласиться с правилами размещения объявлений") })
    
    class Meta:
        model = Ad
        fields = ('international', 'deal_type', 'property_type','property_commercial_type',
                  'addr_country', 'addr_city', 'addr_street', 'addr_house',
                  'rooms',  'area', 'area_living', 'area_kitchen', 'floor', 'floors_total',
                  'building_layout', 'building_type', 'building_type_other', 'building_walls', 'building_windows',
                  'building_heating', 'description', 'currency', 'price', 'guests_limit', 'facilities', 'rules',
                  'is_bargain_possible', 'without_commission')

        fieldsets = (
            (None, {
                'fields': ('international',)
            }),
            (None, {
                'fields': ('deal_type', 'property_type',
                           ('property_commercial_type',),
                           ('addr_country', 'addr_city',),
                           ('addr_street', 'addr_house')
                )
            }),
            (None, {
                'fields': (
                    ('rooms',),
                    ('area', 'area_living', 'area_kitchen'),
                    'description',
                    ('price', 'currency', 'is_bargain_possible', 'without_commission')
                )
            }),
            (None, {
                'fields': (
                    ('floor', 'floors_total'),
                    ('building_layout', 'building_type', 'building_type_other'),
                    ('building_walls', 'building_windows', 'building_heating'),
                    ('guests_limit',),
                    'facilities', 'rules', 'reserved', 'tos'
                )
            }),
            (None, {
                'fields': ('promotion', 'uk_to_international')
            }),
        )
        classes = {
            'international': {'controls': 'col-sm-20 btn-group-big'},
            'deal_type': {'controls': 'col-sm-20 btn-group-big'},
            'property_type': {'controls': 'col-sm-20 btn-group-big'},
            'property_commercial_type': {'group': 'hidden'},
            'area_living': {'group': 'for-living-property', 'label': 'hidden-lg'},
            'area_kitchen': {'group': 'for-living-property', 'label': 'hidden-lg'},
            'building_type_other': {'label': 'hidden-lg'},
            'promotion': {'controls': 'col-sm-20 btn-group-big'},
        }
        widgets = {
            'deal_type': BootstrapRadioSelect(),
            'property_type': BootstrapRadioSelect(),
            'rooms': forms.Select(choices=[(i, str(i)) for i in range(1, 25)]),
            'area': AreaInput(attrs={'min': 0, 'step': 0.1}),
            'area_kitchen': AreaInput(attrs={'min': 0, 'step': 0.1}),
            'area_living': AreaInput(attrs={'min': 0, 'step': 0.1}),
        }
    
    def clean_price(self):
        price = self.cleaned_data['price']
        currency = self.cleaned_data['currency']

        if price <= 0:
            raise forms.ValidationError(_(u"Цена должна быть больше нуля"))

        if 'deal_type' in self.cleaned_data and self.cleaned_data['deal_type'] == 'newhomes' and \
                ((price > 150000 and currency in ['UAH', 'RUB']) or (price > 5000 and currency in ['USD', 'EUR'])):
            raise forms.ValidationError(_(u"Неверная цена. Для новостроек цена указывается за квадратный метр"))
            
        return price

    def clean_addr_street(self):
        street = self.cleaned_data['addr_street']
        if not street and self.cleaned_data.get('property_type', None) != 'plot':
            raise forms.ValidationError(_(u'Обязательное поле.'))
        return street

    def clean_area(self):
        if 'deal_type' in self.cleaned_data and self.cleaned_data['deal_type'] == 'newhomes':
            try:
                if float(self.cleaned_data.get('area', 0.0)) < 1.0:
                    raise forms.ValidationError(_(u'Тип недвижимости "Новостройки" требует указания площади помещения'))

            except:
                raise forms.ValidationError(_(u'Площадь должна быть целым или дробным числом через точку'))

        return self.cleaned_data['area']

    def clean_property_commercial_type(self):
        if 'property_type' in self.cleaned_data and self.cleaned_data['property_type'] != 'commercial' and \
                        self.cleaned_data['property_commercial_type'] is not None:
            raise forms.ValidationError(_(u'Типы коммерческой недвижимости указываются только для коммерческой недвижимости'))
        return self.cleaned_data['property_commercial_type']

    def clean_reserved(self):
        import datetime
        import json

        old_reservations = set(self.instance.reserved.values_list('date', flat=True))
        try:
            reservations = set([datetime.datetime.strptime(date, '%Y-%m-%d').date() for date in json.loads(self.cleaned_data['reserved'])])
        except ValueError:
            reservations = []

        if old_reservations != reservations:
            self.instance.modified_calendar = datetime.datetime.now()
            self.update_m2m_reservations = True

        return reservations
    
    def __init__(self, *args, **kwargs):
        language_code = kwargs.pop('language_code', settings.LANGUAGE_CODE)
        subdomain = kwargs.pop('subdomain', '')

        super(PropertyForm, self).__init__(*args, **kwargs)

        self.facilities_by_deal_type = {
            deal_type: [facility.id for facility in Facility.get_facilities_by_deal_type(deal_type)]
            for deal_type, label in ad_choices.DEAL_TYPE_CHOICES
        }

        for field_key in ['floor', 'floors_total', 'building_type','building_walls','building_windows','building_heating', 'building_layout']:
            field = self.fields[field_key]
            field.choices = [('', u'--- %s ---' % field.label)] + list(field.choices)[1:]

        # каталог зарубежной недвижимости
        self.fields['addr_country'].choices = [('', u'------')] + self.fields['addr_country'].choices

        # если страна не Украина, то это верняк Зарубежный каталог
        if kwargs['instance'].addr_country != 'UA' or (not kwargs['instance'].id and subdomain == 'international'):
            self.fields['international'].initial = 'yes'

        # но если Украина, то может быть отдельно выбран экспорт в Зарубежные каталоги
        if kwargs['instance'].addr_country == 'UA' and kwargs['instance'].international_catalog:
            self.fields['uk_to_international'].initial = True

        # продвижение объявления
        if 'promotion' in self.fields:

            if kwargs['instance'].vip_type:
                self.fields['promotion'].initial = 'vip'

        if kwargs['instance'].pk and 'tos' in self.fields:
            del self.fields['tos']
        else:
            if kwargs['initial']['is_agency']:
                link_url = reverse('simplepage', kwargs={'url': '/about/ad-rules/'})
            else:
                link_url = reverse('simplepage', kwargs={'url': '/agencies/ad-rules/'})

            terms_url = '/about/terms-of-use/'
            link = u'<a href="%s" target="_blank">%s</a> и <a href="%s" target="_blank">%s</a>' % \
                   (link_url, _(u'Правилами размещения объявлений'), terms_url, _(u'Условиями использования сайта'))

            self.fields['tos'].label = _(u'Подтверждаю согласие с %s. '
                u'Объявления, не соответствующие вышеуказанным правилам будут удаляться без предупреждения.') % link

        for field, label in replaced_labels:
            self.fields[field].label = label

    def clean(self):
        cleaned_data = super(PropertyForm, self).clean()
        if 'rooms' in cleaned_data and 'property_type' in cleaned_data:
            if cleaned_data['property_type'] in ('flat', 'house') and not cleaned_data['rooms']:
                self._errors['rooms'] = self.error_class([_(u'Обязательное поле для выбранного типа недвижимости')])
                del cleaned_data['rooms']
                return cleaned_data
            if cleaned_data['property_type'] == 'plot' and cleaned_data['rooms']:
                cleaned_data['rooms'] = None
        return cleaned_data

DEAL_TYPE_SEARCH_CHOICES = ad_choices.DEAL_TYPE_CHOICES
PROPERTY_TYPE_SEARCH_CHOICES = [('all-real-estate', _(u'вся недвижимость') )] + list(ad_choices.PROPERTY_TYPE_CHOICES)
PROPERTY_COMMERCIAL_TYPE_SEARCH_CHOICES = [('', _(u'укажите тип') )] + list(PROPERTY_COMMERCIAL_TYPE_CHOICES)

SORT_CHOICES = (
    ('', _(u'по дате')),
    ('price_uah', _(u'по возрастанию цены')),
    ('-price_uah', _(u'по убыванию цены')),
)

ADDED_CHOICES = (
    (0, _(u'за всё время')),
    (3, _(u'за 3 дня')),
    (7, _(u'за неделю')),
    (14, _(u'за две недели')),
    (30, _(u'за месяц')),
)

FLOOR_CHOICES = (
    ('not-first', _(u'не первый')),
    ('not-last', _(u'не последний')),
    ('first', _(u'первый')),
    ('last', _(u'последний')),
)


class PropertySearchForm(forms.Form):
    region_search = forms.BooleanField(label=_(u'искать в регионах'),  required=False)
    region_city_id = forms.IntegerField(label=_(u'ID города'), required=False, widget=forms.HiddenInput())
    district = forms.ModelMultipleChoiceField(label=_(u'Район'), queryset=Region.objects.filter(kind='district'), required=False)

    price_from = forms.IntegerField(label=_(u'Цена от'), required=False,
                                    widget=forms.TextInput(
                                        attrs={'size': '4', 'placeholder': _(u'от'), 'type': 'number'}))
    price_to = forms.IntegerField(label=_(u'до'), required=False,
                                  widget=forms.TextInput(
                                      attrs={'size': '4', 'placeholder': _(u'до'), 'type': 'number'}))
    currency = forms.ChoiceField(label=_(u'Валюта'), choices=ad_choices.CURRENCY_CHOICES,  required=False, )

    deal_type = forms.ChoiceField(label=_(u'Тип недвижимости'), choices=DEAL_TYPE_SEARCH_CHOICES, required=False)
    property_type = forms.ChoiceField(label=_(u'Тип недвижимости'), choices=PROPERTY_TYPE_SEARCH_CHOICES, required=False)
    property_commercial_type = forms.ChoiceField(label=_(u'Тип коммерческой недвижимости'),
                                                 choices=PROPERTY_COMMERCIAL_TYPE_SEARCH_CHOICES,required=False)

    rooms = forms.MultipleChoiceField(label=_(u'Комнат'), required=False, choices=ad_choices.ROOMS_CHOICES)
    guests_limit = forms.MultipleChoiceField(label=_(u'Спальных мест'), required=False, choices=ad_choices.ROOMS_CHOICES)
    area_from = forms.IntegerField(label=_(u'Площадь общая'), required=False,
                                    widget=forms.TextInput(attrs={'size':'3', 'placeholder':_(u'от'), 'type':'number'}))
    area_to = forms.IntegerField(label=_(u'Площадь общая'), required=False,
                                  widget=forms.TextInput(attrs={'size':'3', 'placeholder':_(u'до'), 'type':'number'}))
    area_living_from = forms.IntegerField(label=_(u'Площадь жилая'), required=False,
                                    widget=forms.TextInput(attrs={'size':'3', 'placeholder':_(u'от'), 'type':'number'}))
    area_living_to = forms.IntegerField(label=_(u'Площадь жилая'), required=False,
                                  widget=forms.TextInput(attrs={'size':'3', 'placeholder':_(u'до'), 'type':'number'}))

    subway_stations = forms.ModelMultipleChoiceField(
        label=_(u'Ближайшая станция метро'), queryset=SubwayStation.objects.all(), required=False,
        widget=forms.widgets.SelectMultiple(attrs={'rows': 1})
    )

    facilities = forms.ModelMultipleChoiceField(label=_(u'Удобства'), queryset=Facility.objects.all(), required=False,
                                        widget=forms.widgets.CheckboxSelectMultiple())
    # rules = forms.ChoiceField(label=_(u'Правила'), choices=DEAL_TYPE_SEARCH_CHOICES, required=False)
    building_type = forms.MultipleChoiceField(label=_(u'Тип здания'), choices=ad_choices.BUILDING_TYPE_CHOICES, required=False,
                                        widget=forms.widgets.CheckboxSelectMultiple())
    building_walls = forms.MultipleChoiceField(label=_(u'Тип стен'), choices=ad_choices.WALLS_CHOICES, required=False,
                                        widget=forms.widgets.CheckboxSelectMultiple())
    building_layout = forms.MultipleChoiceField(label=_(u'Планировка'), choices=ad_choices.LAYOUT_CHOICES, required=False,
                                        widget=forms.widgets.CheckboxSelectMultiple())
    floor_variants = forms.MultipleChoiceField(label=_(u'Этаж'), choices=FLOOR_CHOICES, required=False,
                                        widget=forms.widgets.CheckboxSelectMultiple())

    addr_street_id = forms.IntegerField(required=False)
    addr_street = forms.CharField(
        label=_(u'Улица'), max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _(u'Начните вводить название улицы')})
    )

    keywords = forms.CharField(label=_(u'Ключевые слова'), max_length=100, required=False, help_text = _(u'Укажите слова, которые должно содержать объявление, например, телевизор, кондиционер, лифт и т.п.'))

    with_image = forms.BooleanField(label=_(u'Только с фото'),  required=False)
    without_commission = forms.BooleanField(label=_(u'Без комиссии'),  required=False)
    no_agent = forms.BooleanField(label=_(u'Без посредников'),  required=False)
    no_comission = forms.BooleanField(label=_(u'без комиссии'),  required=False)
    newhouse = forms.BooleanField(label=_(u'новый дом'),  required=False)
    wifi = forms.BooleanField(label=_(u'wi-fi'),  required=False)
    documents = forms.BooleanField(label=_(u'документы'),  required=False)
    in_center = forms.BooleanField(label=_(u'в центре'),  required=False)

    sort = forms.ChoiceField(label=_(u'Поле сортировки'), choices=SORT_CHOICES, required=False)
    added_days = forms.ChoiceField(label=_(u'Свежесть'), choices=ADDED_CHOICES, required=False)

    free_from = forms.DateField(label=_(u'Свободна с'), required=False, widget=forms.TextInput(attrs={'placeholder':_(u'дд.мм.гг'), 'class':'datepicker'}))
    free_to = forms.DateField(label=_(u'по'), required=False, widget=forms.TextInput(attrs={'placeholder':_(u'дд.мм.гг'), 'class':'datepicker'}))
    id = forms.IntegerField(label=_(u'ID объявления'), required=False, help_text=_(u'ID — это уникальный номер объявления'))

    # подготавливаем список дочерних регионов имеющие актуальные объявления,
    # а так же список удобств/услуг по выбранному типу сделки
    def prepare_choices(self, region, deal_type):
        # зарубежная недвижимость
        if region.tree_path.startswith('15805.') or region.tree_path == '15805':
            self.fields['currency'].choices = [('USD', u'$'), ('EUR', u'€'), ('UAH', u'грн.'),  ('RUR', u'руб.'),]
            self.fields['deal_type'].choices = [choice for choice in self.fields['deal_type'].choices if choice[0] in ['sale', 'rent'] ]
            self.fields['property_type'].choices = [choice for choice in self.fields['property_type'].choices if choice[0] in ['all-real-estate', 'flat', 'house', 'plot'] ]

            # больше никаких изменений в форме не требуется
            return

        if deal_type == 'rent_daily':
            self.fields['property_type'].choices = [type for type in self.fields['property_type'].choices if type[0] not in ['all-real-estate', 'plot', 'commercial', 'garages'] ]

        parents = {region.kind: region for region in region.get_parents()}
        locality = parents.get('village', None) or parents.get('locality', None)
        filters_with_properties = {'region_counter__deal_type': deal_type, 'region_counter__count__gt': 0}

        if region.kind in ['district', 'locality']:
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
                short_name = district.name.replace(u"микрорайон", "").replace(u"мікрорайон", "").replace(u" район", "").strip()
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

        if region.kind == 'province':
            self.settlements_url = '%ssettlements.html' % region.get_deal_url(deal_type)

        # фильтруем список услуг по типу сделки
        self.fields['facilities'].queryset = Facility.get_facilities_by_deal_type(deal_type)

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

    def clean(self):
        cleaned_data = super(PropertySearchForm, self).clean()
        if 'free_from' in cleaned_data and 'free_to' in cleaned_data:
            free_from = cleaned_data['free_from']
            free_to = cleaned_data['free_to']
            if [free_from, free_to].count(None) == 1:
                self._errors['free_from'] = self.error_class([_(u'Необходимо указать обе даты.')])
            elif all([free_from, free_to]) and free_from > free_to:
                self._errors['free_from'] = self.error_class([_(u'Конечная дата должна быть не меньше начальной.')])
            if self._errors.get('free_from') is not None:
                del cleaned_data['free_from']
                del cleaned_data['free_to']
        return cleaned_data

    @classmethod
    def get_multiple_fields(cls):
        multiple_fields = []
        for name, field in cls.declared_fields.items():
            if isinstance(field.widget, forms.SelectMultiple):
                multiple_fields.append(name)
        return multiple_fields


class InternationalContactForm(forms.Form):
    id = forms.CharField(widget=forms.HiddenInput())
    email = forms.EmailField(label=_(u'E-mail'))
    phone = PhoneField(required=False, label=u'Телефон')
    firstname = forms.CharField(label=_(u'Имя'))
    lastname  = forms.CharField(label=_(u'Фамилия'), required=False)

    def clean(self):
        import requests
        from lxml import etree

        data = super(InternationalContactForm, self).clean()
        data.update({'login':'ew_mestoUa_s84h', 'password':'d&b%4d2urSPMX^*F', 'EngineAdvertId':data['id'], 'language':'uk'})
        response = requests.post('http://edenway.beezbeez.com/re1/engine/httppost.ashx/EngineSendMail', data=data)

        if response.status_code == 200:
            root = etree.XML(response.content)
            status_code = int(root.findall('q1:StatusCode', root.nsmap)[0].text)
            if status_code != 0:
                message = root.findall('q1:StatusMessage', root.nsmap)[0].text
                raise forms.ValidationError(message)
