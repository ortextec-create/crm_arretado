from django.db import migrations


def popular_empresa(apps, schema_editor):
    Empresa = apps.get_model('empresas', 'Empresa')
    empresa_padrao = Empresa.objects.filter(padrao=True).first()
    if not empresa_padrao:
        return  # banco sem nenhuma Empresa (ex.: settings_test antes da migration de empresas) — nada a fazer

    ConfiguracaoFinanceira = apps.get_model('financeiro', 'ConfiguracaoFinanceira')
    ContaBancaria = apps.get_model('financeiro', 'ContaBancaria')
    ContaPagar = apps.get_model('financeiro', 'ContaPagar')
    ContaReceber = apps.get_model('financeiro', 'ContaReceber')
    DespesaRecorrente = apps.get_model('financeiro', 'DespesaRecorrente')

    ConfiguracaoFinanceira.objects.filter(empresa__isnull=True).update(empresa=empresa_padrao)
    ContaBancaria.objects.filter(empresa__isnull=True).update(empresa=empresa_padrao)
    ContaPagar.objects.filter(empresa__isnull=True).update(empresa=empresa_padrao)
    ContaReceber.objects.filter(empresa__isnull=True).update(empresa=empresa_padrao)
    DespesaRecorrente.objects.filter(empresa__isnull=True).update(empresa=empresa_padrao)


def reverter(apps, schema_editor):
    pass  # não há como reverter com segurança (nem faz sentido) — no-op


class Migration(migrations.Migration):

    dependencies = [
        ('financeiro', '0006_adiciona_empresa_fase4'),
    ]

    operations = [
        migrations.RunPython(popular_empresa, reverter),
    ]
