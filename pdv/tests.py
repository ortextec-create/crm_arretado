from django.test import TestCase
from rest_framework.test import APIRequestFactory

from auditoria.models import LogAuditoria
from usuarios.models import Usuario
from usuarios.views import UsuarioViewSet
from .models import (
    CategoriaProduto, ConfiguracaoEntrega, FaixaPreco, ItemKit, ItemPedidoPDV,
    PedidoPDV, Produto, TaxaEntregaBairro,
)
from .views import (
    CategoriaProdutoViewSet, ConfiguracaoEntregaViewSet, PedidoPDVViewSet,
    ProdutoViewSet, TaxaEntregaBairroViewSet,
)


class AuditoriaPDVTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = Usuario(name='Admin Teste', email='admin@teste.com', role='admin')
        self.admin.set_password('senha-123')
        self.admin.save()

    def _token(self):
        resp = UsuarioViewSet.as_view({'post': 'login'})(self.factory.post(
            '/api/v1/usuarios/login/', {'email': 'admin@teste.com', 'password': 'senha-123'}, format='json',
        ))
        return resp.data['token']


class ConfiguracaoEntregaAuditoriaTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = Usuario(name='Admin Teste', email='admin@teste.com', role='admin')
        self.admin.set_password('senha-123')
        self.admin.save()

    def _token(self):
        resp = UsuarioViewSet.as_view({'post': 'login'})(self.factory.post(
            '/api/v1/usuarios/login/', {'email': 'admin@teste.com', 'password': 'senha-123'}, format='json',
        ))
        return resp.data['token']

    def test_get_nao_exige_login(self):
        view = ConfiguracaoEntregaViewSet.as_view({'get': 'retrieve'})
        resp = view(self.factory.get('/api/v1/pdv/configuracao-entrega/1/'), pk=1)
        self.assertEqual(resp.status_code, 200)

    def test_patch_sem_token_401(self):
        view = ConfiguracaoEntregaViewSet.as_view({'patch': 'partial_update'})
        req = self.factory.patch('/api/v1/pdv/configuracao-entrega/1/', {'frete_padrao': '12.50'}, format='json')
        resp = view(req, pk=1)
        self.assertEqual(resp.status_code, 401)

    def test_patch_com_token_gera_log(self):
        view = ConfiguracaoEntregaViewSet.as_view({'patch': 'partial_update'})
        req = self.factory.patch(
            '/api/v1/pdv/configuracao-entrega/1/', {'frete_padrao': '12.50'}, format='json',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=1)
        self.assertEqual(resp.status_code, 200, resp.data)

        cfg = ConfiguracaoEntrega.get()
        self.assertEqual(str(cfg.frete_padrao), '12.50')

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_CONFIG_ENTREGA_ALTERADA).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['depois']['frete_padrao'], '12.50')


class CategoriaProdutoDestroyTests(AuditoriaPDVTestCase):
    def setUp(self):
        super().setUp()
        self.categoria = CategoriaProduto.objects.create(nome='Bolos')

    def test_sem_token_401(self):
        view = CategoriaProdutoViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(f'/api/v1/pdv/categorias/{self.categoria.id}/')
        resp = view(req, pk=self.categoria.id)
        self.assertEqual(resp.status_code, 401)

    def test_com_token_gera_log(self):
        view = CategoriaProdutoViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(
            f'/api/v1/pdv/categorias/{self.categoria.id}/', HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.categoria.id)
        self.assertEqual(resp.status_code, 204)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.detalhes['model'], 'CategoriaProduto')
        self.assertEqual(log.detalhes['nome'], 'Bolos')


