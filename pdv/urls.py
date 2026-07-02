from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoriaProdutoViewSet, ProdutoViewSet, PedidoPDVViewSet,
    TaxaEntregaBairroViewSet, ConfiguracaoEntregaViewSet,
)

router = DefaultRouter()
router.register('categorias',           CategoriaProdutoViewSet,   basename='pdv-categoria')
router.register('produtos',             ProdutoViewSet,            basename='pdv-produto')
router.register('pedidos',              PedidoPDVViewSet,          basename='pdv-pedido')
router.register('taxas-entrega',        TaxaEntregaBairroViewSet,  basename='pdv-taxa-entrega')
router.register('configuracao-entrega', ConfiguracaoEntregaViewSet, basename='pdv-config-entrega')

urlpatterns = [
    path('', include(router.urls)),
]
