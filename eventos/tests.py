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

    def test_criar_evento_com_sinal_sem_token_loga_sem_usuario(self):
        view = EventoViewSet.as_view({'post': 'create'})
        req = self.factory.post('/api/v1/eventos/', {
            'cliente_nome': 'Fulano', 'cliente_telefone': '86999997777',
            'tipo_evento': 'aniversario', 'data_evento': str(datetime.date.today() + datetime.timedelta(days=5)),
            'sinal_pago': '80.00',
        }, format='json')
        resp = view(req)
        self.assertEqual(resp.status_code, 201, resp.data)

        log = LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_PAGAMENTO_REGISTRADO, detalhes__origem='criacao_evento').latest('id')
        self.assertIsNone(log.usuario_id)

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
