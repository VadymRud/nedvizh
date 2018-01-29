# coding: utf-8
import calendar, datetime
from datetime import timedelta
from django.utils.translation import ugettext as _

class Calendar(object):
    def __init__(self, year, month, monthes_number=12):
        month_names = [
            _(u'Январь'), _(u'Февраль'), _(u'Март'),
            _(u'Апрель'), _(u'Май'), _(u'Июнь'),
            _(u'Июль'), _(u'Август'), _(u'Сентябрь'),
            _(u'Октябрь'), _(u'Ноябрь'), _(u'Декабрь'),
        ]

        self.weekdays = [_(u'Пн'), _(u'Вт'), _(u'Ср'), _(u'Чт'), _(u'Пт'), _(u'Сб'), _(u'Вс')]

        self.monthes = []
        python_calendar = calendar.Calendar()

        for i in xrange(monthes_number):
            self.monthes.append({
                'year': year,
                'month': month,
                'month_name': month_names[month - 1],
                'weeks': python_calendar.monthdatescalendar(year, month),
            })

            month += 1
            if month > 12:
                year += 1
                month = 1

def get_calendar():
    # 1-го числа текущего месяца показываем предыдущий месяц в календаре,  чтобы не было проблем с кеширование и для удобства юзеров
    today = datetime.datetime.today() - timedelta(days=1)
    return Calendar(today.year, today.month)

