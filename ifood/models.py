from django.db import models
from django.utils import timezone
from clientes.models import Cliente


class ConfiguracaoIFood(models.Model):
    """Credenciais OAuth e configurações do merchant iFood."""
    client_id     = models.CharField(max_length=200)
    client_secret = models.CharField(max_length=200)
    merchant_id   = models.CharField(max_length=200)

    # Token gerenciado automaticamente pelo worker
    access_token    = models.TextField(blank=True, default='')
    token_expira_em = models.DateTimeField(null=True, blank=True)
    refresh_token   = models.TextField(blank=True, default='')

    # Estado do polling
    polling_ativo     = models.BooleanField(default=False)
    ultimo_polling    = models.DateTimeField(null=True, blank=True)
    polling_intervalo = models.IntegerField(default=30, help_text='Segundos entre polls')

    # Confirmação automática ao receber pedido (necessário para homologação iFood)
    auto_confirmar = models.BooleanField(
        default=False,
        help_text='Confirma automaticamente todo pedido PLACED ao recebê-lo via polling',
    )
    # Despacho automático após confirmação (cenário "Pedido Despachado Imediato")
    auto_despachar = models.BooleanField(
        default=False,
        help_text='Despacha (DELIVERY) ou marca como pronto (TAKEOUT) logo após confirmar. Requer auto_confirmar=True',
    )

    criado_em    = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração iFood'
        verbose_name_plural = 'Configurações iFood'

    def __str__(self):
        return f'iFood — {self.merchant_id}'

    @property
    def token_valido(self):
        if not self.access_token or not self.token_expira_em:
            return False
        # 60s de margem
        return timezone.now() < self.token_expira_em - timezone.timedelta(seconds=60)


class PedidoIFood(models.Model):
    """Pedido recebido via API do iFood."""

    STATUS_CHOICES = [
        ('PLACED',            'Aguardando confirmação'),
        ('CONFIRMED',         'Confirmado'),
        ('PREPARATION_STARTED', 'Em preparo'),
        ('READY_TO_PICKUP',   'Pronto / Aguardando retirada'),
        ('DISPATCHED',        'Despachado'),
        ('CONCLUDED',         'Concluído'),
        ('CANCELLATION_REQUESTED', 'Cancelamento solicitado'),
        ('CANCELLED',         'Cancelado'),
    ]

    ORDER_TYPE_CHOICES = [
        ('DELIVERY',  'Delivery'),
        ('TAKEOUT',   'Retirada'),
        ('INDOOR',    'Mesa'),
    ]

    # iFood IDs
    ifood_order_id  = models.CharField(max_length=100, unique=True, db_index=True)
    ifood_merchant_id = models.CharField(max_length=100, db_index=True)
    display_id       = models.CharField(max_length=20, blank=True, default='')

    # Vínculo com cliente CRM (pode ser nulo se ainda não associado)
    cliente = models.ForeignKey(
        Cliente, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='pedidos_ifood'
    )

    # Dados do pedido
    status        = models.CharField(max_length=40, choices=STATUS_CHOICES, default='PLACED')
    order_type    = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default='DELIVERY')
    total_valor   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    taxa_entrega  = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    desconto      = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=100, blank=True, default='')
    payment_brand    = models.CharField(max_length=60,  blank=True, default='')  # bandeira: VISA, MASTERCARD…
    payment_troco    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # troco solicitado
    payment_prepaid  = models.BooleanField(default=False)  # True = pago online; False = pagar na entrega

    # Dados do cliente (Cenário 5)
    cliente_cpf      = models.CharField(max_length=20, blank=True, default='')   # CPF/CNPJ para nota

    # Observação do pedido (Cenário 5)
    observacao_pedido = models.TextField(blank=True, default='')

    # Agendamento (Cenário 1)
    agendamento_dt   = models.DateTimeField(null=True, blank=True)  # scheduledDateTimeEnd

    # Cupons / benefícios (Cenário 1)
    benefits_raw     = models.JSONField(default=list, blank=True)   # lista de benefits do payload

    # Plataforma de Negociação (Cenário 4)
    negociacao_pendente  = models.BooleanField(default=False)       # True enquanto aguarda ação do operador
    negociacao_tipo      = models.CharField(max_length=60, blank=True, default='')  # ex: CONSUMER_CANCELLATION_REQUESTED
    negociacao_descricao = models.TextField(blank=True, default='') # motivo enviado pelo consumidor
    # Cliente iFood (pode não estar vinculado ao CRM)
    cliente_nome     = models.CharField(max_length=200, blank=True, default='')
    cliente_telefone = models.CharField(max_length=30, blank=True, default='')
    cliente_ifood_id = models.CharField(max_length=100, blank=True, default='', db_index=True)

    # Modo de entrega: MERCHANT (restaurante entrega), IFOOD_DELIVERY (iFood entrega)
    # Vazio para TAKEOUT/INDOOR ou quando não informado pelo iFood
    delivery_mode = models.CharField(max_length=30, blank=True, default='')

    # Entrega
    endereco_entrega = models.JSONField(default=dict, blank=True)

    # Payload completo guardado para referência
    payload_raw = models.JSONField(default=dict, blank=True)

    # Timestamps
    criado_em     = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    # Quando o iFood criou o pedido
    ifood_criado_em = models.DateTimeField(null=True, blank=True)

    

    class Meta:
        verbose_name = 'Pedido iFood'
        verbose_name_plural = 'Pedidos iFood'
        ordering = ['-ifood_criado_em']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['criado_em']),
            models.Index(fields=['cliente_ifood_id']),
        ]

    def __str__(self):
        return f'Pedido #{self.display_id or self.ifood_order_id[:8]} — {self.get_status_display()}'

    @property
    def pode_confirmar(self):
        return self.status == 'PLACED'

    @property
    def pode_cancelar(self):
        return self.status in ('PLACED', 'CONFIRMED', 'PREPARATION_STARTED', 'DISPATCHED')


