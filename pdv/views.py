from django.db.models import Q, Sum, Count
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import (
    CategoriaProduto, Produto, PedidoPDV, ItemPedidoPDV, TaxaEntregaBairro, ConfiguracaoEntrega,
    ItemKit, FaixaPreco,
)
from notificacoes.servico import notificar, _fone_pedido
from usuarios.authentication import TokenAuthentication
from auditoria.models import LogAuditoria
from auditoria.utils import registrar
from auditoria.mixins import AuditoriaDestroyMixin


def _notificar_pdv(pedido, mensagem):
    notificar(_fone_pedido(pedido), mensagem, cliente=pedido.cliente, tipo='pedido')
from .serializers import (
    CategoriaProdutoSerializer,
    ProdutoSerializer,
    FaixaPrecoSerializer,
    ItemKitSerializer,
    PedidoPDVListSerializer,
    PedidoPDVDetailSerializer,
    PedidoPDVCreateSerializer,
    ItemPedidoPDVCreateSerializer,
    TaxaEntregaBairroSerializer,
    ConfiguracaoEntregaSerializer,
)


class CsrfExemptMixin:
    authentication_classes = []


# ─── Categorias ──────────────────────────────────────────────────────────────

class CategoriaProdutoViewSet(AuditoriaDestroyMixin, CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = CategoriaProduto.objects.all()
    serializer_class   = CategoriaProdutoSerializer
    authentication_classes = [TokenAuthentication]
    campos_log_exclusao = ['nome']

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated()]
        return [AllowAny()]


# ─── Taxas de Entrega por Bairro ─────────────────────────────────────────────

class TaxaEntregaBairroViewSet(AuditoriaDestroyMixin, CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = TaxaEntregaBairro.objects.all()
    serializer_class   = TaxaEntregaBairroSerializer
    authentication_classes = [TokenAuthentication]
    campos_log_exclusao = ['bairro']

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        qs    = super().get_queryset()
        ativo = self.request.query_params.get('ativo')
        if ativo == 'true':
            qs = qs.filter(ativo=True)
        elif ativo == 'false':
            qs = qs.filter(ativo=False)
        return qs


class ConfiguracaoEntregaViewSet(CsrfExemptMixin, viewsets.GenericViewSet):
    serializer_class   = ConfiguracaoEntregaSerializer
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action == 'partial_update':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_object(self):
        return ConfiguracaoEntrega.get()

    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(self.get_object()).data)

    def partial_update(self, request, pk=None):
        config  = self.get_object()
        campos  = list(request.data.keys())
        antes   = {c: str(getattr(config, c)) for c in campos if hasattr(config, c)}
        serializer = ConfiguracaoEntregaSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        depois = {c: str(getattr(config, c)) for c in campos if hasattr(config, c)}
        registrar(
            request.user, LogAuditoria.ACAO_CONFIG_ENTREGA_ALTERADA,
            detalhes={'antes': antes, 'depois': depois},
            request=request,
        )
        return Response(serializer.data)


# ─── Produtos ────────────────────────────────────────────────────────────────

