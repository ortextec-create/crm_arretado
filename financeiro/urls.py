from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CategoriaFinanceiraViewSet,
    ConfiguracaoFinanceiraViewSet,
    ContaBancariaViewSet,
    ContaPagarViewSet,
    FornecedorViewSet,
    MovimentoFinanceiroViewSet,
    TelefoneAlertaFinanceiroViewSet,
)

router = DefaultRouter()
router.register('categorias', CategoriaFinanceiraViewSet, basename='categorias-financeiras')
router.register('contas-bancarias', ContaBancariaViewSet, basename='contas-bancarias')
router.register('fornecedores', FornecedorViewSet, basename='fornecedores')
router.register('contas-pagar', ContaPagarViewSet, basename='contas-pagar')
router.register('movimentos', MovimentoFinanceiroViewSet, basename='movimentos-financeiro')
router.register('configuracao', ConfiguracaoFinanceiraViewSet, basename='configuracao-financeira')
router.register('telefones-alerta', TelefoneAlertaFinanceiroViewSet, basename='telefones-alerta-financeiro')

urlpatterns = [
    path('', include(router.urls)),
]
