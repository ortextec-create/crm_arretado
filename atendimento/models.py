import hashlib
import secrets

from django.db import models
from django.db.models import Q
from django.utils import timezone

from empresas.models import Empresa
from ifood.models import PedidoIFood
from usuarios.models import Usuario

from .modelos_padrao import MODELOS_PADRAO

GATILHOS_COM_MODELO = [
    ('confirmado', 'Pedido confirmado'),
    ('em_preparo', 'Em preparo'),
    ('pronto_retirada', 'Pronto para retirada'),
    ('pronto_entrega', 'Pronto, aguardando entregador'),
    ('saiu_entrega', 'Saiu para entrega'),
    ('concluido', 'Concluído'),
    ('cancelado', 'Cancelado'),
    ('entregador_chegou', 'Entregador chegou na loja'),
    ('atraso_antes_despacho', 'Atraso antes do despacho'),
    ('atraso_apos_despacho', 'Atraso após o despacho'),
]
GATILHOS_SEM_MODELO = [('manual', 'Envio manual'), ('ia', 'Resposta da IA')]
GATILHOS_LIVRES = ('manual', 'ia')  # fora da unicidade (pedido, gatilho)


class ConfiguracaoAtendimento(models.Model):
    """1 linha por empresa — sempre via `.get(empresa)`. `chat_ativo` nasce False e nunca é ligado por código."""

    MODO_IA_CHOICES = [('desligado', 'Desligado'), ('sugestao', 'Sugestão'), ('automatico', 'Automático')]

    empresa = models.OneToOneField(Empresa, on_delete=models.PROTECT, related_name='config_atendimento')
    chat_ativo = models.BooleanField(default=False)
    janela_maxima_horas = models.PositiveIntegerField(default=6)
    expiracao_minutos = models.PositiveIntegerField(default=20)
    atraso_tolerancia_min = models.PositiveIntegerField(default=10)
    modo_ia = models.CharField(max_length=12, choices=MODO_IA_CHOICES, default='desligado')
    ia_modelo = models.CharField(max_length=60, default='claude-haiku-4-5')
    ia_timeout_segundos = models.PositiveIntegerField(default=30)
    ia_instrucoes_tom = models.TextField(blank=True, default='')
    ia_contexto_loja = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Configuração de Atendimento'
        verbose_name_plural = 'Configurações de Atendimento'

    @classmethod
    def get(cls, empresa):
        obj, _ = cls.objects.get_or_create(empresa=empresa)
        ModeloMensagemChat.garantir_padroes(empresa)
        return obj

    def __str__(self):
        return f'Atendimento ({self.empresa.nome})'


class ConfiguracaoExtensao(models.Model):
    """Singleton global da extensão de Chrome — sempre via `.get()`."""

    seletores = models.JSONField(default=dict, blank=True)
    tempos_ms = models.JSONField(default=dict, blank=True)
    intervalo_segundos = models.PositiveIntegerField(default=5)
    pausa_interacao_segundos = models.PositiveIntegerField(default=15)
    lease_segundos = models.PositiveIntegerField(default=120)

    class Meta:
        verbose_name = 'Configuração da Extensão'
        verbose_name_plural = 'Configuração da Extensão'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ModeloMensagemChat(models.Model):
    """Sem DELETE — desativar via `ativo=False`."""

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='modelos_mensagem_chat')
    gatilho = models.CharField(max_length=30, choices=GATILHOS_COM_MODELO)
    texto = models.TextField()
    ativo = models.BooleanField(default=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'gatilho'], name='uniq_modelo_chat_empresa_gatilho'),
        ]
        ordering = ['id']

    @classmethod
    def garantir_padroes(cls, empresa):
        """Cria (preguiçosamente) os modelos que ainda não existem para a empresa. Nunca sobrescreve."""
        existentes = set(cls.objects.filter(empresa=empresa).values_list('gatilho', flat=True))
        for gatilho, (texto, ativo) in MODELOS_PADRAO.items():
            if gatilho not in existentes:
                cls.objects.create(empresa=empresa, gatilho=gatilho, texto=texto, ativo=ativo)

    def __str__(self):
        return f'{self.empresa_id}:{self.gatilho}'


