# coding: utf-8

import os
import datetime
import collections
from ajaxuploader.views import AjaxFileUploader, Http404, json
from django.contrib.auth.models import Permission
from django.core.files import File
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import EmailMessage
from django.core.urlresolvers import reverse
from django.forms import modelformset_factory, formset_factory
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseRedirect
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.db.models import Q

from ad.models import Phone, Ad, Photo
from custom_user.models import User
from newhome.forms import (ProgressForm, NewhomeForm, LayoutForm, RoomForm, BuildingEditForm, BuildingQueueForm,
                           QueueSectionForm, QueueSectionFormSet, NewhomeFilterForm, DeveloperForm)
from newhome.models import (Newhome, Progress, Layout, Floor, Flat, ProgressPhoto, NewhomePhoto, Room, Building,
                            BuildingSection, BuildingQueue, LayoutFlat, ViewsCount, LayoutNameOption)
from ppc.models import get_lead_price, LeadGeneration
from utils import ajax_upload
from newhome.decorators import accept_newhome_user
from utils.paginator import HandyPaginator


@login_required
def developer_form(request):
    title = _(u'Редактирование застройщика')
    if not request.is_developer_cabinet_enabled:
        raise Http404

    developer = request.user.developer

    if request.method == 'POST':
        form = DeveloperForm(request.POST, request.FILES, instance=developer)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('profile_settings_developer'))

    else:
        form = DeveloperForm(
            instance=developer, initial={'city_typeahead': getattr(developer.city, 'name', '')}
        )

    return render(request, 'newhome/cabinet/developer_form.jinja.html', locals())


@login_required
def my_buildings(request):
    """
    Профиль застройщика: Мои новостройки
    """

    if request.user.has_perm('newhome.newhome_admin'):
        newhomes = Newhome.objects.all().order_by('-modified', '-created')

    else:
        newhomes = Newhome.objects.filter(user=request.user).exclude(status=211).order_by('-modified', '-created')

    newhomes = newhomes.prefetch_related('priority_phones', 'newhome_photos').select_related('region')

    # Выставляем изменнеый почтовый ящик по работе с заявками на конкретную новостройку
    if request.method == 'POST':
        action = request.POST.get('action', '')
        accept_actions = ['email', 'remove', 'activate', 'deactivate']

        if action in accept_actions:
            for newhome in newhomes.filter(pk__in=request.POST.getlist('newhome[]')):
                if action == 'email':
                    # Меняем email / телефон ответственного лица
                    newhome.priority_email = request.POST.get(u'email-{:d}'.format(newhome.pk))
                    newhome.save()

                    phones = request.POST.getlist(u'phone-{:d}[]'.format(newhome.pk))
                    if phones:
                        newhome.priority_phones.clear()
                        for phone in phones:
                            if phone.strip('+'):
                                phone, created = Phone.objects.get_or_create(number=phone.strip('+'))
                                newhome.priority_phones.add(phone)

                    messages.success(request, _(u'Контактные данные по объекту обновлены'))

                elif action == 'activate':
                    # Активируем новостройку
                    if newhome.moderation_status and not newhome.fields_for_moderation:
                        messages.error(request, _(u'Пожалуйста, исправьте замечания перед активации объекта'))

                    elif newhome.user.get_balance() > get_lead_price('callrequest', 'newhomes', 'high'):
                        newhome.status = 1
                        newhome.is_published = True
                        newhome.save()  # Включение лидогенерации проходит в сигналах

                        messages.success(request, _(u'Объект успешно активирован'))

                    else:
                        messages.error(request, _(u'Не хватает средств для активации объекта'))

                elif action == 'deactivate':
                    # Деактивируем новостройку
                    newhome.status = 210
                    newhome.is_published = False
                    newhome.save()
                    messages.success(request, _(u'Объект успешно деактивирован'))

                elif action == 'remove':
                    # Удаляем новостройку
                    newhome.status = 211
                    newhome.is_published = False
                    newhome.save()
                    messages.success(request, _(u'Объект успешно удален'))

        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('profile_newhome_my_buildings')))

    # Фильтруем объявления
    filter_form = NewhomeFilterForm(request.GET)

    if not filter_form.is_valid():
        return HttpResponseRedirect(reverse('profile_newhome_my_buildings'))

    # Статус объявления
    status = filter_form.cleaned_data['status']

    if status == 'active':
        ads_list = Newhome.objects.filter(
            pk__in=newhomes.values_list('pk', flat=True), status=1
        ).values_list('pk', flat=True)
        newhomes = newhomes.filter(pk__in=ads_list)

    elif status == 'inactive':
        ads_list = Newhome.objects.filter(
            pk__in=newhomes.values_list('pk', flat=True), status=210
        ).values_list('pk', flat=True)
        newhomes = newhomes.filter(pk__in=ads_list)

    elif status == 'removed':
        ads_list = Newhome.objects.filter(
            pk__in=newhomes.values_list('pk', flat=True), status=211
        ).values_list('pk', flat=True)
        newhomes = newhomes.filter(pk__in=ads_list)

    # Поисковая строка
    search = filter_form.cleaned_data['search'].strip()
    if search:
        newhomes_filter = Q()

        # Фильтр по названию
        newhomes_filter |= Q(name__icontains=search)

        # Фильтр по владельцу (email)
        newhomes_filter |= Q(user__email__icontains=search)

        # Фильтр по ответственному за объект
        newhomes_filter |= Q(priority_email__icontains=search)

        newhomes = newhomes.filter(newhomes_filter)

    # Включаем пагинацию
    paginator = HandyPaginator(newhomes, 10, request=request, per_page_variants=[5, 10, 20, 50])

    return render(request, 'newhome/cabinet/my-buildings.jinja.html', locals())


