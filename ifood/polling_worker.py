"""
ifood/polling_worker.py
Worker de polling do iFood — Arretado CRM
Atualizado: Junho 2026

Fluxo:
  1. GET /order/v1.0/events:polling (a cada 30s)
  2. Para cada evento PLACED → busca detalhes, cria PedidoIFood, vincula Cliente CRM
  3. Para demais eventos → atualiza status do pedido existente
  4. Detecta eventos de negociação (CANCELLATION_REQUESTED etc.) e marca pedido
  5. POST /order/v1.0/events/acknowledgment com os OBJETOS COMPLETOS dos eventos
     (a API extrai o campo 'id' internamente — não enviar só os IDs)

Campos extraídos para homologação:
  - payment_brand    ← payments.methods[0].card.brand
  - payment_troco    ← payments.methods[0].cash.changeFor
  - payment_prepaid  ← payments.prepaid
  - cliente_cpf      ← customer.taxPayerIdentificationNumber
  - observacao_pedido← metadata.observations / userNote
  - agendamento_dt   ← schedule.scheduledDateTimeEnd
  - benefits_raw     ← benefits (lista de cupons)
  - negociacao_*     ← detectado via NEGOCIACAO_CODES
"""
import logging
from datetime import datetime, timezone as dt_tz

from django.utils import timezone
from django.db import transaction

from clientes.models import Cliente
from .models import ConfiguracaoIFood, PedidoIFood, ItemPedidoIFood, EventoPollingIFood
from .ifood_client import IFoodClient, IFoodAPIError

logger = logging.getLogger(__name__)

# ── Mapeamento: fullCode iFood → status interno ───────────────────────────────
STATUS_MAP = {
    'PLACED':                          'PLACED',
    'CONFIRMED':                       'CONFIRMED',
    'PREPARATION_STARTED':             'PREPARATION_STARTED',
    'READY_TO_PICKUP':                 'READY_TO_PICKUP',
    'DISPATCHED':                      'DISPATCHED',
    'CONCLUDED':                       'CONCLUDED',
    'CANCELLATION_REQUESTED':          'CANCELLATION_REQUESTED',
    'CANCELLED':                       'CANCELLED',
    # Aliases usados pelo iFood em diferentes versões
    'ORDER_PLACED':                    'PLACED',
    'ORDER_CONFIRMED':                 'CONFIRMED',
    'ORDER_DISPATCHED':                'DISPATCHED',
    'ORDER_CONCLUDED':                 'CONCLUDED',
    'ORDER_CANCELLED':                 'CANCELLED',
    # Negociação
    'CONSUMER_CANCELLATION_REQUESTED': 'CANCELLATION_REQUESTED',
    'ORDER_CANCELLATION_REQUESTED':    'CANCELLATION_REQUESTED',
    'CANCELLATION_DENIED':             'CONFIRMED',  # loja recusou → volta a CONFIRMED
}

CODE_MAP = {
    'PLC': 'PLC', 'CFM': 'CFM', 'DSP': 'DSP',
    'CAN': 'CAN', 'CAC': 'CAC', 'CON': 'CON', 'HBT': 'HBT',
}

# Eventos que indicam pedido de cancelamento via Plataforma de Negociação
NEGOCIACAO_CODES = {
    'CANCELLATION_REQUESTED',
    'CONSUMER_CANCELLATION_REQUESTED',
    'ORDER_CANCELLATION_REQUESTED',
    'NEGOTIATION_REQUESTED',
}


# ── Entrada principal ─────────────────────────────────────────────────────────

def run_polling():
    """
    Executa um ciclo de polling para todas as configurações ativas.
    Retorna dict com resumo: configs, eventos, pedidos_novos, erros.
    """
    configs = ConfiguracaoIFood.objects.filter(polling_ativo=True)
    if not configs.exists():
        logger.debug('Nenhuma configuração iFood ativa para polling.')
        return {'configs': 0, 'eventos': 0, 'pedidos_novos': 0}

    totais = {'configs': 0, 'eventos': 0, 'pedidos_novos': 0, 'erros': []}

    for config in configs:
        try:
            result = _processar_config(config)
            totais['configs']      += 1
            totais['eventos']      += result['eventos']
            totais['pedidos_novos'] += result['pedidos_novos']
        except Exception as e:
            logger.error('Erro no polling config %s: %s', config.merchant_id, e, exc_info=True)
            totais['erros'].append(str(e))

    return totais


# ── Processamento por configuração ────────────────────────────────────────────

