from django.shortcuts import render
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django import forms
from django.core.cache import cache, caches
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required

from django_redis.cache import RedisCache

class SearchForm(forms.Form):
    lookup = forms.RegexField(regex='[a-zA-Z0-9_]+')

def admin_cache_decorator(view):
    def function(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        elif not isinstance(caches['default'], RedisCache):
            raise Exception('Admin cache tool is available only for RedisCache (you are using %s)' % type(caches['default']))
        return view(request, *args, **kwargs)
    return login_required(function)

@csrf_exempt
@admin_cache_decorator
def cache_view(request):
    if request.method == 'POST':
        for key in request.POST.keys():
            if key.startswith('key_'):
                cache.delete(key[4:])
    
    if 'lookup' in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            keys = sorted(cache.keys('*%s*' % form.cleaned_data['lookup']))
    else:
        form = SearchForm()

    return render(request, 'admin/cache.html', locals())

@csrf_exempt
@admin_cache_decorator
def cache_key(request, key):
    value = cache.get(key, 'not_in_cache')
    try:
        data = {'value': value}
    except:
        try:
            data = {'value': unicode(repr(value), errors='replace')}
        except:
            data = {'value': u'cannot convert to JSON: %s' % type(value)}
    return JsonResponse(data)

@staff_member_required
def export_status(request):
    feeds_data = cache.get('export_status', {})
    for feed, data in feeds_data.iteritems():
        if 'copy' in data:
            for k, v in feeds_data[data['copy']].iteritems():
                if k not in data:
                    data[k] = v
    return render(request, 'admin/export_status.html', locals())