@login_required
@accept_newhome_user
def queue(request, newhome_id):
    """
    Профиль застройщика: Очереди строительства
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)

    return render(request, 'newhome/cabinet/queue.jinja.html', locals())


@login_required
@accept_newhome_user
def queue_add(request, newhome_id):
    """
    Профиль застройщика: Добавление очереди строительства

    todo: При переходе на 1.9 переделать на формсеты
    https://docs.djangoproject.com/en/1.9/topics/forms/formsets/#passing-custom-parameters-to-formset-forms
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)

    formset = formset_factory(QueueSectionForm, QueueSectionFormSet, extra=20)
    if request.method == 'POST':
        form = BuildingQueueForm(request.POST)
        if form.is_valid():
            building_queue = form.save(commit=False)
            building_queue.newhome = newhome
            building_queue.save()

            formset = formset(request.POST, newhome_id=newhome_id, prefix='sections')
            for form_ in formset:
                if form_.is_valid():
                    if form_.cleaned_data.get('section'):
                        building_queue.sections.add(form_.cleaned_data['section'])

            newhome.modified = datetime.datetime.now()
            newhome.save()

            return HttpResponseRedirect(reverse('profile_newhome_queue', args=[newhome_id]))

    else:
        form = BuildingQueueForm()
        formset = formset(newhome_id=newhome_id, prefix='sections')

    return render(request, 'newhome/cabinet/queue-add.jinja.html', locals())


@login_required
@accept_newhome_user
def queue_edit(request, newhome_id, queue_id):
    """
    Профиль застройщика: Редактирование очереди строительства

    todo: При переходе на 1.9 переделать на формсеты
    https://docs.djangoproject.com/en/1.9/topics/forms/formsets/#passing-custom-parameters-to-formset-forms
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)
    queue = get_object_or_404(BuildingQueue, newhome__id=newhome_id, id=queue_id)

    formset = formset_factory(QueueSectionForm, QueueSectionFormSet, extra=20)
    if request.method == 'POST':
        form = BuildingQueueForm(request.POST, instance=queue)
        if form.is_valid():
            building_queue = form.save(commit=False)
            building_queue.newhome = newhome
            building_queue.save()

            building_queue.sections.clear()

            formset = formset(request.POST, newhome_id=newhome_id, prefix='sections')
            for form_ in formset:
                if form_.is_valid():
                    if form_.cleaned_data.get('section'):
                        building_queue.sections.add(form_.cleaned_data['section'])

            # Если не выбрано ни одной секции - удаляем запись об очереди
            if not building_queue.sections.count():
                BuildingQueue.objects.filter(id=building_queue.id).delete()

            newhome.modified = datetime.datetime.now()
            newhome.save()

            return HttpResponseRedirect(reverse('profile_newhome_queue', args=[newhome_id]))

    else:
        form = BuildingQueueForm(instance=queue)

        initial = [{'section': section.id} for section in queue.sections.all().only('id')]
        formset = formset(initial=initial, newhome_id=newhome_id, prefix='sections')

    return render(request, 'newhome/cabinet/queue-add.jinja.html', locals())


@login_required
@accept_newhome_user
def sections(request, newhome_id):
    """
    Профиль застройщика: Дома и секции
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)

    return render(request, 'newhome/cabinet/sections.jinja.html', locals())


