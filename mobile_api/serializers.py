# coding=utf-8
import math
from django.db.models import Prefetch, Q, Count, Max, F
from django.templatetags.static import static
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.utils.http import urlquote_plus
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance
from django.conf import settings

from bs4 import BeautifulSoup
from rest_framework import viewsets, serializers, filters
from rest_framework.decorators import detail_route
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, BasePermission, SAFE_METHODS
from rest_framework.viewsets import mixins, GenericViewSet
import django_filters
from ad.models import Ad, BaseAd, Region, Photo, make_sphere_distance_filters, make_coords_ranges_filters
from ad.forms import create_ad_phones_formset
from agency.models import Agency, Lead, Task, LeadHistoryEvent
from custom_user.models import User
from profile.models import SavedSearch, SavedAd, Message
from paid_services.models import VipPlacement, TRANSACTION_TYPE_CHOICES, AzureMLEntry
from ppc.models import Call, CallRequest
from utils.thumbnail import get_lazy_thumbnail
from utils.currency import get_currency_rates

'''
Permission
'''
class IsOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        if type(obj) in [Ad, Agency]:
            return request.user == obj.user
        elif type(obj) == Photo:
            return request.user == obj.basead.ad.user


class UserPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        return (
            request.method in SAFE_METHODS or
            request.user == obj or
            request.user.has_perm('custom_user.change_user')
        )


class IsAgencyAdminOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        return obj.realtors.filter(user=request.user, is_admin=True).count()

'''
Paginators
'''

