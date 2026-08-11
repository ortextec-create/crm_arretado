from django.db import migrations


def criar_empresa_padrao(apps, schema_editor):
    Empresa = apps.get_model('empresas', 'Empresa')
    if not Empresa.objects.filter(padrao=True).exists():
        Empresa.objects.create(nome='Empresa Principal', padrao=True)


def remover_empresa_padrao(apps, schema_editor):
    Empresa = apps.get_model('empresas', 'Empresa')
    Empresa.objects.filter(nome='Empresa Principal', padrao=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(criar_empresa_padrao, remover_empresa_padrao),
    ]
