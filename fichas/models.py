from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class ParametrosNegocio(models.Model):
    faturamento_meta = models.DecimalField(max_digits=10, decimal_places=2, default=40000)
    despesa_fixa_mensal = models.DecimalField(max_digits=10, decimal_places=2, default=17000)
    despesa_variavel_pct = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0.425'),
        help_text="Percentual das despesas variáveis sobre o preço de venda (ex: 0.425 = 42,5%)"
    )
    margem_lucro_esperada_pct = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0.30'),
        help_text="Margem de lucro esperada sobre a venda (ex: 0.30 = 30%)"
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Parâmetros do Negócio"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def markup(self):
        denominador = 1 - self.despesa_variavel_pct - self.margem_lucro_esperada_pct
        if denominador <= 0:
            return Decimal('1')
        return Decimal('1') / denominador


class MateriaPrima(models.Model):
    UNIDADE_CHOICES = [
        ('g',  'Gramas'),
        ('ml', 'Mililitros'),
        ('un', 'Unidade'),
        ('kg', 'Quilograma'),
        ('l',  'Litro'),
    ]

    nome              = models.CharField(max_length=120, unique=True)
    unidade_compra    = models.CharField(max_length=40, help_text="Ex: 1kg, 500g, 30 unidades")
    quantidade_compra = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text="Quantidade na embalagem de compra (em g, ml ou un)"
    )
    unidade_medida    = models.CharField(max_length=5, choices=UNIDADE_CHOICES, default='g')
    valor_compra      = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    ativo             = models.BooleanField(default=True)
    atualizado_em     = models.DateTimeField(auto_now=True)
    criado_em         = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Matéria-Prima"
        verbose_name_plural = "Matérias-Primas"
        ordering = ['nome']

    def __str__(self):
        return self.nome

    @property
    def custo_unitario(self):
        if self.quantidade_compra and self.quantidade_compra > 0:
            return self.valor_compra / self.quantidade_compra
        return Decimal('0')


class FichaTecnica(models.Model):
    produto_pdv_id = models.IntegerField(
        null=True, blank=True,
        help_text="ID do pdv.Produto correspondente (opcional)"
    )
    nome            = models.CharField(max_length=120)
    rendimento      = models.PositiveIntegerField(
        default=1,
        help_text="Quantas unidades a receita produz"
    )
    embalagem_custo = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0.08'),
        help_text="Custo da embalagem por unidade (R$)"
    )
    ativo           = models.BooleanField(default=True)
    atualizado_em   = models.DateTimeField(auto_now=True)
    criado_em       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Ficha Técnica"
        verbose_name_plural = "Fichas Técnicas"
        ordering = ['nome']

    def __str__(self):
        return self.nome

    @property
    def custo_ingredientes(self):
        return sum(item.custo_proporcional for item in self.itens.all())

    @property
    def custo_total_unitario(self):
        if self.rendimento and self.rendimento > 0:
            return (self.custo_ingredientes / self.rendimento) + self.embalagem_custo
        return self.embalagem_custo

    @property
    def preco_ideal(self):
        params = ParametrosNegocio.get()
        return self.custo_total_unitario * params.markup

    @property
    def margem_bruta_pct(self):
        produto = self._get_produto_pdv()
        if produto and produto.preco > 0:
            return (produto.preco - self.custo_total_unitario) / produto.preco
        return None

    def _get_produto_pdv(self):
        if not self.produto_pdv_id:
            return None
        try:
            from pdv.models import Produto
            return Produto.objects.get(pk=self.produto_pdv_id)
        except Exception:
            return None


class ItemFichaTecnica(models.Model):
    ficha         = models.ForeignKey(FichaTecnica, on_delete=models.CASCADE, related_name='itens')
    materia_prima = models.ForeignKey(MateriaPrima, on_delete=models.PROTECT)
    quantidade    = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text="Quantidade usada na receita (mesma unidade da matéria-prima)"
    )

    class Meta:
        verbose_name    = "Item da Ficha Técnica"
        unique_together = [('ficha', 'materia_prima')]

    def __str__(self):
        return f"{self.ficha.nome} — {self.materia_prima.nome}"

    @property
    def custo_proporcional(self):
        return self.materia_prima.custo_unitario * self.quantidade


class SnapshotPrecos(models.Model):
    descricao  = models.CharField(max_length=200)
    dados      = models.JSONField(help_text="{'produto_id': preco_anterior, ...}")
    criado_em  = models.DateTimeField(auto_now_add=True)
    revertido  = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Snapshot de Preços"
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.descricao} ({self.criado_em:%d/%m/%Y %H:%M})"
