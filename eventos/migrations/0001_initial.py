from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('clientes', '0001_initial'),
        ('pdv', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LocalEvento',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome',       models.CharField(max_length=200)),
                ('endereco',   models.CharField(blank=True, default='', max_length=300)),
                ('bairro',     models.CharField(blank=True, default='', max_length=100)),
                ('cidade',     models.CharField(blank=True, default='Teresina', max_length=100)),
                ('referencia', models.CharField(blank=True, default='', help_text='Ex: portão azul, fundos, sala 3', max_length=300)),
                ('ativo',      models.BooleanField(db_index=True, default=True)),
                ('criado_em',  models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name':        'Local de Evento',
                'verbose_name_plural': 'Locais de Evento',
                'ordering':            ['nome'],
            },
        ),
        migrations.CreateModel(
            name='Evento',
            fields=[
                ('id',               models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero',           models.CharField(db_index=True, max_length=20, unique=True)),
                ('cliente_nome',     models.CharField(blank=True, default='', max_length=200)),
                ('cliente_telefone', models.CharField(blank=True, default='', max_length=30)),
                ('tipo_evento',      models.CharField(choices=[('casamento','Casamento'),('formatura','Formatura'),('aniversario','Aniversário'),('corporativo','Corporativo'),('batizado','Batizado'),('cha','Chá de bebê / revelação'),('outro','Outro')], default='aniversario', max_length=30)),
                ('data_evento',      models.DateField(db_index=True)),
                ('hora_evento',      models.TimeField(blank=True, null=True)),
                ('tipo_entrega',     models.CharField(choices=[('retirada_loja','Retirada na loja'),('entrega_local','Entrega no local da festa')], default='retirada_loja', max_length=20)),
                ('endereco_avulso',  models.CharField(blank=True, default='', max_length=400)),
                ('status',           models.CharField(choices=[('orcamento','Orçamento'),('confirmado','Confirmado'),('em_producao','Em produção'),('pronto','Pronto'),('entregue','Entregue'),('cancelado','Cancelado')], db_index=True, default='orcamento', max_length=20)),
                ('subtotal',         models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('desconto',         models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('valor_total',      models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('sinal_pago',       models.DecimalField(decimal_places=2, default=0, help_text='Valor de entrada/sinal já recebido', max_digits=10)),
                ('observacoes',      models.TextField(blank=True, default='')),
                ('criado_em',        models.DateTimeField(auto_now_add=True)),
                ('atualizado_em',    models.DateTimeField(auto_now=True)),
                ('cliente',          models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='eventos', to='clientes.cliente')),
                ('local',            models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='eventos', to='eventos.localevento')),
            ],
            options={
                'verbose_name':        'Evento',
                'verbose_name_plural': 'Eventos',
                'ordering':            ['data_evento', 'hora_evento'],
            },
        ),
        migrations.AddIndex(
            model_name='evento',
            index=models.Index(fields=['data_evento', 'status'], name='eventos_eve_data_ev_idx'),
        ),
        migrations.AddIndex(
            model_name='evento',
            index=models.Index(fields=['cliente', 'data_evento'], name='eventos_eve_cliente_idx'),
        ),
        migrations.CreateModel(
            name='ItemEvento',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome',        models.CharField(max_length=200)),
                ('preco_unit',  models.DecimalField(decimal_places=2, max_digits=10)),
                ('quantidade',  models.PositiveIntegerField(default=1)),
                ('preco_total', models.DecimalField(decimal_places=2, max_digits=10)),
                ('observacao',  models.CharField(blank=True, default='', max_length=300)),
                ('evento',      models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='itens', to='eventos.evento')),
                ('produto',     models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='itens_evento', to='pdv.produto')),
            ],
            options={
                'verbose_name':        'Item de Evento',
                'verbose_name_plural': 'Itens de Evento',
                'ordering':            ['id'],
            },
        ),
    ]
