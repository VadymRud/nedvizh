# coding: utf-8
import datetime
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.db.models import F
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect

from ad.choices import MODERATION_STATUS_CHOICES
from newhome.forms import NewhomeForm
from newhome.models import Moderation, Newhome


@staff_member_required
def newhome_moderation(request, moderation_id=None):
    if not request.user.has_perm('newhome.newhome_moderation') or not request.user.has_perm('newhome.newhome_admin'):
        return HttpResponseForbidden(u'У вас нет доступа к этой странице')

    # закрываем заявку на модерацию
    if 'newhome_id' in request.POST:
        newhome = Newhome.objects.get(pk=request.POST['newhome_id'])
        newhome.moderate(
            action=request.POST['action'], reject_status=request.POST.get('reject_status'), moderator=request.user
        )

        if 'next' in request.POST:
            return redirect(request.POST['next'])

    # на модерацию попадают объявления с заявками на модерацию (Moderation) и со статусом пре-модерация
    new_newhomes = Newhome.objects.filter(
        newhome_moderations__isnull=False, newhome_moderations__moderator__isnull=True
    )
    new_newhomes_count = new_newhomes.count()

    moderation = None
    if moderation_id:
        moderation = Moderation.objects.get(pk=moderation_id)
        
    else:
        newhomes = new_newhomes.order_by('newhome_moderations__start_time')[:10]
        for newhome in newhomes:
            # проверяем флаг блокировки объявления,
            # если объявление уже открыто другим менеджером, то его следует пропустить
            cache_key_for_blocking = 'newhome%d_moderation_block' % newhome.pk
            if cache.get(cache_key_for_blocking, request.user.id) == request.user.id:
                cache.set(cache_key_for_blocking, request.user.id, 60)
                try:
                    moderation, created = Moderation.objects.get_or_create(newhome=newhome, moderator__isnull=True)

                except Moderation.MultipleObjectsReturned:
                    moderations = Moderation.objects.filter(newhome=newhome, moderator__isnull=True).order_by('id')
                    moderation = moderations[0]
                    moderations.exclude(pk=moderation.pk).delete()
                break

    if not moderation:
        # нет объявлений на модерацию
        text = u'<br/><br/><h1 align="center"><i class="glyphicon glyphicon-thumbs-up"></i> ' \
               u'&nbsp; Поздравляем, вам нечего модерировать!</h1>'
        return render(request, "blank.jinja.html", {'debug': text})

    # форма создается для вывода названия полей, хотя самой формы там нет
    form = NewhomeForm(instance=moderation.newhome)

    # Статистика пользователя
    user_stats = Moderation.get_stats_by_user(moderation.newhome.user_id)

    # Статистика по модерированию новостроек
    moderations_today = Moderation.objects.filter(
        end_time__gt=datetime.date.today(), start_time__lt=F('end_time')
    ).order_by('-end_time')
    moderations_by_you_today = filter(
        lambda moderation_: moderation_.moderator_id == request.user.id, moderations_today
    )
    stats = {
        'moderated_total': len(moderations_today),
        'moderated_by_you': len(moderations_by_you_today),
        'last_10_moderation': moderations_by_you_today[:10]
    }

    return render(request, "newhome/admin/moderation.jinja.html", {
        'moderation': moderation,
        'stats': stats,
        'newhome': moderation.newhome,
        'moderation_queue': not moderation_id,
        'user_stats': user_stats,
        'form': form,
        'statuses': MODERATION_STATUS_CHOICES,
        'new_newhomes_count': new_newhomes_count,
    })
