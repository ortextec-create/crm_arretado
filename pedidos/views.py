"""
ARQUIVO COMPLETO: pedidos/views.py — Fase 4
Adicione este arquivo ao app pedidos/.
Registre no pedidos/urls.py e config/urls.py conforme instruções abaixo.
"""
from django.db.models import Q
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from clientes.models import Cliente
from clientes.serializers import ClienteListSerializer
from .models import PedidoUnificado
from .serializers import PedidoUnificadoSerializer


class CsrfExemptMixin:
    """Remove SessionAuthentication — evita 403 em POSTs sem CSRF token."""
    authentication_classes = []


class PedidoUnificadoViewSet(CsrfExemptMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet somente-leitura do PedidoUnificado.
    Expõe listagem, detalhe e a action de vinculação manual de clientes.

    PedidoUnificado nunca é escrito diretamente — apenas via signals dos
    apps de canal (ifood/, pdv/, anotaai/). A única escrita permitida aqui
    é a atualização do campo `cliente` (FK para o CRM).
    """
    queryset = PedidoUnificado.objects.select_related('cliente').all()
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering = ['-pedido_em']
    serializer_class = PedidoUnificadoSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        # Filtro por canal
        canal = params.get('canal')
        if canal:
            qs = qs.filter(canal=canal)

        # Filtro por status
        status_param = params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        # Apenas sem cliente vinculado
        sem_cliente = params.get('sem_cliente')
        if sem_cliente == 'true':
            qs = qs.filter(cliente__isnull=True)

        # Busca por número, nome ou telefone do cliente
        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(numero__icontains=search) |
                Q(cliente_nome__icontains=search) |
                Q(cliente_telefone__icontains=search)
            )

        return qs

    # ── Action: vincular cliente ───────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='vincular-cliente')
    def vincular_cliente(self, request, pk=None):
        """
        Vincula (ou desvincula) manualmente um cliente do CRM ao PedidoUnificado
        e propaga o vínculo ao pedido nativo do canal correspondente.

        POST /api/v1/pedidos/{id}/vincular-cliente/
        Body: { "cliente_id": 42 }          → vincula
              { "cliente_id": null }         → desvincula
        """
        pedido = self.get_object()
        cliente_id = request.data.get('cliente_id')

        if cliente_id is None:
            # Desvincular
            self._propagar_cliente(pedido, cliente=None)
            pedido.cliente = None
            pedido.save(update_fields=['cliente'])
            return Response({'detail': 'Cliente desvinculado com sucesso.'})

        try:
            cliente = Cliente.objects.get(pk=cliente_id)
        except Cliente.DoesNotExist:
            return Response(
                {'detail': 'Cliente não encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        self._propagar_cliente(pedido, cliente=cliente)
        pedido.cliente = cliente
        pedido.save(update_fields=['cliente'])

        return Response({
            'detail': 'Cliente vinculado com sucesso.',
            'cliente': ClienteListSerializer(cliente).data,
        })

    def _propagar_cliente(self, pedido_unificado, cliente):
        """
        Propaga a associação de cliente ao modelo nativo do canal.
        Nunca falha o fluxo principal — erros são logados silenciosamente.
        """
        try:
            if pedido_unificado.canal == 'ifood':
                from ifood.models import PedidoIFood
                PedidoIFood.objects.filter(pk=pedido_unificado.origem_id).update(
                    cliente=cliente
                )
            elif pedido_unificado.canal == 'pdv':
                from pdv.models import PedidoPDV
                PedidoPDV.objects.filter(pk=pedido_unificado.origem_id).update(
                    cliente=cliente
                )
            # anotaai: adicionar aqui quando implementado
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                'Fase4: falha ao propagar vínculo de cliente ao canal %s (origem_id=%s): %s',
                pedido_unificado.canal, pedido_unificado.origem_id, e,
            )

    # ── Action: estatísticas de pedidos sem vínculo ───────────────────────

    @action(detail=False, methods=['get'], url_path='sem-cliente')
    def sem_cliente(self, request):
        """
        GET /api/v1/pedidos/sem-cliente/
        Retorna contagens de pedidos sem cliente vinculado, agrupados por canal.
        Útil para o badge de alertas no Sidebar.
        """
        from django.db.models import Count

        contagens = (
            PedidoUnificado.objects
            .filter(cliente__isnull=True)
            .values('canal')
            .annotate(total=Count('id'))
            .order_by('canal')
        )

        total = sum(item['total'] for item in contagens)

        return Response({
            'total': total,
            'por_canal': {item['canal']: item['total'] for item in contagens},
        })
