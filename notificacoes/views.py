from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from clientes.models import Cliente
from .models import HistoricoMensagem, ConfiguracaoWhatsApp
from .serializers import HistoricoMensagemSerializer, EnviarMensagemSerializer, ConfiguracaoWhatsAppSerializer
from . import zapi_client as evo


class CsrfExemptMixin:
    authentication_classes = []


class MensagemViewSet(CsrfExemptMixin, viewsets.ReadOnlyModelViewSet):
    queryset           = HistoricoMensagem.objects.select_related('cliente').all()
    serializer_class   = HistoricoMensagemSerializer
    permission_classes = [AllowAny]
    filter_backends    = [filters.OrderingFilter]
    ordering           = ['-enviado_em']

    def get_queryset(self):
        qs     = super().get_queryset()
        params = self.request.query_params

        tipo   = params.get('tipo')
        status = params.get('status')
        if tipo:
            qs = qs.filter(tipo=tipo)
        if status:
            qs = qs.filter(status=status)

        return qs

    @action(detail=False, methods=['post'], url_path='enviar')
    def enviar(self, request):
        serializer = EnviarMensagemSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data      = serializer.validated_data
        cliente   = None
        telefone  = data.get('telefone', '')
        mensagem  = data['mensagem']
        tipo      = data.get('tipo', 'manual')

        if data.get('cliente_id'):
            try:
                cliente  = Cliente.objects.get(pk=data['cliente_id'])
                telefone = telefone or cliente.telefone_principal
            except Cliente.DoesNotExist:
                return Response({'detail': 'Cliente não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        registro = HistoricoMensagem(
            cliente=cliente,
            telefone=telefone,
            mensagem=mensagem,
            tipo=tipo,
            status='pendente',
        )

        try:
            result = evo.enviar_texto(telefone, mensagem)
            registro.status     = 'enviado'
            registro.message_id = result.get('messageId', '') if isinstance(result, dict) else ''
        except evo.ZAPIError as e:
            registro.status = 'falha'
            registro.erro   = str(e)

        registro.save()
        return Response(
            HistoricoMensagemSerializer(registro).data,
            status=status.HTTP_201_CREATED if registro.status == 'enviado' else status.HTTP_502_BAD_GATEWAY,
        )

    @action(detail=False, methods=['get'], url_path='status-conexao')
    def status_conexao(self, request):
        try:
            data = evo.status_conexao()
            return Response(data)
        except evo.ZAPIError as e:
            return Response({'state': 'error', 'detail': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # ── Webhooks Z-API ────────────────────────────────────────────────────────

    _STATUS_MAP = {'DELIVERED': 'entregue', 'READ': 'lido', 'PLAYED': 'lido'}

    @action(detail=False, methods=['post'], url_path='webhook/status')
    def webhook_status(self, request):
        """Z-API → receber confirmação de entrega/leitura."""
        message_id  = request.data.get('messageId', '')
        zapi_status = request.data.get('status', '')
        novo_status = self._STATUS_MAP.get(zapi_status)

        if message_id and novo_status:
            HistoricoMensagem.objects.filter(message_id=message_id).update(status=novo_status)

        return Response({'ok': True})

    @action(detail=False, methods=['post'], url_path='webhook/desconectado')
    def webhook_desconectado(self, request):
        """Z-API → celular desconectado."""
        ConfiguracaoWhatsApp.objects.filter(pk=1).update(whatsapp_conectado=False)
        return Response({'ok': True})

    @action(detail=False, methods=['post'], url_path='webhook/conectado')
    def webhook_conectado(self, request):
        """Z-API → celular reconectado."""
        ConfiguracaoWhatsApp.objects.filter(pk=1).update(whatsapp_conectado=True)
        return Response({'ok': True})


class ConfiguracaoWhatsAppViewSet(CsrfExemptMixin, viewsets.GenericViewSet):
    serializer_class   = ConfiguracaoWhatsAppSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        return ConfiguracaoWhatsApp.get()

    @action(detail=False, methods=['get'], url_path='')
    def retrieve(self, request):
        return Response(self.get_serializer(self.get_object()).data)

    @action(detail=False, methods=['patch'], url_path='')
    def partial_update(self, request):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='testar')
    def testar(self, request):
        try:
            data = evo.status_conexao()
            return Response({'ok': data.get('state') == 'open', **data})
        except evo.ZAPIError as e:
            return Response({'ok': False, 'detail': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
