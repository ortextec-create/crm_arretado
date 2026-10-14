from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from atendimento.models import (
    ConfiguracaoAtendimento, ConfiguracaoExtensao, MensagemChat, ModeloMensagemChat, TokenExtensao,
)
from atendimento.render import renderizar
from atendimento.servico import enfileirar
from auditoria.models import LogAuditoria
from empresas.models import Empresa
from ifood.models import ConfiguracaoIFood, ItemPedidoIFood, PedidoIFood
from ifood.polling_worker import EVENTOS_LOGISTICA, _criar_pedido, _processar_evento_pedido
from usuarios.models import Usuario, gerar_token


def _empresa(nome='Outra Loja'):
    return Empresa.objects.create(nome=nome)


def _pedido(empresa=None, order_id='o-1', **kw):
    empresa = empresa or Empresa.get_padrao()
    defaults = dict(
        ifood_order_id=order_id, ifood_merchant_id='m', empresa=empresa, display_id='1234',
        cliente_nome='maria da silva', status='PLACED', ifood_criado_em=timezone.now(),
    )
    defaults.update(kw)
    return PedidoIFood.objects.create(**defaults)


def _ligar(empresa=None, **kw):
    cfg = ConfiguracaoAtendimento.get(empresa or Empresa.get_padrao())
    cfg.chat_ativo = True
    for k, v in kw.items():
        setattr(cfg, k, v)
    cfg.save()
    return cfg


def _usuario(role='admin', email='adm@teste.com'):
    u = Usuario(name='Admin', email=email, role=role)
    u.set_password('x')
    u.auth_token = gerar_token()
    u.save()
    return u


def _client_usuario(u):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Token {u.auth_token}')
    return c


def _client_extensao(token):
    c = APIClient()
    c.credentials(HTTP_X_EXTENSAO_TOKEN=token)
    return c


class ConfiguracaoTests(TestCase):
    def test_nasce_desligada_e_cria_padroes(self):
        cfg = ConfiguracaoAtendimento.get(Empresa.get_padrao())
        self.assertFalse(cfg.chat_ativo)
        self.assertEqual(cfg.modo_ia, 'desligado')
        self.assertEqual(ModeloMensagemChat.objects.filter(empresa=cfg.empresa).count(), 10)
        self.assertFalse(ModeloMensagemChat.objects.get(empresa=cfg.empresa, gatilho='cancelado').ativo)
        self.assertTrue(ModeloMensagemChat.objects.get(empresa=cfg.empresa, gatilho='confirmado').ativo)

    def test_garantir_padroes_nao_sobrescreve_edicao(self):
        emp = Empresa.get_padrao()
        ConfiguracaoAtendimento.get(emp)
        ModeloMensagemChat.objects.filter(empresa=emp, gatilho='confirmado').update(texto='meu texto', ativo=False)
        ConfiguracaoAtendimento.get(emp)
        m = ModeloMensagemChat.objects.get(empresa=emp, gatilho='confirmado')
        self.assertEqual((m.texto, m.ativo), ('meu texto', False))

    def test_textos_padrao_nao_citam_empresa_fixa(self):
        from atendimento.modelos_padrao import MODELOS_PADRAO
        for texto, _ in MODELOS_PADRAO.values():
            self.assertNotIn('Arretado', texto)


class RenderTests(TestCase):
    def test_todas_variaveis(self):
        p = _pedido(previsao_entrega=timezone.now())
        for nome, qtd in [('Bolo', 2), ('Brigadeiro', 1), ('Torta', 3), ('Pudim', 1)]:
            ItemPedidoIFood.objects.create(pedido=p, nome=nome, quantidade=qtd)
        r = renderizar('{loja}|{nome}|{primeiro_nome}|{pedido}|{itens_resumo}|{previsao}|{minutos_atraso}', p, {'minutos_atraso': 12})
        loja, nome, primeiro, num, itens, prev, atraso = r.split('|')
        self.assertEqual(loja, p.empresa.nome)
        self.assertEqual((nome, primeiro, num), ('maria da silva', 'Maria', '1234'))
        self.assertEqual(itens, '2x Bolo, 1x Brigadeiro e mais 2')
        self.assertRegex(prev, r'^\d\d:\d\d$')
        self.assertEqual(atraso, '12')

    def test_variavel_desconhecida_previsao_nula_e_nome_vazio(self):
        p = _pedido(cliente_nome='', previsao_entrega=None)
        r = renderizar('{xpto} {primeiro_nome} {previsao} [{minutos_atraso}]', p)
        self.assertEqual(r, '{xpto} cliente em breve []')

    def test_valor_com_chaves_nao_e_resubstituido(self):
        p = _pedido(cliente_nome='{pedido}')
        self.assertEqual(renderizar('{nome}', p), '{pedido}')


