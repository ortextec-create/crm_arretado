import datetime
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from django.core.files.uploadedfile import SimpleUploadedFile

from clientes.models import Cliente
from notificacoes.models import HistoricoMensagem
from auditoria.models import LogAuditoria
from usuarios.models import Usuario
from usuarios.views import UsuarioViewSet
from .models import (
    Orcamento, ItemOrcamento, ImagemInspiracao, Contrato, Evento, ItemEvento,
    LocalEvento, PagamentoEvento, ConfiguracaoContrato,
)
from .views import (
    OrcamentoViewSet, ContratoViewSet, EventoViewSet, LocalEventoViewSet, ConfiguracaoContratoViewSet,
)

GIF_1PX = SimpleUploadedFile(
    'inspiracao.gif', b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x01D\x00;',
    content_type='image/gif',
)


class GerarContratoTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = Usuario(name='Admin Teste', email='admin@teste.com', role='admin')
        self.admin.set_password('senha-123')
        self.admin.save()

        self.cliente = Cliente.objects.create(
            nome='Maria Teste', telefone_principal='86999998888',
        )
        self.orc = Orcamento.objects.create(
            numero=Orcamento.proximo_numero(),
            cliente=self.cliente,
            tipo_evento='aniversario',
            data_evento=datetime.date.today() + datetime.timedelta(days=30),
            status='aprovado',
        )
        ItemOrcamento.objects.create(
            orcamento=self.orc, nome='Bolo teste', preco_unit=100, quantidade=2, preco_total=200,
        )
        self.orc.recalcular_totais()
        self.orc.refresh_from_db()

    def _token(self):
        resp = UsuarioViewSet.as_view({'post': 'login'})(self.factory.post(
            '/api/v1/usuarios/login/', {'email': 'admin@teste.com', 'password': 'senha-123'}, format='json',
        ))
        return resp.data['token']

    def _post(self, data, autenticado=True):
        view = OrcamentoViewSet.as_view({'post': 'gerar_contrato'})
        extra = {'HTTP_AUTHORIZATION': f'Token {self._token()}'} if autenticado else {}
        req = self.factory.post(
            f'/api/v1/eventos/orcamentos/{self.orc.id}/gerar-contrato/', data, format='json', **extra,
        )
        return view(req, pk=self.orc.id)

    def test_bloqueia_sem_token_401(self):
        resp = self._post({}, autenticado=False)
        self.assertEqual(resp.status_code, 401)

    def test_bloqueia_se_orcamento_nao_aprovado(self):
        self.orc.status = 'rascunho'
        self.orc.save(update_fields=['status'])
        resp = self._post({})
        self.assertEqual(resp.status_code, 400)

    def test_bloqueia_dados_incompletos(self):
        resp = self._post({})
        resp.render()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['detail'], 'dados_incompletos')
        self.assertIn('cpf', resp.data['campos_faltando'])
        self.assertIn('rg', resp.data['campos_faltando'])
        self.assertFalse(Contrato.objects.exists())

    def test_gera_contrato_com_dados_completos(self):
        payload = {
            'cpf': '123.456.789-00',
            'rg': '1234567',
            'rg_orgao_emissor': 'SSP-PI',
            'nacionalidade': 'brasileira',
            'profissao': 'Professora',
            'estado_civil': 'solteiro',
            'endereco_avulso': 'Rua das Flores, 100 - Centro, Teresina/PI',
        }
        resp = self._post(payload)
        resp.render()
        self.assertEqual(resp.status_code, 201, resp.data)

        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.cpf, payload['cpf'])
        self.assertEqual(self.cliente.rg, payload['rg'])

        contrato = Contrato.objects.get(orcamento=self.orc)
        self.assertEqual(contrato.numero, 'CTR-0001')
        self.assertEqual(contrato.contratante_cpf, payload['cpf'])
        self.assertEqual(contrato.valor_total, self.orc.valor_total)
        self.assertEqual(contrato.percentual_sinal, 50)
        self.assertEqual(contrato.valor_sinal, self.orc.valor_total * 50 / 100)
        self.assertEqual(contrato.data_quitacao, self.orc.data_evento - datetime.timedelta(days=7))

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_CONTRATO_EMITIDO).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['contrato_numero'], contrato.numero)
        return contrato

    def test_pdf_gera_bytes_validos(self):
        contrato = self.test_gera_contrato_com_dados_completos()
        from .pdf_contrato import gerar_pdf_contrato
        pdf_bytes = gerar_pdf_contrato(contrato)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        self.assertGreater(len(pdf_bytes), 1000)

    @patch('notificacoes.servico.zapi.enviar_documento')
    def test_enviar_whatsapp_marca_status_e_grava_historico(self, mock_enviar):
        mock_enviar.return_value = {'messageId': 'abc123'}
        contrato = self.test_gera_contrato_com_dados_completos()

        view = ContratoViewSet.as_view({'post': 'enviar_whatsapp'})
        req = self.factory.post(
            f'/api/v1/eventos/contratos/{contrato.id}/enviar-whatsapp/', {}, format='json',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=contrato.id)
        resp.render()
        self.assertEqual(resp.status_code, 200, resp.data)

        contrato.refresh_from_db()
        self.assertEqual(contrato.status, 'enviado')

        msg = HistoricoMensagem.objects.filter(cliente=self.cliente, tipo='contrato').first()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.status, 'enviado')

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_CONTRATO_ENVIADO).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['contrato_numero'], contrato.numero)

    def test_enviar_whatsapp_sem_token_401(self):
        contrato = self.test_gera_contrato_com_dados_completos()
        view = ContratoViewSet.as_view({'post': 'enviar_whatsapp'})
        req = self.factory.post(
            f'/api/v1/eventos/contratos/{contrato.id}/enviar-whatsapp/', {}, format='json',
        )
        resp = view(req, pk=contrato.id)
        self.assertEqual(resp.status_code, 401)


class PagamentoEventoAuditoriaTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = Usuario(name='Admin Teste', email='admin@teste.com', role='admin')
        self.admin.set_password('senha-123')
        self.admin.save()

        self.cliente = Cliente.objects.create(nome='Cliente Teste', telefone_principal='86999998888')
        self.evento = Evento.objects.create(
            numero=Evento.proximo_numero(),
            cliente=self.cliente,
            tipo_evento='aniversario',
            data_evento=datetime.date.today() + datetime.timedelta(days=10),
            status='orcamento',
        )

    def _token(self):
        resp = UsuarioViewSet.as_view({'post': 'login'})(self.factory.post(
            '/api/v1/usuarios/login/', {'email': 'admin@teste.com', 'password': 'senha-123'}, format='json',
        ))
        return resp.data['token']

    def test_adicionar_pagamento_sem_token_401(self):
        view = EventoViewSet.as_view({'post': 'adicionar_pagamento'})
        req = self.factory.post(f'/api/v1/eventos/{self.evento.id}/pagamentos/', {
            'valor': '100.00', 'forma_pagamento': 'pix', 'status': 'pago',
            'data_pagamento': str(datetime.date.today()),
        }, format='json')
        resp = view(req, pk=self.evento.id)
        self.assertEqual(resp.status_code, 401)

    def test_adicionar_pagamento_com_token_gera_log(self):
        token = self._token()
        view = EventoViewSet.as_view({'post': 'adicionar_pagamento'})
        req = self.factory.post(f'/api/v1/eventos/{self.evento.id}/pagamentos/', {
            'valor': '150.00', 'forma_pagamento': 'pix', 'status': 'pago',
            'data_pagamento': str(datetime.date.today()),
        }, format='json', HTTP_AUTHORIZATION=f'Token {token}')
        resp = view(req, pk=self.evento.id)
        self.assertEqual(resp.status_code, 201, resp.data)

        self.evento.refresh_from_db()
        self.assertEqual(str(self.evento.sinal_pago), '150.00')

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_PAGAMENTO_REGISTRADO).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['valor'], '150.00')
        self.assertEqual(log.detalhes['origem'], 'action_pagamentos')

    def test_remover_pagamento_sem_token_401(self):
        pagamento = PagamentoEvento.objects.create(evento=self.evento, valor=100, forma_pagamento='pix')
        view = EventoViewSet.as_view({'delete': 'remover_pagamento'})
        req = self.factory.delete(f'/api/v1/eventos/{self.evento.id}/pagamentos/{pagamento.id}/remover/')
        resp = view(req, pk=self.evento.id, pagamento_id=pagamento.id)
        self.assertEqual(resp.status_code, 401)

    def test_remover_pagamento_com_token_gera_log(self):
        pagamento = PagamentoEvento.objects.create(evento=self.evento, valor=100, forma_pagamento='pix')
        token = self._token()
        view = EventoViewSet.as_view({'delete': 'remover_pagamento'})
        req = self.factory.delete(
            f'/api/v1/eventos/{self.evento.id}/pagamentos/{pagamento.id}/remover/',
            HTTP_AUTHORIZATION=f'Token {token}',
        )
        resp = view(req, pk=self.evento.id, pagamento_id=pagamento.id)
        self.assertEqual(resp.status_code, 200, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_PAGAMENTO_REMOVIDO).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['pagamento_id'], pagamento.id)

    def test_criar_evento_sem_token_401(self):
        # create() do EventoViewSet passou a exigir login (ver AuditoriaCreateMixin/
        # ACAO_REGISTRO_CRIADO) — antes desta feature, criar Evento sem token era
        # permitido e o pagamento do sinal era logado com usuario=None.
        view = EventoViewSet.as_view({'post': 'create'})
        req = self.factory.post('/api/v1/eventos/', {
            'cliente_nome': 'Fulano', 'cliente_telefone': '86999997777',
            'tipo_evento': 'aniversario', 'data_evento': str(datetime.date.today() + datetime.timedelta(days=5)),
            'sinal_pago': '80.00',
        }, format='json')
        resp = view(req)
        self.assertEqual(resp.status_code, 401)

    def test_criar_evento_com_sinal_com_token_loga_com_usuario(self):
        token = self._token()
        view = EventoViewSet.as_view({'post': 'create'})
        req = self.factory.post('/api/v1/eventos/', {
            'cliente_nome': 'Fulano', 'cliente_telefone': '86999997777',
            'tipo_evento': 'aniversario', 'data_evento': str(datetime.date.today() + datetime.timedelta(days=5)),
            'sinal_pago': '80.00',
        }, format='json', HTTP_AUTHORIZATION=f'Token {token}')
        resp = view(req)
        self.assertEqual(resp.status_code, 201, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_PAGAMENTO_REGISTRADO, detalhes__origem='criacao_evento').latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)

    def test_converter_orcamento_com_sinal_com_token_loga_com_usuario(self):
        orc = Orcamento.objects.create(
            numero=Orcamento.proximo_numero(),
            cliente=self.cliente,
            tipo_evento='aniversario',
            data_evento=datetime.date.today() + datetime.timedelta(days=20),
            status='aprovado',
        )
        token = self._token()
        view = OrcamentoViewSet.as_view({'post': 'converter_em_evento'})
        req = self.factory.post(
            f'/api/v1/eventos/orcamentos/{orc.id}/converter-em-evento/',
            {'sinal_pago': '50.00'}, format='json', HTTP_AUTHORIZATION=f'Token {token}',
        )
        resp = view(req, pk=orc.id)
        self.assertEqual(resp.status_code, 201, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_PAGAMENTO_REGISTRADO, detalhes__origem='conversao_orcamento').latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)


