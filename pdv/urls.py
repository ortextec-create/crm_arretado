from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoriaProdutoViewSet, ProdutoViewSet, PedidoPDVViewSet

router = DefaultRouter()
router.register('categorias', CategoriaProdutoViewSet, basename='pdv-categoria')
router.register('produtos',   ProdutoViewSet,          basename='pdv-produto')
router.register('pedidos',    PedidoPDVViewSet,         basename='pdv-pedido')

urlpatterns = [
    path('', include(router.urls)),
]