class TaxaEntregaBairroDestroyTests(AuditoriaPDVTestCase):
    def setUp(self):
        super().setUp()
        self.taxa = TaxaEntregaBairro.objects.create(bairro='Centro', taxa=5)

    def test_sem_token_401(self):
        view = TaxaEntregaBairroViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(f'/api/v1/pdv/taxas-entrega/{self.taxa.id}/')
        resp = view(req, pk=self.taxa.id)
        self.assertEqual(resp.status_code, 401)

    def test_com_token_gera_log(self):
        view = TaxaEntregaBairroViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(
            f'/api/v1/pdv/taxas-entrega/{self.taxa.id}/', HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.taxa.id)
        self.assertEqual(resp.status_code, 204)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.detalhes['model'], 'TaxaEntregaBairro')
        self.assertEqual(log.detalhes['bairro'], 'Centro')


class ProdutoDestroyAuditoriaTests(AuditoriaPDVTestCase):
    def setUp(self):
        super().setUp()
        self.produto = Produto.objects.create(nome='Bolo Teste', preco=50, segmento='outro')

    def test_destroy_sem_token_401(self):
        view = ProdutoViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(f'/api/v1/pdv/produtos/{self.produto.id}/')
        resp = view(req, pk=self.produto.id)
        self.assertEqual(resp.status_code, 401)
        self.assertTrue(Produto.objects.filter(pk=self.produto.id).exists())

    def test_destroy_com_token_gera_log(self):
        view = ProdutoViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(
            f'/api/v1/pdv/produtos/{self.produto.id}/', HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.produto.id)
        self.assertEqual(resp.status_code, 204)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.detalhes['model'], 'Produto')
        self.assertEqual(log.detalhes['nome'], 'Bolo Teste')

    def test_protegido_por_item_kit_retorna_400(self):
        kit = Produto.objects.create(nome='Kit Festa', preco=100, segmento='outro', tipo='kit')
        ItemKit.objects.create(kit=kit, componente=self.produto, quantidade=1)

        view = ProdutoViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(
            f'/api/v1/pdv/produtos/{self.produto.id}/', HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.produto.id)
        resp.render()
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(Produto.objects.filter(pk=self.produto.id).exists())

    def test_remover_faixa_preco_sem_token_401(self):
        faixa = FaixaPreco.objects.create(produto=self.produto, quantidade_minima=10, preco_unitario=45)
        view = ProdutoViewSet.as_view({'delete': 'remover_faixa_preco'})
        req = self.factory.delete(f'/api/v1/pdv/produtos/{self.produto.id}/faixas-preco/{faixa.id}/remover/')
        resp = view(req, pk=self.produto.id, faixa_id=faixa.id)
        self.assertEqual(resp.status_code, 401)

    def test_remover_faixa_preco_com_token_gera_log(self):
        faixa = FaixaPreco.objects.create(produto=self.produto, quantidade_minima=10, preco_unitario=45)
        view = ProdutoViewSet.as_view({'delete': 'remover_faixa_preco'})
        req = self.factory.delete(
            f'/api/v1/pdv/produtos/{self.produto.id}/faixas-preco/{faixa.id}/remover/',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.produto.id, faixa_id=faixa.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(FaixaPreco.objects.filter(pk=faixa.id).exists())

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.detalhes['model'], 'FaixaPreco')
        self.assertEqual(log.detalhes['produto_id'], self.produto.id)

    def test_remover_item_kit_sem_token_401(self):
        kit = Produto.objects.create(nome='Kit Festa', preco=100, segmento='outro', tipo='kit')
        item = ItemKit.objects.create(kit=kit, componente=self.produto, quantidade=1)
        view = ProdutoViewSet.as_view({'delete': 'remover_item_kit'})
        req = self.factory.delete(f'/api/v1/pdv/produtos/{kit.id}/itens-kit/{item.id}/')
        resp = view(req, pk=kit.id, item_id=item.id)
        self.assertEqual(resp.status_code, 401)

    def test_remover_item_kit_com_token_gera_log(self):
        kit = Produto.objects.create(nome='Kit Festa', preco=100, segmento='outro', tipo='kit')
        item = ItemKit.objects.create(kit=kit, componente=self.produto, quantidade=1)
        view = ProdutoViewSet.as_view({'delete': 'remover_item_kit'})
        req = self.factory.delete(
            f'/api/v1/pdv/produtos/{kit.id}/itens-kit/{item.id}/',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=kit.id, item_id=item.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(ItemKit.objects.filter(pk=item.id).exists())

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.detalhes['model'], 'ItemKit')
        self.assertEqual(log.detalhes['kit_id'], kit.id)


