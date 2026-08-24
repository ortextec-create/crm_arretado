"""
Signals do módulo Financeiro (Fase 4): PDV/iFood/PagamentoEvento batem no
ledger MovimentoFinanceiro.registrar() no fluxo normal de venda. Mesmo
padrão de estoque/signals.py: post_save com sender como string (evita
import circular), sempre dentro de try/except (nunca derruba a venda), e
idempotente checando a existência do movimento antes de gravar (post_save
dispara em TODO save(), não só na transição de status).

Eventos e PDV NUNCA materializam ContaReceber (ver ContaReceber.__doc__ /
CLAUDE.md) — só o iFood no modo 'repasse'. PDV e iFood 'no_ato' batem
direto no ledger porque o dinheiro já entrou no caixa.

Conta destino dos movimentos automáticos: ConfiguracaoFinanceira.get(empresa).
conta_padrao_vendas — resolvida pela empresa do pedido (Fase 4 do
multi-empresa, MULTIEMPRESA.md; não confundir com a "Fase 4" do FINANCEIRO.md
citada acima, numeração de spec diferente). PDV e PagamentoEvento são
mono-empresa (sempre Empresa.get_padrao()); iFood usa pedido.empresa
(denormalizada desde a Fase 1). Se a config da empresa não tiver
conta_padrao_vendas, loga warning e NÃO grava — nunca criar ContaBancaria
automaticamente.

Estorno em cancelamento pós-movimento (PDV/iFood 'no_ato') e em remoção de
PagamentoEvento: movimento manual inverso (saída de mesmo valor), nunca
apagando o movimento original — ledger é imutável.
"""
import logging
from datetime import timedelta

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _conta_padrao_ou_none(empresa):
    from .models import ConfiguracaoFinanceira
    conta = ConfiguracaoFinanceira.get(empresa).conta_padrao_vendas
    if not conta:
        logger.warning(
            'financeiro: conta_padrao_vendas não configurada pra empresa %s — movimento automático não gravado.',
            empresa,
        )
    return conta


# ─── PDV (mono-empresa — sempre a empresa padrão) ──────────────────────────

@receiver(post_save, sender='pdv.PedidoPDV')
def on_pedido_pdv_salvo(sender, instance, **kwargs):
    try:
        if instance.status == 'confirmado':
            _registrar_venda_pdv(instance)
        elif instance.status == 'cancelado':
            _estornar_pdv(instance)
    except Exception as e:
        logger.warning('financeiro: falha no signal do PedidoPDV #%s: %s', instance.pk, e)


def _registrar_venda_pdv(pedido):
    from empresas.models import Empresa

    from .models import MovimentoFinanceiro
    if MovimentoFinanceiro.objects.filter(origem_tipo='pdv', origem_id=pedido.id).exists():
        return  # já registrado — idempotência
    conta = _conta_padrao_ou_none(Empresa.get_padrao())
    if not conta:
        return
    MovimentoFinanceiro.registrar(
        conta=conta, tipo='entrada', valor=pedido.total, origem_tipo='pdv', origem_id=pedido.id,
        cliente=pedido.cliente, descricao=f'Venda PDV #{pedido.numero}',
    )


def _estornar_pdv(pedido):
    from .models import MovimentoFinanceiro
    original = MovimentoFinanceiro.objects.filter(origem_tipo='pdv', origem_id=pedido.id).first()
    if not original:
        return  # nunca chegou a gerar movimento — nada a estornar
    estorno_id = f'estorno-pdv-{pedido.id}'
    if MovimentoFinanceiro.objects.filter(origem_tipo='manual', origem_id=estorno_id).exists():
        return  # já estornado — idempotência
    MovimentoFinanceiro.registrar(
        conta=original.conta, tipo='saida', valor=original.valor, origem_tipo='manual',
        origem_id=estorno_id, descricao=f'Estorno cancelamento PDV #{pedido.numero}',
    )


# ─── iFood ──────────────────────────────────────────────────────────────────

@receiver(post_save, sender='ifood.PedidoIFood')
def on_pedido_ifood_salvo(sender, instance, **kwargs):
    try:
        if instance.status == 'CONCLUDED':
            _registrar_venda_ifood(instance)
        elif instance.status == 'CANCELLED':
            _estornar_ifood(instance)
    except Exception as e:
        logger.warning('financeiro: falha no signal do PedidoIFood #%s: %s', instance.pk, e)