class ProdutoViewSet(AuditoriaDestroyMixin, CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = Produto.objects.select_related('categoria').all()
    serializer_class   = ProdutoSerializer
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ['nome', 'preco', 'categoria__ordem']
    ordering           = ['categoria__ordem', 'nome']
    authentication_classes = [TokenAuthentication]
    campos_log_exclusao = ['nome']

    def get_permissions(self):
        if self.action in ('destroy', 'remover_faixa_preco', 'remover_item_kit'):
            return [IsAuthenticated()]
        return [AllowAny()]

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

    # ── Faixas de preço ────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='faixas-preco')
    def adicionar_faixa_preco(self, request, pk=None):
        produto    = self.get_object()
        serializer = FaixaPrecoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(produto=produto)
        return Response(ProdutoSerializer(produto).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], url_path=r'faixas-preco/(?P<faixa_id>[^/.]+)')
    def editar_faixa_preco(self, request, pk=None, faixa_id=None):
        produto = self.get_object()
        try:
            faixa = produto.faixas_preco.get(pk=faixa_id)
        except FaixaPreco.DoesNotExist:
            return Response({'detail': 'Faixa não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = FaixaPrecoSerializer(faixa, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProdutoSerializer(produto).data)

    @action(detail=True, methods=['delete'], url_path=r'faixas-preco/(?P<faixa_id>[^/.]+)/remover')
    def remover_faixa_preco(self, request, pk=None, faixa_id=None):
        produto = self.get_object()
        try:
            faixa = produto.faixas_preco.get(pk=faixa_id)
        except FaixaPreco.DoesNotExist:
            return Response({'detail': 'Faixa não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        registrar(
            request.user, LogAuditoria.ACAO_REGISTRO_EXCLUIDO,
            detalhes={
                'model': 'FaixaPreco', 'id': faixa.id, 'descricao': str(faixa),
                'produto_id': produto.id, 'produto_nome': produto.nome,
            },
            request=request,
        )
        faixa.delete()
        return Response(ProdutoSerializer(produto).data)

    # ── Itens de Kit ────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='itens-kit')
    def adicionar_item_kit(self, request, pk=None):
        produto = self.get_object()
        if produto.tipo != 'kit':
            return Response({'detail': 'Só é possível adicionar componentes a produtos do tipo "kit".'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ItemKitSerializer(data=request.data, context={'kit': produto})
        serializer.is_valid(raise_exception=True)
        serializer.save(kit=produto)
        return Response(ProdutoSerializer(produto).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path=r'itens-kit/(?P<item_id>[^/.]+)')
    def remover_item_kit(self, request, pk=None, item_id=None):
        produto = self.get_object()
        try:
            item = produto.itens_kit.get(pk=item_id)
        except ItemKit.DoesNotExist:
            return Response({'detail': 'Componente não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        registrar(
            request.user, LogAuditoria.ACAO_REGISTRO_EXCLUIDO,
            detalhes={
                'model': 'ItemKit', 'id': item.id, 'descricao': str(item),
                'kit_id': produto.id, 'kit_nome': produto.nome,
            },
            request=request,
        )
        item.delete()
        return Response(ProdutoSerializer(produto).data)

    # ── Preço resolvido por quantidade/canal ───────────────────────────────

    @action(detail=True, methods=['get'], url_path='preco')
    def preco(self, request, pk=None):
        produto = self.get_object()
        try:
            quantidade = int(request.query_params.get('quantidade', 1))
        except (TypeError, ValueError):
            quantidade = 1
        canal = request.query_params.get('canal') or None
        return Response({'preco': float(produto.preco_para(quantidade=quantidade, canal=canal))})


# ─── Pedidos PDV ─────────────────────────────────────────────────────────────

class PedidoPDVViewSet(AuditoriaDestroyMixin, CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = PedidoPDV.objects.prefetch_related('itens').select_related('cliente').all()
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ['criado_em', 'total', 'status']
    ordering           = ['-criado_em']
    authentication_classes = [TokenAuthentication]
    campos_log_exclusao = ['numero', 'total']

    def get_permissions(self):
        if self.action in ('destroy', 'remover_item'):
            return [IsAuthenticated()]
        return [AllowAny()]

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
        _notificar_pdv(pedido, f'✅ Pedido #{pedido.numero} confirmado! Já estamos separando tudo com carinho. 🍬')
        return Response(PedidoPDVDetailSerializer(pedido).data)

    @action(detail=True, methods=['post'], url_path='iniciar-preparo')
    def iniciar_preparo(self, request, pk=None):
        pedido = self.get_object()
        if pedido.status not in ('confirmado',):
            return Response({'detail': 'Pedido precisa estar confirmado.'}, status=status.HTTP_400_BAD_REQUEST)
        pedido.status = 'em_preparo'
        pedido.save(update_fields=['status', 'atualizado_em'])
        _notificar_pdv(pedido, f'👨‍🍳 Seu pedido #{pedido.numero} entrou em preparo! Em breve ficará pronto.')
        return Response(PedidoPDVDetailSerializer(pedido).data)

    @action(detail=True, methods=['post'], url_path='marcar-pronto')
    def marcar_pronto(self, request, pk=None):
        pedido = self.get_object()
        if pedido.status != 'em_preparo':
            return Response({'detail': 'Pedido precisa estar em preparo.'}, status=status.HTTP_400_BAD_REQUEST)
        pedido.status = 'pronto'
        pedido.save(update_fields=['status', 'atualizado_em'])
        _notificar_pdv(pedido, f'🎉 Seu pedido #{pedido.numero} está pronto! Pode vir retirar na Arretado Doces.')
        return Response(PedidoPDVDetailSerializer(pedido).data)

    @action(detail=True, methods=['post'], url_path='concluir')
    def concluir(self, request, pk=None):
        pedido = self.get_object()
        if not pedido.pode_concluir:
            return Response({'detail': 'Pedido não pode ser concluído neste status.'}, status=status.HTTP_400_BAD_REQUEST)
        pedido.status = 'concluido'
        pedido.save(update_fields=['status', 'atualizado_em'])
        _notificar_pdv(pedido, f'💚 Pedido #{pedido.numero} concluído! Obrigado pela preferência. Volte sempre! 🍬')
        return Response(PedidoPDVDetailSerializer(pedido).data)

    @action(detail=True, methods=['post'], url_path='cancelar')
    def cancelar(self, request, pk=None):
        pedido = self.get_object()
        if not pedido.pode_cancelar:
            return Response({'detail': 'Pedido já foi concluído ou cancelado.'}, status=status.HTTP_400_BAD_REQUEST)
        pedido.status = 'cancelado'
        pedido.save(update_fields=['status', 'atualizado_em'])
        _notificar_pdv(pedido, f'❌ Seu pedido #{pedido.numero} foi cancelado. Entre em contato se precisar de ajuda.')
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
        registrar(
            request.user, LogAuditoria.ACAO_REGISTRO_EXCLUIDO,
            detalhes={
                'model': 'ItemPedidoPDV', 'id': item.id, 'descricao': str(item),
                'pedido_id': pedido.id, 'pedido_numero': pedido.numero,
            },
            request=request,
        )
        item.delete()
        pedido.recalcular_totais()
        return Response(PedidoPDVDetailSerializer(pedido).data)

    # ── Estatísticas ──────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='estatisticas')
    def estatisticas(self, request):
        from django.utils import timezone
        from datetime import timedelta
        hoje = timezone.localtime(timezone.now()).date()
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
