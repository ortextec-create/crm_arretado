"""
App: eventos
Modelos para agendamento de eventos com entrega futura.

Estrutura:
  - LocalEvento    → locais de festa cadastráveis e reutilizáveis
  - Orcamento      → orçamento pré-evento (ORC-0001...) — pode ser convertido em Evento
  - ItemOrcamento  → itens do orçamento (snapshot de nome/preço)
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
# Orçamento (pré-evento)
# ─────────────────────────────────────────────────────────────────────────────

class Orcamento(models.Model):

    STATUS_CHOICES = [
        ('rascunho',   'Rascunho'),
        ('enviado',    'Enviado'),
        ('aprovado',   'Aprovado'),
        ('recusado',   'Recusado'),
        ('expirado',   'Expirado'),
        ('convertido', 'Convertido'),
    ]

    TIPO_EVENTO_CHOICES = [
        ('casamento',   'Casamento'),
        ('formatura',   'Formatura'),
        ('aniversario', 'Aniversário'),
        ('corporativo', 'Corporativo'),
        ('batizado',    'Batizado'),
        ('cha',         'Chá de bebê / revelação'),
        ('outro',       'Outro'),
    ]

    TIPO_ENTREGA_CHOICES = [
        ('retirada_loja',   'Retirada na loja'),
        ('entrega_local',   'Entrega no local da festa'),
    ]

    numero           = models.CharField(max_length=20, unique=True, db_index=True)

    cliente          = models.ForeignKey(
        Cliente,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='orcamentos',
    )
    cliente_nome     = models.CharField(max_length=200, blank=True, default='')
    cliente_telefone = models.CharField(max_length=30,  blank=True, default='')

    tipo_evento      = models.CharField(max_length=30, choices=TIPO_EVENTO_CHOICES, blank=True, default='')
    data_evento      = models.DateField(null=True, blank=True)
    validade         = models.DateField(null=True, blank=True,
                                        help_text='Data limite de validade do orçamento')

    status           = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default='rascunho', db_index=True,
    )

    # Entrega
    tipo_entrega     = models.CharField(max_length=20, choices=TIPO_ENTREGA_CHOICES, default='retirada_loja')
    local            = models.ForeignKey(
        'LocalEvento',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='orcamentos',
    )
    endereco_avulso  = models.CharField(
        max_length=400, blank=True, default='',
        help_text='Endereço livre quando não for usar um local cadastrado'
    )
    bairro_entrega   = models.CharField(max_length=100, blank=True, default='')
    taxa_entrega     = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    subtotal         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    desconto         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_total      = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    observacoes      = models.TextField(blank=True, default='')

    # Preenchido quando o orçamento é convertido em evento
    evento           = models.OneToOneField(
        'Evento',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='orcamento_origem',
    )

    criado_em        = models.DateTimeField(auto_now_add=True)
    atualizado_em    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Orçamento'
        verbose_name_plural = 'Orçamentos'
        ordering            = ['-criado_em']
        indexes             = [models.Index(fields=['status', 'criado_em'])]

    def __str__(self):
        nome = self.cliente.nome if self.cliente else self.cliente_nome or '—'
        return f'{self.numero} — {nome}'

    @classmethod
    def proximo_numero(cls):
        ultimo = cls.objects.order_by('-id').first()
        if not ultimo:
            return 'ORC-0001'
        try:
            seq = int(ultimo.numero.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = cls.objects.count() + 1
        return f'ORC-{seq:04d}'

    def recalcular_totais(self):
        self.subtotal    = sum(i.preco_total for i in self.itens.all())
        self.valor_total = max(self.subtotal - self.desconto, 0) + self.taxa_entrega
        self.save(update_fields=['subtotal', 'valor_total', 'atualizado_em'])

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

    @property
    def pode_enviar(self):
        return self.status == 'rascunho'

    @property
    def pode_aprovar(self):
        return self.status in ('rascunho', 'enviado')

    @property
    def pode_recusar(self):
        return self.status in ('rascunho', 'enviado')

    @property
    def pode_converter(self):
        return self.status == 'aprovado'

    @property
    def pode_cancelar(self):
        return self.status not in ('convertido', 'recusado', 'expirado')

    @property
    def pode_restaurar(self):
        return self.status == 'expirado'


class ItemOrcamento(models.Model):
    orcamento  = models.ForeignKey(Orcamento, on_delete=models.CASCADE, related_name='itens')
    produto    = models.ForeignKey(
        'pdv.Produto',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='itens_orcamento',
    )
    nome        = models.CharField(max_length=200)
    preco_unit  = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade  = models.PositiveIntegerField(default=1)
    preco_total = models.DecimalField(max_digits=10, decimal_places=2)
    observacao  = models.CharField(max_length=300, blank=True, default='')

    class Meta:
        verbose_name = 'Item de Orçamento'
        ordering     = ['id']

    def __str__(self):
        return f'{self.quantidade}x {self.nome} — {self.orcamento.numero}'

    def save(self, *args, **kwargs):
        self.preco_total = self.preco_unit * self.quantidade
        super().save(*args, **kwargs)


class ImagemInspiracao(models.Model):
    orcamento  = models.ForeignKey(Orcamento, on_delete=models.CASCADE, related_name='imagens_inspiracao')
    imagem     = models.ImageField(upload_to='orcamentos/inspiracao/%Y/%m/')
    criado_em  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Imagem de Inspiração'
        ordering     = ['criado_em']

    def __str__(self):
        return f'Inspiração {self.orcamento.numero} #{self.pk}'


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
    bairro_entrega    = models.CharField(max_length=100, blank=True, default='')
    taxa_entrega      = models.DecimalField(max_digits=8, decimal_places=2, default=0)

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
        self.valor_total = max(self.subtotal - self.desconto, 0) + self.taxa_entrega
        self.save(update_fields=['subtotal', 'valor_total', 'atualizado_em'])

    @property
    def saldo_restante(self):
        return max(self.valor_total - self.sinal_pago, 0)

    def recalcular_sinal_pago(self):
        from django.db.models import Sum
        total_pago = self.pagamentos.filter(status='pago').aggregate(
            t=Sum('valor')
        )['t'] or 0
        self.sinal_pago = total_pago
        self.save(update_fields=['sinal_pago', 'atualizado_em'])

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
# Pagamento do Evento
# ─────────────────────────────────────────────────────────────────────────────

class PagamentoEvento(models.Model):

    FORMA_CHOICES = [
        ('pix',      'Pix'),
        ('dinheiro', 'Dinheiro'),
        ('cartao',   'Cartão'),
        ('outro',    'Outro'),
    ]

    STATUS_CHOICES = [
        ('pago',     'Pago'),
        ('pendente', 'Pendente'),
    ]

    evento          = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='pagamentos')
    valor           = models.DecimalField(max_digits=10, decimal_places=2)
    forma_pagamento = models.CharField(max_length=20, choices=FORMA_CHOICES, default='outro')
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pago')
    data_pagamento  = models.DateField(default=timezone.now)
    observacao      = models.CharField(max_length=300, blank=True, default='')
    comprovante     = models.FileField(upload_to='eventos/comprovantes/%Y/%m/', null=True, blank=True)

    criado_em       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Pagamento de Evento'
        verbose_name_plural  = 'Pagamentos de Evento'
        ordering             = ['data_pagamento', 'criado_em']

    def __str__(self):
        return f'{self.evento.numero} — {self.get_forma_pagamento_display()} — R$ {self.valor}'


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
        'total':          float(evento.valor_total),
        'itens_snapshot': itens_snapshot,
        'pedido_em':      evento.criado_em,
    }

    PedidoUnificado.objects.update_or_create(
        canal='eventos',
        origem_id=evento.pk,
        defaults=defaults,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Configuração de Contrato (singleton) — ver Contrato.md
# ─────────────────────────────────────────────────────────────────────────────

class ConfiguracaoContrato(models.Model):
    """Singleton — sempre acessado via ConfiguracaoContrato.get(). Nada pode ficar
    hardcoded no gerador de PDF, pois o CRM é revendável a outros clientes."""

    # CONTRATADA
    razao_social_contratada = models.CharField(max_length=200, blank=True, default='Arretado Doces')
    cnpj_contratada          = models.CharField(max_length=20,  blank=True, default='29.977.080/0001-11')
    endereco_contratada      = models.CharField(
        max_length=400, blank=True,
        default='Avenida João Antônio Leitão, nº 3733, Bairro Piçarreira, CEP 64.055-400, Teresina/PI',
    )
    instagram_contratada     = models.CharField(max_length=50, blank=True, default='@arretadodoces')
    telefone_contratada      = models.CharField(max_length=20, blank=True, default='(86) 99816-4324')

    # Representante da CONTRATADA
    representante_nome          = models.CharField(max_length=200, blank=True, default='Edvan Lima Silva')
    representante_nacionalidade = models.CharField(max_length=50,  blank=True, default='brasileiro')
    representante_estado_civil  = models.CharField(max_length=20,  blank=True, default='casado')
    representante_profissao     = models.CharField(max_length=100, blank=True, default='biomédico')
    representante_rg            = models.CharField(max_length=20,  blank=True, default='3158399 SSP-PB')
    representante_cpf           = models.CharField(max_length=14,  blank=True, default='081.465.044-93')
    representante_endereco      = models.CharField(
        max_length=400, blank=True,
        default='Rua Vereador Edmundo Genuíno de Oliveira, nº 2945, apto 101, Bairro São Cristóvão, '
                'CEP 64.055-030, Teresina/PI',
    )

    # Financeiro
    percentual_sinal      = models.DecimalField(max_digits=5, decimal_places=2, default=50)
    prazo_quitacao_dias   = models.PositiveIntegerField(default=7, help_text='Dias antes do evento')
    multa_inadimplencia_pct = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    juros_mora_pct_mes    = models.DecimalField(max_digits=5, decimal_places=2, default=1)

    # Prazos
    prazo_personalizacao_dias      = models.PositiveIntegerField(default=15)
    prazo_aumento_quantidade_dias  = models.PositiveIntegerField(default=15)
    prazo_aviso_rescisao_dias      = models.PositiveIntegerField(default=30)

    # Multas de rescisão (por faixa de antecedência)
    multa_rescisao_acima_60_dias_pct   = models.DecimalField(max_digits=5, decimal_places=2, default=15)
    multa_rescisao_30_60_dias_pct      = models.DecimalField(max_digits=5, decimal_places=2, default=25)
    multa_rescisao_abaixo_30_dias_pct  = models.DecimalField(max_digits=5, decimal_places=2, default=30)
    multa_rescisao_abaixo_7_dias_pct   = models.DecimalField(max_digits=5, decimal_places=2, default=40)

    prazo_devolucao_dias = models.PositiveIntegerField(default=30)

    # Foro
    foro_comarca = models.CharField(max_length=100, blank=True, default='Teresina')
    foro_estado  = models.CharField(max_length=100, blank=True, default='Piauí')

    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração de Contrato'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f'Config. Contrato — {self.razao_social_contratada}'


# ─────────────────────────────────────────────────────────────────────────────
# Contrato — emitido a partir de um Orçamento aprovado (ver Contrato.md)
# ─────────────────────────────────────────────────────────────────────────────

class Contrato(models.Model):

    STATUS_CHOICES = [
        ('gerado',    'Gerado'),
        ('enviado',   'Enviado'),
        ('cancelado', 'Cancelado'),
    ]

    numero    = models.CharField(max_length=20, unique=True, db_index=True)
    orcamento = models.ForeignKey(Orcamento, on_delete=models.PROTECT, related_name='contratos')
    evento    = models.ForeignKey(Evento, null=True, blank=True, on_delete=models.SET_NULL, related_name='contratos')
    cliente   = models.ForeignKey(Cliente, null=True, blank=True, on_delete=models.SET_NULL, related_name='contratos')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='gerado', db_index=True)

    # ── Snapshot CONTRATANTE (no momento da emissão) ──
    contratante_nome          = models.CharField(max_length=200)
    contratante_nacionalidade = models.CharField(max_length=50)
    contratante_profissao     = models.CharField(max_length=100, blank=True, default='')
    contratante_rg            = models.CharField(max_length=20,  blank=True, default='')
    contratante_rg_orgao_emissor = models.CharField(max_length=20, blank=True, default='')
    contratante_cpf           = models.CharField(max_length=14)
    contratante_estado_civil  = models.CharField(max_length=20, blank=True, default='')
    contratante_endereco      = models.CharField(max_length=400)

    # ── Snapshot do evento (herdado de Orcamento/Evento) ──
    data_evento  = models.DateField()
    hora_evento  = models.TimeField(null=True, blank=True)
    local_evento = models.CharField(max_length=400, blank=True, default='')

    # ── Financeiro (snapshot da config no momento da emissão) ──
    valor_total      = models.DecimalField(max_digits=10, decimal_places=2)
    percentual_sinal = models.DecimalField(max_digits=5, decimal_places=2)
    valor_sinal      = models.DecimalField(max_digits=10, decimal_places=2)
    data_quitacao    = models.DateField()

    criado_em     = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Contrato'
        verbose_name_plural = 'Contratos'
        ordering            = ['-criado_em']

    def __str__(self):
        return f'{self.numero} — {self.contratante_nome}'

    @classmethod
    def proximo_numero(cls):
        ultimo = cls.objects.order_by('-id').first()
        if not ultimo:
            return 'CTR-0001'
        try:
            seq = int(ultimo.numero.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = cls.objects.count() + 1
        return f'CTR-{seq:04d}'

    @property
    def pode_enviar(self):
        return self.status in ('gerado', 'enviado')


# ─────────────────────────────────────────────────────────────────────────────
# Alertas de Evento (pagamento pendente / aviso de entrega) — cron diário
# ver eventos/management/commands/alertar_eventos.py
# ─────────────────────────────────────────────────────────────────────────────

class ConfiguracaoAlertaEvento(models.Model):
    """Singleton — sempre acessado via ConfiguracaoAlertaEvento.get()."""

    # Pagamento pendente
    ativo_pagamento        = models.BooleanField('Alerta de pagamento pendente ativo', default=True)
    dias_antes_pagamento   = models.PositiveIntegerField(
        'Disparar a partir de quantos dias antes do evento', default=10,
    )
    repetir_pagamento_dias = models.PositiveIntegerField(
        'Repetir a cada quantos dias (enquanto não pago)', default=1,
    )

    # Aviso de local/horário de entrega
    ativo_entrega        = models.BooleanField('Alerta de local/horário de entrega ativo', default=True)
    dias_antes_entrega   = models.PositiveIntegerField(
        'Disparar a partir de quantos dias antes do evento', default=30,
    )
    repetir_entrega_dias = models.PositiveIntegerField('Repetir a cada quantos dias', default=5)

    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração de Alertas de Evento'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return 'Configuração de Alertas de Evento'


class TelefoneAlertaEvento(models.Model):
    """Telefones internos da equipe que recebem os alertas de evento (não é o cliente)."""

    numero    = models.CharField(max_length=30)
    nome      = models.CharField('Nome/label (opcional)', max_length=100, blank=True, default='')
    ativo     = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Telefone de Alerta de Evento'
        verbose_name_plural = 'Telefones de Alerta de Evento'
        ordering            = ['nome', 'numero']

    def __str__(self):
        return f'{self.nome or "—"} ({self.numero})'


class AlertaEventoEnviado(models.Model):
    """
    Rastreia o envio mais recente de cada tipo de alerta por evento, pra
    controlar o intervalo de repetição (repetir_pagamento_dias/
    repetir_entrega_dias em ConfiguracaoAlertaEvento). Não usa
    notificacoes.HistoricoMensagem pra isso porque HistoricoMensagem.cliente
    é FK pra Cliente, não pra Evento, e os destinatários aqui são telefones
    da equipe (sem Cliente associado).
    """

    TIPO_CHOICES = [
        ('pagamento_pendente', 'Pagamento pendente'),
        ('aviso_entrega',      'Aviso de entrega'),
    ]

    evento     = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='alertas_enviados')
    tipo       = models.CharField(max_length=30, choices=TIPO_CHOICES)
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Alerta de Evento Enviado'
        verbose_name_plural = 'Alertas de Evento Enviados'
        ordering            = ['-enviado_em']
        indexes = [
            models.Index(fields=['evento', 'tipo', '-enviado_em']),
        ]

    def __str__(self):
        return f'{self.evento.numero} — {self.get_tipo_display()} ({self.enviado_em:%d/%m %H:%M})'
