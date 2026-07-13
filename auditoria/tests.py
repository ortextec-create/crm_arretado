from django.test import TestCase
from rest_framework.test import APIRequestFactory

from usuarios.models import Usuario
from usuarios.views import UsuarioViewSet
from .models import LogAuditoria
from .views import LogAuditoriaViewSet


class LogAuditoriaPermissaoTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = Usuario(name='Admin', email='admin@teste.com', role='admin')
        self.admin.set_password('senha-123')
        self.admin.save()
        self.atendente = Usuario(name='Atendente', email='atendente@teste.com', role='atendente')
        self.atendente.set_password('senha-123')
        self.atendente.save()

    def _token(self, email, password):
        login_view = UsuarioViewSet.as_view({'post': 'login'})
        resp = login_view(self.factory.post(
            '/api/v1/usuarios/login/', {'email': email, 'password': password}, format='json',
        ))
        return resp.data['token']

    def test_nao_admin_recebe_403(self):
        token = self._token('atendente@teste.com', 'senha-123')
        view = LogAuditoriaViewSet.as_view({'get': 'list'})
        req = self.factory.get('/api/v1/auditoria/logs/', HTTP_AUTHORIZATION=f'Token {token}')
        resp = view(req)
        self.assertEqual(resp.status_code, 403)

    def test_admin_recebe_200_e_ve_logs(self):
        token = self._token('admin@teste.com', 'senha-123')
        view = LogAuditoriaViewSet.as_view({'get': 'list'})
        req = self.factory.get('/api/v1/auditoria/logs/', HTTP_AUTHORIZATION=f'Token {token}')
        resp = view(req)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data['count'], 1)

    def test_filtro_por_acao(self):
        token = self._token('admin@teste.com', 'senha-123')
        # gera um login_falha extra
        UsuarioViewSet.as_view({'post': 'login'})(self.factory.post(
            '/api/v1/usuarios/login/', {'email': 'admin@teste.com', 'password': 'errada'}, format='json',
        ))

        view = LogAuditoriaViewSet.as_view({'get': 'list'})
        req = self.factory.get('/api/v1/auditoria/logs/?acao=login_falha', HTTP_AUTHORIZATION=f'Token {token}')
        resp = view(req)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(all(item['acao'] == LogAuditoria.ACAO_LOGIN_FALHA for item in resp.data['results']))
