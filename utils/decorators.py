# coding: utf-8
from functools import wraps

import datetime
import logging

from django.core.urlresolvers import reverse
from django.db.models import F
from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponsePermanentRedirect, QueryDict
from django.shortcuts import get_object_or_404

from ad.models import Ad, PhoneInAd, DeactivationForSale
from custom_user.models import User
from paid_services.models import Transaction, CatalogPlacement


def temporary_http404(func):
    @wraps(func)
    def decorated_view(request, *args, **kwargs):
        raise Http404

    return decorated_view


def update_ads_status(func):
    """
    Декоратор для обновления статусов у объявления
    """

    @wraps(func)
    def wrapped(request, *args, **kwargs):
        data = request.POST.copy() if request.method == 'POST' else request.GET.copy()

        # Проверяем, на необходимость работы с декоратором
        checks = [
            {'action', 'activate', 'deactivate', 'sold', 'delete', 'buy_vip', 'change_owner'} & set(data.keys())
        ]

        if not all(checks):
            return func(request, *args, **kwargs)

        # логируем действия с объявлениями
        data.pop('csrfmiddlewaretoken', None)
        logger_data = {'ip': request.META['REMOTE_ADDR'] , 'user': request.user.id}
        action_logger = logging.getLogger('user_action')
        action_logger.debug('Actions with ads: %s' % data.urlencode(), extra=logger_data)

        if request.own_agency:
            # Все объекты агентства
            allowed_user_ids = list(request.own_agency.get_realtors().values_list('user_id', flat=True))
        else:
            allowed_user_ids = [request.user.id]

        # Выбираем действие, которое необходимо провести
        posted_ads = [int(ad_id) for ad_id in data.getlist('ad')]
        action = data.get('action')

        # Если было действие для одного объявления, то уточняем ключ для POST
        ad_action = set(data.keys()) & {'activate', 'deactivate', 'delete', 'buy_vip'}
        if ad_action:
            action = ad_action.pop()
            posted_ads = [int(data[action])]

        # Если что-то пошло не так - высылаем исключение
        checks = [
            not allowed_user_ids,
            not action,
            None in allowed_user_ids
        ]
        if any(checks):
            raise Exception('can not do action with values')

        # отмечаем причины деактивации для объявлений раздела Продажа
        if action in ['deactivate', 'delete', 'sold'] and 'deactivation_reason' in data:
            sold_ad_ids = []
            for ad in Ad.objects.filter(deal_type='sale', pk__in=posted_ads, user__in=allowed_user_ids):
                if not ad.has_deactivation_reason():
                    DeactivationForSale.objects.create(basead=ad, user=ad.user, reason=data['deactivation_reason'])
                    sold_ad_ids.append(ad.id)

            # юзер нажал "Продолжить размещение", поэтому объявления по продаже нужно активировать. Отметка "Продано" устанавливается выше
            if action == 'sold' and sold_ad_ids:
                action = 'activate'
                posted_ads = sold_ad_ids

                # для свежих объявлений сдвигаем дату обновления на неделю назад, чтобы опустить в поиске
                Ad.objects.filter(id__in=sold_ad_ids, updated__gt=datetime.datetime.now()-datetime.timedelta(days=7)).update(updated=F('updated') - datetime.timedelta(days=7))

        if action == 'delete':
            for ad in Ad.objects.exclude(status=211).filter(pk__in=posted_ads, user__in=allowed_user_ids):
                ad.status = 211
                ad.save()

        elif action == 'deactivate':
            for ad in Ad.objects.filter(status=1, pk__in=posted_ads, user__in=allowed_user_ids):
                ad.status = 210
                ad.save()

        elif action == 'activate':
            for ad in Ad.objects.filter(status__in=[210, 211], pk__in=posted_ads, user__in=allowed_user_ids):
                # очищаем причину деактивации на случай, если объект действительно вернулся в продажу
                if ad.deal_type == 'sale':
                    ad.deactivations.filter(returning_time=None).update(returning_time=datetime.datetime.now())

                if ad.addr_country == 'UA':
                    if not ad.newhome_layouts.exists() and ad.user.can_activate_ad(force=True):
                        ad.status = 1
                        ad.save()
                    elif ad.newhome_layouts.exists() and ad.user.has_active_leadgeneration('newhomes'):
                        # Если это объявление на основе новостройки, то разрешено активировать
                        # ТОЛЬКО доступные к продаже квартиры
                        if ad.newhome_layouts.first().has_available_flats:
                            ad.status = 1
                            ad.save()
                    else:
                        # обычных юзеров шлем на выбор плана, остальных - на выбор типа размещения
                        url_params = QueryDict(mutable=True)
                        url_params.update({
                            'no_prolong':'',
                            'next': '%s?%s' % (request.path, data.urlencode())
                        })
                        if ad.user.get_realtor() or ad.user.is_developer():
                            return HttpResponseRedirect('%s?%s' % (reverse('services:index'), url_params.urlencode()))
                        else:
                            return HttpResponseRedirect('%s?%s' % (reverse('services:plans'), url_params.urlencode()))

                if ad.addr_country != 'UA':
                    if ad.pk in CatalogPlacement.get_active_user_ads():
                        ad.status = 1
                        ad.save()
                    else:
                        return HttpResponseRedirect(reverse('profile_checkout') + '?intl_catalog=intl_mesto&ads=%s' % ad.pk)

        elif action == 'buy_vip':
            vip_ads_as_string = ','.join([str(ad_id) for ad_id in posted_ads])
            return HttpResponseRedirect(reverse('profile_checkout') + '?vip&ads=%s' % vip_ads_as_string)

        elif action == 'change_owner':
            user = User.objects.get(pk=data['user'])
            for ad in Ad.objects.filter(pk__in=posted_ads, user__in=allowed_user_ids):
                old_user = ad.user
                ad.user = user
                if ad.addr_country == 'UA' and ad.status == 1 and not ad.user.can_activate_ad(force=True):
                    ad.status = 210
                ad.save()

                # обновляется количество объявлений предыдущего юзера
                old_user.update_ads_count()

                # Обновляем телефоны объявления
                ad.phones_in_ad.all().delete()
                user = User.objects.get(id=data['user'])
                for position, phone in enumerate(user.phones.all()):
                    PhoneInAd.objects.create(phone=phone, basead_id=ad.pk, order=position)


            return HttpResponse("OK", content_type="text/plain")

        # поле request.user.ads_count может дальше использоваться в шаблонах, поэтому принудительно его нужно обновить
        request.user.update_ads_count()

        if request.method == 'GET':
            return HttpResponseRedirect(request.path)

        return func(request, *args, **kwargs)

    return wrapped
