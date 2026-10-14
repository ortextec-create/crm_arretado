"""Testes de Remarcação e Adiamento de Evento (ver ADIAMENTO.md)."""
import datetime
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from auditoria.models import LogAuditoria
from clientes.models import Cliente
from cobranca import regua
from financeiro.models import ContaPagar
from usuarios.models import Usuario

from . import adiamento as regras
from .management.commands.alertar_adiamentos import decidir_alerta
from .models import (
    AdiamentoEvento, AlertaEventoEnviado, ConfiguracaoAlertaEvento, ConfiguracaoContrato,
    Contrato, Evento, ItemEvento, Orcamento, PagamentoEvento, RemarcacaoEvento,
    TelefoneAlertaEvento, AditivoContrato,
)


def hoje():
    return timezone.localdate()


class FaixaMultaTests(TestCase):
    def setUp(self):
        self.cfg = ConfiguracaoContrato.get()

    def test_limites_das_faixas(self):
        f = lambda dias, prod=False: regras.faixa_multa_pct(dias, prod, self.cfg)
        self.assertEqual(f(6), self.cfg.multa_rescisao_abaixo_7_dias_pct)
        self.assertEqual(f(7), self.cfg.multa_rescisao_abaixo_30_dias_pct)
        self.assertEqual(f(29), self.cfg.multa_rescisao_abaixo_30_dias_pct)
        self.assertEqual(f(30), self.cfg.multa_rescisao_30_60_dias_pct)
        self.assertEqual(f(60), self.cfg.multa_rescisao_30_60_dias_pct)
        self.assertEqual(f(61), self.cfg.multa_rescisao_acima_60_dias_pct)

    def test_producao_iniciada_vai_para_faixa_abaixo_de_7(self):
        self.assertEqual(
            regras.faixa_multa_pct(90, True, self.cfg), self.cfg.multa_rescisao_abaixo_7_dias_pct,
        )


class CalcularAcertoTests(TestCase):
    def test_rescisao_normal(self):
        r = regras.calcular_acerto(Decimal('100'), Decimal('400'), Decimal('15'), 0, 'rescisao')
        self.assertEqual(r, {'multa': Decimal('60.00'), 'retido': Decimal('0.00'), 'devolucao': Decimal('40.00')})

    def test_multa_maior_que_pago_e_limitada_ao_pago(self):
        r = regras.calcular_acerto(Decimal('50'), Decimal('1000'), Decimal('40'), 0, 'rescisao')
        self.assertEqual(r['multa'], Decimal('50.00'))
        self.assertEqual(r['devolucao'], Decimal('0.00'))

    def test_forca_maior_sem_multa(self):
        r = regras.calcular_acerto(Decimal('200'), Decimal('1000'), Decimal('40'), Decimal('30'), 'forca_maior')
        self.assertEqual(r, {'multa': Decimal('0.00'), 'retido': Decimal('30.00'), 'devolucao': Decimal('170.00')})

    def test_retido_maior_que_pago_nao_gera_devolucao_negativa(self):
        r = regras.calcular_acerto(Decimal('100'), Decimal('1000'), Decimal('10'), Decimal('500'), 'forca_maior')
        self.assertEqual(r['devolucao'], Decimal('0.00'))

    def test_acordo_manual_devolve_informado(self):
        r = regras.calcular_acerto(Decimal('100'), Decimal('1000'), None, 10, 'acordo_manual',
                                   valor_multa=Decimal('30'), valor_devolucao=Decimal('60'))
        self.assertEqual(r, {'multa': Decimal('30.00'), 'retido': Decimal('10.00'), 'devolucao': Decimal('60.00')})

    def test_arredondamento_half_up(self):
        r = regras.calcular_acerto(Decimal('1000'), Decimal('100.05'), Decimal('10'), 0, 'rescisao')
        self.assertEqual(r['multa'], Decimal('10.01'))  # 10.005 → 10.01


class DiasUteisTests(TestCase):
    def test_atravessa_fim_de_semana(self):
        sexta = datetime.date(2026, 10, 9)
        self.assertEqual(sexta.weekday(), 4)
        self.assertEqual(regras.somar_dias_uteis(sexta, 1), datetime.date(2026, 10, 12))
        self.assertEqual(regras.somar_dias_uteis(sexta, 5), datetime.date(2026, 10, 16))

    def test_zero_dias(self):
        d = datetime.date(2026, 10, 10)
        self.assertEqual(regras.somar_dias_uteis(d, 0), d)


