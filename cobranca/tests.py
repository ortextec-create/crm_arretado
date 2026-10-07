from datetime import date, timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from empresas.models import Empresa
from eventos.models import Evento, TelefoneAlertaEvento
from usuarios.models import Usuario, gerar_token
from auditoria.models import LogAuditoria
from cobranca.models import ConfiguracaoCobranca, EtapaRegua, PausaCobranca, LigacaoCobranca, EnvioCobranca
from cobranca.mensagens import render, montar_contexto, validar_texto
from cobranca.regua import decidir_do_dia, eventos_elegiveis


def _empresa_padrao():
    return Empresa.get_padrao()


def _evento(**kwargs):
    defaults = dict(
        numero='EV-0001', cliente_nome='Fulano de Tal', cliente_telefone='86999990000',
        tipo_evento='aniversario', data_evento=date(2026, 10, 20),
        status='confirmado', valor_total=1000, sinal_pago=400,
    )
    defaults.update(kwargs)
    return Evento.objects.create(**defaults)


class MensagensTests(TestCase):
    def setUp(self):
        _empresa_padrao()
        self.cfg = ConfiguracaoCobranca.get()
        self.cfg.chave_pix = 'financeiro@arretadodoces.com.br'
        self.cfg.favorecido_pix = 'Arretado Doces LTDA'
        self.cfg.telefone_contato = '(86) 99816-4324'
        self.cfg.save()
        self.evento = _evento()

    def test_render_todas_variaveis_comuns(self):
        texto = (
            '{primeiro_nome} {nome} {numero_evento} {tipo_evento} {data_evento} '
            '{valor_total} {valor_pago} {saldo} {data_limite} {dias_para_limite} '
            '{dias_em_atraso} {dias_para_evento} {chave_pix} {favorecido_pix} '
            '{telefone_empresa} {empresa}'
        )
        ctx = montar_contexto(self.evento, self.cfg, hoje=date(2026, 10, 1))
        resultado = render(texto, ctx)
        self.assertNotIn('{', resultado)
        self.assertIn('Fulano', resultado)
        self.assertIn('600,00', resultado)  # saldo = 1000 - 400

    def test_render_nao_usa_str_format(self):
        # Chave com ponto e texto com {} literal não devem derrubar o render
        # (str.format()/format_map() lançaria KeyError/IndexError aqui).
        texto = 'Valor: {saldo} — literal: {} — acesso: {a.b}'
        resultado = render(texto, {'saldo': '10,00'})
        self.assertIn('10,00', resultado)
        self.assertIn('{} — acesso: {a.b}', resultado)

    def test_variavel_ausente_no_contexto_fica_vazia(self):
        self.assertEqual(render('oi {xyz}', {}), 'oi ')

    def test_validar_texto_vazio_rejeitado(self):
        with self.assertRaises(ValidationError):
            validar_texto('   ', permitir_prazo=False)

    def test_validar_texto_variavel_desconhecida_rejeitada(self):
        with self.assertRaises(ValidationError):
            validar_texto('Olá {variavel_inventada}', permitir_prazo=False)

    def test_prazo_combinado_rejeitado_em_etapa(self):
        with self.assertRaises(ValidationError):
            validar_texto('Prazo: {prazo_combinado}', permitir_prazo=False)

    def test_prazo_combinado_aceito_quando_permitido(self):
        validar_texto('Prazo: {prazo_combinado}', permitir_prazo=True)  # não levanta