class MobileApiPaginator(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 1000

class PropertyOnMapPagination(MobileApiPaginator):
    page_size  = 1000
    max_page_size  = 10000

class MessagePagination(MobileApiPaginator):
    page_size = 100

class TaskPagination(MobileApiPaginator):
    page_size = 1000

class LeadPagination(MobileApiPaginator):
    page_size = 500

class LeadHistoryPagination(MobileApiPaginator):
    page_size = 100




'''
JSON Renderer
'''
class CustomJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        if renderer_context['request'].user.is_authenticated():
            data['saved_properties_ids'] = set(SavedAd.objects.filter(user=renderer_context['request'].user).values_list('basead_id', flat=True))
        return super(CustomJSONRenderer, self).render(data, accepted_media_type, renderer_context)


class MessageJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        user = renderer_context['request'].user
        realtor = user.realtors.first()
        params = renderer_context['request'].GET

        # запрашивается список диалогов
        if 'dialogs' in params:

            # количество непрочитанных сообщений
            dialogs_ids = [message['root_message'] for message in data['results']]
            unreaded_message = dict(Message.objects.filter(root_message__in=dialogs_ids, to_user=user, readed=False).exclude(from_user=user)\
                .values('root_message').annotate(count=Count('root_message')).values_list('root_message', 'count'))

            # лиды пользователей
            companions_ids = [message['companion']['id'] for message in data['results']]
            leads = {lead.user_id: {'id': lead.pk, 'name': unicode(lead), 'label': lead.label, 'label_display': lead.get_label_display()}
                     for lead in user.leads.filter(client__in=companions_ids)}

            for message in data['results']:
                message['unreaded'] = unreaded_message.get(message['root_message'], 0)
                message['lead'] = leads.get(message['companion']['id'])

        if 'root_message' in params and 'results' in data:

            # меняем ссылки из рассылки на редиректы
            for message in data['results']:
                if message['is_promo']:
                    message['text'] = BeautifulSoup(message['text'], 'html.parser')
                    for link in message['text'].find_all('a'):
                        url = link.get('href')
                        if url and 'mailto:' not in url:
                            link['href'] = '%s?url=%s' % (reverse('messages:redirect', kwargs={'message_id':message['id']}),
                                                          urlquote_plus(url))
                    message['text'] = unicode(message['text'])

            # выставляем отметки о прочтении сообщений
            if any(not msg['readed'] for msg in data['results']):
                Message.objects.filter(root_message=params['root_message'], to_user=user).update(readed=True)
                cache.delete('new_messages_for_user%d' % user.id)

            data['unreaded'] = user.get_unread_messages()

            # поиск лида, либо его создание
            message = data['results'][-1] if data['results'] else None
            if message and message['companion']['id']:
                lead = user.find_lead(client=message['companion']['id'])
                if not lead:
                    client = User.objects.get(pk=message['companion']['id'])
                    lead = Lead.objects.create(user=user, client=client, basead_id=message['basead'], name=user.get_public_name())

                data['lead'] = LeadSerializer(instance=lead).data

        return super(MessageJSONRenderer, self).render(data, accepted_media_type, renderer_context)

'''
Filters
'''
class RegionFilter(django_filters.FilterSet):
    parent = django_filters.NumberFilter()

    class Meta:
        model = Region
        fields = ('kind', 'subdomain', 'parent')


class PropertyFilter(django_filters.FilterSet):
    user = django_filters.NumberFilter()
    min_guests_limit = django_filters.NumberFilter(name='guests_limit', lookup_type='gte')
    max_guests_limit = django_filters.NumberFilter(name='guests_limit', lookup_type='lte')
    min_rooms = django_filters.NumberFilter(name='rooms', lookup_type='gte')
    max_rooms = django_filters.NumberFilter(name='rooms', lookup_type='lte')

    min_updated = django_filters.DateTimeFilter(name='updated', lookup_type='gte')
    max_updated = django_filters.DateTimeFilter(name='updated', lookup_type='lte')

    with_image = django_filters.MethodFilter(action="filter_with_image")
    without_commission = django_filters.MethodFilter(action='filter_without_commission')

    vip = django_filters.MethodFilter(action='filter_vip')

    def filter_with_image(self, qs, value):
        if value:
            qs = qs.filter(has_photos=True)
        return qs

    def filter_without_commission(self, qs, value):
        if value:
            qs = qs.filter(without_commission=True)
        return qs

    def filter_vip(self, qs, value):
        # имитация дефолтного фильтра по старому булевому полю vip (почему-то для булевых полей используются 2 и 3, а не, например, 0 и 1)
        if int(value) == 2:
            qs = qs.filter(vip_type__gt=0)
        elif int(value) == 3:
            qs = qs.filter(vip_type=0)
        return qs

    class Meta:
        model = Ad
        fields = [
            'id', 'user', 'rooms',  'area', 'deal_type', 'property_type', 'expired', 'updated', 'guests_limit',
            'status', 'vip_type'
        ]
        order_by = ['-pk']

'''
Serializers
'''
class RegionSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Region
        fields = ('id', 'url', 'kind', 'name', 'name_declension', 'parent', 'province_str', 'text', 'slug', 'static_url', 'subdomain', 'coords_x', 'coords_y', )

    coords_x = serializers.SerializerMethodField()
    coords_y = serializers.SerializerMethodField()
    province_str = serializers.SerializerMethodField()

    def get_coords_x(self, obj):
        coords = obj.get_coords()
        if coords:
            return coords[0]

    def get_coords_y(self, obj):
        coords = obj.get_coords()
        if coords:
            return coords[1]

    def get_province_str(self, obj):
        provinces = obj.get_parents(kind='province')
        if provinces:
            return provinces[0].name


class AgencySerializer(serializers.HyperlinkedModelSerializer):
    city = RegionSerializer()

    class Meta:
        model = Agency
        fields = ('id', 'url', 'name', 'city', 'address', 'description', 'site')


class UserSerializer(serializers.HyperlinkedModelSerializer):
    # groups = serializers.StringRelatedField(many=True, read_only=True)
    # social_auth = serializers.StringRelatedField(many=True, read_only=True)
    agencies = AgencySerializer(many=True, read_only=True)
    manager = serializers.StringRelatedField()
    saved_properties__properties_ids = serializers.SerializerMethodField()
    mobile_edit_permission = serializers.SerializerMethodField()
    extra_info = serializers.SerializerMethodField()
    phones = serializers.StringRelatedField(many=True, read_only=True)
    azureml_probabilities = serializers.SerializerMethodField()
    is_agency_owner = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('url', 'id','username', 'email', 'first_name', 'last_name', 'phones', 'image', 'is_staff', 'manager',
                  'agencies', 'mobile_edit_permission', 'extra_info', 'date_joined', 'saved_searches', 'saved_ads',  'saved_properties__properties_ids',
                  'azureml_probabilities', 'is_agency_owner', 'spcrm_category')
        read_only_fields = ('saved_searches', 'saved_ads', 'is_staff' )

    def get_is_agency_owner(self, obj):
        return bool(obj.get_realtor_admin())

    def get_azureml_probabilities(self, obj):
        entry = AzureMLEntry.objects.filter(transaction__user=obj).last()
        if entry:
            return entry.scored_probabilities

    def get_saved_properties__properties_ids(self, obj):
        return [saved.basead_id for  saved in obj.saved_ads.all()]

    def get_mobile_edit_permission(self, obj):
        return obj.is_staff or obj.email in ['kostyuk_yuliya_90@mail.ru', 'gudz.vladimir@gmail.com', 'sergey@mesto.ua',
                                             'ivo@17.lv', 'ivo@mesto.ua', 'ksenya.kisil@gmail.com', 'lily.081286@gmail.com']

    def get_usertype(self, obj):
        return 2 if self.get_mobile_edit_permission(obj) else 1 # временная заглушка для совместимости с приложением

    def get_extra_info(self, obj):
        extra_info = {
            'last_5_transactions': obj.transactions.order_by('-time')[:5].values('time', 'type', 'amount', 'note'),
            'last_plan': obj.user_plans.order_by('-start').values('start', 'end', 'is_active', 'plan','plan__name_ru', 'ads_limit', 'region__name')[:5],
            'active_ppc': obj.activityperiods.filter(end=None).values('lead_type', 'start', 'user__leadgeneration__ads_limit'),
            'last_5_vips': VipPlacement.objects.filter(basead__ad__user=obj).order_by('-since').values('basead', 'basead__ad__address', 'since', 'until', 'is_active')[:5],
        }
        if extra_info['active_ppc']:
            extra_info['balance'] = obj.get_balance()
        for transaction in extra_info['last_5_transactions']:
            transaction['type_str'] = dict(TRANSACTION_TYPE_CHOICES)[transaction['type']]

        return extra_info


class SavedPropertySerializer(serializers.HyperlinkedModelSerializer):
    user = serializers.ReadOnlyField(source='user_id')
    property = serializers.IntegerField(source='basead_id')
    property_detail = serializers.HyperlinkedRelatedField(source='basead', view_name='ad-detail', read_only=True)

    class Meta:
        model = SavedAd
        fields = ('user', 'property', 'property_detail', 'url')

    def update(self, instance, validated_data):
        instance.basead = validated_data.get('property', instance.basead)
        instance.save()
        return instance

class SavedSearchSerializer(serializers.HyperlinkedModelSerializer):
    user = serializers.ReadOnlyField(source='user_id')
    region = serializers.IntegerField(source='region_id')

    class Meta:
        model = SavedSearch

    def create(self, validated_data):
        return SavedSearch.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.region_id = validated_data.get('region_id', instance.region_id)
        instance.property_type = validated_data.get('property_type', instance.property_type)
        instance.query = validated_data.get('query', instance.query)
        instance.save()
        return instance

class PropertySerializer(serializers.HyperlinkedModelSerializer):
    phones = serializers.StringRelatedField(many=True, read_only=True)
    facilities = serializers.SlugRelatedField(many=True, slug_field='name', read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(source='user', read_only=True)
    region = serializers.PrimaryKeyRelatedField(read_only=True)
    # region_id = serializers.PrimaryKeyRelatedField(source='region')
    status_str = serializers.CharField(source='get_status_display', read_only=True)
    website_url = serializers.ReadOnlyField(source='get_absolute_url')

    images = serializers.SerializerMethodField()
    usercard = serializers.SerializerMethodField()
    region_str = serializers.SerializerMethodField()
    coords_x = serializers.SerializerMethodField()
    coords_y = serializers.SerializerMethodField()

    def get_usercard(self, obj):
        usercard = obj.prepare_usercard(host_name=None)
        if 'profile_image' in usercard:
            del usercard['profile_image']
        return usercard

    def get_region_str(self, obj):
        return obj.region.text if obj.region_id else None

    def get_images(self, obj):
        images = []
        for image in obj.photos.all():
            if image.image:
                url = image.smart_thumbnail('lg')
                images.append({'id': image.id, 'caption': image.caption, 'url': url})
        return images

    class Meta:
        model = Ad
        fields = (
            'id', 'website_url',  'url', 'title', 'address', 'addr_city', 'addr_street', 'addr_house',
            'rooms', 'guests_limit', 'area', 'floor', 'floors_total', 
            'user_id', 'usercard', 'phones', 'contact_person', 'status', 'status_str',  # 'phones',
            'deal_type', 'property_type',
            'region', 'region_str', 'coords_x', 'coords_y', # 'region_id',
            'images',
            'building_type', 'building_layout', 'building_walls', 'building_windows', 'building_heating',
            'description', 'price', 'currency', 'price_uah',
            'expired', 'updated',
            'facilities',
        )
        read_only_fields = ('title', 'address', 'status', 'expired', 'updated', 'price_uah', 'coords_x', 'coords_y',)

    def get_coords_x(self, obj):
        coords = obj.get_coords()
        if coords:
            return coords[0]

    def get_coords_y(self, obj):
        coords = obj.get_coords()
        if coords:
            return coords[1]

class PropertyOnMapSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Ad
        fields = ( 'id', 'coords_x', 'coords_y', )

    coords_x = serializers.SerializerMethodField()
    coords_y = serializers.SerializerMethodField()

    def get_coords_x(self, obj):
        coords = obj.get_coords()
        if coords:
            return coords[0]

    def get_coords_y(self, obj):
        coords = obj.get_coords()
        if coords:
            return coords[1]


class PhotoSerializer(serializers.HyperlinkedModelSerializer):
    property = serializers.IntegerField(source='basead_id')
    image = serializers.FileField(validators=[])
    image_url = serializers.SerializerMethodField('get_image')

    def get_image(self, obj):
        return obj.smart_thumbnail('lg')

    class Meta:
        model = Photo
        fields = ('id', 'url', 'property', 'image', 'caption', 'image_url')


class MessageSerializer(serializers.ModelSerializer):
    # basead = serializers.PrimaryKeyRelatedField(read_only=True)
    basead = serializers.IntegerField(source='basead_id', required=False)
    is_promo = serializers.SerializerMethodField()
    companion = serializers.SerializerMethodField()
    folder = serializers.SerializerMethodField()

    def get_companion(self, obj):
        if obj.message_list:
            return {'id': 0, 'name': 'Mesto.UA'}

        companion = obj.to_user if obj.from_user == self._context['request'].user else obj.from_user
        return {'id':companion.pk, 'name': companion.get_public_name()}

    def get_folder(self, obj):
        return 'outcomming' if obj.from_user == self._context['request'].user else 'incomming'

    def get_is_promo(self, obj):
        return obj.message_list is not None

    class Meta:
        model = Message
        fields = ('id', 'basead', 'folder', 'root_message', 'is_promo', 'from_user', 'companion', 'to_user', 'title',
                  'subject', 'text', 'time', 'readed') #
        read_only_fields = ('root_message', 'title', 'from_user', 'to_user', 'readed', 'time')


from django.utils.translation import ugettext_lazy as _

class LeadHistoryShortSerializer(serializers.ModelSerializer):
    message = serializers.SerializerMethodField()
    time_display = serializers.SerializerMethodField()

    class Meta:
        model = LeadHistoryEvent
        fields = ('id', 'time', 'time_display', 'message')

    def get_time_display(self, obj):
        return u'%s, в %s' % (obj.time.strftime('%d.%m.%Y'), obj.time.strftime('%H:%M'))

    def get_message(self, obj):
        return obj.get_event_message()


class PhoneField(serializers.CharField):
    def to_internal_value(self, data):
        from ad.phones import validate, InvalidPhoneException
        try:
            phone = validate(data)
        except InvalidPhoneException:
            raise serializers.ValidationError(_(u"Некорректный номер %s") % data)
        else:
            return phone

class LeadSerializer(serializers.ModelSerializer):
    ad_id = serializers.SerializerMethodField()
    label_display = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    history = LeadHistoryShortSerializer(many=True, read_only=True)
    phone = PhoneField(max_length=12, min_length=11, allow_blank=True)
    phone_display = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = (
            'id', 'name', 'email', 'label', 'ad_id', 'phone', 'phone_display', 'label_display', 'image_url', 'history',
            'is_readed'
        )

    def get_ad_id(self, obj):
        return obj.basead_id

    def get_label_display(self, obj):
        return obj.get_label_display()


    def get_phone_display(self, obj):
        from ad.phones import pprint_phone
        if obj.phone:
            return pprint_phone(obj.phone)

    def get_image_url(self, obj):
        if obj.user and obj.user.image:
            return get_lazy_thumbnail(obj.user.image, '67x67', crop='center')


class LeadWithOutHistorySerializer(LeadSerializer):
    class Meta:
        model = Lead
        fields = (
            'id', 'name', 'email', 'label', 'ad_id', 'phone', 'phone_display', 'label_display', 'image_url', 'is_readed'
        )

class CallSerializer(serializers.ModelSerializer):
    complaint_display = serializers.SerializerMethodField()
    missed = serializers.SerializerMethodField()
    free = serializers.SerializerMethodField()

    class Meta:
        model = Call
        fields = ('id', 'deal_type', 'complaint', 'complaint_display', 'recordingfile', 'missed', 'free')

    def get_missed(self, obj):
        return obj.duration == 0

    def get_free(self, obj):
        return obj.transaction.amount == 0

    def get_complaint_display(self, obj):
        return obj.get_complaint_display()


class CallRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallRequest
        fields = ('id', 'name', 'email', 'phone')


class LeadHistoryRelatedField(serializers.RelatedField):
    def to_representation(self, value):
        if isinstance(value, CallRequest):
            return {'callrequest': CallRequestSerializer(value).data}
        elif isinstance(value, Call):
            return {'call': CallSerializer(value).data}
        raise Exception('Unexpected type of tagged object')


class LeadHistorySerializer(serializers.ModelSerializer):
    time_display = serializers.SerializerMethodField()
    object = LeadHistoryRelatedField(read_only=True)
    lead = LeadWithOutHistorySerializer(read_only=True)

    ask_complaint_for_call = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = LeadHistoryEvent
        fields = ('id', 'time', 'time_display', 'lead', 'object', 'ask_complaint_for_call', 'is_readed')

    def get_object(self, obj):
        if obj.object:
            return obj.object.__dict__

    def get_time_display(self, obj):
        return obj.time.strftime('%d.%m.%Y<br/>%H:%M')


class LeadField(serializers.PrimaryKeyRelatedField):
    def to_representation(self, value):
        return value

class TaskSerializer(serializers.ModelSerializer):
    basead = serializers.PrimaryKeyRelatedField(queryset=BaseAd.objects.all(), allow_null=True)
    # basead = serializers.IntegerField(source='basead_id', required=False)
    # lead = serializers.IntegerField(source='lead_id', required=False)
    lead_dict = LeadSerializer(source='lead', read_only=True)

    class Meta:
        model = Task
        fields = ('id', 'name', 'note', 'basead', 'lead', 'lead_dict', 'start', 'end', 'url') #
        read_only_fields = ('user',)

'''
ViewSets
'''


class RegionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Region.objects.all()
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter,)
    filter_class = RegionFilter
    serializer_class = RegionSerializer
    pagination_class = MobileApiPaginator
    search_fields = ('name',)

    def get_queryset(self):
        queryset = Region.objects.all()
        parent_id = self.request.query_params.get('parent_tree', None)

        if parent_id is not None:
            parent = Region.objects.get(pk=parent_id)
            queryset = queryset.filter(parent__in=parent.get_descendants(True))

        return queryset

class UserViewSet(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.ListModelMixin, GenericViewSet):
    queryset = User.objects.all().prefetch_related('saved_ads', 'saved_searches', 'realtors')
    serializer_class = UserSerializer
    permission_classes = (UserPermission,)
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter,)
    filter_fields = {'id':['exact'], 'email':['exact'], 'is_staff':['exact'], 'agencies':['exact'], 'date_joined':['gt'], 'last_action':['gt']}
    pagination_class = MobileApiPaginator
    search_fields = ('phones__number',)

    def get_queryset(self):
        if self.request.user.is_staff and 'show_all' in self.request.GET:
            return self.queryset
        else:
            return self.queryset.filter(id=self.request.user.id)


