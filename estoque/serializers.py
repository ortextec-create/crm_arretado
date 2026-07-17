from decimal import Decimal

from rest_framework import serializers

from fichas.models import FichaTecnica, MateriaPrima
from pdv.models import Produto

from .models import (
    AlertaEstoqueEnviado,
    ConfiguracaoEstoque,
    ConfiguracaoIA,
    ImportacaoNotaFiscal,
    ItemNotaImportada,
    MovimentoEstoque,
    Producao,
    TelefoneAlertaEstoque,
)


class MovimentoEstoqueSerializer(serializers.ModelSerializer):
    materia_prima_nome = serializers.CharField(source='materia_prima.nome', read_only=True, default=None)
    produto_nome = serializers.CharField(source='produto.nome', read_only=True, default=None)
    criado_por_nome = serializers.CharField(source='criado_por.name', read_only=True, default=None)

    class Meta:
        model = MovimentoEstoque
        fields = [
            'id', 'materia_prima', 'materia_prima_nome', 'produto', 'produto_nome',
            'tipo_movimento', 'quantidade', 'saldo_anterior', 'saldo_posterior',
            'custo_unitario_snapshot', 'origem_tipo', 'origem_id', 'observacao',
            'criado_por', 'criado_por_nome', 'criado_em',
        ]


class ProducaoSerializer(serializers.ModelSerializer):
    ficha_tecnica_nome = serializers.CharField(source='ficha_tecnica.nome', read_only=True)
    criado_por_nome = serializers.CharField(source='criado_por.name', read_only=True, default=None)
    produto_gerado = serializers.SerializerMethodField()

    class Meta:
        model = Producao
        fields = [
            'id', 'ficha_tecnica', 'ficha_tecnica_nome', 'quantidade_produzida',
            'criado_por', 'criado_por_nome', 'criado_em', 'produto_gerado',
        ]
        read_only_fields = ['criado_por', 'criado_em']

    def get_produto_gerado(self, obj):
        produto = obj.ficha_tecnica._get_produto_pdv()
        return produto.nome if produto else None

    def validate_ficha_tecnica(self, ficha):
        produto = ficha._get_produto_pdv()
        if not produto or produto.modo_estoque != 'estoque':
            raise serializers.ValidationError(
                'Ficha técnica sem produto vinculado em modo_estoque="estoque".'
            )
        return ficha


class ConfiguracaoEstoqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracaoEstoque
        fields = [
            'estoque_minimo_padrao', 'alerta_whatsapp_ativo',
            'alerta_repetir_diariamente', 'atualizado_em',
        ]
        read_only_fields = ['atualizado_em']


class TelefoneAlertaEstoqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelefoneAlertaEstoque
        fields = ['id', 'numero', 'nome', 'ativo', 'criado_em']


class RegistrarCompraSerializer(serializers.Serializer):
    tipo_item = serializers.ChoiceField(choices=['materia_prima', 'produto'])
    item_id = serializers.IntegerField()
    quantidade = serializers.DecimalField(max_digits=10, decimal_places=3, min_value=Decimal('0.001'))
    valor_total = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    numero_nota = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        model = MateriaPrima if data['tipo_item'] == 'materia_prima' else Produto
        try:
            data['item'] = model.objects.get(pk=data['item_id'])
        except model.DoesNotExist:
            raise serializers.ValidationError({'item_id': 'Item não encontrado.'})
        if data['tipo_item'] == 'produto' and data['item'].tipo != 'revenda':
            raise serializers.ValidationError({
                'tipo_item': 'Entrada manual de compra só se aplica a produtos de revenda (fabricados entram via Produção).'
            })
        return data


class AjusteInventarioSerializer(serializers.Serializer):
    tipo_item = serializers.ChoiceField(choices=['materia_prima', 'produto'])
    item_id = serializers.IntegerField()
    saldo_contado = serializers.DecimalField(max_digits=10, decimal_places=3)
    motivo = serializers.CharField()
    observacao = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        model = MateriaPrima if data['tipo_item'] == 'materia_prima' else Produto
        try:
            data['item'] = model.objects.get(pk=data['item_id'])
        except model.DoesNotExist:
            raise serializers.ValidationError({'item_id': 'Item não encontrado.'})
        return data


class ProducaoPreviewSerializer(serializers.Serializer):
    ficha_tecnica = serializers.PrimaryKeyRelatedField(queryset=FichaTecnica.objects.all())
    quantidade = serializers.DecimalField(max_digits=10, decimal_places=3, min_value=Decimal('0.001'))


class ConfiguracaoIASerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracaoIA
        fields = ['extracao_ia_ativa', 'modelo', 'timeout_segundos', 'atualizado_em']
        read_only_fields = ['atualizado_em']


class ItemNotaImportadaSerializer(serializers.ModelSerializer):
    materia_prima_nome = serializers.CharField(source='materia_prima.nome', read_only=True, default=None)
    produto_nome = serializers.CharField(source='produto.nome', read_only=True, default=None)

    class Meta:
        model = ItemNotaImportada
        fields = [
            'id', 'descricao_extraida', 'quantidade', 'valor_unitario',
            'materia_prima', 'materia_prima_nome', 'produto', 'produto_nome',
            'status_match', 'descartado',
        ]
        read_only_fields = ['descricao_extraida', 'status_match']


class ImportacaoNotaFiscalSerializer(serializers.ModelSerializer):
    itens = ItemNotaImportadaSerializer(many=True, read_only=True)
    criado_por_nome = serializers.CharField(source='criado_por.name', read_only=True, default=None)

    class Meta:
        model = ImportacaoNotaFiscal
        fields = [
            'id', 'arquivo', 'metodo_extracao', 'numero_nota', 'fornecedor_nome',
            'status', 'criado_por', 'criado_por_nome', 'criado_em', 'itens',
        ]
        read_only_fields = ['metodo_extracao', 'status', 'criado_por']
