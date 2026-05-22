"""
Worker de polling do iFood.
Chamado a cada 30 segundos via management command ou Celery.

Fluxo:
  1. GET /orders:polling
  2. Para cada evento PLACED → busca detalhes, cria PedidoIFood, vincula Cliente CRM
  3. Para demais eventos → atualiza status do pedido existente
  4. POST /orders:acknowledgment com todos os IDs recebidos
"""
import logging
from datetime import datetime, timezone as dt_tz

from django.utils import timezone
from django.db import transaction

from clientes.models import Cliente
from .models import ConfiguracaoIFood, PedidoIFood, ItemPedidoIFood, EventoPollingIFood
from .ifood_client import IFoodClient, IFoodAPIError

logger = logging.getLogger(__name__)

# Mapeamento: fullCode iFood → status interno
STATUS_MAP = {
    'PLACED':                  'PLACED',
    'CONFIRMED':               'CONFIRMED',
    'PREPARATION_STARTED':     'PREPARATION_STARTED',
    'READY_TO_PICKUP':         'READY_TO_PICKUP',
    'DISPATCHED':              'DISPATCHED',
    'CONCLUDED':               'CONCLUDED',
    'CANCELLATION_REQUESTED':  'CANCELLATION_REQUESTED',
    'CANCELLED':               'CANCELLED',
    'ORDER_PLACED':            'PLACED',
    'ORDER_CONFIRMED':         'CONFIRMED',
    'ORDER_DISPATCHED':        'DISPATCHED',
    'ORDER_CONCLUDED':         'CONCLUDED',
    'ORDER_CANCELLED':         'CANCELLED',
}

CODE_MAP = {
    'PLC': 'PLC', 'CFM': 'CFM', 'DSP': 'DSP',
    'CAN': 'CAN', 'CAC': 'CAC', 'CON': 'CON', 'HBT': 'HBT',
}


def run_polling():
    """
    Executa um ciclo de polling para todas as configurações ativas.
    Retorna dict com resumo.
    """
    configs = ConfiguracaoIFood.objects.filter(polling_ativo=True)
    if not configs.exists():
        logger.debug('Nenhuma configuração iFood ativa para polling.')
        return {'configs': 0, 'eventos': 0, 'pedidos_novos': 0}

    totais = {'configs': 0, 'eventos': 0, 'pedidos_novos': 0, 'erros': []}

    for config in configs:
        try:
            result = _processar_config(config)
            totais['configs'] += 1
            totais['eventos'] += result['eventos']
            totais['pedidos_novos'] += result['pedidos_novos']
        except Exception as e:
            logger.error('Erro no polling config %s: %s', config.merchant_id, e, exc_info=True)
            totais['erros'].append(str(e))

    return totais


def _processar_config(config):
    client = IFoodClient(config)
    eventos_raw = client.polling()

    if not eventos_raw:
        return {'eventos': 0, 'pedidos_novos': 0}

    event_ids_para_ack = []
    pedidos_novos = 0

    for evt in eventos_raw:
        event_id  = evt.get('id', '')
        full_code = evt.get('fullCode', evt.get('code', ''))
        order_id  = evt.get('orderId', '')
        code      = evt.get('code', 'OTH')
        created_at = _parse_dt(evt.get('createdAt'))

        # Salva o evento no log (ignora duplicatas)
        evento_obj, criado = EventoPollingIFood.objects.get_or_create(
            ifood_event_id=event_id,
            defaults={
                'code':            CODE_MAP.get(code, 'OTH'),
                'full_code':       full_code,
                'order_id':        order_id,
                'merchant_id':     evt.get('merchantId', config.merchant_id),
                'payload':         evt,
                'ifood_criado_em': created_at,
            }
        )

        if not criado:
            # Já processado antes
            event_ids_para_ack.append(event_id)
            continue

        # Heartbeat: só faz ACK
        if full_code in ('HEARTBEAT', 'HBT') or code == 'HBT':
            event_ids_para_ack.append(event_id)
            evento_obj.acknowledged = True
            evento_obj.processado = True
            evento_obj.save(update_fields=['acknowledged', 'processado'])
            continue

        # Processar evento de pedido
        try:
            with transaction.atomic():
                novo = _processar_evento_pedido(client, evt, config)
                if novo:
                    pedidos_novos += 1
            evento_obj.processado = True
            evento_obj.save(update_fields=['processado'])
        except Exception as e:
            logger.error('Erro ao processar evento %s (%s): %s', event_id, full_code, e, exc_info=True)

        event_ids_para_ack.append(event_id)

    # Envia ACK para todos os eventos recebidos
    try:
        client.acknowledgment(event_ids_para_ack)
        EventoPollingIFood.objects.filter(
            ifood_event_id__in=event_ids_para_ack
        ).update(acknowledged=True)
    except IFoodAPIError as e:
        logger.error('Falha ao enviar ACK: %s', e)

    return {'eventos': len(eventos_raw), 'pedidos_novos': pedidos_novos}