class ConfiguracaoContratoAuditoriaTests(TestCase):
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
        view = ConfiguracaoContratoViewSet.as_view({'get': 'retrieve'})
        resp = view(self.factory.get('/api/v1/eventos/configuracao-contrato/1/'), pk=1)
        self.assertEqual(resp.status_code, 200)

    def test_patch_sem_token_401(self):
        view = ConfiguracaoContratoViewSet.as_view({'patch': 'partial_update'})
        req = self.factory.patch('/api/v1/eventos/configuracao-contrato/1/', {'percentual_sinal': '40'}, format='json')
        resp = view(req, pk=1)
        self.assertEqual(resp.status_code, 401)

    def test_patch_com_token_gera_log(self):
        view = ConfiguracaoContratoViewSet.as_view({'patch': 'partial_update'})
        req = self.factory.patch(
            '/api/v1/eventos/configuracao-contrato/1/', {'percentual_sinal': '40'}, format='json',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=1)
        self.assertEqual(resp.status_code, 200, resp.data)

        cfg = ConfiguracaoContrato.get()
        self.assertEqual(str(cfg.percentual_sinal), '40.00')

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_CONFIG_CONTRATO_ALTERADA).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['depois']['percentual_sinal'], '40.00')


class AuditoriaEventosDestroyTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = Usuario(name='Admin Teste', email='admin@teste.com', role='admin')
        self.admin.set_password('senha-123')
        self.admin.save()
        self.cliente = Cliente.objects.create(nome='Cliente Teste', telefone_principal='86999998888')

    def _token(self):
        resp = UsuarioViewSet.as_view({'post': 'login'})(self.factory.post(
            '/api/v1/usuarios/login/', {'email': 'admin@teste.com', 'password': 'senha-123'}, format='json',
        ))
        return resp.data['token']


class LocalEventoDestroyAuditoriaTests(AuditoriaEventosDestroyTestCase):
    def setUp(self):
        super().setUp()
        self.local = LocalEvento.objects.create(nome='Salão de Festas')

    def test_destroy_sem_token_401(self):
        view = LocalEventoViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(f'/api/v1/eventos/locais/{self.local.id}/')
        resp = view(req, pk=self.local.id)
        self.assertEqual(resp.status_code, 401)

    def test_destroy_com_token_gera_log(self):
        view = LocalEventoViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(
            f'/api/v1/eventos/locais/{self.local.id}/', HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.local.id)
        self.assertEqual(resp.status_code, 204)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.detalhes['model'], 'LocalEvento')
        self.assertEqual(log.detalhes['nome'], 'Salão de Festas')


class EventoDestroyAuditoriaTests(AuditoriaEventosDestroyTestCase):
    def setUp(self):
        super().setUp()
        self.evento = Evento.objects.create(
            numero=Evento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario',
            data_evento=datetime.date.today() + datetime.timedelta(days=10), status='orcamento',
        )

    def test_destroy_sem_token_401(self):
        view = EventoViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(f'/api/v1/eventos/{self.evento.id}/')
        resp = view(req, pk=self.evento.id)
        self.assertEqual(resp.status_code, 401)
        self.assertTrue(Evento.objects.filter(pk=self.evento.id).exists())

    def test_destroy_com_token_gera_log(self):
        view = EventoViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(
            f'/api/v1/eventos/{self.evento.id}/', HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.evento.id)
        self.assertEqual(resp.status_code, 204)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.detalhes['model'], 'Evento')
        self.assertEqual(log.detalhes['numero'], self.evento.numero)

    def test_remover_item_sem_token_401(self):
        item = ItemEvento.objects.create(evento=self.evento, nome='Bolo', preco_unit=50, quantidade=1)
        view = EventoViewSet.as_view({'delete': 'remover_item'})
        req = self.factory.delete(f'/api/v1/eventos/{self.evento.id}/itens/{item.id}/remover/')
        resp = view(req, pk=self.evento.id, item_id=item.id)
        self.assertEqual(resp.status_code, 401)

    def test_remover_item_com_token_gera_log(self):
        item = ItemEvento.objects.create(evento=self.evento, nome='Bolo', preco_unit=50, quantidade=1)
        view = EventoViewSet.as_view({'delete': 'remover_item'})
        req = self.factory.delete(
            f'/api/v1/eventos/{self.evento.id}/itens/{item.id}/remover/',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.evento.id, item_id=item.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(ItemEvento.objects.filter(pk=item.id).exists())

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.detalhes['model'], 'ItemEvento')
        self.assertEqual(log.detalhes['evento_id'], self.evento.id)


