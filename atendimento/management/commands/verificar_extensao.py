"""
Management command: python manage.py verificar_extensao
Roda a cada 5 minutos (cron). Se a extensão do Gestor de Pedidos parou de mandar heartbeat há mais de
LIMITE_OFFLINE_MIN minutos e há trabalho para ela (mensagem na fila ou pedido iFood em andamento, com
`chat_ativo` ligado), avisa a equipe via WhatsApp (TelefoneAlertaAtendimento). Avisa uma vez por queda e
repete a cada REPETIR_MIN enquanto continuar fora; avisa também quando volta.

Segundo sinal, independente do heartbeat ("fila parada"): a extensão pode estar online e mesmo assim não
entregar (iFood deslogado, aba errada, seletores quebrados). Dispara por empresa com `chat_ativo` quando há
mensagem `pendente` esperando há mais de LIMITE_FILA_MIN minutos (a mais antiga, não a contagem — rajada de
pedidos é normal) ou ≥ MIN_FALHAS falhas de envio sem nenhum envio na janela. `modo_seguro` não conta (é
proposital). Empresa cuja extensão já está offline não recebe este aviso (já explicado pelo outro). Ver
ATENDIMENTO_IFOOD.md.

Autocorreção: se a fila está parada e a extensão (online) reporta `aba_ok=False` (página do Gestor travada ou
em loop), reinicia só o Chromium do container (`supervisorctl restart chromium`), no máximo uma vez por
REPETIR_MIN por empresa (`ultimo_reinicio_chromium_em`) — se continuar parada depois disso, só alerta (provável
iFood deslogado, que reiniciar não resolve).
"""
import logging
import subprocess
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from atendimento.models import ConfiguracaoAtendimento, MensagemChat, TelefoneAlertaAtendimento, TokenExtensao
from empresas.models import Empresa
from ifood.models import PedidoIFood
from notificacoes.servico import notificar

logger = logging.getLogger(__name__)

LIMITE_OFFLINE_MIN = 10
REPETIR_MIN = 120
JANELA_PEDIDO_HORAS = 6
LIMITE_FILA_MIN = 10        # pendente mais antiga além disso = fila parada
JANELA_FILA_HORAS = 3       # ignora pendente velha de queda antiga (ninguém varre pendente com extensão offline)
CONTAINER_BOT = 'gestor-bot'
MIN_FALHAS = 3
JANELA_FALHAS_MIN = 30
ERROS_IGNORADOS = ('modo_seguro',)
STATUS_PEDIDO_EM_ANDAMENTO = ('CONFIRMED', 'PREPARATION_STARTED', 'READY_TO_PICKUP', 'DISPATCHED')


