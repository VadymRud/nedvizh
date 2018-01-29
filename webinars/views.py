# coding: utf-8
import datetime

import pynliner
from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render, get_object_or_404
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt

from seo.meta_tags import get_meta_for_guide
from staticpages.models import Article
from utils.email import make_ga_pixel_dict, make_utm_dict
from webinars.forms import WebinarReminderForm
from webinars.models import Webinar
from utils.google_api import GoogleAPI
from utils.paginator import HandyPaginator


def index(request, type):
    """
    Список вебинаров
    """

    now_date = datetime.datetime.now()

    # Список ближайших 4 вебинаров / семинаров
    future_webinars = Webinar.objects.filter(type=type, finish_at__gt=now_date, is_published=True)[:4]

    # Список архивных вебинаров / семинаров
    archived_webinars = Webinar.objects.filter(
        type=type, finish_at__lt=now_date, is_published=True
    ).order_by('-start_at')

    # Проверяем незаполненные архивные вебинары
    if type == 'webinar':
        for archived_webinar in archived_webinars:
            checks = [
                not archived_webinar.youtube_duration,
                not archived_webinar.youtube_image
            ]
            if any(checks):
                gapi = GoogleAPI()
                try:
                    video_info = gapi.youtube_get_video_info(embed=archived_webinar.video)
                    archived_webinar.youtube_image = video_info['thumbnail_url']
                    archived_webinar.youtube_duration = video_info['duration']
                    archived_webinar.save()
                    archived_webinar.skip = False
                except:
                    archived_webinar.skip = True

            else:
                archived_webinar.skip = False

        # Добавляем проверку, что у нас рабочий EMBED стоит
        archived_webinars = filter(lambda a: not a.skip, archived_webinars)

    archived_webinars_paginator = HandyPaginator(archived_webinars, 12, request=request)

    type_display = _(u'вебинары') if type == 'webinar' else _(u'семинары')
    title = _(u'%s - портал недвижимости Mesto.ua') % type_display.capitalize()
    descriptions = {
        'webinar':  _(u"Вебинар для риэлторов от портала Mesto.ua. Подробные видео уроки \
                        про эффективные продажи недвижимости: работающие методы от практиков"),
        'seminar':  _(u"Обучающие семинары по продаже недвижимости от портала Mesto.ua. Эффективные \
                        методы, готовые и работающие кейсы от ведущих риелторов Украины")
    }
    description = descriptions['webinar'] if type == 'webinar' else descriptions['seminar']

    return render(request, 'webinars/index.jinja.html', locals())


def load_comments(request, type, slug):
    """
    Подгружаем еще комментарии
    """

    webinar = get_object_or_404(Webinar, type=type, slug=slug)
    comments = []
    last_comment_id = None
    next_page_token = None

    if webinar.is_active:
        # Загружаем комментарии
        gapi = GoogleAPI()

        if request.method == 'POST' and request.POST.get('npt', None):
            # Если передали страницу, то переключаем на нее
            comments_data = gapi.youtube_get_video_comments(
                embed=webinar.video, page_token=request.POST['npt']
            )

        else:
            # Запросили первую страницу
            comments_data = gapi.youtube_get_video_comments(embed=webinar.video)

        comments = comments_data.get('items', [])
        next_page_token = comments_data.get('nextPageToken', None)

        # Отображение только новых комментариев
        if request.method == 'POST' and request.POST.get('lcid', None):
            for i, comment in enumerate(comments):
                if comment['id'] == request.POST.get('lcid', None):
                    comments = comments[:i]
                    next_page_token = None
                    if comments:
                        last_comment_id = comments[0]['id']

                    else:
                        last_comment_id = request.POST.get('lcid', None)

    return render(request, 'webinars/comments.jinja.html', locals())