class MensagemChat(models.Model):
    """Fila de saída e registro de entrada do chat. Sem DELETE (histórico)."""

    DIRECAO_CHOICES = [('saida', 'Saída'), ('entrada', 'Entrada')]
    ORIGEM_CHOICES = [
        ('automatico', 'Automático'), ('manual', 'Manual'), ('ia', 'IA'),
        ('cliente', 'Cliente'), ('loja_gestor', 'Digitado no Gestor'), ('sistema', 'Sistema iFood'),
    ]
    STATUS_CHOICES = [
        ('sugerida', 'Sugerida'), ('pendente', 'Pendente'), ('enviando', 'Enviando'),
        ('enviada', 'Enviada'), ('falha', 'Falha'), ('incerta', 'Incerta'),
        ('expirada', 'Expirada'), ('cancelada', 'Cancelada'), ('recebida', 'Recebida'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='mensagens_chat')
    pedido = models.ForeignKey(PedidoIFood, on_delete=models.PROTECT, related_name='mensagens_chat')
    direcao = models.CharField(max_length=8, choices=DIRECAO_CHOICES, default='saida')
    origem = models.CharField(max_length=12, choices=ORIGEM_CHOICES, default='automatico')
    gatilho = models.CharField(max_length=30, choices=GATILHOS_COM_MODELO + GATILHOS_SEM_MODELO, blank=True, default='')
    texto = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pendente')
    tentativas = models.PositiveSmallIntegerField(default=0)
    reservado_em = models.DateTimeField(null=True, blank=True)
    enviado_em = models.DateTimeField(null=True, blank=True)
    expira_em = models.DateTimeField(null=True, blank=True)
    erro = models.TextField(blank=True, default='')
    passos = models.JSONField(default=list, blank=True)
    autor = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='mensagens_chat')
    hash_entrada = models.CharField(max_length=64, null=True, blank=True, unique=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        constraints = [
            # Uma mensagem automática por gatilho por pedido (saída). manual/ia ficam livres.
            models.UniqueConstraint(
                fields=['pedido', 'gatilho'],
                condition=Q(direcao='saida') & ~Q(gatilho__in=GATILHOS_LIVRES),
                name='uniq_msgchat_pedido_gatilho_saida',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'criado_em']),
            models.Index(fields=['pedido', 'criado_em']),
        ]

    def __str__(self):
        return f'MensagemChat #{self.pk} ({self.gatilho or self.direcao}, {self.status})'


def hash_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


class TokenExtensao(models.Model):
    """Credencial da extensão. Só o SHA-256 é gravado; o token puro aparece uma única vez na criação."""

    nome = models.CharField(max_length=100)
    token_hash = models.CharField(max_length=64, unique=True)
    prefixo = models.CharField(max_length=8)
    empresas = models.ManyToManyField(Empresa, related_name='tokens_extensao')
    ativo = models.BooleanField(default=True)
    criado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    criado_em = models.DateTimeField(auto_now_add=True)
    ultimo_heartbeat = models.DateTimeField(null=True, blank=True)
    versao_extensao = models.CharField(max_length=30, blank=True, default='')
    ultimo_diagnostico = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-criado_em']

    @classmethod
    def criar(cls, nome, empresas, criado_por=None):
        """Devolve (instancia, token_puro)."""
        token = secrets.token_urlsafe(32)
        obj = cls.objects.create(
            nome=nome, token_hash=hash_token(token), prefixo=token[:8], criado_por=criado_por,
        )
        obj.empresas.set(empresas)
        return obj, token

    def __str__(self):
        return f'{self.nome} ({self.prefixo}…)'
