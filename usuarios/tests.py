from django.test import TestCase
from rest_framework.test import APIRequestFactory

from auditoria.models import LogAuditoria
from empresas.models import Empresa
from .models import Usuario
from .views import UsuarioViewSet


class AutenticacaoTokenTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = Usuario(name='Admin Teste', email='admin@teste.com', role='admin')
        self.admin.set_password('senha-123')
        self.admin.save()

    def _login(self, email, password):
        view = UsuarioViewSet.as_view({'post': 'login'})
        req = self.factory.post('/api/v1/usuarios/login/', {'email': email, 'password': password}, format='json')
        return view(req)

    def test_login_sucesso_gera_token_e_loga(self):
        resp = self._login('admin@teste.com', 'senha-123')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['token'])

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.auth_token, resp.data['token'])

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_LOGIN_SUCESSO).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)

    def test_login_senha_errada_401_e_loga_falha(self):
        resp = self._login('admin@teste.com', 'senha-errada')
        self.assertEqual(resp.status_code, 401)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_LOGIN_FALHA).latest('id')
        self.assertEqual(log.detalhes.get('motivo'), 'senha_incorreta')

    def test_login_email_inexistente_loga_sem_usuario(self):
        resp = self._login('ninguem@teste.com', 'x')
        self.assertEqual(resp.status_code, 401)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_LOGIN_FALHA).latest('id')
        self.assertIsNone(log.usuario)
        self.assertEqual(log.detalhes.get('email'), 'ninguem@teste.com')

    def test_endpoint_protegido_sem_token_401(self):
        view = UsuarioViewSet.as_view({'get': 'list'})
        req = self.factory.get('/api/v1/usuarios/')
        resp = view(req)
        self.assertEqual(resp.status_code, 401)

    def test_endpoint_protegido_com_token_200(self):
        token = self._login('admin@teste.com', 'senha-123').data['token']
        view = UsuarioViewSet.as_view({'get': 'list'})
        req = self.factory.get('/api/v1/usuarios/', HTTP_AUTHORIZATION=f'Token {token}')
        resp = view(req)
        self.assertEqual(resp.status_code, 200)

    def test_logout_invalida_token(self):
        token = self._login('admin@teste.com', 'senha-123').data['token']

        logout_view = UsuarioViewSet.as_view({'post': 'logout'})
        req = self.factory.post('/api/v1/usuarios/logout/', HTTP_AUTHORIZATION=f'Token {token}')
        resp = logout_view(req)
        self.assertEqual(resp.status_code, 204)

        self.admin.refresh_from_db()
        self.assertIsNone(self.admin.auth_token)

        list_view = UsuarioViewSet.as_view({'get': 'list'})
        req2 = self.factory.get('/api/v1/usuarios/', HTTP_AUTHORIZATION=f'Token {token}')
        resp2 = list_view(req2)
        self.assertEqual(resp2.status_code, 401)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_LOGOUT).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)