class PedidoPDVDestroyAuditoriaTests(AuditoriaPDVTestCase):
    def setUp(self):
        super().setUp()
        self.pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero())

    def test_destroy_sem_token_401(self):
        view = PedidoPDVViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(f'/api/v1/pdv/pedidos/{self.pedido.id}/')
        resp = view(req, pk=self.pedido.id)
        self.assertEqual(resp.status_code, 401)

    def test_destroy_com_token_gera_log(self):
        view = PedidoPDVViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(
            f'/api/v1/pdv/pedidos/{self.pedido.id}/', HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.pedido.id)
        self.assertEqual(resp.status_code, 204)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.detalhes['model'], 'PedidoPDV')
        self.assertEqual(log.detalhes['numero'], self.pedido.numero)

    def test_remover_item_sem_token_401(self):
        item = ItemPedidoPDV.objects.create(pedido=self.pedido, nome='Bolo', preco_unit=20, quantidade=1)
        view = PedidoPDVViewSet.as_view({'delete': 'remover_item'})
        req = self.factory.delete(f'/api/v1/pdv/pedidos/{self.pedido.id}/itens/{item.id}/remover/')
        resp = view(req, pk=self.pedido.id, item_id=item.id)
        self.assertEqual(resp.status_code, 401)

    def test_remover_item_com_token_gera_log(self):
        item = ItemPedidoPDV.objects.create(pedido=self.pedido, nome='Bolo', preco_unit=20, quantidade=1)
        view = PedidoPDVViewSet.as_view({'delete': 'remover_item'})
        req = self.factory.delete(
            f'/api/v1/pdv/pedidos/{self.pedido.id}/itens/{item.id}/remover/',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.pedido.id, item_id=item.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(ItemPedidoPDV.objects.filter(pk=item.id).exists())

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.detalhes['model'], 'ItemPedidoPDV')
        self.assertEqual(log.detalhes['pedido_id'], self.pedido.id)


class ValorTotalItemPDVTests(AuditoriaPDVTestCase):
    """
    Regressão: o cache do prefetch_related('itens') do get_object() fica
    stale dentro da mesma request quando o item é criado/apagado via manager
    direto — recalcular_totais() lia esse cache velho e persistia um total
    errado no banco. Corrigido com refresh_from_db() antes de
    recalcular_totais() (mesmo padrão de eventos.OrcamentoViewSet/EventoViewSet).
    """
    def test_adicionar_item_atualiza_total(self):
        pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero())
        view = PedidoPDVViewSet.as_view({'post': 'adicionar_item'})
        req = self.factory.post(
            f'/api/v1/pdv/pedidos/{pedido.id}/itens/',
            {'nome': 'Bolo', 'preco_unit': '50.00', 'quantidade': 2}, format='json',
        )
        resp = view(req, pk=pedido.id)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(str(resp.data['total']), '100.00')

        pedido.refresh_from_db()
        self.assertEqual(str(pedido.total), '100.00')

    def test_remover_item_atualiza_total(self):
        pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero())
        item = ItemPedidoPDV.objects.create(pedido=pedido, nome='Bolo', preco_unit=50, quantidade=2)
        pedido.recalcular_totais()

        view = PedidoPDVViewSet.as_view({'delete': 'remover_item'})
        req = self.factory.delete(
            f'/api/v1/pdv/pedidos/{pedido.id}/itens/{item.id}/remover/',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=pedido.id, item_id=item.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(str(resp.data['total']), '0.00')

        pedido.refresh_from_db()
        self.assertEqual(str(pedido.total), '0.00')
