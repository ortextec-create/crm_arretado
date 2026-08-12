from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from empresas.models import Empresa
from pedidos.models import PedidoUnificado

from .models import ConfiguracaoIFood, PedidoIFood
from .polling_worker import _criar_pedido
from .views import ConfiguracaoIFoodViewSet, PedidoIFoodViewSet


def _empresa(nome='Mangaio', **kwargs):
    return Empresa.objects.create(nome=nome, **kwargs)


def _config(empresa, merchant_id='merch-1'):
    return ConfiguracaoIFood.objects.create(
        empresa=empresa, client_id='cid', client_secret='sec', merchant_id=merchant_id,
    )


def _pedido(empresa, order_id='order-1'):
    return PedidoIFood.objects.create(
        ifood_order_id=order_id, ifood_merchant_id='merch-1',
        empresa=empresa, total_valor=Decimal('10'), ifood_criado_em=timezone.now(),
    )


class ConfiguracaoIFoodEmpresaTests(TestCase):
    def test_empresa_e_obrigatoria(self):
        with self.assertRaises(Exception):
            ConfiguracaoIFood.objects.create(client_id='a', client_secret='b', merchant_id='m')

    def test_duas_empresas_podem_ter_config_propria(self):
        matriz = Empresa.get_padrao()
        mangaio = _empresa()
        cfg_matriz = _config(matriz, merchant_id='merch-matriz')
        cfg_mangaio = _config(mangaio, merchant_id='merch-mangaio')
        self.assertEqual(cfg_matriz.empresa, matriz)
        self.assertEqual(cfg_mangaio.empresa, mangaio)


class CriarPedidoPropagaEmpresaTests(TestCase):
    def test_criar_pedido_herda_empresa_da_config(self):
        mangaio = _empresa()
        config = _config(mangaio)
        detalhe = {
            'id': 'abc-123',
            'displayId': '001',
            'merchant': {'id': 'merch-1'},
            'customer': {}, 'delivery': {}, 'payments': {},
            'total': {}, 'items': [], 'metadata': {}, 'schedule': {}, 'benefits': [],
            'fullCode': 'PLACED', 'orderType': 'DELIVERY',
        }
        pedido = _criar_pedido(detalhe, config)
        self.assertEqual(pedido.empresa, mangaio)

    def test_sincronizacao_pedido_unificado_propaga_empresa(self):
        mangaio = _empresa()
        pedido = _pedido(mangaio)
        unificado = PedidoUnificado.objects.get(canal='ifood', origem_id=pedido.pk)
        self.assertEqual(unificado.empresa, mangaio)


class CredencialPorEmpresaTests(TestCase):
    """Garante que ações de pedido nunca resolvem credencial via .objects.first() —
    sempre a config da empresa do pedido (MULTIEMPRESA.md Fase 1)."""

    def setUp(self):
        self.matriz = Empresa.get_padrao()
        self.mangaio = _empresa()
        # Config da matriz é criada primeiro — se algum código usar .first(), o teste
        # abaixo pega o pedido da MANGAIO e, se resolver errado, usa o merchant da matriz.
        self.cfg_matriz = _config(self.matriz, merchant_id='merch-matriz')
        self.cfg_mangaio = _config(self.mangaio, merchant_id='merch-mangaio')
        self.factory = APIRequestFactory()

    @patch('ifood.views.IFoodClient')
    def test_confirmar_usa_config_da_empresa_do_pedido(self, mock_client_cls):
        pedido = _pedido(self.mangaio, order_id='order-mangaio')
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance

        view = PedidoIFoodViewSet.as_view({'post': 'confirmar'})
        request = self.factory.post(f'/api/v1/ifood/pedidos/{pedido.id}/confirmar/')
        view(request, pk=pedido.id)

        # IFoodClient deve ter sido instanciado com a config da MANGAIO, não da matriz
        called_config = mock_client_cls.call_args[0][0]
        self.assertEqual(called_config.id, self.cfg_mangaio.id)
        self.assertEqual(called_config.merchant_id, 'merch-mangaio')


class StatusEstatisticasPorEmpresaTests(TestCase):
    def setUp(self):
        self.matriz = Empresa.get_padrao()
        self.mangaio = _empresa()
        _config(self.matriz, merchant_id='merch-matriz')
        _config(self.mangaio, merchant_id='merch-mangaio')
        _pedido(self.matriz, order_id='order-matriz')
        _pedido(self.mangaio, order_id='order-mangaio-1')
        _pedido(self.mangaio, order_id='order-mangaio-2')
        self.factory = APIRequestFactory()

    def test_status_geral_sem_param_usa_empresa_padrao(self):
        view = ConfiguracaoIFoodViewSet.as_view({'get': 'status_geral'})
        request = self.factory.get('/api/v1/ifood/config/status/')
        resp = view(request)
        self.assertEqual(resp.data['empresa'], self.matriz.id)

    def test_status_geral_com_param_resolve_outra_empresa(self):
        view = ConfiguracaoIFoodViewSet.as_view({'get': 'status_geral'})
        request = self.factory.get(f'/api/v1/ifood/config/status/?empresa={self.mangaio.id}')
        resp = view(request)
        self.assertEqual(resp.data['empresa'], self.mangaio.id)
        self.assertEqual(resp.data['pedidos_hoje'], 2)

    def test_estatisticas_filtra_por_empresa(self):
        view = PedidoIFoodViewSet.as_view({'get': 'estatisticas'})
        request = self.factory.get(f'/api/v1/ifood/pedidos/estatisticas/?empresa={self.mangaio.id}')
        resp = view(request)
        self.assertEqual(resp.data['total_geral'], 2)

    def test_lista_pedidos_filtra_por_empresa(self):
        view = PedidoIFoodViewSet.as_view({'get': 'list'})
        request = self.factory.get(f'/api/v1/ifood/pedidos/?empresa={self.mangaio.id}')
        resp = view(request)
        self.assertEqual(resp.data['count'], 2)


class SignalsPdvEventosUsamEmpresaPadraoTests(TestCase):
    def test_pdv_sincroniza_com_empresa_padrao(self):
        from pdv.models import PedidoPDV

        matriz = Empresa.get_padrao()
        _empresa()  # MANGAIO existe, mas PDV é mono-empresa — deve ir sempre pra matriz
        pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), total=Decimal('10'))
        unificado = PedidoUnificado.objects.get(canal='pdv', origem_id=pedido.pk)
        self.assertEqual(unificado.empresa, matriz)

    def test_evento_sincroniza_com_empresa_padrao(self):
        from clientes.models import Cliente
        from eventos.models import Evento

        matriz = Empresa.get_padrao()
        _empresa()
        cliente = Cliente.objects.create(nome='Fulano', telefone_principal='86999999999')
        evento = Evento.objects.create(
            numero=Evento.proximo_numero(), cliente=cliente, data_evento='2026-09-01',
        )
        unificado = PedidoUnificado.objects.get(canal='eventos', origem_id=evento.pk)
        self.assertEqual(unificado.empresa, matriz)
