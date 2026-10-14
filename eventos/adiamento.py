"""
Regras puras de remarcação/adiamento de Evento (ver ADIAMENTO.md).

Sem efeito colateral: nada aqui grava no banco nem chama timezone — `hoje`
e a config entram sempre por parâmetro, pra manter testável.
"""
import datetime
from decimal import Decimal, ROUND_HALF_UP

CENTAVOS = Decimal('0.01')


def _q(valor):
    return Decimal(valor).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def faixa_multa_pct(antecedencia_dias, producao_iniciada, cfg):
    """Faixa da multa da Cláusula 11ª pela antecedência (data original − data do
    adiamento). Produção iniciada cai sempre na faixa "menos de 7 dias"."""
    if producao_iniciada or antecedencia_dias < 7:
        return cfg.multa_rescisao_abaixo_7_dias_pct
    if antecedencia_dias < 30:
        return cfg.multa_rescisao_abaixo_30_dias_pct
    if antecedencia_dias <= 60:
        return cfg.multa_rescisao_30_60_dias_pct
    return cfg.multa_rescisao_acima_60_dias_pct


def calcular_acerto(valor_pago, valor_contrato, multa_pct, valor_retido_producao, desfecho,
                    valor_multa=None, valor_devolucao=None):
    """Devolve {'multa', 'retido', 'devolucao'} (Decimal, 2 casas).

    acordo_manual não calcula nada: devolve os valores informados.
    """
    valor_pago = Decimal(valor_pago or 0)
    retido = Decimal(valor_retido_producao or 0)

    if desfecho == 'acordo_manual':
        return {
            'multa': _q(valor_multa or 0),
            'retido': _q(retido),
            'devolucao': _q(valor_devolucao or 0),
        }
    if desfecho == 'forca_maior':
        multa = Decimal('0')
    elif desfecho == 'rescisao':
        bruta = Decimal(valor_contrato or 0) * Decimal(multa_pct or 0) / Decimal('100')
        multa = min(_q(bruta), valor_pago)
    else:
        raise ValueError(f'desfecho inválido: {desfecho}')

    devolucao = max(valor_pago - multa - retido, Decimal('0'))
    return {'multa': _q(multa), 'retido': _q(retido), 'devolucao': _q(devolucao)}


def somar_dias_uteis(data, n):
    """Soma n dias úteis (pula sábado e domingo). Feriados fora de escopo."""
    atual = data
    restantes = n
    while restantes > 0:
        atual += datetime.timedelta(days=1)
        if atual.weekday() < 5:
            restantes -= 1
    return atual


def data_referencia_contrato(evento):
    """(data, hora) a comparar com a data atual do Evento: a do último aditivo
    com data nova, senão a do Contrato. None se não há contrato."""
    contrato = next(iter(evento.contratos.all()), None)
    if not contrato:
        return None
    for aditivo in contrato.aditivos.all():  # ordering -criado_em
        if aditivo.data_evento_nova:
            return aditivo.data_evento_nova, aditivo.hora_evento_nova
    return contrato.data_evento, contrato.hora_evento
