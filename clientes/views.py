"""
ARQUIVO COMPLETO: clientes/views.py — Fase 4B (Eventos)
Substitui o arquivo existente.

Alteração em relação à versão anterior (Fase 3 / PDV):
  - Bloco de Eventos adicionado na action `historico`
  - Métricas por canal incluem 'eventos'
"""
from django.db.models import Q, Sum, Count, Avg
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import Cliente, Endereco, TagCliente
from .serializers import (
    ClienteListSerializer, ClienteDetailSerializer,
    EnderecoSerializer, TagSerializer
)
from usuarios.authentication import TokenAuthentication
from auditoria.models import LogAuditoria
from auditoria.utils import registrar
from auditoria.mixins import AuditoriaDestroyMixin


class CsrfExemptMixin:
    """Remove SessionAuthentication — evita 403 em POSTs sem CSRF token."""
    authentication_classes = []


class ClienteViewSet(AuditoriaDestroyMixin, CsrfExemptMixin, viewsets.ModelViewSet):
    queryset = Cliente.objects.prefetch_related('enderecos', 'tags').all()
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['nome', 'criado_em', 'atualizado_em', 'status']
    ordering = ['-criado_em']
    authentication_classes = [TokenAuthentication]
    campos_log_exclusao = ['nome', 'telefone_principal']

    def get_permissions(self):
        if self.action in ('destroy', 'remover_endereco'):
            return [IsAuthenticated()]
        return [AllowAny()]

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

    # ── Endereços ─────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='enderecos')
    def adicionar_endereco(self, request, pk=None):
        cliente = self.get_object()
        serializer = EnderecoSerializer(data=request.data, context={'cliente': cliente, 'request': request})
        if serializer.is_valid():
            serializer.save(cliente=cliente)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path=r'enderecos/(?P<endereco_id>[^/.]+)/editar')
    def editar_endereco(self, request, pk=None, endereco_id=None):
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
        registrar(
            request.user, LogAuditoria.ACAO_REGISTRO_EXCLUIDO,
            detalhes={
                'model': 'Endereco', 'id': endereco.id, 'descricao': str(endereco),
                'cliente_id': cliente.id, 'cliente_nome': cliente.nome,
            },
            request=request,
        )
        endereco.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Status ────────────────────────────────────────────────────────────────

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

    # ── Estatísticas gerais ───────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='estatisticas')
    def estatisticas(self, request):
        total       = Cliente.objects.count()
        ativos      = Cliente.objects.filter(status='ativo').count()
        inativos    = Cliente.objects.filter(status='inativo').count()
        bloqueados  = Cliente.objects.filter(status='bloqueado').count()
        com_ifood   = Cliente.objects.exclude(ifood_customer_id__isnull=True).exclude(ifood_customer_id='').count()
        com_anotaai = Cliente.objects.exclude(anotaai_customer_id__isnull=True).exclude(anotaai_customer_id='').count()
        return Response({
            'total':       total,
            'ativos':      ativos,
            'inativos':    inativos,
            'bloqueados':  bloqueados,
            'com_ifood':   com_ifood,
            'com_anotaai': com_anotaai,
        })

    # ── Histórico unificado ───────────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='historico')
    def historico(self, request, pk=None):
        """
        GET /api/v1/clientes/{id}/historico/
        GET /api/v1/clientes/{id}/historico/?canal=ifood|pdv|eventos

        Retorna pedidos de todos os canais vinculados ao cliente + métricas.
        Pedidos ordenados por data decrescente.
        """
        cliente = self.get_object()
        canal   = request.query_params.get('canal')  # filtro opcional por canal

        pedidos_list = []

        metricas = {
            'total_pedidos':   0,
            'total_gasto':     0.0,
            'ticket_medio':    0.0,
            'ultimo_pedido_em': None,
            'por_canal': {
                'ifood':   {'total': 0, 'gasto': 0.0},
                'anotaai': {'total': 0, 'gasto': 0.0},
                'pdv':     {'total': 0, 'gasto': 0.0},
                'eventos': {'total': 0, 'gasto': 0.0},
            },
        }

        # ── iFood ─────────────────────────────────────────────────────────────
        if canal in (None, 'ifood'):
            from ifood.models import PedidoIFood
            pedidos_ifood = (
                PedidoIFood.objects
                .filter(cliente=cliente)
                .prefetch_related('itens')
                .order_by('-criado_em')
            )
            for p in pedidos_ifood:
                pedidos_list.append({
                    'canal':        'ifood',
                    'canal_label':  'iFood',
                    'origem_id':    p.pk,
                    'numero':       p.display_id or str(p.pk),
                    'status':       p.status,
                    'status_label': p.get_status_display(),
                    'tipo':         p.order_type,
                    'tipo_label':   p.get_order_type_display(),
                    'valor':        float(p.total_valor or 0),
                    'pagamento':    p.payment_method,
                    'data':         p.criado_em.isoformat() if p.criado_em else None,
                    'itens_count':  p.itens.count(),
                })
            total_ifood = pedidos_ifood.count()
            gasto_ifood = float(
                pedidos_ifood.filter(status='CONCLUDED')
                .aggregate(t=Sum('total_valor'))['t'] or 0
            )
            metricas['por_canal']['ifood'] = {'total': total_ifood, 'gasto': gasto_ifood}

        # ── PDV Próprio ───────────────────────────────────────────────────────
        if canal in (None, 'pdv'):
            from pdv.models import PedidoPDV
            pedidos_pdv = (
                PedidoPDV.objects
                .filter(cliente=cliente)
                .prefetch_related('itens')
                .order_by('-criado_em')
            )
            for p in pedidos_pdv:
                pedidos_list.append({
                    'canal':        'pdv',
                    'canal_label':  'PDV Próprio',
                    'origem_id':    p.pk,
                    'numero':       p.numero,
                    'status':       p.status,
                    'status_label': p.get_status_display(),
                    'tipo':         p.tipo,
                    'tipo_label':   p.get_tipo_display(),
                    'valor':        float(p.total or 0),
                    'pagamento':    p.pagamento,
                    'data':         p.criado_em.isoformat() if p.criado_em else None,
                    'itens_count':  p.itens.count(),
                })
            total_pdv = pedidos_pdv.count()
            gasto_pdv = float(
                pedidos_pdv.filter(status='concluido')
                .aggregate(t=Sum('total'))['t'] or 0
            )
            metricas['por_canal']['pdv'] = {'total': total_pdv, 'gasto': gasto_pdv}

        # ── Eventos ───────────────────────────────────────────────────────────
        if canal in (None, 'eventos'):
            from eventos.models import Evento
            eventos_qs = (
                Evento.objects
                .filter(cliente=cliente)
                .prefetch_related('itens')
                .order_by('-data_evento')
            )
            for ev in eventos_qs:
                pedidos_list.append({
                    'canal':          'eventos',
                    'canal_label':    'Eventos',
                    'origem_id':      ev.pk,
                    'numero':         ev.numero,
                    'status':         ev.status,
                    'status_label':   ev.get_status_display(),
                    'tipo':           ev.tipo_evento,
                    'tipo_label':     ev.get_tipo_evento_display(),
                    'tipo_entrega':   ev.tipo_entrega,
                    'tipo_entrega_label': ev.get_tipo_entrega_display(),
                    'data_evento':    str(ev.data_evento),
                    'hora_evento':    str(ev.hora_evento) if ev.hora_evento else None,
                    'valor':          float(ev.valor_total or 0),
                    'sinal_pago':     float(ev.sinal_pago or 0),
                    'saldo_restante': float(ev.saldo_restante or 0),
                    'data':           ev.criado_em.isoformat() if ev.criado_em else None,
                    'itens_count':    ev.itens.count(),
                })
            total_eventos = eventos_qs.count()
            gasto_eventos = float(
                eventos_qs.filter(status='entregue')
                .aggregate(t=Sum('valor_total'))['t'] or 0
            )
            metricas['por_canal']['eventos'] = {'total': total_eventos, 'gasto': gasto_eventos}

        # ── Anota AI (placeholder — implementar quando o app existir) ─────────
        if canal in (None, 'anotaai'):
            # from anotaai.models import PedidoAnotaAI
            # pedidos_anotaai = PedidoAnotaAI.objects.filter(cliente=cliente)...
            metricas['por_canal']['anotaai'] = {'total': 0, 'gasto': 0.0}

        # ── Ordenação global por data decrescente ─────────────────────────────
        pedidos_list.sort(key=lambda p: p.get('data') or '', reverse=True)

        # ── Métricas agregadas ────────────────────────────────────────────────
        total_pedidos = sum(v['total'] for v in metricas['por_canal'].values())
        total_gasto   = sum(v['gasto'] for v in metricas['por_canal'].values())

        metricas['total_pedidos'] = total_pedidos
        metricas['total_gasto']   = round(total_gasto, 2)
        metricas['ticket_medio']  = round(total_gasto / total_pedidos, 2) if total_pedidos else 0.0
        metricas['ultimo_pedido_em'] = pedidos_list[0]['data'] if pedidos_list else None

        return Response({
            'pedidos':  pedidos_list,
            'metricas': metricas,
            'total':    len(pedidos_list),
        })


# ─────────────────────────────────────────────────────────────────────────────
# Tags
# ─────────────────────────────────────────────────────────────────────────────

class TagViewSet(AuditoriaDestroyMixin, CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = TagCliente.objects.all()
    serializer_class   = TagSerializer
    filter_backends    = [filters.OrderingFilter]
    ordering           = ['nome']
    authentication_classes = [TokenAuthentication]
    campos_log_exclusao = ['nome']

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated()]
        return [AllowAny()]