class BaseAdiamento(TestCase):
    def setUp(self):
        patcher = patch('eventos.views.notificar')
        self.notificar = patcher.start()
        self.addCleanup(patcher.stop)
        self.user = Usuario(name='Admin Teste', email='admin@teste.com', role='admin')
        self.user.set_password('senha-123')
        self.user.save()
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cliente = Cliente.objects.create(nome='Maria Teste', telefone_principal='86999998888')

    def evento(self, status='confirmado', dias=90, valor=1000, pago=0, contrato=False, clausula=True):
        ev = Evento.objects.create(
            numero=Evento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario',
            data_evento=hoje() + datetime.timedelta(days=dias), status=status,
        )
        ItemEvento.objects.create(evento=ev, nome='Bolo', preco_unit=valor, quantidade=1)
        ev.recalcular_totais()
        if pago:
            PagamentoEvento.objects.create(evento=ev, valor=pago, status='pago')
            ev.recalcular_sinal_pago()
        if contrato:
            orc = Orcamento.objects.create(
                numero=Orcamento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario',
                data_evento=ev.data_evento, status='aprovado',
            )
            Contrato.objects.create(
                numero=Contrato.proximo_numero(), orcamento=orc, evento=ev, cliente=self.cliente,
                contratante_nome='Maria', contratante_nacionalidade='brasileira', contratante_cpf='1',
                contratante_endereco='Rua', data_evento=ev.data_evento, valor_total=ev.valor_total,
                percentual_sinal=50, valor_sinal=500, data_quitacao=ev.data_evento,
                possui_clausula_adiamento=clausula,
            )
        ev.refresh_from_db()
        return ev

    def post(self, ev, acao, dados=None):
        return self.client.post(f'/api/v1/eventos/{ev.id}/{acao}/', dados or {}, format='json')

    def nova_data(self, dias=60):
        return str(hoje() + datetime.timedelta(days=dias))


class PatchDataTests(BaseAdiamento):
    def test_patch_com_data_diferente_400(self):
        ev = self.evento()
        r = self.client.patch(f'/api/v1/eventos/{ev.id}/', {'data_evento': self.nova_data(10)}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('data_evento', r.data)

    def test_patch_com_data_igual_200(self):
        ev = self.evento()
        r = self.client.patch(
            f'/api/v1/eventos/{ev.id}/',
            {'data_evento': str(ev.data_evento), 'observacoes': 'x'}, format='json',
        )
        self.assertEqual(r.status_code, 200, r.data)


class RemarcarTests(BaseAdiamento):
    def test_remarcar_cria_log_e_mantem_status(self):
        ev = self.evento()
        antiga = ev.data_evento
        r = self.post(ev, 'remarcar', {'data_evento': self.nova_data(120), 'motivo': 'Cliente pediu', 'solicitado_por': 'cliente'})
        self.assertEqual(r.status_code, 200, r.data)
        ev.refresh_from_db()
        self.assertEqual(ev.status, 'confirmado')
        self.assertEqual(str(ev.data_evento), self.nova_data(120))
        log = RemarcacaoEvento.objects.get(evento=ev)
        self.assertEqual(log.data_anterior, antiga)
        self.assertTrue(LogAuditoria.objects.filter(acao='evento_remarcado').exists())
        self.assertEqual(r.data['data_original'], antiga)

    def test_remarcar_em_pronto_exige_confirmacao(self):
        ev = self.evento(status='pronto')
        dados = {'data_evento': self.nova_data(120), 'motivo': 'x', 'solicitado_por': 'empresa'}
        r = self.post(ev, 'remarcar', dados)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['detail'], 'producao_iniciada')
        r = self.post(ev, 'remarcar', {**dados, 'confirmar_producao': True, 'voltar_para_confirmado': True})
        self.assertEqual(r.status_code, 200, r.data)
        ev.refresh_from_db()
        self.assertEqual(ev.status, 'confirmado')

    def test_remarcar_data_passada_ou_igual_400(self):
        ev = self.evento()
        base = {'motivo': 'x', 'solicitado_por': 'cliente'}
        passado = str(hoje() - datetime.timedelta(days=1))
        self.assertEqual(self.post(ev, 'remarcar', {**base, 'data_evento': passado}).status_code, 400)
        self.assertEqual(self.post(ev, 'remarcar', {**base, 'data_evento': str(ev.data_evento)}).status_code, 400)

    def test_remarcar_status_invalido(self):
        ev = self.evento(status='entregue')
        r = self.post(ev, 'remarcar', {'data_evento': self.nova_data(), 'motivo': 'x', 'solicitado_por': 'cliente'})
        self.assertEqual(r.status_code, 400)

    def test_remarcar_exige_login(self):
        ev = self.evento()
        anon = APIClient().post(f'/api/v1/eventos/{ev.id}/remarcar/', {}, format='json')
        self.assertIn(anon.status_code, (401, 403))

    def test_aditivo_sugerido_com_contrato(self):
        ev = self.evento(contrato=True)
        r = self.post(ev, 'remarcar', {'data_evento': self.nova_data(120), 'motivo': 'x', 'solicitado_por': 'cliente'})
        self.assertTrue(r.data['aditivo_sugerido'])
        self.assertTrue(r.data['contrato_divergente'])
        self.assertIn('data', r.data['contrato_divergencia'])