@login_required
@accept_newhome_user
def sections_building_add(request, newhome_id):
    """
    Профиль застройщика: Дома и секции, добавление дома с секцией

    todo: Добавить перевод
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)

    building = newhome.buildings.last()

    # todo: Переделать на нормальный подсчет нумирации домов. Ждем запроса от менеджеров по этому поводу
    building_number = u'1'
    if building:
        building_name = building.name[4:]
        try:
            building_number = u'{}'.format(int(building_name) + 1)

        except:
            building_number = u'1'

    name = u'Дом {}'.format(building_number.rjust(2, u'0'))
    building = Building(newhome=newhome, name=name)
    building.save()

    BuildingSection.objects.create(building=building)

    return HttpResponseRedirect(reverse('profile_newhome_sections', args=[newhome_id]))


@login_required
@accept_newhome_user
def sections_building_remove(request, newhome_id, building_id):
    """
    Профиль застройщика: Дома и секции, удаление дома с секцией
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)
    BuildingQueue.objects.filter(sections__building__id=building_id).delete()
    Building.objects.filter(newhome=newhome.id, id=building_id).delete()
    for layout in Layout.objects.filter(section_id=building_id):
        layout.delete()

    for floor in Floor.objects.filter(section_id=building_id):
        floor.delete()

    return HttpResponseRedirect(
        request.META.get('HTTP_REFERER', reverse('profile_newhome_sections', args=[newhome_id]))
    )


@login_required
@accept_newhome_user
def sections_building_edit(request, newhome_id, building_id):
    """
    Профиль застройщика: Дома и секции, редактирование дома с секцией
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)
    edit_building = get_object_or_404(Building, newhome=newhome_id, id=building_id)

    if request.method == 'POST':
        form = BuildingEditForm(request.POST)
        if form.is_valid():
            edit_building.name = form.cleaned_data['name']
            edit_building.save()

            form_positions = map(int, form.cleaned_data['positions'].split(','))
            if not form_positions:
                edit_building.sections.delete()
                edit_building.delete()

            else:
                # Удаляем все секции которые не присутствуют во входящих данных
                edit_building.sections.exclude(position__in=form_positions).delete()

                # Добавляем новые секции
                new_position = list(
                    set(form_positions) - set(edit_building.sections.all().values_list('position', flat=True)))
                for position in new_position:
                    BuildingSection.objects.create(building=edit_building, position=position)

            newhome.modified = datetime.datetime.now()
            newhome.save()

            return HttpResponseRedirect(reverse('profile_newhome_sections', args=[newhome_id]))

    form = BuildingEditForm(initial={
        'name': edit_building.name,
        'positions': ','.join(map(str, edit_building.sections.values_list('position', flat=True)))
    })

    return render(request, 'newhome/cabinet/sections.jinja.html', locals())


@login_required
@accept_newhome_user
def workflow(request, newhome_id):
    """
    Профиль застройщика: Ход строительства
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)
    form = ProgressForm()

    return render(request, 'newhome/cabinet/workflow.jinja.html', locals())


@login_required
@accept_newhome_user
def workflow_progress_remove(request, newhome_id, progress_id):
    """
    Профиль застройщика: Удаление этапа строительства

    todo: unlink изображения
    """

    Progress.objects.filter(newhome__id=newhome_id, newhome__user=request.user, id=progress_id).delete()

    return HttpResponseRedirect(reverse('profile_newhome_workflow', args=[newhome_id]))


