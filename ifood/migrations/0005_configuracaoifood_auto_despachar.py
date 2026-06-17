from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ifood', '0004_configuracaoifood_auto_confirmar'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracaoifood',
            name='auto_despachar',
            field=models.BooleanField(
                default=False,
                help_text='Despacha (DELIVERY) ou marca como pronto (TAKEOUT) logo após confirmar. Requer auto_confirmar=True',
            ),
        ),
    ]
