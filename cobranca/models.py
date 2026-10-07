from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from eventos.models import Evento
from notificacoes.models import HistoricoMensagem
from usuarios.models import Usuario

MSG_PRAZO_HOJE_DEFAULT = (
    'Oi, {primeiro_nome}! Passando para lembrar que hoje é o prazo que combinamos '
    'para o saldo do evento {numero_evento}: *R$ {saldo}*.\n'
    'Pix: {chave_pix}\n'
    'Obrigado! 💛'
)

MSG_PRAZO_VENCIDO_DEFAULT = (
    'Olá, {primeiro_nome}. O prazo combinado ({prazo_combinado}) para o saldo de '
    '*R$ {saldo}* do evento {numero_evento} venceu e ainda não identificamos o pagamento.\n'
    'Pode nos dar um retorno?\n'
    'Pix: {chave_pix}'
)

MSG_LIGACAO_NAO_ATENDIDA_DEFAULT = (
    'Oi, {primeiro_nome}! Tentamos falar com você por telefone sobre o saldo do '
    'evento {numero_evento} (*R$ {saldo}*).\n'
    'Quando puder, nos chame por aqui ou no {telefone_empresa}. Obrigado!'
)


class ConfiguracaoCobranca(models.Model):
    """Singleton — sempre via ConfiguracaoCobranca.get(). Nasce desligada (ver CLAUDE.md/COBRANCA.md)."""

    ativo = models.BooleanField('Envio automático ligado', default=False)
    # Read-only na API — gravado pela view no PATCH que muda ativo de False→True.
    ativo_desde = models.DateField('Ligado desde', null=True, blank=True)

    limite_lembrete = models.IntegerField(
        'Data limite (fronteira lembrete × cobrança)', default=-7,
        validators=[MinValueValidator(-60), MaxValueValidator(60)],
    )
    dias_semana_envio = models.JSONField('Dias da semana com envio', default=list)

    chave_pix = models.CharField('Chave Pix', max_length=120, blank=True, default='')
    favorecido_pix = models.CharField('Favorecido do Pix', max_length=120, blank=True, default='')
    telefone_contato = models.CharField('Telefone de contato', max_length=30, blank=True, default='')

    intervalo_envio_segundos = models.PositiveSmallIntegerField(
        'Intervalo entre envios (segundos)', default=3,
        validators=[MaxValueValidator(30)],
    )
    notificar_equipe_ultima_etapa = models.BooleanField(
        'Avisar a equipe quando a última etapa é enviada sem pagamento', default=True,
    )

    msg_prazo_hoje_ativo = models.BooleanField('Mensagem "prazo vence hoje" ativa', default=True)
    msg_prazo_hoje = models.TextField('Mensagem "prazo vence hoje"', default=MSG_PRAZO_HOJE_DEFAULT)

    msg_prazo_vencido_ativo = models.BooleanField('Mensagem "prazo venceu" ativa', default=True)
    msg_prazo_vencido = models.TextField('Mensagem "prazo venceu"', default=MSG_PRAZO_VENCIDO_DEFAULT)

    msg_ligacao_nao_atendida_ativo = models.BooleanField(
        'Mensagem "tentamos te ligar" ativa', default=False,
    )
    msg_ligacao_nao_atendida = models.TextField(
        'Mensagem "tentamos te ligar"', default=MSG_LIGACAO_NAO_ATENDIDA_DEFAULT,
    )

    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração de Cobrança'

    def __str__(self):
        return 'Configuração de Cobrança'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={
            'dias_semana_envio': [0, 1, 2, 3, 4, 5],
            'msg_prazo_hoje': MSG_PRAZO_HOJE_DEFAULT,
            'msg_prazo_vencido': MSG_PRAZO_VENCIDO_DEFAULT,
            'msg_ligacao_nao_atendida': MSG_LIGACAO_NAO_ATENDIDA_DEFAULT,
        })
        return obj


class EtapaRegua(models.Model):
    """
    Uma mensagem de WhatsApp disparada a `dias` dias da data do evento
    (negativo = antes, positivo = depois). O tipo (lembrete/cobrança) é
    sempre derivado de ConfiguracaoCobranca.limite_lembrete — nunca gravado
    aqui. Sem DELETE: envios antigos apontam pra etapa (PROTECT em
    EnvioCobranca.etapa) — desativar no lugar de excluir.
    """

    dias = models.IntegerField(
        'Dias em relação à data do evento',
        validators=[MinValueValidator(-60), MaxValueValidator(60)],
    )
    mensagem = models.TextField('Mensagem')
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Etapa da Régua de Cobrança'
        verbose_name_plural = 'Etapas da Régua de Cobrança'
        ordering = ['dias']
        constraints = [
            models.UniqueConstraint(fields=['dias'], name='uniq_etapa_regua_dias'),
        ]

    def __str__(self):
        sinal = f'D{self.dias:+d}' if self.dias else 'D0'
        return f'{sinal} — {self.mensagem[:40]}'


