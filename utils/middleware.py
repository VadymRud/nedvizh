# coding=utf-8
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.cache import cache
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.utils.translation import ugettext_lazy as _
from django.utils import translation
from django.urls import translate_url, set_urlconf
from django.conf.urls.i18n import is_language_prefix_patterns_used

from ad.choices import DEAL_TYPE_CHOICES
from ad.models import Region
from profile.models import Stat
from ppc.models import REFERER_TRAFFIC_SOURCE

import urlparse
import datetime
import re


special_urls = re.compile('^/(admin|__debug__|ckeditor|thumbnail|mobile_api)/.*')

def skip_special_urls(method):
    if method.func_name == 'process_request':
        def decorated(self, request):
            if special_urls.match(request.path) is None:
                return method(self, request)
        return decorated
    elif method.func_name == 'process_response':
        def decorated(self, request, response):
            if special_urls.match(request.path) is None:
                return method(self, request, response)
            return response
        return decorated
    else:
        raise NotImplementedError('Cannot apply "skip_special_urls" decorator to "%s" middleware method' % method.func_name)


class AuthLogMiddleware(object):
    def process_request(self, request):
        if '/auth/login/' in request.build_absolute_uri() or '/auth/password/reset/confirm/' in request.build_absolute_uri():
            import logging
            logger_data = {'ip': request.META['REMOTE_ADDR'] , 'user': request.user.id}
            action_logger = logging.getLogger('user_action')
            action_logger.debug('User has shown own password to us on %s. Aha-ha-ha. POST: %s' %
                                (request.build_absolute_uri(), request.POST), extra=logger_data)

class SubdomainMiddleware(object):
    def process_request(self, request):
        request.provinces = Region.get_provinces()
        request.subdomains = Region.get_subdomains()

        if request.subdomains:
            for region in request.subdomains:
                if region.slug == request.subdomain or (region.static_url == ';' and request.subdomain is None):
                    request.subdomain_region = region
                    break
            else:
                from django_hosts.resolvers import reverse
                return HttpResponseRedirect(reverse('index'))
        else:
            raise Exception('No subdomains')  # чтобы не было бесконечных редиректов

        if request.subdomain == 'international':
            request.provinces = request.subdomain_region.get_children().order_by('name')


class TrafficSourceMiddleware(object):
    @skip_special_urls
    def process_request(self, request):
        request.traffic_source = request.COOKIES.get('traffic_source')
        if request.traffic_source is None:
            request.traffic_source = 'direct'

            utm_source = request.GET.get('utm_source')
            utm_medium = request.GET.get('utm_medium')

            if utm_source in ['yandex', 'google'] and utm_medium == 'cpc':
                request.traffic_source = '%s-%s' % (utm_source, utm_medium)
            else:
                if 'HTTP_REFERER' in request.META:
                    # для дебага может использоваться порт, поэтому .netloc
                    hostname = urlparse.urlparse(request.META['HTTP_REFERER']).netloc

                    if hostname and not hostname.endswith(settings.MESTO_PARENT_HOST):
                        for name, description, hostname_pattern in REFERER_TRAFFIC_SOURCE:
                            if re.match(hostname_pattern, hostname):
                                request.traffic_source = name
                                break
                        else:
                            request.traffic_source = 'other'

    @skip_special_urls
    def process_response(self, request, response):
        if request.COOKIES.get('traffic_source') is None and getattr(request, 'traffic_source'):
            response.set_cookie('traffic_source', value=request.traffic_source, domain=settings.SESSION_COOKIE_DOMAIN)

        return response


