from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import LogAuditoriaViewSet

router = DefaultRouter()
router.register(r'logs', LogAuditoriaViewSet, basename='logs')

urlpatterns = [
    path('', include(router.urls)),
]