class AdiarRetomarTests(BaseAdiamento):
    DADOS = {'motivo': 'Doença na família', 'solicitado_por': 'cliente'}

    def test_adiar_cria_snapshot_e_muda_status(self):
        ev = self.evento(dias=90, contrato=True)
        r = self.post(ev, 'adiar', self.DADOS)
        self.assertEqual(r.status_code, 200, r.data)
        ev.refresh_from_db()
        self.assertEqual(ev.status, 'adiado')
        ad = ev.adiamento_vigente
        self.assertEqual(ad.antecedencia_dias, 90)
        self.assertEqual(ad.multa_pct, ConfiguracaoContrato.get().multa_rescisao_acima_60_dias_pct)
        self.assertEqual(ad.limite, ev.data_evento + datetime.timedelta(days=180))
        self.assertEqual(r.data['adiado_limite'], ad.limite)

    def test_adiar_sem_clausula_nao_calcula_multa(self):
        ev = self.evento(contrato=True, clausula=False)
        self.post(ev, 'adiar', self.DADOS)
        self.assertIsNone(ev.adiamento_vigente.multa_pct)

    def test_adiar_em_producao_usa_faixa_de_7_dias(self):
        ev = self.evento(status='em_producao', dias=90, contrato=True)
        self.post(ev, 'adiar', self.DADOS)
        self.assertTrue(ev.adiamento_vigente.producao_iniciada)
        self.assertEqual(ev.adiamento_vigente.multa_pct, ConfiguracaoContrato.get().multa_rescisao_abaixo_7_dias_pct)

    def test_adiar_duas_vezes_400(self):
        ev = self.evento()
        self.post(ev, 'adiar', self.DADOS)
        self.assertEqual(self.post(ev, 'adiar', self.DADOS).status_code, 400)

    def test_retomar_volta_a_confirmado_e_encerra(self):
        ev = self.evento(status='pronto', pago=300)
        self.post(ev, 'adiar', self.DADOS)
        r = self.post(ev, 'retomar', {'data_evento': self.nova_data(150)})
        self.assertEqual(r.status_code, 200, r.data)
        ev.refresh_from_db()
        self.assertEqual(ev.status, 'confirmado')
        self.assertEqual(ev.sinal_pago, Decimal('300.00'))
        ad = AdiamentoEvento.objects.get(evento=ev)
        self.assertEqual(ad.desfecho, 'retomado')
        self.assertIsNotNone(ad.encerrado_em)
        self.assertEqual(RemarcacaoEvento.objects.get(evento=ev).origem, 'retomada')

    def test_retomar_apos_limite_fora_do_prazo(self):
        ev = self.evento(dias=10)
        self.post(ev, 'adiar', self.DADOS)
        r = self.post(ev, 'retomar', {'data_evento': self.nova_data(400)})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['detail'], 'fora_do_prazo')

    def test_prorrogar_ate_o_maximo(self):
        ev = self.evento()
        self.post(ev, 'adiar', self.DADOS)
        limite = ev.adiamento_vigente.limite
        r = self.post(ev, 'adiamento/prorrogar', {'motivo': 'Cliente pediu mais prazo'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(ev.adiamento_vigente.limite, limite + datetime.timedelta(days=180))
        self.assertEqual(self.post(ev, 'adiamento/prorrogar', {'motivo': 'de novo'}).status_code, 400)

    def test_cancelar_em_adiado_400(self):
        ev = self.evento()
        self.post(ev, 'adiar', self.DADOS)
        self.assertEqual(self.post(ev, 'cancelar').status_code, 400)

    def test_contato_atualiza_followup(self):
        ev = self.evento()
        self.post(ev, 'adiar', self.DADOS)
        nova = str(hoje() + datetime.timedelta(days=5))
        r = self.post(ev, 'adiamento/contato', {'retomar_contato_em': nova})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(str(ev.adiamento_vigente.retomar_contato_em), nova)

    def test_gerar_aditivo_rejeita_adiado(self):
        ev = self.evento(contrato=True)
        self.post(ev, 'adiar', self.DADOS)
        r = self.post(ev, 'gerar-aditivo')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['detail'], 'evento_adiado')


class EncerrarAdiamentoTests(BaseAdiamento):
    DADOS = {'motivo': 'x', 'solicitado_por': 'cliente'}

    def setUp(self):
        super().setUp()
        from empresas.models import Empresa
        if not Empresa.objects.filter(padrao=True).exists():
            Empresa.objects.create(nome='Teste', padrao=True)

    def adiado(self, **kw):
        ev = self.evento(**kw)
        self.post(ev, 'adiar', self.DADOS)
        return ev

    def test_rescisao_gera_conta_pagar_em_dias_uteis(self):
        ev = self.adiado(dias=90, valor=1000, pago=400, contrato=True)  # multa 15% de 1000 = 150
        sim = self.client.get(f'/api/v1/eventos/{ev.id}/adiamento/simular-encerramento/?desfecho=rescisao')
        self.assertEqual(Decimal(str(sim.data['multa_sugerida'])), Decimal('150.00'))
        self.assertEqual(Decimal(str(sim.data['devolucao_sugerida'])), Decimal('250.00'))
        r = self.post(ev, 'adiamento/encerrar', {'desfecho': 'rescisao', 'observacao': 'Rescindido'})
        self.assertEqual(r.status_code, 200, r.data)
        ev.refresh_from_db()
        self.assertEqual(ev.status, 'cancelado')
        ad = AdiamentoEvento.objects.get(evento=ev)
        self.assertEqual(ad.valor_multa, Decimal('150.00'))
        conta = ad.conta_pagar
        self.assertEqual(conta.origem, 'devolucao_evento')
        self.assertEqual(conta.valor, Decimal('250.00'))
        self.assertLess(conta.data_vencimento.weekday(), 5)
        self.assertEqual(
            conta.data_vencimento,
            regras.somar_dias_uteis(hoje(), ConfiguracaoContrato.get().prazo_devolucao_dias),
        )
        self.assertTrue(LogAuditoria.objects.filter(acao='adiamento_encerrado').exists())

    def test_soma_diferente_do_pago_400(self):
        ev = self.adiado(pago=400, contrato=True)
        r = self.post(ev, 'adiamento/encerrar', {
            'desfecho': 'rescisao', 'observacao': 'x', 'valor_multa': '10', 'valor_devolucao': '10',
        })
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['detail'], 'soma_invalida')

    def test_rescisao_sem_clausula_400(self):
        ev = self.adiado(pago=400, contrato=True, clausula=False)
        r = self.post(ev, 'adiamento/encerrar', {'desfecho': 'rescisao', 'observacao': 'x'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['detail'], 'sem_clausula')

    def test_acordo_manual_sem_contrato(self):
        ev = self.adiado(pago=400)
        r = self.post(ev, 'adiamento/encerrar', {
            'desfecho': 'acordo_manual', 'observacao': 'Distrato', 'valor_multa': '100', 'valor_devolucao': '300',
        })
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(ContaPagar.objects.get().valor, Decimal('300.00'))

    def test_forca_maior_sem_multa_sem_pagamento_nao_gera_conta(self):
        ev = self.adiado(pago=0)
        r = self.post(ev, 'adiamento/encerrar', {'desfecho': 'forca_maior', 'observacao': 'Enchente'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(ContaPagar.objects.count(), 0)

    def test_sem_adiamento_vigente_400(self):
        ev = self.evento()
        r = self.post(ev, 'adiamento/encerrar', {'desfecho': 'forca_maior', 'observacao': 'x'})
        self.assertEqual(r.status_code, 400)


class ExclusoesAdiadoTests(BaseAdiamento):
    def test_agenda_e_estatisticas_ignoram_adiado(self):
        ev = self.evento(dias=3)
        self.post(ev, 'adiar', {'motivo': 'x', 'solicitado_por': 'empresa'})
        mes = ev.data_evento.strftime('%Y-%m')
        r = self.client.get(f'/api/v1/eventos/agenda/?mes={mes}')
        self.assertEqual(r.data['total'], 0)
        est = self.client.get('/api/v1/eventos/estatisticas/')
        self.assertEqual(est.data['por_status']['adiado'], 1)
        self.assertEqual(est.data['eventos_mes'], 0)

    def test_resumo_cozinha_rejeita_adiado(self):
        ev = self.evento()
        self.post(ev, 'adiar', {'motivo': 'x', 'solicitado_por': 'empresa'})
        self.assertEqual(self.client.get(f'/api/v1/eventos/{ev.id}/resumo-cozinha/').status_code, 400)

    def test_alertar_eventos_ignora_adiado(self):
        ev = self.evento(dias=3, status='confirmado')
        TelefoneAlertaEvento.objects.create(numero='86999990000')
        self.post(ev, 'adiar', {'motivo': 'x', 'solicitado_por': 'empresa'})
        with patch('eventos.management.commands.alertar_eventos.notificar', return_value=True) as n:
            call_command('alertar_eventos', stdout=StringIO())
        n.assert_not_called()

    def test_regua_de_cobranca_ignora_adiado(self):
        self.assertNotIn('adiado', regua.STATUS_ELEGIVEIS)


class ContratoAditivoDataTests(BaseAdiamento):
    def test_aditivo_so_de_data(self):
        ev = self.evento(contrato=True)
        self.post(ev, 'remarcar', {'data_evento': self.nova_data(200), 'motivo': 'x', 'solicitado_por': 'cliente'})
        r = self.post(ev, 'gerar-aditivo')
        self.assertEqual(r.status_code, 201, r.data)
        ad = AditivoContrato.objects.get()
        self.assertEqual(str(ad.data_evento_nova), self.nova_data(200))
        self.assertEqual(ad.valor_total_anterior, ad.valor_total_novo)
        self.assertEqual(
            ad.data_quitacao_nova,
            ad.data_evento_nova - datetime.timedelta(days=ConfiguracaoContrato.get().prazo_quitacao_dias),
        )
        from .pdf_aditivo import gerar_pdf_aditivo
        self.assertTrue(gerar_pdf_aditivo(ad).startswith(b'%PDF'))
        # depois do aditivo, sem divergência → sem_alteracao
        ev = Evento.objects.get(pk=ev.pk)
        self.assertEqual(self.post(ev, 'gerar-aditivo').data['detail'], 'sem_alteracao')

    def test_aditivo_de_data_e_valor(self):
        ev = self.evento(contrato=True)
        self.post(ev, 'remarcar', {'data_evento': self.nova_data(200), 'motivo': 'x', 'solicitado_por': 'cliente'})
        ItemEvento.objects.create(evento=ev, nome='Doce', preco_unit=50, quantidade=1)
        ev.recalcular_totais()
        r = self.post(ev, 'gerar-aditivo')
        self.assertEqual(r.status_code, 201, r.data)
        ad = AditivoContrato.objects.get()
        self.assertNotEqual(ad.valor_total_anterior, ad.valor_total_novo)
        self.assertIsNotNone(ad.data_evento_nova)
        from .pdf_aditivo import gerar_pdf_aditivo
        self.assertTrue(gerar_pdf_aditivo(ad).startswith(b'%PDF'))

    def test_aditivo_so_de_valor_continua_funcionando(self):
        ev = self.evento(contrato=True)
        ItemEvento.objects.create(evento=ev, nome='Doce', preco_unit=50, quantidade=1)
        ev.recalcular_totais()
        self.assertEqual(self.post(ev, 'gerar-aditivo').status_code, 201)
        self.assertIsNone(AditivoContrato.objects.get().data_evento_nova)

    def test_sem_alteracao(self):
        ev = self.evento(contrato=True)
        self.assertEqual(self.post(ev, 'gerar-aditivo').data['detail'], 'sem_alteracao')

    def test_pdf_contrato_com_e_sem_paragrafo_3(self):
        from .pdf_contrato import gerar_pdf_contrato
        import io
        from pypdf import PdfReader
        textos = {}
        for clausula in (True, False):
            Contrato.objects.all().delete()
            ev = self.evento(contrato=True, clausula=clausula)
            pdf = gerar_pdf_contrato(Contrato.objects.get())
            textos[clausula] = ''.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
        self.assertIn('Parágrafo 3º', textos[True])
        self.assertNotIn('Parágrafo 3º', textos[False])


class AlertarAdiamentosTests(BaseAdiamento):
    def setUp(self):
        super().setUp()
        TelefoneAlertaEvento.objects.create(numero='86999990000')
        self.ev = self.evento(dias=100)
        self.post(self.ev, 'adiar', {'motivo': 'x', 'solicitado_por': 'cliente'})
        self.ad = self.ev.adiamento_vigente

    def rodar(self, *args):
        with patch('eventos.management.commands.alertar_adiamentos.notificar', return_value=True) as n:
            call_command('alertar_adiamentos', *args, stdout=StringIO())
        return n

    def test_decide_o_mais_grave(self):
        cfg = ConfiguracaoAlertaEvento.get()
        self.ad.retomar_contato_em = hoje()
        self.ad.limite = hoje() - datetime.timedelta(days=1)
        self.assertEqual(decidir_alerta(self.ad, cfg, hoje())[0], 'adiamento_vencido')
        self.ad.limite = hoje() + datetime.timedelta(days=cfg.dias_antes_limite_adiamento)
        self.assertEqual(decidir_alerta(self.ad, cfg, hoje())[0], 'adiamento_limite')
        self.ad.limite = hoje() + datetime.timedelta(days=cfg.dias_antes_limite_adiamento + 1)
        self.assertEqual(decidir_alerta(self.ad, cfg, hoje())[0], 'adiamento_contato')
        self.ad.retomar_contato_em = hoje() + datetime.timedelta(days=1)
        self.assertIsNone(decidir_alerta(self.ad, cfg, hoje()))

    def test_um_alerta_por_dia_e_repeticao(self):
        AdiamentoEvento.objects.filter(pk=self.ad.pk).update(
            retomar_contato_em=hoje(), limite=hoje() - datetime.timedelta(days=1),
        )
        n = self.rodar()
        self.assertEqual(n.call_count, 1)
        self.assertEqual(AlertaEventoEnviado.objects.filter(evento=self.ev).count(), 1)
        self.assertEqual(AlertaEventoEnviado.objects.get().tipo, 'adiamento_vencido')
        self.assertEqual(self.rodar().call_count, 0)  # dentro de repetir_adiamento_dias
        AlertaEventoEnviado.objects.update(enviado_em=timezone.now() - datetime.timedelta(days=8))
        self.assertEqual(self.rodar().call_count, 1)

    def test_desligado_nao_envia(self):
        AdiamentoEvento.objects.filter(pk=self.ad.pk).update(retomar_contato_em=hoje())
        cfg = ConfiguracaoAlertaEvento.get()
        cfg.ativo_adiamento = False
        cfg.save()
        self.assertEqual(self.rodar().call_count, 0)

    def test_dry_run_nao_envia_nem_grava(self):
        AdiamentoEvento.objects.filter(pk=self.ad.pk).update(retomar_contato_em=hoje())
        self.assertEqual(self.rodar('--dry-run').call_count, 0)
        self.assertEqual(AlertaEventoEnviado.objects.count(), 0)

    def test_nao_encerra_adiamento_vencido(self):
        AdiamentoEvento.objects.filter(pk=self.ad.pk).update(limite=hoje() - datetime.timedelta(days=30))
        self.rodar()
        self.ev.refresh_from_db()
        self.assertEqual(self.ev.status, 'adiado')
