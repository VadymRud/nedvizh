# coding: utf-8
from django.conf.urls import url, include
from rest_framework import routers
from rest_framework.authtoken.views import obtain_auth_token
from mobile_api import serializers, views

router = routers.DefaultRouter()
router.register(r'properties', serializers.PropertyViewSet)
router.register(r'properties-on-map', serializers.PropertyOnMapViewSet, base_name='properties-on-map')
router.register(r'properties-images', serializers.PhotoViewSet)
router.register(r'saved-searches', serializers.SavedSearchViewSet)
router.register(r'saved-properties', serializers.SavedPropertyViewSet)
router.register(r'regions', serializers.RegionViewSet)
router.register(r'user', serializers.UserViewSet)
router.register(r'user_person', serializers.UserViewSet)
router.register(r'user_agency', serializers.AgencyViewSet)

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^auth/register/', views.create_auth),
    url(r'^auth/reset-password/', views.restore_password),
    url(r'^auth/token/', obtain_auth_token),
]


# для backbone в админке агентств
router = routers.DefaultRouter()
router.register(r'messages', serializers.MessageViewSet)
router.register(r'leads', serializers.LeadViewSet)
router.register(r'leadhistories', serializers.LeadHistoryViewSet)
router.register(r'tasks', serializers.TaskViewSet)
urlpatterns.extend([
    # Удаление диалога
    url(r'^crm/message/(?P<message_id>\d+)', views.MessageREST.as_view()),
    url(r'^crm/', include(router.urls))
])

# для push
from push_notifications.api.rest_framework import APNSDeviceAuthorizedViewSet, GCMDeviceAuthorizedViewSet
push_router = routers.DefaultRouter()
push_router.register(r'gcm', GCMDeviceAuthorizedViewSet)
push_router.register(r'apns', APNSDeviceAuthorizedViewSet)
urlpatterns.append(url(r'^push/', include(push_router.urls)))

# monkey patch
from push_notifications.admin import DeviceAdmin
DeviceAdmin.raw_id_fields = ('user',)