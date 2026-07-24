"""
Management command: python manage.py alertar_vencimentos
Roda diariamente (cron). Avisa a equipe interna (telefones cadastrados em
TelefoneAlertaFinanceiro) via WhatsApp sobre ContaPagar pendente/parcial
vencendo em até alerta_antecedencia_dias dias ou já em atraso. Repetição
controlada por alerta_repeticao_dias, via AlertaFinanceiroEnviado (mesma
mecânica de alertar_eventos / alertar_estoque_baixo).
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from financeiro.models import AlertaFinanceiroEnviado, ConfiguracaoFinanceira, ContaPagar, TelefoneAlertaFinanceiro
from notificacoes.servico import notificar


class Command(BaseCommand):
    help = 'Alerta a equipe (WhatsApp) sobre contas a pagar vencendo ou em atraso'

    def handle(self, *args, **options):
        cfg = ConfiguracaoFinanceira.get()
        hoje = timezone.localdate()

        telefones = list(
            TelefoneAlertaFinanceiro.objects.filter(ativo=True).values_list('numero', flat=True)
        )
        if not telefones:
            self.stdout.write('Nenhum telefone de alerta cadastrado/ativo — nada a fazer.')
            return

        limite = hoje + timedelta(days=cfg.alerta_antecedencia_dias)
        qs = ContaPagar.objects.filter(status__in=['pendente', 'parcial'], data_vencimento__lte=limite)

        total_enviados = 0
        for conta in qs:
            if not self._deve_enviar(conta, cfg.alerta_repeticao_dias):
                continue

            dias = (conta.data_vencimento - hoje).days
            if dias < 0:
                situacao = f'em atraso há {-dias} dia(s)'
            elif dias == 0:
                situacao = 'vence hoje'
            else:
                situacao = f'vence em {dias} dia(s)'

            saldo = conta.valor - conta.valor_pago
            mensagem = (
                f'⚠️ Conta a pagar — {conta.numero} ({conta.descricao or (conta.fornecedor.nome if conta.fornecedor else "sem descrição")})\n'
                f'Vencimento: {conta.data_vencimento.strftime("%d/%m/%Y")} — {situacao}\n'
                f'Saldo: R$ {saldo:.2f}'
            )

            enviado_algum = False
            for fone in telefones:
                if notificar(telefone=fone, mensagem=mensagem, tipo='alerta_vencimento'):
                    enviado_algum = True

            if enviado_algum:
                AlertaFinanceiroEnviado.objects.create(conta_pagar=conta)
                total_enviados += 1
                self.stdout.write(f'  ✓ {conta.numero} — {situacao}')
            else:
                self.stderr.write(f'  ✗ {conta.numero}: falha no envio')

        self.stdout.write(self.style.SUCCESS(f'Concluído: {total_enviados} alerta(s) enviado(s).'))

    def _deve_enviar(self, conta_pagar, repetir_dias):
        ultimo = conta_pagar.alertas_enviados.order_by('-enviado_em').first()
        if not ultimo:
            return True
        return (timezone.now() - ultimo.enviado_em).days >= repetir_dias
