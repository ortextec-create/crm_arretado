"""
App: eventos
Modelos para agendamento de eventos com entrega futura.

Estrutura:
  - LocalEvento    → locais de festa cadastráveis e reutilizáveis
  - Evento         → pedido agendado (casamento, aniversário, etc.)
  - ItemEvento     → itens do evento (doces, bolos, salgados, massas)

Ao salvar/atualizar um Evento, um signal espelha os dados
no PedidoUnificado (app pedidos), mantendo o histórico unificado
por cliente.
"""
from django.db import models
from django.utils import timezone
from clientes.models import Cliente


# ─────────────────────────────────────────────────────────────────────────────
# Local do Evento
# ─────────────────────────────────────────────────────────────────────────────

class LocalEvento(models.Model):
    nome       = models.CharField(max_length=200)
    endereco   = models.CharField(max_length=300, blank=True, default='')
    bairro     = models.CharField(max_length=100, blank=True, default='')
    cidade     = models.CharField(max_length=100, blank=True, default='Teresina')
    referencia = models.CharField(
        max_length=300, blank=True, default='',
        help_text='Ex: portão azul, fundos, sala 3'
    )
    ativo      = models.BooleanField(default=True, db_index=True)
    criado_em  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Local de Evento'
        verbose_name_plural = 'Locais de Evento'
        ordering            = ['nome']

    def __str__(self):
        return self.nome

    @property
    def endereco_completo(self):
        partes = [self.endereco, self.bairro, self.cidade]
        return ', '.join(p for p in partes if p)


# ─────────────────────────────────────────────────────────────────────────────
# Evento (pedido agendado)
# ─────────────────────────────────────────────────────────────────────────────

