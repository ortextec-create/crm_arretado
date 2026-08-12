from django.db import migrations


def atribuir_empresa_padrao(apps, schema_editor):
    PedidoUnificado = apps.get_model('pedidos', 'PedidoUnificado')
    Empresa = apps.get_model('empresas', 'Empresa')

    padrao = Empresa.objects.filter(padrao=True).first()
    if not padrao:
        return

    PedidoUnificado.objects.filter(empresa__isnull=True).update(empresa=padrao)


def reverter(apps, schema_editor):
    PedidoUnificado = apps.get_model('pedidos', 'PedidoUnificado')
    PedidoUnificado.objects.update(empresa=None)


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0003_empresa_fase1_nullable'),
        ('empresas', '0002_criar_empresa_padrao'),
    ]

    operations = [
        migrations.RunPython(atribuir_empresa_padrao, reverter),
    ]
