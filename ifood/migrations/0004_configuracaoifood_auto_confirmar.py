from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ifood', '0003_pedidoifood_agendamento_dt_pedidoifood_benefits_raw_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracaoifood',
            name='auto_confirmar',
            field=models.BooleanField(
                default=False,
                help_text='Confirma automaticamente todo pedido PLACED ao recebê-lo via polling',
            ),
        ),
    ]
