import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from usuarios.models import Usuario
from usuarios.views import UsuarioViewSet
from .models import LogAuditoria, PresencaEdicao
from .views import LogAuditoriaViewSet, PresencaHeartbeatView, JANELA_PRESENCA_SEGUNDOS


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


class PresencaHeartbeatTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user1 = Usuario(name='Usuario Um', email='um@teste.com', role='atendente')
        self.user1.set_password('senha-123')
        self.user1.save()
        self.user2 = Usuario(name='Usuario Dois', email='dois@teste.com', role='atendente')
        self.user2.set_password('senha-123')
        self.user2.save()

    def _token(self, email):
        resp = UsuarioViewSet.as_view({'post': 'login'})(self.factory.post(
            '/api/v1/usuarios/login/', {'email': email, 'password': 'senha-123'}, format='json',
        ))
        return resp.data['token']

    def _heartbeat(self, token=None):
        view = PresencaHeartbeatView.as_view()
        extra = {'HTTP_AUTHORIZATION': f'Token {token}'} if token else {}
        req = self.factory.post(
            '/api/v1/auditoria/presenca/', {'model': 'Orcamento', 'objeto_id': 7}, format='json', **extra,
        )
        return view(req)

    def test_sem_token_401(self):
        resp = self._heartbeat()
        self.assertEqual(resp.status_code, 401)

    def test_primeiro_heartbeat_retorna_so_o_proprio_usuario(self):
        resp = self._heartbeat(token=self._token('um@teste.com'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['usuarios']), 1)
        self.assertEqual(resp.data['usuarios'][0]['id'], self.user1.id)

    def test_dois_usuarios_heartbeat_aparecem_ambos(self):
        self._heartbeat(token=self._token('um@teste.com'))
        resp = self._heartbeat(token=self._token('dois@teste.com'))
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {u['id'] for u in resp.data['usuarios']}
        self.assertEqual(ids, {self.user1.id, self.user2.id})

    def test_heartbeat_antigo_fora_da_janela_nao_aparece(self):
        self._heartbeat(token=self._token('um@teste.com'))
        # auto_now não deixa setar atualizado_em no create, então força via update()
        # no queryset (contorna o auto_now, que só age em .save())
        limite_passado = timezone.now() - datetime.timedelta(seconds=JANELA_PRESENCA_SEGUNDOS + 10)
        PresencaEdicao.objects.filter(usuario=self.user1).update(atualizado_em=limite_passado)

        resp = self._heartbeat(token=self._token('dois@teste.com'))
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {u['id'] for u in resp.data['usuarios']}
        self.assertEqual(ids, {self.user2.id})

    def test_heartbeats_repetidos_nao_duplicam_linha(self):
        token = self._token('um@teste.com')
        self._heartbeat(token=token)
        self._heartbeat(token=token)
        self._heartbeat(token=token)
        self.assertEqual(PresencaEdicao.objects.filter(usuario=self.user1).count(), 1)

    def test_sem_model_ou_objeto_id_retorna_400(self):
        view = PresencaHeartbeatView.as_view()
        req = self.factory.post(
            '/api/v1/auditoria/presenca/', {}, format='json',
            HTTP_AUTHORIZATION=f'Token {self._token("um@teste.com")}',
        )
        resp = view(req)
        self.assertEqual(resp.status_code, 400)
