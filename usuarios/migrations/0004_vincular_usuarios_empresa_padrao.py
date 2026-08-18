from django.db import migrations


def vincular_empresa_padrao(apps, schema_editor):
    Usuario = apps.get_model('usuarios', 'Usuario')
    Empresa = apps.get_model('empresas', 'Empresa')

    padrao = Empresa.objects.filter(padrao=True).first()
    if not padrao:
        return

    for usuario in Usuario.objects.all():
        usuario.empresas.add(padrao)
        if usuario.empresa_ativa_id is None:
            usuario.empresa_ativa = padrao
            usuario.save(update_fields=['empresa_ativa'])


def desvincular_empresa_padrao(apps, schema_editor):
    # Sem reversão de dados — desfazer a migration não deve apagar vínculo
    # que o usuário já possa ter alterado manualmente.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0003_usuario_empresa_ativa_usuario_empresas_and_more'),
    ]

    operations = [
        migrations.RunPython(vincular_empresa_padrao, desvincular_empresa_padrao),
    ]
