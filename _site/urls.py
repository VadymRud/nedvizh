# coding: utf-8
from django.contrib import messages
from django.conf.urls import include, url
from django.conf import settings
from django.http import HttpResponseRedirect
from django.views.generic import TemplateView
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.utils.translation import ugettext as _
from django.conf.urls.i18n import i18n_patterns

import django.views

from profile.forms import RegistrationForm
from utils import error_pages
from utils import fix_ckeditor
from utils.thumbnail import view as thumbnail_view

import ad.views
from agency.views import add_realtor_confirm
import autoposting.views
import staticpages.views
import promo.views
import utils.views
import profile.views
import profile.views_messages
import profile.views_balance
import newhome.views.admin
import profile.admin_views
import ad.admin_views
import ppc.views
import utils.admin_views
import i18n.admin_urls
import banner.views

# TODO надо попробовать сделать отдельное приложение, в котором были бы все эти фиксы
from registration.backends.default.views import RegistrationView, ActivationView
from utils import fix_registration
fix_registration.patch()

class MestoRegistrationView(RegistrationView):
    template_name = 'registration/registration_form.jinja.html'
    form_class = RegistrationForm

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            response = self.form_valid(form)
            content = _(u'<span class="pink h5">Регистрация прошла успешно!</span><br>Мы рады, что Вы с нами!<br><br>'
                        u'На указанный email отправлена ссылка<br>для активации аккаунта.')
            messages.info(request, content, extra_tags='modal-success text-center')
            return HttpResponseRedirect(request.POST.get('next', '/'))
        else:
            return self.form_invalid(form)

    def register(self, *args, **kwargs):
        with transaction.atomic():
            return super(MestoRegistrationView, self).register(*args, **kwargs)


class MestoActivationView(ActivationView):
    template_name = 'registration/activate.jinja.html'

    def get_success_url(self, user):
        return ('profile_index', (), {})

admin.autodiscover()

handler403 = error_pages.PermissionDenied.as_view()
handler404 = error_pages.PageNotFound.as_view()
handler500 = error_pages.ServerError.as_view()

