from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LocalEventoViewSet, EventoViewSet, OrcamentoViewSet,
    ContratoViewSet, ConfiguracaoContratoViewSet,
)

router = DefaultRouter()
router.register('locais',               LocalEventoViewSet,         basename='locais-evento')
router.register('orcamentos',           OrcamentoViewSet,           basename='orcamentos')
router.register('contratos',            ContratoViewSet,            basename='contratos')
router.register('configuracao-contrato', ConfiguracaoContratoViewSet, basename='configuracao-contrato')
router.register('',                     EventoViewSet,              basename='eventos')

urlpatterns = [
    path('', include(router.urls)),
]
