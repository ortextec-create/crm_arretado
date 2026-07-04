import logging

from django.db.models import Q, Sum, Count
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.authentication import BasicAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import ConfiguracaoIFood, PedidoIFood, EventoPollingIFood
from notificacoes.servico import notificar, _fone_pedido


def _notificar_ifood(pedido, mensagem):
    notificar(_fone_pedido(pedido), mensagem, cliente=pedido.cliente, tipo='pedido')
from .serializers import (
    ConfiguracaoIFoodSerializer,
    PedidoIFoodListSerializer,
    PedidoIFoodDetailSerializer,
    EventoPollingSerializer,
)
from .ifood_client import IFoodClient, IFoodAPIError
from .polling_worker import run_polling

logger = logging.getLogger(__name__)


class CsrfExemptMixin:
    """
    Remove SessionAuthentication para que o DRF não exija CSRF token.
    Necessário quando o frontend envia JSON sem cookie de sessão Django.
    Em produção, substitua AllowAny por IsAuthenticated + TokenAuthentication.
    """
    authentication_classes = []


class ConfiguracaoIFoodViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    """CRUD da configuração iFood + ações de teste e polling manual."""
    queryset           = ConfiguracaoIFood.objects.all()
    serializer_class   = ConfiguracaoIFoodSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=['post'], url_path='testar')
    def testar_conexao(self, request, pk=None):
        config = self.get_object()
        client = IFoodClient(config)
        result = client.testar_conexao()
        status_code = status.HTTP_200_OK if result['ok'] else status.HTTP_400_BAD_REQUEST
        return Response(result, status=status_code)

    @action(detail=True, methods=['post'], url_path='polling-manual')
    def polling_manual(self, request, pk=None):
        config = self.get_object()
        original = config.polling_ativo
        config.polling_ativo = True
        config.save(update_fields=['polling_ativo'])
        try:
            result = run_polling()
        finally:
            config.polling_ativo = original
            config.save(update_fields=['polling_ativo'])
        return Response(result)

    @action(detail=True, methods=['post'], url_path='ativar-polling')
    def ativar_polling(self, request, pk=None):
        config = self.get_object()
        config.polling_ativo = True
        config.save(update_fields=['polling_ativo'])
        return Response({'polling_ativo': True})

    @action(detail=True, methods=['post'], url_path='pausar-polling')
    def pausar_polling(self, request, pk=None):
        config = self.get_object()
        config.polling_ativo = False
        config.save(update_fields=['polling_ativo'])
        return Response({'polling_ativo': False})

    @action(detail=False, methods=['get'], url_path='status')
    def status_geral(self, request):
        config = ConfiguracaoIFood.objects.first()
        if not config:
            return Response({'configurado': False})

        pendentes    = PedidoIFood.objects.filter(status='PLACED').count()
        hoje         = timezone.localtime(timezone.now()).date()
        pedidos_hoje = PedidoIFood.objects.filter(ifood_criado_em__date=hoje).count()

        return Response({
            'configurado':    True,
            'polling_ativo':  config.polling_ativo,
            'token_valido':   config.token_valido,
            'ultimo_polling': config.ultimo_polling,
            'pendentes':      pendentes,
            'pedidos_hoje':   pedidos_hoje,
            'merchant_id':    config.merchant_id,
        })


