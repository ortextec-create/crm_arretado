"""
Ponto único de criação de MensagemChat de saída (ver ATENDIMENTO_IFOOD.md).
Signal, cron e views chamam só `enfileirar()`. Nunca lança exceção.
"""
import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import ConfiguracaoAtendimento, GATILHOS_LIVRES, MensagemChat, ModeloMensagemChat
from .render import renderizar

logger = logging.getLogger(__name__)


def enfileirar(pedido, gatilho, *, extra=None, origem='automatico', texto=None, autor=None, status='pendente'):
    try:
        if origem == 'automatico' and gatilho not in GATILHOS_LIVRES:
            return _enfileirar_automatico(pedido, gatilho, extra)
        if not (texto or '').strip():
            return None
        return MensagemChat.objects.create(
            empresa=pedido.empresa, pedido=pedido, direcao='saida', origem=origem,
            gatilho=gatilho, texto=texto.strip(), status=status, autor=autor,
        )
    except Exception:
        logger.exception('atendimento: falha ao enfileirar %s do pedido #%s', gatilho, getattr(pedido, 'pk', None))
        return None


def _enfileirar_automatico(pedido, gatilho, extra):
    cfg = ConfiguracaoAtendimento.get(pedido.empresa)
    if not cfg.chat_ativo:
        return None

    agora = timezone.now()
    referencia = pedido.ifood_criado_em or pedido.criado_em
    if referencia < agora - timedelta(hours=cfg.janela_maxima_horas):
        return None

    modelo = ModeloMensagemChat.objects.filter(empresa=pedido.empresa, gatilho=gatilho).first()
    if modelo is None or not modelo.ativo:
        return None

    if MensagemChat.objects.filter(pedido=pedido, gatilho=gatilho, direcao='saida').exists():
        return None

    try:
        with transaction.atomic():
            return MensagemChat.objects.create(
                empresa=pedido.empresa, pedido=pedido, direcao='saida', origem='automatico',
                gatilho=gatilho, texto=renderizar(modelo.texto, pedido, extra), status='pendente',
                expira_em=agora + timedelta(minutes=cfg.expiracao_minutos),
            )
    except IntegrityError:
        return None  # corrida: outra thread criou entre o exists() e o create()