class OrcamentoDestroyAuditoriaTests(AuditoriaEventosDestroyTestCase):
    def setUp(self):
        super().setUp()
        self.orc = Orcamento.objects.create(
            numero=Orcamento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario',
            data_evento=datetime.date.today() + datetime.timedelta(days=30), status='rascunho',
        )

    def test_destroy_sem_token_401(self):
        view = OrcamentoViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(f'/api/v1/eventos/orcamentos/{self.orc.id}/')
        resp = view(req, pk=self.orc.id)
        self.assertEqual(resp.status_code, 401)

    def test_destroy_com_token_gera_log(self):
        view = OrcamentoViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(
            f'/api/v1/eventos/orcamentos/{self.orc.id}/', HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.orc.id)
        self.assertEqual(resp.status_code, 204)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.detalhes['model'], 'Orcamento')
        self.assertEqual(log.detalhes['numero'], self.orc.numero)

    def test_protegido_por_contrato_retorna_400(self):
        Contrato.objects.create(
            numero=Contrato.proximo_numero(), orcamento=self.orc,
            contratante_nome='Maria', contratante_nacionalidade='brasileira',
            contratante_cpf='123.456.789-00', contratante_endereco='Rua A, 1',
            data_evento=self.orc.data_evento, valor_total=100,
            percentual_sinal=50, valor_sinal=50, data_quitacao=self.orc.data_evento,
        )
        view = OrcamentoViewSet.as_view({'delete': 'destroy'})
        req = self.factory.delete(
            f'/api/v1/eventos/orcamentos/{self.orc.id}/', HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.orc.id)
        resp.render()
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(Orcamento.objects.filter(pk=self.orc.id).exists())

    def test_remover_item_sem_token_401(self):
        item = ItemOrcamento.objects.create(orcamento=self.orc, nome='Bolo', preco_unit=50, quantidade=1)
        view = OrcamentoViewSet.as_view({'delete': 'remover_item'})
        req = self.factory.delete(f'/api/v1/eventos/orcamentos/{self.orc.id}/itens/{item.id}/remover/')
        resp = view(req, pk=self.orc.id, item_id=item.id)
        self.assertEqual(resp.status_code, 401)

    def test_remover_item_com_token_gera_log(self):
        item = ItemOrcamento.objects.create(orcamento=self.orc, nome='Bolo', preco_unit=50, quantidade=1)
        view = OrcamentoViewSet.as_view({'delete': 'remover_item'})
        req = self.factory.delete(
            f'/api/v1/eventos/orcamentos/{self.orc.id}/itens/{item.id}/remover/',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.orc.id, item_id=item.id)
        self.assertEqual(resp.status_code, 200, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.detalhes['model'], 'ItemOrcamento')
        self.assertEqual(log.detalhes['orcamento_id'], self.orc.id)

    def test_remover_imagem_sem_token_401(self):
        img = ImagemInspiracao.objects.create(orcamento=self.orc, imagem=GIF_1PX)
        view = OrcamentoViewSet.as_view({'delete': 'remover_imagem'})
        req = self.factory.delete(f'/api/v1/eventos/orcamentos/{self.orc.id}/imagens/{img.id}/remover/')
        resp = view(req, pk=self.orc.id, imagem_id=img.id)
        self.assertEqual(resp.status_code, 401)

    def test_remover_imagem_com_token_gera_log(self):
        img = ImagemInspiracao.objects.create(orcamento=self.orc, imagem=GIF_1PX)
        view = OrcamentoViewSet.as_view({'delete': 'remover_imagem'})
        req = self.factory.delete(
            f'/api/v1/eventos/orcamentos/{self.orc.id}/imagens/{img.id}/remover/',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.orc.id, imagem_id=img.id)
        self.assertEqual(resp.status_code, 200, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_EXCLUIDO).latest('id')
        self.assertEqual(log.detalhes['model'], 'ImagemInspiracao')
        self.assertEqual(log.detalhes['orcamento_id'], self.orc.id)


class OrcamentoCriacaoEdicaoAuditoriaTests(AuditoriaEventosDestroyTestCase):
    def test_create_sem_token_401(self):
        view = OrcamentoViewSet.as_view({'post': 'create'})
        req = self.factory.post('/api/v1/eventos/orcamentos/', {
            'cliente_nome': 'Fulano', 'cliente_telefone': '86999997777', 'tipo_evento': 'aniversario',
        }, format='json')
        resp = view(req)
        self.assertEqual(resp.status_code, 401)

    def test_create_com_token_gera_log_registro_criado(self):
        view = OrcamentoViewSet.as_view({'post': 'create'})
        req = self.factory.post(
            '/api/v1/eventos/orcamentos/',
            {'cliente_nome': 'Fulano', 'cliente_telefone': '86999997777', 'tipo_evento': 'aniversario'},
            format='json', HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req)
        self.assertEqual(resp.status_code, 201, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_CRIADO).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['model'], 'Orcamento')
        self.assertEqual(log.detalhes['cliente_nome'], 'Fulano')

    def test_update_sem_token_401(self):
        orc = Orcamento.objects.create(
            numero=Orcamento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario', status='rascunho',
        )
        view = OrcamentoViewSet.as_view({'patch': 'partial_update'})
        req = self.factory.patch(f'/api/v1/eventos/orcamentos/{orc.id}/', {'observacoes': 'nota'}, format='json')
        resp = view(req, pk=orc.id)
        self.assertEqual(resp.status_code, 401)

    def test_update_com_token_gera_log_apenas_campos_alterados(self):
        orc = Orcamento.objects.create(
            numero=Orcamento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario', status='rascunho',
        )
        view = OrcamentoViewSet.as_view({'patch': 'partial_update'})
        req = self.factory.patch(
            f'/api/v1/eventos/orcamentos/{orc.id}/', {'observacoes': 'Nota atualizada'}, format='json',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=orc.id)
        self.assertEqual(resp.status_code, 200, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_ATUALIZADO).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['model'], 'Orcamento')
        self.assertEqual(set(log.detalhes['campos'].keys()), {'observacoes'})
        self.assertEqual(log.detalhes['campos']['observacoes']['para'], 'Nota atualizada')

    def test_update_bloqueado_fora_de_rascunho_enviado_continua_valendo(self):
        # Regressão: o refactor de update() pra usar perform_update() não pode
        # ter quebrado a validação de status já existente.
        orc = Orcamento.objects.create(
            numero=Orcamento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario', status='aprovado',
        )
        view = OrcamentoViewSet.as_view({'patch': 'partial_update'})
        req = self.factory.patch(
            f'/api/v1/eventos/orcamentos/{orc.id}/', {'observacoes': 'nota'}, format='json',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=orc.id)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_ATUALIZADO).exists())


