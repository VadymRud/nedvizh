from django.contrib import admin

from mail.models import Notification

class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'created', 'user', 'type', 'content_type', 'object_id')
    list_filter = ('type',)
    raw_id_fields = ('user',)

admin.site.register(Notification, NotificationAdmin)