class PropertyViewSet(viewsets.ModelViewSet):
    model = Ad
    queryset = Ad.objects.all()
    serializer_class = PropertySerializer
    permission_classes = (IsOwnerOrReadOnly, IsAuthenticatedOrReadOnly)
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter,)
    filter_class = PropertyFilter
    search_fields = ('address',)
    ordering_fields = '__all__'
    pagination_class = MobileApiPaginator

    def list(self, request):
        if int(request.query_params.get('page', 0)) > 50:
            raise Exception('Block access with raising error for Sentry')
        return super(PropertyViewSet, self).list(request)

    def perform_update(self, serializer):
        instance = serializer.save(user=self.request.user)

        # обработка телефонов
        self.process_phones(instance, self.request.data)

    def perform_create(self, serializer):
        instance = serializer.save(user=self.request.user)

        # вызывается здесь, т.к. по неизвестным причинам не запускается геокодинг в obj.dirty_property()
        instance.address = instance.build_address()
        instance.process_address()
        instance.save()

        # обработка телефонов
        self.process_phones(instance, self.request.data)

    def process_phones(self, instance, data):
        data_from_json = (type(data) == dict)
        phones = data.get('phones') if data_from_json else data.getlist('phones')
        raw_phones = [phone for phone in phones if len(phone) == 12]

        phones_formset = create_ad_phones_formset(raw_phones)
        if phones_formset.is_valid():
            phones_formset.update_phones_m2m(instance.phones_in_ad)
        else:
            raise Exception('Invalid phones formset')

    def get_queryset(self):
        queryset = Ad.objects.all()

        # not detail page
        if not self.kwargs.get('pk'):
            queryset = queryset.filter(is_published=True, region__isnull=0)

        if self.request.query_params.get('own', None) is not None:
            if self.request.user.is_authenticated():
                queryset = Ad.objects.filter(user=self.request.user.id)
            else:
                queryset = Ad.objects.none()

        lon = float(self.request.query_params.get('lon') or 0)
        lat = float(self.request.query_params.get('lat') or 0)
        radius = float(self.request.query_params.get('radius') or 5)

        if lon and lat:
            if settings.MESTO_USE_GEODJANGO:
                distance_filters = make_sphere_distance_filters('point', Point(lon, lat, srid=4326), Distance(km=radius))
            else:
                distance_filters = make_coords_ranges_filters((lon, lat), Distance(km=radius))

            queryset = queryset.filter(**distance_filters)

        region_id = self.request.query_params.get('region', None)
        if region_id is not None:
            region = Region.objects.get(pk=region_id)
            queryset = queryset.filter(region__in=region.get_descendants(True))

        min_price = int(self.request.query_params.get('min_price') or 0)
        max_price = int(self.request.query_params.get('max_price') or 0)
        if min_price or max_price:
            curr_rate = 1
            currency = self.request.query_params.get('currency', None)
            if currency:
                curr_rate = get_currency_rates()[currency]

            if min_price > 0:
                queryset = queryset.filter(price_uah__gte=min_price * curr_rate)

            if max_price > 0:
                queryset = queryset.filter(price_uah__lte=max_price * curr_rate)

        queryset = queryset.prefetch_related(
            'region', 'phones_in_ad', 'phones', 'photos', 'facilities', 'user', 'user__agencies'
        )

        return queryset

