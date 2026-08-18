from django.urls import path
from .views import RelatorioIFoodView, ProdutosMaisVendidosView

urlpatterns = [
    path('ifood/', RelatorioIFoodView.as_view(), name='relatorio-ifood'),
    path('produtos-mais-vendidos/', ProdutosMaisVendidosView.as_view(), name='relatorio-produtos-mais-vendidos'),
]
