"""
Signals do app pdv.

Sempre que um PedidoPDV for salvo, espelha/atualiza o registro
correspondente em pedidos.PedidoUnificado.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='pdv.PedidoPDV')
def on_pedido_pdv_save(sender, instance, **kwargs):
    try:
        _sincronizar(instance)
    except Exception as e:
        logger.warning('Falha ao sincronizar PedidoUnificado para PDV #%s: %s', instance.pk, e)


def _sincronizar(pedido):
    from pedidos.models import PedidoUnificado

    # Mapa de status PDV → status normalizado
    STATUS_MAP = {
        'aberto':     'pendente',
        'confirmado': 'confirmado',
        'em_preparo': 'em_preparo',
        'pronto':     'pronto',
        'concluido':  'concluido',
        'cancelado':  'cancelado',
    }

    # Mapa de tipo PDV → tipo normalizado
    TIPO_MAP = {
        'balcao':   'balcao',
        'retirada': 'retirada',
        'delivery': 'delivery',
        'mesa':     'mesa',
    }

    # Snapshot dos itens
    itens_snapshot = [
        {
            'nome':        item.nome,
            'quantidade':  item.quantidade,
            'preco_unit':  float(item.preco_unit),
            'preco_total': float(item.preco_total),
            'obs':         item.observacao,
        }
        for item in pedido.itens.all()
    ]

    # Nome/telefone: CRM tem prioridade
    nome_cliente = ''
    tel_cliente  = ''
    if pedido.cliente:
        nome_cliente = pedido.cliente.nome
        tel_cliente  = pedido.cliente.telefone_principal
    else:
        nome_cliente = pedido.cliente_nome
        tel_cliente  = pedido.cliente_telefone

    defaults = {
        'canal':           'pdv',
        'numero':          pedido.numero,
        'cliente':         pedido.cliente,
        'status':          STATUS_MAP.get(pedido.status, 'pendente'),
        'status_original': pedido.status,
        'tipo':            TIPO_MAP.get(pedido.tipo, 'balcao'),
        'subtotal':        pedido.subtotal,
        'taxa_entrega':    pedido.taxa_entrega,
        'desconto':        pedido.desconto,
        'total':           pedido.total,
        'pagamento':       pedido.get_pagamento_display(),
        'cliente_nome':    nome_cliente,
        'cliente_telefone': tel_cliente,
        'itens_snapshot':  itens_snapshot,
        'pedido_em':       pedido.criado_em,
    }

    PedidoUnificado.objects.update_or_create(
        canal='pdv',
        origem_id=pedido.pk,
        defaults=defaults,
    )
