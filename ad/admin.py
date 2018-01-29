# coding: utf-8
import datetime
from urlparse import urlparse

from django import forms
from django.conf.urls import url
from django.contrib import admin
from django.db.models import Count, Sum
from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.templatetags.static import static
from modeltranslation.admin import TranslationAdmin

from ad import admin_views
from ad.models import Ad, Region, Photo, Facility, Rules, Phone, PhoneInAd, SubwayLine, SubwayStation, Moderation, SearchCounter, DeactivationForSale
from ad.choices import MODERATION_STATUS_CHOICES, STATUS_CHOICES
from ad.forms import CalendarsWidget
from ad import filterspec as fs
from phones import pprint_phone, PhoneModelChoiceField
from profile.admin import get_user_filter_link
from mail.models import Notification
from admin_ext.filters import make_datetime_filter


def to_rentdaily_ad(modeladmin, request, queryset):
    queryset.update(deal_type='rent_daily')
to_rentdaily_ad.short_description = u"Перенести в посуточную аренду"


# закрываем заявку на модерацию и очищаем список полей, требующих проверки
def approve_ads(modeladmin, request, queryset, new_status=None):
    queryset.update(fields_for_moderation=None)

    now = datetime.datetime.now()
    update_fields = {'moderator': request.user, 'end_time': now}
    if new_status:
        update_fields['new_status'] = new_status

    for ad in queryset:
        updated_rows = ad.moderations.filter(moderator__isnull=True).update(**update_fields)
        if not updated_rows:
            Moderation.objects.create(basead=ad, start_time=now, end_time=now, moderator=request.user, new_status=new_status)

approve_ads.short_description = u'Подтвердить (снять отметку о модерации)'


def update_region(modeladmin, request, queryset):
    for ad in queryset:
        old_region = ad.region
        ad.process_address()
        if old_region != ad.region:
            ad.save()
update_region.short_description = u'Обновить присвоенный регион'


def reject_action_factory(short_description, status):
    def reject_action(modeladmin, request, queryset):
        # при статусе модерации >= 20 объявления не возвращаются на модерацию и соответственно к публикации
        if status >= 20:
            queryset.update(moderation_status=status, status=210, is_published=False)
        else:
            queryset.update(moderation_status=status, is_published=False)

        approve_ads(modeladmin, request, queryset, new_status=status)

        for user in set(ad.user for ad in queryset):
            if user:
                user.update_ads_count()

        for ad in queryset.filter(user__isnull=False):
            Notification(type='ad_rejected', user=ad.user, object=ad).save()

    reject_action.short_description = short_description
    reject_action.__name__ = 'reject_action_with_status_%d' % status
    return reject_action

ban_ad = reject_action_factory(u'Отклонить: бан-лист (для фидов)', 200)
wrong_ad_actions = []
for status in (10, 11, 12, 13, 14, 15, 16, 20, 22):
    short_description = u'Отклонить: %s' % dict(MODERATION_STATUS_CHOICES)[status]
    action = reject_action_factory(short_description, status)
    wrong_ad_actions.append(action)


def change_status_factory(short_description, status):
    def change_status(modeladmin, request, queryset):
        queryset.update(status=status)
        if status == 1:
            queryset.filter(moderation_status=None).update(is_published=True)
        else:
            queryset.update(is_published=False)
            
        for user in set(ad.user for ad in queryset):
            if user:
                user.update_ads_count()
    change_status.short_description = short_description
    change_status.__name__ = 'change_status_status_%d' % status
    return change_status

change_status_actions = []
for status in (1, 210, 211):
    short_description = u'Сменить статус: %s' % dict(STATUS_CHOICES)[status]
    change_status_actions.append(change_status_factory(short_description, status))


def set_phone_is_agency(modeladmin, request, queryset):
    queryset.update(is_agency=True)
set_phone_is_agency.short_description = u'Отметить выбранные телефоны как агентства'


