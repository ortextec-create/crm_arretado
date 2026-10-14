"""
Gatilho por status do PedidoIFood. O signal SÓ grava no banco — nunca faz HTTP.
Todo o corpo em try/except: nunca falha o fluxo do polling.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

STATUS_GATILHO = {
    'CONFIRMED': 'confirmado',
    'PREPARATION_STARTED': 'em_preparo',
    'DISPATCHED': 'saiu_entrega',
    'CONCLUDED': 'concluido',
    'CANCELLED': 'cancelado',
}


def gatilho_do_pedido(pedido):
    if pedido.status == 'READY_TO_PICKUP':
        return 'pronto_retirada' if pedido.order_type == 'TAKEOUT' else 'pronto_entrega'
    return STATUS_GATILHO.get(pedido.status)


@receiver(post_save, sender='ifood.PedidoIFood')
def on_pedido_ifood_save(sender, instance, **kwargs):
    try:
        from .models import MensagemChat
        from .servico import enfileirar

        if instance.status == 'CANCELLED':
            MensagemChat.objects.filter(pedido=instance, direcao='saida', status='pendente') \
                .exclude(gatilho='cancelado').update(status='cancelada')

        gatilho = gatilho_do_pedido(instance)
        if gatilho:
            enfileirar(instance, gatilho)
    except Exception:
        logger.exception('atendimento: falha no signal do PedidoIFood #%s', instance.pk)
