# coding: utf-8

from django.contrib import admin
from django.db.models import Sum


class SumFilter(admin.ListFilter):
    sum_field = None
    title = u'всего'
    template = 'admin/filter_sum.html'

    def has_output(self):
        return True

    def queryset(self, request, queryset):
        return queryset

    def choices(self, cl):
        return [cl.queryset.aggregate(Sum(self.sum_field))['%s__sum' % self.sum_field] or 0]

