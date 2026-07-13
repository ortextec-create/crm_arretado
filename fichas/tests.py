from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from auditoria.models import LogAuditoria
from usuarios.models import Usuario
from usuarios.views import UsuarioViewSet
from pdv.models import Produto
from .models import FichaTecnica, ItemFichaTecnica, MateriaPrima, ParametrosNegocio, SnapshotPrecos
from .views import (
    AjusteLinearView, DesfazerAjusteView, FichaTecnicaViewSet,
    MateriaPrimaViewSet, ParametrosNegocioViewSet,
)


class AuditoriaFichasTestCase(TestCase):
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


class AjusteLinearAuditoriaTests(AuditoriaFichasTestCase):
    def setUp(self):
        super().setUp()
        self.produto = Produto.objects.create(nome='Bolo Teste', preco=100, segmento='outro')

    def _post(self, data, token=None):
        view = AjusteLinearView.as_view()
        extra = {'HTTP_AUTHORIZATION': f'Token {token}'} if token else {}
        req = self.factory.post('/api/v1/fichas/ajuste-linear/', data, format='json', **extra)
        return view(req)

    def test_preview_sem_confirmar_nao_exige_login(self):
        resp = self._post({'valor': '10', 'confirmar': False})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('preview', resp.data)

    def test_aplicar_sem_token_401(self):
        resp = self._post({'valor': '10', 'confirmar': True})
        self.assertEqual(resp.status_code, 401)

    def test_aplicar_com_token_gera_log(self):
        resp = self._post({'valor': '10', 'confirmar': True}, token=self._token())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['aplicado'])

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.preco, 110)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_AJUSTE_LINEAR_APLICADO).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['total_produtos'], 1)

    def test_desfazer_sem_token_401(self):
        self._post({'valor': '10', 'confirmar': True}, token=self._token())
        snapshot = SnapshotPrecos.objects.latest('id')

        view = DesfazerAjusteView.as_view()
        req = self.factory.post(f'/api/v1/fichas/desfazer-ajuste/{snapshot.id}/', format='json')
        resp = view(req, snapshot_id=snapshot.id)
        self.assertEqual(resp.status_code, 401)

    def test_desfazer_com_token_gera_log(self):
        self._post({'valor': '10', 'confirmar': True}, token=self._token())
        snapshot = SnapshotPrecos.objects.latest('id')

        view = DesfazerAjusteView.as_view()
        req = self.factory.post(
            f'/api/v1/fichas/desfazer-ajuste/{snapshot.id}/', format='json',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, snapshot_id=snapshot.id)
        self.assertEqual(resp.status_code, 200, resp.data)

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.preco, 100)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_AJUSTE_LINEAR_DESFEITO).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['snapshot_id'], snapshot.id)


class MateriaPrimaAuditoriaTests(AuditoriaFichasTestCase):
    def setUp(self):
        super().setUp()
        self.materia = MateriaPrima.objects.create(
            nome='Chocolate', unidade_medida='g', valor_compra=10, quantidade_compra=1,
        )

    def _post(self, token=None):
        view = MateriaPrimaViewSet.as_view({'post': 'atualizar_preco'})
        extra = {'HTTP_AUTHORIZATION': f'Token {token}'} if token else {}
        req = self.factory.post(
            f'/api/v1/fichas/materias-primas/{self.materia.id}/atualizar-preco/',
            {'valor_compra': '15.00'}, format='json', **extra,
        )
        return view(req, pk=self.materia.id)

    def test_sem_token_401(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 401)

    def test_com_token_gera_log(self):
        resp = self._post(token=self._token())
        self.assertEqual(resp.status_code, 200, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_PRECO_MATERIA_ATUALIZADO).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(Decimal(log.detalhes['valor_antigo']), Decimal('10'))
        self.assertEqual(Decimal(log.detalhes['valor_novo']), Decimal('15.00'))


