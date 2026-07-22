from django.contrib import admin

from .models import (
    CategoriaFinanceira,
    ConfiguracaoFinanceira,
    ContaBancaria,
    ContaPagar,
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