class DecidirDoDiaTests(TestCase):
    """Etapas seed: -12,-9,-7 (lembrete) · -6,-3,3 (cobrança) · limite=-7."""

    def setUp(self):
        _empresa_padrao()
        self.cfg = ConfiguracaoCobranca.get()
        self.cfg.ativo = True
        self.cfg.ativo_desde = date(2020, 1, 1)
        self.cfg.save()
        self.etapas = list(EtapaRegua.objects.filter(ativo=True))
        self.evento = _evento()

    def _decidir(self, hoje):
        return decidir_do_dia(self.evento, self.etapas, self.cfg, hoje)

    def test_b_atraso_envia_so_a_mais_recente_pula_as_demais(self):
        hoje = self.evento.data_evento - timedelta(days=6)  # D-6 já passou junto com D-12/D-9/D-7
        decisao = self._decidir(hoje)
        self.assertEqual(decisao.enviar['etapa'].dias, -6)
        self.assertEqual(decisao.enviar['tipo'], 'cobranca')
        dias_pulados = sorted(p['etapa'].dias for p in decisao.puladas)
        self.assertEqual(dias_pulados, [-12, -9, -7])
        self.assertTrue(all(p['motivo_pulada'] == 'atraso' for p in decisao.puladas))

    def test_c_pausa_vigente_pula_etapas_e_envia_prazo_hoje(self):
        hoje = self.evento.data_evento - timedelta(days=6)
        pausa = PausaCobranca.objects.create(evento=self.evento, pausado_ate=hoje, motivo='teste')
        decisao = self._decidir(hoje)
        self.assertEqual(decisao.enviar, {'tipo': 'prazo_hoje', 'pausa': pausa})
        self.assertTrue(decisao.puladas)
        self.assertTrue(all(p['motivo_pulada'] == 'pausa' for p in decisao.puladas))

    def test_d_dia_seguinte_envia_prazo_vencido_e_nada_mais(self):
        ontem = self.evento.data_evento - timedelta(days=7)
        hoje = ontem + timedelta(days=1)
        pausa = PausaCobranca.objects.create(evento=self.evento, pausado_ate=ontem, motivo='teste')
        decisao = self._decidir(hoje)
        self.assertEqual(decisao.enviar['tipo'], 'prazo_vencido')
        self.assertEqual(decisao.enviar['pausa'], pausa)
        self.assertTrue(all(p['motivo_pulada'] == 'mesmo_dia' for p in decisao.puladas))

    def test_e_ativo_desde_ignora_etapas_anteriores(self):
        hoje = self.evento.data_evento - timedelta(days=6)
        self.cfg.ativo_desde = hoje  # etapas -12/-9/-7 (antes disso) não existem mais
        self.cfg.save()
        decisao = self._decidir(hoje)
        self.assertEqual(decisao.enviar['etapa'].dias, -6)
        self.assertEqual(decisao.puladas, [])

    def test_f_remarcacao_recomeca(self):
        etapa = next(e for e in self.etapas if e.dias == -12)
        data_antiga = self.evento.data_evento
        EnvioCobranca.objects.create(
            evento=self.evento, tipo='lembrete', etapa=etapa, dias_etapa=-12,
            data_evento_referencia=data_antiga, status='enviado',
        )
        # Evento remarcado — data nova, o envio antigo referencia a data antiga
        self.evento.data_evento = data_antiga + timedelta(days=10)
        self.evento.save(update_fields=['data_evento'])
        hoje = self.evento.data_evento + timedelta(days=-12)
        decisao = self._decidir(hoje)
        self.assertEqual(decisao.enviar['etapa'].dias, -12)

    def test_g_falha_nao_ocupa_a_vaga(self):
        etapa = next(e for e in self.etapas if e.dias == -12)
        EnvioCobranca.objects.create(
            evento=self.evento, tipo='lembrete', etapa=etapa, dias_etapa=-12,
            data_evento_referencia=self.evento.data_evento, status='falha',
        )
        hoje = self.evento.data_evento - timedelta(days=12)
        decisao = self._decidir(hoje)
        self.assertEqual(decisao.enviar['etapa'].dias, -12)

    def test_j_status_fora_de_elegiveis_nao_entra(self):
        self.evento.status = 'orcamento'
        self.evento.save(update_fields=['status'])
        self.assertNotIn(self.evento.id, eventos_elegiveis().values_list('id', flat=True))

    def test_k_entregue_com_saldo_entra(self):
        self.evento.status = 'entregue'
        self.evento.save(update_fields=['status'])
        self.assertIn(self.evento.id, eventos_elegiveis().values_list('id', flat=True))

    def test_sem_telefone_nao_envia(self):
        self.evento.cliente_telefone = ''
        self.evento.save(update_fields=['cliente_telefone'])
        hoje = self.evento.data_evento - timedelta(days=12)
        decisao = self._decidir(hoje)
        self.assertIsNone(decisao.enviar)
        self.assertEqual(decisao.puladas, [])


