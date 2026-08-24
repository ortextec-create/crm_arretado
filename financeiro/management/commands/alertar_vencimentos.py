"""
Management command: python manage.py alertar_vencimentos
Roda diariamente (cron). Avisa a equipe interna (telefones cadastrados em
TelefoneAlertaFinanceiro, compartilhados entre empresas) via WhatsApp sobre
ContaPagar pendente/parcial vencendo em até alerta_antecedencia_dias dias ou
já em atraso — janela e repetição (alerta_repeticao_dias) são lidas da
ConfiguracaoFinanceira **de cada empresa** (Fase 4 do multi-empresa,
MULTIEMPRESA.md), já que passam a poder divergir entre matriz e MANGAIO.
Repetição controlada por AlertaFinanceiroEnviado (mesma mecânica de
alertar_eventos / alertar_estoque_baixo). Com 2+ empresas ativas alimentando
os mesmos telefones, a mensagem ganha o prefixo "[{empresa.nome}]" — sem
isso, o alerta é adivinhação sobre qual CNPJ está vencendo.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from empresas.models import Empresa
from financeiro.models import AlertaFinanceiroEnviado, ConfiguracaoFinanceira, ContaPagar, TelefoneAlertaFinanceiro
from notificacoes.servico import notificar


class Command(BaseCommand):
    help = 'Alerta a equipe (WhatsApp) sobre contas a pagar vencendo ou em atraso'

    def handle(self, *args, **options):
        hoje = timezone.localdate()

        telefones = list(
            TelefoneAlertaFinanceiro.objects.filter(ativo=True).values_list('numero', flat=True)
        )
        if not telefones:
            self.stdout.write('Nenhum telefone de alerta cadastrado/ativo — nada a fazer.')
            return

        total_enviados = 0
        for empresa in Empresa.objects.filter(ativo=True):
            cfg = ConfiguracaoFinanceira.get(empresa)
            limite = hoje + timedelta(days=cfg.alerta_antecedencia_dias)
            qs = ContaPagar.objects.filter(
                empresa=empresa, status__in=['pendente', 'parcial'], data_vencimento__lte=limite,
            )

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
                    f'⚠️ [{empresa.nome}] Conta a pagar — {conta.numero} '
                    f'({conta.descricao or (conta.fornecedor.nome if conta.fornecedor else "sem descrição")})\n'
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
                    self.stdout.write(f'  ✓ [{empresa.nome}] {conta.numero} — {situacao}')
                else:
                    self.stderr.write(f'  ✗ [{empresa.nome}] {conta.numero}: falha no envio')

        self.stdout.write(self.style.SUCCESS(f'Concluído: {total_enviados} alerta(s) enviado(s).'))

    def _deve_enviar(self, conta_pagar, repetir_dias):
        ultimo = conta_pagar.alertas_enviados.order_by('-enviado_em').first()
        if not ultimo:
            return True
        return (timezone.now() - ultimo.enviado_em).days >= repetir_dias
