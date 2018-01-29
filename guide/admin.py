# coding: utf-8
import string

from django.contrib import admin
from django import forms
from guide.models import Video, Photo, Cinema, Taxi, Restaurant, Shop, WorkingHours
from ad.models import Region
from utils.thumbnail import get_lazy_thumbnail
from ckeditor.widgets import CKEditorWidget


class SubdomainFilter(admin.SimpleListFilter):
    title = u'по поддомену'
    parameter_name = 'subdomain'
    template = 'admin/filter_select.html'

    def lookups(self, request, model_admin):
        values = [(region.id, region.name) for region in Region.objects.filter(subdomain=True).order_by('name')]
        return values
        
    def queryset(self, request, queryset):
        if self.value(): 
            return queryset.filter(subdomain=Region.objects.get(id=self.value()))

class VideoAdmin(admin.ModelAdmin):
    list_display = ('name','youtube_id','views_count', 'preview')
    search_fields = ('name', 'youtube_id')
    exclude = ('image',)
    readonly_fields = ('views_count',)

    def preview(self, obj):
        return u'<a href="%s" target="_blank"><img src="%s" height="100"/></a>' % (obj.image.url, obj.image.url)
    preview.short_description = u'изображение'
    preview.allow_tags = True

def get_subdomain_admin_form(model_class):
    class AdminForm(forms.ModelForm):
        subdomain = forms.ModelChoiceField(label=u'Город (поддомен)', queryset=Region.objects.filter(subdomain=True))
        class Meta:
            model = model_class
            fields = '__all__'
    return AdminForm

class PhotoAdmin(admin.ModelAdmin):
    form = get_subdomain_admin_form(Photo)
    list_display = ('id', 'preview', 'subdomain', 'description')
    readonly_fields = ('likes',)
    list_filter = (SubdomainFilter,)

    def preview(self, obj):
        url = get_lazy_thumbnail(obj.image, '200x200')
        if url:
            return u'<a href="%s" target="_blank"><img src="%s" height="100"/></a>' % (obj.image.url, url)
        else:
            return u'нет изображения'

    preview.short_description = u'превью'
    preview.allow_tags = True

class CinemaAdmin(admin.ModelAdmin):
    form = get_subdomain_admin_form(Cinema)
    list_display = ('name', 'subdomain')
    search_fields = ('name',)
    list_filter = (SubdomainFilter,)

class TaxiAdminForm(forms.ModelForm):
    subdomain = forms.ModelChoiceField(label=u'Город (поддомен)', queryset=Region.objects.filter(subdomain=True))
    description = forms.CharField(widget=CKEditorWidget(), label='описание', required=False)

    class Meta:
        model = Taxi
        fields = '__all__'

class TaxiAdmin(admin.ModelAdmin):
    form = TaxiAdminForm
    list_display = ('name', 'subdomain')
    search_fields = ('name',)
    readonly_fields = ('likes',)
    list_filter = (SubdomainFilter,)

class PlaceAdmin(admin.ModelAdmin):
    readonly_fields = ('region', 'coords_x', 'coords_y', 'likes')
    search_fields = ('region__name', 'name')

    def admin_region(self, obj):
        if obj.region:
            return u'<a href="?region__id__exact=%d" title="%s">%s</a>' % (obj.region.pk, obj.region.text, obj.region)
        else:
            return u'нет региона'
    admin_region.allow_tags = True
    admin_region.short_description = u"присв.\nрегион"
    admin_region.admin_order_field = 'region'

class RestaurantAdminForm(forms.ModelForm):
    description = forms.CharField(widget=CKEditorWidget(), label='описание', required=False)

    class Meta:
        model = Restaurant
        fields = '__all__'

class RestaurantAdmin(PlaceAdmin):
    form = RestaurantAdminForm
    list_display = ('name', 'admin_types', 'admin_cookeries', 'address', 'admin_region')
    list_filter = ('types', 'cookeries')
    filter_horizontal = ('types', 'cookeries')

    def admin_types(self, obj):
        return string.join(obj.types.values_list('name', flat=True), ', ')
    admin_types.short_description = u'типы'

    def admin_cookeries(self, obj):
        return string.join(obj.cookeries.values_list('name', flat=True), ', ')
    admin_cookeries.short_description = u'кухни'

class WorkingHoursAdminForm(forms.ModelForm):
    class Meta:
        model = WorkingHours
        fields = '__all__'

    def clean(self):
        def get_seconds(time):
            return time.hour * 3600 + time.minute * 60 + time.second
        if get_seconds(self.cleaned_data['close']) - get_seconds(self.cleaned_data['open']) <= 0:
            self._errors['close'] = self._errors['open'] = self.error_class([u'время закрытия должно быть больше времени открытия'])
            del self.cleaned_data['close']
            del self.cleaned_data['open']

        return self.cleaned_data

class WorkingHoursInline(admin.TabularInline):
    model = WorkingHours
    form = WorkingHoursAdminForm

class ShopAdmin(PlaceAdmin):
    list_display = ('name', 'type', 'address', 'admin_region')
    list_filter = ('type',)
    inlines = (WorkingHoursInline,)

admin.site.register(Video, VideoAdmin)
admin.site.register(Photo, PhotoAdmin)
admin.site.register(Cinema, CinemaAdmin)
admin.site.register(Taxi, TaxiAdmin)
admin.site.register(Restaurant, RestaurantAdmin)
admin.site.register(Shop, ShopAdmin)

