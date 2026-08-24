from decimal import Decimal

from rest_framework import serializers

from clientes.models import Cliente

from .models import (
    CategoriaFinanceira,
    ConfiguracaoFinanceira,
    ContaBancaria,
    ContaPagar,
    ContaReceber,
    DespesaRecorrente,
    Fornecedor,
    MovimentoFinanceiro,
    SaldoConferido,
    TelefoneAlertaFinanceiro,
)


class CategoriaFinanceiraSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaFinanceira
        fields = ['id', 'nome', 'tipo', 'pai', 'ativo', 'criado_em', 'atualizado_em']


class ContaBancariaSerializer(serializers.ModelSerializer):
    empresa_nome = serializers.CharField(source='empresa.nome', read_only=True, default=None)

    class Meta:
        model = ContaBancaria
        fields = ['id', 'nome', 'tipo', 'empresa', 'empresa_nome', 'saldo_atual', 'ativo', 'criado_em', 'atualizado_em']
        read_only_fields = ['empresa', 'saldo_atual']


class FornecedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fornecedor
        fields = [
            'id', 'nome', 'cnpj', 'telefone', 'email', 'categoria_padrao',
            'ativo', 'criado_em', 'atualizado_em',
        ]


class ConfiguracaoFinanceiraSerializer(serializers.ModelSerializer):
    empresa_nome = serializers.CharField(source='empresa.nome', read_only=True, default=None)

    class Meta:
        model = ConfiguracaoFinanceira
        fields = [
            'empresa', 'empresa_nome', 'recebimento_ifood', 'dias_repasse_ifood', 'nota_gera_conta_pagar',
            'alerta_antecedencia_dias', 'alerta_repeticao_dias', 'horizonte_recorrencia_dias',
            'conta_padrao_vendas', 'atualizado_em',
        ]
        read_only_fields = ['empresa', 'atualizado_em']

    def validate_conta_padrao_vendas(self, conta):
        if conta and self.instance and conta.empresa_id != self.instance.empresa_id:
            raise serializers.ValidationError('A conta bancária precisa ser da mesma empresa desta configuração.')
        return conta


class TelefoneAlertaFinanceiroSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelefoneAlertaFinanceiro
        fields = ['id', 'numero', 'nome', 'ativo', 'criado_em']


class MovimentoFinanceiroSerializer(serializers.ModelSerializer):
    conta_nome = serializers.CharField(source='conta.nome', read_only=True, default=None)
    empresa_nome = serializers.CharField(source='conta.empresa.nome', read_only=True, default=None)
    categoria_nome = serializers.CharField(source='categoria.nome', read_only=True, default=None)
    fornecedor_nome = serializers.CharField(source='fornecedor.nome', read_only=True, default=None)
    cliente_nome = serializers.CharField(source='cliente.nome', read_only=True, default=None)
    criado_por_nome = serializers.CharField(source='criado_por.name', read_only=True, default=None)

    class Meta:
        model = MovimentoFinanceiro
        fields = [
            'id', 'conta', 'conta_nome', 'empresa_nome', 'tipo', 'valor', 'data_movimento',
            'categoria', 'categoria_nome', 'fornecedor', 'fornecedor_nome',
            'cliente', 'cliente_nome', 'descricao', 'forma_pagamento',
            'origem_tipo', 'origem_id', 'comprovante', 'saldo_posterior',
            'criado_por', 'criado_por_nome', 'criado_em',
        ]


