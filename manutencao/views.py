from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from auditoria.mixins import AuditoriaDestroyMixin
from auditoria.models import LogAuditoria
from auditoria.utils import registrar
from usuarios.authentication import TokenAuthentication

from .models import ConfiguracaoBackup, TelefoneAlertaBackup
from .serializers import ConfiguracaoBackupSerializer, TelefoneAlertaBackupSerializer


class CsrfExemptMixin:
    authentication_classes = []


# ─── Configuração de Backup (singleton) ───────────────────────────────────────

class ConfiguracaoBackupViewSet(CsrfExemptMixin, viewsets.GenericViewSet):
    serializer_class = ConfiguracaoBackupSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]  # expõe caminhos do servidor, exige login em tudo (mesmo padrão de ConfiguracaoWhatsApp)

    def get_object(self):
        return ConfiguracaoBackup.get()

    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(self.get_object()).data)

    def partial_update(self, request, pk=None):
        config = self.get_object()
        campos = list(request.data.keys())
        antes = {c: str(getattr(config, c)) for c in campos if hasattr(config, c)}
        serializer = self.get_serializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        depois = {c: str(getattr(config, c)) for c in campos if hasattr(config, c)}
        registrar(
            request.user, LogAuditoria.ACAO_CONFIG_BACKUP_ALTERADA,
            detalhes={'antes': antes, 'depois': depois},
            request=request,
        )
        return Response(serializer.data)


# ─── Telefones de Alerta de Backup ─────────────────────────────────────────────

class TelefoneAlertaBackupViewSet(AuditoriaDestroyMixin, CsrfExemptMixin, viewsets.ModelViewSet):
    queryset = TelefoneAlertaBackup.objects.all()
    serializer_class = TelefoneAlertaBackupSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    campos_log_exclusao = ['numero', 'nome']