@login_required
@accept_newhome_user
def workflow_progress_change(request, newhome_id, progress_id=None):
    """
    Профиль застройщика: Добавление фотографий
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)
    if progress_id is not None:
        progress = get_object_or_404(Progress, newhome=newhome, id=progress_id)

    else:
        progress = Progress.objects.none()

    if request.method == 'POST':
        form = ProgressForm(request.POST)
        if form.is_valid():
            if progress_id is None:
                progress = Progress()
                progress.newhome = newhome
                progress.date = form.cleaned_data['date']
                progress.save()

            # Работа с изображениями на этапе строительства
            workflow_images = []
            for filename in request.POST.getlist('ajax_add_images'):
                path = os.path.join(settings.AJAX_UPLOAD_DIR, filename.split('/')[-1])
                if default_storage.exists(path):
                    content = default_storage.open(path).read()
                    workflow_images.append([filename, ContentFile(content)])

            for image in workflow_images:
                img = ProgressPhoto(progress=progress)
                img.image.save(image[0], image[1])

            if request.POST.getlist('delete_images'):
                ProgressPhoto.objects.filter(progress=progress, pk__in=request.POST.getlist('delete_images')).delete()

            newhome.modified = datetime.datetime.now()
            newhome.save()

            return HttpResponseRedirect(reverse('profile_newhome_workflow', args=[newhome_id]))

    else:
        if progress_id is None:
            form = ProgressForm()

        else:
            form = ProgressForm(initial={'date': progress.date.strftime('%d-%m-%Y')})

    return render(request, 'newhome/cabinet/workflow-add.jinja.html', locals())

object_uploader = login_required(AjaxFileUploader(
    backend=ajax_upload.NewhomeStorageBackend, UPLOAD_DIR=settings.AJAX_UPLOAD_DIR
))


@login_required
@accept_newhome_user
def object_change(request, newhome_id=None):
    """
    Профиль застройщика: добавление/редактирование объекта

    todo: упростить работу с формой или разделить на два разных метода
    todo: создание Ad + присвоение региона
    """

    if newhome_id is None:
        del newhome_id

        # Добавление объекта
        if request.method == 'POST':
            form = NewhomeForm(request.POST)
            if form.is_valid():
                newhome = form.save(commit=False)
                newhome.user = request.user
                newhome.updated = datetime.datetime.now()
                newhome.modified = datetime.datetime.now()
                newhome.save()

                # Работа с изображениями на этапе строительства
                workflow_images = []
                for filename in request.POST.getlist('ajax_add_images'):
                    path = os.path.join(settings.AJAX_UPLOAD_DIR, filename.split('/')[-1])
                    if default_storage.exists(path):
                        content = default_storage.open(path).read()
                        workflow_images.append([filename, ContentFile(content)])

                for image in workflow_images:
                    img = NewhomePhoto(newhome=newhome)
                    img.image.save(image[0], image[1])

                if request.POST.getlist('delete_images'):
                    newhome.newhome_photos.filter(pk__in=request.POST.getlist('delete_images')).delete()

                # Отправляем уведомление ответственным лицам
                perm = Permission.objects.get(codename='newhome_notification')
                emails = list(User.objects.filter(
                    Q(groups__permissions=perm) | Q(user_permissions=perm)
                ).distinct().values_list('email', flat=True))

                for email in emails:
                    message = EmailMessage(
                        u'Добавление нового объекта новостройки на Mesto.ua', u'Название: {}'.format(newhome.name),
                        settings.DEFAULT_FROM_EMAIL,
                        [email]
                    )
                    message.content_subtype = 'html'
                    message.send()

                messages.success(request, _(u'Ваш комплекс успешно добавлен'))

                return HttpResponseRedirect(reverse('profile_newhome_sections', args=[newhome.id]))

            else:
                for field_name, errors in form.errors.items():
                    messages.error(
                        request,
                        u'{}: {}'.format(form.fields[field_name].label, u', '.join([error for error in errors]))
                    )

        else:
            form = NewhomeForm()

    else:
        # Редактирование объекта
        newhome = get_object_or_404(Newhome, pk=newhome_id)

        region_subdomain_slug, region_slug = None, None
        if newhome.region:
            region_subdomain_slug, region_slug = newhome.region.static_url.split(';')

        # Информация по этажам и квартирам
        (flats_rooms_options, flats_available, flats_prices_by_floor, flats_info_exists, flats_floor_options,
         flats_area_by_rooms, flats_prices_by_rooms, currency) = newhome.get_aggregation_floors_info(request)

        # Ход Строительства
        progress, progress_next, progress_prev = newhome.get_progress(request.GET.get('progress'))

        if request.method == 'POST':
            form = NewhomeForm(request.POST, instance=newhome)
            if form.is_valid():
                newhome = form.save(commit=False)
                newhome.modified = datetime.datetime.now()
                newhome.save()

                # Работа с изображениями на этапе строительства
                workflow_images = []
                for filename in request.POST.getlist('ajax_add_images'):
                    path = os.path.join(settings.AJAX_UPLOAD_DIR, filename.split('/')[-1])
                    if default_storage.exists(path):
                        content = default_storage.open(path).read()
                        workflow_images.append([filename, ContentFile(content)])

                for image in workflow_images:
                    img = NewhomePhoto(newhome=newhome)
                    img.image.save(image[0], image[1])

                if request.POST.getlist('delete_images'):
                    newhome.newhome_photos.filter(newhome=newhome, pk__in=request.POST.getlist('delete_images')).delete()

                if request.POST.get('is_main'):
                    newhome.newhome_photos.all().update(is_main=False)
                    newhome.newhome_photos.filter(pk=request.POST.get('is_main')).update(is_main=True)

                messages.success(request, _(u'Данные о комплексе успешно изменены'))

                return HttpResponseRedirect(reverse('profile_newhome_my_buildings'))

            else:
                for field_name, errors in form.errors.items():
                    messages.error(
                        request,
                        u'{}: {}'.format(form.fields[field_name].label, u', '.join([error for error in errors]))
                    )

        else:
            form = NewhomeForm(instance=newhome)

    return render(request, 'newhome/cabinet/object.jinja.html', locals())


@login_required
@accept_newhome_user
def flat_add_ad(request, newhome_id, section_id, flat_id):
    """
    Профиль застройщика: подготовка данных для создания нового объекта объявлений
    Обязательное условие, одно объявление на одно количество квартир данного ЖК
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)
    layout = newhome.layouts.filter(section__id=section_id, id=flat_id).first()
    ad = None

    if layout.basead:
        ad = layout.basead

    else:
        similar_layouts = newhome.layouts.filter(rooms_total=layout.rooms_total, basead__isnull=False).first()
        if similar_layouts is not None:
            ad = similar_layouts.basead

            layout.basead = ad
            layout.save()

    if ad is None:
        ad = Ad.objects.create(
            deal_type='sale',
            property_type='flat',
            user=newhome.user,
            price=layout.area * newhome.price_at,
            rooms=layout.rooms_total,
            description=newhome.content,
            region=newhome.region,
            address=newhome.address,
            addr_country=newhome.addr_country,
            addr_city=newhome.addr_city,
            addr_street=newhome.addr_street,
            addr_house=newhome.addr_house,
            geo_source=newhome.geo_source,
            coords_x=newhome.coords_x,
            coords_y=newhome.coords_y
        )

        # Копируем фото
        photo_sources = list(newhome.newhome_photos.all()) + \
            list(newhome.layouts.filter(rooms_total=layout.rooms_total))

        for position, photo in enumerate(photo_sources):
            if default_storage.exists(photo.image.name):
                content = default_storage.open(photo.image.name).read()
                img = Photo(basead=ad, order=position, caption='')
                img.image.save('temporary_name', ContentFile(content))

        # Переносим телефоны
        for phone in (list(newhome.priority_phones.all()) + list(newhome.user.phones.all())):
            ad.phones_in_ad.get_or_create(phone=phone, basead=ad, order=0)

        # Сделано специально через update, дабы не вызвать выполнение сигнала на добавление фото планировки к объявлению
        Layout.objects.filter(id=layout.id).update(basead=ad)

        # Все планировки с таким же количеством комнат данного ЖК привязываем к созданному объявлению
        newhome.layouts.filter(rooms_total=layout.rooms_total).exclude(id=layout.id).update(basead=ad)

    return HttpResponseRedirect(reverse('profile_edit_property', args=[ad.pk]))


