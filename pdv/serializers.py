from rest_framework import serializers
from .models import (
    CategoriaProduto, Produto, PedidoPDV, ItemPedidoPDV, TaxaEntregaBairro, ConfiguracaoEntrega,
    ItemKit, FaixaPreco, DadosFiscaisProduto,
)


# ─── Categoria ───────────────────────────────────────────────────────────────

class CategoriaProdutoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CategoriaProduto
        fields = ['id', 'nome', 'ordem']


# ─── Taxa de Entrega por Bairro ───────────────────────────────────────────────

class TaxaEntregaBairroSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TaxaEntregaBairro
        fields = ['id', 'bairro', 'taxa', 'ativo']


class ConfiguracaoEntregaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ConfiguracaoEntrega
        fields = ['frete_padrao']


# ─── Faixa de Preço / Item de Kit / Dados Fiscais ────────────────────────────

class FaixaPrecoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FaixaPreco
        fields = ['id', 'produto', 'quantidade_minima', 'preco_unitario', 'canal']
        read_only_fields = ['produto']

    def validate_quantidade_minima(self, value):
        if value <= 1:
            raise serializers.ValidationError('A quantidade mínima da faixa deve ser maior que 1.')
        return value


class ItemKitSerializer(serializers.ModelSerializer):
    componente_nome  = serializers.CharField(source='componente.nome', read_only=True)
    componente_preco = serializers.DecimalField(source='componente.preco', read_only=True, max_digits=10, decimal_places=2)

    class Meta:
        model  = ItemKit
        fields = ['id', 'kit', 'componente', 'componente_nome', 'componente_preco', 'quantidade']
        read_only_fields = ['kit']

    def validate_componente(self, value):
        if value.tipo == 'kit':
            raise serializers.ValidationError('Não é permitido adicionar um kit como componente de outro kit.')
        return value

    def validate(self, data):
        kit = self.context.get('kit')
        componente = data.get('componente')
        if kit and componente and kit.id == componente.id:
            raise serializers.ValidationError('Um kit não pode se conter.')
        return data


class DadosFiscaisProdutoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DadosFiscaisProduto
        fields = ['unidade', 'codigo', 'codigo_barras', 'ncm']


# ─── Produto ─────────────────────────────────────────────────────────────────

class ProdutoSerializer(serializers.ModelSerializer):
    categoria_nome         = serializers.CharField(source='categoria.nome', read_only=True, default=None)
    materia_prima_nome     = serializers.CharField(source='materia_prima_origem.nome', read_only=True, default=None)
    custo                  = serializers.SerializerMethodField()
    custo_origem           = serializers.CharField(read_only=True)
    margem_pct             = serializers.SerializerMethodField()
    preco_sugerido_revenda = serializers.SerializerMethodField()
    faixas_preco           = FaixaPrecoSerializer(many=True, read_only=True)
    itens_kit              = ItemKitSerializer(many=True, read_only=True)
    dados_fiscais          = DadosFiscaisProdutoSerializer(required=False, allow_null=True)

    class Meta:
        model  = Produto
        fields = [
            'id', 'nome', 'descricao', 'preco', 'categoria', 'categoria_nome',
            'segmento', 'foto', 'disponivel_pdv', 'disponivel_ifood', 'disponivel_eventos',
            'ativo', 'tipo', 'materia_prima_origem', 'materia_prima_nome', 'margem_desejada_pct',
            'custo', 'custo_origem', 'margem_pct', 'preco_sugerido_revenda',
            'faixas_preco', 'itens_kit', 'dados_fiscais',
        ]

    def get_custo(self, obj):
        c = obj.custo
        return float(c) if c is not None else None

    def get_margem_pct(self, obj):
        m = obj.margem_pct
        return float(m) if m is not None else None

    def get_preco_sugerido_revenda(self, obj):
        v = obj.preco_sugerido_revenda
        return float(v) if v is not None else None

    def validate(self, data):
        tipo = data.get('tipo', getattr(self.instance, 'tipo', 'fabricado'))
        materia_prima_origem = data.get('materia_prima_origem', getattr(self.instance, 'materia_prima_origem', None))
        if materia_prima_origem and tipo != 'revenda':
            raise serializers.ValidationError({
                'materia_prima_origem': 'Só pode ser preenchido quando o tipo do produto é "revenda".'
            })
        return data

    def create(self, validated_data):
        dados_fiscais_data = validated_data.pop('dados_fiscais', None)
        produto = Produto.objects.create(**validated_data)
        if dados_fiscais_data:
            DadosFiscaisProduto.objects.create(produto=produto, **dados_fiscais_data)
        return produto

    def update(self, instance, validated_data):
        dados_fiscais_data = validated_data.pop('dados_fiscais', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if dados_fiscais_data is not None:
            DadosFiscaisProduto.objects.update_or_create(produto=instance, defaults=dados_fiscais_data)
        return instance


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
            'total', 'subtotal', 'desconto', 'taxa_entrega', 'bairro_entrega',
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
            'tipo', 'pagamento', 'desconto', 'taxa_entrega', 'bairro_entrega', 'observacoes',
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
