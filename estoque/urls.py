from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AjusteInventarioView,
    ConfiguracaoEstoqueViewSet,
    ConfiguracaoIAViewSet,
    ImportacaoNotaFiscalViewSet,
    MovimentoEstoqueViewSet,
    ProducaoViewSet,
    RegistrarCompraView,
    TelefoneAlertaEstoqueViewSet,
)

router = DefaultRouter()
router.register('movimentos', MovimentoEstoqueViewSet, basename='movimentos-estoque')
router.register('producoes', ProducaoViewSet, basename='producoes')
router.register('configuracao', ConfiguracaoEstoqueViewSet, basename='configuracao-estoque')
router.register('configuracao-ia', ConfiguracaoIAViewSet, basename='configuracao-ia')
router.register('telefones-alerta', TelefoneAlertaEstoqueViewSet, basename='telefones-alerta-estoque')
router.register('notas', ImportacaoNotaFiscalViewSet, basename='notas-fiscais')

urlpatterns = [
    path('', include(router.urls)),
    path('compras/registrar/', RegistrarCompraView.as_view()),
    path('ajuste-inventario/', AjusteInventarioView.as_view()),
]
