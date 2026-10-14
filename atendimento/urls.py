from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ConfiguracaoAtendimentoView, ConfiguracaoExtensaoView, ExtensaoConfigView, ExtensaoHeartbeatView,
    ExtensaoReservarView, ExtensaoResultadoView, MensagemChatViewSet, ModeloMensagemChatViewSet,
    StatusExtensaoView, TokenExtensaoViewSet,
)

router = DefaultRouter()
router.register('modelos', ModeloMensagemChatViewSet, basename='atendimento-modelos')
router.register('mensagens', MensagemChatViewSet, basename='atendimento-mensagens')
router.register('tokens', TokenExtensaoViewSet, basename='atendimento-tokens')

urlpatterns = [
    path('extensao/config/', ExtensaoConfigView.as_view()),
    path('extensao/heartbeat/', ExtensaoHeartbeatView.as_view()),
    path('extensao/fila/reservar/', ExtensaoReservarView.as_view()),
    path('extensao/fila/<int:pk>/resultado/', ExtensaoResultadoView.as_view()),
    path('configuracao/', ConfiguracaoAtendimentoView.as_view()),
    path('configuracao-extensao/', ConfiguracaoExtensaoView.as_view()),
    path('status-extensao/', StatusExtensaoView.as_view()),
    path('', include(router.urls)),
]