class ItemPedidoIFood(models.Model):
    """Item de um pedido iFood."""
    pedido      = models.ForeignKey(PedidoIFood, on_delete=models.CASCADE, related_name='itens')
    ifood_item_id = models.CharField(max_length=100, blank=True, default='')
    nome        = models.CharField(max_length=300)
    quantidade  = models.IntegerField(default=1)
    preco_unit  = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    preco_total = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    observacao  = models.TextField(blank=True, default='')
    # Complementos/adicionais como JSON
    complementos = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = 'Item do Pedido'
        ordering = ['id']

    def __str__(self):
        return f'{self.quantidade}x {self.nome}'


class EventoPollingIFood(models.Model):
    """Log de cada evento recebido do polling iFood."""
    EVENT_CODES = [
        ('PLC', 'PLACED — Pedido criado'),
        ('CFM', 'CONFIRMED — Confirmado'),
        ('DSP', 'DISPATCHED — Despachado'),
        ('CAN', 'CANCELLATION_REQUESTED'),
        ('CAC', 'CANCELLED'),
        ('CON', 'CONCLUDED'),
        ('HBT', 'HEARTBEAT'),
        ('OTH', 'Outro'),
    ]

    ifood_event_id = models.CharField(max_length=100, unique=True)
    code           = models.CharField(max_length=10, choices=EVENT_CODES, default='OTH')
    full_code      = models.CharField(max_length=60, blank=True, default='')
    order_id       = models.CharField(max_length=100, blank=True, default='')
    merchant_id    = models.CharField(max_length=100, blank=True, default='')
    acknowledged   = models.BooleanField(default=False)
    processado     = models.BooleanField(default=False)
    payload        = models.JSONField(default=dict)
    criado_em      = models.DateTimeField(auto_now_add=True)
    ifood_criado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Evento de Polling'
        verbose_name_plural = 'Eventos de Polling'
        ordering = ['-ifood_criado_em']

    def __str__(self):
        return f'{self.full_code} — {self.order_id[:12]}'