@csrf_exempt
def detail(request, type, slug):
    """
    Отображаем один вебинар
    """

    webinar = get_object_or_404(Webinar, type=type, slug=slug)
    comments = None
    next_page_token = None
    last_comment_id = None

    if webinar.is_active:
        gapi = GoogleAPI()
        # Загружаем комментарии
        comments_data = gapi.youtube_get_video_comments(embed=webinar.video)
        comments = comments_data.get('items', [])
        if comments:
            last_comment_id = comments[0]['id']

        next_page_token = comments_data.get('nextPageToken', None)

    initial_data = {
        'email': request.user.email if request.user.is_authenticated() else '',
        'name': request.user.get_full_name() if request.user.is_authenticated() else ''
    }
    form = WebinarReminderForm(initial=initial_data)
    show_form = webinar.is_registration_available
    if request.method == 'POST':
        if 'csrfmiddlewaretoken' not in request.POST and '.mesto.ua/' not in request.META.get('HTTP_REFERER', ''):
            return HttpResponseForbidden()

        form = WebinarReminderForm(request.POST)
        if form.is_valid():
            show_form = False

            webinar_reminder = form.save(commit=False)
            webinar_reminder.webinar = webinar
            webinar_reminder.language = translation.get_language()
            if request.user.is_authenticated():
                webinar_reminder.user = request.user

            webinar_reminder.save()

            event_type_str = {
                u'seminar': (_(u'семинар'), _(u'семинара')),
                u'webinar': (_(u'вебинар'), _(u'вебинара'))
            }[webinar.type]
            messages.info(
                request,
                _(u'Поздравляем, Вы зарегистрированы на супер-крутой %s <b>Mesto School</b><br/><br/>'
                  u'В день проведения %s Вы получите<br/> уведомление на Ваш email') % event_type_str,
                extra_tags='modal-dialog-w500 modal-mesto-school'
            )

            # Отправка сообщения об успешной регистрации на мероприятие
            if webinar.type == 'webinar':
                subject = _(u'Регистрация на бесплатный вебинар Mesto School')
            else:
                subject = _(u'Регистрация на бесплатный семинар Mesto School')

            utm = make_utm_dict(utm_campaign=webinar.type, utm_term=webinar.slug)
            content = render_to_string(
                'webinars/mail/event-registration.jinja.html',
                {
                    'utm': utm,
                    'ga_pixel': make_ga_pixel_dict(request.user if request.user.is_authenticated() else None, utm),
                    'event': webinar
                }
            )
            content_with_inline_css = pynliner.fromString(content)

            message = EmailMessage(
                subject, content_with_inline_css, settings.DEFAULT_FROM_EMAIL, [webinar_reminder.email])
            message.content_subtype = 'html'
            message.send()

            if 'next' in request.POST:
                return redirect(request.POST['next'] or request.META['HTTP_REFERER'])

    if type == 'seminar' and webinar.is_archived:
        previous_seminars = Webinar.objects.filter(
            type='seminar', finish_at__lt=datetime.datetime.now(), is_published=True
        ).exclude(id=webinar.id).order_by('-start_at')[:3]

    type_display = _(u'вебинары') if type == 'webinar' else _(u'семинары')
    title = webinar.__unicode__()

    return render(request, 'webinars/detail.jinja.html', locals())


def category_list(request):
    category = 'school'
    articles = Article.objects.filter(category=category, visible=True).filter(
        Q(subdomains=request.subdomain_region) | Q(subdomains__isnull=True)
    )
    paginator = HandyPaginator(articles, 16, request=request)

    title = _(u"Полезные статьи от портала недвижимости Mesto.ua")
    description = _(u"Полезные статьи о рынке недвижимости Украины. Новые методы продаж,\
                      что работает в 2017 году, актуальные кейсы от портала Mesto.ua")

    return render(request, 'guide/category_list.jinja.html', locals())


def article_detail(request, slug):
    category = 'school'
    query = Article.objects.filter(category=category, slug=slug, visible=True).filter(
        Q(subdomains=request.subdomain_region) | Q(subdomains__isnull=True)
    )
    if query:
        article = query[0]
    else:
        raise Http404
    title = article.title if article.title.strip() else article.name
    return render(request, 'guide/article_detail.jinja.html', locals())