class EnviarCobrancasCommandTests(TestCase):
    def setUp(self):
        _empresa_padrao()
        self.cfg = ConfiguracaoCobranca.get()
        self.cfg.ativo = True
        self.cfg.ativo_desde = date(2020, 1, 1)
        self.cfg.dias_semana_envio = [0, 1, 2, 3, 4, 5, 6]
        self.cfg.save()
        self.evento = _evento()

    @patch('cobranca.management.commands.enviar_cobrancas.notificar', return_value=True)
    def test_a_duas_execucoes_mesmo_dia_nao_duplicam(self, mock_notificar):
        hoje = self.evento.data_evento - timedelta(days=12)
        with patch('django.utils.timezone.localdate', return_value=hoje):
            call_command('enviar_cobrancas', verbosity=0)
            call_command('enviar_cobrancas', verbosity=0)
        self.assertEqual(EnvioCobranca.objects.filter(evento=self.evento, status='enviado').count(), 1)
        self.assertEqual(mock_notificar.call_count, 1)

    @patch('cobranca.management.commands.enviar_cobrancas.notificar', return_value=True)
    def test_l_aviso_equipe_na_ultima_etapa_uma_vez(self, mock_notificar):
        TelefoneAlertaEvento.objects.create(numero='86999998888', ativo=True)
        for dias in (-12, -9, -7, -6, -3):
            etapa = EtapaRegua.objects.get(dias=dias)
            EnvioCobranca.objects.create(
                evento=self.evento, tipo='lembrete' if dias <= -7 else 'cobranca', etapa=etapa,
                dias_etapa=dias, data_evento_referencia=self.evento.data_evento, status='enviado',
            )
        hoje = self.evento.data_evento + timedelta(days=3)
        with patch('django.utils.timezone.localdate', return_value=hoje):
            call_command('enviar_cobrancas', verbosity=0)
        # 1 chamada pro cliente (C3) + 1 chamada pra equipe = 2
        self.assertEqual(mock_notificar.call_count, 2)
        chamada_equipe = mock_notificar.call_args_list[1]
        self.assertEqual(chamada_equipe.kwargs.get('telefone'), '86999998888')
        self.assertEqual(chamada_equipe.kwargs.get('tipo'), 'alerta_pagamento')

    @patch('cobranca.management.commands.enviar_cobrancas.notificar')
    def test_dry_run_nao_grava_nem_envia(self, mock_notificar):
        hoje = self.evento.data_evento - timedelta(days=12)
        call_command('enviar_cobrancas', dry_run=True, data=hoje.isoformat(), verbosity=0)
        mock_notificar.assert_not_called()
        self.assertEqual(EnvioCobranca.objects.count(), 0)


def _usuario(**kwargs):
    defaults = dict(name='Carla Mendes', email='carla@teste.com', role='atendente')
    defaults.update(kwargs)
    usuario = Usuario(**defaults)
    usuario.set_password('senha-123')
    usuario.auth_token = gerar_token()
    usuario.save()
    return usuario


def _client_autenticado(usuario):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Token {usuario.auth_token}')
    return client


class ConfiguracaoCobrancaAPITests(TestCase):
    def setUp(self):
        _empresa_padrao()
        self.usuario = _usuario()
        self.client_auth = _client_autenticado(self.usuario)

    def test_patch_sem_login_e_rejeitado(self):
        resp = APIClient().patch('/api/v1/cobranca/configuracao/1/', {'ativo': True}, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_ativo_false_para_true_grava_ativo_desde_e_audita(self):
        cfg = ConfiguracaoCobranca.get()
        self.assertFalse(cfg.ativo)
        self.assertIsNone(cfg.ativo_desde)

        resp = self.client_auth.patch('/api/v1/cobranca/configuracao/1/', {'ativo': True}, format='json')
        self.assertEqual(resp.status_code, 200)

        cfg.refresh_from_db()
        self.assertTrue(cfg.ativo)
        self.assertEqual(cfg.ativo_desde, date.today())
        self.assertTrue(
            LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_COBRANCA_CONFIG_ALTERADA).exists()
        )

    def test_dias_semana_envio_vazio_e_rejeitado(self):
        resp = self.client_auth.patch(
            '/api/v1/cobranca/configuracao/1/', {'dias_semana_envio': []}, format='json',
        )
        self.assertEqual(resp.status_code, 400)