class OrcamentoStatusAuditoriaTests(AuditoriaEventosDestroyTestCase):
    def setUp(self):
        super().setUp()
        self.orc = Orcamento.objects.create(
            numero=Orcamento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario', status='rascunho',
        )

    def _post(self, action_name, token=None):
        view = OrcamentoViewSet.as_view({'post': action_name})
        extra = {'HTTP_AUTHORIZATION': f'Token {token}'} if token else {}
        req = self.factory.post(f'/api/v1/eventos/orcamentos/{self.orc.id}/{action_name}/', format='json', **extra)
        return view(req, pk=self.orc.id)

    def test_enviar_sem_token_401(self):
        resp = self._post('enviar')
        self.assertEqual(resp.status_code, 401)

    def test_enviar_com_token_gera_log_status_alterado(self):
        resp = self._post('enviar', token=self._token())
        self.assertEqual(resp.status_code, 200, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_STATUS_ALTERADO).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['model'], 'Orcamento')
        self.assertEqual(log.detalhes['de'], 'rascunho')
        self.assertEqual(log.detalhes['para'], 'enviado')

    def test_aprovar_sem_token_401(self):
        resp = self._post('aprovar')
        self.assertEqual(resp.status_code, 401)

    def test_aprovar_com_token_gera_log_status_alterado(self):
        resp = self._post('aprovar', token=self._token())
        self.assertEqual(resp.status_code, 200, resp.data)
        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_STATUS_ALTERADO).latest('id')
        self.assertEqual(log.detalhes['para'], 'aprovado')

    def test_recusar_sem_token_401(self):
        resp = self._post('recusar')
        self.assertEqual(resp.status_code, 401)

    def test_recusar_com_token_gera_log_status_alterado(self):
        resp = self._post('recusar', token=self._token())
        self.assertEqual(resp.status_code, 200, resp.data)
        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_STATUS_ALTERADO).latest('id')
        self.assertEqual(log.detalhes['para'], 'recusado')

    def test_restaurar_sem_token_401(self):
        self.orc.status = 'expirado'
        self.orc.save(update_fields=['status'])
        resp = self._post('restaurar')
        self.assertEqual(resp.status_code, 401)

    def test_restaurar_com_token_gera_log_status_alterado(self):
        self.orc.status = 'expirado'
        self.orc.save(update_fields=['status'])
        resp = self._post('restaurar', token=self._token())
        self.assertEqual(resp.status_code, 200, resp.data)
        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_STATUS_ALTERADO).latest('id')
        self.assertEqual(log.detalhes['de'], 'expirado')
        self.assertEqual(log.detalhes['para'], 'rascunho')

    @patch('notificacoes.servico.zapi.enviar_documento')
    def test_enviar_whatsapp_muda_status_e_loga_status_alterado(self, mock_enviar):
        mock_enviar.return_value = {'messageId': 'abc123'}
        self.cliente.telefone_principal = '86999998888'
        self.cliente.save(update_fields=['telefone_principal'])

        view = OrcamentoViewSet.as_view({'post': 'enviar_whatsapp'})
        req = self.factory.post(f'/api/v1/eventos/orcamentos/{self.orc.id}/enviar-whatsapp/', {}, format='json')
        resp = view(req, pk=self.orc.id)
        resp.render()
        self.assertEqual(resp.status_code, 200, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_STATUS_ALTERADO).latest('id')
        self.assertEqual(log.detalhes['de'], 'rascunho')
        self.assertEqual(log.detalhes['para'], 'enviado')
        # enviar_whatsapp continua AllowAny (oportunista) — sem token, ator é None
        self.assertIsNone(log.usuario_id)


class EventoCriacaoEdicaoAuditoriaTests(AuditoriaEventosDestroyTestCase):
    def test_create_sem_token_401(self):
        view = EventoViewSet.as_view({'post': 'create'})
        req = self.factory.post('/api/v1/eventos/', {
            'cliente_nome': 'Fulano', 'cliente_telefone': '86999997777', 'tipo_evento': 'aniversario',
            'data_evento': str(datetime.date.today() + datetime.timedelta(days=5)),
        }, format='json')
        resp = view(req)
        self.assertEqual(resp.status_code, 401)

    def test_create_com_token_gera_log_registro_criado(self):
        view = EventoViewSet.as_view({'post': 'create'})
        req = self.factory.post(
            '/api/v1/eventos/',
            {
                'cliente_nome': 'Fulano', 'cliente_telefone': '86999997777', 'tipo_evento': 'aniversario',
                'data_evento': str(datetime.date.today() + datetime.timedelta(days=5)),
            },
            format='json', HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req)
        self.assertEqual(resp.status_code, 201, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_CRIADO, detalhes__model='Evento').latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['cliente_nome'], 'Fulano')

    def test_update_sem_token_401(self):
        evento = Evento.objects.create(
            numero=Evento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario',
            data_evento=datetime.date.today() + datetime.timedelta(days=10), status='orcamento',
        )
        view = EventoViewSet.as_view({'patch': 'partial_update'})
        req = self.factory.patch(f'/api/v1/eventos/{evento.id}/', {'observacoes': 'nota'}, format='json')
        resp = view(req, pk=evento.id)
        self.assertEqual(resp.status_code, 401)

    def test_update_com_token_gera_log_apenas_campos_alterados(self):
        evento = Evento.objects.create(
            numero=Evento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario',
            data_evento=datetime.date.today() + datetime.timedelta(days=10), status='orcamento',
        )
        view = EventoViewSet.as_view({'patch': 'partial_update'})
        req = self.factory.patch(
            f'/api/v1/eventos/{evento.id}/', {'observacoes': 'Nota nova'}, format='json',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=evento.id)
        self.assertEqual(resp.status_code, 200, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_ATUALIZADO, detalhes__model='Evento').latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(set(log.detalhes['campos'].keys()), {'observacoes'})