class MultiEmpresaUsuarioTests(TestCase):
    """Fase 2 do MULTIEMPRESA.md — vínculo usuário×empresa e empresa ativa."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.padrao = Empresa.get_padrao()
        self.mangaio = Empresa.objects.create(nome='Mangaio')

        self.admin = Usuario(name='Admin Teste', email='admin@teste.com', role='admin')
        self.admin.set_password('senha-123')
        self.admin.save()

        self.atendente = Usuario(name='Atendente Teste', email='atendente@teste.com', role='atendente')
        self.atendente.set_password('senha-123')
        self.atendente.save()
        self.atendente.empresas.add(self.padrao)

    def _login(self, email, password='senha-123'):
        view = UsuarioViewSet.as_view({'post': 'login'})
        req = self.factory.post('/api/v1/usuarios/login/', {'email': email, 'password': password}, format='json')
        return view(req)

    def _authed(self, usuario, method, path, data=None):
        usuario.auth_token = 'tok-' + str(usuario.id)
        usuario.save(update_fields=['auth_token'])
        factory_method = getattr(self.factory, method)
        return factory_method(path, data, format='json', HTTP_AUTHORIZATION=f'Token {usuario.auth_token}')

    def test_login_usuario_sem_vinculo_cai_na_empresa_padrao(self):
        # Usuário não-admin, nunca vinculado a nenhuma empresa — não pode bloquear o login
        sem_vinculo = Usuario(name='Sem Vinculo', email='semvinculo@teste.com', role='gerente')
        sem_vinculo.set_password('senha-123')
        sem_vinculo.save()

        resp = self._login('semvinculo@teste.com')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['empresas']), 1)
        self.assertEqual(resp.data['empresas'][0]['id'], self.padrao.id)
        self.assertEqual(resp.data['empresa_ativa']['id'], self.padrao.id)
        self.assertEqual(resp.data['preferencia_tema'], 'empresa')

    def test_login_admin_ve_todas_as_empresas_ativas(self):
        resp = self._login('admin@teste.com')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual({e['id'] for e in resp.data['empresas']}, {self.padrao.id, self.mangaio.id})

    def test_login_usuario_com_vinculo_devolve_empresas_e_ativa(self):
        resp = self._login('atendente@teste.com')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['empresas']), 1)
        self.assertEqual(resp.data['empresas'][0]['id'], self.padrao.id)
        self.assertEqual(resp.data['empresa_ativa']['id'], self.padrao.id)

    def test_definir_empresa_ativa_rejeita_empresa_nao_vinculada(self):
        view = UsuarioViewSet.as_view({'post': 'definir_empresa_ativa'})
        req = self._authed(self.atendente, 'post', '/api/v1/usuarios/definir-empresa-ativa/', {'empresa': self.mangaio.id})
        resp = view(req)
        self.assertEqual(resp.status_code, 403)

    def test_definir_empresa_ativa_admin_pode_ativar_qualquer_empresa(self):
        view = UsuarioViewSet.as_view({'post': 'definir_empresa_ativa'})
        req = self._authed(self.admin, 'post', '/api/v1/usuarios/definir-empresa-ativa/', {'empresa': self.mangaio.id})
        resp = view(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['empresa_ativa']['id'], self.mangaio.id)

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.empresa_ativa_id, self.mangaio.id)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_EMPRESA_ALTERNADA).latest('id')
        self.assertEqual(log.detalhes['para'], 'Mangaio')

    def test_definir_empresa_ativa_usuario_vinculado_funciona(self):
        self.atendente.empresas.add(self.mangaio)
        view = UsuarioViewSet.as_view({'post': 'definir_empresa_ativa'})
        req = self._authed(self.atendente, 'post', '/api/v1/usuarios/definir-empresa-ativa/', {'empresa': self.mangaio.id})
        resp = view(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['empresa_ativa']['id'], self.mangaio.id)

    def test_definir_empresa_ativa_empresa_inativa_404(self):
        self.mangaio.ativo = False
        self.mangaio.save(update_fields=['ativo'])
        view = UsuarioViewSet.as_view({'post': 'definir_empresa_ativa'})
        req = self._authed(self.admin, 'post', '/api/v1/usuarios/definir-empresa-ativa/', {'empresa': self.mangaio.id})
        resp = view(req)
        self.assertEqual(resp.status_code, 404)

    def test_preferencia_tema_grava_sem_auditar(self):
        antes = LogAuditoria.objects.count()
        view = UsuarioViewSet.as_view({'post': 'preferencia_tema'})
        req = self._authed(self.atendente, 'post', '/api/v1/usuarios/preferencia-tema/', {'tema': 'neutro_escuro'})
        resp = view(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['preferencia_tema'], 'neutro_escuro')

        self.atendente.refresh_from_db()
        self.assertEqual(self.atendente.preferencia_tema, 'neutro_escuro')
        self.assertEqual(LogAuditoria.objects.count(), antes)

    def test_preferencia_tema_invalida_400(self):
        view = UsuarioViewSet.as_view({'post': 'preferencia_tema'})
        req = self._authed(self.atendente, 'post', '/api/v1/usuarios/preferencia-tema/', {'tema': 'roxo'})
        resp = view(req)
        self.assertEqual(resp.status_code, 400)

    def test_criar_usuario_com_empresas_ids(self):
        view = UsuarioViewSet.as_view({'post': 'create'})
        req = self._authed(self.admin, 'post', '/api/v1/usuarios/', {
            'name': 'Novo Usuario', 'email': 'novo2@teste.com', 'password': '123456',
            'role': 'atendente', 'empresas_ids': [self.padrao.id, self.mangaio.id],
        })
        resp = view(req)
        self.assertEqual(resp.status_code, 201)
        criado = Usuario.objects.get(email='novo2@teste.com')
        self.assertEqual(criado.empresas.count(), 2)


class CrudUsuarioAuditoriaTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = Usuario(name='Admin Teste', email='admin@teste.com', role='admin')
        self.admin.set_password('senha-123')
        self.admin.save()

    def _authed_request(self, method, path, data=None):
        token = UsuarioViewSet.as_view({'post': 'login'})(
            self.factory.post('/api/v1/usuarios/login/', {'email': 'admin@teste.com', 'password': 'senha-123'}, format='json')
        ).data['token']
        factory_method = getattr(self.factory, method)
        return factory_method(path, data, format='json', HTTP_AUTHORIZATION=f'Token {token}')

    def test_criar_usuario_gera_log(self):
        view = UsuarioViewSet.as_view({'post': 'create'})
        req = self._authed_request('post', '/api/v1/usuarios/', {
            'name': 'Novo Usuario', 'email': 'novo@teste.com', 'password': '123456', 'role': 'atendente',
        })
        resp = view(req)
        self.assertEqual(resp.status_code, 201)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_USUARIO_CRIADO).latest('id')
        self.assertEqual(log.detalhes['criado_email'], 'novo@teste.com')

    def test_alterar_role_gera_log_permissao_alterada(self):
        alvo = Usuario(name='Alvo', email='alvo@teste.com', role='atendente')
        alvo.set_password('123456')
        alvo.save()

        view = UsuarioViewSet.as_view({'patch': 'partial_update'})
        req = self._authed_request('patch', f'/api/v1/usuarios/{alvo.id}/', {'role': 'gerente'})
        resp = view(req, pk=alvo.id)
        self.assertEqual(resp.status_code, 200)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_PERMISSAO_ALTERADA).latest('id')
        self.assertEqual(log.detalhes['role_antes'], 'atendente')
        self.assertEqual(log.detalhes['role_depois'], 'gerente')

    def test_remover_usuario_gera_log_com_snapshot(self):
        # "usuario" no log é sempre o ATOR (quem fez a ação) — aqui, o admin que exclui.
        # Os dados de quem foi removido ficam em detalhes (removido_*).
        alvo = Usuario(name='Para Remover', email='remover@teste.com', role='atendente')
        alvo.set_password('123456')
        alvo.save()
        alvo_id = alvo.id

        view = UsuarioViewSet.as_view({'delete': 'destroy'})
        req = self._authed_request('delete', f'/api/v1/usuarios/{alvo_id}/')
        resp = view(req, pk=alvo_id)
        self.assertEqual(resp.status_code, 204)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_USUARIO_REMOVIDO).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['removido_nome'], 'Para Remover')
        self.assertEqual(log.detalhes['removido_id'], alvo_id)

    def test_log_sobrevive_a_exclusao_do_proprio_ator(self):
        # Se o ATOR (quem fez a ação) for excluído depois, o log sobrevive via SET_NULL + snapshot.
        admin_id = self.admin.id
        login_view = UsuarioViewSet.as_view({'post': 'login'})
        login_view(self.factory.post(
            '/api/v1/usuarios/login/', {'email': 'admin@teste.com', 'password': 'senha-123'}, format='json',
        ))
        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_LOGIN_SUCESSO, usuario_id=admin_id).latest('id')

        self.admin.delete()

        log.refresh_from_db()
        self.assertIsNone(log.usuario_id)
        self.assertEqual(log.usuario_nome_snapshot, 'Admin Teste')