class ContaPagarSerializer(serializers.ModelSerializer):
    empresa_nome = serializers.CharField(source='empresa.nome', read_only=True, default=None)
    fornecedor_nome = serializers.CharField(source='fornecedor.nome', read_only=True, default=None)
    categoria_nome = serializers.CharField(source='categoria.nome', read_only=True, default=None)
    saldo_restante = serializers.SerializerMethodField()

    class Meta:
        model = ContaPagar
        fields = [
            'id', 'numero', 'empresa', 'empresa_nome', 'fornecedor', 'fornecedor_nome', 'descricao', 'categoria',
            'categoria_nome', 'valor', 'data_emissao', 'data_vencimento', 'status',
            'origem', 'nota_fiscal', 'recorrente', 'anexo', 'observacao', 'valor_pago',
            'saldo_restante', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['numero', 'empresa', 'status', 'origem', 'nota_fiscal', 'recorrente', 'valor_pago']

    def get_saldo_restante(self, obj):
        return obj.valor - obj.valor_pago

    def validate_categoria(self, categoria):
        if categoria and categoria.tipo != 'saida':
            raise serializers.ValidationError('Categoria deve ser do tipo "saida".')
        return categoria

    def validate_valor(self, valor):
        if valor <= 0:
            raise serializers.ValidationError('Deve ser maior que zero.')
        return valor


class DespesaRecorrenteSerializer(serializers.ModelSerializer):
    empresa_nome = serializers.CharField(source='empresa.nome', read_only=True, default=None)
    fornecedor_nome = serializers.CharField(source='fornecedor.nome', read_only=True, default=None)
    categoria_nome = serializers.CharField(source='categoria.nome', read_only=True, default=None)

    class Meta:
        model = DespesaRecorrente
        fields = [
            'id', 'empresa', 'empresa_nome', 'descricao', 'fornecedor', 'fornecedor_nome', 'categoria', 'categoria_nome',
            'valor', 'valor_tipo', 'dias_vencimento', 'ativo', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['empresa']

    def validate_categoria(self, categoria):
        if categoria.tipo != 'saida':
            raise serializers.ValidationError('Categoria deve ser do tipo "saida".')
        return categoria

    def validate_valor(self, valor):
        if valor <= 0:
            raise serializers.ValidationError('Deve ser maior que zero.')
        return valor

    def validate_dias_vencimento(self, dias):
        if not isinstance(dias, list) or not dias:
            raise serializers.ValidationError('Informe ao menos um dia do mês (1-31).')
        for dia in dias:
            if not isinstance(dia, int) or not (1 <= dia <= 31):
                raise serializers.ValidationError('Cada dia deve ser um inteiro entre 1 e 31.')
        return dias


class ContaReceberSerializer(serializers.ModelSerializer):
    empresa_nome = serializers.CharField(source='empresa.nome', read_only=True, default=None)
    cliente_nome_crm = serializers.CharField(source='cliente.nome', read_only=True, default=None)
    categoria_nome = serializers.CharField(source='categoria.nome', read_only=True, default=None)
    saldo_restante = serializers.SerializerMethodField()

    class Meta:
        model = ContaReceber
        fields = [
            'id', 'numero', 'empresa', 'empresa_nome', 'cliente', 'cliente_nome_crm', 'cliente_nome', 'canal',
            'referencia', 'categoria', 'categoria_nome', 'valor', 'data_vencimento', 'status', 'origem_canal',
            'origem_id', 'valor_recebido', 'saldo_restante', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['numero', 'empresa', 'status', 'canal', 'origem_canal', 'origem_id', 'valor_recebido']

    def get_saldo_restante(self, obj):
        return obj.valor - obj.valor_recebido

    def validate_categoria(self, categoria):
        if categoria and categoria.tipo != 'entrada':
            raise serializers.ValidationError('Categoria deve ser do tipo "entrada".')
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


class MovimentoManualSerializer(serializers.Serializer):
    """Lançamento avulso/estorno manual — sempre grava com origem_tipo='manual'."""

    conta = serializers.PrimaryKeyRelatedField(queryset=ContaBancaria.objects.all())
    tipo = serializers.ChoiceField(choices=MovimentoFinanceiro.TIPO_CHOICES)
    valor = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    data_movimento = serializers.DateField(required=False)
    categoria = serializers.PrimaryKeyRelatedField(queryset=CategoriaFinanceira.objects.all(), required=False, allow_null=True)
    fornecedor = serializers.PrimaryKeyRelatedField(queryset=Fornecedor.objects.all(), required=False, allow_null=True)
    cliente = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.all(), required=False, allow_null=True)
    descricao = serializers.CharField(max_length=200, required=False, allow_blank=True)
    forma_pagamento = serializers.ChoiceField(
        choices=MovimentoFinanceiro.FORMA_PAGAMENTO_CHOICES, required=False, allow_blank=True,
    )
    comprovante = serializers.FileField(required=False, allow_null=True)

    def validate_categoria(self, categoria):
        if categoria and categoria.tipo != self.initial_data.get('tipo'):
            raise serializers.ValidationError('Categoria deve ser do mesmo tipo do movimento (entrada/saída).')
        return categoria


class SaldoConferidoSerializer(serializers.ModelSerializer):
    conta_nome = serializers.CharField(source='conta.nome', read_only=True, default=None)
    criado_por_nome = serializers.CharField(source='criado_por.name', read_only=True, default=None)
    diferenca = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = SaldoConferido
        fields = [
            'id', 'conta', 'conta_nome', 'data', 'saldo_informado', 'saldo_calculado',
            'diferenca', 'criado_por', 'criado_por_nome', 'criado_em',
        ]
        read_only_fields = ['saldo_calculado', 'criado_por']