class EventoStatusAuditoriaTests(AuditoriaEventosDestroyTestCase):
    def setUp(self):
        super().setUp()
        self.evento = Evento.objects.create(
            numero=Evento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario',
            data_evento=datetime.date.today() + datetime.timedelta(days=10), status='orcamento',
        )

    def _post(self, action_name, token=None):
        view = EventoViewSet.as_view({'post': action_name})
        extra = {'HTTP_AUTHORIZATION': f'Token {token}'} if token else {}
        req = self.factory.post(f'/api/v1/eventos/{self.evento.id}/{action_name.replace("_", "-")}/', format='json', **extra)
        return view(req, pk=self.evento.id)

    def test_confirmar_sem_token_401(self):
        resp = self._post('confirmar')
        self.assertEqual(resp.status_code, 401)

    def test_confirmar_com_token_gera_log_status_alterado(self):
        resp = self._post('confirmar', token=self._token())
        self.assertEqual(resp.status_code, 200, resp.data)
        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_STATUS_ALTERADO, detalhes__model='Evento').latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['de'], 'orcamento')
        self.assertEqual(log.detalhes['para'], 'confirmado')

    def test_iniciar_producao_sem_token_401(self):
        self.evento.status = 'confirmado'
        self.evento.save(update_fields=['status'])
        resp = self._post('iniciar_producao')
        self.assertEqual(resp.status_code, 401)

    def test_iniciar_producao_com_token_gera_log(self):
        self.evento.status = 'confirmado'
        self.evento.save(update_fields=['status'])
        resp = self._post('iniciar_producao', token=self._token())
        self.assertEqual(resp.status_code, 200, resp.data)
        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_STATUS_ALTERADO, detalhes__model='Evento').latest('id')
        self.assertEqual(log.detalhes['para'], 'em_producao')

    def test_marcar_pronto_com_token_gera_log(self):
        self.evento.status = 'em_producao'
        self.evento.save(update_fields=['status'])
        resp = self._post('marcar_pronto', token=self._token())
        self.assertEqual(resp.status_code, 200, resp.data)
        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_STATUS_ALTERADO, detalhes__model='Evento').latest('id')
        self.assertEqual(log.detalhes['para'], 'pronto')

    def test_entregar_sem_token_401(self):
        self.evento.status = 'pronto'
        self.evento.save(update_fields=['status'])
        resp = self._post('entregar')
        self.assertEqual(resp.status_code, 401)

    def test_entregar_com_token_gera_log(self):
        self.evento.status = 'pronto'
        self.evento.save(update_fields=['status'])
        resp = self._post('entregar', token=self._token())
        self.assertEqual(resp.status_code, 200, resp.data)
        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_STATUS_ALTERADO, detalhes__model='Evento').latest('id')
        self.assertEqual(log.detalhes['para'], 'entregue')

    def test_cancelar_com_token_gera_log(self):
        resp = self._post('cancelar', token=self._token())
        self.assertEqual(resp.status_code, 200, resp.data)
        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_STATUS_ALTERADO, detalhes__model='Evento').latest('id')
        self.assertEqual(log.detalhes['para'], 'cancelado')