class PedidoIFoodViewSet(CsrfExemptMixin, viewsets.ReadOnlyModelViewSet):
    """Listagem e detalhe de pedidos iFood + ações confirmar/cancelar/despachar."""
    queryset           = PedidoIFood.objects.prefetch_related('itens').select_related('cliente').all()
    permission_classes = [AllowAny]
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ['ifood_criado_em', 'total_valor', 'status']
    ordering           = ['-ifood_criado_em']

    def get_serializer_class(self):
        if self.action == 'list':
            return PedidoIFoodListSerializer
        return PedidoIFoodDetailSerializer

    def get_queryset(self):
        qs     = super().get_queryset()
        params = self.request.query_params

        status_f = params.get('status')
        if status_f:
            qs = qs.filter(status=status_f)

        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(display_id__icontains=search) |
                Q(cliente_nome__icontains=search) |
                Q(cliente_telefone__icontains=search) |
                Q(ifood_order_id__icontains=search)
            )

        data_inicio = params.get('data_inicio')
        data_fim    = params.get('data_fim')
        if data_inicio:
            qs = qs.filter(ifood_criado_em__date__gte=data_inicio)
        if data_fim:
            qs = qs.filter(ifood_criado_em__date__lte=data_fim)

        return qs

    def _get_client(self):
        config = ConfiguracaoIFood.objects.first()
        if not config:
            return None, Response(
                {'detail': 'Integração iFood não configurada.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return IFoodClient(config), None

    @action(detail=True, methods=['post'], url_path='confirmar')
    def confirmar(self, request, pk=None):
        pedido = self.get_object()
        if not pedido.pode_confirmar:
            return Response({'detail': f'Pedido não pode ser confirmado (status: {pedido.status})'}, status=400)
        client, err = self._get_client()
        if err:
            return err
        try:
            client.confirm_order(pedido.ifood_order_id)
            pedido.status = 'CONFIRMED'
            pedido.save(update_fields=['status', 'atualizado_em'])
            _notificar_ifood(pedido, f'✅ Seu pedido iFood #{pedido.display_id} foi confirmado! Estamos preparando com carinho. 🍬')
            return Response({'status': 'CONFIRMED'})
        except IFoodAPIError as e:
            return Response({'detail': str(e)}, status=502)

    @action(detail=True, methods=['post'], url_path='cancelar')
    def cancelar(self, request, pk=None):
        pedido = self.get_object()
        if not pedido.pode_cancelar:
            return Response({'detail': f'Pedido não pode ser cancelado (status: {pedido.status})'}, status=400)
        reason_code = request.data.get('cancellationCode', '501')
        reason_desc = request.data.get('reason', '')
        client, err = self._get_client()
        if err:
            return err
        try:
            client.cancel_order(pedido.ifood_order_id, reason_code, reason_desc)
            pedido.status = 'CANCELLED'
            pedido.save(update_fields=['status', 'atualizado_em'])
            _notificar_ifood(pedido, f'❌ Seu pedido iFood #{pedido.display_id} foi cancelado. Pedimos desculpas pelo inconveniente.')
            return Response({'status': 'CANCELLED'})
        except IFoodAPIError as e:
            return Response({'detail': str(e)}, status=502)
        
    @action(detail=True, methods=['post'], url_path='aceitar-negociacao')
    def aceitar_negociacao(self, request, pk=None):
        """
        POST /api/v1/ifood/pedidos/{id}/aceitar-negociacao/

        Aceita o cancelamento solicitado pelo cliente via Plataforma de Negociação.
        Chama POST /orders/{id}/acceptCancellation na API iFood.
        """
        pedido = self.get_object()

        if not pedido.negociacao_pendente:
            return Response(
                {'detail': 'Não há negociação pendente para este pedido.'},
                status=400,
            )

        client, err = self._get_client()
        if err:
            return err

        try:
            client.accept_cancellation(pedido.ifood_order_id)
            pedido.negociacao_pendente = False
            pedido.status = 'CANCELLED'
            pedido.save(update_fields=['negociacao_pendente', 'status', 'atualizado_em'])
            return Response({'status': 'CANCELLED', 'detail': 'Cancelamento aceito.'})
        except IFoodAPIError as e:
            return Response({'detail': str(e)}, status=502)

    @action(detail=True, methods=['post'], url_path='recusar-negociacao')
    def recusar_negociacao(self, request, pk=None):
        """
        POST /api/v1/ifood/pedidos/{id}/recusar-negociacao/

        Recusa o cancelamento solicitado pelo cliente via Plataforma de Negociação.
        Chama POST /orders/{id}/denyCancellation na API iFood.
        O pedido volta ao status CONFIRMED.
        """
        pedido = self.get_object()

        if not pedido.negociacao_pendente:
            return Response(
                {'detail': 'Não há negociação pendente para este pedido.'},
                status=400,
            )

        client, err = self._get_client()
        if err:
            return err

        try:
            client.deny_cancellation(pedido.ifood_order_id)
            pedido.negociacao_pendente   = False
            pedido.negociacao_tipo       = ''
            pedido.negociacao_descricao  = ''
            pedido.status = 'CONFIRMED'
            pedido.save(update_fields=[
                'negociacao_pendente', 'negociacao_tipo',
                'negociacao_descricao', 'status', 'atualizado_em',
            ])
            return Response({'status': 'CONFIRMED', 'detail': 'Cancelamento recusado. Pedido mantido.'})
        except IFoodAPIError as e:
            return Response({'detail': str(e)}, status=502)

    @action(detail=True, methods=['post'], url_path='despachar')
    def despachar(self, request, pk=None):
        pedido = self.get_object()
        client, err = self._get_client()
        if err:
            return err
        try:
            client.dispatch_order(pedido.ifood_order_id)
            pedido.status = 'DISPATCHED'
            pedido.save(update_fields=['status', 'atualizado_em'])
            _notificar_ifood(pedido, f'🛵 Seu pedido iFood #{pedido.display_id} saiu para entrega! Aguarde.')
            return Response({'status': 'DISPATCHED'})
        except IFoodAPIError as e:
            return Response({'detail': str(e)}, status=502)

    @action(detail=True, methods=['post'], url_path='pronto-retirada')
    def pronto_retirada(self, request, pk=None):
        pedido = self.get_object()
        client, err = self._get_client()
        if err:
            return err
        try:
            client.ready_to_pickup(pedido.ifood_order_id)
            pedido.status = 'READY_TO_PICKUP'
            pedido.save(update_fields=['status', 'atualizado_em'])
            _notificar_ifood(pedido, f'🎉 Seu pedido iFood #{pedido.display_id} está pronto para retirada na Arretado Doces!')
            return Response({'status': 'READY_TO_PICKUP'})
        except IFoodAPIError as e:
            return Response({'detail': str(e)}, status=502)

    @action(detail=True, methods=['post'], url_path='vincular-cliente')
    def vincular_cliente(self, request, pk=None):
        from clientes.models import Cliente
        pedido     = self.get_object()
        cliente_id = request.data.get('cliente_id')
        if not cliente_id:
            return Response({'detail': 'cliente_id é obrigatório.'}, status=400)
        try:
            cliente = Cliente.objects.get(pk=cliente_id)
        except Cliente.DoesNotExist:
            return Response({'detail': 'Cliente não encontrado.'}, status=404)

        pedido.cliente = cliente
        pedido.save(update_fields=['cliente', 'atualizado_em'])

        if pedido.cliente_ifood_id and not cliente.ifood_customer_id:
            cliente.ifood_customer_id = pedido.cliente_ifood_id
            cliente.save(update_fields=['ifood_customer_id'])

        return Response({'cliente_id': cliente.id, 'cliente_nome': cliente.nome})

    @action(detail=True, methods=['get'], url_path='motivos-cancelamento')
    def motivos_cancelamento(self, request, pk=None):
        pedido = self.get_object()
        client, err = self._get_client()
        if err:
            return err
        try:
            reasons = client.get_cancellation_reasons(pedido.ifood_order_id)
            return Response(reasons)
        except IFoodAPIError as e:
            return Response({'detail': str(e)}, status=502)

    @action(detail=False, methods=['get'], url_path='estatisticas')
    def estatisticas(self, request):
        hoje = timezone.localtime(timezone.now()).date()
        mes  = timezone.localtime(timezone.now()).replace(day=1).date()

        qs_hoje = PedidoIFood.objects.filter(ifood_criado_em__date=hoje)
        qs_mes  = PedidoIFood.objects.filter(ifood_criado_em__date__gte=mes)

        por_status = {}
        for row in PedidoIFood.objects.values('status').annotate(total=Count('id')):
            por_status[row['status']] = row['total']

        return Response({
            'hoje': {
                'pedidos':     qs_hoje.count(),
                'receita':     float(qs_hoje.aggregate(s=Sum('total_valor'))['s'] or 0),
                'confirmados': qs_hoje.filter(status='CONFIRMED').count(),
                'cancelados':  qs_hoje.filter(status='CANCELLED').count(),
            },
            'mes': {
                'pedidos': qs_mes.count(),
                'receita': float(qs_mes.aggregate(s=Sum('total_valor'))['s'] or 0),
            },
            'pendentes':   por_status.get('PLACED', 0),
            'por_status':  por_status,
            'total_geral': PedidoIFood.objects.count(),
        })


    @action(detail=True, methods=['post'], url_path='criar-cliente')
    def criar_cliente(self, request, pk=None):
        """
        POST /api/v1/ifood/pedidos/{id}/criar-cliente/
        Cria um Cliente CRM com os dados do pedido iFood e vincula ao pedido.
        Retorna 400 se já houver cliente vinculado, 409 se telefone já existir.
        """
        from clientes.models import Cliente, Endereco
        from clientes.serializers import ClienteDetailSerializer, ClienteListSerializer

        pedido = self.get_object()

        if pedido.cliente:
            return Response(
                {'detail': 'Este pedido já possui um cliente vinculado. Use "Vincular Cliente" para trocar.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        nome     = pedido.cliente_nome or ''
        telefone = pedido.cliente_telefone or ''
        addr     = pedido.endereco_entrega or {}

        if not nome:
            return Response(
                {'detail': 'O pedido não possui nome do cliente para criar cadastro.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if telefone:
            sufixo = telefone[-8:] if len(telefone) >= 8 else telefone
            existente = Cliente.objects.filter(telefone_principal__endswith=sufixo).first()
            if existente:
                return Response(
                    {
                        'detail': f'Já existe um cliente com este telefone: {existente.nome} (ID {existente.id}). Use "Vincular Cliente" para associar.',
                        'cliente_existente': ClienteListSerializer(existente).data,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        cliente = Cliente.objects.create(
            nome               = nome,
            telefone_principal = telefone,
            ifood_customer_id  = pedido.cliente_ifood_id or '',
            status             = 'ativo',
        )

        logradouro = addr.get('streetName', '') or addr.get('formattedAddress', '')
        if logradouro:
            Endereco.objects.create(
                cliente     = cliente,
                logradouro  = logradouro,
                numero      = addr.get('streetNumber', '') or addr.get('number', ''),
                complemento = addr.get('complement', ''),
                bairro      = addr.get('neighborhood', ''),
                cidade      = addr.get('city', ''),
                estado      = addr.get('state', ''),
                cep         = addr.get('postalCode', ''),
                principal   = True,
            )

        pedido.cliente = cliente
        pedido.save(update_fields=['cliente'])

        try:
            from pedidos.models import PedidoUnificado
            PedidoUnificado.objects.filter(canal='ifood', origem_id=pedido.pk).update(cliente=cliente)
        except Exception as e:
            logger.warning('criar_cliente: falha ao propagar para PedidoUnificado: %s', e)

        serializer = ClienteDetailSerializer(cliente)
        return Response(
            {'detail': f'Cliente "{cliente.nome}" criado e vinculado com sucesso.', 'cliente': serializer.data},
            status=status.HTTP_201_CREATED,
        )


class EventoPollingViewSet(CsrfExemptMixin, viewsets.ReadOnlyModelViewSet):
    """Log de eventos de polling — somente leitura."""
    queryset           = EventoPollingIFood.objects.all()
    serializer_class   = EventoPollingSerializer
    permission_classes = [AllowAny]
    ordering           = ['-ifood_criado_em']