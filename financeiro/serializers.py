from decimal import Decimal

from rest_framework import serializers

from .models import (
    CategoriaFinanceira,
    ConfiguracaoFinanceira,
    ContaBancaria,
    ContaPagar,
    Fornecedor,
    MovimentoFinanceiro,
    TelefoneAlertaFinanceiro,
)


class CategoriaFinanceiraSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaFinanceira
        fields = ['id', 'nome', 'tipo', 'pai', 'ativo', 'criado_em', 'atualizado_em']


class ContaBancariaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContaBancaria
        fields = ['id', 'nome', 'tipo', 'saldo_atual', 'ativo', 'criado_em', 'atualizado_em']
        read_only_fields = ['saldo_atual']


class FornecedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fornecedor
        fields = [
            'id', 'nome', 'cnpj', 'telefone', 'email', 'categoria_padrao',
            'ativo', 'criado_em', 'atualizado_em',
        ]


class ConfiguracaoFinanceiraSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracaoFinanceira
        fields = [
            'recebimento_ifood', 'dias_repasse_ifood', 'nota_gera_conta_pagar',
            'alerta_antecedencia_dias', 'alerta_repeticao_dias', 'horizonte_recorrencia_dias',
            'conta_padrao_vendas', 'atualizado_em',
        ]
        read_only_fields = ['atualizado_em']


class TelefoneAlertaFinanceiroSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelefoneAlertaFinanceiro
        fields = ['id', 'numero', 'nome', 'ativo', 'criado_em']


class MovimentoFinanceiroSerializer(serializers.ModelSerializer):
    conta_nome = serializers.CharField(source='conta.nome', read_only=True, default=None)
    categoria_nome = serializers.CharField(source='categoria.nome', read_only=True, default=None)
    fornecedor_nome = serializers.CharField(source='fornecedor.nome', read_only=True, default=None)
    cliente_nome = serializers.CharField(source='cliente.nome', read_only=True, default=None)
    criado_por_nome = serializers.CharField(source='criado_por.name', read_only=True, default=None)

    class Meta:
        model = MovimentoFinanceiro
        fields = [
            'id', 'conta', 'conta_nome', 'tipo', 'valor', 'data_movimento',
            'categoria', 'categoria_nome', 'fornecedor', 'fornecedor_nome',
            'cliente', 'cliente_nome', 'descricao', 'forma_pagamento',
            'origem_tipo', 'origem_id', 'comprovante', 'saldo_posterior',
            'criado_por', 'criado_por_nome', 'criado_em',
        ]


class ContaPagarSerializer(serializers.ModelSerializer):
    fornecedor_nome = serializers.CharField(source='fornecedor.nome', read_only=True, default=None)
    categoria_nome = serializers.CharField(source='categoria.nome', read_only=True, default=None)
    saldo_restante = serializers.SerializerMethodField()

    class Meta:
        model = ContaPagar
        fields = [
            'id', 'numero', 'fornecedor', 'fornecedor_nome', 'descricao', 'categoria',
            'categoria_nome', 'valor', 'data_emissao', 'data_vencimento', 'status',
            'origem', 'nota_fiscal', 'anexo', 'observacao', 'valor_pago', 'saldo_restante',
            'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['numero', 'status', 'origem', 'nota_fiscal', 'valor_pago']

    def get_saldo_restante(self, obj):
        return obj.valor - obj.valor_pago

    def validate_categoria(self, categoria):
        if categoria.tipo != 'saida':
            raise serializers.ValidationError('Categoria deve ser do tipo "saida".')
        return categoria

    def validate_valor(self, valor):
        if valor <= 0:
            raise serializers.ValidationError('Deve ser maior que zero.')
        return valor


class BaixaContaSerializer(serializers.Serializer):
    data = serializers.DateField()
    valor = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    conta = serializers.PrimaryKeyRelatedField(queryset=ContaBancaria.objects.all())
    forma = serializers.ChoiceField(choices=MovimentoFinanceiro.FORMA_PAGAMENTO_CHOICES)
    comprovante = serializers.FileField(required=False, allow_null=True)