class Command(BaseCommand):
    help = 'Alerta a equipe via WhatsApp quando a extensão do chat iFood está offline com trabalho pendente'

    def handle(self, *args, **options):
        agora = timezone.now()
        limite = agora - timedelta(minutes=LIMITE_OFFLINE_MIN)
        telefones = list(TelefoneAlertaAtendimento.objects.filter(ativo=True).values_list('numero', flat=True))

        empresas_offline = set()
        for token in TokenExtensao.objects.filter(ativo=True, ultimo_heartbeat__isnull=False):
            if token.ultimo_heartbeat < limite:
                empresas_offline.update(token.empresas.values_list('id', flat=True))
            if token.ultimo_heartbeat >= limite:
                if token.alertado_offline_em:
                    self._avisar(telefones, f'✅ Extensão do chat iFood voltou a responder ("{token.nome}") — '
                                            f'{timezone.localtime(agora).strftime("%d/%m/%Y %H:%M")}')
                    token.alertado_offline_em = None
                    token.save(update_fields=['alertado_offline_em'])
                continue

            empresas = [e for e in token.empresas.filter(ativo=True) if ConfiguracaoAtendimento.get(e).chat_ativo]
            if not empresas or not self._ha_trabalho(empresas):
                continue
            if token.alertado_offline_em and token.alertado_offline_em > agora - timedelta(minutes=REPETIR_MIN):
                continue

            minutos = int((agora - token.ultimo_heartbeat).total_seconds() // 60)
            msg = (
                f'🚨 Extensão do chat iFood OFFLINE ("{token.nome}") — sem sinal há {minutos} min '
                f'(último: {timezone.localtime(token.ultimo_heartbeat).strftime("%d/%m %H:%M")}). '
                'Mensagens automáticas aos clientes não estão saindo. '
                'Verifique o gestor-bot (Chromium/login no Gestor de Pedidos).'
            )
            self.stderr.write(self.style.ERROR(msg))
            logger.error('Extensão do chat iFood offline: token=%s, %s min sem heartbeat', token.nome, minutos)
            self._avisar(telefones, msg)
            token.alertado_offline_em = agora
            token.save(update_fields=['alertado_offline_em'])

        self._verificar_fila(agora, telefones, empresas_offline)

    def _verificar_fila(self, agora, telefones, empresas_offline):
        for empresa in Empresa.objects.filter(ativo=True):
            cfg = ConfiguracaoAtendimento.get(empresa)
            if not cfg.chat_ativo or empresa.id in empresas_offline:
                continue
            problema = self._diagnosticar_fila(empresa, agora)
            reiniciou = False
            if problema is not None:
                reiniciou = self._tentar_reiniciar_chromium(empresa, cfg, agora, problema)
            if problema is None:
                if cfg.alertado_fila_parada_em:
                    self._avisar(telefones, f'✅ Fila do chat iFood voltou a andar ({empresa.nome}) — '
                                            f'{timezone.localtime(agora).strftime("%d/%m/%Y %H:%M")}')
                    cfg.alertado_fila_parada_em = None
                    cfg.save(update_fields=['alertado_fila_parada_em'])
                continue
            if cfg.alertado_fila_parada_em and cfg.alertado_fila_parada_em > agora - timedelta(minutes=REPETIR_MIN):
                continue
            acao = ('O Chromium do gestor-bot foi reiniciado automaticamente; se não normalizar, verifique o login '
                    'no Gestor de Pedidos (noVNC do gestor-bot).' if reiniciou else
                    'A extensão está respondendo, mas as mensagens não estão saindo. '
                    'Verifique o login no Gestor de Pedidos e a aba da extensão (noVNC do gestor-bot).')
            msg = f'🚨 Fila do chat iFood PARADA ({empresa.nome}): {problema}. {acao}'
            self.stderr.write(self.style.ERROR(msg))
            logger.error('Fila do chat iFood parada: empresa=%s, %s', empresa.nome, problema)
            self._avisar(telefones, msg)
            cfg.alertado_fila_parada_em = agora
            cfg.save(update_fields=['alertado_fila_parada_em'])

    def _tentar_reiniciar_chromium(self, empresa, cfg, agora, problema):
        """Reinicia o Chromium do gestor-bot quando a aba da extensão está quebrada. True se reiniciou."""
        if cfg.ultimo_reinicio_chromium_em and cfg.ultimo_reinicio_chromium_em > agora - timedelta(minutes=REPETIR_MIN):
            return False
        limite = agora - timedelta(minutes=LIMITE_OFFLINE_MIN)
        aba_quebrada = any(
            t.ultimo_heartbeat >= limite and t.ultimo_diagnostico.get('aba_ok') is False
            for t in TokenExtensao.objects.filter(ativo=True, empresas=empresa, ultimo_heartbeat__isnull=False)
        )
        if not aba_quebrada:
            return False
        try:
            r = subprocess.run(['docker', 'exec', CONTAINER_BOT, 'supervisorctl', 'restart', 'chromium'],
                               capture_output=True, text=True, timeout=90)
        except Exception:
            logger.exception('Falha ao reiniciar o Chromium do %s', CONTAINER_BOT)
            return False
        if r.returncode != 0:
            logger.error('Reinício do Chromium falhou: %s', (r.stderr or r.stdout).strip()[:200])
            return False
        logger.warning('Chromium do %s reiniciado automaticamente (empresa=%s, %s)', CONTAINER_BOT, empresa.nome, problema)
        cfg.ultimo_reinicio_chromium_em = agora
        cfg.save(update_fields=['ultimo_reinicio_chromium_em'])
        return True

    @staticmethod
    def _diagnosticar_fila(empresa, agora):
        """Texto do problema, ou None se a fila está saudável."""
        saida = MensagemChat.objects.filter(empresa=empresa, direcao='saida')
        pendentes = saida.filter(status='pendente', criado_em__gte=agora - timedelta(hours=JANELA_FILA_HORAS)).filter(
            Q(proxima_tentativa_em__isnull=True) | Q(proxima_tentativa_em__lte=agora),
        )
        antiga = pendentes.order_by('criado_em').first()
        if antiga and antiga.criado_em < agora - timedelta(minutes=LIMITE_FILA_MIN):
            minutos = int((agora - antiga.criado_em).total_seconds() // 60)
            return f'{pendentes.count()} mensagem(ns) pendente(s), a mais antiga há {minutos} min'

        desde = agora - timedelta(minutes=JANELA_FALHAS_MIN)
        recentes = saida.filter(criado_em__gte=desde)
        falhas = recentes.filter(status__in=('falha', 'incerta')).exclude(erro__in=ERROS_IGNORADOS).count()
        if falhas >= MIN_FALHAS and not recentes.filter(status='enviada').exists():
            return f'{falhas} falha(s) de envio nos últimos {JANELA_FALHAS_MIN} min e nenhuma mensagem enviada'
        return None

    @staticmethod
    def _ha_trabalho(empresas):
        if MensagemChat.objects.filter(
            empresa__in=empresas, direcao='saida', status__in=('pendente', 'enviando'),
        ).exists():
            return True
        return PedidoIFood.objects.filter(
            empresa__in=empresas, status__in=STATUS_PEDIDO_EM_ANDAMENTO,
            criado_em__gte=timezone.now() - timedelta(hours=JANELA_PEDIDO_HORAS),  # ignora pedido velho parado
        ).exists()

    def _avisar(self, telefones, mensagem):
        if not telefones:
            logger.warning('Alerta de extensão sem nenhum TelefoneAlertaAtendimento ativo cadastrado.')
            return
        for fone in telefones:
            notificar(telefone=fone, mensagem=mensagem, tipo='alerta_extensao')
