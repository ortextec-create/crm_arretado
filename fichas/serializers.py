from rest_framework import serializers
from .models import MateriaPrima, FichaTecnica, ItemFichaTecnica, ParametrosNegocio, SnapshotPrecos


class MateriaPrimaSerializer(serializers.ModelSerializer):
    custo_unitario = serializers.SerializerMethodField()

    class Meta:
        model  = MateriaPrima
        fields = [
            'id', 'nome', 'unidade_compra', 'quantidade_compra',
            'unidade_medida', 'valor_compra', 'custo_unitario',
            'ativo', 'atualizado_em',
        ]

    def get_custo_unitario(self, obj):
        return float(obj.custo_unitario)


class ItemFichaTecnicaSerializer(serializers.ModelSerializer):
    materia_prima_nome    = serializers.CharField(source='materia_prima.nome', read_only=True)
    materia_prima_unidade = serializers.CharField(source='materia_prima.unidade_medida', read_only=True)
    custo_proporcional    = serializers.SerializerMethodField()

    class Meta:
        model  = ItemFichaTecnica
        fields = [
            'id', 'materia_prima', 'materia_prima_nome', 'materia_prima_unidade',
            'quantidade', 'custo_proporcional',
        ]

    def get_custo_proporcional(self, obj):
        return float(obj.custo_proporcional)


class ItemFichaTecnicaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ItemFichaTecnica
        fields = ['materia_prima', 'quantidade']


class FichaTecnicaListSerializer(serializers.ModelSerializer):
    custo_total_unitario = serializers.SerializerMethodField()
    preco_ideal          = serializers.SerializerMethodField()
    margem_bruta_pct     = serializers.SerializerMethodField()
    produto_nome         = serializers.SerializerMethodField()
    produto_preco        = serializers.SerializerMethodField()

    class Meta:
        model  = FichaTecnica
        fields = [
            'id', 'nome', 'rendimento', 'embalagem_custo', 'ativo',
            'produto_pdv_id', 'produto_nome', 'produto_preco',
            'custo_total_unitario', 'preco_ideal', 'margem_bruta_pct',
        ]

    def get_custo_total_unitario(self, obj):
        return float(obj.custo_total_unitario)

    def get_preco_ideal(self, obj):
        return float(obj.preco_ideal)

    def get_margem_bruta_pct(self, obj):
        m = obj.margem_bruta_pct
        return float(m) if m is not None else None

    def get_produto_nome(self, obj):
        p = obj._get_produto_pdv()
        return p.nome if p else None

    def get_produto_preco(self, obj):
        p = obj._get_produto_pdv()
        return float(p.preco) if p else None


class FichaTecnicaDetailSerializer(FichaTecnicaListSerializer):
    itens               = ItemFichaTecnicaSerializer(many=True, read_only=True)
    custo_ingredientes  = serializers.SerializerMethodField()

    class Meta(FichaTecnicaListSerializer.Meta):
        fields = FichaTecnicaListSerializer.Meta.fields + ['itens', 'custo_ingredientes']

    def get_custo_ingredientes(self, obj):
        return float(obj.custo_ingredientes)


class FichaTecnicaCreateSerializer(serializers.ModelSerializer):
    itens = ItemFichaTecnicaCreateSerializer(many=True, required=False)

    class Meta:
        model  = FichaTecnica
        fields = ['id', 'nome', 'produto_pdv_id', 'rendimento', 'embalagem_custo', 'ativo', 'itens']

    def create(self, validated_data):
        itens_data = validated_data.pop('itens', [])
        ficha = FichaTecnica.objects.create(**validated_data)
        for item_data in itens_data:
            ItemFichaTecnica.objects.create(ficha=ficha, **item_data)
        return ficha

    def update(self, instance, validated_data):
        itens_data = validated_data.pop('itens', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if itens_data is not None:
            instance.itens.all().delete()
            for item_data in itens_data:
                ItemFichaTecnica.objects.create(ficha=instance, **item_data)
        return instance


class ParametrosNegocioSerializer(serializers.ModelSerializer):
    markup = serializers.SerializerMethodField()

    class Meta:
        model  = ParametrosNegocio
        fields = [
            'id', 'faturamento_meta', 'despesa_fixa_mensal',
            'despesa_variavel_pct', 'margem_lucro_esperada_pct',
            'markup', 'atualizado_em',
        ]

    def get_markup(self, obj):
        return float(obj.markup)


class SnapshotPrecosSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SnapshotPrecos
        fields = ['id', 'descricao', 'criado_em', 'revertido']
