from decimal import Decimal

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MateriaPrima, FichaTecnica, ItemFichaTecnica, ParametrosNegocio, SnapshotPrecos
from .serializers import (
    MateriaPrimaSerializer,
    FichaTecnicaListSerializer,
    FichaTecnicaDetailSerializer,
    FichaTecnicaCreateSerializer,
    ParametrosNegocioSerializer,
    SnapshotPrecosSerializer,
)


class CsrfExemptMixin:
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


# ─── Matérias-Primas ──────────────────────────────────────────────────────────

class MateriaPrimaViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = MateriaPrima.objects.all()
    serializer_class   = MateriaPrimaSerializer
    permission_classes = [AllowAny]
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['nome']
    ordering_fields    = ['nome', 'valor_compra', 'atualizado_em']
    ordering           = ['nome']

    def get_queryset(self):
        qs    = super().get_queryset()
        ativo = self.request.query_params.get('ativo')
        if ativo is not None:
            qs = qs.filter(ativo=ativo.lower() == 'true')
        return qs

    @action(detail=True, methods=['post'], url_path='atualizar-preco')
    def atualizar_preco(self, request, pk=None):
        materia    = self.get_object()
        novo_valor = request.data.get('valor_compra')
        if novo_valor is None:
            return Response({'detail': 'valor_compra é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)
        materia.valor_compra = Decimal(str(novo_valor))
        materia.save(update_fields=['valor_compra', 'atualizado_em'])
        fichas_ids       = materia.itemfichatecnica_set.values_list('ficha_id', flat=True)
        fichas           = FichaTecnica.objects.filter(id__in=fichas_ids)
        produtos_impact  = list(set(f.produto_pdv_id for f in fichas if f.produto_pdv_id))
        return Response({
            'materia':              MateriaPrimaSerializer(materia).data,
            'produtos_impactados':  produtos_impact,
        })


# ─── Fichas Técnicas ──────────────────────────────────────────────────────────

class FichaTecnicaViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = FichaTecnica.objects.prefetch_related('itens__materia_prima').all()
    permission_classes = [AllowAny]
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['nome']
    ordering           = ['nome']

    def get_serializer_class(self):
        if self.action == 'list':
            return FichaTecnicaListSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return FichaTecnicaCreateSerializer
        return FichaTecnicaDetailSerializer

    def get_queryset(self):
        qs    = super().get_queryset()
        ativo = self.request.query_params.get('ativo')
        if ativo is not None:
            qs = qs.filter(ativo=ativo.lower() == 'true')
        return qs

    @action(detail=True, methods=['get'], url_path='resumo')
    def resumo(self, request, pk=None):
        ficha = self.get_object()
        itens = [
            {
                'ingrediente':      item.materia_prima.nome,
                'unidade':          item.materia_prima.unidade_medida,
                'quantidade':       float(item.quantidade),
                'custo_unitario':   float(item.materia_prima.custo_unitario),
                'custo_proporcional': float(item.custo_proporcional),
            }
            for item in ficha.itens.select_related('materia_prima').all()
        ]
        return Response({
            'ficha':                 FichaTecnicaDetailSerializer(ficha).data,
            'itens':                 itens,
            'custo_ingredientes':    float(ficha.custo_ingredientes),
            'embalagem_custo':       float(ficha.embalagem_custo),
            'custo_total_unitario':  float(ficha.custo_total_unitario),
            'preco_ideal':           float(ficha.preco_ideal),
        })

    @action(detail=True, methods=['post'], url_path='adicionar-item')
    def adicionar_item(self, request, pk=None):
        ficha      = self.get_object()
        materia_id = request.data.get('materia_prima')
        quantidade = request.data.get('quantidade')
        if not materia_id or quantidade is None:
            return Response(
                {'detail': 'materia_prima e quantidade são obrigatórios.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            materia = MateriaPrima.objects.get(pk=materia_id)
        except MateriaPrima.DoesNotExist:
            return Response({'detail': 'Matéria-prima não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        ItemFichaTecnica.objects.update_or_create(
            ficha=ficha, materia_prima=materia,
            defaults={'quantidade': Decimal(str(quantidade))},
        )
        return Response(FichaTecnicaDetailSerializer(ficha).data)

    @action(detail=True, methods=['delete'], url_path=r'remover-item/(?P<item_id>[0-9]+)')
    def remover_item(self, request, pk=None, item_id=None):
        ficha = self.get_object()
        try:
            ficha.itens.get(pk=item_id).delete()
        except ItemFichaTecnica.DoesNotExist:
            return Response({'detail': 'Item não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(FichaTecnicaDetailSerializer(ficha).data)


# ─── Parâmetros do Negócio ────────────────────────────────────────────────────

class ParametrosNegocioViewSet(CsrfExemptMixin, viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    serializer_class   = ParametrosNegocioSerializer

    def get_object(self):
        return ParametrosNegocio.get()

    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(self.get_object()).data)

    def partial_update(self, request, pk=None):
        params     = self.get_object()
        serializer = ParametrosNegocioSerializer(params, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        fichas = FichaTecnica.objects.prefetch_related('itens__materia_prima').filter(ativo=True)
        precos_ideais = [
            {'produto_id': f.produto_pdv_id, 'ficha_nome': f.nome, 'preco_ideal': float(f.preco_ideal)}
            for f in fichas if f.produto_pdv_id
        ]
        return Response({'parametros': serializer.data, 'precos_ideais': precos_ideais})


# ─── Snapshots ────────────────────────────────────────────────────────────────

class SnapshotPrecosViewSet(CsrfExemptMixin, viewsets.ReadOnlyModelViewSet):
    queryset           = SnapshotPrecos.objects.all()
    serializer_class   = SnapshotPrecosSerializer
    permission_classes = [AllowAny]


# ─── Ajuste Linear ────────────────────────────────────────────────────────────

class AjusteLinearView(CsrfExemptMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        segmento  = request.data.get('segmento', 'todos')
        tipo      = request.data.get('tipo', 'percentual')
        operacao  = request.data.get('operacao', 'aumento')
        valor     = Decimal(str(request.data.get('valor', 0)))
        confirmar = request.data.get('confirmar', False)

        from pdv.models import Produto
        qs = Produto.objects.filter(ativo=True)
        if segmento and segmento != 'todos':
            qs = qs.filter(segmento=segmento)

        preview = []
        for produto in qs:
            delta = produto.preco * (valor / Decimal('100')) if tipo == 'percentual' else valor
            if operacao == 'desconto':
                delta = -delta
            novo_preco = max(produto.preco + delta, Decimal('0.01'))
            preview.append({
                'id':          produto.id,
                'nome':        produto.nome,
                'segmento':    produto.segmento,
                'preco_atual': float(produto.preco),
                'preco_novo':  float(round(novo_preco, 2)),
                'variacao':    float(round(novo_preco - produto.preco, 2)),
            })

        if not confirmar:
            return Response({'preview': preview, 'total_produtos': len(preview)})

        # Salvar snapshot antes de aplicar
        snapshot_dados = {str(p['id']): p['preco_atual'] for p in preview}
        sinal     = '+' if operacao == 'aumento' else '-'
        sufixo    = '%' if tipo == 'percentual' else 'R$'
        seg_label = segmento if segmento != 'todos' else 'Todos'
        snapshot  = SnapshotPrecos.objects.create(
            descricao=f"{sinal}{valor}{sufixo} em {seg_label} ({len(preview)} produtos)",
            dados=snapshot_dados,
        )

        for item in preview:
            Produto.objects.filter(pk=item['id']).update(preco=Decimal(str(item['preco_novo'])))

        return Response({
            'aplicado':            True,
            'total_produtos':      len(preview),
            'snapshot_id':         snapshot.id,
            'snapshot_descricao':  snapshot.descricao,
        })


# ─── Desfazer Ajuste ──────────────────────────────────────────────────────────

class DesfazerAjusteView(CsrfExemptMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request, snapshot_id):
        try:
            snapshot = SnapshotPrecos.objects.get(pk=snapshot_id)
        except SnapshotPrecos.DoesNotExist:
            return Response({'detail': 'Snapshot não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        if snapshot.revertido:
            return Response({'detail': 'Este ajuste já foi desfeito.'}, status=status.HTTP_400_BAD_REQUEST)

        from pdv.models import Produto
        revertidos = 0
        for produto_id_str, preco_anterior in snapshot.dados.items():
            revertidos += Produto.objects.filter(pk=int(produto_id_str)).update(
                preco=Decimal(str(preco_anterior))
            )

        snapshot.revertido = True
        snapshot.save(update_fields=['revertido'])

        return Response({'revertido': True, 'produtos_restaurados': revertidos})
