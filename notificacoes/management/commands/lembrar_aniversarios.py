"""
Management command: python manage.py lembrar_aniversarios
Roda diariamente (cron). Usa template e toggle da ConfiguracaoWhatsApp.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from clientes.models import Cliente
from notificacoes.models import ConfiguracaoWhatsApp
from notificacoes.servico import notificar


class Command(BaseCommand):
    help = 'Envia mensagem de parabéns para clientes aniversariantes de hoje'

    def handle(self, *args, **options):
        cfg = ConfiguracaoWhatsApp.get()

        if not cfg.aniversario_ativo:
            self.stdout.write('Notificações de aniversário desativadas na configuração.')
            return

        hoje = timezone.localdate()
        aniversariantes = Cliente.objects.filter(
            status='ativo',
            data_nascimento__month=hoje.month,
            data_nascimento__day=hoje.day,
        ).exclude(telefone_principal='')

        if not aniversariantes.exists():
            self.stdout.write('Nenhum aniversariante hoje.')
            return

        enviados = falhas = 0

        for cliente in aniversariantes:
            mensagem = cfg.mensagem_aniversario.format(nome=cliente.nome.split()[0])
            ok = notificar(
                telefone=cliente.telefone_principal,
                mensagem=mensagem,
                cliente=cliente,
                tipo='aniversario',
            )
            if ok:
                enviados += 1
                self.stdout.write(f'  ✓ {cliente.nome} ({cliente.telefone_principal})')
            else:
                falhas += 1
                self.stderr.write(f'  ✗ {cliente.nome}: falha no envio')

        self.stdout.write(self.style.SUCCESS(
            f'Concluído: {enviados} enviados, {falhas} falhas.'
        ))
