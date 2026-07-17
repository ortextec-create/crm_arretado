"""
Débito automático de estoque na venda. Reaproveita o padrão já usado em
pdv/signals.py: post_save com sender='app.Model' (string, evita import
circular), sempre dentro de try/except (nunca derruba o save() principal).

Gatilhos (decididos com o usuário durante o planejamento):
  - PedidoPDV: ao entrar em status 'confirmado' (simétrico ao iFood).
  - PedidoIFood: ao entrar em status 'CONFIRMED'.
  - Evento: ao entrar em status 'entregue' (não há status por item).

Idempotência: post_save dispara em TODO save(), não só na transição de
status — por isso cada handler checa se já existe MovimentoEstoque para
aquela origem antes de debitar.

Estorno automático em cancelamento pós-débito: fora de escopo (decisão
tomada com o usuário) — ajuste manual de inventário cobre esse caso.
"""
import logging
from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _debitar_produto(produto, quantidade, *, origem_tipo, origem_id, criado_por=None):
    """
    Aplica a regra de estoque de 3 vias do produto vendido:
      - revenda / fabricado+estoque -> débito direto no saldo do produto.
      - fabricado+sob_encomenda     -> débito direto nos insumos da ficha
                                        vinculada (proporcional), sem passar
                                        por Producao.
      - kit                         -> recursivo em cada ItemKit.componente.
    """
    from .models import MovimentoEstoque

    if produto.tipo == 'kit':
        for item_kit in produto.itens_kit.select_related('componente').all():
            _debitar_produto(
                item_kit.componente, quantidade * item_kit.quantidade,
                origem_tipo=origem_tipo, origem_id=origem_id, criado_por=criado_por,
            )
        return

    if produto.tipo == 'fabricado' and produto.modo_estoque == 'sob_encomenda':
        from fichas.models import FichaTecnica
        ficha = FichaTecnica.objects.filter(produto_pdv_id=produto.id, ativo=True).first()
        if not ficha or not ficha.rendimento:
            logger.warning(
                'Produto "%s" (id=%s) sob_encomenda sem ficha técnica ativa/rendimento — estoque não debitado.',
                produto.nome, produto.id,
            )
            return
        for item in ficha.itens.select_related('materia_prima'):
            consumo = item.quantidade * (Decimal(quantidade) / ficha.rendimento)
            MovimentoEstoque.registrar(
                materia_prima=item.materia_prima, tipo_movimento='saida_venda',
                quantidade=consumo, origem_tipo=origem_tipo, origem_id=origem_id,
                custo_unitario_snapshot=item.materia_prima.custo_unitario, criado_por=criado_por,
            )
        return

    # revenda ou fabricado+estoque: débito direto no saldo do próprio produto
    MovimentoEstoque.registrar(
        produto=produto, tipo_movimento='saida_venda', quantidade=quantidade,
        origem_tipo=origem_tipo, origem_id=origem_id, criado_por=criado_por,
    )


@receiver(post_save, sender='pdv.PedidoPDV')
def on_pedido_pdv_confirmado(sender, instance, **kwargs):
    try:
        if instance.status == 'confirmado':
            _debitar_pedido_pdv(instance)
    except Exception as e:
        logger.warning('Falha ao debitar estoque do PedidoPDV #%s: %s', instance.pk, e)


def _debitar_pedido_pdv(pedido):
    from .models import MovimentoEstoque
    if MovimentoEstoque.objects.filter(origem_tipo='pedido_pdv', origem_id=pedido.id).exists():
        return  # já debitado — idempotência
    for item in pedido.itens.select_related('produto'):
        if item.produto_id:
            _debitar_produto(item.produto, item.quantidade, origem_tipo='pedido_pdv', origem_id=pedido.id)


@receiver(post_save, sender='ifood.PedidoIFood')
def on_pedido_ifood_confirmado(sender, instance, **kwargs):
    try:
        if instance.status == 'CONFIRMED':
            _debitar_pedido_ifood(instance)
    except Exception as e:
        logger.warning('Falha ao debitar estoque do PedidoIFood #%s: %s', instance.pk, e)


def _debitar_pedido_ifood(pedido):
    from .models import MovimentoEstoque
    from pdv.models import Produto

    if MovimentoEstoque.objects.filter(origem_tipo='pedido_ifood', origem_id=pedido.id).exists():
        return  # já debitado — idempotência

    for item in pedido.itens.all():
        produto = (
            Produto.objects.filter(nome__iexact=item.nome).first()
            or Produto.objects.filter(nome__icontains=item.nome).first()
        )
        if not produto:
            logger.warning(
                'Item iFood "%s" (pedido #%s) sem correspondência em Produto — estoque não debitado.',
                item.nome, pedido.id,
            )
            continue
        _debitar_produto(produto, item.quantidade, origem_tipo='pedido_ifood', origem_id=pedido.id)


@receiver(post_save, sender='eventos.Evento')
def on_evento_entregue(sender, instance, **kwargs):
    try:
        if instance.status == 'entregue':
            _debitar_evento(instance)
    except Exception as e:
        logger.warning('Falha ao debitar estoque do Evento #%s: %s', instance.pk, e)


def _debitar_evento(evento):
    from .models import MovimentoEstoque
    if MovimentoEstoque.objects.filter(origem_tipo='evento', origem_id=evento.id).exists():
        return  # já debitado — idempotência
    for item in evento.itens.select_related('produto'):
        if item.produto_id:
            _debitar_produto(item.produto, item.quantidade, origem_tipo='evento', origem_id=evento.id)