class ItemAdicionadoAuditoriaTests(AuditoriaEventosDestroyTestCase):
    def setUp(self):
        super().setUp()
        self.orc = Orcamento.objects.create(
            numero=Orcamento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario', status='rascunho',
        )
        self.evento = Evento.objects.create(
            numero=Evento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario',
            data_evento=datetime.date.today() + datetime.timedelta(days=10), status='orcamento',
        )

    def test_orcamento_adicionar_item_sem_token_401(self):
        view = OrcamentoViewSet.as_view({'post': 'adicionar_item'})
        req = self.factory.post(
            f'/api/v1/eventos/orcamentos/{self.orc.id}/itens/',
            {'nome': 'Bolo', 'preco_unit': '50.00', 'quantidade': 1}, format='json',
        )
        resp = view(req, pk=self.orc.id)
        self.assertEqual(resp.status_code, 401)

    def test_orcamento_adicionar_item_com_token_gera_log(self):
        view = OrcamentoViewSet.as_view({'post': 'adicionar_item'})
        req = self.factory.post(
            f'/api/v1/eventos/orcamentos/{self.orc.id}/itens/',
            {'nome': 'Bolo', 'preco_unit': '50.00', 'quantidade': 1}, format='json',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.orc.id)
        self.assertEqual(resp.status_code, 201, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_ITEM_ADICIONADO, detalhes__model='ItemOrcamento').latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['nome'], 'Bolo')
        self.assertEqual(log.detalhes['orcamento_id'], self.orc.id)

    def test_orcamento_editar_item_gera_log_registro_atualizado(self):
        item = ItemOrcamento.objects.create(orcamento=self.orc, nome='Bolo', preco_unit=50, quantidade=1)
        view = OrcamentoViewSet.as_view({'patch': 'editar_item'})
        req = self.factory.patch(
            f'/api/v1/eventos/orcamentos/{self.orc.id}/itens/{item.id}/editar/',
            {'nome': 'Bolo', 'preco_unit': '60.00', 'quantidade': 2}, format='json',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.orc.id, item_id=item.id)
        self.assertEqual(resp.status_code, 200, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_REGISTRO_ATUALIZADO, detalhes__model='ItemOrcamento').latest('id')
        self.assertEqual(log.detalhes['orcamento_id'], self.orc.id)
        self.assertIn('preco_unit', log.detalhes['campos'])
        self.assertIn('quantidade', log.detalhes['campos'])

    def test_evento_adicionar_item_sem_token_401(self):
        view = EventoViewSet.as_view({'post': 'adicionar_item'})
        req = self.factory.post(
            f'/api/v1/eventos/{self.evento.id}/itens/',
            {'nome': 'Bolo', 'preco_unit': '50.00', 'quantidade': 1}, format='json',
        )
        resp = view(req, pk=self.evento.id)
        self.assertEqual(resp.status_code, 401)

    def test_evento_adicionar_item_com_token_gera_log(self):
        view = EventoViewSet.as_view({'post': 'adicionar_item'})
        req = self.factory.post(
            f'/api/v1/eventos/{self.evento.id}/itens/',
            {'nome': 'Bolo', 'preco_unit': '50.00', 'quantidade': 1}, format='json',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.evento.id)
        self.assertEqual(resp.status_code, 201, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_ITEM_ADICIONADO, detalhes__model='ItemEvento').latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['evento_id'], self.evento.id)


class ConversaoOrcamentoAuditoriaTests(AuditoriaEventosDestroyTestCase):
    def setUp(self):
        super().setUp()
        self.orc = Orcamento.objects.create(
            numero=Orcamento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario',
            data_evento=datetime.date.today() + datetime.timedelta(days=20), status='aprovado',
        )

    def test_converter_sem_token_loga_ator_none(self):
        view = OrcamentoViewSet.as_view({'post': 'converter_em_evento'})
        req = self.factory.post(
            f'/api/v1/eventos/orcamentos/{self.orc.id}/converter-em-evento/', {}, format='json',
        )
        resp = view(req, pk=self.orc.id)
        self.assertEqual(resp.status_code, 201, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_ORCAMENTO_CONVERTIDO).latest('id')
        self.assertIsNone(log.usuario_id)
        self.assertEqual(log.detalhes['orcamento_id'], self.orc.id)

    def test_converter_com_token_loga_ator(self):
        view = OrcamentoViewSet.as_view({'post': 'converter_em_evento'})
        req = self.factory.post(
            f'/api/v1/eventos/orcamentos/{self.orc.id}/converter-em-evento/', {}, format='json',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=self.orc.id)
        self.assertEqual(resp.status_code, 201, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_ORCAMENTO_CONVERTIDO).latest('id')
        self.assertEqual(log.usuario_id, self.admin.id)
        self.assertEqual(log.detalhes['evento_numero'], resp.data['evento']['numero'])


class HistoricoPorObjetoTests(AuditoriaEventosDestroyTestCase):
    def test_historico_orcamento_sem_token_401(self):
        orc = Orcamento.objects.create(
            numero=Orcamento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario', status='rascunho',
        )
        view = OrcamentoViewSet.as_view({'get': 'historico'})
        req = self.factory.get(f'/api/v1/eventos/orcamentos/{orc.id}/historico/')
        resp = view(req, pk=orc.id)
        self.assertEqual(resp.status_code, 401)

    def test_historico_orcamento_agrega_criacao_status_e_itens(self):
        token = self._token()

        create_view = OrcamentoViewSet.as_view({'post': 'create'})
        req = self.factory.post(
            '/api/v1/eventos/orcamentos/',
            {'cliente_nome': 'Fulano', 'cliente_telefone': '86999997777', 'tipo_evento': 'aniversario'},
            format='json', HTTP_AUTHORIZATION=f'Token {token}',
        )
        resp = create_view(req)
        orc_id = resp.data['id']

        item_view = OrcamentoViewSet.as_view({'post': 'adicionar_item'})
        req = self.factory.post(
            f'/api/v1/eventos/orcamentos/{orc_id}/itens/',
            {'nome': 'Bolo', 'preco_unit': '50.00', 'quantidade': 1}, format='json',
            HTTP_AUTHORIZATION=f'Token {token}',
        )
        item_view(req, pk=orc_id)

        enviar_view = OrcamentoViewSet.as_view({'post': 'enviar'})
        req = self.factory.post(
            f'/api/v1/eventos/orcamentos/{orc_id}/enviar/', format='json', HTTP_AUTHORIZATION=f'Token {token}',
        )
        enviar_view(req, pk=orc_id)

        hist_view = OrcamentoViewSet.as_view({'get': 'historico'})
        req = self.factory.get(
            f'/api/v1/eventos/orcamentos/{orc_id}/historico/', HTTP_AUTHORIZATION=f'Token {token}',
        )
        resp = hist_view(req, pk=orc_id)
        self.assertEqual(resp.status_code, 200, resp.data)

        acoes = [log['acao'] for log in resp.data]
        self.assertIn(LogAuditoria.ACAO_REGISTRO_CRIADO, acoes)
        self.assertIn(LogAuditoria.ACAO_ITEM_ADICIONADO, acoes)
        self.assertIn(LogAuditoria.ACAO_STATUS_ALTERADO, acoes)
        # ordenado por criado_em desc — o mais recente (enviar) deve vir primeiro
        self.assertEqual(resp.data[0]['acao'], LogAuditoria.ACAO_STATUS_ALTERADO)

    def test_historico_evento_agrega_pagamentos(self):
        token = self._token()
        evento = Evento.objects.create(
            numero=Evento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario',
            data_evento=datetime.date.today() + datetime.timedelta(days=10), status='orcamento',
        )
        pag_view = EventoViewSet.as_view({'post': 'adicionar_pagamento'})
        req = self.factory.post(
            f'/api/v1/eventos/{evento.id}/pagamentos/',
            {'valor': '100.00', 'forma_pagamento': 'pix', 'status': 'pago', 'data_pagamento': str(datetime.date.today())},
            format='json', HTTP_AUTHORIZATION=f'Token {token}',
        )
        pag_view(req, pk=evento.id)

        hist_view = EventoViewSet.as_view({'get': 'historico'})
        req = self.factory.get(f'/api/v1/eventos/{evento.id}/historico/', HTTP_AUTHORIZATION=f'Token {token}')
        resp = hist_view(req, pk=evento.id)
        self.assertEqual(resp.status_code, 200, resp.data)

        acoes = [log['acao'] for log in resp.data]
        self.assertIn(LogAuditoria.ACAO_PAGAMENTO_REGISTRADO, acoes)


