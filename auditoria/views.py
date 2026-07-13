import datetime

from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.authentication import TokenAuthentication
from usuarios.permissions import IsAdminRole

from .models import LogAuditoria, PresencaEdicao
from .serializers import LogAuditoriaSerializer

JANELA_PRESENCA_SEGUNDOS = 40


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

        model = params.get('model')
        if model:
            qs = qs.filter(detalhes__model=model)

        data_inicio = params.get('data_inicio')
        if data_inicio:
            qs = qs.filter(criado_em__date__gte=data_inicio)

        data_fim = params.get('data_fim')
        if data_fim:
            qs = qs.filter(criado_em__date__lte=data_fim)

        return qs


class PresencaHeartbeatView(APIView):
    """
    POST /api/v1/auditoria/presenca/
    Body: {"model": "Orcamento", "objeto_id": 12}

    Heartbeat de "quem está vendo este registro agora" via polling (não
    WebSocket — ver CLAUDE.md). Atualiza/registra a presença do usuário
    autenticado e devolve quem mais está ativo no mesmo (model, objeto_id)
    dentro de uma janela de JANELA_PRESENCA_SEGUNDOS. Inclui o próprio
    chamador na lista — o frontend filtra.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        model = request.data.get('model')
        objeto_id = request.data.get('objeto_id')
        if not model or not objeto_id:
            return Response({'detail': 'Informe model e objeto_id.'}, status=status.HTTP_400_BAD_REQUEST)

        PresencaEdicao.objects.update_or_create(
            usuario=request.user, model=model, objeto_id=objeto_id,
        )

        limite = timezone.now() - datetime.timedelta(seconds=JANELA_PRESENCA_SEGUNDOS)
        ativos = (
            PresencaEdicao.objects
            .filter(model=model, objeto_id=objeto_id, atualizado_em__gte=limite)
            .select_related('usuario')
            .order_by('-atualizado_em')
        )
        return Response({
            'usuarios': [
                {'id': p.usuario_id, 'name': p.usuario.name, 'atualizado_em': p.atualizado_em}
                for p in ativos
            ],
        })
