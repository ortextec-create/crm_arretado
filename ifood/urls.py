from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'config',   views.ConfiguracaoIFoodViewSet, basename='ifood-config')
router.register(r'pedidos',  views.PedidoIFoodViewSet,       basename='ifood-pedido')
router.register(r'eventos',  views.EventoPollingViewSet,     basename='ifood-evento')

urlpatterns = [
    path('', include(router.urls)),
]
