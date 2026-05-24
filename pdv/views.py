from django.db.models import Q, Sum, Count
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import CategoriaProduto, Produto, PedidoPDV, ItemPedidoPDV
from .serializers import (
    CategoriaProdutoSerializer,
    ProdutoSerializer,
    PedidoPDVListSerializer,
    PedidoPDVDetailSerializer,
    PedidoPDVCreateSerializer,
    ItemPedidoPDVCreateSerializer,
)


class CsrfExemptMixin:
    authentication_classes = []


# ─── Categorias ──────────────────────────────────────────────────────────────

class CategoriaProdutoViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = CategoriaProduto.objects.all()
    serializer_class   = CategoriaProdutoSerializer
    permission_classes = [AllowAny]


# ─── Produtos ────────────────────────────────────────────────────────────────

class ProdutoViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = Produto.objects.select_related('categoria').all()
    serializer_class   = ProdutoSerializer
    permission_classes = [AllowAny]
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ['nome', 'preco', 'categoria__ordem']
    ordering           = ['categoria__ordem', 'nome']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(nome__icontains=search) | Q(descricao__icontains=search))

        categoria = params.get('categoria')
        if categoria:
            qs = qs.filter(categoria_id=categoria)

        ativo = params.get('ativo')
        if ativo == 'true':
            qs = qs.filter(ativo=True)
        elif ativo == 'false':
            qs = qs.filter(ativo=False)

        return qs

    @action(detail=True, methods=['post'], url_path='ativar')
    def ativar(self, request, pk=None):
        produto = self.get_object()
        produto.ativo = True
        produto.save(update_fields=['ativo', 'atualizado_em'])
        return Response({'ativo': True})

    @action(detail=True, methods=['post'], url_path='desativar')
    def desativar(self, request, pk=None):
        produto = self.get_object()
        produto.ativo = False
        produto.save(update_fields=['ativo', 'atualizado_em'])
        return Response({'ativo': False})


# ─── Pedidos PDV ─────────────────────────────────────────────────────────────

class PedidoPDVViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = PedidoPDV.objects.prefetch_related('itens').select_related('cliente').all()
    permission_classes = [AllowAny]
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ['criado_em', 'total', 'status']
    ordering           = ['-criado_em']

    def get_serializer_class(self):
        if self.action == 'create':
            return PedidoPDVCreateSerializer
        if self.action in ('retrieve', 'update', 'partial_update'):
            return PedidoPDVDetailSerializer
        return PedidoPDVListSerializer

    def get_queryset(self):
        qs     = super().get_queryset()
        params = self.request.query_params

        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(numero__icontains=search) |
                Q(cliente_nome__icontains=search) |
                Q(cliente_telefone__icontains=search) |
                Q(cliente__nome__icontains=search)
            )

        st = params.get('status')
        if st:
            qs = qs.filter(status=st)

        tipo = params.get('tipo')
        if tipo:
            qs = qs.filter(tipo=tipo)

        return qs

    # ── Ações de status ────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='confirmar')
    def confirmar(self, request, pk=None):
        pedido = self.get_object()
        if not pedido.pode_confirmar:
            return Response({'detail': 'Pedido não pode ser confirmado.'}, status=status.HTTP_400_BAD_REQUEST)
        pedido.status = 'confirmado'
        pedido.save(update_fields=['status', 'atualizado_em'])
        return Response(PedidoPDVDetailSerializer(pedido).data)

    @action(detail=True, methods=['post'], url_path='iniciar-preparo')
    def iniciar_preparo(self, request, pk=None):
        pedido = self.get_object()
        if pedido.status not in ('confirmado',):
            return Response({'detail': 'Pedido precisa estar confirmado.'}, status=status.HTTP_400_BAD_REQUEST)
        pedido.status = 'em_preparo'
        pedido.save(update_fields=['status', 'atualizado_em'])
        return Response(PedidoPDVDetailSerializer(pedido).data)

    @action(detail=True, methods=['post'], url_path='marcar-pronto')
    def marcar_pronto(self, request, pk=None):
        pedido = self.get_object()
        if pedido.status != 'em_preparo':
            return Response({'detail': 'Pedido precisa estar em preparo.'}, status=status.HTTP_400_BAD_REQUEST)
        pedido.status = 'pronto'
        pedido.save(update_fields=['status', 'atualizado_em'])
        return Response(PedidoPDVDetailSerializer(pedido).data)

    @action(detail=True, methods=['post'], url_path='concluir')
    def concluir(self, request, pk=None):
        pedido = self.get_object()
        if not pedido.pode_concluir:
            return Response({'detail': 'Pedido não pode ser concluído neste status.'}, status=status.HTTP_400_BAD_REQUEST)
        pedido.status = 'concluido'
        pedido.save(update_fields=['status', 'atualizado_em'])
        return Response(PedidoPDVDetailSerializer(pedido).data)

    @action(detail=True, methods=['post'], url_path='cancelar')
    def cancelar(self, request, pk=None):
        pedido = self.get_object()
        if not pedido.pode_cancelar:
            return Response({'detail': 'Pedido já foi concluído ou cancelado.'}, status=status.HTTP_400_BAD_REQUEST)
        pedido.status = 'cancelado'
        pedido.save(update_fields=['status', 'atualizado_em'])
        return Response(PedidoPDVDetailSerializer(pedido).data)

    # ── Gerenciar itens ────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='itens')
    def adicionar_item(self, request, pk=None):
        pedido = self.get_object()
        if pedido.status not in ('aberto', 'confirmado'):
            return Response({'detail': 'Não é possível adicionar itens neste status.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ItemPedidoPDVCreateSerializer(data=request.data)
        if serializer.is_valid():
            data  = serializer.validated_data
            qty   = data.get('quantidade', 1)
            price = data['preco_unit']
            ItemPedidoPDV.objects.create(pedido=pedido, preco_total=price * qty, **data)
            pedido.recalcular_totais()
            return Response(PedidoPDVDetailSerializer(pedido).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path=r'itens/(?P<item_id>[^/.]+)/remover')
    def remover_item(self, request, pk=None, item_id=None):
        pedido = self.get_object()
        try:
            item = pedido.itens.get(pk=item_id)
        except ItemPedidoPDV.DoesNotExist:
            return Response({'detail': 'Item não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        item.delete()
        pedido.recalcular_totais()
        return Response(PedidoPDVDetailSerializer(pedido).data)

    # ── Estatísticas ──────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='estatisticas')
    def estatisticas(self, request):
        from django.utils import timezone
        from datetime import timedelta
        hoje = timezone.now().date()
        mes_inicio = hoje.replace(day=1)

        base = PedidoPDV.objects.exclude(status='cancelado')

        agg_hoje = base.filter(criado_em__date=hoje).aggregate(
            pedidos=Count('id'), receita=Sum('total')
        )
        agg_mes = base.filter(criado_em__date__gte=mes_inicio).aggregate(
            pedidos=Count('id'), receita=Sum('total')
        )
        pendentes = PedidoPDV.objects.filter(status__in=['aberto', 'confirmado', 'em_preparo', 'pronto']).count()

        return Response({
            'hoje':      {'pedidos': agg_hoje['pedidos'] or 0, 'receita': float(agg_hoje['receita'] or 0)},
            'mes':       {'pedidos': agg_mes['pedidos'] or 0,  'receita': float(agg_mes['receita'] or 0)},
            'pendentes': pendentes,
        })
