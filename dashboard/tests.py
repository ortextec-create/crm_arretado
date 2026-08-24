from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from empresas.models import Empresa
from financeiro.models import ContaReceber
from pedidos.models import PedidoUnificado
from usuarios.models import Usuario


def _pedido_unificado(canal, empresa, total='10.00', status='concluido', origem_id=1):
    return PedidoUnificado.objects.create(
        canal=canal, origem_id=origem_id, empresa=empresa,
        status=status, total=Decimal(total), pedido_em=timezone.now(),
    )


class DashboardResumoMultiEmpresaTests(TestCase):
    """
    Critério de pronto da Fase 5 (dashboard): a visão de uma empresa não-matriz
    (ex: MANGAIO) zera PDV/Eventos/Estoque e ganha o card repasse_ifood_a_receber;
    a matriz e o consolidado ('todas') continuam com o comportamento de sempre.
    """

    def setUp(self):
        self.matriz = Empresa.get_padrao()
        self.mangaio = Empresa.objects.create(nome='Mangaio')

    def _get(self, **params):
        return self.client.get('/api/v1/dashboard/resumo/', params)

    def test_default_sem_parametro_usa_matriz(self):
        _pedido_unificado('ifood', self.matriz, total='30.00', origem_id=1)
        _pedido_unificado('ifood', self.mangaio, total='50.00', origem_id=2)

        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['canais']['ifood']['total_hoje'], 30.0)
        self.assertEqual(resp.data['empresa']['id'], self.matriz.id)

    def test_empresa_explicita_nao_matriz_zera_pdv_e_eventos(self):
        _pedido_unificado('ifood', self.mangaio, total='50.00', origem_id=1)
        _pedido_unificado('pdv', self.matriz, total='20.00', origem_id=2)

        resp = self._get(empresa=self.mangaio.id)
        self.assertEqual(resp.data['canais']['ifood']['total_hoje'], 50.0)
        self.assertEqual(resp.data['canais']['pdv']['total_hoje'], 0.0)
        self.assertEqual(resp.data['canais']['eventos']['recebido_hoje'], 0.0)
        self.assertEqual(resp.data['a_receber'], {'total': 0.0, 'eventos': []})
        self.assertEqual(resp.data['estoque'], {'itens_abaixo_minimo': 0, 'insumos': [], 'produtos': []})
        self.assertEqual(resp.data['proximos_eventos'], [])
        self.assertEqual(resp.data['alertas'], [])
        self.assertFalse(resp.data['empresa']['padrao'])

    def test_repasse_ifood_a_receber_soma_conta_receber_pendente_da_empresa(self):
        ContaReceber.objects.create(
            numero=ContaReceber.proximo_numero(), empresa=self.mangaio,
            canal='ifood', origem_canal='ifood', origem_id='ped-1',
            valor=Decimal('40.00'), data_vencimento=date.today(),
        )
        resp = self._get(empresa=self.mangaio.id)
        self.assertEqual(resp.data['repasse_ifood_a_receber'], 40.0)

    def test_empresa_todas_soma_ifood_das_duas_empresas(self):
        _pedido_unificado('ifood', self.matriz, total='30.00', origem_id=1)
        _pedido_unificado('ifood', self.mangaio, total='50.00', origem_id=2)

        resp = self._get(empresa='todas')
        self.assertIsNone(resp.data['empresa'])
        self.assertEqual(resp.data['canais']['ifood']['total_hoje'], 80.0)

    def test_usuario_autenticado_usa_empresa_ativa_por_default(self):
        usuario = Usuario.objects.create(
            name='Teste Dashboard', email='dashboard-teste@arretado.local',
            role='atendente', empresa_ativa=self.mangaio,
            auth_token='tok-dashboard-teste',
        )
        _pedido_unificado('ifood', self.mangaio, total='50.00', origem_id=1)

        resp = self.client.get(
            '/api/v1/dashboard/resumo/', HTTP_AUTHORIZATION=f'Token {usuario.auth_token}',
        )
        self.assertEqual(resp.data['empresa']['id'], self.mangaio.id)
        self.assertEqual(resp.data['canais']['ifood']['total_hoje'], 50.0)