class PropertyOnMapViewSet(PropertyViewSet):
    serializer_class = PropertyOnMapSerializer
    pagination_class = PropertyOnMapPagination


class PhotoViewSet(viewsets.ModelViewSet):
    model = Photo
    queryset = Photo.objects.all()
    serializer_class = PhotoSerializer
    permission_classes = (IsOwnerOrReadOnly,)
    pagination_class = MobileApiPaginator

    def perform_create(self, serializer):
        serializer.save(order=0)

    def get_queryset(self):
        photo_id = self.kwargs.get('pk')
        property_id = int(self.request.query_params.get('property', 0))
        if property_id:
            return Photo.objects.filter(basead_id=property_id)
        elif photo_id and self.request.user.is_authenticated():
            return Photo.objects.filter(pk=photo_id, ad__user=self.request.user)
        else:
            return Photo.objects.none()


class MessageFilter(django_filters.FilterSet):
    root_message = django_filters.NumberFilter(name="root_message")
    class Meta:
        model = Message
        fields = ['root_message', ]


class MessageViewSet(viewsets.ModelViewSet):
    model = Message
    queryset = Message.objects.order_by('-pk')
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter,)
    filter_class = MessageFilter
    serializer_class = MessageSerializer
    renderer_classes = (MessageJSONRenderer, BrowsableAPIRenderer)
    permission_classes = (IsAuthenticated,)
    ordering_fields = ('time',)
    pagination_class = MessagePagination

    def get_queryset(self):
        leads = self.request.user.leads.all()
        user_condition = Q(from_user=self.request.user) | Q(to_user=self.request.user)
        message_list_sender = Q(from_user=self.request.user, message_list__isnull=False) & ~Q(to_user=self.request.user)
        hidden_messages_for_user = Q(root_message__hidden_for_user=self.request.user)
        self.queryset = self.queryset.filter(user_condition)\
            .exclude(message_list_sender | hidden_messages_for_user)\
            .select_related('to_user', 'from_user')\
            .prefetch_related('from_user__leads', 'to_user__leads', 'message_list')

        if self.request.query_params.get('lead_type'):
            users = leads.filter(label=self.request.query_params['lead_type'])\
                                                                    .values_list('user_id', flat=True)
            user_condition = Q(from_user__in=users) | Q(to_user__in=users)
            self.queryset = self.queryset.filter(user_condition)

        if self.request.query_params.get('query'):
            query = self.request.query_params.get('query').strip()
            if query.isnumeric():
                self.queryset = self.queryset.filter(basead__pk__contains=query)
            else:
                search_condition = Q(from_user__first_name__icontains=query) | Q(from_user__last_name__icontains=query) | Q(text__icontains=query)

                lead_users = leads.filter(Q(name__icontains=query) | Q(email__icontains=query)).values_list('user_id', flat=True)
                if lead_users:
                    search_condition.add(Q(from_user__in=lead_users) | Q(to_user__in=lead_users), Q.OR)

                self.queryset = self.queryset.filter(search_condition)

        if 'dialogs' in self.request.query_params:
            last_message_ids = self.queryset.values('root_message').annotate(last_id=Max('id')).order_by('root_message')
            self.queryset = self.queryset.filter(pk__in=[row['last_id'] for row in last_message_ids]).order_by('-time')

        return self.queryset

    def perform_create(self, serializer):
        dialogue = Message.objects.get(pk=serializer.initial_data['root_message'])
        to_user = dialogue.to_user if dialogue.from_user == self.request.user else dialogue.from_user
        serializer.save(from_user=self.request.user, to_user=to_user, title=dialogue.title,
                        root_message=dialogue, basead=dialogue.basead)


