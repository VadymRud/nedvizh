# coding: utf-8
import hashlib

from bs4 import BeautifulSoup
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.http import  Http404
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.db.models import Q, Count, Max
from django.utils.http import urlquote_plus

from custom_user.models import User
from profile.models import Message, MessageList
from profile.forms import MessageReplyForm, MessageAboutAdForm, UnsubscribeForm
from ad.models import Ad
from django.utils.translation import ugettext as _

from utils.paginator import HandyPaginator


@staff_member_required
def admin_message_list_preview(request, id):
    message_list = MessageList.objects.get(id=id)
    new_message = Message(from_user=request.user, title=message_list.title, text=message_list.content, message_list_id=id, text_type='html')
    dialog_messages = [new_message]
    form = MessageReplyForm(instance=new_message)
    return render(request, 'profile/messages/form.jinja.html', locals())

@login_required
def link_clicker(request, message_id=None):
    message = Message.objects.get(pk=message_id)
    message.link_clicked = True
    message.save()

    return redirect(request.GET['url'])

@login_required
def add_message(request, property_id=None, user_id=None):
    if property_id and (user_id is None):
        ad = get_object_or_404(Ad, pk=property_id)
        to_user = ad.user
        title = _(u'Объявление #%(id)d: %(title)s, %(address)s') % {'id': ad.pk, 'title': ad.title, 'address': ad.address}
        form_class = MessageAboutAdForm

    elif user_id and (property_id is None):
        ad = None
        to_user = User.objects.get(id=user_id)
        title = _(u'Сообщение от пользователя')
        form_class = MessageReplyForm
    else:
        raise Exception('Illegal request to add a message')

    new_message = Message(to_user=to_user, from_user=request.user, basead=ad, title=title)

    if property_id and 'subject' in request.GET:
        new_message.subject = request.GET['subject']

     # попытка найти старое сообщение, чтобы объединить диалог
    new_message.root_message = Message.objects.filter(to_user=to_user, from_user=request.user, basead=ad).order_by('time').first()

    form = form_class(request.POST if request.method == 'POST' else None, instance=new_message)
    if form.is_valid():
        new_message = form.save()

        if property_id:
            messages.info(request, _(u'Ваше сообщение было успешно<br/> отправлено владельцу объявления.'), extra_tags='modal-dialog-w400 modal-success')

        # если сообщение создавалось со страницы объявления, то перекидываем юзера в ЦРМ, если он агентство с включенным новым личным кабинетом
        if request.own_agency:
            return redirect(reverse('agency_admin:crm'))
        else:
            return redirect(reverse('messages:inbox'))

    title = _(u'Отправить сообщение')
    return render(request, 'profile/messages/add_message.jinja.html', locals())

@login_required
def reply(request, dialog_id=None, property_id=None):
    # диалога еще нет, сообщение со страницы объявления
    if property_id:
        ad = get_object_or_404(Ad, pk=property_id)
        new_message = Message(to_user=ad.user, from_user=request.user, basead=ad,
            title=_(u'Объявление #%(id)d: %(title)s, %(address)s') % {'id': ad.pk, 'title': ad.title, 'address': ad.address})

        # попытка найти старое сообщение, чтобы объединить диалог
        same_message = Message.objects.filter(to_user=ad.user, from_user=request.user, basead=ad).order_by('time')
        if same_message.exists():
            root_message =  same_message[0].root_message
            new_message.root_message = root_message
            dialog_id = root_message.id

        dialog_messages = []

    # открыт созданный диалог
    if dialog_id:
        condition = (Q(from_user=request.user) | Q(to_user=request.user)) & Q(root_message=dialog_id)

        dialog_messages = list(Message.objects.filter(condition).order_by('time')\
            .prefetch_related('to_user','to_user__agencies','from_user', 'from_user__agencies', ).order_by('-id'))

        # устанавливаем отметки о прочтенных сообщения и сбрасываем кеш со счетчиком
        messages_readed = [message.id for message in dialog_messages if message.to_user == request.user and not message.readed]
        Message.objects.filter(id__in=messages_readed).update(readed=True)
        cache.delete('new_messages_for_user%d' % request.user.id)

        if not dialog_messages:
            raise Http404

        # замена ссылок на view с редиректом
        for message in dialog_messages:
            if '</a>' in message.text:
                message.text = BeautifulSoup(message.text, 'html.parser')
                for link in message.text.find_all('a'):
                    url = link.get('href')
                    if url and 'mailto:' not in url:
                        link['href'] = '%s?url=%s' % (reverse('messages:redirect', kwargs={'message_id':message.id}),
                                                      urlquote_plus(url))

        root_message = dialog_messages[-1] # reverse ordering
        to_user = root_message.to_user if root_message.to_user_id != request.user.id else root_message.from_user

        new_message = Message(to_user=to_user, from_user=request.user, root_message=root_message,
                          basead=root_message.basead, title=root_message.title)

    form = MessageReplyForm(request.POST if request.method == 'POST' else None, instance=new_message)
    if form.is_valid():
        new_message = form.save()
        return redirect(reverse('messages:inbox'))

    title = _(u'Отправить сообщение')
    return render(request, 'profile/messages/form.jinja.html', locals())


