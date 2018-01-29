# coding: utf-8

from django.shortcuts import render
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.conf import settings


def offer_mobile_app(request, decline=False):
    if decline:
        response = HttpResponseRedirect(request.GET.get('next', '/'))
        response.set_cookie('no-mobile-app', 1, 60*60*24*30, domain=settings.SESSION_COOKIE_DOMAIN)
        return response
    else:
        next = request.META.get('HTTP_REFERER')
        if not next or settings.MESTO_PARENT_HOST not in next:
            next = '/'
        return render(request, 'offer_mobile_app.jinja.html', locals())