@login_required
@accept_newhome_user
def flat_remove(request, newhome_id, section_id, flat_id):
    """
    Профиль застройщика: удаление планировки
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)
    newhome.layouts.filter(section__id=section_id, id=flat_id).delete()

    return HttpResponseRedirect(reverse('profile_newhome_flats', args=[newhome_id, section_id]))


@login_required
@accept_newhome_user
def flats_copy(request, newhome_id, section_id, from_section_id):
    """
    Профиль застройщика: копирование секции со всем наполнением
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)
    section = BuildingSection.objects.get(id=section_id)

    # Копируем квартиры с наполнением
    layouts_comparison = {}
    for layout in newhome.layouts.filter(section__id=from_section_id):
        copied_layout, created = Layout.objects.get_or_create(name=layout.name, newhome=newhome, section=section,
                                                              building=section.building, rooms_total=layout.rooms_total,
                                                              area=layout.area)

        layouts_comparison[layout.id] = copied_layout

        for room in layout.rooms.all():
            Room.objects.create(layout=copied_layout, image_num=room.image_num, name=room.name, area=room.area)

        with default_storage.open(layout.image.name) as f:
            copied_layout.image.save(layout.image.name, File(f))

    # Копируем этажи с данными
    for floor in newhome.floors.filter(section__id=from_section_id):
        copied_floor, created = Floor.objects.get_or_create(
            newhome=newhome, number=floor.number, section=section, building=section.building, name=floor.name
        )

        with default_storage.open(floor.image.name) as f:
            copied_floor.image.save(floor.image.name, File(f))

        for layout in floor.layouts.all():
            copied_floor.layouts.add(layouts_comparison[layout.id])

            for layout_flat in layout.layout_flats.filter(floor=floor):
                LayoutFlat.objects.create(layout=layouts_comparison[layout.id], coordinates=layout_flat.coordinates,
                                          price=layout_flat.price, currency=layout_flat.currency, floor=copied_floor)

    return HttpResponseRedirect(reverse('profile_newhome_flats', args=[newhome_id, section_id]))


