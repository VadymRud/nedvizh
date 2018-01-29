# coding=utf-8

from django.shortcuts import render, redirect
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponse
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required

from agency.models import Agency
from profile.forms import SettingsImportForm, TestImportForm
from import_.models import ImportTask
from views import check_ban

from staticpages.models import ContentBlock

import collections

def import_view(view):
    def decorated_view(request, *args, **kwargs):
        if request.user.get_realtor_admin():
            return view(request, *args, **kwargs)
        else:
            raise PermissionDenied()
    return login_required(decorated_view)

@import_view
@check_ban
def index(request):
    if request.own_agency.import_url:
        return redirect(reverse('import:log'))
    else:
        return redirect(reverse('import:howto'))

@login_required
def howto(request):
    from django.template.loader import render_to_string
    from ad.models import Facility
    import ad.choices as ad_choices

    content = ContentBlock.objects.get(name='import_howto').content
    content = content.replace('#facilities#',
        render_to_string('profile/import/howto_choices.jinja.html', {'choices': Facility.objects.order_by('id').values_list('id', 'name')})
    )

    for name in ['deal_type', 'property_type', 'building_type', 'layout', 'walls', 'windows', 'heating', 'currency']:
        content = content.replace('#%s#' % name,
            render_to_string('profile/import/howto_choices.jinja.html', {'choices': getattr(ad_choices, '%s_CHOICES' % name.upper())})
        )

    return render(request, 'profile/import/howto.jinja.html', locals())

@import_view
@check_ban
def settings(request):
    success = False
    if request.method == 'POST':
        form = SettingsImportForm(request.POST)
        if form.is_valid():
            request.own_agency.import_url=form.cleaned_data['url']
            request.own_agency.save()
            success = True
    else:
        form = SettingsImportForm(initial={'url': request.own_agency.import_url or ''})
    return render(request, 'profile/import/settings.jinja.html', locals())

@import_view
@check_ban
def test(request):
    agency = request.user.get_agency()

    try:
        importtask = ImportTask.objects.get(agency=agency, is_test=True)
    except ImportTask.DoesNotExist:
        importtask = None
        if request.method == 'POST':
            form = TestImportForm(request.POST)
            if form.is_valid():
                importtask = ImportTask(agency=agency, url=form.cleaned_data['url'], is_test=True)
                importtask.save()
                from import_.tasks import perform_importtask
                perform_importtask(importtask.id)
        else:
            form = TestImportForm()
    else:
        if importtask.status == 'completed' and 'new' in request.GET:
            importtask.delete()
            return redirect('import:test')

        counter = collections.Counter()
        ads_groupped_by_errors = collections.defaultdict(list)
        for raw_xml_id, errors in importtask.importadtasks.values_list('raw_xml_id', 'errors'):
            counter['total'] += 1
            if errors:
                counter['with_errors'] += 1
                ads_groupped_by_errors[errors].append(raw_xml_id or u'объявление без xml_id')

    return render(request, 'profile/import/test.jinja.html', locals())

@import_view
@check_ban
def test_update_status(request):
    importtask = ImportTask.objects.get(agency=request.user.get_agency(), is_test=True)
    if importtask.status != 'completed':
        if ImportTask.get_queryset_to_complete().filter(id=importtask.id).exists():
            importtask.complete()
    return JsonResponse({'status': importtask.status})

@import_view
@check_ban
def log(request):
    importtasks = ImportTask.objects.filter(is_test=False, agency=request.user.get_agency(), status='completed').order_by('-completed')[:10]
    return render(request, 'profile/import/log.jinja.html', locals())

def report(request):
    agency = Agency.objects.get(import_report_access_code=request.GET['access_code'])
    importtask = agency.importtasks.filter(status='completed').order_by('-completed').first()
    if importtask:
        return HttpResponse(importtask.make_report(), content_type='text/xml')
    else:
        return HttpResponse()
