# coding: utf-8
from django.shortcuts import render, redirect
from django.http import Http404
from django.db.models import Q
from django.core.urlresolvers import reverse
from django.conf import settings
from staticpages.models import Article
from seo.meta_tags import get_meta_for_guide
from utils.paginator import HandyPaginator


def has_subdomain(view_func):
    def decorator(request, *args, **kwargs):
        if request.subdomain_region.static_url == ';':
            raise Http404
        else:
            return view_func(request, *args, **kwargs)

    return decorator


def index(request):
    if request.subdomain_region.static_url == ';':
        return render(request, 'guide/region_choice.jinja.html')
    else:
        return redirect(reverse('guide:category_list', args=['news']))


@has_subdomain
def category_list(request, category):
    if category == 'news':
        categories = settings.NEWS_CATEGORIES
    else:
        categories = (category,)
    articles = Article.objects.filter(category__in=categories, visible=True).filter(
        Q(subdomains=request.subdomain_region) | Q(subdomains__isnull=True)
    )
    paginator = HandyPaginator(articles, 16, request=request)

    title, description = get_meta_for_guide(request.subdomain_region, category)
    return render(request, 'guide/category_list.jinja.html', locals())


@has_subdomain
def article_detail(request, category, slug):
    query = Article.objects.filter(category=category, slug=slug, visible=True).filter(
        Q(subdomains=request.subdomain_region) | Q(subdomains__isnull=True)
    )
    if query:
        article = query[0]
    else:
        raise Http404
    title = article.title if article.title.strip() else article.name
    return render(request, 'guide/article_detail.jinja.html', locals())
