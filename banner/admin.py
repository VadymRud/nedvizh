# coding: utf-8
from django.contrib import admin
from banner.models import Banner
import datetime


class BannerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'url', 'place', 'order', 'is_active', 'display_clicks')
    list_editable = ('order', 'is_active', 'place')
    ordering = ( 'place', '-is_active', 'order')
    readonly_fields = ('link_clicks',)

    def display_clicks(self, obj):
        stats = {'total':0, 'day':0, 'week':0, 'month':0}
        for click in obj.clicks.all():
            stats['total'] += click.clicks
            if click.date > datetime.date.today() - datetime.timedelta(days=1):
                stats['day'] += click.clicks
            if click.date > datetime.date.today() - datetime.timedelta(days=7):
                stats['week'] += click.clicks
            if click.date > datetime.date.today() - datetime.timedelta(days=30):
                stats['month'] += click.clicks

        if stats['total']:
            return u'<abbr title="%(day)s / %(week)s / %(month)s" >%(total)s</abbr>' % stats
        else:
            return '—'
    display_clicks.short_description = u'переходы'
    display_clicks.allow_tags = True


admin.site.register(Banner, BannerAdmin)