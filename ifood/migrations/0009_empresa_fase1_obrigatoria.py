import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0002_criar_empresa_padrao'),
        ('ifood', '0008_empresa_fase1_atribuir_padrao'),
    ]

    operations = [
        migrations.AlterField(
            model_name='configuracaoifood',
            name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='configuracoes_ifood', to='empresas.empresa'),
        ),
        migrations.AlterField(
            model_name='pedidoifood',
            name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pedidos_ifood', to='empresas.empresa'),
        ),
    ]