@login_required
def inbox(request, outbox=False):
    condition = Q(from_user=request.user) | Q(to_user=request.user)
    sended_message_lists = Q(from_user=request.user, message_list__isnull=False) & ~Q(to_user=request.user)

    if request.GET.get('filter') == 'unreaded':
        condition.add(Q(readed=False) & Q(to_user=request.user), Q.AND)

    # группируем по диалогам (root_message у группы сообщений одинаковый)
    dialogs = Message.objects.filter(condition).exclude(sended_message_lists)\
        .values("root_message").annotate(count=Count('id'), id=Max('id'))

    counters = dict( (message['id'], message['count']) for message in dialogs )

    user_messages = Message.objects.filter(id__in=counters.keys()).exclude(sended_message_lists).order_by('-time')

    # архив
    if request.GET.get('filter') == 'deleted':
        user_messages = user_messages.filter(root_message__hidden_for_user=request.user)
        archive = True
    else:
        user_messages = user_messages.exclude(root_message__hidden_for_user=request.user)

    for message in user_messages:
        message.replies = counters[message.id] - 1

    if 'delete-this' in request.GET or 'delete-selected' in request.GET:
        message_ids = [] + request.GET.getlist('delete-this')
        if 'delete-selected' in request.GET:
            message_ids += request.GET.getlist('delete')

        root_messages_to_delete = Message.objects.filter(id__in=message_ids)
        for message in root_messages_to_delete:
            message.hidden_for_user.add(request.user)

        # обновим счетчик новых сообщений
        cache.delete('new_messages_for_user%d' % request.user.id)

        return redirect('.')

    paginator = HandyPaginator(user_messages, 10, request=request)

    title = _(u'Отправленные сообщения') if outbox else _(u'Входяшие сообщения')
    return render(request, 'profile/messages/list.jinja.html', locals())


def unsubscribe(request):
    """
    Отписываемся от рассылки
    :param request:
    :return:
    """

    form = None
    request_hash = request.GET.get('hash', '')
    request_email = request.GET.get('email', '')

    valid_hash = u'Unsubscribe %s, please' % request_email
    valid_hash = hashlib.md5(valid_hash.encode('utf-8')).hexdigest()[10:22]

    # Проверяем хэш
    if request_hash == valid_hash:
        # Ищем пользователя по email
        user = User.objects.filter(email=request_email)
        if user.exists():
            if request.method == 'GET':
                form = UnsubscribeForm(instance=user.first())

            else:
                form = UnsubscribeForm(request.POST, instance=user.first())
                if form.is_valid():
                    form.save()
                    messages.info(request, u'Ваши настройки успешно обновлены')

                else:
                    messages.error(request, u'Ошибка сохранения, попробуйте повторить попытку позже')

    return render(request, 'profile/messages/unsubscribe.jinja.html', locals())
