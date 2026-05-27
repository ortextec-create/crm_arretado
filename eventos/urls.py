from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LocalEventoViewSet, EventoViewSet

router = DefaultRouter()
router.register('locais',  LocalEventoViewSet, basename='locais-evento')
router.register('',        EventoViewSet,       basename='eventos')

urlpatterns = [
    path('', include(router.urls)),
]