@login_required
@accept_newhome_user
def flats(request, newhome_id, section_id=None):
    """
    Профиль застройщика: список планировок ЖК
    todo: упростить до работы с одной картинкой
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)

    # Если нет секции, выбираем первую попавшуюся :)
    if section_id is None:
        section = BuildingSection.objects.none()
        section.id = section_id = 0

    else:
        section = get_object_or_404(BuildingSection, pk=section_id)

    layout_formset = modelformset_factory(Room, form=RoomForm, extra=20)
    if request.method == 'POST':
        # Работа с изображениями квартир, выбираем первое изображение
        flat_images = []
        for filename in request.POST.getlist('ajax_add_images'):
            path = os.path.join(settings.AJAX_UPLOAD_DIR, filename.split('/')[-1])
            if default_storage.exists(path):
                content = default_storage.open(path).read()
                flat_images.append([filename, ContentFile(content)])

        for image in flat_images[:1]:
            layout = Layout(
                newhome=newhome, name=_(u'Не указано'), area=0.0, section_id=section_id, building_id=section.building_id
            )
            layout.image.save(image[0], image[1])

        # Обновляем информацию по квартире и комнатам
        for newhome_layout in newhome.layouts.filter(section__id=section_id):
            form = LayoutForm(request.POST, instance=newhome_layout, prefix='layout_{}'.format(newhome_layout.id))
            if form.is_valid():
                newhome_layout = form.save(commit=False)

                layout_formset = layout_formset(
                    request.POST, queryset=newhome_layout.rooms.all(), prefix='layout_{}_rooms'.format(newhome_layout.id)
                )
                newhome_layout.area = 0.0
                rooms_for_delete = []
                for form_layout in layout_formset:
                    if form_layout.is_valid():
                        room = form_layout.save(commit=False)
                        room.layout = newhome_layout
                        if room.area and len(room.name):
                            room.save()
                            newhome_layout.area += float(room.area)

                        elif room.id and not all([room.area, len(room.name)]):
                            rooms_for_delete.append(room.id)

                newhome_layout.save()

                if rooms_for_delete:
                    Room.objects.filter(id__in=rooms_for_delete, layout=newhome_layout).delete()

        newhome.modified = datetime.datetime.now()
        newhome.save()

    # Подготавливаем разбивку по этажам и данные для форм
    layouts_list = {}
    layouts = newhome.layouts.filter(section__id=section_id).prefetch_related('rooms')

    for newhome_layout in layouts:
        ll = layouts_list.setdefault(newhome_layout.rooms_total, [])
        ll.append(newhome_layout)

        layout_formset = modelformset_factory(Room, form=RoomForm, extra=20)
        newhome_layout.formset = layout_formset(queryset=newhome_layout.rooms.all(),
                                                prefix='layout_{}_rooms'.format(newhome_layout.id))
        newhome_layout.form = LayoutForm(instance=newhome_layout, prefix='layout_{}'.format(newhome_layout.id))

    layout_name_options = LayoutNameOption.objects.all().order_by('name')

    return render(request, 'newhome/cabinet/flats.jinja.html', locals())


@login_required
@accept_newhome_user
def floors_remove(request, newhome_id, section_id, floor_id):
    """
    Профиль застройщика: удаление этажа из ЛК
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)
    Floor.objects.filter(id=floor_id, newhome__id=newhome.id, section__id=section_id).delete()

    return HttpResponseRedirect(reverse('profile_newhome_floors', args=[newhome_id, section_id]))


