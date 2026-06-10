from rest_framework import serializers
from .models import CategoriaProduto, Produto, PedidoPDV, ItemPedidoPDV


# ─── Categoria ───────────────────────────────────────────────────────────────

class CategoriaProdutoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CategoriaProduto
        fields = ['id', 'nome', 'ordem']


# ─── Produto ─────────────────────────────────────────────────────────────────

class ProdutoSerializer(serializers.ModelSerializer):
    categoria_nome = serializers.CharField(source='categoria.nome', read_only=True, default=None)

    class Meta:
        model  = Produto
        fields = [
            'id', 'nome', 'descricao', 'preco', 'categoria', 'categoria_nome',
            'segmento', 'foto', 'disponivel_pdv', 'disponivel_ifood', 'disponivel_eventos',
            'ativo',
        ]


# ─── Item ────────────────────────────────────────────────────────────────────

class ItemPedidoPDVSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ItemPedidoPDV
        fields = ['id', 'produto', 'nome', 'preco_unit', 'quantidade', 'preco_total', 'observacao']
        read_only_fields = ['preco_total']


class ItemPedidoPDVCreateSerializer(serializers.ModelSerializer):
    """Usado na criação: popula nome/preco_unit a partir do produto se não informados."""

    class Meta:
        model  = ItemPedidoPDV
        fields = ['produto', 'nome', 'preco_unit', 'quantidade', 'observacao']

    def validate(self, data):
        produto = data.get('produto')
        if produto:
            data.setdefault('nome',       produto.nome)
            data.setdefault('preco_unit', produto.preco)
        if not data.get('nome'):
            raise serializers.ValidationError({'nome': 'Informe o nome do item.'})
        if not data.get('preco_unit'):
            raise serializers.ValidationError({'preco_unit': 'Informe o preço unitário.'})
        return data


# ─── Pedido PDV ──────────────────────────────────────────────────────────────

class PedidoPDVListSerializer(serializers.ModelSerializer):
    status_display    = serializers.CharField(source='get_status_display',    read_only=True)
    tipo_display      = serializers.CharField(source='get_tipo_display',      read_only=True)
    pagamento_display = serializers.CharField(source='get_pagamento_display', read_only=True)
    cliente_nome_crm  = serializers.SerializerMethodField()

    class Meta:
        model  = PedidoPDV
        fields = [
            'id', 'numero',
            'status', 'status_display',
            'tipo',   'tipo_display',
            'pagamento', 'pagamento_display',
            'total', 'subtotal', 'desconto', 'taxa_entrega',
            'cliente', 'cliente_nome', 'cliente_telefone', 'cliente_nome_crm',
            'pode_confirmar', 'pode_cancelar', 'pode_concluir',
            'criado_em', 'atualizado_em',
        ]

    def get_cliente_nome_crm(self, obj):
        return obj.cliente.nome if obj.cliente else None


class PedidoPDVDetailSerializer(PedidoPDVListSerializer):
    itens = ItemPedidoPDVSerializer(many=True, read_only=True)

    class Meta(PedidoPDVListSerializer.Meta):
        fields = PedidoPDVListSerializer.Meta.fields + ['itens', 'observacoes']


class PedidoPDVCreateSerializer(serializers.ModelSerializer):
    itens = ItemPedidoPDVCreateSerializer(many=True, required=False)

    class Meta:
        model  = PedidoPDV
        fields = [
            'cliente', 'cliente_nome', 'cliente_telefone',
            'tipo', 'pagamento', 'desconto', 'taxa_entrega', 'observacoes',
            'itens',
        ]

    def create(self, validated_data):
        itens_data     = validated_data.pop('itens', [])
        validated_data['numero'] = PedidoPDV.proximo_numero()
        pedido = PedidoPDV.objects.create(**validated_data)

        subtotal = 0
        for item_data in itens_data:
            qty   = item_data.get('quantidade', 1)
            price = item_data['preco_unit']
            item  = ItemPedidoPDV.objects.create(
                pedido=pedido,
                preco_total=price * qty,
                **item_data,
            )
            subtotal += item.preco_total

        pedido.subtotal = subtotal
        pedido.total    = subtotal - pedido.desconto + pedido.taxa_entrega
        pedido.save(update_fields=['subtotal', 'total'])
        return pedido
