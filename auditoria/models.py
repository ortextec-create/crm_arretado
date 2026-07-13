from django.db import models

from usuarios.models import Usuario


class LogAuditoria(models.Model):
    ACAO_LOGIN_SUCESSO      = 'login_sucesso'
    ACAO_LOGIN_FALHA        = 'login_falha'
    ACAO_LOGOUT             = 'logout'
    ACAO_USUARIO_CRIADO     = 'usuario_criado'
    ACAO_USUARIO_EDITADO    = 'usuario_editado'
    ACAO_USUARIO_REMOVIDO   = 'usuario_removido'
    ACAO_PERMISSAO_ALTERADA = 'permissao_alterada'
    ACAO_SENHA_REDEFINIDA   = 'senha_redefinida'
    ACAO_PAGAMENTO_REGISTRADO = 'pagamento_registrado'
    ACAO_PAGAMENTO_REMOVIDO   = 'pagamento_removido'
    ACAO_CONTRATO_EMITIDO = 'contrato_emitido'
    ACAO_CONTRATO_ENVIADO = 'contrato_enviado'
    ACAO_AJUSTE_LINEAR_APLICADO = 'ajuste_linear_aplicado'
    ACAO_AJUSTE_LINEAR_DESFEITO = 'ajuste_linear_desfeito'
    ACAO_PRECO_MATERIA_ATUALIZADO = 'preco_materia_atualizado'
    ACAO_PARAMETROS_NEGOCIO_ALTERADOS = 'parametros_negocio_alterados'
    ACAO_CONFIG_CONTRATO_ALTERADA = 'config_contrato_alterada'
    ACAO_CONFIG_ENTREGA_ALTERADA = 'config_entrega_alterada'
    ACAO_CONFIG_WHATSAPP_ALTERADA = 'config_whatsapp_alterada'
    ACAO_REGISTRO_EXCLUIDO = 'registro_excluido'
    ACAO_REGISTRO_CRIADO = 'registro_criado'
    ACAO_REGISTRO_ATUALIZADO = 'registro_atualizado'
    ACAO_STATUS_ALTERADO = 'status_alterado'
    ACAO_ITEM_ADICIONADO = 'item_adicionado'
    ACAO_ORCAMENTO_CONVERTIDO = 'orcamento_convertido_em_evento'

    # NOTA: choices é só documentação/UI (dropdown do frontend) — o campo é
    # CharField livre por baixo, então futuros apps (pagamentos, contratos,
    # ajuste de preço, singletons) podem gravar ações novas via registrar()
    # sem quebrar nada; ao adicionar uma ação nova, também acrescentar aqui
    # pra manter o filtro do frontend íntegro.
    ACAO_CHOICES = [
        (ACAO_LOGIN_SUCESSO,      'Login com sucesso'),
        (ACAO_LOGIN_FALHA,        'Tentativa de login falhou'),
        (ACAO_LOGOUT,             'Logout'),
        (ACAO_USUARIO_CRIADO,     'Usuário criado'),
        (ACAO_USUARIO_EDITADO,    'Usuário editado'),
        (ACAO_USUARIO_REMOVIDO,   'Usuário removido'),
        (ACAO_PERMISSAO_ALTERADA, 'Permissão/role alterada'),
        (ACAO_SENHA_REDEFINIDA,   'Senha redefinida'),
        (ACAO_PAGAMENTO_REGISTRADO, 'Pagamento registrado'),
        (ACAO_PAGAMENTO_REMOVIDO,   'Pagamento removido'),
        (ACAO_CONTRATO_EMITIDO, 'Contrato emitido'),
        (ACAO_CONTRATO_ENVIADO, 'Contrato enviado'),
        (ACAO_AJUSTE_LINEAR_APLICADO, 'Ajuste linear de preços aplicado'),
        (ACAO_AJUSTE_LINEAR_DESFEITO, 'Ajuste linear de preços desfeito'),
        (ACAO_PRECO_MATERIA_ATUALIZADO, 'Preço de matéria-prima atualizado'),
        (ACAO_PARAMETROS_NEGOCIO_ALTERADOS, 'Parâmetros de negócio alterados'),
        (ACAO_CONFIG_CONTRATO_ALTERADA, 'Configuração de contrato alterada'),
        (ACAO_CONFIG_ENTREGA_ALTERADA, 'Configuração de entrega alterada'),
        (ACAO_CONFIG_WHATSAPP_ALTERADA, 'Configuração de WhatsApp alterada'),
        (ACAO_REGISTRO_EXCLUIDO, 'Registro excluído'),
        (ACAO_REGISTRO_CRIADO, 'Registro criado'),
        (ACAO_REGISTRO_ATUALIZADO, 'Registro atualizado'),
        (ACAO_STATUS_ALTERADO, 'Status alterado'),
        (ACAO_ITEM_ADICIONADO, 'Item adicionado'),
        (ACAO_ORCAMENTO_CONVERTIDO, 'Orçamento convertido em evento'),
    ]

    usuario = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logs_auditoria', verbose_name='Usuário (ator)',
    )
    usuario_nome_snapshot = models.CharField('Nome do usuário (snapshot)', max_length=150, blank=True)
    acao      = models.CharField('Ação', max_length=40, choices=ACAO_CHOICES)
    detalhes  = models.JSONField('Detalhes', default=dict, blank=True)
    ip        = models.GenericIPAddressField('IP', null=True, blank=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        db_table = 'auditoria_logs'
        verbose_name = 'Log de Auditoria'
        verbose_name_plural = 'Logs de Auditoria'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['acao']),
            models.Index(fields=['-criado_em']),
            models.Index(fields=['usuario']),
        ]

    def __str__(self):
        return f'{self.get_acao_display()} — {self.usuario_nome_snapshot} ({self.criado_em:%d/%m/%Y %H:%M})'


class PresencaEdicao(models.Model):
    """
    Heartbeat de "quem está vendo/editando este registro agora" — via polling
    REST (não WebSocket, ver CLAUDE.md). unique_together garante no máximo 1
    linha por usuário×objeto, então a tabela cresce por combinação única já
    visitada, não por visita — não precisa de limpeza periódica por ora.
    """
    usuario   = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='presencas')
    model     = models.CharField(max_length=50)
    objeto_id = models.PositiveIntegerField()
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'auditoria_presenca_edicao'
        verbose_name = 'Presença de Edição'
        verbose_name_plural = 'Presenças de Edição'
        unique_together = [('usuario', 'model', 'objeto_id')]
        indexes = [
            models.Index(fields=['model', 'objeto_id']),
        ]

    def __str__(self):
        return f'{self.usuario.name} em {self.model}#{self.objeto_id} ({self.atualizado_em:%H:%M:%S})'
