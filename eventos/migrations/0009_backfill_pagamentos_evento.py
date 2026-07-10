from django.db import migrations


def backfill_pagamentos(apps, schema_editor):
    Evento = apps.get_model('eventos', 'Evento')
    PagamentoEvento = apps.get_model('eventos', 'PagamentoEvento')

    for evento in Evento.objects.filter(sinal_pago__gt=0):
        PagamentoEvento.objects.create(
            evento=evento,
            valor=evento.sinal_pago,
            forma_pagamento='outro',
            status='pago',
            data_pagamento=evento.criado_em.date(),
            observacao='Sinal migrado automaticamente (pré-existente ao módulo de Pagamentos)',
        )


def reverter_backfill(apps, schema_editor):
    PagamentoEvento = apps.get_model('eventos', 'PagamentoEvento')
    PagamentoEvento.objects.filter(
        observacao='Sinal migrado automaticamente (pré-existente ao módulo de Pagamentos)'
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('eventos', '0008_pagamento_evento'),
    ]

    operations = [
        migrations.RunPython(backfill_pagamentos, reverter_backfill),
    ]