def _processar_evento_pedido(client, evt, config):
    """
    Cria ou atualiza PedidoIFood com base no evento.
    Retorna True se foi criado novo pedido.
    """
    full_code = evt.get('fullCode', evt.get('code', ''))
    order_id  = evt.get('orderId', '')

    if not order_id:
        return False

    novo_status = STATUS_MAP.get(full_code)

    # Pedido ainda não existe → busca detalhes e cria
    pedido_existente = PedidoIFood.objects.filter(ifood_order_id=order_id).first()

    if pedido_existente is None:
        # Busca detalhes mesmo que não seja PLACED (pode ter perdido o evento)
        try:
            detalhe = client.get_order(order_id)
        except IFoodAPIError as e:
            if e.status_code == 404:
                logger.warning('Pedido %s não encontrado na API iFood', order_id)
                return False
            raise
        pedido = _criar_pedido(detalhe, config)
        if novo_status and novo_status != 'PLACED':
            pedido.status = novo_status
            pedido.save(update_fields=['status'])
        return True
    else:
        # Atualiza status se mapeado
        if novo_status and pedido_existente.status != novo_status:
            pedido_existente.status = novo_status
            pedido_existente.save(update_fields=['status', 'atualizado_em'])
        return False


def _criar_pedido(detalhe: dict, config) -> PedidoIFood:
    """
    Cria PedidoIFood + ItemPedidoIFood a partir do payload completo.
    Tenta vincular ao Cliente CRM por telefone ou ifood_customer_id.
    """
    order_id   = detalhe.get('id', '')
    customer   = detalhe.get('customer', {})
    delivery   = detalhe.get('delivery', {})
    payments   = detalhe.get('payments', {})
    total_info = detalhe.get('total', {})
    items_raw  = detalhe.get('items', [])

    # Pagamento
    payment_label = ''
    methods = payments.get('methods', [])
    if methods:
        m = methods[0]
        payment_label = m.get('method', '') or m.get('type', '')

    # Valores
    total_valor  = _cents(total_info.get('orderAmount', 0))
    subtotal     = _cents(total_info.get('subTotal', 0))
    taxa_entrega = _cents(total_info.get('deliveryFee', 0))
    desconto     = _cents(total_info.get('benefits', 0))

    # Endereço
    delivery_address = delivery.get('deliveryAddress', {}) if delivery else {}

    # Tenta vincular cliente CRM
    cliente_obj = None
    ifood_cust_id = customer.get('id', '')
    telefone_raw  = customer.get('phone', {})
    telefone_num  = telefone_raw.get('number', '') if isinstance(telefone_raw, dict) else str(telefone_raw)

    if ifood_cust_id:
        cliente_obj = Cliente.objects.filter(ifood_customer_id=ifood_cust_id).first()

    if not cliente_obj and telefone_num:
        # Tenta por telefone (busca parcial nos últimos 8 dígitos)
        sufixo = telefone_num[-8:] if len(telefone_num) >= 8 else telefone_num
        cliente_obj = Cliente.objects.filter(telefone_principal__endswith=sufixo).first()

    pedido = PedidoIFood.objects.create(
        ifood_order_id   = order_id,
        ifood_merchant_id= detalhe.get('merchant', {}).get('id', config.merchant_id),
        display_id       = detalhe.get('displayId', ''),
        cliente          = cliente_obj,
        status           = STATUS_MAP.get(detalhe.get('fullCode', 'PLACED'), 'PLACED'),
        order_type       = detalhe.get('orderType', 'DELIVERY'),
        total_valor      = total_valor,
        subtotal         = subtotal,
        taxa_entrega     = taxa_entrega,
        desconto         = desconto,
        payment_method   = payment_label,
        cliente_nome     = customer.get('name', ''),
        cliente_telefone = telefone_num,
        cliente_ifood_id = ifood_cust_id,
        endereco_entrega = delivery_address,
        payload_raw      = detalhe,
        ifood_criado_em  = _parse_dt(detalhe.get('createdAt')),
    )

    # Cria itens
    for item in items_raw:
        complementos = []
        for opt in item.get('options', []):
            complementos.append({
                'nome': opt.get('name', ''),
                'quantidade': opt.get('quantity', 1),
                'preco': _cents(opt.get('unitPrice', 0)),
            })
        ItemPedidoIFood.objects.create(
            pedido        = pedido,
            ifood_item_id = item.get('id', ''),
            nome          = item.get('name', ''),
            quantidade    = item.get('quantity', 1),
            preco_unit    = _cents(item.get('unitPrice', 0)),
            preco_total   = _cents(item.get('totalPrice', 0)),
            observacao    = item.get('observations', ''),
            complementos  = complementos,
        )

    logger.info('Pedido iFood criado: %s (cliente=%s)', pedido.display_id or order_id[:8], cliente_obj)
    return pedido


def _cents(value):
    """iFood retorna valores em centavos (int) ou float — normaliza para Decimal."""
    try:
        v = float(value)
        return v / 100 if v > 1000 else v  # heurística: >1000 provavelmente centavos
    except (TypeError, ValueError):
        return 0


def _parse_dt(value):
    if not value:
        return None
    try:
        if value.endswith('Z'):
            value = value[:-1] + '+00:00'
        return datetime.fromisoformat(value).astimezone(dt_tz.utc).replace(tzinfo=dt_tz.utc)
    except Exception:
        return None
