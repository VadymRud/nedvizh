# coding: utf-8
from __future__ import unicode_literals

import datetime

from django.contrib import messages
from facebook import GraphAPI
from django.conf import settings
from django.core.urlresolvers import reverse
from django.shortcuts import redirect

from autoposting.models import FacebookAutoposting
from utils.templatetags.jinja import host_url


def facebook_callback(request):
    graph = GraphAPI()

    # Получаем Long Term Access Token
    if request.GET.get('code'):
        access_token = graph.get_access_token_from_code(
            request.GET.get('code'), host_url('autoposting-facebook-callback'), settings.FACEBOOK_APP_ID,
            settings.FACEBOOK_APP_SECRET)

    else:
        access_token = graph.get_app_access_token(settings.FACEBOOK_APP_ID, settings.FACEBOOK_APP_SECRET)

    graph.access_token = access_token['access_token']
    access_token_response = graph.extend_access_token(settings.FACEBOOK_APP_ID, settings.FACEBOOK_APP_SECRET)
    access_token = access_token_response['access_token']
    access_token_expires_at = datetime.datetime.now() + datetime.timedelta(
        seconds=int(access_token_response.get('expires', 60 * 60 * 24 * 60)))

    # Получаем список access_token для каждой из групп, что у нас есть в настройках
    graph = GraphAPI(access_token=access_token)
    group_access_tokens = {}
    after = None
    while True:
        if after:
            objects = graph.get_object('me/accounts', limit=25, after=after)

        else:
            objects = graph.get_object('me/accounts', limit=25)

        for group in objects['data']:
            if group['category'] == 'Community':
                group_access_tokens[group['id']] = group['access_token']

        if objects['paging'].get('next'):
            after = objects['paging']['cursors']['after']

        else:
            break

    facebook_autoposting = FacebookAutoposting.objects.all()
    for fb_autoposting in facebook_autoposting:
        if not group_access_tokens.get(fb_autoposting.page_id):
            messages.error(request, 'Access Token for %s not found' % fb_autoposting)
            continue

        fb_autoposting.access_token = group_access_tokens.get(fb_autoposting.page_id)
        fb_autoposting.access_token_expires_at = access_token_expires_at
        fb_autoposting.save()

    return redirect(reverse('admin:autoposting_facebookautoposting_changelist'))


def vk_callback(request):
    return redirect('/')
