"""
App: estoque
Controle de saldo físico de insumos (fichas.MateriaPrima) e produtos
(pdv.Produto), produção formal e alertas de estoque baixo.

MovimentoEstoque é o ledger — fonte única da verdade. Nenhuma view/signal/
management command deve escrever quantidade_estoque direto em MateriaPrima/
Produto — sempre passar por MovimentoEstoque.registrar().

Política de saldo negativo: sempre permitido — nenhum movimento bloqueia por
saldo insuficiente, o sistema só alerta a equipe (ver alertar_estoque_baixo).
"""
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction

TRES_CASAS = Decimal('0.001')
QUATRO_CASAS = Decimal('0.0001')


class MovimentoEstoque(models.Model):
    TIPO_CHOICES = [
        ('entrada_compra', 'Entrada — compra'),
        ('entrada_producao', 'Entrada — produção'),
        ('saida_producao', 'Saída — produção'),
        ('saida_venda', 'Saída — venda'),
        ('ajuste_inventario', 'Ajuste — inventário'),
    ]

    materia_prima = models.ForeignKey(
        'fichas.MateriaPrima', null=True, blank=True,
        on_delete=models.PROTECT, related_name='movimentos',
    )
    produto = models.ForeignKey(
        'pdv.Produto', null=True, blank=True,
        on_delete=models.PROTECT, related_name='movimentos_estoque',
    )
    tipo_movimento = models.CharField(max_length=20, choices=TIPO_CHOICES)
    quantidade = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text="Sempre positivo — o efeito no saldo vem de tipo_movimento, não do sinal deste campo",
    )
    saldo_anterior = models.DecimalField(max_digits=10, decimal_places=3)
    saldo_posterior = models.DecimalField(max_digits=10, decimal_places=3)
    custo_unitario_snapshot = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Preserva o custo no momento do movimento — não recalcula histórico se o preço mudar depois",
    )
    origem_tipo = models.CharField(
        max_length=20, null=True, blank=True,
        help_text="'pedido_pdv' | 'pedido_ifood' | 'evento' | 'producao' | 'nota_fiscal' | 'manual'",
    )
    origem_id = models.IntegerField(
        null=True, blank=True,
        help_text="FK fraca pro registro de origem — evita dependência circular entre apps (mesmo padrão de FichaTecnica.produto_pdv_id)",
    )
    observacao = models.CharField(max_length=300, blank=True, default='')
    criado_por = models.ForeignKey(
        'usuarios.Usuario', null=True, blank=True, on_delete=models.SET_NULL,
        help_text="Null quando o movimento vem de signal automático (venda)",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Movimento de Estoque'
        verbose_name_plural = 'Movimentos de Estoque'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['origem_tipo', 'origem_id']),
            models.Index(fields=['materia_prima', '-criado_em']),
            models.Index(fields=['produto', '-criado_em']),
        ]

    def __str__(self):
        alvo = self.materia_prima or self.produto
        return f'{self.get_tipo_movimento_display()} — {alvo} ({self.quantidade})'

    def clean(self):
        preenchidos = [self.materia_prima_id, self.produto_id]
        if sum(1 for p in preenchidos if p) != 1:
            raise ValidationError('Exatamente um de materia_prima/produto deve ser preenchido.')

    @classmethod
    def registrar(cls, *, materia_prima=None, produto=None, tipo_movimento, quantidade,
                  origem_tipo=None, origem_id=None, custo_unitario_snapshot=None,
                  observacao='', criado_por=None):
        """
        Único ponto de escrita de saldo de estoque. Nunca usar
        MovimentoEstoque.objects.create() direto em view/signal/command.
        """
        if sum(1 for p in (materia_prima, produto) if p) != 1:
            raise ValidationError('Exatamente um de materia_prima/produto deve ser preenchido.')

        alvo = materia_prima or produto
        # consumo calculado por proporção (ex: item.quantidade * (produzido/rendimento)) pode
        # sair com mais de 3 casas decimais — quantizar aqui, no único ponto de escrita,
        # em vez de em cada chamador (Producao.executar, signals de débito etc.)
        quantidade = Decimal(quantidade).quantize(TRES_CASAS, rounding=ROUND_HALF_UP)
        # idem para custo_unitario_snapshot (DecimalField decimal_places=4) — custo_unitario
        # é uma divisão sem quantização (ex: valor_compra/quantidade_compra) e pode sair com
        # dezenas de casas decimais, estourando max_digits
        if custo_unitario_snapshot is not None:
            custo_unitario_snapshot = Decimal(custo_unitario_snapshot).quantize(QUATRO_CASAS, rounding=ROUND_HALF_UP)

        with transaction.atomic():
            # bloqueia a linha até o fim da transação — evita race condition entre
            # movimentos concorrentes (ex: duas vendas do mesmo produto ao mesmo tempo)
            alvo_travado = type(alvo).objects.select_for_update().get(pk=alvo.pk)
            saldo_anterior = alvo_travado.quantidade_estoque

            if tipo_movimento == 'ajuste_inventario':
                # quantidade É o novo saldo absoluto (contagem física), não delta
                saldo_posterior = quantidade
            elif tipo_movimento in ('saida_producao', 'saida_venda'):
                saldo_posterior = saldo_anterior - quantidade
            else:
                saldo_posterior = saldo_anterior + quantidade

            mov = cls(
                materia_prima=materia_prima, produto=produto, tipo_movimento=tipo_movimento,
                quantidade=quantidade, saldo_anterior=saldo_anterior, saldo_posterior=saldo_posterior,
                custo_unitario_snapshot=custo_unitario_snapshot, origem_tipo=origem_tipo,
                origem_id=origem_id, observacao=observacao, criado_por=criado_por,
            )
            mov.full_clean()
            mov.save()

            alvo_travado.quantidade_estoque = saldo_posterior
            alvo_travado.save(update_fields=['quantidade_estoque'])

        return mov


