from django.db import migrations


def atribuir_empresa_padrao(apps, schema_editor):
    ConfiguracaoIFood = apps.get_model('ifood', 'ConfiguracaoIFood')
    PedidoIFood = apps.get_model('ifood', 'PedidoIFood')
    Empresa = apps.get_model('empresas', 'Empresa')

    padrao = Empresa.objects.filter(padrao=True).first()
    if not padrao:
        return

    ConfiguracaoIFood.objects.filter(empresa__isnull=True).update(empresa=padrao)
    PedidoIFood.objects.filter(empresa__isnull=True).update(empresa=padrao)


def reverter(apps, schema_editor):
    ConfiguracaoIFood = apps.get_model('ifood', 'ConfiguracaoIFood')
    PedidoIFood = apps.get_model('ifood', 'PedidoIFood')
    ConfiguracaoIFood.objects.update(empresa=None)
    PedidoIFood.objects.update(empresa=None)


class Migration(migrations.Migration):

    dependencies = [
        ('ifood', '0007_empresa_fase1_nullable'),
        ('empresas', '0002_criar_empresa_padrao'),
    ]

    operations = [
        migrations.RunPython(atribuir_empresa_padrao, reverter),
    ]