urlpatterns = [
    url(r'^robots.txt$', staticpages.views.robots),
    url(r'^ads.txt$', staticpages.views.ads_txt),
    url(r'^yandex_(?P<hash>[a-z0-9\-\.]*).html$', staticpages.views.yandex),
    url(r'^google(?P<hash>[a-z0-9\-\.]*).html$', staticpages.views.google),

    # silde-banner statistics
    url(r'^banner_link_click/(?P<id>\d+)/$', banner.views.banner_link_click, name="banner_link_click"),

    url(r'^ckeditor/upload/', staff_member_required(fix_ckeditor.upload), name='ckeditor_upload'), # см. utils.fix_ckeditor
    url(r'^ckeditor/', include('ckeditor_uploader.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/profile/messagelist/(?P<id>\d+)/preview/$', profile.views_messages.admin_message_list_preview, name='admin_message_list_preview'),
    url(r'^admin/profile/export_stats/$', profile.admin_views.export_profiles_stats),
    url(r'^admin/profile/export_entrances_stats/$', profile.admin_views.export_entrances_stats, name='admin_export_entrances_stats'),
    url(r'^admin/profile/export_ads_by_region_stats/$', profile.admin_views.export_ads_by_region_stats, name='admin_export_ads_by_region_stats'),

    # Статистика
    url(r'^admin/statistics/$', profile.admin_views.statistics, name='admin_statistics_general'),
    url(r'^admin/statistics/ads_by_region/$', profile.admin_views.statistics_ads_by_region,
        name='admin_statistics_ads_by_region'),
    url(r'^admin/statistics/weekly/$', profile.admin_views.statistics_weekly, name='admin_statistics_weekly'),
    url(r'^admin/statistics/monthly/$', profile.admin_views.statistics_monthly, name='admin_statistics_monthly'),
    url(r'^admin/statistics/by_province/$', profile.admin_views.statistics_by_province,
        name='admin_statistics_by_province'),
    url(r'^admin/statistics/analysis_disclosed_contacts/$', profile.admin_views.statistics_analysis_disclosed_contacts,
        name='admin_statistics_analysis_disclosed_contacts'),

    url(r'^admin/profile/add_transaction/$', profile.admin_views.add_transaction, name='admin_add_transaction'),
    url(r'^admin/fastcheck/$', ad.admin_views.fastcheck),
    url(r'^admin/ad/moderation/$', ad.admin_views.moderation, name='moderation_queue'),
    url(r'^admin/ad/moderation/stats/$', ad.admin_views.moderation_stats, name='moderation_stats'),
    url(r'^admin/ad/moderation/(?P<moderation_id>\d+)/$', ad.admin_views.moderation, name='moderation_detail'),
    url(r'^admin/ad/region/merge/$', ad.admin_views.region_merge),
    url(r'^admin/cache/$', utils.admin_views.cache_view),
    url(r'^admin/cache/(?P<key>[a-zA-Z0-9_]+)/$', utils.admin_views.cache_key),
    url(r'^admin/export_status/$', utils.admin_views.export_status, name='admin_export_status'),

    # Модерация новостроек
    url(r'^admin/newhome/', include('newhome.urls.admin')),

    url(r'^admin/', include(admin.site.urls)),

    url(r'^thumbnail/(?P<key>[a-f0-9]{32})/$', thumbnail_view, name='thumbnail'),
    url(r'^no-thumbnails/$', ad.views.no_thumbnails, name='no_thumbnails'),

    url(r'^social/', include('social_django.urls', namespace='social')),

    # для автопостинга объявлений в Facebook
    url(r'^ap/facebook-callback/$', autoposting.views.facebook_callback, name='autoposting-facebook-callback'),
    url(r'^ap/vk-callback/$', autoposting.views.vk_callback, name='autoposting-vk-callback'),
]


ad_patterns = {
    'region_slug': '(?P<region_slug>[/a-z0-9\-]*?)',
    'region_slug_greedy': '(?P<region_slug>[/a-z0-9\-]*)',
    'subway_slug': '(?P<subway_slug>[/a-z0-9\-]*)',
    'deal_type': '(?P<deal_type>sale|rent|rent_daily)',
    'property_type': '(?P<property_type>flat|room|house|plot|commercial|property|garages|other|all-real-estate)',
}

urlpatterns += i18n_patterns(
    url(r'^jsi18n/$', django.views.i18n.javascript_catalog, name='javascript_catalog'),

    url(r'^$', ad.views.index, name='index'),

    url(r'^subscription/$', promo.views.subscription, name='promo_subscription'),

    url(r'^offer_mobile_app/$', utils.views.offer_mobile_app, name='offer_mobile_app'),
    url(r'^offer_mobile_app/decline/$', utils.views.offer_mobile_app, {'decline': True}, name='offer_mobile_app_decline'),

    url(r'^%(deal_type)s/%(region_slug)s-%(property_type)s/metro-%(subway_slug)s/' % ad_patterns, include('ad.urls')),
    url(r'^%(deal_type)s/%(region_slug_greedy)s/metro-%(subway_slug)s/' % ad_patterns, include('ad.urls')),
    url(r'^%(deal_type)s-%(property_type)s/metro-%(subway_slug)s/' % ad_patterns, include('ad.urls')),
    url(r'^%(deal_type)s/metro-%(subway_slug)s/' % ad_patterns, include('ad.urls'), {'region_slug':None}),

    url(r'^%(deal_type)s/%(region_slug)s-%(property_type)s/' % ad_patterns, include('ad.urls')),
    url(r'^%(deal_type)s/%(region_slug_greedy)s/' % ad_patterns, include('ad.urls')),
    url(r'^%(deal_type)s-%(property_type)s/' % ad_patterns, include('ad.urls')),
    url(r'^%(deal_type)s/' % ad_patterns, include('ad.urls'), {'region_slug':None}),

    url(r'^newhomes/%(region_slug)s-%(property_type)s/metro-%(subway_slug)s/' % ad_patterns, include('newhome.urls.newhomes'), {'deal_type': 'newhomes'}),
    url(r'^newhomes/%(region_slug_greedy)s/metro-%(subway_slug)s/' % ad_patterns, include('newhome.urls.newhomes'), {'deal_type': 'newhomes'}),
    url(r'^newhomes-%(property_type)s/metro-%(subway_slug)s/' % ad_patterns, include('newhome.urls.newhomes'), {'deal_type': 'newhomes'}),
    url(r'^newhomes/metro-%(subway_slug)s/' % ad_patterns, include('newhome.urls.newhomes'), {'deal_type': 'newhomes', 'region_slug': None}),

    url(r'^newhomes/%(region_slug)s-%(property_type)s/' % ad_patterns, include('newhome.urls.newhomes'), {'deal_type': 'newhomes'}),
    url(r'^newhomes/%(region_slug_greedy)s/' % ad_patterns, include('newhome.urls.newhomes'), {'deal_type': 'newhomes'}),
    url(r'^newhomes-%(property_type)s/' % ad_patterns, include('newhome.urls.newhomes'), {'deal_type': 'newhomes'}),
    url(r'^newhomes/' % ad_patterns, include('newhome.urls.newhomes'), {'deal_type': 'newhomes', 'region_slug': None}),

    url(r'^mobile_api/', include('mobile_api.urls')),

    url(r'^ivr/incoming/', ppc.views.incoming_call),
    url(r'^ivr/finished/', ppc.views.finished_call),

    url(r'^city-autocomplete/', ad.views.cities_autocomplete, name='cities_autocomplete'),
    url(r'^region-cities/(?P<rid>\d+)/', ad.views.region_cities, name='region_cities'),

    url(r'^professionals/', include('professionals.urls', namespace='professionals')),

    url(r'^ad/(?P<id>\d+)$', ad.views.short_property),

    url(r'^guide/', include('guide.urls', namespace='guide')),

    url(r'^auth/register/$', MestoRegistrationView.as_view(), name='register'),
    url(r'^auth/register/complete/$', TemplateView.as_view(template_name='registration/registration_complete.jinja.html'), name='registration_complete'),
    url(r'^auth/activate/(?P<activation_key>\w+)/$', MestoActivationView.as_view(), name='registration_activate'),
    url(r'^auth/login/', profile.views.auth_login, name='auth_login'),
    url(r'^auth/logout/', profile.views.auth_logout, name='auth_logout'),
    url(r'^auth/password/change/$', auth_views.password_change, {'template_name': 'registration/password_change_form.jinja.html'}, name='password_change'),
    url(r'^auth/password/change/done/$', auth_views.password_change_done, {'template_name': 'registration/password_change_done.jinja.html'}, name='password_change_done'),
    url(r'^auth/password/reset/$', auth_views.password_reset, {'template_name': 'registration/password_reset_form.jinja.html'}, name='password_reset'),
    url(r'^auth/password/reset/confirm/(?P<uidb64>[0-9A-Za-z]+)-(?P<token>.+)/$', auth_views.password_reset_confirm, {'template_name': 'registration/password_reset_confirm.jinja.html'}, name='password_reset_confirm'),
    url(r'^auth/password/reset/complete/$', auth_views.password_reset_complete, {'template_name': 'registration/password_reset_complete.jinja.html'}, name='password_reset_complete'),
    url(r'^auth/password/reset/done/$', auth_views.password_reset_done, {'template_name': 'registration/password_reset_done.jinja.html'}, name='password_reset_done'),

    url(r'^account/', include('profile.urls')),
    url(r'^account/agency/', include('agency.urls', namespace='agency_admin')),
    url(r'^rc/(?P<key>[\da-f]{32})/$', add_realtor_confirm, name='agency_add_realtor_confirm'),

    url(r'^account/developer/', include('newhome.urls.cabinet')),

    # ссылки для платежной системы PeliPay
    url(r'^payment/successUrl', profile.views_balance.topup_success),
    url(r'^payment/failUrl', profile.views_balance.topup_fail),
    url(r'^payment/statusUrl', profile.views_balance.topup_status, {'payment_system': 'pelipay'}),

    url(r'^pages(?P<url>.*/)$', staticpages.views.simplepage, name='simplepage'),

    url(r'^event/sales-trening/$', promo.views.training_with_topal, name='training_with_topal'),
    url(r'^seminar/kharkiv/$', promo.views.training_kharkiv, name='training_kharkiv'),

    # Mesto School
    url(r'^mesto-school/', include('webinars.urls', namespace="school")),

    url(r'^faq/$', staticpages.views.faq_index, name='faq_index'),
    url(r'^faq/(?P<slug>[_a-zA-Z0-9\-\.]*)/$', staticpages.views.faq_category_articles, name='faq_category_articles'),
    url(r'^faq/(?P<category_slug>[_a-zA-Z0-9\-\.]*)/(?P<slug>[_a-zA-Z0-9\-\.]*)/$', staticpages.views.faq_article, name='faq_article'),

    # Лендинги
    url(r'^', include('mail.urls', namespace='landing')),

    prefix_default_language=False,
)

if settings.DEBUG:
    import debug_toolbar
    
    urlpatterns += [
        url(r'^__debug__/', include(debug_toolbar.urls)),
        url(r'^media/(?P<path>.*)$', django.views.static.serve, {'document_root': settings.MEDIA_ROOT, 'show_indexes': True }),
    ]
