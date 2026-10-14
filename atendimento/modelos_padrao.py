"""
Textos padrão das mensagens automáticas do chat iFood (ver ATENDIMENTO_IFOOD.md).
Genéricos: usam {loja}, nunca o nome de uma empresa.
Formato: gatilho -> (texto, ativo_por_padrao)
"""

MODELOS_PADRAO = {
    'confirmado': (
        'Oi, {primeiro_nome}! Aqui é da {loja} 😊 Seu pedido #{pedido} foi confirmado e já vai pra produção.',
        True,
    ),
    'em_preparo': (
        '{primeiro_nome}, seu pedido #{pedido} já está sendo preparado! 👩‍🍳',
        True,
    ),
    'pronto_retirada': (
        'Seu pedido #{pedido} está pronto para retirada. Te esperamos! 🎉',
        True,
    ),
    'pronto_entrega': (
        'Seu pedido #{pedido} está pronto e aguardando o entregador. 🛵',
        True,
    ),
    'saiu_entrega': (
        'Seu pedido #{pedido} saiu para entrega! Previsão: {previsao}.',
        True,
    ),
    'concluido': (
        'Pedido entregue! Esperamos que goste, {primeiro_nome}. Se puder, avalie a gente no iFood, ajuda demais! 💛',
        True,
    ),
    'cancelado': (
        'Seu pedido #{pedido} foi cancelado. Sentimos muito pelo transtorno.',
        False,
    ),
    'entregador_chegou': (
        'O entregador já chegou na loja para buscar seu pedido #{pedido}!',
        False,
    ),
    'atraso_antes_despacho': (
        '{primeiro_nome}, seu pedido #{pedido} está levando um pouco mais que o previsto '
        '(uns {minutos_atraso} min). Já estamos finalizando, obrigado pela paciência!',
        True,
    ),
    'atraso_apos_despacho': (
        'Seu pedido #{pedido} já está a caminho, mas atrasou cerca de {minutos_atraso} min. '
        'Desculpe! Estamos acompanhando.',
        True,
    ),
}
