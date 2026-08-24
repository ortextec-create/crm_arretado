"""
App: financeiro
Contas a Pagar/Receber (obrigação projetada) + MovimentoFinanceiro (ledger,
fonte única da verdade). Ver FINANCEIRO.md na raiz do repo para a spec
completa e o plano de fases.

MovimentoFinanceiro.registrar() é o único ponto de escrita de
ContaBancaria.saldo_atual — nenhuma view/signal/management command deve
gravar esse campo direto (mesmo contrato de estoque.MovimentoEstoque).

Requisito de revenda: nenhum valor da Arretado fica hardcoded aqui —
CategoriaFinanceira nasce vazia, o usuário cadastra a lista dele.
"""
import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from empresas.models import Empresa

DUAS_CASAS = Decimal('0.01')

# origem_tipo cuja idempotência é garantida por UniqueConstraint(origem_tipo, origem_id) —
# baixas de conta (parciais) e lançamentos manuais/estorno ficam de fora de propósito.
ORIGENS_IDEMPOTENTES = ('pdv', 'ifood', 'evento_pagamento')


class CategoriaFinanceira(models.Model):
    TIPO_CHOICES = [
        ('entrada', 'Entrada'),
        ('saida', 'Saída'),
    ]

    nome = models.CharField(max_length=80)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    pai = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT, related_name='subcategorias',
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Categoria Financeira'
        verbose_name_plural = 'Categorias Financeiras'
        ordering = ['tipo', 'nome']
        constraints = [
            models.UniqueConstraint(fields=['nome', 'tipo'], name='uniq_categoria_financeira_nome_tipo'),
        ]

    def __str__(self):
        return f'{self.nome} ({self.get_tipo_display()})'


