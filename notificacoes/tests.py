from django.test import TestCase
from rest_framework.test import APIRequestFactory

from auditoria.models import LogAuditoria
from usuarios.models import Usuario
from usuarios.views import UsuarioViewSet
from .models import ConfiguracaoWhatsApp
from .views import ConfiguracaoWhatsAppViewSet


class ConfiguracaoWhatsAppAuditoriaTests(TestCase):
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

    def test_get_sem_token_401(self):
        view = ConfiguracaoWhatsAppViewSet.as_view({'get': 'retrieve'})
        resp = view(self.factory.get('/api/v1/notificacoes/configuracao/'))
        self.assertEqual(resp.status_code, 401)

    def test_get_com_token_200(self):
        view = ConfiguracaoWhatsAppViewSet.as_view({'get': 'retrieve'})
        req = self.factory.get('/api/v1/notificacoes/configuracao/', HTTP_AUTHORIZATION=f'Token {self._token()}')
        resp = view(req)
        self.assertEqual(resp.status_code, 200)

    def test_patch_sem_token_401(self):
        view = ConfiguracaoWhatsAppViewSet.as_view({'patch': 'partial_update'})
        req = self.factory.patch('/api/v1/notificacoes/configuracao/', {'zapi_token': 'novo-token-secreto'}, format='json')
        resp = view(req)
        self.assertEqual(resp.status_code, 401)

    def test_patch_com_token_gera_log_mascarado(self):
        view = ConfiguracaoWhatsAppViewSet.as_view({'patch': 'partial_update'})
        req = self.factory.patch(
            '/api/v1/notificacoes/configuracao/', {'zapi_token': 'novo-token-secreto'}, format='json',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req)
        self.assertEqual(resp.status_code, 200, resp.data)

        cfg = ConfiguracaoWhatsApp.get()
        self.assertEqual(cfg.zapi_token, 'novo-token-secreto')

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_CONFIG_WHATSAPP_ALTERADA).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['depois']['zapi_token'], '***')
        self.assertNotIn('novo-token-secreto', str(log.detalhes))