@login_required
@accept_newhome_user
def floors_copy(request, newhome_id, section_id, floor_id):
    """
    Профиль застройщика: копирование данных по этажу из ЛК
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)
    floor = Floor.objects.filter(id=floor_id, newhome__id=newhome.id, section__id=section_id).first()

    # получаем максимальный номер доступного этажа и увеличиваем на 1
    floor_position = max(map(int, map(
        lambda name: name.replace(u' этаж', u''),
        newhome.floors.filter(section__id=section_id).values_list('name', flat=True)
    ))) + 1
    floor_name = u'{} этаж'.format(floor_position)

    copied_floor, created = Floor.objects.get_or_create(
        newhome=newhome, number=floor_position, section=floor.section, building=floor.building,
        name=floor_name
    )

    with default_storage.open(floor.image.name) as f:
        copied_floor.image.save(floor.image.name, File(f))

    # Переносим планировки квартир
    for layout in floor.layouts.all():
        copied_floor.layouts.add(layout)
        for layout_flat in layout.layout_flats.filter(floor=floor):
            LayoutFlat.objects.create(layout=layout, coordinates=layout_flat.coordinates, price=layout_flat.price,
                                      currency=layout_flat.currency, floor=copied_floor)

    return HttpResponseRedirect(reverse('profile_newhome_floors', args=[newhome_id, section_id]))


@login_required
@accept_newhome_user
def floors(request, newhome_id, section_id):
    """
    Профиль застройщика: список этажей в ЖК

    todo: упростить до работы с одной картинкой
    """

    import ad.choices as ad_choices
    currencies = ad_choices.CURRENCY_CHOICES

    newhome = get_object_or_404(Newhome, pk=newhome_id)
    section = BuildingSection.objects.filter(pk=section_id).first()
    if section is None:
        section = BuildingSection.objects.none()
        section.id = section_id = 0

    if request.method == 'POST':
        # Работаем с первым корректным изображением
        for filename in request.POST.getlist('ajax_add_images'):
            path = os.path.join(settings.AJAX_UPLOAD_DIR, filename.split('/')[-1])
            if default_storage.exists(path):
                content = default_storage.open(path).read()
                floor_position = int(request.POST.get('floor_position', 1) or 1)
                floor_name = u'{} этаж'.format(floor_position)

                floor = Floor.objects.filter(
                    newhome=newhome, number=floor_position, section_id=section_id, building_id=section.building_id,
                    name=floor_name
                )
                # Нам нельзя повторять номера этажей
                if not floor.exists():
                    floor = Floor.objects.create(
                        newhome=newhome, number=floor_position, section_id=section_id, building_id=section.building_id,
                        name=floor_name
                    )
                    floor.image.save(filename, ContentFile(content))

                    break

        # Обновляем данные по привязкам
        floor_id = request.POST.get('floor_id', None)
        if floor_id:
            floor = Floor.objects.get(id=floor_id, newhome__id=newhome.id)
            old_layouts = set(floor.layouts.all().values_list('id', flat=True))
            new_layouts = set()
            LayoutFlat.objects.filter(floor=floor).delete()

            layouts_coordinates = request.POST.get('layouts_coordinates', '{"layouts_coordinates": []}')
            layouts_coordinates = json.loads(layouts_coordinates).get('layouts_coordinates', [])
            for layout_coordinate in layouts_coordinates:
                LayoutFlat.objects.create(layout_id=layout_coordinate['layout_id'],
                                          coordinates=layout_coordinate['coordinates'],
                                          price=layout_coordinate['price'] or 0,
                                          currency=layout_coordinate['currency'], floor=floor)

                floor.layouts.add(int(layout_coordinate['layout_id']))
                new_layouts.add(int(layout_coordinate['layout_id']))

            # Очищаем от неиспользуемых слоев
            for layout_id in old_layouts - new_layouts:
                floor.layouts.remove(layout_id)

        newhome.modified = datetime.datetime.now()
        newhome.save()

    newhome_floors = newhome.floors.filter(section__id=section_id)

    # получаем максимальный номер доступного этажа и увеличиваем на 1
    floor_position = max(map(int, map(
        lambda name: name.replace(u' этаж', u''),
        newhome.floors.filter(section__id=section_id).values_list('name', flat=True) or [u'0']
    ))) + 1

    return render(request, 'newhome/cabinet/floors.jinja.html', locals())


@login_required
@accept_newhome_user
def flats_available(request, newhome_id, section_id):
    """
    Профиль застройщика: список свободных квартир в доме
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)
    section = BuildingSection.objects.filter(pk=section_id).first()
    if section is None:
        section = BuildingSection.objects.none()
        section.id = section_id = 0

    # Подготавливаем разбивку по этажам
    floors_ = newhome.floors.filter(section__id=section_id).order_by('number')
    for floor_ in floors_:
        floor_.unavailable_layouts = list(Flat.objects.filter(
            newhome__id=newhome.id, floor__id=floor_.id, is_available=False
        ).values_list('layout__id', flat=True))

    return render(request, 'newhome/cabinet/flats-available.jinja.html', locals())


