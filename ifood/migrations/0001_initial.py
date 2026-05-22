from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('clientes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracaoIFood',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('client_id', models.CharField(max_length=200)),
                ('client_secret', models.CharField(max_length=200)),
                ('merchant_id', models.CharField(max_length=200)),
                ('access_token', models.TextField(blank=True, default='')),
                ('token_expira_em', models.DateTimeField(blank=True, null=True)),
                ('refresh_token', models.TextField(blank=True, default='')),
                ('polling_ativo', models.BooleanField(default=False)),
                ('ultimo_polling', models.DateTimeField(blank=True, null=True)),
                ('polling_intervalo', models.IntegerField(default=30)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'Configuração iFood', 'verbose_name_plural': 'Configurações iFood'},
        ),
        migrations.CreateModel(
            name='PedidoIFood',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('ifood_order_id', models.CharField(db_index=True, max_length=100, unique=True)),
                ('ifood_merchant_id', models.CharField(db_index=True, max_length=100)),
                ('display_id', models.CharField(blank=True, default='', max_length=20)),
                ('cliente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pedidos_ifood', to='clientes.cliente')),
                ('status', models.CharField(choices=[('PLACED', 'Aguardando confirmação'), ('CONFIRMED', 'Confirmado'), ('PREPARATION_STARTED', 'Em preparo'), ('READY_TO_PICKUP', 'Pronto / Aguardando retirada'), ('DISPATCHED', 'Despachado'), ('CONCLUDED', 'Concluído'), ('CANCELLATION_REQUESTED', 'Cancelamento solicitado'), ('CANCELLED', 'Cancelado')], default='PLACED', max_length=40)),
                ('order_type', models.CharField(choices=[('DELIVERY', 'Delivery'), ('TAKEOUT', 'Retirada'), ('INDOOR', 'Mesa')], default='DELIVERY', max_length=20)),
                ('total_valor', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('subtotal', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('taxa_entrega', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('desconto', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('payment_method', models.CharField(blank=True, default='', max_length=100)),
                ('cliente_nome', models.CharField(blank=True, default='', max_length=200)),
                ('cliente_telefone', models.CharField(blank=True, default='', max_length=30)),
                ('cliente_ifood_id', models.CharField(blank=True, db_index=True, default='', max_length=100)),
                ('endereco_entrega', models.JSONField(blank=True, default=dict)),
                ('payload_raw', models.JSONField(blank=True, default=dict)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('ifood_criado_em', models.DateTimeField(blank=True, null=True)),
            ],
            options={'verbose_name': 'Pedido iFood', 'verbose_name_plural': 'Pedidos iFood', 'ordering': ['-ifood_criado_em']},
        ),
        migrations.CreateModel(
            name='ItemPedidoIFood',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('pedido', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='itens', to='ifood.pedidoifood')),
                ('ifood_item_id', models.CharField(blank=True, default='', max_length=100)),
                ('nome', models.CharField(max_length=300)),
                ('quantidade', models.IntegerField(default=1)),
                ('preco_unit', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('preco_total', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('observacao', models.TextField(blank=True, default='')),
                ('complementos', models.JSONField(blank=True, default=list)),
            ],
            options={'verbose_name': 'Item do Pedido', 'ordering': ['id']},
        ),
        migrations.CreateModel(
            name='EventoPollingIFood',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('ifood_event_id', models.CharField(max_length=100, unique=True)),
                ('code', models.CharField(choices=[('PLC', 'PLACED — Pedido criado'), ('CFM', 'CONFIRMED — Confirmado'), ('DSP', 'DISPATCHED — Despachado'), ('CAN', 'CANCELLATION_REQUESTED'), ('CAC', 'CANCELLED'), ('CON', 'CONCLUDED'), ('HBT', 'HEARTBEAT'), ('OTH', 'Outro')], default='OTH', max_length=10)),
                ('full_code', models.CharField(blank=True, default='', max_length=60)),
                ('order_id', models.CharField(blank=True, default='', max_length=100)),
                ('merchant_id', models.CharField(blank=True, default='', max_length=100)),
                ('acknowledged', models.BooleanField(default=False)),
                ('processado', models.BooleanField(default=False)),
                ('payload', models.JSONField(default=dict)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('ifood_criado_em', models.DateTimeField(blank=True, null=True)),
            ],
            options={'verbose_name': 'Evento de Polling', 'verbose_name_plural': 'Eventos de Polling', 'ordering': ['-ifood_criado_em']},
        ),
        migrations.AddIndex(model_name='pedidoifood', index=models.Index(fields=['status'], name='pedido_status_idx')),
        migrations.AddIndex(model_name='pedidoifood', index=models.Index(fields=['criado_em'], name='pedido_criado_em_idx')),
        migrations.AddIndex(model_name='pedidoifood', index=models.Index(fields=['cliente_ifood_id'], name='pedido_cliente_ifood_idx')),
    ]
