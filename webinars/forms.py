# coding: utf-8
from django import forms
from ad.forms import PhoneForm
from webinars.models import WebinarReminder


class WebinarReminderForm(forms.ModelForm, PhoneForm):
    class Meta:
        model = WebinarReminder
        fields = ('email', 'name', 'phone', 'city')
