"""
App: pedidos
Modelo unificado de pedidos — agrega iFood, Anota AI e PDV próprio
em uma tabela única para histórico, relatórios e CRM.

Cada canal continua tendo seu próprio app com modelo nativo completo
(PedidoIFood, PedidoAnotaAI, PedidoPDV). O PedidoUnificado é uma
camada de leitura/espelho, populada por signals ou workers,
que permite consultas unificadas por cliente sem joins complexos.
"""
from django.db import models
from django.utils import timezone
from clientes.models import Cliente


class PedidoUnificado(models.Model):
    """
    Espelho unificado de pedidos de todos os canais.

    Não substitui os modelos nativos de cada canal — é uma projeção
    normalizada para permitir histórico, métricas e relatórios unificados
    por cliente sem depender de joins entre apps distintos.

    Populado automaticamente via signals (post_save) em cada app de canal.
    """

    # ── Canal de origem ────────────────────────────────────────────────────
    CANAL_CHOICES = [
        ('ifood',   'iFood'),
        ('anotaai', 'Anota AI'),
        ('pdv',     'PDV Próprio'),
    ]

    canal = models.CharField(
        max_length=20,
        choices=CANAL_CHOICES,
        db_index=True,
    )

    # ID do objeto nativo no app de origem (PedidoIFood.id, etc.)
    origem_id = models.PositiveIntegerField(
        db_index=True,
        help_text='PK do pedido no app de origem (ifood.PedidoIFood, etc.)',
    )

    # Número/código exibível ao operador (display_id do iFood, número do PDV…)
    numero = models.CharField(max_length=50, blank=True, default='')

    # ── Vínculo com o CRM ─────────────────────────────────────────────────
    cliente = models.ForeignKey(
        Cliente,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='pedidos_unificados',
        db_index=True,
    )

    # ── Status normalizado ────────────────────────────────────────────────
    STATUS_CHOICES = [
        ('pendente',    'Pendente'),
        ('confirmado',  'Confirmado'),
        ('em_preparo',  'Em preparo'),
        ('pronto',      'Pronto / Aguardando retirada'),
        ('em_entrega',  'Em entrega'),
        ('concluido',   'Concluído'),
        ('cancelado',   'Cancelado'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pendente',
        db_index=True,
    )

    # Status original do canal (string livre — ex: 'PLACED', 'CONCLUDED')
    status_original = models.CharField(max_length=50, blank=True, default='')

    # ── Tipo de pedido normalizado ─────────────────────────────────────────
    TIPO_CHOICES = [
        ('delivery', 'Delivery'),
        ('retirada', 'Retirada'),
        ('mesa',     'Mesa / Indoor'),
        ('balcao',   'Balcão'),
    ]

    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='delivery',
    )

    # ── Valores financeiros ────────────────────────────────────────────────
    subtotal     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    taxa_entrega = models.DecimalField(max_digits=8,  decimal_places=2, default=0)
    desconto     = models.DecimalField(max_digits=8,  decimal_places=2, default=0)
    total        = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # ── Pagamento ──────────────────────────────────────────────────────────
    pagamento = models.CharField(max_length=100, blank=True, default='')

    # ── Dados do cliente no momento do pedido ─────────────────────────────
    # (desnormalizado para manter histórico mesmo se o CRM for alterado)
    cliente_nome     = models.CharField(max_length=200, blank=True, default='')
    cliente_telefone = models.CharField(max_length=30,  blank=True, default='')

    # ── Endereço de entrega snapshot ──────────────────────────────────────
    endereco_entrega = models.JSONField(default=dict, blank=True)

    # ── Itens snapshot ────────────────────────────────────────────────────
    # Lista de dicts: [{nome, quantidade, preco_unit, preco_total, obs, complementos}]
    itens_snapshot = models.JSONField(
        default=list, blank=True,
        help_text='Snapshot dos itens no momento do pedido',
    )

    # ── Timestamps ────────────────────────────────────────────────────────
    pedido_em     = models.DateTimeField(
        db_index=True,
        help_text='Data/hora em que o pedido foi criado no canal de origem',
    )
    sincronizado_em = models.DateTimeField(auto_now=True)
    criado_em       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Pedido Unificado'
        verbose_name_plural = 'Pedidos Unificados'
        ordering            = ['-pedido_em']
        # Garante unicidade por canal + origem (evita duplicatas no espelho)
        unique_together = [('canal', 'origem_id')]
        indexes = [
            models.Index(fields=['cliente', '-pedido_em']),
            models.Index(fields=['canal', 'status']),
            models.Index(fields=['pedido_em']),
        ]

    def __str__(self):
        canal_label = dict(self.CANAL_CHOICES).get(self.canal, self.canal)
        return f'[{canal_label}] #{self.numero or self.origem_id} — {self.get_status_display()}'

    @property
    def cancelado(self):
        return self.status == 'cancelado'

    @property
    def concluido(self):
        return self.status == 'concluido'


