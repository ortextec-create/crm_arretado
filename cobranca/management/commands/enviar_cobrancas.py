"""
Management command: python manage.py enviar_cobrancas [--dry-run] [--evento EV-123] [--data AAAA-MM-DD]

Roda diariamente (cron, 09:30). Executa a régua de cobrança de Eventos
(ver COBRANCA.md) — no máximo 1 WhatsApp por evento por dia.
"""
import logging
import time
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from notificacoes.servico import notificar
from notificacoes.models import HistoricoMensagem

from cobranca.models import ConfiguracaoCobranca, EtapaRegua, EnvioCobranca
from cobranca.mensagens import render, montar_contexto
from cobranca.regua import (
    eventos_elegiveis, decidir_do_dia, rotulos, tipo_da_etapa,
)

logger = logging.getLogger(__name__)

_MAPA_HISTORICO = {
    'lembrete': 'lembrete_pagamento',
    'prazo_hoje': 'lembrete_pagamento',
    'cobranca': 'cobranca',
    'prazo_vencido': 'cobranca',
    'ligacao_nao_atendida': 'cobranca',
}


class Command(BaseCommand):
    help = 'Executa a régua de cobrança de eventos (WhatsApp ao cliente)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Não envia nem grava nada, só imprime a decisão')
        parser.add_argument('--evento', type=str, default=None, help='Restringe a um único evento (numero)')
        parser.add_argument('--data', type=str, default=None, help='Simula outra data (AAAA-MM-DD) — só com --dry-run')

    def handle(self, *args, **options):
        cfg = ConfiguracaoCobranca.get()
        if not cfg.ativo:
            self.stdout.write('Cobrança automática desligada — nada a fazer.')
            return

        dry_run = options['dry_run']

        if options['data']:
            if not dry_run:
                self.stderr.write(self.style.ERROR('--data só pode ser usado junto com --dry-run.'))
                return
            hoje = date.fromisoformat(options['data'])
        else:
            hoje = timezone.localdate()

        if hoje.weekday() not in (cfg.dias_semana_envio or []):
            self.stdout.write(f'{hoje:%d/%m/%Y} não é dia de envio configurado — nada a fazer.')
            return

        etapas_ativas = list(EtapaRegua.objects.filter(ativo=True))
        if not etapas_ativas:
            self.stdout.write('Nenhuma etapa ativa cadastrada — nada a fazer.')
            return

        rotulos_map = rotulos(etapas_ativas, cfg.limite_lembrete)
        maior_dias_ativa = max(e.dias for e in etapas_ativas)

        qs = eventos_elegiveis()
        if options['evento']:
            qs = qs.filter(numero=options['evento'])

        telefones_equipe = None  # resolvido só se precisar (evita query sem necessidade)

        enviados = falhas = pulados = 0

        for evento in qs:
            try:
                decisao = decidir_do_dia(evento, etapas_ativas, cfg, hoje)

                if dry_run:
                    if decisao.enviar:
                        tipo = decisao.enviar['tipo']
                        self.stdout.write(f'  {evento.numero}: enviaria "{tipo}"')
                    for p in decisao.puladas:
                        self.stdout.write(
                            f'  {evento.numero}: pularia etapa D{p["etapa"].dias:+d} ({p["motivo_pulada"]})'
                        )
                    if not decisao.enviar and not decisao.puladas:
                        self.stdout.write(f'  {evento.numero}: nada a fazer')
                    continue

                for p in decisao.puladas:
                    etapa = p['etapa']
                    EnvioCobranca.objects.create(
                        evento=evento,
                        tipo=tipo_da_etapa(etapa.dias, cfg.limite_lembrete),
                        etapa=etapa,
                        dias_etapa=etapa.dias,
                        rotulo_etapa=rotulos_map.get(etapa.id, ''),
                        data_evento_referencia=evento.data_evento,
                        pausa=p.get('pausa'),
                        status='pulada',
                        motivo_pulada=p['motivo_pulada'],
                    )
                    pulados += 1

                if not decisao.enviar:
                    continue

                # Saldo no momento do envio — cobre pagamento lançado entre a
                # montagem do queryset e o disparo (ver COBRANCA.md).
                evento.refresh_from_db()
                saldo = max(evento.valor_total - evento.sinal_pago, 0)
                if saldo <= 0:
                    continue

                info = decisao.enviar
                tipo = info['tipo']

                if tipo in ('prazo_hoje', 'prazo_vencido'):
                    pausa = info['pausa']
                    etapa = None
                    texto_base = cfg.msg_prazo_hoje if tipo == 'prazo_hoje' else cfg.msg_prazo_vencido
                    ctx = montar_contexto(evento, cfg, hoje, pausa=pausa)
                else:
                    etapa = info['etapa']
                    pausa = None
                    texto_base = etapa.mensagem
                    ctx = montar_contexto(evento, cfg, hoje)

                mensagem = render(texto_base, ctx)
                telefone = evento.telefone_display

                inicio_envio = timezone.now()
                tipo_historico = _MAPA_HISTORICO[tipo]
                ok = notificar(telefone, mensagem, cliente=evento.cliente, tipo=tipo_historico)

                historico = (
                    HistoricoMensagem.objects
                    .filter(telefone=telefone, tipo=tipo_historico, enviado_em__gte=inicio_envio)
                    .order_by('-enviado_em')
                    .first()
                )

                EnvioCobranca.objects.create(
                    evento=evento,
                    tipo=tipo,
                    etapa=etapa,
                    dias_etapa=etapa.dias if etapa else None,
                    rotulo_etapa=rotulos_map.get(etapa.id, '') if etapa else '',
                    data_evento_referencia=evento.data_evento,
                    pausa=pausa,
                    status='enviado' if ok else 'falha',
                    telefone=telefone,
                    mensagem_renderizada=mensagem if ok else '',
                    saldo_no_envio=saldo,
                    historico=historico,
                )

                if ok:
                    enviados += 1
                    self.stdout.write(f'  ✓ {evento.numero}: {tipo}')

                    if etapa and info.get('ultima_etapa') and cfg.notificar_equipe_ultima_etapa:
                        if telefones_equipe is None:
                            from eventos.models import TelefoneAlertaEvento
                            telefones_equipe = list(
                                TelefoneAlertaEvento.objects.filter(ativo=True).values_list('numero', flat=True)
                            )
                        msg_equipe = (
                            f'Régua de cobrança concluída sem pagamento — {evento.numero} '
                            f'({evento.nome_cliente_display}) · saldo R$ {saldo:.2f}'
                        )
                        for fone_equipe in telefones_equipe:
                            notificar(telefone=fone_equipe, mensagem=msg_equipe, tipo='alerta_pagamento')
                else:
                    falhas += 1
                    self.stderr.write(f'  ✗ {evento.numero}: falha ao enviar ({tipo})')

                time.sleep(cfg.intervalo_envio_segundos)

            except Exception:
                logger.exception('enviar_cobrancas: erro ao processar evento %s', evento.numero)

        if dry_run:
            self.stdout.write(self.style.SUCCESS('Dry-run concluído — nada foi enviado ou gravado.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Concluído: {enviados} enviado(s) · {falhas} falha(s) · {pulados} pulado(s).'
            ))
