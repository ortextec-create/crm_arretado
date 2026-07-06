from rest_framework import serializers
from .models import Cliente, Endereco, TagCliente


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = TagCliente
        fields = ['id', 'nome', 'cor']


class EnderecoSerializer(serializers.ModelSerializer):
    endereco_completo = serializers.ReadOnlyField()

    class Meta:
        model = Endereco
        fields = [
            'id', 'tipo', 'apelido', 'cep', 'logradouro', 'numero',
            'complemento', 'bairro', 'cidade', 'estado', 'principal',
            'latitude', 'longitude', 'endereco_completo', 'criado_em'
        ]

    def validate(self, data):
        cliente = self.context.get('cliente')
        if not cliente and self.instance:
            cliente = self.instance.cliente
        return data


class ClienteListSerializer(serializers.ModelSerializer):
    """Serializer compacto para listagem"""
    tags = TagSerializer(many=True, read_only=True)
    endereco_principal = serializers.SerializerMethodField()
    iniciais = serializers.ReadOnlyField()
    tem_integracao_ifood = serializers.ReadOnlyField()
    tem_integracao_anotaai = serializers.ReadOnlyField()

    class Meta:
        model = Cliente
        fields = [
            'id', 'nome', 'iniciais', 'cpf', 'email', 'telefone_principal',
            'status', 'tags', 'endereco_principal',
            'tem_integracao_ifood', 'tem_integracao_anotaai',
            'criado_em', 'atualizado_em'
        ]

    def get_endereco_principal(self, obj):
        end = obj.enderecos.filter(principal=True).first()
        if end:
            return {'cidade': end.cidade, 'estado': end.estado, 'bairro': end.bairro}
        return None


class ClienteDetailSerializer(serializers.ModelSerializer):
    """Serializer completo para criação/edição/detalhe"""
    enderecos = EnderecoSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=TagCliente.objects.all(), write_only=True,
        required=False, source='tags'
    )
    iniciais = serializers.ReadOnlyField()
    tem_integracao_ifood = serializers.ReadOnlyField()
    tem_integracao_anotaai = serializers.ReadOnlyField()

    class Meta:
        model = Cliente
        fields = [
            'id', 'nome', 'iniciais', 'cpf', 'email', 'data_nascimento', 'sexo',
            'telefone_principal', 'telefone_secundario',
            'rg', 'rg_orgao_emissor', 'nacionalidade', 'profissao', 'estado_civil',
            'status', 'observacoes',
            'ifood_customer_id', 'anotaai_customer_id',
            'tem_integracao_ifood', 'tem_integracao_anotaai',
            'tags', 'tag_ids', 'enderecos',
            'criado_em', 'atualizado_em'
        ]
        read_only_fields = ['criado_em', 'atualizado_em']

    def to_internal_value(self, data):
        data = data.copy()
        for campo in ('cpf', 'email', 'data_nascimento', 'sexo'):
            if data.get(campo) == '':
                data[campo] = None
        return super().to_internal_value(data)

    def validate_cpf(self, value):
        if value:
            qs = Cliente.objects.filter(cpf=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError('Já existe um cliente com este CPF.')
        return value

    def validate_email(self, value):
        if value:
            qs = Cliente.objects.filter(email=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError('Já existe um cliente com este e-mail.')
        return value
