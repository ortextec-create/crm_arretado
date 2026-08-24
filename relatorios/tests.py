from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from empresas.models import Empresa
from eventos.models import Evento, ItemEvento
from ifood.models import ConfiguracaoIFood, ItemPedidoIFood, PedidoIFood
from pdv.models import ItemPedidoPDV, PedidoPDV


def _pedido_ifood(order_id, status='CONCLUDED', dias_atras=0, empresa=None):
    empresa = empresa or Empresa.get_padrao()
    config, _ = ConfiguracaoIFood.objects.get_or_create(
        merchant_id=f'merch-{empresa.id}',
        defaults={'empresa': empresa, 'client_id': 'cid', 'client_secret': 'sec'},
    )
    return PedidoIFood.objects.create(
        ifood_order_id=order_id, ifood_merchant_id=config.merchant_id, empresa=empresa,
        status=status, total_valor=Decimal('10'),
        ifood_criado_em=timezone.now() - timedelta(days=dias_atras),
    )


class ProdutosMaisVendidosTests(TestCase):
    def _get(self, **params):
        resp = self.client.get('/api/v1/relatorios/produtos-mais-vendidos/', params)
        resp.render() if hasattr(resp, 'render') else None
        return resp

    def test_soma_quantidade_e_valor_entre_canais_por_nome_normalizado(self):
        pedido = _pedido_ifood('order-1')
        ItemPedidoIFood.objects.create(
            pedido=pedido, nome='Bolo de Chocolate', quantidade=3,
            preco_unit=Decimal('20'), preco_total=Decimal('60'),
        )
        pdv_pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), status='concluido')
        # mesmo produto, nome com acentuação/caixa diferente — deve agrupar junto
        ItemPedidoPDV.objects.create(
            pedido=pdv_pedido, nome='BOLO DE CHOCOLATE', quantidade=2,
            preco_unit=Decimal('18'), preco_total=Decimal('36'),
        )

        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        produtos = resp.data['produtos']
        self.assertEqual(len(produtos), 1)
        p = produtos[0]
        self.assertEqual(p['quantidade_total'], 5)
        self.assertEqual(p['valor_total'], 96.0)
        self.assertEqual(p['canais']['ifood']['quantidade'], 3)
        self.assertEqual(p['canais']['pdv']['quantidade'], 2)

    def test_ifood_so_conta_pedido_concluido(self):
        pedido = _pedido_ifood('order-2', status='CANCELLED')
        ItemPedidoIFood.objects.create(
            pedido=pedido, nome='Torta de Morango', quantidade=1,
            preco_unit=Decimal('30'), preco_total=Decimal('30'),
        )
        resp = self._get()
        self.assertEqual(resp.data['produtos'], [])

    def test_pdv_exclui_aberto_e_cancelado(self):
        aberto = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), status='aberto')
        ItemPedidoPDV.objects.create(pedido=aberto, nome='Cookie', quantidade=1, preco_unit=Decimal('5'), preco_total=Decimal('5'))
        cancelado = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), status='cancelado')
        ItemPedidoPDV.objects.create(pedido=cancelado, nome='Cookie', quantidade=1, preco_unit=Decimal('5'), preco_total=Decimal('5'))

        resp = self._get()
        self.assertEqual(resp.data['produtos'], [])

    def test_pdv_exclui_item_brinde_e_permuta(self):
        # Fase 2 do BRINDES_PERMUTAS.md: natureza != 'venda' não conta no ranking.
        pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), status='concluido')
        ItemPedidoPDV.objects.create(
            pedido=pedido, nome='Brigadeiro', quantidade=10, preco_unit=Decimal('3'), natureza='brinde',
        )
        ItemPedidoPDV.objects.create(
            pedido=pedido, nome='Docinho', quantidade=5, preco_unit=Decimal('2'), natureza='permuta',
        )
        resp = self._get()
        self.assertEqual(resp.data['produtos'], [])

    def test_eventos_exclui_item_brinde_e_permuta(self):
        evento = Evento.objects.create(
            numero=Evento.proximo_numero(), tipo_evento='aniversario',
            data_evento=date.today(), status='entregue',
        )
        ItemEvento.objects.create(
            evento=evento, nome='Bolo de Brinde', quantidade=1, preco_unit=Decimal('100'), natureza='brinde',
        )
        resp = self._get()
        self.assertEqual(resp.data['produtos'], [])

    def test_item_venda_conta_normalmente_junto_com_brinde_no_mesmo_pedido(self):
        pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), status='concluido')
        ItemPedidoPDV.objects.create(pedido=pedido, nome='Bolo Vendido', quantidade=1, preco_unit=Decimal('50'))
        ItemPedidoPDV.objects.create(
            pedido=pedido, nome='Brinde Junto', quantidade=1, preco_unit=Decimal('20'), natureza='brinde',
        )
        resp = self._get()
        produtos = resp.data['produtos']
        self.assertEqual(len(produtos), 1)
        self.assertEqual(produtos[0]['nome'], 'Bolo Vendido')

    def test_eventos_so_conta_status_entregue(self):
        confirmado = Evento.objects.create(
            numero=Evento.proximo_numero(), tipo_evento='aniversario',
            data_evento=date.today(), status='confirmado',
        )
        ItemEvento.objects.create(evento=confirmado, nome='Bolo de Festa', quantidade=1, preco_unit=Decimal('100'), preco_total=Decimal('100'))

        entregue = Evento.objects.create(
            numero=Evento.proximo_numero(), tipo_evento='aniversario',
            data_evento=date.today(), status='entregue',
        )
        ItemEvento.objects.create(evento=entregue, nome='Bolo de Festa', quantidade=2, preco_unit=Decimal('100'), preco_total=Decimal('200'))

        resp = self._get()
        produtos = resp.data['produtos']
        self.assertEqual(len(produtos), 1)
        self.assertEqual(produtos[0]['quantidade_total'], 2)

    def test_filtro_canal_restringe_agregacao(self):
        pedido = _pedido_ifood('order-3')
        ItemPedidoIFood.objects.create(pedido=pedido, nome='Brigadeiro', quantidade=10, preco_unit=Decimal('3'), preco_total=Decimal('30'))
        pdv_pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), status='concluido')
        ItemPedidoPDV.objects.create(pedido=pdv_pedido, nome='Brigadeiro', quantidade=4, preco_unit=Decimal('3'), preco_total=Decimal('12'))

        resp = self._get(canal='pdv')
        self.assertEqual(resp.data['produtos'][0]['quantidade_total'], 4)
        self.assertNotIn('ifood', resp.data['produtos'][0]['canais'])

    def test_ordenar_por_valor(self):
        pedido = _pedido_ifood('order-4')
        ItemPedidoIFood.objects.create(pedido=pedido, nome='Item Caro', quantidade=1, preco_unit=Decimal('500'), preco_total=Decimal('500'))
        pdv_pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), status='concluido')
        ItemPedidoPDV.objects.create(pedido=pdv_pedido, nome='Item Popular', quantidade=50, preco_unit=Decimal('2'), preco_total=Decimal('100'))

        resp_qtd = self._get(ordenar='quantidade')
        self.assertEqual(resp_qtd.data['produtos'][0]['nome'], 'Item Popular')

        resp_valor = self._get(ordenar='valor')
        self.assertEqual(resp_valor.data['produtos'][0]['nome'], 'Item Caro')

    def test_filtro_periodo_exclui_fora_do_range(self):
        pedido = _pedido_ifood('order-5', dias_atras=60)
        ItemPedidoIFood.objects.create(pedido=pedido, nome='Fora do Periodo', quantidade=1, preco_unit=Decimal('10'), preco_total=Decimal('10'))

        resp = self._get()  # default: últimos 30 dias
        self.assertEqual(resp.data['produtos'], [])

    def test_resumo_soma_todos_produtos(self):
        pedido = _pedido_ifood('order-6')
        ItemPedidoIFood.objects.create(pedido=pedido, nome='A', quantidade=2, preco_unit=Decimal('10'), preco_total=Decimal('20'))
        ItemPedidoIFood.objects.create(pedido=pedido, nome='B', quantidade=3, preco_unit=Decimal('5'), preco_total=Decimal('15'))

        resp = self._get()
        self.assertEqual(resp.data['resumo']['produtos_distintos'], 2)
        self.assertEqual(resp.data['resumo']['quantidade_total'], 5)
        self.assertEqual(resp.data['resumo']['valor_total'], 35.0)