class SignalTests(TestCase):
    def setUp(self):
        self.emp = Empresa.get_padrao()

    def test_chat_desligado_nao_cria(self):
        p = _pedido(status='CONFIRMED')
        p.save()
        self.assertEqual(MensagemChat.objects.count(), 0)

    def test_uma_mensagem_por_gatilho_mesmo_com_varios_saves(self):
        _ligar()
        p = _pedido(status='CONFIRMED')
        for _ in range(4):
            p.save()
            p.save(update_fields=['atualizado_em'])
        msgs = MensagemChat.objects.filter(pedido=p)
        self.assertEqual(msgs.count(), 1)
        m = msgs.get()
        self.assertEqual((m.gatilho, m.status, m.origem, m.direcao), ('confirmado', 'pendente', 'automatico', 'saida'))
        self.assertIn('Maria', m.texto)
        self.assertIsNotNone(m.expira_em)

    def test_mapeamento_de_status_e_pronto_por_tipo(self):
        _ligar()
        casos = [
            ('PREPARATION_STARTED', 'DELIVERY', 'em_preparo'),
            ('READY_TO_PICKUP', 'TAKEOUT', 'pronto_retirada'),
            ('READY_TO_PICKUP', 'DELIVERY', 'pronto_entrega'),
            ('DISPATCHED', 'DELIVERY', 'saiu_entrega'),
            ('CONCLUDED', 'DELIVERY', 'concluido'),
        ]
        for i, (st, tp, gat) in enumerate(casos):
            p = _pedido(order_id=f'x{i}', status=st, order_type=tp)
            self.assertEqual(list(MensagemChat.objects.filter(pedido=p).values_list('gatilho', flat=True)), [gat])

    def test_placed_e_negociacao_nao_geram(self):
        _ligar()
        _pedido(order_id='a', status='PLACED')
        _pedido(order_id='b', status='CANCELLATION_REQUESTED')
        self.assertEqual(MensagemChat.objects.count(), 0)

    def test_modelo_inativo_nao_cria(self):
        _ligar()
        ModeloMensagemChat.objects.filter(empresa=self.emp, gatilho='confirmado').update(ativo=False)
        _pedido(status='CONFIRMED')
        self.assertEqual(MensagemChat.objects.count(), 0)

    def test_cancelado_inativo_por_padrao(self):
        _ligar()
        _pedido(status='CANCELLED')
        self.assertEqual(MensagemChat.objects.count(), 0)

    def test_fora_da_janela_nao_cria(self):
        _ligar(janela_maxima_horas=6)
        _pedido(status='CONFIRMED', ifood_criado_em=timezone.now() - timedelta(hours=7))
        self.assertEqual(MensagemChat.objects.count(), 0)

    def test_cancelled_cancela_pendentes_exceto_a_de_cancelado(self):
        _ligar()
        ModeloMensagemChat.objects.filter(empresa=self.emp, gatilho='cancelado').update(ativo=True)
        p = _pedido(status='CONFIRMED')
        self.assertEqual(MensagemChat.objects.get(pedido=p).status, 'pendente')
        p.status = 'CANCELLED'
        p.save()
        self.assertEqual(MensagemChat.objects.get(pedido=p, gatilho='confirmado').status, 'cancelada')
        self.assertEqual(MensagemChat.objects.get(pedido=p, gatilho='cancelado').status, 'pendente')

    def test_texto_e_snapshot(self):
        _ligar()
        p = _pedido(status='CONFIRMED')
        ModeloMensagemChat.objects.filter(empresa=self.emp, gatilho='confirmado').update(texto='OUTRO')
        self.assertIn('Maria', MensagemChat.objects.get(pedido=p).texto)

    def test_falha_do_servico_nunca_quebra_o_save(self):
        _ligar()
        with patch('atendimento.servico.enfileirar', side_effect=RuntimeError('boom')):
            p = _pedido(status='CONFIRMED')
        self.assertEqual(PedidoIFood.objects.get(pk=p.pk).status, 'CONFIRMED')


