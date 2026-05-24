"""
ARQUIVO COMPLETO: clientes/views.py — Fase 3
Substitui o arquivo existente.
"""
from django.db.models import Q, Sum, Count, Avg
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import Cliente, Endereco, TagCliente
from .serializers import (
    ClienteListSerializer, ClienteDetailSerializer,
    EnderecoSerializer, TagSerializer
)


class CsrfExemptMixin:
    """Remove SessionAuthentication — evita 403 em POSTs sem CSRF token."""
    authentication_classes = []


class ClienteViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    queryset = Cliente.objects.prefetch_related('enderecos', 'tags').all()
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['nome', 'criado_em', 'atualizado_em', 'status']
    ordering = ['-criado_em']

    def get_serializer_class(self):
        if self.action == 'list':
            return ClienteListSerializer
        return ClienteDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(nome__icontains=search) |
                Q(cpf__icontains=search) |
                Q(email__icontains=search) |
                Q(telefone_principal__icontains=search)
            )

        status_filter = params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        cidade = params.get('cidade')
        if cidade:
            qs = qs.filter(enderecos__cidade__icontains=cidade)

        tag_id = params.get('tag')
        if tag_id:
            qs = qs.filter(tags__id=tag_id)

        com_ifood = params.get('com_ifood')
        if com_ifood == 'true':
            qs = qs.exclude(ifood_customer_id__isnull=True).exclude(ifood_customer_id='')
        elif com_ifood == 'false':
            qs = qs.filter(Q(ifood_customer_id__isnull=True) | Q(ifood_customer_id=''))

        return qs.distinct()

    # ── Endereços ──────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='enderecos')
    def adicionar_endereco(self, request, pk=None):
        cliente = self.get_object()
        serializer = EnderecoSerializer(data=request.data, context={'cliente': cliente, 'request': request})
        if serializer.is_valid():
            serializer.save(cliente=cliente)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path=r'enderecos/(?P<endereco_id>[^/.]+)')
    def atualizar_endereco(self, request, pk=None, endereco_id=None):
        cliente = self.get_object()
        try:
            endereco = cliente.enderecos.get(pk=endereco_id)
        except Endereco.DoesNotExist:
            return Response({'detail': 'Endereço não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = EnderecoSerializer(endereco, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path=r'enderecos/(?P<endereco_id>[^/.]+)/remover')
    def remover_endereco(self, request, pk=None, endereco_id=None):
        cliente = self.get_object()
        try:
            endereco = cliente.enderecos.get(pk=endereco_id)
        except Endereco.DoesNotExist:
            return Response({'detail': 'Endereço não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        endereco.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Status ─────────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='bloquear')
    def bloquear(self, request, pk=None):
        cliente = self.get_object()
        cliente.status = 'bloqueado'
        cliente.save(update_fields=['status', 'atualizado_em'])
        return Response({'status': 'bloqueado'})

    @action(detail=True, methods=['post'], url_path='ativar')
    def ativar(self, request, pk=None):
        cliente = self.get_object()
        cliente.status = 'ativo'
        cliente.save(update_fields=['status', 'atualizado_em'])
        return Response({'status': 'ativo'})

    # ── Estatísticas gerais ────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='estatisticas')
    def estatisticas(self, request):
        total      = Cliente.objects.count()
        ativos     = Cliente.objects.filter(status='ativo').count()
        inativos   = Cliente.objects.filter(status='inativo').count()
        bloqueados = Cliente.objects.filter(status='bloqueado').count()
        com_ifood  = Cliente.objects.exclude(ifood_customer_id__isnull=True).exclude(ifood_customer_id='').count()
        com_anotaai = Cliente.objects.exclude(anotaai_customer_id__isnull=True).exclude(anotaai_customer_id='').count()
        return Response({
            'total': total,
            'ativos': ativos,
            'inativos': inativos,
            'bloqueados': bloqueados,
            'com_ifood': com_ifood,
            'com_anotaai': com_anotaai,
        })

    # ── FASE 3: Histórico unificado ────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='historico')
    def historico(self, request, pk=None):
        """
        GET /api/v1/clientes/{id}/historico/
        Retorna pedidos de todos os canais vinculados ao cliente + métricas.
        Canais ativos: iFood
        Canais planejados: Anota AI, PDV Próprio
        """
        from ifood.models import PedidoIFood
        from ifood.serializers import PedidoIFoodListSerializer

        cliente = self.get_object()
        canal = request.query_params.get('canal')  # filtro opcional: ifood | anotaai | pdv

        # ── iFood ──────────────────────────────────────────────────────────────
        pedidos_ifood_qs = cliente.pedidos_ifood.all().order_by('-ifood_criado_em')
        if canal and canal != 'ifood':
            pedidos_ifood_qs = pedidos_ifood_qs.none()

        pedidos_ifood_data = PedidoIFoodListSerializer(pedidos_ifood_qs, many=True).data

        historico = []
        for p in pedidos_ifood_data:
            historico.append({
                'id':           p['id'],
                'canal':        'ifood',
                'canal_label':  'iFood',
                'numero':       p['display_id'] or p['ifood_order_id'][:8],
                'status':       p['status'],
                'status_label': p['status_display'],
                'tipo':         p['order_type'],
                'tipo_label':   p['order_type_display'],
                'total':        float(p['total_valor']),
                'pagamento':    p['payment_method'],
                'data':         p['ifood_criado_em'],
                'pode_confirmar': p['pode_confirmar'],
                'pode_cancelar':  p['pode_cancelar'],
                'origem_id':    p['id'],
            })

        # ── Anota AI (placeholder fase futura) ─────────────────────────────────
        # pedidos_anotaai_qs = cliente.pedidos_anotaai.all().order_by('-criado_em')
        # ...

        # ── PDV Próprio (placeholder fase futura) ──────────────────────────────
        # pedidos_pdv_qs = cliente.pedidos_pdv.all().order_by('-criado_em')
        # ...

        # Ordena tudo por data decrescente
        historico.sort(key=lambda x: x['data'] or '', reverse=True)

        # ── Métricas (apenas pedidos não cancelados) ───────────────────────────
        agg_ifood = pedidos_ifood_qs.exclude(
            status__in=['CANCELLED', 'CANCELLATION_REQUESTED']
        ).aggregate(
            total_gasto=Sum('total_valor'),
            total_pedidos=Count('id'),
            ticket_medio=Avg('total_valor'),
        )

        ultimo = pedidos_ifood_qs.first()

        metricas = {
            'total_pedidos':    agg_ifood['total_pedidos'] or 0,
            'total_gasto':      float(agg_ifood['total_gasto'] or 0),
            'ticket_medio':     float(agg_ifood['ticket_medio'] or 0),
            'ultimo_pedido_em': ultimo.ifood_criado_em if ultimo else None,
            'por_canal': {
                'ifood':   pedidos_ifood_qs.count(),
                'anotaai': 0,
                'pdv':     0,
            },
        }

        return Response({
            'pedidos':  historico,
            'metricas': metricas,
            'total':    len(historico),
        })


class TagViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    queryset = TagCliente.objects.all()
    serializer_class = TagSerializer
    permission_classes = [AllowAny]