class ValorTotalItemAuditoriaTests(AuditoriaEventosDestroyTestCase):
    """
    Regressão: o cache do prefetch_related('itens') do get_object() fica
    stale dentro da mesma request quando o item é criado/apagado via manager
    direto (ItemOrcamento.objects.create/item.delete()) — recalcular_totais()
    lia esse cache velho e persistia um valor_total errado no banco. Corrigido
    com refresh_from_db() antes de recalcular_totais() (mesmo padrão já usado
    em adicionar_imagens/adicionar_pagamento — ver CLAUDE.md).
    """
    def test_orcamento_adicionar_item_atualiza_valor_total(self):
        orc = Orcamento.objects.create(
            numero=Orcamento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario', status='rascunho',
        )
        view = OrcamentoViewSet.as_view({'post': 'adicionar_item'})
        req = self.factory.post(
            f'/api/v1/eventos/orcamentos/{orc.id}/itens/',
            {'nome': 'Bolo', 'preco_unit': '100.00', 'quantidade': 1}, format='json',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=orc.id)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(str(resp.data['valor_total']), '100.00')

        orc.refresh_from_db()
        self.assertEqual(str(orc.valor_total), '100.00')

    def test_orcamento_remover_item_atualiza_valor_total(self):
        orc = Orcamento.objects.create(
            numero=Orcamento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario', status='rascunho',
        )
        item = ItemOrcamento.objects.create(orcamento=orc, nome='Bolo', preco_unit=100, quantidade=1)
        orc.recalcular_totais()

        view = OrcamentoViewSet.as_view({'delete': 'remover_item'})
        req = self.factory.delete(
            f'/api/v1/eventos/orcamentos/{orc.id}/itens/{item.id}/remover/',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=orc.id, item_id=item.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(str(resp.data['valor_total']), '0.00')

        orc.refresh_from_db()
        self.assertEqual(str(orc.valor_total), '0.00')

    def test_orcamento_editar_item_atualiza_valor_total(self):
        orc = Orcamento.objects.create(
            numero=Orcamento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario', status='rascunho',
        )
        item = ItemOrcamento.objects.create(orcamento=orc, nome='Bolo', preco_unit=100, quantidade=1)
        orc.recalcular_totais()

        view = OrcamentoViewSet.as_view({'patch': 'editar_item'})
        req = self.factory.patch(
            f'/api/v1/eventos/orcamentos/{orc.id}/itens/{item.id}/editar/',
            {'nome': 'Bolo', 'preco_unit': '60.00', 'quantidade': 2}, format='json',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=orc.id, item_id=item.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(str(resp.data['valor_total']), '120.00')

        orc.refresh_from_db()
        self.assertEqual(str(orc.valor_total), '120.00')

    def test_evento_adicionar_item_atualiza_valor_total(self):
        evento = Evento.objects.create(
            numero=Evento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario',
            data_evento=datetime.date.today() + datetime.timedelta(days=10), status='orcamento',
        )
        view = EventoViewSet.as_view({'post': 'adicionar_item'})
        req = self.factory.post(
            f'/api/v1/eventos/{evento.id}/itens/',
            {'nome': 'Bolo', 'preco_unit': '80.00', 'quantidade': 1}, format='json',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=evento.id)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(str(resp.data['valor_total']), '80.00')

        evento.refresh_from_db()
        self.assertEqual(str(evento.valor_total), '80.00')

    def test_evento_remover_item_atualiza_valor_total(self):
        evento = Evento.objects.create(
            numero=Evento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario',
            data_evento=datetime.date.today() + datetime.timedelta(days=10), status='orcamento',
        )
        item = ItemEvento.objects.create(evento=evento, nome='Bolo', preco_unit=80, quantidade=1)
        evento.recalcular_totais()

        view = EventoViewSet.as_view({'delete': 'remover_item'})
        req = self.factory.delete(
            f'/api/v1/eventos/{evento.id}/itens/{item.id}/remover/',
            HTTP_AUTHORIZATION=f'Token {self._token()}',
        )
        resp = view(req, pk=evento.id, item_id=item.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(str(resp.data['valor_total']), '0.00')

        evento.refresh_from_db()
        self.assertEqual(str(evento.valor_total), '0.00')
