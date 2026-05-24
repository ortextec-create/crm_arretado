from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('clientes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CategoriaProduto',
            fields=[
                ('id',    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome',  models.CharField(max_length=100, unique=True)),
                ('ordem', models.PositiveSmallIntegerField(default=0)),
            ],
            options={'verbose_name': 'Categoria', 'verbose_name_plural': 'Categorias', 'ordering': ['ordem', 'nome']},
        ),
        migrations.CreateModel(
            name='Produto',
            fields=[
                ('id',           models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome',         models.CharField(max_length=200)),
                ('descricao',    models.TextField(blank=True, default='')),
                ('preco',        models.DecimalField(decimal_places=2, max_digits=10)),
                ('ativo',        models.BooleanField(db_index=True, default=True)),
                ('criado_em',    models.DateTimeField(auto_now_add=True)),
                ('atualizado_em',models.DateTimeField(auto_now=True)),
                ('categoria',    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='produtos', to='pdv.categoriaproduto')),
            ],
            options={'verbose_name': 'Produto', 'verbose_name_plural': 'Produtos', 'ordering': ['categoria__ordem', 'nome']},
        ),
        migrations.AddIndex(
            model_name='produto',
            index=models.Index(fields=['ativo', 'nome'], name='pdv_produto_ativo_idx'),
        ),
        migrations.CreateModel(
            name='PedidoPDV',
            fields=[
                ('id',               models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero',           models.CharField(db_index=True, max_length=20, unique=True)),
                ('cliente_nome',     models.CharField(blank=True, default='', max_length=200)),
                ('cliente_telefone', models.CharField(blank=True, default='', max_length=30)),
                ('status',           models.CharField(choices=[('aberto','Aberto'),('confirmado','Confirmado'),('em_preparo','Em preparo'),('pronto','Pronto'),('concluido','Concluído'),('cancelado','Cancelado')], db_index=True, default='aberto', max_length=20)),
                ('tipo',             models.CharField(choices=[('balcao','Balcão'),('retirada','Retirada'),('delivery','Delivery'),('mesa','Mesa')], default='balcao', max_length=20)),
                ('pagamento',        models.CharField(blank=True, choices=[('dinheiro','Dinheiro'),('pix','PIX'),('credito','Cartão de Crédito'),('debito','Cartão de Débito'),('outro','Outro')], default='', max_length=20)),
                ('subtotal',         models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('desconto',         models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('taxa_entrega',     models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('total',            models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('observacoes',      models.TextField(blank=True, default='')),
                ('criado_em',        models.DateTimeField(auto_now_add=True, db_index=True)),
                ('atualizado_em',    models.DateTimeField(auto_now=True)),
                ('cliente',          models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pedidos_pdv', to='clientes.cliente')),
            ],
            options={'verbose_name': 'Pedido PDV', 'verbose_name_plural': 'Pedidos PDV', 'ordering': ['-criado_em']},
        ),
        migrations.AddIndex(
            model_name='pedidopdv',
            index=models.Index(fields=['status'], name='pdv_pedido_status_idx'),
        ),
        migrations.AddIndex(
            model_name='pedidopdv',
            index=models.Index(fields=['criado_em'], name='pdv_pedido_criado_idx'),
        ),
        migrations.CreateModel(
            name='ItemPedidoPDV',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome',        models.CharField(max_length=200)),
                ('preco_unit',  models.DecimalField(decimal_places=2, max_digits=8)),
                ('quantidade',  models.PositiveSmallIntegerField(default=1)),
                ('preco_total', models.DecimalField(decimal_places=2, max_digits=10)),
                ('observacao',  models.TextField(blank=True, default='')),
                ('pedido',      models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='itens', to='pdv.pedidopdv')),
                ('produto',     models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='itens_pedido', to='pdv.produto')),
            ],
            options={'verbose_name': 'Item do Pedido PDV', 'ordering': ['id']},
        ),
    ]
