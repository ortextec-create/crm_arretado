"""
Serviço central de notificações WhatsApp.

Use notificar() a partir de views e management commands.
Nunca chame zapi_client diretamente em signals ou models.
"""
import logging
from . import zapi_client as zapi
from .models import HistoricoMensagem

logger = logging.getLogger(__name__)

_TIPOS_COM_TOGGLE = {
    'pedido':        'notificacoes_pedido_ativo',
    'aniversario':   'aniversario_ativo',
    'reengajamento': 'reengajamento_ativo',
}


def _tipo_ativo(tipo: str) -> bool:
    """Verifica se o tipo de notificação está ativo na configuração do banco."""
    campo = _TIPOS_COM_TOGGLE.get(tipo)
    if not campo:
        return True
    try:
        from .models import ConfiguracaoWhatsApp
        cfg = ConfiguracaoWhatsApp.objects.filter(pk=1).first()
        if cfg:
            return getattr(cfg, campo, True)
    except Exception:
        pass
    return True


def notificar(telefone: str, mensagem: str, cliente=None, tipo: str = 'pedido') -> bool:
    """
    Envia mensagem WhatsApp e grava HistoricoMensagem.
    Retorna True se enviado, False se desativado, sem telefone ou com falha.
    Nunca lança exceção.
    """
    if not telefone:
        return False

    if not _tipo_ativo(tipo):
        return False

    registro = HistoricoMensagem(
        cliente=cliente,
        telefone=telefone,
        mensagem=mensagem,
        tipo=tipo,
        status='pendente',
    )

    try:
        result = zapi.enviar_texto(telefone, mensagem)
        registro.status     = 'enviado'
        registro.message_id = result.get('messageId', '') if isinstance(result, dict) else ''
    except zapi.ZAPIError as e:
        registro.status = 'falha'
        registro.erro   = str(e)
        logger.warning('notificar: falha ao enviar para %s — %s', telefone, e)

    try:
        registro.save()
    except Exception as e:
        logger.error('notificar: falha ao gravar HistoricoMensagem — %s', e)

    return registro.status == 'enviado'


def _fone_pedido(pedido) -> str:
    """Retorna telefone do cliente vinculado ou do campo snapshot do pedido."""
    if pedido.cliente and pedido.cliente.telefone_principal:
        return pedido.cliente.telefone_principal
    return getattr(pedido, 'cliente_telefone', '') or ''
