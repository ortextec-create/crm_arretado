"""
ARQUIVO NOVO: pedidos/urls.py — Fase 4
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PedidoUnificadoViewSet

router = DefaultRouter()
router.register(r'pedidos', PedidoUnificadoViewSet, basename='pedidos')

urlpatterns = [
    path('', include(router.urls)),
]
