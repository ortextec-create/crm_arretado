from django.urls import path
from .views import RelatorioIFoodView, ProdutosMaisVendidosView, RelatorioEventosView, RelatorioCatalogoView

urlpatterns = [
    path('ifood/', RelatorioIFoodView.as_view(), name='relatorio-ifood'),
    path('produtos-mais-vendidos/', ProdutosMaisVendidosView.as_view(), name='relatorio-produtos-mais-vendidos'),
    path('eventos/', RelatorioEventosView.as_view(), name='relatorio-eventos'),
    path('catalogo/', RelatorioCatalogoView.as_view(), name='relatorio-catalogo'),
]
