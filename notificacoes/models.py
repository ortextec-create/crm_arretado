from django.db import models
from clientes.models import Cliente

MSG_ANIVERSARIO_DEFAULT = (
    'Olá, {nome}! 🎂\n'
    'A equipe Arretado Doces deseja a você um feliz aniversário!\n'
    'Que seu dia seja tão doce quanto os nossos produtos. 🍬'
)

MSG_REENGAJAMENTO_DEFAULT = (
    'Olá, {nome}! Sentimos sua falta por aqui. 🍬\n'
    'Faz um tempinho que você não aparece na Arretado Doces.\n'
    'Temos novidades esperando por você! Que tal dar uma passada?'
)


class ConfiguracaoWhatsApp(models.Model):
    """Singleton — sempre use ConfiguracaoWhatsApp.get()."""

    # Credenciais Z-API
    zapi_instance_id  = models.CharField('Instance ID',   max_length=200, blank=True)
    zapi_token        = models.CharField('Token',         max_length=200, blank=True)
    zapi_client_token = models.CharField('Client-Token',  max_length=200, blank=True)

    # Estado de conexão (atualizado pelos webhooks Ao conectar / Ao desconectar)
    whatsapp_conectado = models.BooleanField('WhatsApp conectado', default=True)

    # Toggles
    notificacoes_pedido_ativo = models.BooleanField('Notif. de pedidos ativa', default=True)
    aniversario_ativo         = models.BooleanField('Parabéns de aniversário ativo', default=True)
    reengajamento_ativo       = models.BooleanField('Reengajamento ativo', default=True)

    # Reengajamento
    dias_sem_compra = models.PositiveIntegerField('Dias sem compra', default=30)

    # Orçamentos
    validade_orcamento_dias = models.PositiveIntegerField('Validade padrão do orçamento (dias)', default=30)

    # Templates (suportam {nome})
    mensagem_aniversario   = models.TextField('Mensagem de aniversário',  default=MSG_ANIVERSARIO_DEFAULT)
    mensagem_reengajamento = models.TextField('Mensagem de reengajamento', default=MSG_REENGAJAMENTO_DEFAULT)

    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração WhatsApp'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={
            'mensagem_aniversario':   MSG_ANIVERSARIO_DEFAULT,
            'mensagem_reengajamento': MSG_REENGAJAMENTO_DEFAULT,
        })
        return obj


class HistoricoMensagem(models.Model):

    TIPO_CHOICES = [
        ('manual',        'Envio Manual'),
        ('aniversario',   'Parabéns Aniversário'),
        ('pedido',        'Atualização de Pedido'),
        ('reengajamento', 'Reengajamento'),
        ('lembrete',      'Lembrete'),
        ('orcamento',     'Orçamento PDF'),
        ('contrato',      'Contrato PDF'),
        ('alerta_pagamento', 'Alerta de Pagamento Pendente'),
        ('alerta_entrega',   'Alerta de Entrega Próxima'),
    ]

    STATUS_CHOICES = [
        ('pendente',  'Pendente'),
        ('enviado',   'Enviado'),
        ('entregue',  'Entregue'),
        ('lido',      'Lido'),
        ('falha',     'Falha'),
    ]

    cliente  = models.ForeignKey(
        Cliente,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='mensagens_whatsapp',
    )
    telefone   = models.CharField(max_length=30)
    mensagem   = models.TextField()
    tipo       = models.CharField(max_length=20, choices=TIPO_CHOICES, default='manual')
    status     = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pendente', db_index=True)
    message_id = models.CharField(max_length=100, blank=True, db_index=True)
    erro       = models.TextField(blank=True, default='')
    enviado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = 'Mensagem WhatsApp'
        verbose_name_plural = 'Histórico de Mensagens WhatsApp'
        ordering            = ['-enviado_em']
        indexes             = [
            models.Index(fields=['tipo', 'status']),
        ]

    def __str__(self):
        dest = self.cliente.nome if self.cliente else self.telefone
        return f'{self.get_tipo_display()} → {dest} [{self.get_status_display()}]'
