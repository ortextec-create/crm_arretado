from rest_framework import serializers
from .models import ConfiguracaoIFood, PedidoIFood, ItemPedidoIFood, EventoPollingIFood


class ConfiguracaoIFoodSerializer(serializers.ModelSerializer):
    token_valido    = serializers.ReadOnlyField()
    # Nunca expõe o secret completo — apenas os primeiros 6 chars
    client_secret_preview = serializers.SerializerMethodField()

    class Meta:
        model  = ConfiguracaoIFood
        fields = [
            'id', 'client_id', 'client_secret', 'client_secret_preview',
            'merchant_id', 'polling_ativo', 'polling_intervalo',
            'token_valido', 'ultimo_polling', 'token_expira_em',
            'criado_em', 'atualizado_em',
        ]
        extra_kwargs = {
            'client_secret': {'write_only': True},
        }

    def get_client_secret_preview(self, obj):
        if obj.client_secret:
            return obj.client_secret[:6] + '••••••••'
        return ''


class ItemPedidoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ItemPedidoIFood
        fields = [
            'id', 'nome', 'quantidade', 'preco_unit',
            'preco_total', 'observacao', 'complementos',
        ]


class PedidoIFoodListSerializer(serializers.ModelSerializer):
    """Serializer compacto para listagem."""
    status_display     = serializers.CharField(source='get_status_display', read_only=True)
    order_type_display = serializers.CharField(source='get_order_type_display', read_only=True)
    cliente_nome_crm   = serializers.SerializerMethodField()

    class Meta:
        model  = PedidoIFood
        fields = [
            'id', 'ifood_order_id', 'display_id',
            'status', 'status_display',
            'order_type', 'order_type_display',
            'total_valor', 'payment_method',
            'cliente_nome', 'cliente_nome_crm',
            'pode_confirmar', 'pode_cancelar',
            'ifood_criado_em', 'atualizado_em',
        ]

    def get_cliente_nome_crm(self, obj):
        return obj.cliente.nome if obj.cliente else None


class PedidoIFoodDetailSerializer(serializers.ModelSerializer):
    """Serializer completo com itens."""
    status_display     = serializers.CharField(source='get_status_display', read_only=True)
    order_type_display = serializers.CharField(source='get_order_type_display', read_only=True)
    itens              = ItemPedidoSerializer(many=True, read_only=True)
    cliente_crm_id     = serializers.SerializerMethodField()
    cliente_nome_crm   = serializers.SerializerMethodField()

    class Meta:
        model  = PedidoIFood
        fields = [
            'id', 'ifood_order_id', 'display_id',
            'status', 'status_display',
            'order_type', 'order_type_display',
            'total_valor', 'subtotal', 'taxa_entrega', 'desconto',
            'payment_method',
            'cliente_nome', 'cliente_telefone', 'cliente_ifood_id',
            'cliente_crm_id', 'cliente_nome_crm',
            'endereco_entrega', 'itens',
            'pode_confirmar', 'pode_cancelar',
            'ifood_criado_em', 'criado_em', 'atualizado_em',
        ]

    def get_cliente_crm_id(self, obj):
        return obj.cliente.id if obj.cliente else None

    def get_cliente_nome_crm(self, obj):
        return obj.cliente.nome if obj.cliente else None


class EventoPollingSerializer(serializers.ModelSerializer):
    class Meta:
        model  = EventoPollingIFood
        fields = [
            'id', 'ifood_event_id', 'code', 'full_code',
            'order_id', 'acknowledged', 'processado',
            'ifood_criado_em', 'criado_em',
        ]
