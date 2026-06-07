from rest_framework import serializers
from .models import HistoricoMensagem, ConfiguracaoWhatsApp


class ConfiguracaoWhatsAppSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ConfiguracaoWhatsApp
        fields = [
            'zapi_instance_id', 'zapi_token', 'zapi_client_token',
            'notificacoes_pedido_ativo', 'aniversario_ativo',
            'reengajamento_ativo', 'dias_sem_compra',
            'mensagem_aniversario', 'mensagem_reengajamento',
            'atualizado_em',
        ]
        read_only_fields = ['atualizado_em']


class HistoricoMensagemSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.SerializerMethodField()
    tipo_label   = serializers.CharField(source='get_tipo_display',   read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model  = HistoricoMensagem
        fields = [
            'id', 'cliente', 'cliente_nome', 'telefone',
            'mensagem', 'tipo', 'tipo_label', 'status', 'status_label',
            'erro', 'enviado_em',
        ]
        read_only_fields = ['id', 'status', 'erro', 'enviado_em']

    def get_cliente_nome(self, obj):
        return obj.cliente.nome if obj.cliente else None


class EnviarMensagemSerializer(serializers.Serializer):
    cliente_id = serializers.IntegerField(required=False, allow_null=True)
    telefone   = serializers.CharField(max_length=30, required=False, allow_blank=True)
    mensagem   = serializers.CharField()
    tipo       = serializers.ChoiceField(
        choices=HistoricoMensagem.TIPO_CHOICES,
        default='manual',
    )

    def validate(self, data):
        if not data.get('cliente_id') and not data.get('telefone'):
            raise serializers.ValidationError('Informe cliente_id ou telefone.')
        return data
