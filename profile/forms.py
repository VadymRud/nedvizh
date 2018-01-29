# -*- coding: utf-8 -*-
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe
from django.core.urlresolvers import reverse_lazy
from django.conf import settings

from ad.forms import PhoneForm
from ad.phones import pprint_phone
from ad.models import Region
from profile.models import Message, MESSAGE_SUBJECT_CHOICES
from custom_user.models import User, LANGUAGE_CHOICES
from agency.models import city_region_filters


class AdminImageWidget(forms.FileInput):
    """
    A ImageField Widget for admin that shows a thumbnail.
    """

    def __init__(self, attrs={}):
        super(AdminImageWidget, self).__init__(attrs)

    def render(self, name, value, attrs=None):
        output = []
        if value and hasattr(value, "url"):
            output.append((u'<a target="_blank" href="%s">посмотреть</a><br/>Изменить: ' % value.url ))
            
        output.append(super(AdminImageWidget, self).render(name, value, attrs))
        return mark_safe(u''.join(output))


class CityTypeaheadWidget(forms.MultiWidget):
    def __init__(self, *args, **kwargs):
        widgets = (
            forms.HiddenInput(attrs={'class': 'city-typeahead-widget-0'}),
            forms.TextInput(attrs={'class': 'city-typeahead-widget-1', 'autocomplete': 'off', 'data-url': reverse_lazy('agency_admin:city_typeahead')})
        )
        super(CityTypeaheadWidget, self).__init__(widgets, **kwargs)

    def decompress(self, value):
        if value:
            return [value, Region.objects.get(id=value).name]
        else:
            return [None, None]


class CityTypeaheadField(forms.MultiValueField):
    def __init__(self, **kwargs):
        fields = (
            # в queryset не должно выполняться запросов в базу типа Region.objects.get(id=1)...,
            # иначе при добавлении новых полей к Region и генерации миграций в момент импорта этого модуля возникнет ошибка "column <new_field> does not exist"
            forms.ModelChoiceField(required=False, queryset=Region.objects.filter(**city_region_filters).order_by('name')),
            forms.CharField(required=False),
        )
        super(CityTypeaheadField, self).__init__(fields, widget=CityTypeaheadWidget, **kwargs)

    def compress(self, data_list):
        if data_list:
            return data_list[0]


class RegistrationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('email',)

    email = forms.EmailField(max_length=75, label=u'Email')
    password1 = forms.CharField(widget=forms.PasswordInput(render_value=False), label=_(u'Пароль'))
    password2 = forms.CharField(widget=forms.PasswordInput(render_value=False), label=_(u'Пароль (еще раз)'))

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_(u'Пользователь с адресом электронной почты %s уже зарегистрирован' % email))
        return email

    def clean(self):
        super(RegistrationForm, self).clean()
        if 'password1' in self.cleaned_data and 'password2' in self.cleaned_data:
            if self.cleaned_data['password1'] != self.cleaned_data['password2']:
                message = _(u'Пароли не совпадают')
                self.add_error('password1', message)
                self.add_error('password2', message)
        return self.cleaned_data

    def save(self, commit=True):
        user = super(RegistrationForm, self).save(commit=False)
        user.username = User.make_unique_username(self.cleaned_data['email'])
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class ImageFileInput(forms.ClearableFileInput):
    class Media:
        css = {
           'all': ('css/widgets.css',)
        }

    def render(self, name, value, attrs=None):
        from django.utils.html import conditional_escape
        from django.contrib.staticfiles.templatetags.staticfiles import static
        from utils.thumbnail import get_lazy_thumbnail

        template = (
            u'<div class="media image-upload-widget"><div class="media-left media-middle">%(img)s</div>'
            u' <div class="media-body rel">%(input)s <div class="fake_button"><i></i>%(button_text)s</div> <div class="blocker_button"></div>'
            u' <div class="helptext">%(help_text)s</div>'
            u' <div class="clear checkbox">%(clear_template)s</div>'
            u'</div></div>'
        )
        substitutions = {
            'initial_text': self.initial_text,
            'input_text': self.input_text,
            'clear_template': '',
            'clear_checkbox_label': self.clear_checkbox_label,
            'img':'',
            'button_text': self.button_text,
            'help_text': self.help_text
        }
        template_with_clear = '<label for="%(clear_checkbox_id)s">%(clear)s %(clear_checkbox_label)s</label>'

        substitutions['input'] = super(forms.ClearableFileInput, self).render(name, value, attrs)

        if self.is_initial(value):
            substitutions['img'] = '<a href="%s" target="_blank"><img src="%s" /></a>' % (
                value.url,
                get_lazy_thumbnail(value, '200x200')
            )
            if not self.is_required:
                checkbox_name = self.clear_checkbox_name(name)
                checkbox_id = self.clear_checkbox_id(checkbox_name)
                substitutions['clear_checkbox_name'] = conditional_escape(checkbox_name)
                substitutions['clear_checkbox_id'] = conditional_escape(checkbox_id)
                substitutions['clear'] = forms.widgets.CheckboxInput().render(checkbox_name, False, attrs={'id': checkbox_id})
                substitutions['clear_template'] = template_with_clear % substitutions
        else:
            substitutions['img'] = '<img src="%s" />' % static('img/no-photo2.png')


        return mark_safe(template % substitutions)


