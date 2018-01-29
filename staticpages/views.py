# coding: utf-8
from django.http import HttpResponseNotFound, HttpResponse, Http404
from django.core.files.storage import default_storage
from django.shortcuts import render
from django.core.urlresolvers import reverse

from staticpages.models import SimplePage, FAQCategory, FAQArticle


def simplepage(request, url):
    try:
        page = SimplePage.objects.get(url=url, urlconf='_site.urls')
    except SimplePage.DoesNotExist:
        raise Http404
    else:
        # TODO: раньше было булево поле pages_menu в ExtendedFlatPage, не хочется копировать его в SimplePage,
        # может быть можно сделать модель для меню или что-то в этом роде
        ulrs = ('/about/', '/about/advertising/', '/about/contact/', '/about/private-policy/', '/about/terms-of-use/')
        menu_items = [
            (reverse('simplepage', kwargs={'url': menu_page.url}), menu_page.title)
            for menu_page in SimplePage.objects.filter(urlconf='_site.urls', url__in=ulrs)
        ]
        return render(request, 'staticpages/simplepage.jinja.html', {'page': page, 'menu_items': menu_items})

def robots(request):
    host = request.subdomain_region.get_host()
    sitemap_url = default_storage.url('sitemaps/%s.xml' % (request.subdomain or 'mesto'))
    sitemap_uk_url = default_storage.url('sitemaps/%s-uk.xml' % (request.subdomain or 'mesto'))

    extra_disallow = ''
    if request.subdomain == 'international':
        extra_disallow += 'Disallow:/guide/\n'

    # PRE_UA_VERSION_CRUTCH_GUIDE: возможно нужно будет когда-нибудь открыть украинский Путеводитель (/uk/guide/) для индексации
    robots = '''User-agent: *
Host: https://%s
Disallow:/uk/guide/
Disallow:/social/
Disallow:/auth/
Disallow:/thumbnail/
Disallow:/no-thumbnails/
Disallow:/subscription/
Disallow:/*_openstat
Disallow:/*from=adwords
Disallow:/*utm_source*
Disallow:/*gclid=
Disallow:/*?price*
Disallow:/*?letter=*
Disallow:/*-garages/?rooms=*
Disallow: /*?id=*
Disallow:/*?addr_street=*
Disallow:/*?added_days=
Disallow:/*?sort=
Disallow:/*?*no_agent=
Disallow:/*?*with_image=
Disallow:/*?*without_commission=
Disallow:/accounts/
Disallow:/sale-room/?property_type=room
Disallow: /reviews/
Disallow: *?deal_type=
Disallow: *?region_search=*
%s
Sitemap: %s
Sitemap: %s''' % (host, extra_disallow, sitemap_url, sitemap_uk_url)

    return HttpResponse(robots, content_type="text/plain")


def google(request, hash):
    if hash in ['a8d5198249f0666c']:
        content = '''google-site-verification: google%s.html''' % hash
        return HttpResponse(content, content_type="text/html")
        
    return HttpResponseNotFound('<h1>Page not found</h1>')


def yandex(request, hash):
    if hash in ['4ccd3a3c72299dd1', '4c36d2e681c02b52', '5674e2b185c5f6cd', '54bb8c3b90aafddc', '70702f17f976a5be',
                '56f7e1c8ad2ab6d3', '5b69ec0f4cc831d3', '55d4fc01f7db5dda', '5c5443d0391ebd0b', '4c49f7c5f1114700',
                '6f8c613067518952', '67e29d9145d08cb5', '62cf71c55d17380a', '78d3a0df7ca63d55', '5b69ec0f4cc831d3',
                '4ccd3a3c72299dd1', '55d4fc01f7db5dda', '4c36d2e681c02b52', '62cf71c55d17380a', '5c5443d0391ebd0b',
                '4c49f7c5f1114700', '54bb8c3b90aafddc', '6f8c613067518952', '70702f17f976a5be', '67e29d9145d08cb5',
                '56f7e1c8ad2ab6d3', '5674e2b185c5f6cd']:
        content = '''<html>
                    <head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"></head>
                    <body>Verification: %s</body></html>''' % hash
        return HttpResponse(content, content_type="text/html")

    return HttpResponseNotFound('<h1>Page not found</h1>')


def faq_index(request):
    """
    Отображение списка разделов FAQ
    """
    faq_categories = FAQCategory.objects.filter(is_published=True)

    # Подвязываем статьи, отображаемые на главной странице, к разделам
    categories_id = [faq_category.id for faq_category in faq_categories]
    articles = FAQArticle.objects.filter(category__id__in=categories_id, is_published=True).select_related('category')
    faq_articles = {}
    for article in articles:
        fa = faq_articles.setdefault(article.category_id, [])
        fa.append(article)

    return render(request, 'faq/index.jinja.html', {
        'faq_categories': faq_categories,
        'faq_articles': faq_articles
    })


def faq_category_articles(request, slug):
    """
    Отображение списка вопросов раздела FAQ
    """
    faq_articles = FAQArticle.objects.filter(
        is_published=True, category__slug=slug
    ).prefetch_related('category')

    if not faq_articles.exists():
        faq_category = FAQCategory.objects.get(slug=slug)

    else:
        faq_category = faq_articles.first().category

    return render(request, 'faq/category.jinja.html', {
        'faq_category': faq_category,
        'faq_articles': faq_articles
    })


def faq_article(request, category_slug, slug):
    """
    Отображаем один вопрос
    """

    articles = FAQArticle.objects.filter(
        category__slug=category_slug, is_published=True
    ).select_related('category').order_by('order', 'id')

    prev_article, current_article, next_article = (None, None, None)
    for position, article in enumerate(articles):
        if article.slug == slug:
            current_article = article

            if position > 0:
                prev_article = articles[position - 1]

            if position < len(articles) - 1:
                next_article = articles[position + 1]

    if not current_article:
        raise Http404()

    return render(request, 'faq/article.jinja.html', {
        'next_article': next_article,
        'prev_article': prev_article,
        'faq_article': current_article
    })

def ads_txt(request):
    content = '''admixer.net, 7e42e70c-801a-47e7-967a-d45a54f8a7ff, direct
google.com, pub-3379969116950199, reseller, f08c47fec0942fa0
smartadserver.com, 1994, reseller
appnexus.com, 6953, reseller
adform.com, 1762, reseller'''
    return HttpResponse(content, content_type="text/plain")