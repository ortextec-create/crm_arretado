from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import MensagemViewSet, ConfiguracaoWhatsAppViewSet

router = DefaultRouter()
router.register('mensagens', MensagemViewSet, basename='mensagem')

_cfg = ConfiguracaoWhatsAppViewSet.as_view

urlpatterns = router.urls + [
    path('configuracao/',        _cfg({'get': 'retrieve', 'patch': 'partial_update'})),
    path('configuracao/testar/', _cfg({'post': 'testar'})),
]