@login_required
def statistic(request):
    """
    Профиль застройщика: Статистика просмотров и заказов данных по форме

    todo: plural days
    """

    newhomes_id = list(Newhome.objects.filter(user=request.user).values_list('pk', flat=True))
    finish_at = datetime.datetime.now()
    start_at = datetime.datetime.now() + datetime.timedelta(days=-7)

    statistic = list(ViewsCount.objects.filter(
        newhome__pk__in=newhomes_id, date__gt=start_at, type__in=[0, 2]
    ))

    # Аггрегируем данные для построения графика
    statistic_week = collections.defaultdict(dict)
    for day in range(0, 7):
        date = (finish_at + datetime.timedelta(days=-day)).date()
        statistic_week[date][0] = 0
        statistic_week[date][2] = 0
        statistic_week[date]['date'] = date

    for stat in statistic:
        statistic_week[stat.date][stat.type] = stat.views
        statistic_week[stat.date]['date'] = stat.date

    statistic_week = [statistic_week[key] for key in sorted(statistic_week.keys())]

    # Рассчитываем количество заявок
    money_per_lead = get_lead_price('callrequest', 'newhomes', 'high')
    if money_per_lead > 0:
        request_amount = int(float(request.user.get_balance()) / float(money_per_lead))
    else:
        request_amount = int(float(request.user.get_balance()))

    # Рассчитываем количество дней
    statistic_week_sum = float(sum([sw[2] for sw in statistic_week]))
    if statistic_week_sum > 0:
        days_amount = int(float(request_amount) / statistic_week_sum)

    else:
        days_amount = int(float(request_amount))

    return render(request, 'newhome/cabinet/statistic.jinja.html', locals())


@login_required
@accept_newhome_user
def flats_available_set(request, newhome_id, floor_id, layout_id):
    """
    Профиль застройщика: меняем данные по свободной квартире в доме
    """

    newhome = get_object_or_404(Newhome, pk=newhome_id)
    newhome.modified = datetime.datetime.now()
    newhome.save()

    flat_, created = Flat.objects.get_or_create(newhome=newhome, floor_id=floor_id, layout_id=layout_id)
    flat_.is_available = not flat_.is_available
    flat_.save()

    layout = Layout.objects.get(id=layout_id)

    return HttpResponseRedirect(reverse('profile_newhome_flats_available', args=[newhome_id, layout.section_id]))
