from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import MensagemViewSet, ConfiguracaoWhatsAppViewSet

router = DefaultRouter()
router.register('mensagens', MensagemViewSet, basename='mensagem')

_cfg = ConfiguracaoWhatsAppViewSet.as_view
_msg = MensagemViewSet.as_view

urlpatterns = router.urls + [
    path('configuracao/',        _cfg({'get': 'retrieve', 'patch': 'partial_update'})),
    path('configuracao/testar/', _cfg({'post': 'testar'})),

    # Webhooks Z-API (sem autenticação — chamados pelo servidor Z-API)
    path('webhook/status/',       _msg({'post': 'webhook_status'})),
    path('webhook/desconectado/', _msg({'post': 'webhook_desconectado'})),
    path('webhook/conectado/',    _msg({'post': 'webhook_conectado'})),
]
