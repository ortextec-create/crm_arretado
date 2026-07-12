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
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
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


class TaxaEntregaBairro(models.Model):
    bairro        = models.CharField(max_length=100, unique=True)
    taxa          = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    ativo         = models.BooleanField(default=True, db_index=True)
    criado_em     = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Taxa de Entrega por Bairro'
        verbose_name_plural = 'Taxas de Entrega por Bairro'
        ordering            = ['bairro']

    def __str__(self):
        return f'{self.bairro} — R$ {self.taxa}'


class ConfiguracaoEntrega(models.Model):
    """Singleton — sempre acessado via ConfiguracaoEntrega.get()."""
    frete_padrao  = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text='Taxa de entrega usada quando nenhum bairro cadastrado for selecionado'
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração de Entrega'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f'Frete padrão: R$ {self.frete_padrao}'


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

    TIPO_CHOICES = [
        ('fabricado', 'Fabricado'),
        ('revenda',   'Revenda'),
        ('kit',       'Kit'),
    ]

    tipo = models.CharField(
        max_length=12, choices=TIPO_CHOICES, default='fabricado', db_index=True,
        help_text="Natureza do produto: de onde vem o custo"
    )

    # Só relevante quando tipo == 'revenda'
    materia_prima_origem = models.ForeignKey(
        'fichas.MateriaPrima',
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name='produtos_revenda',
        help_text="Matéria-prima da qual este produto de revenda deriva o custo"
    )
    margem_desejada_pct = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True,
        help_text="Opcional. Sugere preço de venda para produtos de revenda (não substitui `preco`)."
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

    # ── Custo e margem polimórficos ──────────────────────────────────

    @property
    def custo(self):
        if self.tipo == 'fabricado':
            ficha = self._ficha_vinculada()
            return ficha.custo_total_unitario if ficha else None
        if self.tipo == 'revenda':
            return self.materia_prima_origem.custo_unitario if self.materia_prima_origem_id else None
        if self.tipo == 'kit':
            itens = self.itens_kit.select_related('componente').all()
            if not itens:
                return None
            total = Decimal('0')
            for item in itens:
                c = item.componente.custo
                if c is None:
                    return None
                total += c * item.quantidade
            return total
        return None

    @property
    def custo_origem(self):
        """Rótulo curto pra exibir no card: 'ficha', 'compra' ou 'soma'."""
        return {'fabricado': 'ficha', 'revenda': 'compra', 'kit': 'soma'}.get(self.tipo)

    @property
    def margem_pct(self):
        c = self.custo
        if c is None or not self.preco or self.preco <= 0:
            return None
        return (self.preco - c) / self.preco

    @property
    def preco_sugerido_revenda(self):
        if self.tipo != 'revenda' or not self.materia_prima_origem_id or not self.margem_desejada_pct:
            return None
        denom = Decimal('1') - self.margem_desejada_pct
        if denom <= 0:
            return None
        return self.materia_prima_origem.custo_unitario / denom

    def _ficha_vinculada(self):
        from fichas.models import FichaTecnica
        return FichaTecnica.objects.filter(produto_pdv_id=self.id, ativo=True).first()

    def preco_para(self, quantidade=1, canal=None):
        """
        Resolve o preço aplicável considerando faixas de quantidade.
        Prioridade: faixa do canal específico > faixa geral (canal=null) > preco base.
        """
        faixas = self.faixas_preco.filter(quantidade_minima__lte=quantidade).order_by('-quantidade_minima')
        if canal:
            especifica = faixas.filter(canal=canal).first()
            if especifica:
                return especifica.preco_unitario
        geral = faixas.filter(canal__isnull=True).first()
        if geral:
            return geral.preco_unitario
        return self.preco


class ItemKit(models.Model):
    kit        = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='itens_kit')
    componente = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name='usado_em_kits')
    quantidade = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Item do Kit"
        unique_together = [('kit', 'componente')]

    def clean(self):
        if self.kit_id == self.componente_id:
            raise ValidationError("Um kit não pode se conter.")
        if self.componente.tipo == 'kit':
            raise ValidationError("Não é permitido kit-de-kit.")

    def __str__(self):
        return f'{self.quantidade}x {self.componente.nome} em {self.kit.nome}'


class FaixaPreco(models.Model):
    CANAL_CHOICES = [
        ('pdv',     'PDV'),
        ('ifood',   'iFood'),
        ('eventos', 'Eventos'),
    ]

    produto           = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='faixas_preco')
    quantidade_minima = models.PositiveIntegerField(help_text="A partir de quantas unidades esta faixa vale")
    preco_unitario    = models.DecimalField(max_digits=10, decimal_places=2)
    canal             = models.CharField(
        max_length=10, choices=CANAL_CHOICES, null=True, blank=True,
        help_text="Vazio/null = vale para todos os canais"
    )

    class Meta:
        verbose_name = "Faixa de Preço"
        ordering = ['produto', 'quantidade_minima']
        unique_together = [('produto', 'quantidade_minima', 'canal')]

    def __str__(self):
        canal_label = self.get_canal_display() if self.canal else 'Todos'
        return f"{self.produto.nome} — {self.quantidade_minima}un ({canal_label}): R$ {self.preco_unitario}"


class DadosFiscaisProduto(models.Model):
    UNIDADE_CHOICES = [('UN', 'Unidade'), ('KG', 'Quilograma'), ('CENTO', 'Cento'), ('DUZIA', 'Dúzia'), ('L', 'Litro')]

    produto       = models.OneToOneField(Produto, on_delete=models.CASCADE, related_name='dados_fiscais')
    unidade       = models.CharField(max_length=6, choices=UNIDADE_CHOICES, default='UN')
    codigo        = models.CharField(max_length=50, blank=True, default='', help_text="SKU interno")
    codigo_barras = models.CharField(max_length=14, blank=True, default='', help_text="EAN, opcional")
    ncm           = models.CharField(max_length=10, blank=True, default='')

    class Meta:
        verbose_name = "Dados Fiscais do Produto"

    def __str__(self):
        return f'Dados fiscais — {self.produto.nome}'


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

    subtotal       = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    desconto       = models.DecimalField(max_digits=8,  decimal_places=2, default=0)
    taxa_entrega   = models.DecimalField(max_digits=8,  decimal_places=2, default=0)
    bairro_entrega = models.CharField(max_length=100, blank=True, default='')
    total          = models.DecimalField(max_digits=10, decimal_places=2, default=0)

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
