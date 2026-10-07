from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ConfiguracaoCobrancaViewSet, EtapaReguaViewSet, EnvioCobrancaViewSet,
    LigacaoCobrancaViewSet, PausaCobrancaViewSet, FilaCobrancaView, LinhaDoTempoView,
)

router = DefaultRouter()
router.register('configuracao', ConfiguracaoCobrancaViewSet, basename='cobranca-configuracao')
router.register('etapas', EtapaReguaViewSet, basename='cobranca-etapas')
router.register('envios', EnvioCobrancaViewSet, basename='cobranca-envios')
router.register('ligacoes', LigacaoCobrancaViewSet, basename='cobranca-ligacoes')
router.register('pausas', PausaCobrancaViewSet, basename='cobranca-pausas')

urlpatterns = [
    path('fila/', FilaCobrancaView.as_view(), name='cobranca-fila'),
    path('eventos/<int:evento_id>/linha-do-tempo/', LinhaDoTempoView.as_view(), name='cobranca-linha-do-tempo'),
    path('', include(router.urls)),
]