def _processar_config(config):
    client = IFoodClient(config)
    eventos_raw = client.polling()

    if not eventos_raw:
        return {'eventos': 0, 'pedidos_novos': 0}

    # Guarda OBJETOS COMPLETOS para ACK (a API extrai o campo 'id' internamente)
    eventos_para_ack = []
    pedidos_novos    = 0

    for evt in eventos_raw:
        event_id   = evt.get('id', '')
        full_code  = evt.get('fullCode', evt.get('code', ''))
        order_id   = evt.get('orderId', '')
        code       = evt.get('code', 'OTH')
        created_at = _parse_dt(evt.get('createdAt'))

        # ── Salva evento no log (ignora duplicatas) ──
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

        # Sempre inclui no ACK (duplicata ou não)
        eventos_para_ack.append(evt)

        if not criado:
            # Evento já processado anteriormente — só faz ACK
            continue

        # ── Heartbeat: só faz ACK, não cria pedido ──
        if full_code in ('HEARTBEAT', 'HBT') or code == 'HBT':
            evento_obj.acknowledged = True
            evento_obj.processado   = True
            evento_obj.save(update_fields=['acknowledged', 'processado'])
            continue

        # ── Processa evento de pedido ──
        try:
            with transaction.atomic():
                novo = _processar_evento_pedido(client, evt, config)
                if novo:
                    pedidos_novos += 1

                # ── Negociação: marcar pedido como pendente ──
                # Só marca se for cancelamento do CONSUMIDOR, não automático do sistema
                metadata = evt.get('metadata', {}) or {}
                is_system_cancel = (
                    metadata.get('ORIGIN', '').upper() == 'SYSTEM'
                    or full_code == 'CANCELLATION_REQUESTED' and metadata.get('ORIGIN', '') == ''
                    and metadata.get('reason_code', '') in ('902', '903', '904')
                )
                if full_code in NEGOCIACAO_CODES and order_id and not is_system_cancel:
                    nego_desc = (
                        metadata.get('reason', '')
                        or evt.get('reason', '')
                    )
                    PedidoIFood.objects.filter(ifood_order_id=order_id).update(
                        negociacao_pendente  = True,
                        negociacao_tipo      = full_code,
                        negociacao_descricao = nego_desc,
                        status               = 'CANCELLATION_REQUESTED',
                    )
                    logger.info(
                        'Negociação detectada para pedido %s: %s',
                        order_id[:8], full_code,
                    )

            evento_obj.processado = True
            evento_obj.save(update_fields=['processado'])

        except Exception as e:
            logger.error(
                'Erro ao processar evento %s (%s): %s',
                event_id, full_code, e, exc_info=True,
            )

    # ── ACK: envia objetos completos (não apenas IDs) ──
    # A documentação iFood diz: "send an array with event IDs or the complete
    # content received in polling. The API only uses the ID to process acknowledgment."
    # Enviamos os objetos completos pois é o formato que o endpoint aceita.
    if eventos_para_ack:
        try:
            client.acknowledgment(eventos_para_ack)
            # Marca como acknowledged no banco usando os IDs extraídos
            ids_ack = [e.get('id') for e in eventos_para_ack if e.get('id')]
            EventoPollingIFood.objects.filter(
                ifood_event_id__in=ids_ack
            ).update(acknowledged=True)
            logger.info('ACK enviado para %d eventos', len(eventos_para_ack))
        except IFoodAPIError as e:
            logger.error('Falha ao enviar ACK: %s', e)

    return {'eventos': len(eventos_raw), 'pedidos_novos': pedidos_novos}


