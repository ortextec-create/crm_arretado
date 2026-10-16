"""
Management command: python manage.py verificar_atrasos_ifood
Roda a cada minuto (cron). Enfileira o aviso de atraso no chat do pedido iFood quando
`agora > previsao_entrega + atraso_tolerancia_min`. Só decide e enfileira (via `servico.enfileirar()`,
que garante uma mensagem por gatilho por pedido) — quem envia é a extensão. Ver ATENDIMENTO_IFOOD.md, Fase 3.
"""
import logging
from collections import Counter
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from atendimento.models import ConfiguracaoAtendimento, MensagemChat
from atendimento.servico import enfileirar
from empresas.models import Empresa
from ifood.models import PedidoIFood

logger = logging.getLogger(__name__)

STATUS_ANTES_DESPACHO = ('CONFIRMED', 'PREPARATION_STARTED', 'READY_TO_PICKUP')
STATUS_APOS_DESPACHO = ('DISPATCHED',)


class Command(BaseCommand):
    help = 'Enfileira aviso de atraso no chat dos pedidos iFood que passaram da previsão + tolerância'

    def handle(self, *args, **options):
        agora = timezone.now()
        contagem = Counter()

        for empresa in Empresa.objects.filter(ativo=True):
            cfg = ConfiguracaoAtendimento.get(empresa)
            if not cfg.chat_ativo:
                continue
            limite = agora - timedelta(minutes=cfg.atraso_tolerancia_min)
            janela = agora - timedelta(hours=cfg.janela_maxima_horas)

            base = (
                PedidoIFood.objects
                .filter(empresa=empresa, ifood_criado_em__gte=janela, previsao_entrega__isnull=False,
                        previsao_entrega__lt=limite)
                .exclude(order_type='TAKEOUT')
            )
            for gatilho, status in (
                ('atraso_antes_despacho', STATUS_ANTES_DESPACHO),
                ('atraso_apos_despacho', STATUS_APOS_DESPACHO),
            ):
                ja_enviados = MensagemChat.objects.filter(direcao='saida', gatilho=gatilho).values('pedido_id')
                for pedido in base.filter(status__in=status).exclude(pk__in=ja_enviados):
                    try:
                        minutos = int((agora - pedido.previsao_entrega).total_seconds() // 60)
                        if enfileirar(pedido, gatilho, extra={'minutos_atraso': minutos}):
                            contagem[gatilho] += 1
                    except Exception:
                        logger.exception('atendimento: falha ao checar atraso do pedido #%s', pedido.pk)

        resumo = ', '.join(f'{g}={n}' for g, n in sorted(contagem.items())) or 'nenhum'
        self.stdout.write(self.style.SUCCESS(f'Atrasos enfileirados: {resumo}.'))
