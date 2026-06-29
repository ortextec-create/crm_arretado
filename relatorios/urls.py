from django.urls import path
from .views import RelatorioIFoodView

urlpatterns = [
    path('ifood/', RelatorioIFoodView.as_view(), name='relatorio-ifood'),
]
