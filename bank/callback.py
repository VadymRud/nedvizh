# coding=utf-8
from django import forms
from django.utils.translation import ugettext as _
from django.http import HttpResponse, Http404
from django.utils.html import strip_tags
from django.core.mail import EmailMessage
from django.conf import settings
import json

class CallbackForm(forms.Form):
    fio = forms.CharField(label=_(u'Ваше ФИО'), required=True, widget=forms.TextInput(attrs={'placeholder': u'Напишите свое имя'}))
    phone = forms.CharField(label=_(u'Номер телефона'), required=True, widget=forms.TextInput(attrs={'placeholder': u'В формате +38(067)1111111'}))
    property_id = forms.CharField(label=_(u'Номер обьявления'), required=False, widget=forms.TextInput(attrs={'placeholder': u'Пример #1234567'}))
    cb_type = forms.CharField(label=_(u'Тип звонка'), required=True, widget=forms.HiddenInput)

def callback(request):
    if request.method == 'POST':
        callback_form_original = CallbackForm()
        callback_form = CallbackForm(request.POST)
        cleaned_data = callback_form.data
        for field in callback_form_original.fields:
            if callback_form_original.fields[field].required and field in cleaned_data and cleaned_data[field] == callback_form_original.fields[field].initial:
                callback_form.errors[field] = [_(u"Обязательное поле.")]
        
        if callback_form.is_valid() and len(callback_form.errors) == 0:
            email = 'bank@mesto.ua'
            content = ''
            for field in callback_form_original.fields:
                if field in cleaned_data and cleaned_data[field] != "" and cleaned_data[field] != callback_form_original.fields[field].initial and field != 'cb_type':
                    content += '<b>%s</b>: %s<br />' % (callback_form_original.fields[field].label, strip_tags(cleaned_data[field]))
            
            email = EmailMessage(_(u"Запрос на перезвон!"), content, settings.DEFAULT_FROM_EMAIL, [email])
            email.content_subtype = "html"
            email.send()
            
            return HttpResponse(json.dumps({'response': _(u"Заявка отправлена! В ближайшее время вам перезвонит менеджер Mesto.Ua"), 'result': 'success'}))
        
        response = {}
        for k in callback_form.errors:
            response[k] = callback_form.errors[k][0]
        return HttpResponse(json.dumps({'response': response, 'result': 'error'}))
    else:
        raise Http404
    
