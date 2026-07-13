from rest_framework import viewsets

from usuarios.authentication import TokenAuthentication
from usuarios.permissions import IsAdminRole

from .models import LogAuditoria
from .serializers import LogAuditoriaSerializer


class LogAuditoriaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LogAuditoria.objects.select_related('usuario').all()
    serializer_class = LogAuditoriaSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdminRole]
    ordering = ['-criado_em']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        usuario_id = params.get('usuario')
        if usuario_id:
            qs = qs.filter(usuario_id=usuario_id)

        acao = params.get('acao')
        if acao:
            qs = qs.filter(acao=acao)

        data_inicio = params.get('data_inicio')
        if data_inicio:
            qs = qs.filter(criado_em__date__gte=data_inicio)

        data_fim = params.get('data_fim')
        if data_fim:
            qs = qs.filter(criado_em__date__lte=data_fim)

        return qs
