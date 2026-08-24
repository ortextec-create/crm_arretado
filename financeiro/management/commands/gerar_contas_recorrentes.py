"""
Management command: python manage.py gerar_contas_recorrentes
Roda diariamente (cron). Para cada DespesaRecorrente ativa (de qualquer
empresa, numa única passada — Fase 4 do multi-empresa, MULTIEMPRESA.md),
materializa uma ContaPagar (origem='recorrente') por vencimento dentro do
horizonte configurado em ConfiguracaoFinanceira.get(despesa.empresa).
horizonte_recorrencia_dias — a ContaPagar gerada herda a empresa do molde.
Idempotente pela UniqueConstraint(recorrente, data_vencimento) — nunca duplica.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from financeiro.models import ConfiguracaoFinanceira, ContaPagar, DespesaRecorrente


class Command(BaseCommand):
    help = 'Gera ContaPagar para os vencimentos de DespesaRecorrente ativas dentro do horizonte configurado'

    def handle(self, *args, **options):
        hoje = timezone.localdate()

        total_criadas = 0
        for despesa in DespesaRecorrente.objects.select_related('empresa').filter(ativo=True):
            cfg = ConfiguracaoFinanceira.get(despesa.empresa)
            limite = hoje + timedelta(days=cfg.horizonte_recorrencia_dias)
            for data_vencimento in despesa.datas_no_periodo(hoje, limite):
                if ContaPagar.objects.filter(recorrente=despesa, data_vencimento=data_vencimento).exists():
                    continue
                conta = ContaPagar.objects.create(
                    numero=ContaPagar.proximo_numero(),
                    empresa=despesa.empresa,
                    fornecedor=despesa.fornecedor,
                    descricao=despesa.descricao,
                    categoria=despesa.categoria,
                    valor=despesa.valor,
                    data_emissao=hoje,
                    data_vencimento=data_vencimento,
                    origem='recorrente',
                    recorrente=despesa,
                )
                total_criadas += 1
                self.stdout.write(f'  ✓ {conta.numero} — {despesa.descricao} ({data_vencimento.strftime("%d/%m/%Y")})')

        self.stdout.write(self.style.SUCCESS(f'Concluído: {total_criadas} conta(s) a pagar gerada(s).'))
