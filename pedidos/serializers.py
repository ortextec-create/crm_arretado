"""
ARQUIVO NOVO: pedidos/serializers.py — Fase 4
"""
from rest_framework import serializers
from .models import PedidoUnificado
from clientes.serializers import ClienteListSerializer


class PedidoUnificadoSerializer(serializers.ModelSerializer):
    canal_label  = serializers.CharField(source='get_canal_display',  read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    tipo_label   = serializers.CharField(source='get_tipo_display',   read_only=True)
    cliente_info = ClienteListSerializer(source='cliente', read_only=True)

    class Meta:
        model = PedidoUnificado
        fields = [
            'id', 'canal', 'canal_label',
            'origem_id', 'numero',
            'status', 'status_label', 'status_original',
            'tipo', 'tipo_label',
            'subtotal', 'taxa_entrega', 'desconto', 'total', 'pagamento',
            'cliente', 'cliente_info', 'cliente_nome', 'cliente_telefone',
            'itens_snapshot', 'endereco_entrega',
            'pedido_em', 'sincronizado_em',
        ]
        read_only_fields = fields  # escrita só via signals/vincular-cliente
