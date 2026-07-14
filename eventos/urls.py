from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LocalEventoViewSet, EventoViewSet, OrcamentoViewSet,
    ContratoViewSet, ConfiguracaoContratoViewSet,
    ConfiguracaoAlertaEventoViewSet, TelefoneAlertaEventoViewSet,
)

router = DefaultRouter()
router.register('locais',               LocalEventoViewSet,         basename='locais-evento')
router.register('orcamentos',           OrcamentoViewSet,           basename='orcamentos')
router.register('contratos',            ContratoViewSet,            basename='contratos')
router.register('configuracao-contrato', ConfiguracaoContratoViewSet, basename='configuracao-contrato')
router.register('configuracao-alertas', ConfiguracaoAlertaEventoViewSet, basename='configuracao-alertas')
router.register('telefones-alerta',     TelefoneAlertaEventoViewSet, basename='telefones-alerta')
router.register('',                     EventoViewSet,              basename='eventos')

urlpatterns = [
    path('', include(router.urls)),
]