class PausaCobranca(models.Model):
    """
    Pausa da régua combinada com o cliente, sempre com prazo (nunca
    indefinida). Vigente = derivado (encerrada_em IS NULL AND
    pausado_ate >= hoje) — ver regua.pausa_vigente(). Sem PATCH/DELETE:
    encerrar antes do prazo só via action `encerrar/`.
    """

    ORIGEM_CHOICES = [
        ('manual', 'Manual'),
        ('ligacao', 'Via ligação'),
    ]

    evento = models.ForeignKey(Evento, on_delete=models.PROTECT, related_name='pausas_cobranca')
    pausado_ate = models.DateField('Pausado até')
    motivo = models.CharField(max_length=300)
    origem = models.CharField(max_length=10, choices=ORIGEM_CHOICES, default='manual')
    ligacao = models.OneToOneField(
        'LigacaoCobranca', on_delete=models.PROTECT, null=True, blank=True,
        related_name='pausa_criada',
    )

    criado_por = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='pausas_cobranca_criadas',
    )
    criado_por_nome = models.CharField(max_length=150, blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)

    encerrada_em = models.DateTimeField(null=True, blank=True)
    encerrada_por = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='pausas_cobranca_encerradas',
    )
    encerrada_por_nome = models.CharField(max_length=150, blank=True, default='')
    motivo_encerramento = models.CharField(max_length=300, blank=True, default='')

    class Meta:
        verbose_name = 'Pausa de Cobrança'
        verbose_name_plural = 'Pausas de Cobrança'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['evento', '-criado_em']),
        ]

    def __str__(self):
        return f'{self.evento.numero} — pausa até {self.pausado_ate:%d/%m/%Y}'

    @property
    def vigente(self):
        return self.encerrada_em is None and self.pausado_ate >= timezone.localdate()


class LigacaoCobranca(models.Model):
    """Registro imutável de tentativa de ligação de cobrança. Correção = novo registro."""

    evento = models.ForeignKey(Evento, on_delete=models.PROTECT, related_name='ligacoes_cobranca')
    data_hora = models.DateTimeField(default=timezone.now)
    atendente = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='ligacoes_cobranca_atendidas',
    )
    atendente_nome = models.CharField(max_length=150, blank=True, default='')
    telefone_discado = models.CharField(max_length=30)
    atendeu = models.BooleanField()
    prazo_pagamento = models.DateField(null=True, blank=True)
    observacao = models.TextField(blank=True, default='')

    registrado_por = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='ligacoes_cobranca_registradas',
    )
    registrado_por_nome = models.CharField(max_length=150, blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ligação de Cobrança'
        verbose_name_plural = 'Ligações de Cobrança'
        ordering = ['-data_hora']
        indexes = [
            models.Index(fields=['evento', '-data_hora']),
        ]

    def __str__(self):
        resultado = 'atendeu' if self.atendeu else 'não atendeu'
        return f'{self.evento.numero} — {self.data_hora:%d/%m/%Y %H:%M} ({resultado})'


class EnvioCobranca(models.Model):
    """Log imutável de cada mensagem de WhatsApp (ou pulo) da régua/pausa/ligação."""

    TIPO_CHOICES = [
        ('lembrete', 'Lembrete'),
        ('cobranca', 'Cobrança'),
        ('prazo_hoje', 'Prazo combinado vence hoje'),
        ('prazo_vencido', 'Prazo combinado venceu'),
        ('ligacao_nao_atendida', 'Ligação não atendida'),
    ]

    STATUS_CHOICES = [
        ('enviado', 'Enviado'),
        ('falha', 'Falha'),
        ('pulada', 'Pulada'),
    ]

    MOTIVO_PULADA_CHOICES = [
        ('atraso', 'Atraso (etapa mais antiga pulada em favor da mais recente)'),
        ('pausa', 'Pausa vigente'),
        ('mesmo_dia', 'Já saiu outra mensagem no mesmo dia'),
    ]

    evento = models.ForeignKey(Evento, on_delete=models.PROTECT, related_name='envios_cobranca')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    etapa = models.ForeignKey(
        EtapaRegua, on_delete=models.PROTECT, null=True, blank=True, related_name='envios',
    )
    dias_etapa = models.IntegerField(null=True, blank=True)
    rotulo_etapa = models.CharField(max_length=5, blank=True, default='')
    data_evento_referencia = models.DateField()

    pausa = models.ForeignKey(
        PausaCobranca, on_delete=models.PROTECT, null=True, blank=True, related_name='envios',
    )
    ligacao = models.ForeignKey(
        LigacaoCobranca, on_delete=models.PROTECT, null=True, blank=True, related_name='envios',
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    motivo_pulada = models.CharField(max_length=10, choices=MOTIVO_PULADA_CHOICES, blank=True, default='')

    telefone = models.CharField(max_length=30, blank=True, default='')
    mensagem_renderizada = models.TextField(blank=True, default='')
    saldo_no_envio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    historico = models.ForeignKey(
        HistoricoMensagem, on_delete=models.SET_NULL, null=True, blank=True, related_name='envios_cobranca',
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Envio de Cobrança'
        verbose_name_plural = 'Envios de Cobrança'
        ordering = ['-criado_em']
        constraints = [
            models.UniqueConstraint(
                fields=['evento', 'etapa', 'data_evento_referencia'],
                condition=Q(etapa__isnull=False) & Q(status__in=['enviado', 'pulada']),
                name='uniq_envio_etapa_evento_data',
            ),
            models.UniqueConstraint(
                fields=['pausa', 'tipo'],
                condition=Q(pausa__isnull=False) & Q(tipo__in=['prazo_hoje', 'prazo_vencido']) & Q(status='enviado'),
                name='uniq_envio_pausa_tipo',
            ),
            models.UniqueConstraint(
                fields=['ligacao'],
                condition=Q(ligacao__isnull=False) & Q(status='enviado'),
                name='uniq_envio_ligacao',
            ),
        ]
        indexes = [
            models.Index(fields=['evento', '-criado_em']),
        ]

    def __str__(self):
        return f'{self.evento.numero} — {self.get_tipo_display()} ({self.get_status_display()})'
