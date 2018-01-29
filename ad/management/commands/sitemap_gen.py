# coding: utf-8
from django.core.management.base import BaseCommand
from django.utils import translation
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.template import loader
from django.conf import settings
from django.core.cache import cache

from ad.models import Region, Ad
from ad.forms import PROPERTY_TYPE_SEARCH_CHOICES
from staticpages.models import Article
from newhome.models import Newhome
from utils.storage import overwrite

import itertools
import xml.dom.minidom
import datetime
import re


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--subdomain', '-s', dest='subdomain')
        parser.add_argument('--root-domain', '-r', dest='root_domain', action='store_true')

    def handle(self, *args, **options):
        translation.activate('ru')

        subdomains_query = Region.objects.filter(subdomain=True).exclude(static_url=';')

        if options['subdomain']:
            subdomain = subdomains_query.get(slug=options['subdomain']).slug
        elif options['root_domain']:
            subdomain = None
        else:
            subdomains = [None] + list(subdomains_query.values_list('slug', flat=True).order_by('slug'))
            index = cache.get('sitemap-subdomain-index', 0)
            if index >= len(subdomains):
                index = 0
            print '%d of %d' % (index + 1, len(subdomains))
            subdomain = subdomains[index]
            index += 1
            cache.set('sitemap-subdomain-index', index, None)

        sitemaps = {'ru': [], 'uk': []}

        for sitemap_class in sitemap_section_classes:
            sitemap_obj = sitemap_class(subdomain)
            section_sitemaps = sitemap_obj.generate()
            for language, pathes in section_sitemaps.items():
                sitemaps[language].extend(pathes)

        for language, pathes in sitemaps.items():
            xml = loader.render_to_string('sitemap_index.xml', {'sitemaps': [default_storage.url(path) for path in pathes]})
            subdomain_path = 'sitemaps/%s%s.xml' % (subdomain or 'mesto', {'ru': '', 'uk': '-uk'}[language])
            overwrite(subdomain_path, ContentFile(xml))
            print 'created', subdomain_path

        update_index()


def update_index():
    subdomain_index_file_re = re.compile(r'^(%s)(-(?P<language>uk))?\.xml$' % '|'.join(
        Region.objects.filter(subdomain=True).exclude(static_url=';').values_list('slug', flat=True)
    ))

    domain_file_re = re.compile(r'^mesto(-(?P<language>uk))?-(%s)(-\d+)?\.xml$' % '|'.join(
        [sitemap_class.section_name for sitemap_class in sitemap_section_classes]
    ))

    sitemaps = {'ru': [], 'uk': []}

    dirs, files = default_storage.listdir('sitemaps')
    for file_ in files:
        path = 'sitemaps/%s' % file_

        # сильно устаревший sitemap (бывает при отключении у региона поддомена)
        if (datetime.datetime.now() - default_storage.get_modified_time(path)).days > 7:
            default_storage.delete(path)
        else:
            subdomain_index_file_match = subdomain_index_file_re.match(file_)
            if subdomain_index_file_match:
                language = subdomain_index_file_match.group('language') or 'ru'
                sitemaps[language].append(path)

            domain_file_match = domain_file_re.match(file_)
            if domain_file_match:
                language = domain_file_match.group('language') or 'ru'
                sitemaps[language].append(path)

    for language, pathes in sitemaps.items():
        xml = loader.render_to_string('sitemap_index.xml', {'sitemaps': [default_storage.url(path) for path in pathes]})
        index_path = 'sitemaps/mesto%s.xml' % {'ru': '', 'uk': '-uk'}[language]
        overwrite(index_path, ContentFile(xml))
        print 'updated', index_path


class SectionSitemap(object):
    section_name = None
    chunk_size = 20000
    template_name = 'sitemap.xml'
    translate_to_uk = True
    changefreq = 'weekly'

    def __init__(self, subdomain):
        self.subdomain = subdomain

        # по аналогии с SubdomainMiddleware
        if subdomain:
            self.subdomain_region = Region.objects.get(subdomain=True, slug=self.subdomain)
        else:
            self.subdomain_region = Region.objects.get(static_url=';')

    def iterate_urls_by_chunk(self):
        chunks = 0

        chunk = []
        for url in self.iterate_urls():
            chunk.append(url)
            if len(chunk) == self.chunk_size:
                yield chunk
                chunks += 1
                chunk = []

        if len(chunk) or chunks == 0:
            yield chunk

    def iterate_urls(self):
        raise NotImplementedError()

    def make_path(self, language, chunk_number):
        return 'sitemaps/%s%s-%s%s.xml' % (
            self.subdomain or 'mesto',
            {'ru': '', 'uk': '-uk'}[language],
            self.section_name,
            '-%d' % chunk_number if chunk_number > 1 else ''
        )

    # можно изменить стандартный шаблон, и просто передавать в него список ссылок и changefreq отдельно
    def make_urls_dict(self, urls):
        return [{'location': url, 'changefreq': self.changefreq} for url in urls]

    def generate(self):
        sitemaps = {'ru': [], 'uk': []}

        for chunk_number, chunk_urls in enumerate(self.iterate_urls_by_chunk(), start=1):
            xml = loader.render_to_string(self.template_name, {'urlset': self.make_urls_dict(chunk_urls)})
            path = self.make_path('ru', chunk_number)
            overwrite(path, ContentFile(xml))
            print 'created', path
            sitemaps['ru'].append(path)

            # костыль для дублирования sitemaps с укр. адресами
            if self.translate_to_uk:
                xml_uk = xml.replace('%s/' % settings.MESTO_PARENT_HOST, '%s/uk/' % settings.MESTO_PARENT_HOST)
                uk_path = self.make_path('uk', chunk_number)
                overwrite(uk_path, ContentFile(xml_uk))
                print 'created', uk_path
                sitemaps['uk'].append(uk_path)

        return sitemaps