class CustomerMiddleware(object):
    @skip_special_urls
    def process_request(self, request):
        # плохие боты имеют HTTP_X_DISTIL_BOT>0
        # поисковики, соц сети, белый список (сотридники офиса) имеют HTTP_X_DISTIL_BOT=0, HTTP_X_DISTIL_WHITELIST > 0
        # всех остальных считаем обычными юзерами (покупателеями)
        request.is_customer = int(request.META.get('HTTP_X_DISTIL_BOT', 0)) == 0 and int(request.META.get('HTTP_X_DISTIL_WHITELIST', 0)) == 0

        # поисковые системы HTTP_X_DISTIL_WHITELIST=8, и заодно соц сети HTTP_X_DISTIL_WHITELIST=16
        request.is_search_engine = int(request.META.get('HTTP_X_DISTIL_BOT', 0)) == 0 and \
                                   int(request.META.get('HTTP_X_DISTIL_WHITELIST', 0)) in [8,16]

        # закрытие сайта от юзеров, доступ только сотрудникам
        if getattr(settings, 'ONLY_FOR_STAFF', None):
            if not request.user.is_authenticated() or not request.user.is_staff:
                return HttpResponseForbidden()

        # попап Экспертная проверка жилья
        '''
        # временно отключено, т.к. страница анализа будет переделываться
        if request.is_customer and 'expert_analysis_banner_was_shown' not in request.session:
            from django.template.loader import render_to_string
            from django.contrib import messages
            content = render_to_string('paid_services/analysis_popup.jinja.html')
            messages.info(request, content, extra_tags='modal-newhome-analysis')
            request.session['expert_analysis_banner_was_shown'] = True
        '''


class ProfileMiddleware(object):
    def log_entrances(self, request):
        last_action = request.user.last_action
        is_inactive_for_30minutes = (not last_action or (datetime.datetime.now() - last_action).total_seconds() > 60 * 30 )

        # обновляем отметку об активности, если предыдщая устарела на 5 минут или вообще отсутствовала
        if last_action is None or (datetime.datetime.now() - last_action).seconds > 5 * 60:
            request.user.last_action = datetime.datetime.now()
            request.user.save()

        # пользователь был неактивен или пришел с другого сайта
        referer = request.META.get('HTTP_REFERER')
        if is_inactive_for_30minutes or (referer and settings.MESTO_PARENT_HOST not in referer):
            Stat.write_stat(user=request.user, name='entrances')

    @skip_special_urls
    def process_request(self, request):
        request.profile_middleware = True
        request.favorite_properties = []

        # По умолчанию кабинет застройщика никому недоступен
        request.is_developer_cabinet_enabled = False

        if request.user.is_authenticated():
            self.log_entrances(request)

            # проверяем не сменился ли IP адрес пользователя
            if not request.user.ip_addresses or request.META['REMOTE_ADDR'] not in request.user.ip_addresses[0]:
                request.user.ip_addresses.insert(0, request.META['REMOTE_ADDR'])
                request.user.ip_addresses = request.user.ip_addresses[:10]
                request.user.save()

            # проверка соответствия языка в настройках пользователя и языка в request
            if request.LANGUAGE_CODE != request.user.language:
                original_url = request.get_full_path()
                # translate_url() должна вызываться для соотвествующего urlconf (например, для банков он другой), мидлвари django-hosts его не выставляют
                set_urlconf(request.urlconf)
                translated_url = translate_url(original_url, request.user.language)
                if translated_url != original_url:
                    return HttpResponseRedirect(translated_url)

            # тарифные планы
            request.active_plan = request.user.get_active_plan()

            # проверка новых событий по лидогенерации
            new_lead_cache_key = 'user{}_notified_about_new_lead'.format(request.user.id)
            if not request.active_plan and request.user.has_active_leadgeneration() and not cache.get(new_lead_cache_key):
                from agency.models import LeadHistoryEvent
                from django.contrib import messages
                import pytils
                import random

                week_ago = datetime.datetime.now() - datetime.timedelta(days=3)
                new_leads = LeadHistoryEvent.objects.filter(time__gt=week_ago, lead__user=request.user, is_readed=False,
                                                            object_id__isnull=False).order_by('-time')
                content = ''
                for lead in new_leads:
                    lead_source = lead.object

                    if lead_source._meta.model_name == 'call' and lead.object.duration < 5:
                        content += u'''
                            {} вы пропустили звонок от клиента.<br/> Пожалуйста, перезвоните ему по номеру <b>{}</b>.<br/><br/>
                        '''.format(pytils.dt.distance_of_time_in_words(lead.time), lead_source.callerid1)

                    if lead_source._meta.model_name == 'callrequest':
                        ad = lead_source.object
                        intrested_in = ''
                        if ad and ad._meta.model_name == 'ad':
                            intrested_in = _(u'Клиент интересуется объявлением <b>#{}</b> по адресу <b>{}</b>. ').format(ad.pk, ad.address)

                        if lead_source.phone:
                            content += _(u'''{} вам поступила заявка на обратный звонок от клиента <b>{}</b>. {}<br/>
                                Пожалуйста, перезвоните ему по номеру <b>{}</b>.<br/><br/>
                            ''').format(pytils.dt.distance_of_time_in_words(lead.time), lead_source.name, intrested_in, lead_source.phone)
                        elif lead_source.email:
                            content += _(u'''{} вам поступила запрос на детальную информацию от клиента <b>{}</b>. {}<br/>
                                Пожалуйста, напишите ему письмо на адрес <b>{}</b>.<br/><br/>
                            ''').format(pytils.dt.distance_of_time_in_words(lead.time), lead_source.name, intrested_in, lead_source.email)

                if content:
                    html = u'''<h4>{},</h4><br/>{}<br/><a href="{}?rnd={}#leadhistories" class="{}">Пропущенные обращения</a>
                    '''.format(
                        request.user or u'Уважаемый  пользователь', content,
                        reverse('agency_admin:crm'), random.randint(100, 999), 'btn btn-lg btn-danger btn-block'
                    )
                    messages.info(request, html, extra_tags='modal-style2')
                    cache.set(new_lead_cache_key, True, 60*60)

            # Уменьшаем количество запросов к кешу
            request.favorite_properties = cache.get('saved_properties_for_user%d' % request.user.id, [])

            # новый кабинет для админов агентств
            request.own_agency = request.user.get_own_agency()

            # включен кабинет застройщика или нет
            request.is_developer_cabinet_enabled = (
                hasattr(request.user, 'developer') and request.user.developer.is_cabinet_enabled
            )


