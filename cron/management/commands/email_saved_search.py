# coding: utf-8
import pynliner
from django.core.exceptions import FieldError
from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.core.cache import cache
from django.utils import translation
from django.conf import settings

from profile.models import SavedSearch
from ad.models import Ad, Region

import datetime
import traceback


class Command(BaseCommand):
    help = 'emails user about new ads in saved search'

    def handle(self, *args, **options):
        print datetime.datetime.now()

        now = datetime.datetime.now()
        last_run = cache.get('saved-search-subscribe', now - datetime.timedelta(days=2))
        new_ads = Ad.objects.filter(status=1, is_published=True, created__gte=last_run).prefetch_related('photos')

        for search in SavedSearch.objects.filter(user=1980, subscribe=True, user__subscribe_info=True).prefetch_related('user'):
            print 'saved search #%d (user #%d):' % (search.id, search.user.id),

            if search.user.email:
                try:
                    new_ads_for_user = new_ads.filter(
                        property_type=search.property_type, region=search.region, **make_filters(search.query_parameters)
                    )
                    if search.deal_type != 'all-real-estate':
                        new_ads_for_user = new_ads_for_user.filter(deal_type=search.deal_type)

                except FieldError:
                    traceback.print_exc(5)
                    search.delete()
                else:
                    if new_ads_for_user:
                        print 'new ads - %s' % [ad.pk for ad in new_ads_for_user]
                        subject = u'Mesto.ua'
                        translation.activate(search.user.language)
                        content = render_to_string('mail/saved_search.jinja.html', {
                            'user': search.user,
                            'property_list': new_ads_for_user[:10],
                            'search': search,
                        })
                        content_with_inline_css = pynliner.fromString(content)
                        message = EmailMessage(
                            subject, content_with_inline_css, settings.DEFAULT_FROM_EMAIL, [search.user.email]
                        )
                        message.content_subtype = 'html'
                        message.send()
                    else:
                        print 'no new ads'
            else:
                print 'user doesn`t have an email'

        cache.set('saved-search-subscribe', now, None)


def make_filters(parameters):
    filters = {}

    for name, value in parameters.items():
        if name not in ['gclid', 'sort', 'added_days','floor_variants'] and not isinstance(value, list):
            if name == 'region':
                filters.update(region__in=Region.objects.get(id=parameters['region']).get_descendants(include_self=True))
            elif name == 'property_type':
                if value != 'all-real-estate':
                    filters.update(property_type=value)
            elif name == 'rooms':
                filters.update(rooms__gte=int(value[0]), rooms__lte=int(value[-1]))
            elif name == 'with_image' and value == 'on':
                filters.update(has_photos=True)
            elif name == 'without_commission' and value == 'on':
                filters.update(without_commission=True)
            elif name == 'price_to':
                filters.update(price_uah__lte=value)
            elif name == 'price_from':
                filters.update(price_uah__gte=value)
            elif name == 'area_to':
                filters.update(area_living__lte=value)
            elif name == 'area_from':
                filters.update(area_living__gte=value)
            else:
                filters[name] = value

    return filters
