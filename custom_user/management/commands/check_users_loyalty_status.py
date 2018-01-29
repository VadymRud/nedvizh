# coding: utf-8
from __future__ import unicode_literals

import datetime

import logging
from custom_user.models import User
from django.core.management.base import BaseCommand
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from paid_services.models import VipPlacement, CatalogPlacement
from utils.email import make_utm_dict, make_ga_pixel_dict


class Command(BaseCommand):
    help = 'Check user`s loyalty'

    def handle(self, *args, **options):
        utm = make_utm_dict(utm_campaign='loyalty')
        logger = logging.getLogger('loyalty')

        users = User.objects.filter(loyalty_started__isnull=False)
        for user in users:
            translation.activate(user.language)

            ga_pixel = make_ga_pixel_dict(user, utm)
            loyalty_bonus = int(user.get_loyalty_bonus() * 100.0)
            previous_loyalty_bonus = int(user.get_loyalty_bonus(
                (datetime.datetime.now() - datetime.timedelta(days=1)).date()) * 100.0)

            # Сначала радостные новости, проверяем изменился ли у пользователя бонус лояльности
            if loyalty_bonus != previous_loyalty_bonus:
                user.send_email(
                    subject=_(u'Поздравляем, Вы перешли на новый уровень'),
                    content=_(u'Ура, поздравляем, Вы перешли на новый уровень нашей программы лояльности.\n'
                              u'Теперь Вы будете получать %(loyalty_bonus)s%% бонус от каждого пополнения '
                              u'Баланса на сайте.\n'
                              u'Желаем вам успешных продаж и новых клиентов.'
                              ) % {'loyalty_bonus': loyalty_bonus},
                    utm=utm, ga_pixel=ga_pixel)

                logger.info('Loyalty',
                            extra={
                                'user_id': user.id,
                                'action': 'Send notification about changed loyalty from %s%% to %s%%' % (
                                    previous_loyalty_bonus, loyalty_bonus)
                            })

            inactive_date = datetime.date.today() - datetime.timedelta(days=5)

            # Проверяем активные пакеты
            user_plan = user.user_plans.order_by('-end').first()
            if user_plan:
                inactive_date = max(inactive_date, user_plan.end.date())

            # Проверяем активные ППК
            if user.activityperiods.filter(end__isnull=True).exists():
                continue

            ppk = user.activityperiods.exclude(end__isnull=True).order_by('-end').first()
            if ppk:
                inactive_date = max(inactive_date, ppk.end.date())

            # Проверем всякие размещения
            placements = VipPlacement.objects.filter(is_active=True, transaction__user=user)
            if placements.exists():
                continue

            placements = VipPlacement.objects.filter(transaction__user=user).order_by('-until').first()
            if placements:
                inactive_date = max(inactive_date, placements.until.date())

            placements = CatalogPlacement.objects.filter(is_active=True, transaction__user=user)
            if placements.exists():
                continue

            placements = CatalogPlacement.objects.filter(transaction__user=user).order_by('-until').first()
            if placements:
                inactive_date = max(inactive_date, placements.until.date())

            days_difference = (datetime.date.today() - inactive_date).days

            if days_difference == 1:
                # Первый день, когда у пользователя нет ничего активного
                user.send_email(
                    subject=_(u'Ваш бонус ждет Вас'),
                    content=_(u'Спешите пополнить Баланс и получите %(loyalty_bonus)s%% бонус от суммы пополнения.\n'
                              u'Нам будет очень жаль, если вы не станете участником программы лояльности и '
                              u'потеряете свой бонус.\n'
                              u'Приобретайте услуги публикации объявлений на mesto.ua для продолжения участия '
                              u'в программе лояльности'
                              ) % {'loyalty_bonus': loyalty_bonus},
                    template='paid_services/mail/loyalty-balance.jinja.html', utm=utm, ga_pixel=ga_pixel)

                logger.info('Loyalty',
                            extra={
                                'user_id': user.id,
                                'action': 'Send loyalty notification about first day without activity'
                            })

            elif days_difference == 4:
                # Последний допустимый день, когда у пользователя нет ничего активного
                user.send_email(
                    subject=_(u'Остался последний день. Спешите получить бонус'),
                    content=_(u'Сегодня остался последний день действия программы лояльности.\n'
                              u'Приобретайте услуги публикации объявлений на mesto.ua для продолжения участия в '
                              u'программе лояльности\n'
                              u'Нам будет очень жаль, если вы прекратите участие в программе лояльности и потеряете '
                              u'свой бонус.'
                              ),
                    template='paid_services/mail/loyalty-balance.jinja.html', utm=utm, ga_pixel=ga_pixel)

                logger.info('Loyalty',
                            extra={
                                'user_id': user.id,
                                'action': 'Send loyalty notification about last available day without activity'
                            })

            elif days_difference > 4:
                # Отключаем программу лояльности, письмо отправляется в сигналах User
                user.loyalty_started = None
                user.save()
