from django.test import TestCase
from rest_framework.test import APIRequestFactory

from auditoria.models import LogAuditoria
from usuarios.models import Usuario
from usuarios.views import UsuarioViewSet
from .models import Cliente, Endereco, TagCliente
from .views import ClienteViewSet, TagViewSet


class AuditoriaClientesTestCase(TestCase):
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


class ClienteDestroyAuditoriaTests(AuditoriaClientesTestCase):
    def setUp(self):
        super().setUp()
        self.cliente = Cliente.objects.create(nome='Maria Teste', telefone_principal='86999998888')

    def test_destroy_sem_token_401(self):
        view = ClienteViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(f'/api/v1/clientes/{self.cliente.id}/')
        resp = view(req, pk=self.cliente.id)
        self.assertEqual(resp.status_code, 401)
        self.assertTrue(Cliente.objects.filter(pk=self.cliente.id).exists())

    def test_destroy_com_token_gera_log(self):
        view = ClienteViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(
            f'/api/v1/clientes/{self.cliente.id}/', HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.cliente.id)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Cliente.objects.filter(pk=self.cliente.id).exists())

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['model'], 'Cliente')
        self.assertEqual(log.detalhes['nome'], 'Maria Teste')

    def test_remover_endereco_sem_token_401(self):
        endereco = Endereco.objects.create(
            cliente=self.cliente, cep='64000-000', logradouro='Rua A', numero='1',
            bairro='Centro', cidade='Teresina', estado='PI',
        )
        view = ClienteViewSet.as_view({'delete': 'remover_endereco'})
        req = self.factory.delete(f'/api/v1/clientes/{self.cliente.id}/enderecos/{endereco.id}/remover/')
        resp = view(req, pk=self.cliente.id, endereco_id=endereco.id)
        self.assertEqual(resp.status_code, 401)
        self.assertTrue(Endereco.objects.filter(pk=endereco.id).exists())

    def test_remover_endereco_com_token_gera_log(self):
        endereco = Endereco.objects.create(
            cliente=self.cliente, cep='64000-000', logradouro='Rua A', numero='1',
            bairro='Centro', cidade='Teresina', estado='PI',
        )
        view = ClienteViewSet.as_view({'delete': 'remover_endereco'})
        req = self.factory.delete(
            f'/api/v1/clientes/{self.cliente.id}/enderecos/{endereco.id}/remover/',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.cliente.id, endereco_id=endereco.id)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Endereco.objects.filter(pk=endereco.id).exists())

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['model'], 'Endereco')
        self.assertEqual(log.detalhes['cliente_id'], self.cliente.id)


class TagDestroyAuditoriaTests(AuditoriaClientesTestCase):
    def setUp(self):
        super().setUp()
        self.tag = TagCliente.objects.create(nome='VIP')

    def test_destroy_sem_token_401(self):
        view = TagViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(f'/api/v1/tags/{self.tag.id}/')
        resp = view(req, pk=self.tag.id)
        self.assertEqual(resp.status_code, 401)

    def test_destroy_com_token_gera_log(self):
        view = TagViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(
            f'/api/v1/tags/{self.tag.id}/', HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.tag.id)
        self.assertEqual(resp.status_code, 204)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.detalhes['model'], 'TagCliente')
        self.assertEqual(log.detalhes['nome'], 'VIP')