class PhoneInAdForm(forms.ModelForm):
    # TODO: здесь нужно подключить новое форматирование номеров
    # class Media:
    #    js = form_media_js

    phone = PhoneModelChoiceField(label=u'Номер телефона', queryset=PhoneInAd.objects.none())

class PhoneInline(admin.TabularInline):
    form = PhoneInAdForm
    model = PhoneInAd
    max_num = 3

class PhotoInline(admin.TabularInline):
    model = Photo
    template = 'admin/tabular_image.html'
    fields = ['image', 'order']

class AdminCalendarsWidget(CalendarsWidget):
    def _media(self):
        return forms.Media(
            css={'all': ('css/calendars.css', 'libs/lionbars/lionbars.css')},
            js=('js/libs/jquery.json-2.3.min.js', 'libs/lionbars/jquery.lionbars.0.3.min.js', 'js/calendars_widget.js')
        )
    media = property(_media)

TAG_CHOICES = (
    ('mainpage', u'на главной'),
)
class AdAdminForm(forms.ModelForm):
    class Meta:
        model = Ad
        fields = '__all__'

    reserved = forms.CharField(widget=AdminCalendarsWidget(), required=False, label='Занятые дни')
    title = forms.CharField(label=u'Заголовок объявления', required=False, max_length=255)

    detail_views = forms.CharField(label=u'Просмотры', widget=forms.TextInput(attrs={'readonly':'readonly'}), required=False)
    contacts_views = forms.CharField(label=u'Просмотры контактов', widget=forms.TextInput(attrs={'readonly':'readonly'}), required=False)

    def clean_property_commercial_type(self):
        if self.cleaned_data['property_type'] != 'commercial' and self.cleaned_data['property_commercial_type'] is not None:
            raise forms.ValidationError('Типы коммерческой недвижимости указываются только для коммерческой недвижимости') 
        return self.cleaned_data['property_commercial_type']
    
    def __init__(self, *args, **kwargs):
        property = kwargs.get('instance', None)
        initial = kwargs.get('initial', {})
        if property:
            initial.update(property.reserved_json())
            aggregated_views = property.viewscounts.aggregate(
                detail_views=Sum('detail_views'),
                contacts_views=Sum('contacts_views'),
            )
            initial.update(aggregated_views)
            kwargs.update(initial=initial)
        else:
            kwargs.update(initial={'reserved': '{}', 'status': 0})
        super(AdAdminForm, self).__init__(*args, **kwargs)

    def clean_reserved(self):
        import json
        old_reservations = set(self.instance.reserved.values_list('date', flat=True))
        try:
            reservations = set([datetime.datetime.strptime(date, '%Y-%m-%d').date() for date in json.loads(self.cleaned_data['reserved'])])
        except ValueError:
            reservations = []

        if old_reservations != reservations:
            self.instance.modified_calendar = datetime.datetime.now()
            self.update_m2m_reservations = True

        return reservations

icon_website = u'<img src="%s" alt=""/>' % static('admin/img/icon-website.gif')