class ContaBancaria(models.Model):
    TIPO_CHOICES = [
        ('banco', 'Banco'),
        ('caixa', 'Caixa'),
    ]

    nome = models.CharField(max_length=60)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.PROTECT, related_name='contas_bancarias',
        help_text="Fase 4 do multi-empresa.",
    )
    saldo_atual = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        help_text="Atualizado só por MovimentoFinanceiro.registrar() — nunca gravar direto",
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Conta Bancária'
        verbose_name_plural = 'Contas Bancárias'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Fornecedor(models.Model):
    nome = models.CharField(max_length=120)
    cnpj = models.CharField(max_length=18, blank=True, default='')
    telefone = models.CharField(max_length=30, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    categoria_padrao = models.ForeignKey(
        CategoriaFinanceira, null=True, blank=True, on_delete=models.SET_NULL, related_name='fornecedores',
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Fornecedor'
        verbose_name_plural = 'Fornecedores'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class ConfiguracaoFinanceira(models.Model):
    """Singleton — sempre acessado via ConfiguracaoFinanceira.get()."""

    RECEBIMENTO_IFOOD_CHOICES = [
        ('no_ato', 'No ato (pago direto)'),
        ('repasse', 'Repasse (recebido depois)'),
    ]

    empresa = models.OneToOneField(
        Empresa, on_delete=models.PROTECT, related_name='configuracao_financeira',
        help_text="Fase 4 do multi-empresa — deixa de ser singleton global, vira 1 linha por empresa.",
    )
    recebimento_ifood = models.CharField(max_length=10, choices=RECEBIMENTO_IFOOD_CHOICES, default='no_ato')
    dias_repasse_ifood = models.PositiveSmallIntegerField(default=30)
    nota_gera_conta_pagar = models.BooleanField(default=True)
    alerta_antecedencia_dias = models.PositiveSmallIntegerField(default=2)
    alerta_repeticao_dias = models.PositiveSmallIntegerField(default=1)
    horizonte_recorrencia_dias = models.PositiveSmallIntegerField(default=40)
    conta_padrao_vendas = models.ForeignKey(
        ContaBancaria, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        help_text="Destino dos movimentos automáticos de venda (PDV/iFood — Fase 4). "
                  "Se vazia, os signals correspondentes logam warning e não gravam.",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração Financeira'

    @classmethod
    def get(cls, empresa):
        """Uma linha por empresa (Fase 4) — cria on-demand, mesmo espírito do singleton anterior."""
        obj, _ = cls.objects.get_or_create(empresa=empresa)
        return obj

    def __str__(self):
        return f'Configuração Financeira ({self.empresa.nome})' if self.empresa_id else 'Configuração Financeira'


class TelefoneAlertaFinanceiro(models.Model):
    """Telefones internos da equipe que recebem alertas de vencimento (não é o fornecedor/cliente)."""

    numero = models.CharField(max_length=30)
    nome = models.CharField('Nome/label (opcional)', max_length=100, blank=True, default='')
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Telefone de Alerta Financeiro'
        verbose_name_plural = 'Telefones de Alerta Financeiro'
        ordering = ['nome', 'numero']

    def __str__(self):
        return f'{self.nome} ({self.numero})' if self.nome else self.numero


class MovimentoFinanceiro(models.Model):
    """
    O ledger — fonte única da verdade do que passou pelo caixa. Escrita
    exclusivamente via MovimentoFinanceiro.registrar(); nunca
    .objects.create() direto em view/signal/command. Não implementar DELETE
    — ledger é imutável, erro se corrige com um movimento manual inverso
    (estorno), nunca apagando o original.
    """
    TIPO_CHOICES = [
        ('entrada', 'Entrada'),
        ('saida', 'Saída'),
    ]
    FORMA_PAGAMENTO_CHOICES = [
        ('pix', 'Pix'),
        ('boleto', 'Boleto'),
        ('cartao', 'Cartão'),
        ('dinheiro', 'Dinheiro'),
        ('outro', 'Outro'),
    ]
    ORIGEM_TIPO_CHOICES = [
        ('conta_pagar', 'Conta a Pagar'),
        ('conta_receber', 'Conta a Receber'),
        ('pdv', 'PDV'),
        ('ifood', 'iFood'),
        ('evento_pagamento', 'Pagamento de Evento'),
        ('manual', 'Manual'),
    ]
    conta = models.ForeignKey(ContaBancaria, on_delete=models.PROTECT, related_name='movimentos')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    data_movimento = models.DateField(db_index=True)
    categoria = models.ForeignKey(
        CategoriaFinanceira, null=True, blank=True, on_delete=models.PROTECT, related_name='movimentos',
    )
    fornecedor = models.ForeignKey(
        Fornecedor, null=True, blank=True, on_delete=models.SET_NULL, related_name='movimentos',
    )
    cliente = models.ForeignKey(
        'clientes.Cliente', null=True, blank=True, on_delete=models.SET_NULL, related_name='movimentos_financeiros',
    )
    descricao = models.CharField(max_length=200, blank=True, default='')
    forma_pagamento = models.CharField(max_length=10, choices=FORMA_PAGAMENTO_CHOICES, blank=True, default='')
    origem_tipo = models.CharField(max_length=20, choices=ORIGEM_TIPO_CHOICES)
    origem_id = models.CharField(max_length=64, blank=True, default='')
    comprovante = models.FileField(upload_to='financeiro/comprovantes/%Y/%m/', null=True, blank=True)
    saldo_posterior = models.DecimalField(max_digits=12, decimal_places=2)
    criado_por = models.ForeignKey(
        'usuarios.Usuario', null=True, blank=True, on_delete=models.SET_NULL, related_name='movimentos_financeiros',
    )
    criado_por_nome_snapshot = models.CharField(max_length=150, blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Movimento Financeiro'
        verbose_name_plural = 'Movimentos Financeiros'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['origem_tipo', 'origem_id']),
            models.Index(fields=['conta', '-criado_em']),
            models.Index(fields=['-data_movimento']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['origem_tipo', 'origem_id'],
                condition=models.Q(origem_tipo__in=ORIGENS_IDEMPOTENTES),
                name='uniq_movimento_financeiro_origem_idempotente',
            ),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} — R$ {self.valor} ({self.conta.nome})'

    @property
    def empresa(self):
        """Sem campo próprio (Fase 4) — a empresa do movimento é sempre a da ContaBancaria. Não denormalizar."""
        return self.conta.empresa

    def clean(self):
        if self.valor is not None and self.valor <= 0:
            raise ValidationError({'valor': 'Deve ser maior que zero.'})

    @classmethod
    def registrar(cls, *, conta, tipo, valor, origem_tipo, data_movimento=None,
                  categoria=None, fornecedor=None, cliente=None, descricao='',
                  forma_pagamento='', origem_id='', comprovante=None, criado_por=None):
        """
        Único ponto de escrita do ledger financeiro. Nunca usar
        MovimentoFinanceiro.objects.create() direto em view/signal/command.
        """
        if tipo not in ('entrada', 'saida'):
            raise ValidationError({'tipo': 'Deve ser "entrada" ou "saida".'})

        # quantizar aqui, no único ponto de escrita, em vez de em cada
        # chamador — mesma lição do módulo Estoque (MovimentoEstoque.registrar)
        valor = Decimal(valor).quantize(DUAS_CASAS, rounding=ROUND_HALF_UP)
        if valor <= 0:
            raise ValidationError({'valor': 'Deve ser maior que zero.'})

        with transaction.atomic():
            # bloqueia a linha até o fim da transação — evita race condition
            # entre baixas/vendas concorrentes da mesma conta
            conta_travada = ContaBancaria.objects.select_for_update().get(pk=conta.pk)
            saldo_anterior = conta_travada.saldo_atual
            saldo_posterior = (
                saldo_anterior + valor if tipo == 'entrada' else saldo_anterior - valor
            )

            mov = cls(
                conta=conta_travada, tipo=tipo, valor=valor,
                data_movimento=data_movimento or timezone.localdate(),
                categoria=categoria, fornecedor=fornecedor, cliente=cliente,
                descricao=descricao, forma_pagamento=forma_pagamento,
                origem_tipo=origem_tipo, origem_id=str(origem_id) if origem_id else '',
                comprovante=comprovante, saldo_posterior=saldo_posterior,
                criado_por=criado_por, criado_por_nome_snapshot=criado_por.name if criado_por else '',
            )
            mov.full_clean()
            mov.save()

            conta_travada.saldo_atual = saldo_posterior
            conta_travada.save(update_fields=['saldo_atual'])

        return mov


class ContaPagar(models.Model):
    """
    Obrigação projetada (mesma filosofia de eventos.Evento): tem vencimento
    e status, pode nunca acontecer. valor_pago/status são sempre derivados
    via recalcular_valor_pago() — nunca gravados direto (mesma regra de
    Evento.sinal_pago).
    """
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('parcial', 'Parcial'),
        ('paga', 'Paga'),
        ('cancelada', 'Cancelada'),
    ]
    ORIGEM_CHOICES = [
        ('manual', 'Manual'),
        ('nota_fiscal', 'Nota Fiscal'),
        ('recorrente', 'Recorrente'),
    ]

    numero = models.CharField(max_length=12, unique=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.PROTECT, related_name='contas_pagar',
        help_text="Fase 4 do multi-empresa.",
    )
    fornecedor = models.ForeignKey(
        Fornecedor, null=True, blank=True, on_delete=models.PROTECT, related_name='contas_pagar',
    )
    descricao = models.CharField(max_length=160, blank=True, default='')
    categoria = models.ForeignKey(
        CategoriaFinanceira, null=True, blank=True, on_delete=models.PROTECT, related_name='contas_pagar',
        help_text="Opcional — ContaPagar gerada automaticamente por nota fiscal nasce sem categoria "
                  "(a extração não tem como determinar uma), o usuário categoriza depois via PATCH.",
    )
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    data_emissao = models.DateField()
    data_vencimento = models.DateField(db_index=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pendente')
    origem = models.CharField(max_length=12, choices=ORIGEM_CHOICES, default='manual')
    nota_fiscal = models.OneToOneField(
        'estoque.ImportacaoNotaFiscal', null=True, blank=True, on_delete=models.PROTECT, related_name='conta_pagar',
        help_text="Preenchido na Fase 5 (integração com Estoque) — OneToOne garante idempotência do confirmar()",
    )
    recorrente = models.ForeignKey(
        'DespesaRecorrente', null=True, blank=True, on_delete=models.PROTECT, related_name='contas_pagar',
        help_text="Preenchida só pelo cron gerar_contas_recorrentes",
    )
    anexo = models.FileField(upload_to='financeiro/contas_pagar/%Y/%m/', blank=True)
    observacao = models.TextField(blank=True, default='')
    valor_pago = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Conta a Pagar'
        verbose_name_plural = 'Contas a Pagar'
        ordering = ['data_vencimento', 'numero']
        constraints = [
            models.UniqueConstraint(
                fields=['recorrente', 'data_vencimento'],
                condition=models.Q(recorrente__isnull=False),
                name='uniq_contapagar_recorrente_vencimento',
            ),
        ]

    def __str__(self):
        return f'{self.numero} — {self.descricao or (self.fornecedor.nome if self.fornecedor else "—")}'

    @classmethod
    def proximo_numero(cls):
        ultimo = cls.objects.order_by('-id').first()
        if not ultimo:
            return 'CP-0001'
        try:
            seq = int(ultimo.numero.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = cls.objects.count() + 1
        return f'CP-{seq:04d}'

    def recalcular_valor_pago(self):
        from django.db.models import Sum
        total = MovimentoFinanceiro.objects.filter(
            origem_tipo='conta_pagar', origem_id=str(self.id), tipo='saida',
        ).aggregate(t=Sum('valor'))['t'] or Decimal('0')
        self.valor_pago = total
        if self.status != 'cancelada':
            if self.valor_pago >= self.valor:
                self.status = 'paga'
            elif self.valor_pago > 0:
                self.status = 'parcial'
            else:
                self.status = 'pendente'
        self.save(update_fields=['valor_pago', 'status', 'atualizado_em'])


class ContaReceber(models.Model):
    """
    Espelho de ContaPagar pro lado de entradas — mas só existe pra canais
    que realmente atrasam o recebimento (iFood no modo 'repasse') ou
    lançamento manual avulso. Eventos e PDV NUNCA materializam ContaReceber
    (ver O Que NÃO Fazer no CLAUDE.md — evita dupla contagem): PDV e iFood
    'no_ato' batem direto no ledger via signal (dinheiro já entrou no
    caixa); o saldo de Eventos é sempre consultado dinamicamente
    (Evento.valor_total - sinal_pago), nunca materializado aqui.
    """
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('parcial', 'Parcial'),
        ('recebida', 'Recebida'),
        ('cancelada', 'Cancelada'),
    ]
    CANAL_CHOICES = [
        ('ifood', 'iFood'),
        ('manual', 'Manual'),
    ]

    numero = models.CharField(max_length=12, unique=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.PROTECT, related_name='contas_receber',
        help_text="Fase 4 do multi-empresa.",
    )
    cliente = models.ForeignKey(
        'clientes.Cliente', null=True, blank=True, on_delete=models.SET_NULL, related_name='contas_receber',
    )
    cliente_nome = models.CharField(max_length=120, blank=True, default='')
    canal = models.CharField(max_length=10, choices=CANAL_CHOICES, default='manual')
    referencia = models.CharField(max_length=60, blank=True, default='')
    categoria = models.ForeignKey(
        CategoriaFinanceira, null=True, blank=True, on_delete=models.PROTECT, related_name='contas_receber',
    )
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    data_vencimento = models.DateField(db_index=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pendente')
    origem_canal = models.CharField(max_length=20, blank=True, default='manual')
    origem_id = models.CharField(max_length=64, blank=True, default='')
    valor_recebido = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Conta a Receber'
        verbose_name_plural = 'Contas a Receber'
        ordering = ['data_vencimento', 'numero']
        constraints = [
            models.UniqueConstraint(
                fields=['origem_canal', 'origem_id'],
                condition=~models.Q(origem_canal='manual'),
                name='uniq_contareceber_origem_idempotente',
            ),
        ]

    def __str__(self):
        return f'{self.numero} — {self.cliente_nome or (self.cliente.nome if self.cliente else "—")}'

    @classmethod
    def proximo_numero(cls):
        ultimo = cls.objects.order_by('-id').first()
        if not ultimo:
            return 'CR-0001'
        try:
            seq = int(ultimo.numero.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = cls.objects.count() + 1
        return f'CR-{seq:04d}'

    def recalcular_valor_recebido(self):
        from django.db.models import Sum
        total = MovimentoFinanceiro.objects.filter(
            origem_tipo='conta_receber', origem_id=str(self.id), tipo='entrada',
        ).aggregate(t=Sum('valor'))['t'] or Decimal('0')
        self.valor_recebido = total
        if self.status != 'cancelada':
            if self.valor_recebido >= self.valor:
                self.status = 'recebida'
            elif self.valor_recebido > 0:
                self.status = 'parcial'
            else:
                self.status = 'pendente'
        self.save(update_fields=['valor_recebido', 'status', 'atualizado_em'])


class DespesaRecorrente(models.Model):
    """
    Molde de despesa que se repete todo mês (aluguel, energia, assinatura...).
    O cron gerar_contas_recorrentes materializa uma ContaPagar (origem='recorrente')
    por vencimento dentro do horizonte configurado — nunca gerar o pagamento em si
    aqui, só a obrigação projetada.
    """
    VALOR_TIPO_CHOICES = [
        ('fixo', 'Fixo'),
        ('estimado', 'Estimado'),
    ]

    descricao = models.CharField(max_length=120)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.PROTECT, related_name='despesas_recorrentes',
        help_text="Fase 4 do multi-empresa. A ContaPagar gerada pelo cron herda a empresa do molde.",
    )
    fornecedor = models.ForeignKey(
        Fornecedor, null=True, blank=True, on_delete=models.PROTECT, related_name='despesas_recorrentes',
    )
    categoria = models.ForeignKey(CategoriaFinanceira, on_delete=models.PROTECT, related_name='despesas_recorrentes')
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    valor_tipo = models.CharField(max_length=10, choices=VALOR_TIPO_CHOICES, default='fixo')
    dias_vencimento = models.JSONField(
        default=list, help_text='Lista de dias do mês (1-31), ex.: [1, 30]. Dia inexistente no mês '
                                 '(31 em fevereiro) cai no último dia.',
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Despesa Recorrente'
        verbose_name_plural = 'Despesas Recorrentes'
        ordering = ['descricao']

    def __str__(self):
        return self.descricao

    def clean(self):
        if not isinstance(self.dias_vencimento, list) or not self.dias_vencimento:
            raise ValidationError({'dias_vencimento': 'Informe ao menos um dia do mês (1-31).'})
        for dia in self.dias_vencimento:
            if not isinstance(dia, int) or not (1 <= dia <= 31):
                raise ValidationError({'dias_vencimento': 'Cada dia deve ser um inteiro entre 1 e 31.'})

    def datas_no_periodo(self, data_inicio, data_fim):
        """
        Vencimentos dentro de [data_inicio, data_fim], varrendo mês a mês.
        Dia inexistente no mês (ex.: 31 em fevereiro) cai no último dia do mês —
        nunca rola pro mês seguinte.
        """
        datas = []
        ano, mes = data_inicio.year, data_inicio.month
        while (ano, mes) <= (data_fim.year, data_fim.month):
            ultimo_dia_mes = calendar.monthrange(ano, mes)[1]
            for dia in self.dias_vencimento:
                data = date(ano, mes, min(dia, ultimo_dia_mes))
                if data_inicio <= data <= data_fim:
                    datas.append(data)
            mes += 1
            if mes > 12:
                mes = 1
                ano += 1
        return sorted(set(datas))


class SaldoConferido(models.Model):
    """
    Conferência de saldo (o usuário digita o saldo informado pelo app do
    banco e compara com o saldo calculado pelo ledger). Sem edição — uma
    nova conferência só acrescenta um registro novo, nunca corrige o
    anterior; o histórico completo fica preservado no banco, a UI mostra
    a mais recente por conta.
    """
    conta = models.ForeignKey(ContaBancaria, on_delete=models.PROTECT, related_name='conferencias')
    data = models.DateField()
    saldo_informado = models.DecimalField(max_digits=12, decimal_places=2)
    saldo_calculado = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Snapshot de ContaBancaria.saldo_atual no momento da conferência — nunca recalculado depois",
    )
    criado_por = models.ForeignKey(
        'usuarios.Usuario', null=True, blank=True, on_delete=models.SET_NULL, related_name='conferencias_saldo',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Conferência de Saldo'
        verbose_name_plural = 'Conferências de Saldo'
        ordering = ['-data', '-criado_em']

    def __str__(self):
        return f'{self.conta.nome} — {self.data} (informado R$ {self.saldo_informado})'

    @property
    def diferenca(self):
        return self.saldo_informado - self.saldo_calculado


class AlertaFinanceiroEnviado(models.Model):
    """Rastreia o último envio de alerta de vencimento por ContaPagar — controla a repetição."""

    conta_pagar = models.ForeignKey(ContaPagar, on_delete=models.CASCADE, related_name='alertas_enviados')
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Alerta Financeiro Enviado'
        verbose_name_plural = 'Alertas Financeiros Enviados'
        ordering = ['-enviado_em']
        indexes = [models.Index(fields=['conta_pagar', '-enviado_em'])]