class Producao(models.Model):
    ficha_tecnica = models.ForeignKey(
        'fichas.FichaTecnica', on_delete=models.PROTECT, related_name='producoes',
    )
    quantidade_produzida = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text="Em unidades do produto (não da ficha)",
    )
    criado_por = models.ForeignKey('usuarios.Usuario', null=True, blank=True, on_delete=models.SET_NULL)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Produção'
        verbose_name_plural = 'Produções'
        ordering = ['-criado_em']

    def __str__(self):
        return f'Produção #{self.pk} — {self.ficha_tecnica.nome} ({self.quantidade_produzida})'

    def executar(self, usuario=None):
        """
        Debita insumos proporcionalmente ao rendimento da ficha e credita o
        saldo do produto vinculado. Só permitido quando o produto vinculado
        está em modo_estoque == 'estoque' (produção formal não se aplica a
        'sob_encomenda', que debita insumo direto no signal de venda).
        """
        produto = self.ficha_tecnica._get_produto_pdv()
        if not produto or produto.modo_estoque != 'estoque':
            raise ValidationError(
                'Ficha técnica sem produto vinculado em modo_estoque="estoque" — produção formal não se aplica aqui.'
            )
        if not self.ficha_tecnica.rendimento:
            raise ValidationError('Ficha técnica sem rendimento definido.')

        with transaction.atomic():
            for item in self.ficha_tecnica.itens.select_related('materia_prima'):
                consumo = item.quantidade * (self.quantidade_produzida / self.ficha_tecnica.rendimento)
                MovimentoEstoque.registrar(
                    materia_prima=item.materia_prima, tipo_movimento='saida_producao',
                    quantidade=consumo, origem_tipo='producao', origem_id=self.id,
                    custo_unitario_snapshot=item.materia_prima.custo_unitario, criado_por=usuario,
                )
            MovimentoEstoque.registrar(
                produto=produto, tipo_movimento='entrada_producao',
                quantidade=self.quantidade_produzida, origem_tipo='producao', origem_id=self.id,
                criado_por=usuario,
            )


class ConfiguracaoEstoque(models.Model):
    """Singleton — sempre acessado via ConfiguracaoEstoque.get()."""
    estoque_minimo_padrao = models.DecimalField(
        max_digits=10, decimal_places=3, default=Decimal('0'),
        help_text="Sugerido ao cadastrar item novo sem mínimo definido (não sobrescreve os já cadastrados)",
    )
    alerta_whatsapp_ativo = models.BooleanField(default=True)
    alerta_repetir_diariamente = models.BooleanField(
        default=True, help_text="Enquanto o item continuar abaixo do mínimo",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração de Estoque'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return 'Configuração de Estoque'


class TelefoneAlertaEstoque(models.Model):
    numero = models.CharField(max_length=30)
    nome = models.CharField('Nome/label (opcional)', max_length=100, blank=True, default='')
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Telefone de Alerta de Estoque'
        verbose_name_plural = 'Telefones de Alerta de Estoque'
        ordering = ['nome', 'numero']

    def __str__(self):
        return f'{self.nome} ({self.numero})' if self.nome else self.numero


class AlertaEstoqueEnviado(models.Model):
    TIPO_CHOICES = [
        ('materia_prima', 'Insumo'),
        ('produto', 'Produto'),
    ]

    materia_prima = models.ForeignKey(
        'fichas.MateriaPrima', null=True, blank=True, on_delete=models.CASCADE, related_name='alertas_enviados',
    )
    produto = models.ForeignKey(
        'pdv.Produto', null=True, blank=True, on_delete=models.CASCADE, related_name='alertas_enviados',
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Alerta de Estoque Enviado'
        verbose_name_plural = 'Alertas de Estoque Enviados'
        ordering = ['-enviado_em']
        indexes = [models.Index(fields=['materia_prima', 'produto', '-enviado_em'])]

    def __str__(self):
        alvo = self.materia_prima or self.produto
        return f'{alvo} — {self.enviado_em:%d/%m/%Y %H:%M}'
