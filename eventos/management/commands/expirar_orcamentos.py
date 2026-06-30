"""
Management command: marca como 'expirado' todo orçamento (rascunho ou enviado)
cuja data de validade já passou.

Uso:
    python manage.py expirar_orcamentos

Cron sugerido (diário às 00:05):
    5 0 * * * /var/www/crm_arretado/venv/bin/python /var/www/crm_arretado/manage.py expirar_orcamentos >> /var/log/arretado/expirar_orcamentos.log 2>&1
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from eventos.models import Orcamento


class Command(BaseCommand):
    help = 'Expira orçamentos com validade vencida'

    def handle(self, *args, **options):
        hoje = timezone.now().date()
        qs   = Orcamento.objects.filter(
            status__in=('rascunho', 'enviado'),
            validade__lt=hoje,
        )
        count = qs.update(status='expirado')
        self.stdout.write(self.style.SUCCESS(f'{count} orçamento(s) expirado(s).'))
