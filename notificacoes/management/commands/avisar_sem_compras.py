"""
Management command: python manage.py avisar_sem_compras
Roda diariamente (cron). Usa dias, template e toggle da ConfiguracaoWhatsApp.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from clientes.models import Cliente
from pedidos.models import PedidoUnificado
from notificacoes.models import ConfiguracaoWhatsApp, HistoricoMensagem
from notificacoes.servico import notificar


class Command(BaseCommand):
    help = 'Avisa clientes sem compras há X dias (configurável via painel)'

    def handle(self, *args, **options):
        cfg = ConfiguracaoWhatsApp.get()

        if not cfg.reengajamento_ativo:
            self.stdout.write('Notificações de reengajamento desativadas na configuração.')
            return

        dias      = cfg.dias_sem_compra
        hoje      = timezone.now()
        corte     = hoje - timedelta(days=dias)
        anti_spam = hoje - timedelta(days=7)

        clientes_com_pedido = (
            PedidoUnificado.objects
            .filter(cliente__isnull=False)
            .values_list('cliente_id', flat=True)
            .distinct()
        )
        compraram_recente = (
            PedidoUnificado.objects
            .filter(cliente__isnull=False, pedido_em__gte=corte)
            .values_list('cliente_id', flat=True)
            .distinct()
        )
        ja_avisados = (
            HistoricoMensagem.objects
            .filter(tipo='reengajamento', status='enviado', enviado_em__gte=anti_spam)
            .exclude(cliente__isnull=True)
            .values_list('cliente_id', flat=True)
            .distinct()
        )

        candidatos = (
            Cliente.objects
            .filter(status='ativo', id__in=clientes_com_pedido)
            .exclude(id__in=compraram_recente)
            .exclude(id__in=ja_avisados)
            .exclude(telefone_principal='')
        )

        total = candidatos.count()
        if total == 0:
            self.stdout.write(f'Nenhum cliente sem compras há {dias} dias.')
            return

        self.stdout.write(f'{total} cliente(s) sem compras há {dias}+ dias.')
        enviados = falhas = 0

        for cliente in candidatos:
            ultimo = (
                PedidoUnificado.objects
                .filter(cliente=cliente)
                .order_by('-pedido_em')
                .values_list('pedido_em', flat=True)
                .first()
            )
            dias_ausente = (hoje - ultimo).days if ultimo else '?'
            mensagem = cfg.mensagem_reengajamento.format(nome=cliente.nome.split()[0])

            ok = notificar(
                telefone=cliente.telefone_principal,
                mensagem=mensagem,
                cliente=cliente,
                tipo='reengajamento',
            )
            if ok:
                enviados += 1
                self.stdout.write(f'  ✓ {cliente.nome} — {dias_ausente} dias sem compra')
            else:
                falhas += 1
                self.stderr.write(f'  ✗ {cliente.nome}: falha no envio')

        self.stdout.write(self.style.SUCCESS(
            f'Concluído: {enviados} enviados, {falhas} falhas.'
        ))
