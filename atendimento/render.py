"""Renderização de variáveis das mensagens do chat — função pura, nunca levanta exceção."""
import re

from django.utils import timezone

_VAR = re.compile(r'\{(\w+)\}')


def _primeiro_nome(nome):
    partes = (nome or '').strip().split()
    return partes[0].capitalize() if partes else 'cliente'


def _itens_resumo(pedido):
    itens = list(pedido.itens.all())
    if not itens:
        return ''
    texto = ', '.join(f'{i.quantidade}x {i.nome}' for i in itens[:2])
    if len(itens) > 2:
        texto += f' e mais {len(itens) - 2}'
    return texto


def _previsao(pedido):
    dt = getattr(pedido, 'previsao_entrega', None)
    if not dt:
        return 'em breve'
    return timezone.localtime(dt).strftime('%H:%M')


def valores(pedido, extra=None):
    extra = extra or {}
    return {
        'loja': pedido.empresa.nome,
        'nome': (pedido.cliente_nome or '').strip() or 'cliente',
        'primeiro_nome': _primeiro_nome(pedido.cliente_nome),
        'pedido': pedido.display_id or '',
        'itens_resumo': _itens_resumo(pedido),
        'previsao': _previsao(pedido),
        'minutos_atraso': str(extra.get('minutos_atraso', '')),
    }


def renderizar(texto, pedido, extra=None):
    """Passada única: valor que contenha '{x}' nunca é re-substituído; chave desconhecida fica como está."""
    vals = valores(pedido, extra)
    return _VAR.sub(lambda m: vals.get(m.group(1), m.group(0)), texto or '')
