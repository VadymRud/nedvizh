 # coding: utf-8
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.utils.dateparse import parse_duration

from ad.forms import PhoneForm
from models import CallRequest, LeadGeneration

import datetime


class CallRequestForm(forms.ModelForm, PhoneForm):
    destination = forms.CharField(label=_(u'Получатель заявки'), widget=forms.widgets.HiddenInput, required=False)
    name = forms.CharField(label=_(u'Представьтесь, пожалуйста'))

    class Meta:
        model = CallRequest
        fields = ('name', 'email', 'phone')

    def __init__(self, *args, **kwargs):
        super(CallRequestForm, self).__init__(*args, **kwargs)
        self.fields['phone'].required = True


class SplitHoursMinsWidget(forms.widgets.MultiWidget):
    def __init__(self, attrs={}):
        hours = [(i, '{0:02d}'.format(i) )for i in range(0, 24)]
        minutes = [(i, '{0:02d}'.format(i) )for i in range(0, 60, 15)]

        _widgets = (
            forms.widgets.Select(attrs={'size':1, 'class':'form-control'}, choices=hours),
            forms.widgets.Select(attrs={'size':1, 'class':'form-control'}, choices=minutes),
        )
        super(SplitHoursMinsWidget, self).__init__(_widgets, attrs)

    def decompress(self, value):
        if value:
            return map(int, str(value).split(':'))
        return [None, None]

    def format_output(self, rendered_widgets):
        return (rendered_widgets[0] + "" + rendered_widgets[1])

    def value_from_datadict(self, data, files, name):
        hours_mins_secs = [
            widget.value_from_datadict(data, files, name + '_%s' % i) or 0
            for i, widget in enumerate(self.widgets)]
        try:
            time_delta = datetime.timedelta(hours=float(hours_mins_secs[0]), minutes=float(hours_mins_secs[1]))
        except ValueError:
            return None
        else:
            return time_delta


class DayWorkTimeWidget(forms.widgets.MultiWidget):
    def __init__(self, attrs=None):
        _widgets = (
            SplitHoursMinsWidget(),
            SplitHoursMinsWidget(),
        )
        super(DayWorkTimeWidget, self).__init__(_widgets, attrs)

    def format_output(self, rendered_widgets):
        return u'<div class="workday" data-toggle="buttons"><label class="btn btn-default">%s<input type="checkbox"/></label> ' \
               u'%s %s &nbsp; %s %s</div>' % (self.attrs['label'], _(u'c'), rendered_widgets[0], _(u'до'), rendered_widgets[1])


class WeekWorkTimeWidget(forms.widgets.MultiWidget):
    def __init__(self, attrs=None):
        _widgets = (
            DayWorkTimeWidget(attrs={'label':_(u'Пн')}),
            DayWorkTimeWidget(attrs={'label':_(u'Вт')}),
            DayWorkTimeWidget(attrs={'label':_(u'Ср')}),
            DayWorkTimeWidget(attrs={'label':_(u'Чт')}),
            DayWorkTimeWidget(attrs={'label':_(u'Пт')}),
            DayWorkTimeWidget(attrs={'label':_(u'Сб')}),
            DayWorkTimeWidget(attrs={'label':_(u'Вс')}),
        )
        super(WeekWorkTimeWidget, self).__init__(_widgets, attrs)


class WorkTimeField(forms.MultiValueField):
    widget = WeekWorkTimeWidget

    def clean(self, value):
        return value

    def prepare_value(self, value):
        worktime = value if value else [[datetime.timedelta(), datetime.timedelta()]] * 7
        return worktime

WEEKDAYS_CHOICES = (
    (0, u'Пн'),
    (1, u'Вт'),
    (2, u'Ср'),
    (3, u'Чт'),
    (4, u'Пт'),
    (5, u'Сб'),
    (6, u'Вс'),
)


class LeadGenerationForm(forms.ModelForm):
    worktime = WorkTimeField(label=u'', required=False)

    class Meta:
        model = LeadGeneration
        fields = ('worktime', 'dedicated_numbers') # 'weekdays_str'x
        widgets = {
            'dedicated_numbers': forms.widgets.HiddenInput(),
        }

    def clean_weekdays(self):
        return [int(i) for i in self.cleaned_data['weekdays']]