class ProdutosMaisVendidosMultiEmpresaTests(TestCase):
    """Fase 5 do multi-empresa: iFood filtra por empresa; PDV/Eventos (mono-empresa) só entram na soma pra matriz/'todas'."""

    def setUp(self):
        self.matriz = Empresa.get_padrao()
        self.mangaio = Empresa.objects.create(nome='Mangaio')

    def _get(self, **params):
        return self.client.get('/api/v1/relatorios/produtos-mais-vendidos/', params)

    def test_default_sem_parametro_usa_matriz(self):
        pedido_matriz = _pedido_ifood('order-matriz', empresa=self.matriz)
        ItemPedidoIFood.objects.create(pedido=pedido_matriz, nome='Bolo Matriz', quantidade=1, preco_unit=Decimal('10'), preco_total=Decimal('10'))
        pedido_mangaio = _pedido_ifood('order-mangaio', empresa=self.mangaio)
        ItemPedidoIFood.objects.create(pedido=pedido_mangaio, nome='Prato Mangaio', quantidade=1, preco_unit=Decimal('20'), preco_total=Decimal('20'))

        resp = self._get()
        nomes = [p['nome'] for p in resp.data['produtos']]
        self.assertIn('Bolo Matriz', nomes)
        self.assertNotIn('Prato Mangaio', nomes)

    def test_empresa_explicita_nao_matriz_exclui_pdv_e_eventos(self):
        pedido = _pedido_ifood('order-m2', empresa=self.mangaio)
        ItemPedidoIFood.objects.create(pedido=pedido, nome='Prato Mangaio', quantidade=1, preco_unit=Decimal('20'), preco_total=Decimal('20'))
        pdv_pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), status='concluido')
        ItemPedidoPDV.objects.create(pedido=pdv_pedido, nome='Cookie', quantidade=1, preco_unit=Decimal('5'), preco_total=Decimal('5'))

        resp = self._get(empresa=self.mangaio.id)
        nomes = [p['nome'] for p in resp.data['produtos']]
        self.assertEqual(nomes, ['Prato Mangaio'])

    def test_empresa_todas_soma_ifood_das_duas_e_pdv_da_matriz(self):
        pedido_matriz = _pedido_ifood('order-m3', empresa=self.matriz)
        ItemPedidoIFood.objects.create(pedido=pedido_matriz, nome='Bolo Matriz', quantidade=1, preco_unit=Decimal('10'), preco_total=Decimal('10'))
        pedido_mangaio = _pedido_ifood('order-m4', empresa=self.mangaio)
        ItemPedidoIFood.objects.create(pedido=pedido_mangaio, nome='Prato Mangaio', quantidade=1, preco_unit=Decimal('20'), preco_total=Decimal('20'))

        resp = self._get(empresa='todas')
        nomes = [p['nome'] for p in resp.data['produtos']]
        self.assertIn('Bolo Matriz', nomes)
        self.assertIn('Prato Mangaio', nomes)


