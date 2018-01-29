# coding: utf-8

from django import forms

from ad.models import Ad, Facility, Photo
from utils.currency import get_currency_rates
from models import ad_attrs

PAID_PLACEMENT_CHOICES = (
    ('vip', u'VIP-размещение'),
    ('vip7', u'VIP-размещение'),  # TODO: предупредить клиентов с импортом, сделать рассылку, потом через какое-то время убрать
    ('intl_mesto', u'Размещение зарубежной недвижимости на сайте mesto.ua'),
    ('worldwide', u'Размещение в международных каталогах'),
)

class ImportAdForm(forms.ModelForm):
    class Meta:
        model = Ad
        fields = ad_attrs

    def clean(self):
        cleaned_data = super(ImportAdForm, self).clean()

        rates = get_currency_rates()

        if 'deal_type' in cleaned_data and 'price' in cleaned_data and 'currency' in cleaned_data:
            price_uah = cleaned_data['price'] * rates[cleaned_data['currency']]

            if cleaned_data['deal_type'] == 'newhouse' and price_uah > 150000:
                self.add_error('price', u'Неверная цена. Для новостроек цена указывается за квадратный метр')

            if cleaned_data['deal_type'] == 'sale' and 'property_type' in cleaned_data:
                if cleaned_data['property_type'] == 'plot':
                    if price_uah < (100 * rates['USD']):
                        self.add_error('price', u'Неверная цена. Минимальная цена продажи участков $100')
                else:
                    if price_uah < (1000 * rates['USD']):
                        self.add_error('price', u'Неверная цена. Минимальная цена продажи объекта $1000')

            if cleaned_data['deal_type'] == 'rent' and price_uah < (75 * rates['USD']):
                self.add_error('price', u'Неверная цена. Минимальная цена аренды объекта $75')

        if 'rooms' in cleaned_data and 'property_type' in cleaned_data:
            if cleaned_data['property_type'] in ('flat', 'house') and not cleaned_data['rooms']:
                self.add_error('rooms', u'Обязательное поле для выбранного типа недвижимости')

        if 'property_type' in cleaned_data:
            if cleaned_data['property_type'] != 'plot' and not cleaned_data.get('addr_street', ''):
                self.add_error('addr_street', u'Обязательное поле для выбранного типа недвижимости')

        return cleaned_data

class ImportFacilityForm(forms.Form):
    facility_id = forms.ChoiceField(choices=[])

    def __init__(self, *args, **kwargs):
        super(ImportFacilityForm, self).__init__(*args, **kwargs)
        self.fields['facility_id'].choices = [(id, id) for id in Facility.objects.values_list('id', flat=True)]

class BaseImportFacilitiesFormset(forms.BaseFormSet):
    def update_ad(self, ad):
        new_facilities_ids = set([form.cleaned_data['facility_id'] for form in self])
        old_facilities_ids = set(ad.facilities.values_list('id', flat=True))
        if old_facilities_ids != new_facilities_ids:
            ad.facilities.clear()
            ad.facilities.add(*Facility.objects.filter(id__in=new_facilities_ids))

ImportFacilitiesFormset = forms.formset_factory(ImportFacilityForm, formset=BaseImportFacilitiesFormset)

def create_import_facilities_formset(raw_values):
    formset_data = {
        'form-TOTAL_FORMS': len(raw_values),
        'form-INITIAL_FORMS': len(raw_values),
    }
    for index, value in enumerate(raw_values):
        formset_data['form-%d-facility_id' % index] = value
    return ImportFacilitiesFormset(formset_data)


class ImportPhotoForm(forms.Form):
    photo_url = forms.URLField(max_length=512)

class BaseImportPhotosFormset(forms.BaseFormSet):
    def update_ad(self, ad):
        new_photo_urls = [form.cleaned_data['photo_url'] for form in self]
        old_photo_urls = list(ad.photos.values_list('source_url', flat=True))
        if old_photo_urls != new_photo_urls:
            for photo in ad.photos.all():
                photo.delete()
            for order, photo_url in enumerate(new_photo_urls, start=1):
                Photo(basead=ad, source_url=photo_url, order=order).save()

ImportPhotosFormset = forms.formset_factory(ImportPhotoForm, formset=BaseImportPhotosFormset)

def create_import_photos_formset(raw_values):
    formset_data = {
        'form-TOTAL_FORMS': len(raw_values),
        'form-INITIAL_FORMS': len(raw_values),
    }
    for index, value in enumerate(raw_values):
        formset_data['form-%d-photo_url' % index] = value
    return ImportPhotosFormset(formset_data)


class ImportPaidPlacementForm(forms.Form):
    paidplacement = forms.ChoiceField(choices=PAID_PLACEMENT_CHOICES)

class BaseImportPaidPlacementFormset(forms.BaseFormSet):
    def clean_according_with_ad(self, ad):
        for form in self:
            if ad.addr_country == 'UA' and form.cleaned_data['paidplacement'] == 'intl_mesto':
                form.add_error('paidplacement', u'Платное размещение "intl_mesto" доступно только для зарубежной недвижимости')

ImportPaidPlacementFormset = forms.formset_factory(ImportPaidPlacementForm, formset=BaseImportPaidPlacementFormset)

def create_import_paidplacements_formset(raw_values):
    formset_data = {
        'form-TOTAL_FORMS': len(raw_values),
        'form-INITIAL_FORMS': len(raw_values),
    }
    for index, value in enumerate(raw_values):
        formset_data['form-%d-paidplacement' % index] = value
    return ImportPaidPlacementFormset(formset_data)
