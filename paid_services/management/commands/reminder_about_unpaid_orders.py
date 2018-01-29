# coding: utf-8

from django.core.management.base import BaseCommand
from django_hosts.resolvers import reverse
from django.utils import translation

from paid_services.models import Order
from django.utils.translation import ugettext_lazy as _

import datetime
from collections import defaultdict


class Command(BaseCommand):
    def handle(self, *args, **options):
        now = datetime.datetime.now()
        period = [now - datetime.timedelta(hours=3), now - datetime.timedelta(hours=1)]
        print 'unpaid orders between', period

        orders = Order.objects.filter(time__range=period, is_paid=False, is_reminder_sent=False)
        orders_by_user = defaultdict(list)
        for order in orders:
            orders_by_user[order.user].append(order)

        for user, orders_list in orders_by_user.items():
            translation.activate(user.language)
            
            content = ""
            for order in orders_list:
                content += _(u'<span class="pink">%s</span> вы пытались совершить оплату на '
                             u'сумму <span class="pink">%s</span> грн.<br/>') % \
                           (order.time.strftime('%d.%m.%Y %H:%M'), order.amount)

            content += _(u'Данная сделка не была завершена.<br/>Вы можете произвести оплату '
                         u'повторно на странице "<a href="%s">Мои счета</a>".') % reverse('profile_orders')

            user.send_email('Неоплаченные счета', content)

        print 'Reminders have sent for %d orders' % orders.update(is_reminder_sent=True)