class EtapaReguaAPITests(TestCase):
    def setUp(self):
        _empresa_padrao()
        self.usuario = _usuario()
        self.client_auth = _client_autenticado(self.usuario)

    def test_dias_duplicado_retorna_400_amigavel(self):
        resp = self.client_auth.post(
            '/api/v1/cobranca/etapas/', {'dias': -12, 'mensagem': 'Olá {nome}, saldo {saldo}'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_criar_etapa_exige_login_e_audita(self):
        resp = APIClient().post(
            '/api/v1/cobranca/etapas/', {'dias': 10, 'mensagem': 'Olá {nome}, saldo {saldo}'}, format='json',
        )
        self.assertEqual(resp.status_code, 401)

        resp = self.client_auth.post(
            '/api/v1/cobranca/etapas/', {'dias': 10, 'mensagem': 'Olá {nome}, saldo {saldo}'}, format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(
            LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_COBRANCA_ETAPA_CRIADA).exists()
        )

    def test_prazo_combinado_em_etapa_e_rejeitado(self):
        resp = self.client_auth.post(
            '/api/v1/cobranca/etapas/', {'dias': 10, 'mensagem': 'Prazo: {prazo_combinado}'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_sem_put_nem_delete(self):
        etapa = EtapaRegua.objects.get(dias=-12)
        resp = self.client_auth.put(
            f'/api/v1/cobranca/etapas/{etapa.id}/', {'dias': -12, 'mensagem': 'x', 'ativo': True}, format='json',
        )
        self.assertEqual(resp.status_code, 405)
        resp = self.client_auth.delete(f'/api/v1/cobranca/etapas/{etapa.id}/')
        self.assertEqual(resp.status_code, 405)

    def test_preview_allowany_sem_efeito_colateral(self):
        total_antes = EtapaRegua.objects.count()
        resp = APIClient().post(
            '/api/v1/cobranca/etapas/preview/',
            {'mensagem': 'Olá {nome}, variável {invalida_xyz}'}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('invalida_xyz', resp.data['variaveis_invalidas'])
        self.assertEqual(EtapaRegua.objects.count(), total_antes)


class LigacaoCobrancaAPITests(TestCase):
    def setUp(self):
        _empresa_padrao()
        self.usuario = _usuario()
        self.client_auth = _client_autenticado(self.usuario)
        self.cfg = ConfiguracaoCobranca.get()
        self.evento = _evento()

    def test_sem_login_e_rejeitado(self):
        resp = APIClient().post('/api/v1/cobranca/ligacoes/', {
            'evento': self.evento.id, 'telefone_discado': self.evento.cliente_telefone, 'atendeu': False,
        }, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_prazo_pagamento_com_atendeu_false_e_rejeitado(self):
        resp = self.client_auth.post('/api/v1/cobranca/ligacoes/', {
            'evento': self.evento.id, 'telefone_discado': '86999990000', 'atendeu': False,
            'prazo_pagamento': (date.today() + timedelta(days=5)).isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_data_hora_futura_e_rejeitada(self):
        from django.utils import timezone
        futuro = (timezone.now() + timedelta(days=1)).isoformat()
        resp = self.client_auth.post('/api/v1/cobranca/ligacoes/', {
            'evento': self.evento.id, 'telefone_discado': '86999990000', 'atendeu': True,
            'data_hora': futuro,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    @patch('cobranca.views.notificar', return_value=True)
    def test_nao_atendida_envia_whatsapp_so_com_toggle_ligado(self, mock_notificar):
        self.cfg.ativo = True
        self.cfg.msg_ligacao_nao_atendida_ativo = False
        self.cfg.save()

        resp = self.client_auth.post('/api/v1/cobranca/ligacoes/', {
            'evento': self.evento.id, 'telefone_discado': '86999990000', 'atendeu': False,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.data['whatsapp_enviado'])
        mock_notificar.assert_not_called()

        self.cfg.msg_ligacao_nao_atendida_ativo = True
        self.cfg.save()
        resp = self.client_auth.post('/api/v1/cobranca/ligacoes/', {
            'evento': self.evento.id, 'telefone_discado': '86999990000', 'atendeu': False,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['whatsapp_enviado'])
        mock_notificar.assert_called_once()

    def test_ligacao_e_imutavel(self):
        ligacao = LigacaoCobranca.objects.create(
            evento=self.evento, telefone_discado='86999990000', atendeu=False,
            registrado_por=self.usuario, registrado_por_nome=self.usuario.name,
        )
        resp = self.client_auth.patch(f'/api/v1/cobranca/ligacoes/{ligacao.id}/', {'observacao': 'x'}, format='json')
        self.assertEqual(resp.status_code, 405)
        resp = self.client_auth.delete(f'/api/v1/cobranca/ligacoes/{ligacao.id}/')
        self.assertEqual(resp.status_code, 405)

    def test_ligacao_com_prazo_cria_pausa_e_encerra_anterior(self):
        anterior = PausaCobranca.objects.create(
            evento=self.evento, pausado_ate=date.today() + timedelta(days=20), motivo='antiga',
        )
        resp = self.client_auth.post('/api/v1/cobranca/ligacoes/', {
            'evento': self.evento.id, 'telefone_discado': '86999990000', 'atendeu': True,
            'prazo_pagamento': (date.today() + timedelta(days=5)).isoformat(), 'observacao': 'paga sexta',
        }, format='json')
        self.assertEqual(resp.status_code, 201)

        anterior.refresh_from_db()
        self.assertIsNotNone(anterior.encerrada_em)

        nova = PausaCobranca.objects.exclude(pk=anterior.pk).get(evento=self.evento)
        self.assertEqual(nova.origem, 'ligacao')
        self.assertTrue(nova.vigente)


class PausaCobrancaAPITests(TestCase):
    def setUp(self):
        _empresa_padrao()
        self.usuario = _usuario()
        self.client_auth = _client_autenticado(self.usuario)
        self.evento = _evento()

    def test_sem_delete_nem_patch(self):
        pausa = PausaCobranca.objects.create(
            evento=self.evento, pausado_ate=date.today() + timedelta(days=5), motivo='x',
        )
        resp = self.client_auth.patch(f'/api/v1/cobranca/pausas/{pausa.id}/', {'motivo': 'y'}, format='json')
        self.assertEqual(resp.status_code, 405)
        resp = self.client_auth.delete(f'/api/v1/cobranca/pausas/{pausa.id}/')
        self.assertEqual(resp.status_code, 405)

    def test_encerrar_exige_motivo_e_audita(self):
        pausa = PausaCobranca.objects.create(
            evento=self.evento, pausado_ate=date.today() + timedelta(days=5), motivo='x',
        )
        resp = self.client_auth.post(f'/api/v1/cobranca/pausas/{pausa.id}/encerrar/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

        resp = self.client_auth.post(
            f'/api/v1/cobranca/pausas/{pausa.id}/encerrar/', {'motivo': 'cliente desistiu'}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        pausa.refresh_from_db()
        self.assertIsNotNone(pausa.encerrada_em)
        self.assertTrue(
            LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_COBRANCA_RETOMADA).exists()
        )

    def test_encerrar_pausa_ja_vencida_e_rejeitado(self):
        pausa = PausaCobranca.objects.create(
            evento=self.evento, pausado_ate=date.today() - timedelta(days=1), motivo='x',
        )
        resp = self.client_auth.post(
            f'/api/v1/cobranca/pausas/{pausa.id}/encerrar/', {'motivo': 'y'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_pausado_no_passado_e_rejeitado_na_criacao(self):
        resp = self.client_auth.post('/api/v1/cobranca/pausas/', {
            'evento': self.evento.id, 'pausado_ate': (date.today() - timedelta(days=1)).isoformat(),
            'motivo': 'x',
        }, format='json')
        self.assertEqual(resp.status_code, 400)


class FilaLinhaDoTempoAPITests(TestCase):
    def setUp(self):
        _empresa_padrao()
        self.cfg = ConfiguracaoCobranca.get()
        self.cfg.ativo = True
        self.cfg.ativo_desde = date(2020, 1, 1)
        self.cfg.save()
        self.evento = _evento()

    def test_fila_lista_evento_elegivel(self):
        resp = APIClient().get('/api/v1/cobranca/fila/')
        self.assertEqual(resp.status_code, 200)
        numeros = [i['numero'] for i in resp.data]
        self.assertIn(self.evento.numero, numeros)

    def test_linha_do_tempo_inclui_pagamento(self):
        from eventos.models import PagamentoEvento
        PagamentoEvento.objects.create(evento=self.evento, valor=100, status='pago')
        resp = APIClient().get(f'/api/v1/cobranca/eventos/{self.evento.id}/linha-do-tempo/')
        self.assertEqual(resp.status_code, 200)
        tipos = [i['tipo'] for i in resp.data['linha_do_tempo']]
        self.assertIn('pagamento', tipos)


class SeedEtapasTests(TestCase):
    def test_seed_nao_duplica_ao_rodar_2x(self):
        import importlib
        from django.apps import apps as real_apps

        seed_mod = importlib.import_module('cobranca.migrations.0002_seed_etapas_padrao')

        total = EtapaRegua.objects.count()
        self.assertEqual(total, 6)  # já rodou no migrate do test runner

        seed_mod.seed_etapas(real_apps, None)
        self.assertEqual(EtapaRegua.objects.count(), total)
