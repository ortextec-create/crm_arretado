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
            'merchant_id', 'polling_ativo', 'polling_intervalo', 'auto_confirmar', 'auto_despachar',
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
            'order_type', 'order_type_display', 'delivery_mode',
            'total_valor', 'payment_method',
            'cliente_nome', 'cliente_nome_crm',
            'pode_confirmar', 'pode_cancelar',
            'ifood_criado_em', 'atualizado_em',
        ]

    def get_cliente_nome_crm(self, obj):
        return obj.cliente.nome if obj.cliente else None


class PedidoIFoodDetailSerializer(serializers.ModelSerializer):
    """Serializer completo com itens — inclui campos de homologação."""
    status_display     = serializers.CharField(source='get_status_display', read_only=True)
    order_type_display = serializers.CharField(source='get_order_type_display', read_only=True)
    itens              = ItemPedidoSerializer(many=True, read_only=True)
    cliente_crm_id     = serializers.SerializerMethodField()
    cliente_nome_crm   = serializers.SerializerMethodField()

    # ── Campos extras para homologação ──────────────────────────────────────
    # Pagamento detalhado
    payment_brand    = serializers.CharField(read_only=True)
    payment_troco    = serializers.DecimalField(max_digits=10, decimal_places=2,
                                                 read_only=True, allow_null=True)
    payment_prepaid  = serializers.BooleanField(read_only=True)

    # Cliente fiscal
    cliente_cpf       = serializers.CharField(read_only=True)

    # Pedido
    observacao_pedido = serializers.CharField(read_only=True)

    # Agendamento
    agendamento_dt    = serializers.DateTimeField(read_only=True, allow_null=True)

    # Benefícios / cupons
    benefits_raw      = serializers.JSONField(read_only=True)

    # Negociação
    negociacao_pendente  = serializers.BooleanField(read_only=True)
    negociacao_tipo      = serializers.CharField(read_only=True)
    negociacao_descricao = serializers.CharField(read_only=True)

    class Meta:
        model  = PedidoIFood
        fields = [
            'id', 'ifood_order_id', 'display_id',
            'status', 'status_display',
            'order_type', 'order_type_display', 'delivery_mode',
            'total_valor', 'subtotal', 'taxa_entrega', 'desconto',
            # Pagamento
            'payment_method', 'payment_brand', 'payment_troco', 'payment_prepaid',
            # Cliente
            'cliente_nome', 'cliente_telefone', 'cliente_ifood_id',
            'cliente_cpf',
            'cliente_crm_id', 'cliente_nome_crm',
            # Pedido
            'observacao_pedido', 'agendamento_dt', 'benefits_raw',
            # Negociação
            'negociacao_pendente', 'negociacao_tipo', 'negociacao_descricao',
            # Endereço e itens
            'endereco_entrega', 'itens',
            # Ações e datas
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
