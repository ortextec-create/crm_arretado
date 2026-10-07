"""
Motor da régua de cobrança — funções puras (recebem `hoje` como argumento,
nunca chamam timezone.localdate() internamente, pra facilitar teste). Não
fazem I/O (sem notificar(), sem gravar EnvioCobranca) — quem decide envia e
grava é o management command (enviar_cobrancas) e as actions síncronas de
ligação/pausa.
"""
from collections import namedtuple
from datetime import timedelta

from django.db.models import F

from eventos.models import Evento
from .models import EtapaRegua, PausaCobranca, EnvioCobranca

STATUS_ELEGIVEIS = ('confirmado', 'em_producao', 'pronto', 'entregue')


def tipo_da_etapa(dias: int, limite: int) -> str:
    return 'lembrete' if dias <= limite else 'cobranca'


def rotulos(etapas_ativas, limite: int) -> dict:
    """{etapa_id: 'L1'|'L2'|...|'C1'|...} — ordem por dias dentro de cada tipo."""
    lembretes = sorted((e for e in etapas_ativas if tipo_da_etapa(e.dias, limite) == 'lembrete'), key=lambda e: e.dias)
    cobrancas = sorted((e for e in etapas_ativas if tipo_da_etapa(e.dias, limite) == 'cobranca'), key=lambda e: e.dias)
    out = {}
    for i, e in enumerate(lembretes, start=1):
        out[e.id] = f'L{i}'
    for i, e in enumerate(cobrancas, start=1):
        out[e.id] = f'C{i}'
    return out


def data_da_etapa(evento, etapa):
    return evento.data_evento + timedelta(days=etapa.dias)


def pausa_vigente(evento, hoje):
    return (
        evento.pausas_cobranca
        .filter(encerrada_em__isnull=True, pausado_ate__gte=hoje)
        .order_by('-criado_em')
        .first()
    )


def pausa_recem_vencida(evento, hoje):
    """A pausa mais recente ainda não encerrada manualmente, com prazo já
    vencido (pausado_ate < hoje) e sem pausa mais nova vigente/futura."""
    return (
        evento.pausas_cobranca
        .filter(encerrada_em__isnull=True, pausado_ate__lt=hoje)
        .order_by('-criado_em')
        .first()
    )


def eventos_elegiveis():
    return (
        Evento.objects
        .filter(status__in=STATUS_ELEGIVEIS)
        .annotate(saldo=F('valor_total') - F('sinal_pago'))
        .filter(saldo__gt=0)
        .select_related('cliente')
    )


Decisao = namedtuple('Decisao', ['enviar', 'puladas'])
# enviar: dict com tipo/etapa/pausa/ligacao ou None (nada a enviar)
# puladas: lista de dicts {etapa, motivo_pulada, pausa?}


def decidir_do_dia(evento, etapas_ativas, cfg, hoje):
    if not evento.telefone_display:
        return Decisao(enviar=None, puladas=[])

    pausa = pausa_vigente(evento, hoje)
    if pausa:
        puladas = []
        pendentes = [
            e for e in etapas_ativas
            if cfg.ativo_desde and cfg.ativo_desde <= data_da_etapa(evento, e) <= hoje
            and not EnvioCobranca.objects.filter(
                evento=evento, etapa=e, data_evento_referencia=evento.data_evento,
                status__in=['enviado', 'pulada'],
            ).exists()
        ]
        for e in pendentes:
            puladas.append({'etapa': e, 'motivo_pulada': 'pausa', 'pausa': pausa})

        if pausa.pausado_ate == hoje and cfg.msg_prazo_hoje_ativo:
            ja_enviado = EnvioCobranca.objects.filter(
                pausa=pausa, tipo='prazo_hoje', status='enviado',
            ).exists()
            if not ja_enviado:
                return Decisao(enviar={'tipo': 'prazo_hoje', 'pausa': pausa}, puladas=puladas)

        return Decisao(enviar=None, puladas=puladas)

    pausa_vencida = pausa_recem_vencida(evento, hoje)
    if pausa_vencida and cfg.ativo_desde and pausa_vencida.pausado_ate >= cfg.ativo_desde:
        ja_enviado = EnvioCobranca.objects.filter(
            pausa=pausa_vencida, tipo='prazo_vencido', status='enviado',
        ).exists()
        if not ja_enviado:
            if cfg.msg_prazo_vencido_ativo:
                puladas = []
                pendentes = [
                    e for e in etapas_ativas
                    if cfg.ativo_desde <= data_da_etapa(evento, e) <= hoje
                    and not EnvioCobranca.objects.filter(
                        evento=evento, etapa=e, data_evento_referencia=evento.data_evento,
                        status__in=['enviado', 'pulada'],
                    ).exists()
                ]
                for e in pendentes:
                    puladas.append({'etapa': e, 'motivo_pulada': 'mesmo_dia', 'pausa': None})
                return Decisao(enviar={'tipo': 'prazo_vencido', 'pausa': pausa_vencida}, puladas=puladas)
            # desativada — segue pro passo 4 normalmente (não marca como "enviado")

    pendentes = sorted(
        (
            e for e in etapas_ativas
            if cfg.ativo_desde and cfg.ativo_desde <= data_da_etapa(evento, e) <= hoje
            and not EnvioCobranca.objects.filter(
                evento=evento, etapa=e, data_evento_referencia=evento.data_evento,
                status__in=['enviado', 'pulada'],
            ).exists()
        ),
        key=lambda e: e.dias,
    )
    if not pendentes:
        return Decisao(enviar=None, puladas=[])

    escolhida = pendentes[-1]
    puladas = [{'etapa': e, 'motivo_pulada': 'atraso', 'pausa': None} for e in pendentes[:-1]]

    maior_dias_ativa = max(e.dias for e in etapas_ativas)
    e_ultima = escolhida.dias == maior_dias_ativa

    return Decisao(
        enviar={
            'tipo': tipo_da_etapa(escolhida.dias, cfg.limite_lembrete),
            'etapa': escolhida,
            'ultima_etapa': e_ultima,
        },
        puladas=puladas,
    )
