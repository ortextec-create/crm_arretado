from django.urls import path
from .views import RelatorioIFoodView, ProdutosMaisVendidosView, RelatorioEventosView

urlpatterns = [
    path('ifood/', RelatorioIFoodView.as_view(), name='relatorio-ifood'),
    path('produtos-mais-vendidos/', ProdutosMaisVendidosView.as_view(), name='relatorio-produtos-mais-vendidos'),
    path('eventos/', RelatorioEventosView.as_view(), name='relatorio-eventos'),
]