class UserImageFileInput(ImageFileInput):
    button_text = _(u'Измените фото')
    help_text = _(u'Ваша фотография — первое, что видят другие люди, поэтому выберите лучшую.')


class ProfileForm(forms.ModelForm):
    is_realtor = forms.BooleanField(label=_(u'Я риелтор'), required=False,
        help_text=_(u'Выберите этот пункт, если вы хотите размещать от 3 объявлений и выше. Вам станут доступны различные инструменты для увеличения продаж.'))
    is_developer = forms.BooleanField(label=_(u'Я застройщик'), required=False,
        help_text=_(u'Выберите этот пункт, если вы хотите добавить Жилой Комплекс/Новострой'))
    image = forms.ImageField(label=_(u'Ваша фотография'), widget=UserImageFileInput(), required=False)
    language = forms.ChoiceField(label=_(u'Язык'), choices=LANGUAGE_CHOICES[:2])

    class Meta:
        model = User
        fields = (
            'is_realtor', 'is_developer',
            'image', 'first_name', 'last_name', 'gender', 'language', 'show_email', 'subscribe_info', 'subscribe_news',
            'receive_sms'
        )

    def __init__(self, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)

        if not kwargs['instance'].email:
            del self.fields['show_email']

        if settings.MESTO_SITE == 'nesto':
            del self.fields['language']

        def disable_field(field_name):
            field = self.fields[field_name]
            field.widget.attrs['disabled'] = 'disabled'
            field.help_text = u'%s<br/>%s' % (field.help_text, _(u'Для смены текущего профиля обратитесь к личному менеджеру'))

        initial = kwargs['initial']

        if initial['is_realtor']:
            disable_field('is_realtor')
            if not initial['is_developer']:
                del self.fields['is_developer']

        if initial['is_developer']:
            disable_field('is_developer')
            if not initial['is_realtor']:
                del self.fields['is_realtor']

    def clean(self):
        if self.cleaned_data.get('is_realtor') and self.cleaned_data.get('is_developer'):
            message = _(u'Можно выбрать только один из двух вариантов')
            self.add_error('is_realtor', message)
            self.add_error('is_developer', message)


class EmailForm(forms.Form):
    email = forms.EmailField(label=_(u'Новый E-mail'))

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_(u'Пользователь с таким e-mail адресом уже зарегистрирован'))
        return email


MESSAGE_SUBJECT_CHOICES_EMPTY = (('', _(u'Выберите тему из списка')),) + MESSAGE_SUBJECT_CHOICES
class MessageAboutAdForm(forms.ModelForm):
    text = forms.CharField(label=_(u'Сообщение'), required=True, widget=forms.Textarea(attrs={'rows':5}))
    # subject = forms.ChoiceField(label=_(u'Тема'), choices=MESSAGE_SUBJECT_CHOICES_EMPTY, required=False)

    class Meta:
        model = Message
        fields = ['text']

    def __init__(self, *args, **kwargs):
        super(MessageAboutAdForm, self).__init__(*args, **kwargs)

        instance = kwargs['instance']
        if instance.subject:
            placeholders = {
                "details": _(u'Если вам недостаточно предоставленной в объявлении информации и вы хотите знать о понравившемся объекте недвижимости больше,- задайте автору объявления дополнительные вопросы, которые помогут вам уточнить необходимые детали и сложить целостный образ понравившегося объекта.'),
                "counteroffer": _(u'У вас есть возможность предложить продавцу недвижимости свою цену. Отправьте ему предложение контроферты с аргументацией и дайте время обдумать этот вариант. Как правило, владельцы идут на встречу потенциальному клиенту и снижают стоимость.'),
            }
            self.fields['text'].widget.attrs['placeholder'] = placeholders.get(instance.subject)


class MessageReplyForm(forms.ModelForm):
    text = forms.CharField(label=_(u'Сообщение'), required=True, widget=forms.Textarea(attrs={'rows':3}))

    class Meta:
        model = Message
        fields = ['text',]


class UnsubscribeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['subscribe_info', 'subscribe_news']


class SettingsImportForm(forms.Form):
    url = forms.URLField(max_length=100, label=_(u'Ссылка на файл для импорта'), required=False)


class TestImportForm(forms.Form):
    url = forms.URLField(max_length=100, label=_(u'Ссылка на файл для проверки'), required=True)