class ArticleSitemap(SectionSitemap):
    section_name = 'article'
    changefreq = 'monthly'
    translate_to_uk = False  # PRE_UA_VERSION_CRUTCH_GUIDE: для путеводителя не создается sitemap с украинскими ссылками

    def iterate_urls(self):
        for category in settings.NEWS_CATEGORIES:
            yield self.subdomain_region.get_host_url('guide:category_list', kwargs={'category': category})

        if self.subdomain:
            articles = Article.objects.filter(subdomains=self.subdomain_region)
        else:
            articles = Article.objects.filter(subdomains=None)

        for article in articles:
            yield article.get_absolute_url()


class PropertySitemap(SectionSitemap):
    section_name = 'propertyitem'

    def iterate_urls(self):
        if self.subdomain:
            regions = self.subdomain_region.get_descendants(include_self=True)
        else:
            regions = Region.objects.filter(static_url__startswith=';')

        for ad in Ad.objects.filter(is_published=True, region__in=regions).only('region').select_related('region'):
            yield ad.get_absolute_url()


class PropertyRegionSitemap(SectionSitemap):
    section_name = 'region'

    def iterate_urls(self):
        if self.subdomain:
            regions = self.subdomain_region.get_descendants(include_self=True)
        else:
            regions = Region.objects.filter(static_url__startswith=';')

        for region in regions.filter(
            kind__in=['street', 'locality', 'village', 'district', 'province']
        ).prefetch_related('region_counter', 'subwayline_set__stations'):

            for counter in region.region_counter.all():
                if counter.count > 0:
                    for property_type, property_type_verbose in PROPERTY_TYPE_SEARCH_CHOICES:
                        if counter.deal_type == 'rent_daily' and property_type not in ['flat', 'house', 'room']:
                            continue

                        base_url = region.get_deal_url(counter.deal_type, property_type)
                        yield base_url

                        if property_type in ['flat', 'house', 'commercial', 'garages', 'all-real-estate']:
                            for room in [1, 2, 3, 4, 5]:
                                yield base_url + ('?rooms=%d' % room)

                        for line in region.subwayline_set.all():
                            for station in line.stations.all():
                                station_url = region.get_deal_url(counter.deal_type, property_type, station.slug)
                                yield station_url

                                if property_type in ['flat', 'house', 'commercial', 'garages', 'all-real-estate']:
                                    for room in [1, 2, 3, 4, 5]:
                                        yield station_url + ('?rooms=%d' % room)


class NewhomeSitemap(SectionSitemap):
    section_name = 'newhomes'

    def iterate_urls(self):
        if self.subdomain:
            regions = self.subdomain_region.get_descendants(include_self=True)
        else:
            regions = Region.objects.filter(static_url__startswith=';')

        for newhome in Newhome.objects.filter(is_published=True, region__in=regions).only('region').select_related('region'):
            yield newhome.get_absolute_url()


class NewhomesRegionSitemap(SectionSitemap):
    section_name = 'newhomes-region'

    def iterate_urls(self):
        if self.subdomain and self.subdomain != 'international':  # все ссылки поиска новостроек у нас только на поддоменах
            city_children = self.subdomain_region.get_descendants(include_self=True)
            province = self.subdomain_region.get_ancestors().get(kind='province')
            province_chidren_without_subdomain = province.get_descendants(include_self=True).filter(static_url__startswith=';')

            if Newhome.objects.filter(is_published=True, region__in=city_children).exists():
                yield self.subdomain_region.get_deal_url(deal_type='newhomes')

            if Newhome.objects.filter(is_published=True, region__in=province_chidren_without_subdomain).exists():
                yield self.subdomain_region.get_deal_url(deal_type='newhomes') + '?region_search=1'


sitemap_section_classes = [ArticleSitemap, PropertySitemap, PropertyRegionSitemap, NewhomeSitemap, NewhomesRegionSitemap]

