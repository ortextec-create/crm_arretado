"""
Management command: python manage.py ifood_polling

Executa o loop de polling do iFood continuamente.
Pode ser rodado via systemd, supervisor ou como processo separado.

Uso:
    python manage.py ifood_polling              # loop contínuo (30s)
    python manage.py ifood_polling --once       # executa uma vez e sai
    python manage.py ifood_polling --interval 15  # intervalo customizado
"""
import time
import signal
import logging

from django.core.management.base import BaseCommand

from ifood.polling_worker import run_polling

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Executa o worker de polling de pedidos do iFood'

    def add_arguments(self, parser):
        parser.add_argument(
            '--once', action='store_true',
            help='Executa apenas um ciclo e encerra',
        )
        parser.add_argument(
            '--interval', type=int, default=30,
            help='Intervalo entre polls em segundos (padrão: 30)',
        )

    def handle(self, *args, **options):
        once     = options['once']
        interval = options['interval']

        self.stdout.write(self.style.SUCCESS(
            f'🍊 Worker iFood iniciado (intervalo={interval}s)'
        ))

        # Graceful shutdown
        self._running = True
        def _stop(sig, frame):
            self._running = False
            self.stdout.write(self.style.WARNING('\nEncerrando worker iFood...'))
        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        while self._running:
            try:
                result = run_polling()
                if result['eventos'] > 0:
                    self.stdout.write(
                        f'[{self._now()}] Polling: '
                        f'{result["eventos"]} eventos, '
                        f'{result["pedidos_novos"]} pedidos novos'
                    )
            except Exception as e:
                logger.error('Erro no ciclo de polling: %s', e, exc_info=True)
                self.stderr.write(f'ERRO: {e}')

            if once:
                break

            # Aguarda próximo ciclo respeitando sinal de parada
            for _ in range(interval):
                if not self._running:
                    break
                time.sleep(1)

        self.stdout.write(self.style.SUCCESS('Worker iFood encerrado.'))

    def _now(self):
        from django.utils import timezone
        return timezone.localtime().strftime('%H:%M:%S')