class TaskViewSet(viewsets.ModelViewSet):
    model = Task
    serializer_class = TaskSerializer
    permission_classes = (IsAuthenticated,)
    queryset = Task.objects.order_by('start')
    pagination_class = TaskPagination

    filter_backends = (filters.SearchFilter, )
    search_fields = ('name', 'note', 'lead__name', 'lead__email', 'lead__phone',)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        overwrite_fields = {'user':self.request.user}

        data = serializer.initial_data
        if not data['lead'] and data['lead_name']:
            ad = Ad.objects.filter(pk=data['basead']).first() if data['basead'].isnumeric() else None
            lead = Lead.objects.create(user=self.request.user, basead=ad, name=data['lead_name'], phone=data['lead_phone'])
            overwrite_fields['lead'] = lead

        serializer.save(**overwrite_fields)


class LeadViewSet(viewsets.ModelViewSet):
    model = Lead
    serializer_class = LeadSerializer
    permission_classes = (IsAuthenticated,)
    queryset = Lead.objects.all()
    pagination_class = LeadPagination

    filter_backends = (filters.SearchFilter, )
    search_fields = ('name', 'email', 'phone',)

    def get_queryset(self):
        own_agency = self.request.user.get_own_agency()
        if own_agency:
            queryset = self.queryset.filter(user__in=own_agency.get_realtors().values('user'))
        else:
            queryset = self.queryset.filter(user=self.request.user)

        query = self.request.query_params.get('query')
        if query:
            search_condition = Q(name__icontains=query) | Q(email__icontains=query)
            if query.isnumeric():
                search_condition |= Q(phone__icontains=query)
            queryset = queryset.filter(search_condition)

        label = self.request.query_params.get('label')
        if label:
            queryset = queryset.filter(label=label)

        return queryset