def _registrar_venda_ifood(pedido):
    """
    Só dispara na transição pra CONCLUDED — nunca em cada evento de polling.
    Resolve tudo pela empresa do próprio pedido (FK desde a Fase 1 do
    multi-empresa) — permite MANGAIO em 'repasse' e matriz em 'no_ato'
    simultaneamente, sem misturar credencial/conta de uma empresa com o
    pedido de outra.
    """
    from .models import ConfiguracaoFinanceira, ContaReceber, MovimentoFinanceiro

    cfg = ConfiguracaoFinanceira.get(pedido.empresa)
    referencia = pedido.display_id or pedido.ifood_order_id

    if cfg.recebimento_ifood == 'no_ato':
        if MovimentoFinanceiro.objects.filter(origem_tipo='ifood', origem_id=pedido.id).exists():
            return
        conta = _conta_padrao_ou_none(pedido.empresa)
        if not conta:
            return
        MovimentoFinanceiro.registrar(
            conta=conta, tipo='entrada', valor=pedido.total_valor, origem_tipo='ifood',
            origem_id=pedido.id, cliente=pedido.cliente, descricao=f'Venda iFood #{referencia}',
        )
        return

    # modo 'repasse': dinheiro só chega depois — vira ContaReceber, não bate no ledger agora
    if ContaReceber.objects.filter(origem_canal='ifood', origem_id=str(pedido.id)).exists():
        return
    data_pedido = (pedido.ifood_criado_em or pedido.criado_em).date()
    ContaReceber.objects.create(
        numero=ContaReceber.proximo_numero(), empresa=pedido.empresa,
        cliente=pedido.cliente, cliente_nome=pedido.cliente_nome,
        canal='ifood', referencia=referencia, valor=pedido.total_valor,
        data_vencimento=data_pedido + timedelta(days=cfg.dias_repasse_ifood),
        origem_canal='ifood', origem_id=str(pedido.id),
    )


def _estornar_ifood(pedido):
    from .models import ContaReceber, MovimentoFinanceiro

    # modo 'no_ato': já bateu no ledger — reverte com movimento manual inverso
    original = MovimentoFinanceiro.objects.filter(origem_tipo='ifood', origem_id=pedido.id).first()
    if original:
        estorno_id = f'estorno-ifood-{pedido.id}'
        if not MovimentoFinanceiro.objects.filter(origem_tipo='manual', origem_id=estorno_id).exists():
            MovimentoFinanceiro.registrar(
                conta=original.conta, tipo='saida', valor=original.valor, origem_tipo='manual',
                origem_id=estorno_id,
                descricao=f'Estorno cancelamento iFood #{pedido.display_id or pedido.ifood_order_id}',
            )

    # modo 'repasse': dinheiro nunca chegou a entrar — só cancela a ContaReceber, sem lançamento no ledger
    conta_receber = ContaReceber.objects.filter(
        origem_canal='ifood', origem_id=str(pedido.id), status__in=['pendente', 'parcial'],
    ).first()
    if conta_receber and conta_receber.valor_recebido == 0:
        conta_receber.status = 'cancelada'
        conta_receber.save(update_fields=['status', 'atualizado_em'])


# ─── Eventos (PagamentoEvento) ──────────────────────────────────────────────

@receiver(post_save, sender='eventos.PagamentoEvento')
def on_pagamento_evento_salvo(sender, instance, **kwargs):
    try:
        if instance.status == 'pago':
            _registrar_pagamento_evento(instance)
    except Exception as e:
        logger.warning('financeiro: falha no signal do PagamentoEvento #%s: %s', instance.pk, e)


def _registrar_pagamento_evento(pagamento):
    from empresas.models import Empresa

    from .models import MovimentoFinanceiro
    if MovimentoFinanceiro.objects.filter(origem_tipo='evento_pagamento', origem_id=pagamento.id).exists():
        return
    conta = _conta_padrao_ou_none(Empresa.get_padrao())
    if not conta:
        return
    MovimentoFinanceiro.registrar(
        conta=conta, tipo='entrada', valor=pagamento.valor, origem_tipo='evento_pagamento',
        origem_id=pagamento.id, data_movimento=pagamento.data_pagamento,
        forma_pagamento=pagamento.forma_pagamento, descricao=f'Pagamento {pagamento.evento.numero}',
    )


@receiver(post_delete, sender='eventos.PagamentoEvento')
def on_pagamento_evento_removido(sender, instance, **kwargs):
    try:
        _estornar_pagamento_evento(instance)
    except Exception as e:
        logger.warning('financeiro: falha no estorno do PagamentoEvento #%s: %s', instance.pk, e)


def _estornar_pagamento_evento(pagamento):
    from .models import MovimentoFinanceiro
    original = MovimentoFinanceiro.objects.filter(origem_tipo='evento_pagamento', origem_id=pagamento.id).first()
    if not original:
        return  # pagamento removido nunca tinha batido no ledger (ex.: status pendente) — nada a estornar
    estorno_id = f'estorno-evento-pagamento-{pagamento.id}'
    if MovimentoFinanceiro.objects.filter(origem_tipo='manual', origem_id=estorno_id).exists():
        return
    MovimentoFinanceiro.registrar(
        conta=original.conta, tipo='saida', valor=original.valor, origem_tipo='manual',
        origem_id=estorno_id, descricao=f'Estorno pagamento {pagamento.evento.numero}',
    )
