# coding: utf-8
from functools import wraps

import datetime
from django.db.models import F
from django.http import HttpResponseGone
from django.http import HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

from newhome.models import Newhome, ViewsCount


def accept_newhome_user(func):
    """
    Проверяем, есть ли у пользователя доступ к странице с данной новостройкой
    """

    @wraps(func)
    def wrapped(request, newhome_id=None, *args, **kwargs):
        if request.user.has_perm('newhome.newhome_admin') and newhome_id is not None:
            get_object_or_404(Newhome, pk=newhome_id)

        elif newhome_id is not None:
            get_object_or_404(Newhome, pk=newhome_id, user=request.user)

        return func(request, newhome_id, *args, **kwargs)

    return wrapped


def restrict_access_for_developer(func):
    """
    Ограничиваем доступ для застройщиков (для персонала не действует данное ограничение)
    """

    @wraps(func)
    def wrapped(request, *args, **kwargs):
        if (
            hasattr(request.user, 'developer') and
            not request.user.is_staff and
            request.user.developer.is_cabinet_enabled
        ):
            return HttpResponseGone(render_to_string('403.jinja.html', locals(), request=request))

        return func(request, *args, **kwargs)

    return wrapped


def mark_unique_user(func):
    """Простая функция пометки пользователя на сутки о просмотре новостройки"""

    @wraps(func)
    def wrapped(request, *args, **kwargs):
        statistic_type = 0 if request.method == 'GET' else 2
        newhome_session = request.session.get('newhomes_{}'.format(statistic_type), {})
        newhome_id = kwargs.get('id', kwargs.get('newhome_id', None))

        # Подчищаем старые записи
        for key in newhome_session.keys():
            if key != str(datetime.date.today()):
                del newhome_session[key]

        # Запоминаем что данный пользователь посмотрел новостройки и обновляем статистику, при необходимости
        current_newhomes_id = newhome_session.get(str(datetime.date.today()), [])
        if newhome_id not in current_newhomes_id:
            current_newhomes_id.append(newhome_id)

            # для всех пользователей, кроме ботов (хорошие боты имеют значение -1)
            newhome = Newhome.objects.filter(pk=newhome_id).first()
            if newhome is None:
                return HttpResponsePermanentRedirect('/')

            if request.is_customer:
                # Cчитаем просмотры
                updated_rows = ViewsCount.objects.filter(
                    newhome__pk=newhome_id, type=statistic_type, date=datetime.date.today()
                ).update(views=F('views') + 1)
                if not updated_rows:
                    ViewsCount.objects.create(
                        newhome=newhome, type=statistic_type, date=datetime.date.today(), views=1
                    )

        newhome_session[str(datetime.date.today())] = current_newhomes_id
        request.session['newhomes_{}'.format(statistic_type)] = newhome_session

        return func(request, *args, **kwargs)

    return wrapped