class RelatorioIFoodMultiEmpresaTests(TestCase):
    """Fase 5 do multi-empresa: relatorios/ifood/ aceita ?empresa=<id>/?empresa=todas."""

    def setUp(self):
        self.matriz = Empresa.get_padrao()
        self.mangaio = Empresa.objects.create(nome='Mangaio')

    def _get(self, **params):
        return self.client.get('/api/v1/relatorios/ifood/', params)

    def test_default_sem_parametro_usa_matriz(self):
        _pedido_ifood('order-r1', empresa=self.matriz)
        _pedido_ifood('order-r2', empresa=self.mangaio)

        resp = self._get()
        self.assertEqual(resp.data['resumo']['total_pedidos'], 1)

    def test_empresa_explicita_filtra(self):
        _pedido_ifood('order-r3', empresa=self.matriz)
        _pedido_ifood('order-r4', empresa=self.mangaio)
        _pedido_ifood('order-r5', empresa=self.mangaio)

        resp = self._get(empresa=self.mangaio.id)
        self.assertEqual(resp.data['resumo']['total_pedidos'], 2)

    def test_empresa_todas_soma_as_duas(self):
        _pedido_ifood('order-r6', empresa=self.matriz)
        _pedido_ifood('order-r7', empresa=self.mangaio)

        resp = self._get(empresa='todas')
        self.assertEqual(resp.data['resumo']['total_pedidos'], 2)
