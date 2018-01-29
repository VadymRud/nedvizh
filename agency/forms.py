# coding: utf-8
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.core.cache import cache

from profile.forms import AdminImageWidget, CityTypeaheadField, ImageFileInput
from agency.models import Agency, Note, Realtor, LEAD_TYPES
from custom_user.models import User
from ad.forms import PhoneForm
from ad.models import DealType



class AsnuNumberBoundField(forms.boundfield.BoundField):
    def asnunumber_is_confirmed(self):
        value = self.value()
        return bool(value and value.replace('-', '') in cache.get('valid_asnu_numbers', []))


class AsnuNumberField(forms.CharField):
    def __init__(self, *args, **kwargs):
        super(AsnuNumberField, self).__init__(*args, **kwargs)

    def get_bound_field(self, form, field_name):
        return AsnuNumberBoundField(form, self, field_name)


class AgencyLogoFileInput(ImageFileInput):
    button_text = u'Измените лого'
    help_text = u'На логотипе запрещается размещать номер телефона или любую другую контактную информацию'


class AgencyForm(forms.ModelForm):
    logo = forms.ImageField(label=_(u'Логотип'), widget=AgencyLogoFileInput(), required=False)
    city = CityTypeaheadField(label=_(u'Город'), required=False)
    deal_types = forms.ModelMultipleChoiceField(label=_(u'Типы сделки'), required=False, widget=forms.CheckboxSelectMultiple(), queryset=DealType.objects.all())
    asnu_number = AsnuNumberField(label=_(u'Номер свидетельства АСНУ'), required=False)

    class Meta:
        model = Agency
        fields = (
            'name', 'logo', 'city', 'address', 'asnu_number', 'show_in_agencies', 'deal_types', 'description', 'site',
            'working_hours'
        )

    def clean_asnu_number(self):
        if 'asnu_number' in self.cleaned_data:
            cleaned_asnu_number = self.cleaned_data['asnu_number'].replace('-', '')
            valid_asnu_numbers = cache.get('valid_asnu_numbers', [])
            other_agency_numbers = [
                number.replace('-', '') for number in Agency.objects.exclude(id=self.instance.id).filter(asnu_number__gt='').values_list('asnu_number', flat=True)
            ]
            if (cleaned_asnu_number in valid_asnu_numbers) and (cleaned_asnu_number in other_agency_numbers):
                raise forms.ValidationError(_(u'Такой номер свидетельства уже зарегистрирован на сайте, проверьте введенные данные'))
            return self.cleaned_data['asnu_number']


class RieltorFilterForm(forms.Form):
    search = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder':_(u'Искать по имени, фамилии...')}))


PERIOD_CHOICES = (
    (7, _(u'Неделя')),
    (30, _(u'Месяц')),
    (90, _(u'3 месяца')),
    (0, _(u'За всё время')),
)
STAT_TYPE_CHOICES = (
    ('ads', _(u'Кол-во объектов')), # COUNT at ad.created (through ad.user)
    ('ad_views', _(u'Просмотров')), # views at viewscount@type=0.date (trough viewscount.basead.ad.user)
    ('contact_views', _(u'Открытых контактов')), # views at viewscount@type=1.date (trough viewscount.basead.ad.user)
    ('inbox', _(u'Входящих сообщений')), # COUNT at message.time (trough message.to_user)
    ('login', _(u'Логинов в систему')), # message.entrances at message.time (trough Stat.user)
)

class StatFilterForm(forms.Form):
    period = forms.ChoiceField(label=_(u'Временной отрезок'), widget=forms.RadioSelect, choices=PERIOD_CHOICES, required=False)
    stat_type = forms.ChoiceField(label=_(u'Тип статистики'), widget=forms.RadioSelect, choices=STAT_TYPE_CHOICES, required=False)


TRANSACTION_TYPE_CHOICES = (
    ('', _(u'Все операции')),
    ('in', _(u'Пополнения')),
    ('out', _(u'Расходы')),
)
class TransactionFilterForm(forms.Form):
    period = forms.ChoiceField(label=_(u'Временной отрезок'), choices=PERIOD_CHOICES)
    type = forms.ChoiceField(label=_(u'Тип операции'), choices=TRANSACTION_TYPE_CHOICES, required=False)

class RieltorStatFilterForm(forms.Form):
    period = forms.ChoiceField(label=_(u'Временной отрезок'), choices=PERIOD_CHOICES,
                               widget=forms.Select(attrs={'class':'form-control'}))

class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ('text',)
        widgets = {
            'text': forms.Textarea(attrs={'cols': 80, 'rows': 1, 'class':'form-control',
                                          'placeholder':u'Место для заметок (заметки видны только вам)'}),
        }

class AddRealtorForm(forms.ModelForm, PhoneForm):
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'city', 'phone', 'image')

    email = forms.EmailField(label=_(u'E-mail'), max_length=254, required=True)
    image = forms.ImageField(label=_(u'Фото'), widget=AdminImageWidget, required=False)

    def __init__(self, *args, **kwargs):
        self.agency = kwargs.pop('agency')
        super(AddRealtorForm, self).__init__(*args, **kwargs)

    def set_required(self):
        for f in self.fields:
            if f != 'image':
                self.fields[f].required = True

    def clean_email(self):
        email = self.cleaned_data['email']
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            pass
        else:
            if Realtor.objects.filter(agency=self.agency, user=user).exists():
                raise forms.ValidationError(_(u'Вы уже добавили риелтора %s' % email))
        return email

    def clean(self):
        super(AddRealtorForm, self).clean()

        if 'email' in self.cleaned_data:
            try:
                User.objects.get(email__iexact=self.cleaned_data['email'])
            except User.DoesNotExist:
                for f in self.fields:
                    if f not in ('email', 'image') and f not in self.errors:
                        if not self.cleaned_data.get(f, ''):
                            self.add_error(f, _(u'This field is required.'))