class Evento(models.Model):

    TIPO_EVENTO_CHOICES = [
        ('casamento',    'Casamento'),
        ('formatura',    'Formatura'),
        ('aniversario',  'Aniversário'),
        ('corporativo',  'Corporativo'),
        ('batizado',     'Batizado'),
        ('cha',          'Chá de bebê / revelação'),
        ('outro',        'Outro'),
    ]

    TIPO_ENTREGA_CHOICES = [
        ('retirada_loja',   'Retirada na loja'),
        ('entrega_local',   'Entrega no local da festa'),
    ]

    STATUS_CHOICES = [
        ('orcamento',    'Orçamento'),
        ('confirmado',   'Confirmado'),
        ('em_producao',  'Em produção'),
        ('pronto',       'Pronto'),
        ('entregue',     'Entregue'),
        ('cancelado',    'Cancelado'),
    ]

    # Número sequencial legível (EV-001, EV-002…)
    numero = models.CharField(max_length=20, unique=True, db_index=True)

    # Vínculo com o CRM
    cliente = models.ForeignKey(
        Cliente,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='eventos',
    )
    # Nome avulso para quando não há cliente no CRM
    cliente_nome     = models.CharField(max_length=200, blank=True, default='')
    cliente_telefone = models.CharField(max_length=30,  blank=True, default='')

    # Dados do evento
    tipo_evento   = models.CharField(max_length=30, choices=TIPO_EVENTO_CHOICES, default='aniversario')
    data_evento   = models.DateField(db_index=True)
    hora_evento   = models.TimeField(null=True, blank=True)

    # Entrega
    tipo_entrega      = models.CharField(max_length=20, choices=TIPO_ENTREGA_CHOICES, default='retirada_loja')
    local             = models.ForeignKey(
        LocalEvento,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='eventos',
    )
    endereco_avulso   = models.CharField(
        max_length=400, blank=True, default='',
        help_text='Endereço livre quando não for usar um local cadastrado'
    )

    # Status
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default='orcamento', db_index=True
    )

    # Financeiro
    subtotal      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    desconto      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_total   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sinal_pago    = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                        help_text='Valor de entrada/sinal já recebido')

    observacoes   = models.TextField(blank=True, default='')

    criado_em     = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Evento'
        verbose_name_plural = 'Eventos'
        ordering            = ['data_evento', 'hora_evento']
        indexes             = [
            models.Index(fields=['data_evento', 'status']),
            models.Index(fields=['cliente', 'data_evento']),
        ]

    def __str__(self):
        nome = self.cliente.nome if self.cliente else self.cliente_nome or '—'
        return f'{self.numero} — {nome} ({self.get_tipo_evento_display()}) {self.data_evento}'

    # ── Numeração automática ───────────────────────────────────────────────
    @classmethod
    def proximo_numero(cls):
        ultimo = cls.objects.order_by('-id').first()
        if not ultimo:
            return 'EV-0001'
        try:
            seq = int(ultimo.numero.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = cls.objects.count() + 1
        return f'EV-{seq:04d}'

    # ── Financeiro ────────────────────────────────────────────────────────
    def recalcular_totais(self):
        self.subtotal   = sum(i.preco_total for i in self.itens.all())
        self.valor_total = max(self.subtotal - self.desconto, 0)
        self.save(update_fields=['subtotal', 'valor_total', 'atualizado_em'])

    @property
    def saldo_restante(self):
        return max(self.valor_total - self.sinal_pago, 0)

    # ── Permissões de transição ───────────────────────────────────────────
    @property
    def pode_confirmar(self):
        return self.status == 'orcamento'

    @property
    def pode_iniciar_producao(self):
        return self.status == 'confirmado'

    @property
    def pode_marcar_pronto(self):
        return self.status == 'em_producao'

    @property
    def pode_entregar(self):
        return self.status == 'pronto'

    @property
    def pode_cancelar(self):
        return self.status not in ('entregue', 'cancelado')

    @property
    def nome_cliente_display(self):
        if self.cliente:
            return self.cliente.nome
        return self.cliente_nome or '—'

    @property
    def telefone_display(self):
        if self.cliente:
            return self.cliente.telefone_principal or self.cliente_telefone
        return self.cliente_telefone


# ─────────────────────────────────────────────────────────────────────────────
# Item do Evento
# ─────────────────────────────────────────────────────────────────────────────

class ItemEvento(models.Model):
    evento     = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='itens')

    # Vínculo com catálogo (snapshot de nome/preço para histórico fiel)
    produto    = models.ForeignKey(
        'pdv.Produto',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='itens_evento',
    )
    nome       = models.CharField(max_length=200)
    preco_unit = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade = models.PositiveIntegerField(default=1)
    preco_total = models.DecimalField(max_digits=10, decimal_places=2)
    observacao = models.CharField(max_length=300, blank=True, default='')

    class Meta:
        verbose_name        = 'Item de Evento'
        verbose_name_plural = 'Itens de Evento'
        ordering            = ['id']

    def __str__(self):
        return f'{self.quantidade}x {self.nome} — {self.evento.numero}'

    def save(self, *args, **kwargs):
        self.preco_total = self.preco_unit * self.quantidade
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Signal helper: sincroniza Evento → PedidoUnificado
# ─────────────────────────────────────────────────────────────────────────────

EVENTO_STATUS_MAP = {
    'orcamento':   'pendente',
    'confirmado':  'confirmado',
    'em_producao': 'em_preparo',
    'pronto':      'pronto',
    'entregue':    'concluido',
    'cancelado':   'cancelado',
}

EVENTO_TIPO_MAP = {
    'retirada_loja':  'retirada',
    'entrega_local':  'delivery',
}


def sincronizar_evento(evento):
    """
    Cria ou atualiza o PedidoUnificado correspondente a um Evento.
    Chamado pelo signal post_save do Evento (eventos/signals.py).
    """
    from pedidos.models import PedidoUnificado

    itens_snapshot = [
        {
            'nome':        item.nome,
            'quantidade':  item.quantidade,
            'preco_unit':  float(item.preco_unit),
            'preco_total': float(item.preco_total),
            'observacao':  item.observacao,
        }
        for item in evento.itens.all()
    ]

    defaults = {
        'cliente':    evento.cliente,
        'numero':     evento.numero,
        'status':     EVENTO_STATUS_MAP.get(evento.status, 'pendente'),
        'tipo':       EVENTO_TIPO_MAP.get(evento.tipo_entrega, 'retirada'),
        'total':      float(evento.valor_total),
        'itens_json': itens_snapshot,
        'pedido_em':  evento.criado_em,
    }

    PedidoUnificado.objects.update_or_create(
        canal='eventos',
        origem_id=evento.pk,
        defaults=defaults,
    )