# скопировано с django.middleware.locale.LocaleMiddleware и значительно упрощено
# с учетом хранения языка в модели User, без использования сессии
# (вместо надстройки над оригинальным middleware и его частичным использованием)
class CustomLocaleMiddleware(object):
    def process_request(self, request):
        urlconf = getattr(request, 'urlconf', settings.ROOT_URLCONF)
        i18n_patterns_used, prefixed_default_language = is_language_prefix_patterns_used(urlconf)

        if i18n_patterns_used:
            language = translation.get_language_from_path(request.path_info) or settings.LANGUAGE_CODE
        else:
            language = settings.LANGUAGE_CODE

        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()

    def process_response(self, request, response):
        language = translation.get_language()
        if 'Content-Language' not in response:
            response['Content-Language'] = language
        return response


class MobileMiddleware(object):
    @skip_special_urls
    def process_request(self, request):
        request.mobile_device = None

        # для всех пользователей, кроме ботов (хорошие боты имеют значение -1)
        if request.host.name == 'default' and request.is_customer:
            user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
            if "iphone" in user_agent or "ipad" in user_agent:
                request.mobile_device = 'iphone'
            if "android" in user_agent:
                request.mobile_device = 'android'

            if request.mobile_device and 'no-mobile-app' not in request.COOKIES:
                offer_mobile_app_url = reverse('offer_mobile_app')
                if not request.path.startswith(offer_mobile_app_url):
                    return HttpResponseRedirect(offer_mobile_app_url)