# ── Processamento individual de evento ───────────────────────────────────────

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

    pedido_existente = PedidoIFood.objects.filter(ifood_order_id=order_id).first()

    if pedido_existente is None:
        # Pedido ainda não existe → busca detalhes e cria
        try:
            detalhe = client.get_order(order_id)
        except IFoodAPIError as e:
            if e.status_code == 404:
                logger.warning('Pedido %s não encontrado na API iFood (ainda não disponível)', order_id)
                return False
            raise
        pedido = _criar_pedido(detalhe, config)
        if config.auto_confirmar:
            try:
                client.confirm_order(order_id)
                pedido.status = 'CONFIRMED'
                pedido.save(update_fields=['status', 'atualizado_em'])
                logger.info('Pedido %s auto-confirmado', order_id[:8])
            except IFoodAPIError as e:
                logger.error('Falha ao auto-confirmar pedido %s: %s', order_id[:8], e)

            if config.auto_despachar and pedido.status == 'CONFIRMED' and not pedido.agendamento_dt:
                try:
                    despachou = True
                    if pedido.order_type == 'TAKEOUT':
                        client.ready_to_pickup(order_id)
                        pedido.status = 'READY_TO_PICKUP'
                        logger.info('Pedido %s auto-marcado pronto p/ retirada', order_id[:8])
                    elif pedido.delivery_mode == 'MERCHANT':
                        client.dispatch_order(order_id)
                        pedido.status = 'DISPATCHED'
                        logger.info('Pedido %s auto-despachado (MERCHANT)', order_id[:8])
                    else:
                        # IFOOD_DELIVERY: iFood cuida do despacho, restaurante não chama dispatch
                        despachou = False
                        logger.info('Pedido %s sem despacho automático (modo=%s)', order_id[:8], pedido.delivery_mode)
                    if despachou:
                        pedido.save(update_fields=['status', 'atualizado_em'])
                except IFoodAPIError as e:
                    logger.error('Falha ao auto-despachar pedido %s: %s', order_id[:8], e)
            elif config.auto_despachar and pedido.agendamento_dt:
                logger.info('Pedido %s agendado — despacho automático ignorado (janela: %s)', order_id[:8], pedido.agendamento_dt)
        elif novo_status and novo_status != 'PLACED':
            pedido.status = novo_status
            pedido.save(update_fields=['status'])
        return True
    else:
        # Pedido já existe → atualiza status se mapeado
        if novo_status and pedido_existente.status != novo_status:
            pedido_existente.status = novo_status
            pedido_existente.save(update_fields=['status', 'atualizado_em'])
        return False


# ── Criação de pedido a partir do payload completo ────────────────────────────

