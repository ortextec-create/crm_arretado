from rest_framework import serializers
from .models import LocalEvento, Evento, ItemEvento, Orcamento, ItemOrcamento


# ─── Local de Evento ──────────────────────────────────────────────────────────

class LocalEventoSerializer(serializers.ModelSerializer):
    endereco_completo = serializers.ReadOnlyField()

    class Meta:
        model  = LocalEvento
        fields = ['id', 'nome', 'endereco', 'bairro', 'cidade', 'referencia',
                  'endereco_completo', 'ativo']


# ─── Item de Evento ───────────────────────────────────────────────────────────

class ItemEventoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ItemEvento
        fields = ['id', 'produto', 'nome', 'preco_unit', 'quantidade',
                  'preco_total', 'observacao']
        read_only_fields = ['preco_total']


class ItemEventoCreateSerializer(serializers.ModelSerializer):
    """Criação de item: popula nome/preco_unit a partir do produto se não informados."""

    class Meta:
        model  = ItemEvento
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


# ─── Evento ───────────────────────────────────────────────────────────────────

class EventoListSerializer(serializers.ModelSerializer):
    status_display       = serializers.CharField(source='get_status_display',       read_only=True)
    tipo_evento_display  = serializers.CharField(source='get_tipo_evento_display',  read_only=True)
    tipo_entrega_display = serializers.CharField(source='get_tipo_entrega_display', read_only=True)
    cliente_nome_crm     = serializers.SerializerMethodField()
    local_nome           = serializers.SerializerMethodField()
    saldo_restante       = serializers.ReadOnlyField()
    nome_cliente_display = serializers.ReadOnlyField()
    telefone_display     = serializers.ReadOnlyField()

    class Meta:
        model  = Evento
        fields = [
            'id', 'numero',
            'status', 'status_display',
            'tipo_evento', 'tipo_evento_display',
            'tipo_entrega', 'tipo_entrega_display',
            'data_evento', 'hora_evento',
            'cliente', 'cliente_nome', 'cliente_telefone',
            'cliente_nome_crm', 'nome_cliente_display', 'telefone_display',
            'local', 'local_nome', 'endereco_avulso', 'bairro_entrega', 'taxa_entrega',
            'subtotal', 'desconto', 'valor_total', 'sinal_pago', 'saldo_restante',
            'pode_confirmar', 'pode_iniciar_producao', 'pode_marcar_pronto',
            'pode_entregar', 'pode_cancelar',
            'criado_em', 'atualizado_em',
        ]

    def get_cliente_nome_crm(self, obj):
        return obj.cliente.nome if obj.cliente else None

    def get_local_nome(self, obj):
        return obj.local.nome if obj.local else None


class EventoDetailSerializer(EventoListSerializer):
    itens = ItemEventoSerializer(many=True, read_only=True)
    local_detalhe = LocalEventoSerializer(source='local', read_only=True)

    class Meta(EventoListSerializer.Meta):
        fields = EventoListSerializer.Meta.fields + ['itens', 'local_detalhe', 'observacoes']