class LeadHistoryViewSet(viewsets.ModelViewSet):
    model = LeadHistoryEvent
    serializer_class = LeadHistorySerializer
    permission_classes = (IsAuthenticated,)
    queryset = LeadHistoryEvent.objects.filter(object_id__isnull=False)
    pagination_class = LeadHistoryPagination

    filter_backends = (filters.SearchFilter, )
    search_fields = ('lead__name', 'lead__email', 'lead__phone',)

    def perform_update(self, serializer):
        instance = serializer.save()

        # вообще нет такого поля в LeadHistoryEvent, но это был самый простой способ через бэкбон пропихнуть команду на подачу жалобы по звонку
        if serializer.initial_data.get('ask_complaint_for_call'):
            call = serializer.instance.object
            if not call.complaint:
                call.complaint = 'awaiting'
                call.save()


    def get_queryset(self):
        own_agency = self.request.user.get_own_agency()
        if own_agency:
            queryset = self.queryset.filter(lead__user__in=own_agency.get_realtors().values('user'))
        else:
            queryset = self.queryset.filter(lead__user=self.request.user)

        query = self.request.query_params.get('query')
        if query:
            search_condition = Q(lead__name__icontains=query) | Q(lead__email__icontains=query)
            if query.isnumeric():
                search_condition |= Q(lead__phone__icontains=query)
            queryset = queryset.filter(search_condition)

        label = self.request.query_params.get('label')
        if label:
            queryset = queryset.filter(lead__label=label)

        return queryset

'''
User related viewsets
'''
class UserFilteredWithAddViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return self.queryset.filter(pk=self.request.user.id)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AgencyViewSet(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.ListModelMixin, GenericViewSet):
    queryset = Agency.objects.all()
    serializer_class = AgencySerializer
    permission_classes = (IsAgencyAdminOrReadOnly, IsAuthenticated,)

    def get_queryset(self):
        if not self.request.user.is_staff:
            return self.queryset.filter(users=self.request.user)

        return self.queryset


class SavedSearchViewSet(UserFilteredWithAddViewSet):
    queryset = SavedSearch.objects.all()
    serializer_class = SavedSearchSerializer


class SavedPropertyViewSet(UserFilteredWithAddViewSet):
    renderer_classes = (CustomJSONRenderer, BrowsableAPIRenderer)
    queryset = SavedAd.objects.all()
    serializer_class = SavedPropertySerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @detail_route(methods=['GET', 'POST', 'DELETE'])
    def delete_by_property_id(self, request, pk=None):
        target_properties = SavedAd.objects.filter(user=request.user, basead_id=pk)
        count = target_properties.count()
        target_properties.delete()
        return Response({'deleted_rows': count})