def _criar_pedido(detalhe: dict, config) -> PedidoIFood:
    """
    Cria PedidoIFood + ItemPedidoIFood a partir do payload completo da API iFood.
    Tenta vincular ao Cliente CRM por ifood_customer_id ou telefone.

    Campos extraídos para homologação:
      - payment_brand     ← payments.methods[0].card.brand
      - payment_troco     ← payments.methods[0].cash.changeFor
      - payment_prepaid   ← payments.prepaid
      - cliente_cpf       ← customer.taxPayerIdentificationNumber
      - observacao_pedido ← metadata.observations / userNote
      - agendamento_dt    ← schedule.scheduledDateTimeEnd
      - benefits_raw      ← benefits (lista de cupons)
    """
    order_id   = detalhe.get('id', '')
    customer   = detalhe.get('customer', {}) or {}
    delivery   = detalhe.get('delivery', {}) or {}
    payments   = detalhe.get('payments', {}) or {}
    total_info = detalhe.get('total', {}) or {}
    items_raw  = detalhe.get('items', []) or []
    metadata   = detalhe.get('metadata', {}) or {}
    schedule   = detalhe.get('schedule', {}) or {}
    benefits   = detalhe.get('benefits', []) or []

    # ── Pagamento ──────────────────────────────────────────────────────────────
    payment_label   = ''
    payment_brand   = ''
    payment_troco   = None
    payment_prepaid = bool(payments.get('prepaid', False))

    methods = payments.get('methods', [])
    if methods:
        m = methods[0]
        payment_label = m.get('method', '') or m.get('type', '')

        card_info = m.get('card', {}) or {}
        if card_info:
            payment_brand = card_info.get('brand', '')

        cash_info = m.get('cash', {}) or {}
        if cash_info:
            raw_troco = cash_info.get('changeFor', None)
            if raw_troco is not None:
                payment_troco = _cents(raw_troco)

    # ── Valores financeiros ───────────────────────────────────────────────────
    total_valor  = _cents(total_info.get('orderAmount', 0))
    subtotal     = _cents(total_info.get('subTotal', 0))
    taxa_entrega = _cents(total_info.get('deliveryFee', 0))
    desconto     = _cents(total_info.get('benefits', 0))

    # ── Endereço de entrega ───────────────────────────────────────────────────
    delivery_address = delivery.get('deliveryAddress', {}) or {}

    # ── CPF/CNPJ do cliente ───────────────────────────────────────────────────
    cliente_cpf = customer.get('taxPayerIdentificationNumber', '') or ''

    # ── Observação do pedido ──────────────────────────────────────────────────
    observacao_pedido = (
        metadata.get('observations', '')
        or detalhe.get('userNote', '')
        or detalhe.get('observations', '')
        or ''
    )

    # ── Agendamento ───────────────────────────────────────────────────────────
    agendamento_dt = None
    if schedule:
        raw_sched = (
            schedule.get('scheduledDateTimeEnd')
            or schedule.get('deliveryDateTimeEnd')
        )
        if raw_sched:
            agendamento_dt = _parse_dt(raw_sched)

    # ── Modo de entrega ───────────────────────────────────────────────────────
    # deliveryMethod pode estar na raiz do payload ou dentro de delivery
    delivery_method_raw = detalhe.get('deliveryMethod', {}) or delivery.get('deliveryMethod', {}) or {}
    delivery_mode = (
        delivery_method_raw.get('mode', '')
        or delivery_method_raw.get('deliveredBy', '')
        or delivery.get('deliveredBy', '')
        or ''
    ).upper()

    # ── Vínculo com Cliente CRM ───────────────────────────────────────────────
    cliente_obj   = None
    ifood_cust_id = customer.get('id', '')
    telefone_raw  = customer.get('phone', {})
    if isinstance(telefone_raw, dict):
        # localizer = número real do cliente; number = 0800 mascarado pelo iFood
        telefone_num = telefone_raw.get('localizer', '') or telefone_raw.get('number', '')
    else:
        telefone_num = str(telefone_raw or '')

    if ifood_cust_id:
        cliente_obj = Cliente.objects.filter(ifood_customer_id=ifood_cust_id).first()

    if not cliente_obj and telefone_num:
        sufixo = telefone_num[-8:] if len(telefone_num) >= 8 else telefone_num
        cliente_obj = Cliente.objects.filter(
            telefone_principal__endswith=sufixo
        ).first()

    # ── Cria o pedido ─────────────────────────────────────────────────────────
    pedido = PedidoIFood.objects.create(
        ifood_order_id    = order_id,
        ifood_merchant_id = detalhe.get('merchant', {}).get('id', config.merchant_id),
        display_id        = detalhe.get('displayId', ''),
        cliente           = cliente_obj,
        status            = STATUS_MAP.get(detalhe.get('fullCode', 'PLACED'), 'PLACED'),
        order_type        = detalhe.get('orderType', 'DELIVERY'),
        total_valor       = total_valor,
        subtotal          = subtotal,
        taxa_entrega      = taxa_entrega,
        desconto          = desconto,
        # Pagamento
        payment_method    = payment_label,
        payment_brand     = payment_brand,
        payment_troco     = payment_troco,
        payment_prepaid   = payment_prepaid,
        # Cliente
        cliente_nome      = customer.get('name', ''),
        cliente_telefone  = telefone_num,
        cliente_ifood_id  = ifood_cust_id,
        cliente_cpf       = cliente_cpf,
        # Pedido
        observacao_pedido = observacao_pedido,
        agendamento_dt    = agendamento_dt,
        benefits_raw      = benefits if isinstance(benefits, list) else [],
        # Entrega e payload
        delivery_mode     = delivery_mode,
        endereco_entrega  = delivery_address,
        payload_raw       = detalhe,
        ifood_criado_em   = _parse_dt(detalhe.get('createdAt')),
    )

    # ── Cria itens ────────────────────────────────────────────────────────────
    for item in items_raw:
        complementos = []
        for opt in item.get('options', []) or []:
            complementos.append({
                'nome':       opt.get('name', ''),
                'quantidade': opt.get('quantity', 1),
                'preco':      _cents(opt.get('unitPrice', 0)),
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

    logger.info(
        'Pedido iFood criado: %s (cliente=%s, tipo=%s, agendado=%s, troco=%s)',
        pedido.display_id or order_id[:8],
        cliente_obj,
        pedido.order_type,
        agendamento_dt,
        payment_troco,
    )
    return pedido


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cents(value):
    """
    iFood retorna valores monetários de formas inconsistentes:
    às vezes em centavos (int > 1000), às vezes em reais (float < 100).
    Heurística: se valor > 1000, assume centavos e divide por 100.
    """
    try:
        v = float(value)
        return round(v / 100, 2) if v > 1000 else round(v, 2)
    except (TypeError, ValueError):
        return 0


def _parse_dt(value):
    """Converte string ISO 8601 (com ou sem 'Z') para datetime UTC."""
    if not value:
        return None
    try:
        if isinstance(value, str) and value.endswith('Z'):
            value = value[:-1] + '+00:00'
        return datetime.fromisoformat(value).astimezone(dt_tz.utc).replace(tzinfo=dt_tz.utc)
    except Exception:
        return None