class AdAdmin(admin.ModelAdmin):
    form = AdAdminForm
    list_display = (
        'short_name', 'user_link', 'get_status_display', 'type', 'region_text', 'address', 'price_currency', 'add_date',
        'updated_date', 'item_images'
    )
    fieldsets = (
        (None, {
            'classes': ('wide_label',),
            'fields': (('user_info', 'bank'), ('status', 'moderation_status', 'vip_type'), ('deal_type', 'property_type', 'property_commercial_type'))
        }),
        (u'Основные параметры', {
            'fields': ('title', 'address',
                       ('addr_city', 'addr_street', 'addr_house', 'addr_country'),
                       ('rooms', 'area', 'area_living', 'area_kitchen'),
                       'description', ('price', 'currency'), 'iframe_url')
        }),
        (u'Дополнительные параметры', {
            'fields': (
                        ('floor', 'floors_total'),
                        ('building_layout', 'building_type', 'building_type_other'),
                        ('building_walls', 'building_windows', 'building_heating'),
                        'guests_limit',)
        }),
        (u'Прочее', {
            'classes': ('collapse',),
            'fields': (('created', 'modified'), ('updated',  'expired'), ('reserved', 'modified_calendar'), ('price_period', 'space_units'),
                'facilities', 'contact_person', ('detail_views', 'contacts_views'), ('coords_x', 'coords_y', 'geo_source'),
            )
        }),
    )
    readonly_fields = ('title', 'contact_person', 'updated', 'expired', 'user_info', 'address', 'modified',
                       'modified_calendar')
    list_filter = (
        fs.PropertyById, fs.M2MPhoneFilter, make_datetime_filter('created'), make_datetime_filter('updated'), fs.PropertyWithModeration, fs.PropertyBySource,
        fs.PropertyByContentProvider, 'status', 'moderation_status', 'vip_type', fs.CityRegionFilter, fs.ProvinceRegionFilter,
        'deal_type', 'property_type'
    )
    filter_horizontal = ['facilities', 'rules']
    exclude = ['image', 'region', 'price_uah', 'xml_id']
    search_fields = ['id']
    show_full_result_count = False
    #  date_hierarchy = 'created'
    actions = [update_region, approve_ads, to_rentdaily_ad] + change_status_actions + wrong_ad_actions + [ban_ad]
    inlines = [
        PhoneInline,
        PhotoInline,
    ]

    # custom field in fieldsets
    def user_info(self, obj):
        if obj.user:
            return u'ID %d (%s)' % (obj.user_id, obj.user.email or u'нет e-mail')
    user_info.short_description = u'пользователь'

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = self.readonly_fields

        if not request.user.has_perm("%s.%s_%s" % ( 'ad', 'change', 'moderation')):
            readonly_fields = readonly_fields + ('status', 'moderation_status')

        if not request.user.has_perm("%s.%s_%s" % ( 'bank', 'change', 'bank')):
            readonly_fields = readonly_fields + ('vip_type', )

        if not request.user.is_superuser:
            readonly_fields = readonly_fields + ('addr_country',)

        # шиш вам
        if request.user.groups.filter(name__icontains=u'комитет').exists():
            return list(set(
                list(readonly_fields) + ['facilities'] +
                [field.name for field in self.opts.local_fields] +
                [field.name for field in self.opts.local_many_to_many]
            ))

        return readonly_fields

    def get_actions(self, request):
        actions = super(AdAdmin, self).get_actions(request)
        if not request.user.has_perm("%s.%s_%s" % ( 'ad', 'change', 'moderation')):
            return []
        return actions

    @property
    def media(self):
        return super(AdAdmin, self).media + forms.Media(js=['js/libs/jquery-last.min.js', 'js/admin_changeform.js', ])

    def get_queryset(self, request):
        qs = super(AdAdmin, self).get_queryset(request)
        return qs.select_related('region').prefetch_related('photos', 'bank', 'user', 'moderations',
                                                            'catalogplacements', 'user__user_plans', 'user__activityperiods',
                                                            'user__realtors__agency', 'user__leadgeneration')

    def get_status_display(self, obj):
        if not obj.moderation_status:
            status = obj.get_status_display()

            if obj.status == 1:
                for deactivation in obj.deactivations.all():
                    if not deactivation.returning_time:
                        status = u'<a href="%s?basead=%d">продано</a>' % (reverse('admin:ad_deactivationforsale_changelist'), obj.id)
                        break

            if obj.user:
                for placement in obj.catalogplacements.all():
                    if placement.until > datetime.datetime.now():
                        status += u'&nbsp;<a href="{}?basead={}" title="размещение в зарубежном каталоге"><img src="{}" style="background-color:{}"/></a> '.format(
                                    reverse('admin:paid_services_catalogplacement_changelist'), obj.id,
                                    static('admin/img/icon-dollar.png'), '#6c6874')

                if obj.addr_country == 'UA':
                    active_plan = obj.user.get_active_plan_using_prefetch()
                    if active_plan:
                        status += u'&nbsp;<a href="{}?id={}" title="{}"><img src="{}" style="background-color:{}"/></a> '.format(
                                    reverse('admin:paid_services_userplan_changelist'), active_plan.id,
                                    u'Тариф до {:%d.%m.%Y}. Лимит объявлений - {}'.format(active_plan.end, active_plan.ads_limit),
                                    static('admin/img/icon-dollar.png'), '#ecb310')

                    if obj.user.has_active_leadgeneration('ads'):
                        status += u'&nbsp;<a href="{}?id={}" title="лидогенерация"><img src="{}" style="background-color:{}"/></a> '.format(
                                    reverse('admin:ppc_leadgeneration_changelist'), obj.user.leadgeneration.id,
                                    static('admin/img/icon-dollar.png'), '#31c500')
            return status
        else:
            status = obj.get_moderation_status_display()
            return '<b class="red">%s</b>' % status[:18] + '..' if len(status) > 18 else status
    get_status_display.allow_tags = True
    get_status_display.short_description = u"статус"
    get_status_display.admin_order_field = 'status'

    def region_text(self, obj):
        if obj.region is None:
            return u'(без региона)'
        else:
            return u'<a href="?region__id__exact=%d" title="все объявления региона \'%s\'">%s</a>' % (obj.region.pk, obj.region.text, obj.region)
    region_text.allow_tags = True
    region_text.short_description = u"присв.\nрегион"
    region_text.admin_order_field = 'region'

    def short_name(self, obj):
        name = obj.title
        if obj.xml_id: name += " (#%s)" % obj.xml_id
        if len(name) > 25: name = "<span title='%s'>%s...</span>" % (name, name[:25])
        if obj.fields_for_moderation:
            active_moderations = filter(lambda moderation: not moderation.moderator_id, obj.moderations.all())
            if active_moderations:
                name += u'&nbsp;<a href="%s"><img src="%s" title="Модерация: %s"/></a>' % \
                        (reverse('moderation_detail', args=[active_moderations[0].id]), static('admin/img/icon-moderate.gif'),
                         obj.fields_for_moderation.replace("__all__", u"Новое"))
        return name
    short_name.allow_tags = True
    short_name.short_description = u"объявление"
    short_name.admin_order_field = 'title'
    
    def price_currency(self, obj):
        if obj.currency != 'UAH':
            return u'<acronym title="%s грн.">%s %s</acronym>' % (obj.price_uah, obj.price, obj.get_currency_display())
        else:
            return u'%s %s' % (obj.price, obj.get_currency_display())
    price_currency.allow_tags = True
    price_currency.short_description = u"Цена"
    price_currency.admin_order_field = 'price_uah'
    
    def add_date(self, obj):
        return obj.created.strftime('%d.%m.%y %H:%M')
    add_date.short_description = u"Добавлено"
    add_date.admin_order_field = 'created'

    def updated_date(self, obj):
        return obj.updated.strftime('%d.%m.%y %H:%M')
    updated_date.short_description = u"Обновлено"
    updated_date.admin_order_field = 'updated'

    def type(self,obj):
        return u'%s, %s' % (obj.get_deal_type_display(), obj.get_property_type_display())
    type.short_description = u"Тип"
    type.admin_order_field = 'deal_type'
    
    def user_link(self, obj):
        if obj.user:
            html = get_user_filter_link(obj.user)
            if obj.bank:
                url = reverse('admin:ad_ad_changelist') + '?bank_id=%d' % obj.bank_id
                html += u'<br/>банк: <a href="%s">%s</a>' % (url, obj.bank.name)
            return html
        else:
            if obj.source_url:
                o = urlparse(obj.source_url)
                return u'<nobr><a href="?source_url__icontains=%s" title="фильтровать по адресу сайта">%s %s</a></nobr>' % (o.netloc, icon_website, o.netloc)
            elif obj.content_provider:
                return obj.get_content_provider_display()

    user_link.allow_tags = True
    user_link.short_description = u"Источник/Юзер"
    user_link.admin_order_field = 'source_url'
    
    def item_images(self, obj):
        image_count = obj.photos.all().count()
        return u'<a href="%s?basead__exact=%d">%s шт.</a>' % (reverse('admin:ad_photo_changelist'), obj.pk, image_count)
    item_images.allow_tags = True
    item_images.short_description = u"Фото"

    def save_model(self, request, obj, form, change):
        if request.user.has_perm("%s.%s_%s" % ( 'ad', 'change', 'moderation')):
            # после сохранения в админке очищаются поля, требующие модерации
            obj.fields_for_moderation = None

            # ..., а так же закрываются заявки на модерацию
            update_fields = {'moderator':request.user, 'end_time':datetime.datetime.now()}
            if 'status' in obj.get_dirty_fields():
                update_fields['new_status'] = obj.status
            obj.moderations.filter(moderator__isnull=True).update(**update_fields)

        if obj.id is None and obj.user is None:
            obj.user = request.user

        super(AdAdmin, self).save_model(request, obj, form, change)

        if request.user.has_perm('ad.change_reserveddate') and getattr(form, 'update_m2m_reservations', False):
            obj.update_reserved_from_json(form.cleaned_data['reserved'])

    def get_urls(self):
        urls = super(AdAdmin, self).get_urls()
        return [
                   url(r'^stats_by_propertytype/$', admin_views.stats_by_propertytype),
                   url(r'^feed_sources/$', admin_views.feed_sources),
                   url(r'^duplicates/$', admin_views.show_photo_duplicates),
               ] + urls


