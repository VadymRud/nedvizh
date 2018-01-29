# coding=utf-8

from django.contrib import admin
from django.core.urlresolvers import reverse
from django.conf.urls import url
from django.db.models import Count
from django.http import HttpResponse

from bank.models import Bank
from ad.models import Ad

from collections import defaultdict, Counter

class BankAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_active', 'ads_count')

    def changelist_view(self, request, extra_context=None):
        self.groupped_ads_count = defaultdict(Counter)
        query = Ad.objects.filter(bank__isnull=False).values_list('bank_id', 'status').order_by().annotate(Count('bank_id'), Count('status'))
        for bank_id, status, count, count in query:
            if status == 1:
                self.groupped_ads_count[bank_id]['published'] += count
            self.groupped_ads_count[bank_id]['total'] += count
        return super(BankAdmin, self).changelist_view(request, extra_context=None)

    def ads_count(self, obj):
        published = self.groupped_ads_count[obj.id]['published']
        total = self.groupped_ads_count[obj.id]['total']
        url = reverse('admin:ad_ad_changelist') + ('?bank_id=%d' % obj.id)
        return u'активных - %d, всего - <a href="%s">%d</a>' % (published, url, total)
    ads_count.allow_tags = True
    ads_count.short_description = u'Объявления'

    def get_urls(self):
        urls = super(BankAdmin, self).get_urls()
        my_urls = [
            url(r'^ids/(?P<bank_id>[0-9]*)/$', self.ids),
            url(r'^ids/(?P<bank_id>[0-9]*)/(?P<deal_type>sale|rent|rent_daily)/$', self.ids),
        ]
        return my_urls + urls

    def ids(self, request, bank_id, deal_type=None):
        ads = Ad.objects.filter(bank_id=bank_id, is_published=True)
        if deal_type:
            ads = ads.filter(deal_type=deal_type)
        if 'q' in request.GET:
            ads = ads.filter(description__icontains=request.GET['q'])
        response = '\n'.join(map(str, ads.values_list('id', flat=True)))
        return HttpResponse(response , content_type='text/plain')

admin.site.register(Bank, BankAdmin)

