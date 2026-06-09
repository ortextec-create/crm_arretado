"""
App: pdv
Modelos nativos do PDV Próprio da Arretado Doces.

Estrutura:
  - Produto      → catálogo de itens vendáveis
  - PedidoPDV    → pedido aberto manualmente pelo operador
  - ItemPedidoPDV → linha de item dentro de um PedidoPDV

Ao salvar/atualizar um PedidoPDV, um signal espelha os dados
no PedidoUnificado (app pedidos), mantendo o histórico unificado
por cliente.
"""
from django.db import models
from django.utils import timezone
from clientes.models import Cliente


# ─────────────────────────────────────────────────────────────────────────────
# Catálogo de Produtos
# ─────────────────────────────────────────────────────────────────────────────

class CategoriaProduto(models.Model):
    nome  = models.CharField(max_length=100, unique=True)
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering            = ['ordem', 'nome']

    def __str__(self):
        return self.nome


class Produto(models.Model):
    SEGMENTO_CHOICES = [
        ('unidade_pequena', 'Unidade Pequena'),
        ('unidade_media',   'Unidade Média'),
        ('bem_casado',      'Bem Casado'),
        ('bolo_encomenda',  'Bolo / Encomenda'),
        ('outro',           'Outro'),
    ]

    nome      = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, default='')
    preco     = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.ForeignKey(
        CategoriaProduto,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='produtos',
    )
    foto               = models.ImageField(upload_to='produtos/', null=True, blank=True)
    disponivel_pdv     = models.BooleanField(default=True)
    disponivel_ifood   = models.BooleanField(default=False)
    disponivel_eventos = models.BooleanField(default=False)
    segmento           = models.CharField(
        max_length=30, choices=SEGMENTO_CHOICES, default='outro'
    )
    ativo       = models.BooleanField(default=True, db_index=True)
    criado_em   = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering            = ['categoria__ordem', 'nome']
        indexes             = [models.Index(fields=['ativo', 'nome'])]

    def __str__(self):
        return f'{self.nome} — R$ {self.preco}'


# ─────────────────────────────────────────────────────────────────────────────
# Pedido PDV
# ─────────────────────────────────────────────────────────────────────────────

class PedidoPDV(models.Model):

    STATUS_CHOICES = [
        ('aberto',     'Aberto'),
        ('confirmado', 'Confirmado'),
        ('em_preparo', 'Em preparo'),
        ('pronto',     'Pronto'),
        ('concluido',  'Concluído'),
        ('cancelado',  'Cancelado'),
    ]

    TIPO_CHOICES = [
        ('balcao',   'Balcão'),
        ('retirada', 'Retirada'),
        ('delivery', 'Delivery'),
        ('mesa',     'Mesa'),
    ]

    PAGAMENTO_CHOICES = [
        ('dinheiro',  'Dinheiro'),
        ('pix',       'PIX'),
        ('credito',   'Cartão de Crédito'),
        ('debito',    'Cartão de Débito'),
        ('outro',     'Outro'),
    ]

    # Número sequencial legível (ex: 001, 002…)
    numero = models.CharField(max_length=20, unique=True, db_index=True)

    # Vínculo com o CRM (opcional — pode ser cliente avulso)
    cliente = models.ForeignKey(
        Cliente,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='pedidos_pdv',
    )
    # Nome/telefone avulso para quando não há cliente no CRM
    cliente_nome     = models.CharField(max_length=200, blank=True, default='')
    cliente_telefone = models.CharField(max_length=30,  blank=True, default='')

    status    = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aberto', db_index=True)
    tipo      = models.CharField(max_length=20, choices=TIPO_CHOICES,   default='balcao')
    pagamento = models.CharField(max_length=20, choices=PAGAMENTO_CHOICES, blank=True, default='')

    subtotal     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    desconto     = models.DecimalField(max_digits=8,  decimal_places=2, default=0)
    taxa_entrega = models.DecimalField(max_digits=8,  decimal_places=2, default=0)
    total        = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    observacoes  = models.TextField(blank=True, default='')

    criado_em     = models.DateTimeField(auto_now_add=True, db_index=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Pedido PDV'
        verbose_name_plural = 'Pedidos PDV'
        ordering            = ['-criado_em']
        indexes             = [
            models.Index(fields=['status']),
            models.Index(fields=['criado_em']),
        ]

    def __str__(self):
        return f'PDV #{self.numero} — {self.get_status_display()}'

    # ── Helpers de status ──────────────────────────────────────────────────

    @property
    def pode_confirmar(self):
        return self.status == 'aberto'

    @property
    def pode_cancelar(self):
        return self.status not in ('concluido', 'cancelado')

    @property
    def pode_concluir(self):
        return self.status in ('confirmado', 'em_preparo', 'pronto')

    # ── Recalcula totais a partir dos itens ───────────────────────────────

    def recalcular_totais(self):
        subtotal = sum(i.preco_total for i in self.itens.all())
        self.subtotal = subtotal
        self.total    = subtotal - self.desconto + self.taxa_entrega
        self.save(update_fields=['subtotal', 'total', 'atualizado_em'])

    # ── Gera próximo número sequencial ────────────────────────────────────

    @classmethod
    def proximo_numero(cls):
        ultimo = cls.objects.order_by('-id').first()
        seq    = (ultimo.id + 1) if ultimo else 1
        return str(seq).zfill(4)


# ─────────────────────────────────────────────────────────────────────────────
# Itens do Pedido PDV
# ─────────────────────────────────────────────────────────────────────────────

class ItemPedidoPDV(models.Model):
    pedido     = models.ForeignKey(PedidoPDV, on_delete=models.CASCADE, related_name='itens')
    produto    = models.ForeignKey(
        Produto,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='itens_pedido',
    )
    # Snapshot do produto no momento da venda
    nome        = models.CharField(max_length=200)
    preco_unit  = models.DecimalField(max_digits=8, decimal_places=2)
    quantidade  = models.PositiveSmallIntegerField(default=1)
    preco_total = models.DecimalField(max_digits=10, decimal_places=2)
    observacao  = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Item do Pedido PDV'
        ordering     = ['id']

    def save(self, *args, **kwargs):
        self.preco_total = self.preco_unit * self.quantidade
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.quantidade}x {self.nome}'
