from django.apps import AppConfig


class FinanceiroConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'financeiro'
    verbose_name = 'Financeiro'

    # Sem signals ainda — chegam na Fase 4 (PDV/iFood/PagamentoEvento).
    # Quando existir financeiro/signals.py, registrar aqui via ready(),
    # mesmo padrão de estoque/apps.py.
