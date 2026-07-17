from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auditoria.mixins import AuditoriaDestroyMixin
from auditoria.models import LogAuditoria
from auditoria.utils import ator_ou_none, registrar
from fichas.models import FichaTecnica
from usuarios.authentication import TokenAuthentication

from .models import ConfiguracaoEstoque, MovimentoEstoque, Producao, TelefoneAlertaEstoque
from .serializers import (
    AjusteInventarioSerializer,
    ConfiguracaoEstoqueSerializer,
    MovimentoEstoqueSerializer,
    ProducaoPreviewSerializer,
    ProducaoSerializer,
    RegistrarCompraSerializer,
    TelefoneAlertaEstoqueSerializer,
)


class CsrfExemptMixin:
    authentication_classes = []


# ─── Movimentos (ledger, só leitura) ──────────────────────────────────────────

class MovimentoEstoqueViewSet(CsrfExemptMixin, viewsets.ReadOnlyModelViewSet):
    queryset = MovimentoEstoque.objects.select_related('materia_prima', 'produto', 'criado_por').all()
    serializer_class = MovimentoEstoqueSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get('materia_prima'):
            qs = qs.filter(materia_prima_id=params['materia_prima'])
        if params.get('produto'):
            qs = qs.filter(produto_id=params['produto'])
        if params.get('tipo_movimento'):
            qs = qs.filter(tipo_movimento=params['tipo_movimento'])
        if params.get('origem_tipo'):
            qs = qs.filter(origem_tipo=params['origem_tipo'])
        if params.get('data_inicio'):
            qs = qs.filter(criado_em__date__gte=params['data_inicio'])
        if params.get('data_fim'):
            qs = qs.filter(criado_em__date__lte=params['data_fim'])
        return qs


# ─── Entrada manual de compra ─────────────────────────────────────────────────

class RegistrarCompraView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RegistrarCompraSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        item = dados['item']
        quantidade = dados['quantidade']
        valor_total = dados.get('valor_total')

        custo_unitario_snapshot = None
        if dados['tipo_item'] == 'materia_prima':
            if valor_total is not None:
                item.valor_compra = valor_total
                item.quantidade_compra = quantidade
                item.save(update_fields=['valor_compra', 'quantidade_compra', 'atualizado_em'])
            custo_unitario_snapshot = item.custo_unitario
            movimento_kwargs = {'materia_prima': item}
        else:
            if valor_total:
                custo_unitario_snapshot = valor_total / quantidade
            movimento_kwargs = {'produto': item}

        try:
            mov = MovimentoEstoque.registrar(
                tipo_movimento='entrada_compra', quantidade=quantidade,
                origem_tipo='manual', custo_unitario_snapshot=custo_unitario_snapshot,
                observacao=dados.get('numero_nota', ''), criado_por=request.user,
                **movimento_kwargs,
            )
        except DjangoValidationError as e:
            raise ValidationError(e.message_dict if hasattr(e, 'message_dict') else e.messages)

        registrar(
            request.user, LogAuditoria.ACAO_ENTRADA_ESTOQUE_REGISTRADA,
            detalhes={
                'tipo_item': dados['tipo_item'], 'item_id': item.id, 'item_nome': str(item),
                'quantidade': str(quantidade), 'numero_nota': dados.get('numero_nota', ''),
            },
            request=request,
        )
        return Response(MovimentoEstoqueSerializer(mov).data, status=status.HTTP_201_CREATED)


# ─── Ajuste de inventário ──────────────────────────────────────────────────────

