"""
Management command: python manage.py verificar_extensao
Roda a cada 5 minutos (cron). Se a extensão do Gestor de Pedidos parou de mandar heartbeat há mais de
LIMITE_OFFLINE_MIN minutos e há trabalho para ela (mensagem na fila ou pedido iFood em andamento, com
`chat_ativo` ligado), avisa a equipe via WhatsApp (TelefoneAlertaAtendimento). Avisa uma vez por queda e
repete a cada REPETIR_MIN enquanto continuar fora; avisa também quando volta. Ver ATENDIMENTO_IFOOD.md.
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from atendimento.models import ConfiguracaoAtendimento, MensagemChat, TelefoneAlertaAtendimento, TokenExtensao
from ifood.models import PedidoIFood
from notificacoes.servico import notificar

logger = logging.getLogger(__name__)

LIMITE_OFFLINE_MIN = 10
REPETIR_MIN = 120
JANELA_PEDIDO_HORAS = 6
STATUS_PEDIDO_EM_ANDAMENTO = ('CONFIRMED', 'PREPARATION_STARTED', 'READY_TO_PICKUP', 'DISPATCHED')


class Command(BaseCommand):
    help = 'Alerta a equipe via WhatsApp quando a extensão do chat iFood está offline com trabalho pendente'

    def handle(self, *args, **options):
        agora = timezone.now()
        limite = agora - timedelta(minutes=LIMITE_OFFLINE_MIN)
        telefones = list(TelefoneAlertaAtendimento.objects.filter(ativo=True).values_list('numero', flat=True))

        for token in TokenExtensao.objects.filter(ativo=True, ultimo_heartbeat__isnull=False):
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