# ─────────────────────────────────────────────────────────────────────────────
# Signal: sincroniza PedidoIFood → PedidoUnificado automaticamente
# ─────────────────────────────────────────────────────────────────────────────

# Mapeamento de status iFood → status unificado
IFOOD_STATUS_MAP = {
    'PLACED':                   'pendente',
    'CONFIRMED':                'confirmado',
    'PREPARATION_STARTED':      'em_preparo',
    'READY_TO_PICKUP':          'pronto',
    'DISPATCHED':               'em_entrega',
    'CONCLUDED':                'concluido',
    'CANCELLATION_REQUESTED':   'cancelado',
    'CANCELLED':                'cancelado',
}

# Mapeamento de tipo iFood → tipo unificado
IFOOD_TIPO_MAP = {
    'DELIVERY': 'delivery',
    'TAKEOUT':  'retirada',
    'INDOOR':   'mesa',
}


def _itens_ifood_para_snapshot(pedido_ifood):
    """Converte itens de PedidoIFood para o formato snapshot unificado."""
    itens = []
    for item in pedido_ifood.itens.all():
        itens.append({
            'nome':         item.nome,
            'quantidade':   item.quantidade,
            'preco_unit':   float(item.preco_unit),
            'preco_total':  float(item.preco_total),
            'observacao':   item.observacao,
            'complementos': item.complementos,
        })
    return itens


def sincronizar_pedido_ifood(pedido_ifood):
    """
    Cria ou atualiza o PedidoUnificado correspondente a um PedidoIFood.
    Chamado pelo signal post_save do PedidoIFood.
    """
    defaults = {
        'numero':          pedido_ifood.display_id or pedido_ifood.ifood_order_id[:8],
        'cliente':         pedido_ifood.cliente,
        'status':          IFOOD_STATUS_MAP.get(pedido_ifood.status, 'pendente'),
        'status_original': pedido_ifood.status,
        'tipo':            IFOOD_TIPO_MAP.get(pedido_ifood.order_type, 'delivery'),
        'subtotal':        pedido_ifood.subtotal,
        'taxa_entrega':    pedido_ifood.taxa_entrega,
        'desconto':        pedido_ifood.desconto,
        'total':           pedido_ifood.total_valor,
        'pagamento':       pedido_ifood.payment_method,
        'cliente_nome':    pedido_ifood.cliente_nome,
        'cliente_telefone':pedido_ifood.cliente_telefone,
        'endereco_entrega':pedido_ifood.endereco_entrega,
        'itens_snapshot':  _itens_ifood_para_snapshot(pedido_ifood),
        'pedido_em':       pedido_ifood.ifood_criado_em or pedido_ifood.criado_em,
    }

    PedidoUnificado.objects.update_or_create(
        canal='ifood',
        origem_id=pedido_ifood.pk,
        defaults=defaults,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Registro do signal (coloque isto em pedidos/apps.py → ready())
# ─────────────────────────────────────────────────────────────────────────────
#
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from ifood.models import PedidoIFood
# from .models import sincronizar_pedido_ifood
#
# @receiver(post_save, sender=PedidoIFood)
# def on_pedido_ifood_save(sender, instance, **kwargs):
#     sincronizar_pedido_ifood(instance)
#
