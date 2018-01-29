# coding: utf-8
from django.conf.urls import url

import newhome.views.cabinet

urlpatterns = [
    # Статистика
    url(r'^statistic/$', newhome.views.cabinet.statistic, name='profile_newhome_statistic'),

    # Мои новостройки
    url(r'^my_buildings/$', newhome.views.cabinet.my_buildings, name='profile_newhome_my_buildings'),

    # Дома и очереди
    url(r'^my_buildings/(?P<newhome_id>\d+)/queue/$', newhome.views.cabinet.queue, name='profile_newhome_queue'),
    url(r'^my_buildings/(?P<newhome_id>\d+)/queue/add/$', newhome.views.cabinet.queue_add, name='profile_newhome_queue_add'),
    url(r'^my_buildings/(?P<newhome_id>\d+)/queue/(?P<queue_id>\d+)/edit/$', newhome.views.cabinet.queue_edit, name='profile_newhome_queue_edit'),
    url(r'^my_buildings/(?P<newhome_id>\d+)/sections/$', newhome.views.cabinet.sections, name='profile_newhome_sections'),
    url(r'^my_buildings/(?P<newhome_id>\d+)/sections/building/add/$', newhome.views.cabinet.sections_building_add, name='profile_newhome_sections_building_add'),
    url(r'^my_buildings/(?P<newhome_id>\d+)/sections/building/(?P<building_id>\d+)/edit/$', newhome.views.cabinet.sections_building_edit, name='profile_newhome_sections_building_edit'),
    url(r'^my_buildings/(?P<newhome_id>\d+)/sections/building/(?P<building_id>\d+)/remove/$', newhome.views.cabinet.sections_building_remove, name='profile_newhome_sections_building_remove'),

    # Ход строительства
    url(r'^my_buildings/(?P<newhome_id>\d+)/workflow/$', newhome.views.cabinet.workflow, name='profile_newhome_workflow'),
    url(r'^my_buildings/(?P<newhome_id>\d+)/workflow/add/$', newhome.views.cabinet.workflow_progress_change, name='profile_newhome_workflow_add'),
    url(r'^my_buildings/(?P<newhome_id>\d+)/workflow/(?P<progress_id>\d+)/edit/$', newhome.views.cabinet.workflow_progress_change, name='profile_newhome_workflow_edit'),
    url(r'^my_buildings/(?P<newhome_id>\d+)/workflow/(?P<progress_id>\d+)/remove/$', newhome.views.cabinet.workflow_progress_remove, name='profile_newhome_workflow_remove'),

    # Описание/редактирование ЖК
    url(r'^my_buildings/(?P<newhome_id>\d+)/edit/$', newhome.views.cabinet.object_change, name='profile_newhome_object_edit'),
    url(r'^my_buildings/add/$', newhome.views.cabinet.object_change, name='profile_newhome_object_add'),
    url(r'^my_buildings/object-uploader$', newhome.views.cabinet.object_uploader, name='profile_newhome_object_upload'),

    # Описание/редактирование квартир ЖК
    url(r'^my_buildings/(?P<newhome_id>\d+)/(?P<section_id>\d+)/flats/(?P<flat_id>\d+)/remove/$', newhome.views.cabinet.flat_remove, name='profile_newhome_flats_remove'),
    url(r'^my_buildings/(?P<newhome_id>\d+)/(?P<section_id>\d+)/flats/(?P<flat_id>\d+)/add_ad/$', newhome.views.cabinet.flat_add_ad, name='profile_newhome_flats_add_ad'),
    url(r'^my_buildings/(?P<newhome_id>\d+)/(?P<section_id>\d+)/flats/copy/(?P<from_section_id>\d+)/$', newhome.views.cabinet.flats_copy, name='profile_newhome_flats_copy'),
    url(r'^my_buildings/(?P<newhome_id>\d+)/(?P<section_id>\d+)/flats/$', newhome.views.cabinet.flats, name='profile_newhome_flats'),
    url(r'^my_buildings/(?P<newhome_id>\d+)/flats/$', newhome.views.cabinet.flats, name='profile_newhome_flats'),

    # Описание/редактирование этажей ЖК
    url(r'^my_buildings/(?P<newhome_id>\d+)/(?P<section_id>\d+)/floors/$', newhome.views.cabinet.floors, name='profile_newhome_floors'),
    url(r'^my_buildings/(?P<newhome_id>\d+)/(?P<section_id>\d+)/floors/(?P<floor_id>\d+)/remove/$', newhome.views.cabinet.floors_remove, name='profile_newhome_floors_remove'),
    url(r'^my_buildings/(?P<newhome_id>\d+)/(?P<section_id>\d+)/floors/(?P<floor_id>\d+)/copy/$', newhome.views.cabinet.floors_copy, name='profile_newhome_floors_copy'),

    # Описание/редактирование свободных квартир ЖК
    url(r'^my_buildings/(?P<newhome_id>\d+)/(?P<section_id>\d+)/flats/available/$', newhome.views.cabinet.flats_available, name='profile_newhome_flats_available'),
    url(r'^my_buildings/(?P<newhome_id>\d+)/flats/available/(?P<floor_id>\d+)/(?P<layout_id>\d+)/$', newhome.views.cabinet.flats_available_set, name='profile_newhome_flats_available_set'),
]

