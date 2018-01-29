# coding: utf-8
from django.shortcuts import render

def view_render_email(request):
    return render(request, 'mail/mailing/mail_saint_mykholay.jinja.html')