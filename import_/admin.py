# coding: utf-8

from django.contrib import admin
from django.core.urlresolvers import reverse

from models import ImportTask, ImportAdTask


class ImportTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'agency_link', 'is_test', 'status', 'error', 'stats', 'created', 'started', 'completed', 'importadtasks_link')
    raw_id_fields = ('agency',)
    list_filter = ('is_test', 'status')

    def get_queryset(self, request):
        return super(ImportTaskAdmin, self).get_queryset(request).prefetch_related('agency')

    def agency_link(self, obj):
        return u'<a href="%s?id=%s">%s</a>' % (reverse('admin:agency_agency_changelist'), obj.agency.id, obj.agency.name)
    agency_link.allow_tags = True
    agency_link.short_description = u'агентство'

    def importadtasks_link(self, obj):
        return u'<a href="%s?importtask_id=%s">посмотреть</a>' % (reverse('admin:import__importadtask_changelist'), obj.id)
    importadtasks_link.allow_tags = True
    importadtasks_link.short_description = u'задачи импорта объявлений'


class ImportAdTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'importtask_link', 'status', 'created', 'started', 'completed')
    raw_id_fields = ('basead', 'importtask')
    list_filter = ('status',)

    def importtask_link(self, obj):
        return u'<a href="%s?id=%d">#%d</a>' % (reverse('admin:import__importtask_changelist'), obj.importtask_id, obj.importtask_id)
    importtask_link.allow_tags = True
    importtask_link.short_description = u'задача импорта'


admin.site.register(ImportTask, ImportTaskAdmin)
admin.site.register(ImportAdTask, ImportAdTaskAdmin)