class EventoCreateSerializer(serializers.ModelSerializer):
    itens = ItemEventoCreateSerializer(many=True, required=False)

    class Meta:
        model  = Evento
        fields = [
            'cliente', 'cliente_nome', 'cliente_telefone',
            'tipo_evento', 'data_evento', 'hora_evento',
            'tipo_entrega', 'local', 'endereco_avulso', 'bairro_entrega', 'taxa_entrega',
            'desconto', 'sinal_pago', 'observacoes',
            'itens',
        ]

    def validate(self, data):
        if data.get('tipo_entrega') == 'entrega_local':
            if not data.get('local') and not data.get('endereco_avulso'):
                raise serializers.ValidationError(
                    'Para entrega no local, informe o local cadastrado ou o endereço avulso.'
                )
        return data

    def create(self, validated_data):
        itens_data = validated_data.pop('itens', [])
        validated_data['numero'] = Evento.proximo_numero()
        evento = Evento.objects.create(**validated_data)

        subtotal = 0
        for item_data in itens_data:
            qty   = item_data.get('quantidade', 1)
            price = item_data['preco_unit']
            total = price * qty
            ItemEvento.objects.create(
                evento=evento,
                preco_total=total,
                **item_data,
            )
            subtotal += total

        evento.subtotal    = subtotal
        evento.valor_total = max(subtotal - evento.desconto, 0) + evento.taxa_entrega
        evento.save(update_fields=['subtotal', 'valor_total'])
        return evento

    def update(self, instance, validated_data):
        # Itens não são atualizados em massa via PUT — use os endpoints de item
        validated_data.pop('itens', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class EventoAgendaSerializer(serializers.ModelSerializer):
    """Serializer leve para a view de calendário."""
    tipo_evento_display  = serializers.CharField(source='get_tipo_evento_display',  read_only=True)
    tipo_entrega_display = serializers.CharField(source='get_tipo_entrega_display', read_only=True)
    status_display       = serializers.CharField(source='get_status_display',       read_only=True)
    nome_cliente_display = serializers.ReadOnlyField()
    local_nome           = serializers.SerializerMethodField()

    class Meta:
        model  = Evento
        fields = [
            'id', 'numero', 'tipo_evento', 'tipo_evento_display',
            'data_evento', 'hora_evento',
            'status', 'status_display',
            'tipo_entrega', 'tipo_entrega_display',
            'nome_cliente_display', 'local_nome',
            'valor_total',
        ]

    def get_local_nome(self, obj):
        return obj.local.nome if obj.local else None


# ─── Orçamento ────────────────────────────────────────────────────────────────

class ItemOrcamentoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ItemOrcamento
        fields = ['id', 'produto', 'nome', 'preco_unit', 'quantidade',
                  'preco_total', 'observacao']
        read_only_fields = ['preco_total']


class ItemOrcamentoCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ItemOrcamento
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


class OrcamentoListSerializer(serializers.ModelSerializer):
    status_display       = serializers.CharField(source='get_status_display',      read_only=True)
    tipo_evento_display  = serializers.CharField(source='get_tipo_evento_display', read_only=True)
    tipo_entrega_display = serializers.CharField(source='get_tipo_entrega_display', read_only=True)
    nome_cliente_display = serializers.ReadOnlyField()
    telefone_display     = serializers.ReadOnlyField()
    cliente_nome_crm     = serializers.SerializerMethodField()
    evento_numero        = serializers.SerializerMethodField()
    local_nome           = serializers.SerializerMethodField()

    class Meta:
        model  = Orcamento
        fields = [
            'id', 'numero',
            'status', 'status_display',
            'tipo_evento', 'tipo_evento_display',
            'data_evento', 'validade',
            'cliente', 'cliente_nome', 'cliente_telefone',
            'cliente_nome_crm', 'nome_cliente_display', 'telefone_display',
            'tipo_entrega', 'tipo_entrega_display',
            'local', 'local_nome', 'endereco_avulso', 'bairro_entrega', 'taxa_entrega',
            'subtotal', 'desconto', 'valor_total',
            'pode_enviar', 'pode_aprovar', 'pode_recusar',
            'pode_converter', 'pode_cancelar', 'pode_restaurar',
            'evento', 'evento_numero',
            'criado_em', 'atualizado_em',
        ]

    def get_cliente_nome_crm(self, obj):
        return obj.cliente.nome if obj.cliente else None

    def get_evento_numero(self, obj):
        return obj.evento.numero if obj.evento else None

    def get_local_nome(self, obj):
        return obj.local.nome if obj.local else None


class OrcamentoDetailSerializer(OrcamentoListSerializer):
    itens = ItemOrcamentoSerializer(many=True, read_only=True)

    class Meta(OrcamentoListSerializer.Meta):
        fields = OrcamentoListSerializer.Meta.fields + ['itens', 'observacoes']


class OrcamentoCreateSerializer(serializers.ModelSerializer):
    itens = ItemOrcamentoCreateSerializer(many=True, required=False)

    class Meta:
        model  = Orcamento
        fields = [
            'cliente', 'cliente_nome', 'cliente_telefone',
            'tipo_evento', 'data_evento', 'validade',
            'tipo_entrega', 'local', 'endereco_avulso', 'bairro_entrega', 'taxa_entrega',
            'desconto', 'observacoes',
            'itens',
        ]

    def validate(self, data):
        if data.get('tipo_entrega') == 'entrega_local':
            if not data.get('local') and not data.get('endereco_avulso'):
                raise serializers.ValidationError(
                    'Para entrega no local, informe o local cadastrado ou o endereço avulso.'
                )
        return data

    def create(self, validated_data):
        import datetime
        from django.conf import settings
        from django.utils import timezone

        itens_data = validated_data.pop('itens', [])
        validated_data['numero'] = Orcamento.proximo_numero()

        if not validated_data.get('validade'):
            from notificacoes.models import ConfiguracaoWhatsApp
            dias = ConfiguracaoWhatsApp.get().validade_orcamento_dias
            validated_data['validade'] = timezone.now().date() + datetime.timedelta(days=dias)

        orcamento = Orcamento.objects.create(**validated_data)

        subtotal = 0
        for item_data in itens_data:
            qty   = item_data.get('quantidade', 1)
            price = item_data['preco_unit']
            total = price * qty
            ItemOrcamento.objects.create(
                orcamento=orcamento,
                preco_total=total,
                **item_data,
            )
            subtotal += total

        orcamento.subtotal    = subtotal
        orcamento.valor_total = max(subtotal - orcamento.desconto, 0) + orcamento.taxa_entrega
        orcamento.save(update_fields=['subtotal', 'valor_total'])
        return orcamento

    def update(self, instance, validated_data):
        validated_data.pop('itens', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
