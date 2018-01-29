# coding: utf-8

from django.contrib.admin import ListFilter

import datetime

datetime_formats = [
    ('%d.%m.%Y %H:%M:%S', u'дд.мм.гггг чч:мм:сс'),
    ('%d.%m.%Y %H:%M', u'дд.мм.гггг чч:мм'),
]

date_formats = [
    ('%d.%m.%Y', u'дд.мм.гггг'),
]

class BaseDateTimeFilter(ListFilter):
    template = 'admin_ext/filters/datetime.html'
    available_formats = [pattern for pattern, verbose in datetime_formats + date_formats]
    available_formats_verbose = u'Доступны следующие форматы дат\n%s' % u'\n'.join([verbose for pattern, verbose in datetime_formats + date_formats])
    field = None # установить при наследовании

    def __init__(self, request, params, model, model_admin):
        self.title = model._meta.get_field(self.field).verbose_name

        super(BaseDateTimeFilter, self).__init__(request, params, model, model_admin)

        self.keys = ['%s__%s' % (self.field, lookup) for lookup in ['gte', 'lte']]
        self.values = [params.pop(key, '') for key in self.keys]
        self.filters = {}
        self.errors = []
        for key, value in zip(self.keys, self.values):
            if value:
                error = True
                for pattern in self.available_formats:
                    try:
                        self.filters[key] = datetime.datetime.strptime(value, pattern)
                        error = False
                        break
                    except ValueError:
                        continue
            else:
                error = False
            self.errors.append(error)

    def queryset(self, request, queryset):
        return queryset.filter(**self.filters)

    def has_output(self):
        return True

    def choices(self, cl):
        base_query_string = cl.get_query_string(new_params={}, remove=self.keys)
        query_string = cl.get_query_string({})

        return [
            {'base_query_string': base_query_string, 'selected': self.field not in query_string},
            {'selected': self.field in query_string}
        ]


def make_datetime_filter(field_):
    class DateTimeFilter(BaseDateTimeFilter):
        field = field_
    return DateTimeFilter


class InputFilter(ListFilter):
    template = 'admin_ext/filters/input.html'
    input_type = 'text'

    # установить в подклассе (например, 'user__email__icontains', 'price_from__gte' и т.д.)
    queryset_lookup = None

    def __init__(self, request, params, model, model_admin):
        self.value = params.pop(self.parameter_name, '').strip()
        super(InputFilter, self).__init__(request, params, model, model_admin)

    # переопределить в подклассе, если потребуется (например, "return re.sub(r'[^0-9]*', '', value)")
    def clean_value(self, value):
        return value

    def queryset(self, request, queryset):
        if self.value:
            return queryset.filter(**{self.queryset_lookup: self.clean_value(self.value)})
        else:
            return queryset

    def has_output(self):
        return True

    def choices(self, cl):
        base_query_string = cl.get_query_string(remove=[self.parameter_name])
        query_string = cl.get_query_string()
        return [
            {'base_query_string': base_query_string, 'selected': self.parameter_name not in query_string},
            {'selected': self.parameter_name in query_string}
        ]