class PropertyRegionAdmin(TranslationAdmin):
    list_display = ('__unicode__', 'id', 'text', 'kind', 'static_url', 'coords_x', 'coords_y')
    list_filter = ['kind', 'subdomain']
    filter_horizontal = ['groupped']
    search_fields = ['name', 'slug', 'static_url']
    raw_id_fields = ('parent',)
    show_full_result_count = False

    fieldsets = (
        (None, {
            'classes': ('wide_label',),
            'fields': ('kind', 'parent', ('name', 'name_declension'), 'text', ('slug', 'subdomain'), 'static_url', 'price_level', 'plan_discount')
        }),
        # (u'Для группы регионов', {
        #     'classes': ('collapse',),
        #     'fields': ('groupped', )
        # }),
        (u'Google.Analytics и технические данные', {
            'classes': ('collapse',),
            'fields': ('analytics',  'coords_x', 'coords_y', 'bounded_by_coords')
        }),
    )


class PhotoAdmin(admin.ModelAdmin):
    list_display = ['id', 'display_user', 'display_basead', 'source_url', 'display_hash', 'show_image']
    raw_id_fields = ('basead',)
    readonly_fields = ('source_url', 'image', 'basead')
    show_full_result_count = False
    ordering = ['-id']

    def get_queryset(self, request):
        qs = super(PhotoAdmin, self).get_queryset(request)
        return qs.prefetch_related('basead__ad__user')

    def show_image(self, obj):
        if obj.image:
            return u'<a href="%s" target="_blank"><img src="%s" height="100"/></a>' % (obj.image.url, obj.smart_thumbnail('md'))
        else:
            return u'(нет файла изображения)'
    show_image.short_description = u"Фотография"
    show_image.allow_tags = True

    def display_user(self, obj):
        if obj.basead and obj.basead.ad and obj.basead.ad.user:
            return u'<a href="%s?id=%s">%s</a>' % (reverse('admin:custom_user_user_changelist'), obj.basead.ad.user_id, obj.basead.ad.user)
    display_user.short_description = u"Пользователь"
    display_user.allow_tags = True

    def display_basead(self, obj):
        if obj.basead and obj.basead.ad:
            return u'<a href="%s?id=%s">%s</a>' % (reverse('admin:ad_ad_changelist'), obj.basead_id, obj.basead.ad)
    display_basead.short_description = u"Объявление"
    display_basead.allow_tags = True

    def display_hash(self, obj):
        if obj.hash:
            similar_photo = Photo.objects.filter(hash=obj.hash).count()
            if similar_photo > 1:
                return u'<a href="?hash=%s">%s шт</a>' % (obj.hash, similar_photo)

        return u''
    display_hash.short_description = u"Похожие фото"
    display_hash.allow_tags = True

    
