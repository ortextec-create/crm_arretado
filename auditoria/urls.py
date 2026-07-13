from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import LogAuditoriaViewSet, PresencaHeartbeatView

router = DefaultRouter()
router.register(r'logs', LogAuditoriaViewSet, basename='logs')

urlpatterns = [
    path('presenca/', PresencaHeartbeatView.as_view(), name='presenca-heartbeat'),
    path('', include(router.urls)),
]
