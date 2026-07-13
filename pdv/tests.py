from django.test import TestCase
from rest_framework.test import APIRequestFactory

from auditoria.models import LogAuditoria
from usuarios.models import Usuario
from usuarios.views import UsuarioViewSet
from .models import ConfiguracaoEntrega
from .views import ConfiguracaoEntregaViewSet


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
