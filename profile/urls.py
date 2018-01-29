# coding=utf-8
from django.conf.urls import url, include
from django.views.generic import TemplateView
from django.conf import settings

from profile import views, views_balance, views_import, views_messages
from paid_services import views as paid_services_views

import agency.views
import newhome.views.cabinet

import_patterns = [
    url(r'^$', views_import.index, name='index'),
    url(r'^settings/$', views_import.settings, name='settings'),
    url(r'^howto/$', views_import.howto, name='howto'),
    url(r'^help/$', views_import.import_view(TemplateView.as_view(template_name='profile/import/help.html')), name='help'),
    url(r'^test/$', views_import.test, name='test'),
    url(r'^test/update_status/$', views_import.test_update_status, name='test_update_status'),
    url(r'^log/$', views_import.log, name='log'),
    url(r'^report/$', views_import.report, name='report'),
]

messages_patterns = [
    url(r'^$', views_messages.inbox, name='inbox'),
    url(r'^reply/(?P<dialog_id>\d+)/$', views_messages.reply, name='reply'),
    url(r'^about-property/(?P<property_id>\d+)/$', views_messages.add_message, name='about_property'),
    url(r'^redirect/(?P<message_id>\d+)/$', views_messages.link_clicker, name='redirect'),
    url(r'^unsubscribe/$', views_messages.unsubscribe, name='unsubscribe'),
]

languages_re = '|'.join(zip(*settings.LANGUAGES)[0])

urlpatterns = [
    url(r'^$', views.index, name='profile_index'),

    url(r'^set_language/(?P<language_code>%s)/$' % languages_re, views.set_language, name='profile_set_language'),

    url(r'^settings/profile/$', views.edit_profile, name='profile_settings'),
    url(r'^settings/agency/$', agency.views.agency_form, name='profile_settings_agency'),
    url(r'^settings/developer/$', newhome.views.cabinet.developer_form, name='profile_settings_developer'),

    url(r'^manager_callrequest/$', views.manager_callrequest, name='profile_manager_callrequest'),

    url(r'^import/', include((import_patterns, 'profile', 'import'))),
    url(r'^messages/', include((messages_patterns, 'profile', 'messages'))),

    url(r'^orders/$', views_balance.orders, name='profile_orders'),

    url(r'^balance/$', views_balance.balance, name='profile_balance'),
    url(r'^balance/topup/$', views_balance.topup, name='profile_balance_topup'),
    url(r'^balance/topup/success.html$', views_balance.topup_success),
    url(r'^balance/topup/fail.html$', views_balance.topup_fail),
    url(r'^balance/topup/status.html$', views_balance.topup_status),
    url(r'^balance/topup/comeback.html$', views_balance.topup_comeback_from_payment_system),

    url(r'^my_properties/$', views.my_properties, name='profile_my_properties'),

    url(r'^my_properties/add/$', views.edit_property, name='profile_add_property'),
    url(r'^my_properties/edit/(?P<property_id>\d+)/$', views.edit_property, name='profile_edit_property'),

    url(r'^my_properties/views/(?P<property_id>\d+)/$', views.views_graph, name='profile_views_graph'),
    url(r'^my_properties/views/(?P<property_id>\d+)/clear/$', views.clear_views_graph, name='profile_clear_views_graph'),

    url(r'^checkout/$', views.checkout, name='profile_checkout'),
    url(r'^purchase/$', views.purchase, name='profile_purchase'),

    url(r'^services/', include('paid_services.urls', namespace='services')),
    url(r'^plans/$', paid_services_views.plans, name='profile_plans'), # TODO: эту страницу нужно будет удалить после проверки ссылок на неё из flatpages

    url(r'ajax-upload$', views.import_uploader, name="my_ajax_upload"),
    url(r'rotate_ad_photo$', views.rotate_ad_photo, name='rotate_ad_photo'),

    url(r'^saved_searches/$', views.saved_searches, name='profile_saved_searches'),
    url(r'^saved_searches/add/$', views.save_search, name='profile_save_search'),
    url(r'^saved_searches/subscribe/$', views.save_search, {'subscribe': True}, name='profile_subscribe_search'),
    url(r'^saved_searches/delete/(?P<search_id>\d+)/$', views.delete_saved_searches, name='profile_delete_saved_searches'),
    url(r'^saved_searches/clear/$', views.clear_saved_searches, name='profile_clear_saved_searches'),
    url(r'^saved_properties/$', views.saved_properties, name='profile_saved_properties'),
    url(r'^saved_properties/add/(?P<property_id>\d+)/$', views.save_property, name='profile_save_property'),
    url(r'^saved_properties/clear/$', views.clear_saved_properties, name='profile_clear_saved_properties'),

    url(r'^change_email/$', views.change_email, name='change_email'),
    url(r'^confirm_email_change/(?P<key>\w+)/$', views.confirm_email_change, name='confirm_email_change'),

    url(r'^notification_link_click/$', views.notification_link_click, name='notification_link_click'),
]