class MateriaPrimaDestroyAuditoriaTests(AuditoriaFichasTestCase):
    def setUp(self):
        super().setUp()
        self.materia = MateriaPrima.objects.create(
            nome='Chocolate', unidade_medida='g', valor_compra=10, quantidade_compra=1,
        )

    def _delete(self, token=None):
        view = MateriaPrimaViewSet.as_view({'delete': 'destroy'})
        extra = {'HTTP_AUTHORIZATION': f'Token {token}'} if token else {}
        req = self.factory.delete(f'/api/v1/fichas/materias-primas/{self.materia.id}/', **extra)
        return view(req, pk=self.materia.id)

    def test_sem_token_401(self):
        resp = self._delete()
        self.assertEqual(resp.status_code, 401)
        self.assertTrue(MateriaPrima.objects.filter(pk=self.materia.id).exists())

    def test_com_token_exclui_e_gera_log(self):
        resp = self._delete(token=self._token())
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(MateriaPrima.objects.filter(pk=self.materia.id).exists())

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['model'], 'MateriaPrima')
        self.assertEqual(log.detalhes['id'], self.materia.id)
        self.assertEqual(log.detalhes['nome'], 'Chocolate')

    def test_protegida_por_item_ficha_tecnica_retorna_400(self):
        ficha = FichaTecnica.objects.create(nome='Bolo Teste')
        ItemFichaTecnica.objects.create(ficha=ficha, materia_prima=self.materia, quantidade=1)

        resp = self._delete(token=self._token())
        resp.render()
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(MateriaPrima.objects.filter(pk=self.materia.id).exists())
        self.assertFalse(LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).exists())

    def test_protegida_por_produto_revenda_retorna_400(self):
        Produto.objects.create(
            nome='Chocolate Revenda', preco=20, segmento='outro',
            tipo='revenda', materia_prima_origem=self.materia,
        )

        resp = self._delete(token=self._token())
        resp.render()
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(MateriaPrima.objects.filter(pk=self.materia.id).exists())


class FichaTecnicaDestroyAuditoriaTests(AuditoriaFichasTestCase):
    def setUp(self):
        super().setUp()
        self.ficha = FichaTecnica.objects.create(nome='Bolo Teste')
        self.materia = MateriaPrima.objects.create(
            nome='Chocolate', unidade_medida='g', valor_compra=10, quantidade_compra=1,
        )

    def test_destroy_sem_token_401(self):
        view = FichaTecnicaViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(f'/api/v1/fichas/fichas/{self.ficha.id}/')
        resp = view(req, pk=self.ficha.id)
        self.assertEqual(resp.status_code, 401)

    def test_destroy_com_token_gera_log(self):
        view = FichaTecnicaViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(
            f'/api/v1/fichas/fichas/{self.ficha.id}/', HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.ficha.id)
        self.assertEqual(resp.status_code, 204)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.detalhes['model'], 'FichaTecnica')
        self.assertEqual(log.detalhes['nome'], 'Bolo Teste')

    def test_remover_item_sem_token_401(self):
        item = ItemFichaTecnica.objects.create(ficha=self.ficha, materia_prima=self.materia, quantidade=1)
        view = FichaTecnicaViewSet.as_view({'delete': 'remover_item'})
        req = self.factory.delete(f'/api/v1/fichas/fichas/{self.ficha.id}/remover-item/{item.id}/')
        resp = view(req, pk=self.ficha.id, item_id=item.id)
        self.assertEqual(resp.status_code, 401)
        self.assertTrue(ItemFichaTecnica.objects.filter(pk=item.id).exists())

    def test_remover_item_com_token_gera_log(self):
        item = ItemFichaTecnica.objects.create(ficha=self.ficha, materia_prima=self.materia, quantidade=1)
        view = FichaTecnicaViewSet.as_view({'delete': 'remover_item'})
        req = self.factory.delete(
            f'/api/v1/fichas/fichas/{self.ficha.id}/remover-item/{item.id}/',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.ficha.id, item_id=item.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(ItemFichaTecnica.objects.filter(pk=item.id).exists())

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.detalhes['model'], 'ItemFichaTecnica')
        self.assertEqual(log.detalhes['ficha_id'], self.ficha.id)


class ParametrosNegocioAuditoriaTests(AuditoriaFichasTestCase):
    def _patch(self, token=None):
        view = ParametrosNegocioViewSet.as_view({'patch': 'partial_update'})
        extra = {'HTTP_AUTHORIZATION': f'Token {token}'} if token else {}
        req = self.factory.patch(
            '/api/v1/fichas/parametros/1/', {'margem_lucro_esperada_pct': '0.35'}, format='json', **extra,
        )
        return view(req, pk=1)

    def test_sem_token_401(self):
        resp = self._patch()
        self.assertEqual(resp.status_code, 401)

    def test_com_token_gera_log(self):
        resp = self._patch(token=self._token())
        self.assertEqual(resp.status_code, 200, resp.data)

        params = ParametrosNegocio.get()
        self.assertEqual(str(params.margem_lucro_esperada_pct), '0.3500')

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_PARAMETROS_NEGOCIO_ALTERADOS).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['depois']['margem_lucro_esperada_pct'], '0.3500')

    def test_get_nao_exige_login(self):
        view = ParametrosNegocioViewSet.as_view({'get': 'retrieve'})
        req = self.factory.get('/api/v1/fichas/parametros/1/')
        resp = view(req, pk=1)
        self.assertEqual(resp.status_code, 200)
