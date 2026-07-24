from django.contrib import admin

from .models import (
    AlertaFinanceiroEnviado,
    CategoriaFinanceira,
    ConfiguracaoFinanceira,
    ContaBancaria,
    ContaPagar,
    DespesaRecorrente,
    Fornecedor,
    MovimentoFinanceiro,
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