class FacilityAdmin(TranslationAdmin):
    list_display = ['name']

class RulesAdmin(TranslationAdmin):
    list_display = ['name']

class PhoneAdmin(admin.ModelAdmin):
    list_display = ('number_pprint', 'is_agency', 'is_banned')
    list_filter = ('is_agency', 'is_banned', fs.PhoneNumberFilter, fs.PhoneByCity)
    ordering = ('number',)
    readonly_fields = ('number',)
    actions = (set_phone_is_agency,)
    show_full_result_count = False
    
    def number_pprint(self, obj):
        return pprint_phone(obj.number)
    number_pprint.admin_order_field = 'number'
    number_pprint.short_description = u'Номер телефона'

class SubwayStationInline(admin.StackedInline):
    model = SubwayStation
    extra = 0
    exclude = ['name']


class SubwayLineAdmin(admin.ModelAdmin):
    list_display = ['name_ru', 'order']
    list_editable = ['order']
    inlines = [SubwayStationInline]
    exclude = ['name']
    raw_id_fields = ['city']


class SearchCounterAdmin(admin.ModelAdmin):
    raw_id_fields = ['region']
    list_display = [
        'date', 'deal_type', 'property_type', 'rooms', 'region', 'price_from', 'price_to', 'currency',
        'area_from', 'area_to', 'facilities', 'without_commission', 'other_parameters',
        'searches_first_page', 'searches_all_pages'
    ]
    list_filter = (
        make_datetime_filter('date'), 'deal_type', 'property_type', fs.RoomsFilter, 'without_commission',
        'currency', fs.PriceFromFilter, fs.PriceToFilter, fs.AreaFromFilter, fs.AreaToFilter,
        fs.FacilitiesFilter, fs.ProvinceRegionFilter, fs.CityRegionFilter, fs.DistrictFilter,
    )