class AjusteInventarioView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AjusteInventarioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        item = dados['item']
        movimento_kwargs = (
            {'materia_prima': item} if dados['tipo_item'] == 'materia_prima' else {'produto': item}
        )

        try:
            mov = MovimentoEstoque.registrar(
                tipo_movimento='ajuste_inventario', quantidade=dados['saldo_contado'],
                origem_tipo='manual',
                observacao=f"{dados['motivo']}" + (f" — {dados['observacao']}" if dados.get('observacao') else ''),
                criado_por=request.user,
                **movimento_kwargs,
            )
        except DjangoValidationError as e:
            raise ValidationError(e.message_dict if hasattr(e, 'message_dict') else e.messages)

        registrar(
            request.user, LogAuditoria.ACAO_AJUSTE_INVENTARIO_REGISTRADO,
            detalhes={
                'tipo_item': dados['tipo_item'], 'item_id': item.id, 'item_nome': str(item),
                'saldo_anterior': str(mov.saldo_anterior), 'saldo_contado': str(dados['saldo_contado']),
                'motivo': dados['motivo'],
            },
            request=request,
        )
        return Response(MovimentoEstoqueSerializer(mov).data, status=status.HTTP_201_CREATED)


# ─── Produção ──────────────────────────────────────────────────────────────────

class ProducaoViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    queryset = Producao.objects.select_related('ficha_tecnica', 'criado_por').all()
    serializer_class = ProducaoSerializer
    authentication_classes = [TokenAuthentication]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated()]
        return [AllowAny()]

    def perform_create(self, serializer):
        producao = serializer.save(criado_por=ator_ou_none(self.request))
        try:
            producao.executar(usuario=ator_ou_none(self.request))
        except DjangoValidationError as e:
            producao.delete()
            raise ValidationError(e.message_dict if hasattr(e, 'message_dict') else e.messages)
        registrar(
            self.request.user, LogAuditoria.ACAO_PRODUCAO_REGISTRADA,
            detalhes={
                'ficha_tecnica': producao.ficha_tecnica.nome,
                'quantidade_produzida': str(producao.quantidade_produzida),
            },
            request=self.request,
        )

    @action(detail=False, methods=['get'], url_path='preview')
    def preview(self, request):
        serializer = ProducaoPreviewSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        ficha = serializer.validated_data['ficha_tecnica']
        quantidade = serializer.validated_data['quantidade']

        if not ficha.rendimento:
            return Response({'detail': 'Ficha técnica sem rendimento definido.'}, status=status.HTTP_400_BAD_REQUEST)

        itens = []
        for item in ficha.itens.select_related('materia_prima'):
            consumo = item.quantidade * (quantidade / ficha.rendimento)
            itens.append({
                'materia_prima_id': item.materia_prima_id,
                'materia_prima_nome': item.materia_prima.nome,
                'unidade_medida': item.materia_prima.unidade_medida,
                'quantidade': str(consumo),
                'saldo_atual': str(item.materia_prima.quantidade_estoque),
                'suficiente': item.materia_prima.quantidade_estoque >= consumo,
            })
        return Response({'itens': itens})


# ─── Configuração de Estoque (singleton) ──────────────────────────────────────

class ConfiguracaoEstoqueViewSet(CsrfExemptMixin, viewsets.GenericViewSet):
    serializer_class = ConfiguracaoEstoqueSerializer
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action == 'partial_update':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_object(self):
        return ConfiguracaoEstoque.get()

    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(self.get_object()).data)

    def partial_update(self, request, pk=None):
        config = self.get_object()
        campos = list(request.data.keys())
        antes = {c: str(getattr(config, c)) for c in campos if hasattr(config, c)}
        serializer = ConfiguracaoEstoqueSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        depois = {c: str(getattr(config, c)) for c in campos if hasattr(config, c)}
        registrar(
            request.user, LogAuditoria.ACAO_CONFIG_ESTOQUE_ALTERADA,
            detalhes={'antes': antes, 'depois': depois},
            request=request,
        )
        return Response(serializer.data)


# ─── Telefones de Alerta de Estoque ────────────────────────────────────────────

class TelefoneAlertaEstoqueViewSet(AuditoriaDestroyMixin, CsrfExemptMixin, viewsets.ModelViewSet):
    queryset = TelefoneAlertaEstoque.objects.all()
    serializer_class = TelefoneAlertaEstoqueSerializer
    authentication_classes = [TokenAuthentication]
    campos_log_exclusao = ['numero', 'nome']

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated()]
        return [AllowAny()]
