from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ConfiguracaoBackupViewSet, TelefoneAlertaBackupViewSet

router = DefaultRouter()
router.register('configuracao-backup', ConfiguracaoBackupViewSet, basename='configuracao-backup')
router.register('telefones-alerta', TelefoneAlertaBackupViewSet, basename='telefones-alerta-backup')

urlpatterns = [
    path('', include(router.urls)),
]