class DeactivationForSaleAdmin(admin.ModelAdmin):
    raw_id_fields = ['user', 'basead']
    list_display = ['id', 'display_ad', 'display_ad_is_published', 'user', 'reason', 'deactivation_time', 'returning_time']
    list_filter = ('returning_time', 'reason')
    date_hierarchy = 'deactivation_time'

    def display_ad(self, obj):
        if obj.basead:
            return '<a href="%s">%s</a>' % (obj.basead.ad.get_absolute_url(), obj.basead)
    display_ad.admin_order_field = 'basead'
    display_ad.short_description = u'Объявление'
    display_ad.allow_tags = True

    def display_ad_is_published(self, obj):
        if obj.basead:
            return obj.basead.ad.is_published
    display_ad_is_published.admin_order_field = 'basead'
    display_ad_is_published.short_description = u'Опубликовано'
    display_ad_is_published.boolean = True

    def get_queryset(self, request):
        qs = super(DeactivationForSaleAdmin, self).get_queryset(request)
        return qs.select_related('basead__ad').prefetch_related('basead__ad__region', 'user')


admin.site.register(Ad, AdAdmin)
admin.site.register(Region, PropertyRegionAdmin)
admin.site.register(Photo, PhotoAdmin)
admin.site.register(Facility, FacilityAdmin)
admin.site.register(Rules, RulesAdmin)
admin.site.register(Phone, PhoneAdmin)
admin.site.register(SubwayLine, SubwayLineAdmin)
admin.site.register(SearchCounter, SearchCounterAdmin)
admin.site.register(DeactivationForSale, DeactivationForSaleAdmin)

