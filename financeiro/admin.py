from django.contrib import admin

from .models import (
    AlertaFinanceiroEnviado,
    CategoriaFinanceira,
    ConfiguracaoFinanceira,
    ContaBancaria,
    ContaPagar,
    ContaReceber,
    DespesaRecorrente,
    Fornecedor,
    MovimentoFinanceiro,
    SaldoConferido,
    TelefoneAlertaFinanceiro,
)

admin.site.register(CategoriaFinanceira)
admin.site.register(ContaBancaria)
admin.site.register(Fornecedor)
admin.site.register(ConfiguracaoFinanceira)
admin.site.register(TelefoneAlertaFinanceiro)
admin.site.register(MovimentoFinanceiro)
admin.site.register(ContaPagar)
admin.site.register(DespesaRecorrente)
admin.site.register(AlertaFinanceiroEnviado)
admin.site.register(ContaReceber)
admin.site.register(SaldoConferido)
