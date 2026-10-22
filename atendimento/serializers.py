from rest_framework import serializers

from empresas.models import Empresa

from .models import (
    ConfiguracaoAtendimento, ConfiguracaoExtensao, MensagemChat, ModeloMensagemChat, TokenExtensao,
)


class ConfiguracaoAtendimentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracaoAtendimento
        exclude = ['empresa']


class ConfiguracaoExtensaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracaoExtensao
        fields = ['seletores', 'tempos_ms', 'intervalo_segundos', 'pausa_interacao_segundos', 'lease_segundos', 'max_tentativas']

    def validate_seletores(self, v):
        if not isinstance(v, dict):
            raise serializers.ValidationError('Deve ser um objeto JSON.')
        return v

    def validate_tempos_ms(self, v):
        if not isinstance(v, dict):
            raise serializers.ValidationError('Deve ser um objeto JSON.')
        return v


class ModeloMensagemChatSerializer(serializers.ModelSerializer):
    gatilho_display = serializers.CharField(source='get_gatilho_display', read_only=True)

    class Meta:
        model = ModeloMensagemChat
        fields = ['id', 'gatilho', 'gatilho_display', 'texto', 'ativo', 'atualizado_em']
        read_only_fields = ['gatilho']

    def validate_texto(self, v):
        if not v.strip():
            raise serializers.ValidationError('O texto não pode ficar vazio.')
        return v


class PreviewSerializer(serializers.Serializer):
    texto = serializers.CharField(allow_blank=True)
    pedido_id = serializers.IntegerField(required=False)


class MensagemChatSerializer(serializers.ModelSerializer):
    display_id = serializers.CharField(source='pedido.display_id', read_only=True)
    gatilho_display = serializers.CharField(source='get_gatilho_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    autor_nome = serializers.CharField(source='autor.name', read_only=True, default=None)
    pedido_status = serializers.CharField(source='pedido.status', read_only=True)

    class Meta:
        model = MensagemChat
        fields = [
            'id', 'empresa', 'pedido', 'display_id', 'pedido_status', 'direcao', 'origem', 'gatilho', 'gatilho_display',
            'texto', 'status', 'status_display', 'tentativas', 'reservado_em', 'enviado_em',
            'expira_em', 'proxima_tentativa_em', 'erro', 'passos', 'autor', 'autor_nome', 'criado_em',
        ]
        read_only_fields = fields


class MensagemManualSerializer(serializers.Serializer):
    pedido = serializers.IntegerField()
    texto = serializers.CharField()

    def validate_texto(self, v):
        if not v.strip():
            raise serializers.ValidationError('O texto não pode ficar vazio.')
        return v.strip()


class TokenExtensaoSerializer(serializers.ModelSerializer):
    empresas_ids = serializers.PrimaryKeyRelatedField(
        source='empresas', many=True, queryset=Empresa.objects.all(), write_only=True,
    )
    empresas = serializers.SerializerMethodField()

    class Meta:
        model = TokenExtensao
        fields = [
            'id', 'nome', 'prefixo', 'empresas', 'empresas_ids', 'ativo', 'criado_em',
            'ultimo_heartbeat', 'versao_extensao', 'ultimo_diagnostico',
        ]
        read_only_fields = ['prefixo', 'ativo', 'criado_em', 'ultimo_heartbeat', 'versao_extensao', 'ultimo_diagnostico']

    def get_empresas(self, obj):
        return [{'id': e.id, 'nome': e.nome} for e in obj.empresas.all()]