class EnfileirarTests(TestCase):
    def test_manual_pula_modelo_janela_e_unicidade(self):
        p = _pedido(ifood_criado_em=timezone.now() - timedelta(days=3))
        a = enfileirar(p, 'manual', origem='manual', texto='oi')
        b = enfileirar(p, 'manual', origem='manual', texto='oi de novo')
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertIsNone(a.expira_em)

    def test_texto_vazio_manual_devolve_none(self):
        self.assertIsNone(enfileirar(_pedido(), 'manual', origem='manual', texto='  '))

    def test_automatico_duplicado_devolve_none(self):
        _ligar()
        p = _pedido()
        self.assertIsNotNone(enfileirar(p, 'confirmado'))
        self.assertIsNone(enfileirar(p, 'confirmado'))


class ExtensaoAPITests(TestCase):
    def setUp(self):
        self.emp = Empresa.get_padrao()
        self.outra = _empresa()
        _ligar(self.emp)
        self.tok, self.raw = TokenExtensao.criar('Caixa', [self.emp])
        self.api = _client_extensao(self.raw)

    def _msg(self, pedido=None, texto='oi', **kw):
        pedido = pedido or _pedido(order_id=f'p{MensagemChat.objects.count()}')
        return MensagemChat.objects.create(
            empresa=pedido.empresa, pedido=pedido, gatilho='manual', origem='manual', texto=texto, **kw)

    def test_token_puro_nunca_gravado(self):
        self.assertNotEqual(self.tok.token_hash, self.raw)
        self.assertEqual(len(self.tok.token_hash), 64)
        self.assertEqual(self.tok.prefixo, self.raw[:8])

    def test_sem_token_invalido_e_revogado_dao_401(self):
        self.assertEqual(APIClient().post('/api/v1/atendimento/extensao/fila/reservar/').status_code, 401)
        self.assertEqual(_client_extensao('lixo').post('/api/v1/atendimento/extensao/fila/reservar/').status_code, 401)
        self.tok.ativo = False
        self.tok.save()
        self.assertEqual(self.api.post('/api/v1/atendimento/extensao/fila/reservar/').status_code, 401)

    def test_token_de_usuario_nao_serve_na_extensao(self):
        u = _usuario()
        r = _client_usuario(u).get('/api/v1/atendimento/extensao/config/')
        self.assertIn(r.status_code, (401, 403))

    def test_config_da_extensao(self):
        cfg = ConfiguracaoExtensao.get()
        cfg.seletores = {'messageInput': 'textarea.x'}
        cfg.save()
        r = self.api.get('/api/v1/atendimento/extensao/config/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['seletores'], {'messageInput': 'textarea.x'})
        self.assertEqual(r.data['intervalo_segundos'], 5)

    def test_heartbeat_grava_diagnostico(self):
        r = self.api.post('/api/v1/atendimento/extensao/heartbeat/',
                          {'versao': '1.0.0', 'aba_ok': True, 'seletores_ok': {'messageInput': True}, 'url': 'https://g'},
                          format='json')
        self.assertEqual(r.status_code, 204)
        self.tok.refresh_from_db()
        self.assertEqual(self.tok.versao_extensao, '1.0.0')
        self.assertTrue(self.tok.ultimo_diagnostico['seletores_ok']['messageInput'])
        self.assertIsNotNone(self.tok.ultimo_heartbeat)

    def test_reservar_fila_vazia_204(self):
        self.assertEqual(self.api.post('/api/v1/atendimento/extensao/fila/reservar/').status_code, 204)

    def test_reservar_mais_antiga_primeiro_e_nunca_repete(self):
        a = self._msg(texto='primeira')
        b = self._msg(texto='segunda')
        r1 = self.api.post('/api/v1/atendimento/extensao/fila/reservar/')
        r2 = self.api.post('/api/v1/atendimento/extensao/fila/reservar/')
        r3 = self.api.post('/api/v1/atendimento/extensao/fila/reservar/')
        self.assertEqual((r1.data['id'], r2.data['id'], r3.status_code), (a.id, b.id, 204))
        self.assertEqual(r1.data['display_id'], '1234')
        a.refresh_from_db()
        self.assertEqual((a.status, a.tentativas), ('enviando', 1))
        self.assertIsNotNone(a.reservado_em)

    def test_token_nao_ve_fila_de_outra_empresa(self):
        _ligar(self.outra)
        self._msg(pedido=_pedido(self.outra, order_id='x'))
        self.assertEqual(self.api.post('/api/v1/atendimento/extensao/fila/reservar/').status_code, 204)

    def test_lease_vencido_vira_incerta_e_nao_volta(self):
        m = self._msg()
        self.assertEqual(self.api.post('/api/v1/atendimento/extensao/fila/reservar/').status_code, 200)
        MensagemChat.objects.filter(pk=m.pk).update(reservado_em=timezone.now() - timedelta(seconds=500))
        self.assertEqual(self.api.post('/api/v1/atendimento/extensao/fila/reservar/').status_code, 204)
        m.refresh_from_db()
        self.assertEqual(m.status, 'incerta')
        self.assertEqual(self.api.post('/api/v1/atendimento/extensao/fila/reservar/').status_code, 204)
        m.refresh_from_db()
        self.assertEqual(m.status, 'incerta')

    def test_pendente_vencida_vira_expirada(self):
        m = self._msg(expira_em=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.api.post('/api/v1/atendimento/extensao/fila/reservar/').status_code, 204)
        m.refresh_from_db()
        self.assertEqual(m.status, 'expirada')

    def test_resultado_ok_e_falha(self):
        a = self._msg()
        b = self._msg()
        self.api.post('/api/v1/atendimento/extensao/fila/reservar/')
        self.api.post('/api/v1/atendimento/extensao/fila/reservar/')
        r = self.api.post(f'/api/v1/atendimento/extensao/fila/{a.id}/resultado/', {'ok': True, 'passos': ['abriu', 'enviou']}, format='json')
        self.assertEqual(r.status_code, 204)
        r = self.api.post(f'/api/v1/atendimento/extensao/fila/{b.id}/resultado/', {'ok': False, 'erro': 'modo_seguro', 'passos': ['x']}, format='json')
        self.assertEqual(r.status_code, 204)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual((a.status, a.passos), ('enviada', ['abriu', 'enviou']))
        self.assertIsNotNone(a.enviado_em)
        self.assertEqual((b.status, b.erro), ('falha', 'modo_seguro'))

    def test_resultado_fora_de_enviando_409_e_outra_empresa_404(self):
        a = self._msg()
        r = self.api.post(f'/api/v1/atendimento/extensao/fila/{a.id}/resultado/', {'ok': True}, format='json')
        self.assertEqual(r.status_code, 409)
        _ligar(self.outra)
        alheia = self._msg(pedido=_pedido(self.outra, order_id='z'))
        r = self.api.post(f'/api/v1/atendimento/extensao/fila/{alheia.id}/resultado/', {'ok': True}, format='json')
        self.assertEqual(r.status_code, 404)


class ReservarConcorrenciaTests(TransactionTestCase):
    """Em Postgres o skip_locked garante; aqui garantimos o contrato sequencial de 2 extensões."""

    def test_duas_extensoes_nunca_pegam_a_mesma(self):
        emp = Empresa.get_padrao()
        _, raw1 = TokenExtensao.criar('A', [emp])
        _, raw2 = TokenExtensao.criar('B', [emp])
        p = _pedido()
        m = MensagemChat.objects.create(empresa=emp, pedido=p, gatilho='manual', origem='manual', texto='x')
        r1 = _client_extensao(raw1).post('/api/v1/atendimento/extensao/fila/reservar/')
        r2 = _client_extensao(raw2).post('/api/v1/atendimento/extensao/fila/reservar/')
        self.assertEqual((r1.status_code, r1.data['id'], r2.status_code), (200, m.id, 204))


class CrmAPITests(TestCase):
    def setUp(self):
        self.emp = Empresa.get_padrao()
        self.admin = _usuario()
        self.api = _client_usuario(self.admin)

    def test_exige_login(self):
        for url in ['configuracao/', 'modelos/', 'mensagens/', 'status-extensao/', 'tokens/', 'configuracao-extensao/']:
            self.assertEqual(APIClient().get(f'/api/v1/atendimento/{url}').status_code, 401, url)

    def test_configuracao_patch_audita(self):
        r = self.api.patch('/api/v1/atendimento/configuracao/', {'chat_ativo': True, 'janela_maxima_horas': 4}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ConfiguracaoAtendimento.get(self.emp).chat_ativo)
        self.assertTrue(LogAuditoria.objects.filter(acao='config_atendimento_alterada').exists())

    def test_modelos_lista_garante_padroes_patch_e_sem_delete(self):
        r = self.api.get('/api/v1/atendimento/modelos/')
        self.assertEqual(len(r.data), 10)
        mid = next(m['id'] for m in r.data if m['gatilho'] == 'confirmado')
        r = self.api.patch(f'/api/v1/atendimento/modelos/{mid}/', {'texto': 'Novo {pedido}', 'ativo': False}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(LogAuditoria.objects.filter(acao='modelo_atendimento_alterado').exists())
        self.assertEqual(self.api.delete(f'/api/v1/atendimento/modelos/{mid}/').status_code, 405)
        r = self.api.patch(f'/api/v1/atendimento/modelos/{mid}/', {'gatilho': 'cancelado'}, format='json')
        self.assertEqual(ModeloMensagemChat.objects.get(pk=mid).gatilho, 'confirmado')

    def test_preview_ficticio_e_com_pedido(self):
        r = self.api.post('/api/v1/atendimento/modelos/preview/', {'texto': 'Oi {primeiro_nome} #{pedido} {itens_resumo}'}, format='json')
        self.assertEqual(r.data['renderizado'], 'Oi Maria #1234 2x Bolo de pote, 1x Brigadeiro')
        p = _pedido()
        r = self.api.post('/api/v1/atendimento/modelos/preview/', {'texto': '{nome}', 'pedido_id': p.id}, format='json')
        self.assertEqual(r.data['renderizado'], 'maria da silva')

    def test_manual_cria_pendente_com_autor(self):
        p = _pedido(status='CONFIRMED')
        r = self.api.post('/api/v1/atendimento/mensagens/manual/', {'pedido': p.id, 'texto': ' Olá! '}, format='json')
        self.assertEqual(r.status_code, 201)
        m = MensagemChat.objects.get(pk=r.data['id'])
        self.assertEqual((m.status, m.origem, m.gatilho, m.autor, m.texto), ('pendente', 'manual', 'manual', self.admin, 'Olá!'))

    def test_manual_rejeita_pedido_fechado_ha_mais_de_24h(self):
        p = _pedido(status='CONCLUDED')
        PedidoIFood.objects.filter(pk=p.pk).update(atualizado_em=timezone.now() - timedelta(hours=25))
        r = self.api.post('/api/v1/atendimento/mensagens/manual/', {'pedido': p.id, 'texto': 'oi'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_manual_pedido_de_outra_empresa_404(self):
        p = _pedido(_empresa())
        r = self.api.post('/api/v1/atendimento/mensagens/manual/', {'pedido': p.id, 'texto': 'oi'}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_cancelar_so_pendente(self):
        p = _pedido()
        m = enfileirar(p, 'manual', origem='manual', texto='a')
        r = self.api.post(f'/api/v1/atendimento/mensagens/{m.id}/cancelar/')
        self.assertEqual((r.status_code, r.data['status']), (200, 'cancelada'))
        self.assertEqual(self.api.post(f'/api/v1/atendimento/mensagens/{m.id}/cancelar/').status_code, 400)

    def test_reenviar_cria_nova_manual_e_mantem_a_original(self):
        p = _pedido()
        m = enfileirar(p, 'manual', origem='manual', texto='a')
        self.assertEqual(self.api.post(f'/api/v1/atendimento/mensagens/{m.id}/reenviar/').status_code, 400)
        MensagemChat.objects.filter(pk=m.pk).update(status='incerta')
        r = self.api.post(f'/api/v1/atendimento/mensagens/{m.id}/reenviar/')
        self.assertEqual(r.status_code, 201)
        self.assertNotEqual(r.data['id'], m.id)
        self.assertEqual((r.data['status'], r.data['origem']), ('pendente', 'manual'))
        m.refresh_from_db()
        self.assertEqual(m.status, 'incerta')

    def test_lista_filtra_e_nao_tem_delete(self):
        p = _pedido()
        m = enfileirar(p, 'manual', origem='manual', texto='a')
        enfileirar(_pedido(order_id='o-2'), 'manual', origem='manual', texto='b')
        r = self.api.get(f'/api/v1/atendimento/mensagens/?pedido={p.id}')
        self.assertEqual([x['id'] for x in r.data['results']], [m.id])
        self.assertIn(self.api.delete(f'/api/v1/atendimento/mensagens/{m.id}/').status_code, (404, 405))

    def test_status_extensao(self):
        r = self.api.get('/api/v1/atendimento/status-extensao/')
        self.assertFalse(r.data['online'])
        tok, raw = TokenExtensao.criar('Caixa', [self.emp])
        _client_extensao(raw).post('/api/v1/atendimento/extensao/heartbeat/', {'versao': '1', 'seletores_ok': {'a': True}}, format='json')
        r = self.api.get('/api/v1/atendimento/status-extensao/')
        self.assertTrue(r.data['online'])
        self.assertEqual(r.data['seletores_ok'], {'a': True})
        TokenExtensao.objects.filter(pk=tok.pk).update(ultimo_heartbeat=timezone.now() - timedelta(seconds=120))
        self.assertFalse(self.api.get('/api/v1/atendimento/status-extensao/').data['online'])

    def test_tokens_so_admin_token_puro_uma_vez_e_revogar(self):
        atendente = _client_usuario(_usuario('atendente', 'at@teste.com'))
        self.assertEqual(atendente.get('/api/v1/atendimento/tokens/').status_code, 403)
        self.assertEqual(atendente.get('/api/v1/atendimento/configuracao-extensao/').status_code, 403)
        r = self.api.post('/api/v1/atendimento/tokens/', {'nome': 'Caixa', 'empresas_ids': [self.emp.id]}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertIn('token', r.data)
        tid = r.data['id']
        self.assertNotIn('token', self.api.get('/api/v1/atendimento/tokens/').data[0])
        self.assertEqual(_client_extensao(r.data['token']).get('/api/v1/atendimento/extensao/config/').status_code, 200)
        self.assertEqual(self.api.post(f'/api/v1/atendimento/tokens/{tid}/revogar/').status_code, 200)
        self.assertEqual(_client_extensao(r.data['token']).get('/api/v1/atendimento/extensao/config/').status_code, 401)
        self.assertIn(self.api.delete(f'/api/v1/atendimento/tokens/{tid}/').status_code, (404, 405))
        self.assertTrue(LogAuditoria.objects.filter(acao='token_extensao_criado').exists())
        self.assertTrue(LogAuditoria.objects.filter(acao='token_extensao_revogado').exists())

    def test_configuracao_extensao_patch_audita(self):
        r = self.api.patch('/api/v1/atendimento/configuracao-extensao/', {'seletores': {'sendButton': 'button.s'}, 'intervalo_segundos': 8}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ConfiguracaoExtensao.get().seletores, {'sendButton': 'button.s'})
        self.assertTrue(LogAuditoria.objects.filter(acao='config_extensao_alterada').exists())
        r = self.api.patch('/api/v1/atendimento/configuracao-extensao/', {'seletores': 'texto'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_gerar_token_extensao_command(self):
        out = StringIO()
        call_command('gerar_token_extensao', '--empresa', str(self.emp.id), '--nome', 'Teste', stdout=out)
        token = out.getvalue().strip().splitlines()[-1]
        self.assertEqual(_client_extensao(token).get('/api/v1/atendimento/extensao/config/').status_code, 200)


class IFoodIntegracaoTests(TestCase):
    def _detalhe(self, **extra):
        d = {
            'id': 'abc', 'displayId': '001', 'merchant': {'id': 'm'}, 'customer': {}, 'delivery': {},
            'payments': {}, 'total': {}, 'items': [], 'metadata': {}, 'schedule': {}, 'benefits': [],
            'fullCode': 'PLACED', 'orderType': 'DELIVERY',
        }
        d.update(extra)
        return d

    def setUp(self):
        self.config = ConfiguracaoIFood.objects.create(
            empresa=Empresa.get_padrao(), client_id='c', client_secret='s', merchant_id='m')

    def test_criar_pedido_sem_campos_de_previsao_grava_none(self):
        p = _criar_pedido(self._detalhe(), self.config)
        self.assertIsNone(p.previsao_entrega)
        self.assertIsNone(p.previsao_preparo_inicio)

    def test_criar_pedido_le_previsoes_com_prioridade(self):
        p = _criar_pedido(self._detalhe(
            preparationStartDateTime='2026-10-14T20:00:00Z',
            delivery={'deliveryDateTime': '2026-10-14T21:00:00Z'},
            takeout={'takeoutDateTime': '2026-10-14T22:00:00Z'},
            schedule={'scheduledDateTimeEnd': '2026-10-14T23:00:00Z'},
        ), self.config)
        self.assertEqual(p.previsao_preparo_inicio.hour, 20)
        self.assertEqual(p.previsao_entrega.hour, 21)
        p2 = _criar_pedido(self._detalhe(id='def', takeout={'takeoutDateTime': '2026-10-14T22:00:00Z'},
                                         schedule={'scheduledDateTimeEnd': '2026-10-14T23:00:00Z'}), self.config)
        self.assertEqual(p2.previsao_entrega.hour, 22)

    def test_evento_de_logistica_grava_timestamp_sem_mexer_no_status(self):
        _ligar()
        ModeloMensagemChat.objects.filter(empresa=self.config.empresa, gatilho='entregador_chegou').update(ativo=True)
        p = _pedido(order_id='ord-1', status='READY_TO_PICKUP')
        evt = {'fullCode': 'ARRIVED_AT_ORIGIN', 'orderId': 'ord-1', 'createdAt': '2026-10-14T20:10:00Z'}
        self.assertFalse(_processar_evento_pedido(None, evt, self.config))
        p.refresh_from_db()
        self.assertEqual(p.status, 'READY_TO_PICKUP')
        self.assertEqual(p.entregador_chegou_em.minute, 10)
        self.assertEqual(MensagemChat.objects.filter(pedido=p, gatilho='entregador_chegou').count(), 1)
        # reprocessar não duplica nem sobrescreve
        evt['createdAt'] = '2026-10-14T20:50:00Z'
        _processar_evento_pedido(None, evt, self.config)
        p.refresh_from_db()
        self.assertEqual(p.entregador_chegou_em.minute, 10)
        self.assertEqual(MensagemChat.objects.filter(pedido=p).count(), 2)  # pronto_entrega (criação) + entregador_chegou

    def test_collected_grava_coletado_em(self):
        p = _pedido(order_id='ord-2', status='DISPATCHED')
        _processar_evento_pedido(None, {'fullCode': 'COLLECTED', 'orderId': 'ord-2', 'createdAt': '2026-10-14T20:30:00Z'}, self.config)
        p.refresh_from_db()
        self.assertEqual(p.coletado_em.minute, 30)
        self.assertEqual(p.status, 'DISPATCHED')

    def test_views_do_ifood_nao_notificam_mais_por_whatsapp(self):
        import ifood.views as v
        self.assertFalse(hasattr(v, 'notificar'))
        self.assertFalse(hasattr(v, '_notificar_ifood'))

    def test_serializer_detalhe_expoe_campos_novos(self):
        from ifood.serializers import PedidoIFoodDetailSerializer
        data = PedidoIFoodDetailSerializer(_pedido()).data
        for c in ('previsao_preparo_inicio', 'previsao_entrega', 'entregador_chegou_em', 'coletado_em'):
            self.assertIn(c, data)
