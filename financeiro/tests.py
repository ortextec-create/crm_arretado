from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from clientes.models import Cliente
from empresas.models import Empresa
from eventos.models import Evento, PagamentoEvento
from ifood.models import PedidoIFood
from pdv.models import PedidoPDV
from usuarios.models import Usuario
from usuarios.views import UsuarioViewSet

from .models import (
    AlertaFinanceiroEnviado,
    CategoriaFinanceira,
    ConfiguracaoFinanceira,
    ContaBancaria,
    ContaPagar,
    ContaReceber,
    DespesaRecorrente,
    Fornecedor,
    MovimentoFinanceiro,
    SaldoConferido,
    TelefoneAlertaFinanceiro,
)
from .views import (
    ContaPagarViewSet,
    ContaReceberViewSet,
    FluxoCaixaView,
    MovimentoFinanceiroViewSet,
    SaldoConferidoViewSet,
)


def _conta(nome='Caixa da loja', saldo=Decimal('0'), empresa=None):
    return ContaBancaria.objects.create(
        nome=nome, tipo='caixa', saldo_atual=saldo, empresa=empresa or Empresa.get_padrao(),
    )


def _categoria_saida(nome='Fornecedores'):
    return CategoriaFinanceira.objects.create(nome=nome, tipo='saida')


class MovimentoFinanceiroRegistrarTests(TestCase):
    def test_entrada_aumenta_saldo(self):
        conta = _conta(saldo=Decimal('100.00'))
        mov = MovimentoFinanceiro.registrar(
            conta=conta, tipo='entrada', valor=Decimal('50.00'), origem_tipo='manual',
        )
        conta.refresh_from_db()
        self.assertEqual(conta.saldo_atual, Decimal('150.00'))
        self.assertEqual(mov.saldo_posterior, Decimal('150.00'))

    def test_saida_diminui_saldo(self):
        conta = _conta(saldo=Decimal('100.00'))
        MovimentoFinanceiro.registrar(
            conta=conta, tipo='saida', valor=Decimal('30.00'), origem_tipo='manual',
        )
        conta.refresh_from_db()
        self.assertEqual(conta.saldo_atual, Decimal('70.00'))

    def test_quantiza_valor_a_duas_casas(self):
        conta = _conta()
        mov = MovimentoFinanceiro.registrar(
            conta=conta, tipo='entrada', valor=Decimal('10.005'), origem_tipo='manual',
        )
        self.assertEqual(mov.valor, Decimal('10.01'))  # ROUND_HALF_UP

    def test_valor_zero_ou_negativo_rejeitado(self):
        conta = _conta()
        with self.assertRaises(ValidationError):
            MovimentoFinanceiro.registrar(
                conta=conta, tipo='entrada', valor=Decimal('0'), origem_tipo='manual',
            )

    def test_tipo_invalido_rejeitado(self):
        conta = _conta()
        with self.assertRaises(ValidationError):
            MovimentoFinanceiro.registrar(
                conta=conta, tipo='transferencia', valor=Decimal('10'), origem_tipo='manual',
            )

    def test_constraint_idempotente_origem_pdv(self):
        conta = _conta()
        MovimentoFinanceiro.registrar(
            conta=conta, tipo='entrada', valor=Decimal('10'), origem_tipo='pdv', origem_id=42,
        )
        with self.assertRaises(ValidationError):
            MovimentoFinanceiro.registrar(
                conta=conta, tipo='entrada', valor=Decimal('10'), origem_tipo='pdv', origem_id=42,
            )

    def test_origem_manual_permite_multiplos_lancamentos(self):
        conta = _conta()
        MovimentoFinanceiro.registrar(conta=conta, tipo='entrada', valor=Decimal('10'), origem_tipo='manual')
        MovimentoFinanceiro.registrar(conta=conta, tipo='entrada', valor=Decimal('10'), origem_tipo='manual')
        self.assertEqual(MovimentoFinanceiro.objects.filter(origem_tipo='manual').count(), 2)


class ContaPagarViewSetTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = Usuario(name='Admin Financeiro', email='admin-fin@teste.com', role='admin')
        self.admin.set_password('senha-123')
        self.admin.save()
        self.categoria = _categoria_saida()
        self.fornecedor = Fornecedor.objects.create(nome='Distribuidora ABC')
        self.conta_bancaria = _conta(saldo=Decimal('1000.00'))

    def _token(self):
        resp = UsuarioViewSet.as_view({'post': 'login'})(self.factory.post(
            '/api/v1/usuarios/login/', {'email': 'admin-fin@teste.com', 'password': 'senha-123'}, format='json',
        ))
        return resp.data['token']

    def _auth_header(self):
        return {'HTTP_AUTHORIZATION': f'Token {self._token()}'}

    def _criar_conta_pagar(self, valor=Decimal('300.00')):
        return ContaPagar.objects.create(
            numero=ContaPagar.proximo_numero(), empresa=Empresa.get_padrao(),
            fornecedor=self.fornecedor, categoria=self.categoria,
            valor=valor, data_emissao='2026-07-01', data_vencimento='2026-07-30',
        )

    def test_create_gera_numero_sequencial(self):
        view = ContaPagarViewSet.as_view({'post': 'create'})
        req = self.factory.post('/api/v1/financeiro/contas-pagar/', {
            'categoria': self.categoria.id, 'fornecedor': self.fornecedor.id,
            'valor': '150.00', 'data_emissao': '2026-07-22', 'data_vencimento': '2026-08-05',
        }, format='json', **self._auth_header())
        resp = view(req)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['numero'], 'CP-0001')
        self.assertEqual(resp.data['status'], 'pendente')

    def test_categoria_de_entrada_e_rejeitada(self):
        categoria_entrada = CategoriaFinanceira.objects.create(nome='Vendas', tipo='entrada')
        view = ContaPagarViewSet.as_view({'post': 'create'})
        req = self.factory.post('/api/v1/financeiro/contas-pagar/', {
            'categoria': categoria_entrada.id, 'valor': '100.00',
            'data_emissao': '2026-07-22', 'data_vencimento': '2026-08-05',
        }, format='json', **self._auth_header())
        resp = view(req)
        self.assertEqual(resp.status_code, 400)

    def test_baixa_parcial_deriva_status_parcial(self):
        conta_pagar = self._criar_conta_pagar(valor=Decimal('300.00'))
        view = ContaPagarViewSet.as_view({'post': 'baixa'})
        req = self.factory.post(f'/api/v1/financeiro/contas-pagar/{conta_pagar.id}/baixa/', {
            'data': '2026-07-22', 'valor': '100.00', 'conta': self.conta_bancaria.id, 'forma': 'pix',
        }, format='json', **self._auth_header())
        resp = view(req, pk=conta_pagar.id)
        self.assertEqual(resp.status_code, 200, resp.data)

        conta_pagar.refresh_from_db()
        self.conta_bancaria.refresh_from_db()
        self.assertEqual(conta_pagar.status, 'parcial')
        self.assertEqual(conta_pagar.valor_pago, Decimal('100.00'))
        self.assertEqual(self.conta_bancaria.saldo_atual, Decimal('900.00'))

    def test_baixa_total_deriva_status_paga(self):
        conta_pagar = self._criar_conta_pagar(valor=Decimal('300.00'))
        view = ContaPagarViewSet.as_view({'post': 'baixa'})
        req = self.factory.post(f'/api/v1/financeiro/contas-pagar/{conta_pagar.id}/baixa/', {
            'data': '2026-07-22', 'valor': '300.00', 'conta': self.conta_bancaria.id, 'forma': 'pix',
        }, format='json', **self._auth_header())
        resp = view(req, pk=conta_pagar.id)
        self.assertEqual(resp.status_code, 200, resp.data)

        conta_pagar.refresh_from_db()
        self.assertEqual(conta_pagar.status, 'paga')
        self.assertEqual(conta_pagar.valor_pago, conta_pagar.valor)

    def test_baixa_rejeita_valor_maior_que_saldo_restante(self):
        conta_pagar = self._criar_conta_pagar(valor=Decimal('100.00'))
        view = ContaPagarViewSet.as_view({'post': 'baixa'})
        req = self.factory.post(f'/api/v1/financeiro/contas-pagar/{conta_pagar.id}/baixa/', {
            'data': '2026-07-22', 'valor': '150.00', 'conta': self.conta_bancaria.id, 'forma': 'pix',
        }, format='json', **self._auth_header())
        resp = view(req, pk=conta_pagar.id)
        self.assertEqual(resp.status_code, 400)

    def test_movimento_gravado_com_origem_conta_pagar(self):
        conta_pagar = self._criar_conta_pagar(valor=Decimal('100.00'))
        view = ContaPagarViewSet.as_view({'post': 'baixa'})
        req = self.factory.post(f'/api/v1/financeiro/contas-pagar/{conta_pagar.id}/baixa/', {
            'data': '2026-07-22', 'valor': '100.00', 'conta': self.conta_bancaria.id, 'forma': 'dinheiro',
        }, format='json', **self._auth_header())
        view(req, pk=conta_pagar.id)
        mov = MovimentoFinanceiro.objects.get(origem_tipo='conta_pagar', origem_id=str(conta_pagar.id))
        self.assertEqual(mov.tipo, 'saida')
        self.assertEqual(mov.valor, Decimal('100.00'))

    def test_cancelar_sem_pagamento_ok(self):
        conta_pagar = self._criar_conta_pagar()
        view = ContaPagarViewSet.as_view({'post': 'cancelar'})
        req = self.factory.post(
            f'/api/v1/financeiro/contas-pagar/{conta_pagar.id}/cancelar/', **self._auth_header(),
        )
        resp = view(req, pk=conta_pagar.id)
        self.assertEqual(resp.status_code, 200)
        conta_pagar.refresh_from_db()
        self.assertEqual(conta_pagar.status, 'cancelada')

    def test_cancelar_com_pagamento_rejeitado(self):
        conta_pagar = self._criar_conta_pagar(valor=Decimal('100.00'))
        baixa_view = ContaPagarViewSet.as_view({'post': 'baixa'})
        req = self.factory.post(f'/api/v1/financeiro/contas-pagar/{conta_pagar.id}/baixa/', {
            'data': '2026-07-22', 'valor': '50.00', 'conta': self.conta_bancaria.id, 'forma': 'pix',
        }, format='json', **self._auth_header())
        baixa_view(req, pk=conta_pagar.id)

        view = ContaPagarViewSet.as_view({'post': 'cancelar'})
        req2 = self.factory.post(
            f'/api/v1/financeiro/contas-pagar/{conta_pagar.id}/cancelar/', **self._auth_header(),
        )
        resp = view(req2, pk=conta_pagar.id)
        self.assertEqual(resp.status_code, 400)

    def test_editar_conta_paga_e_bloqueado(self):
        conta_pagar = self._criar_conta_pagar(valor=Decimal('100.00'))
        baixa_view = ContaPagarViewSet.as_view({'post': 'baixa'})
        req = self.factory.post(f'/api/v1/financeiro/contas-pagar/{conta_pagar.id}/baixa/', {
            'data': '2026-07-22', 'valor': '100.00', 'conta': self.conta_bancaria.id, 'forma': 'pix',
        }, format='json', **self._auth_header())
        baixa_view(req, pk=conta_pagar.id)

        view = ContaPagarViewSet.as_view({'patch': 'partial_update'})
        req2 = self.factory.patch(
            f'/api/v1/financeiro/contas-pagar/{conta_pagar.id}/', {'valor': '999.00'},
            format='json', **self._auth_header(),
        )
        resp = view(req2, pk=conta_pagar.id)
        self.assertEqual(resp.status_code, 400)

    def test_resumo_conta_a_vencer(self):
        self._criar_conta_pagar(valor=Decimal('100.00'))
        view = ContaPagarViewSet.as_view({'get': 'resumo'})
        req = self.factory.get('/api/v1/financeiro/contas-pagar/resumo/')
        resp = view(req)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('em_atraso', resp.data)
        self.assertIn('total_mes', resp.data)
        self.assertIn('pago', resp.data['total_mes'])
        self.assertIn('pendente', resp.data['total_mes'])

    def test_create_exige_login(self):
        view = ContaPagarViewSet.as_view({'post': 'create'})
        req = self.factory.post('/api/v1/financeiro/contas-pagar/', {
            'categoria': self.categoria.id, 'valor': '100.00',
            'data_emissao': '2026-07-22', 'data_vencimento': '2026-08-05',
        }, format='json')
        resp = view(req)
        self.assertEqual(resp.status_code, 401)


class DespesaRecorrenteDatasNoPeriodoTests(TestCase):
    def setUp(self):
        self.categoria = _categoria_saida()

    def _despesa(self, dias):
        return DespesaRecorrente.objects.create(
            descricao='Aluguel', empresa=Empresa.get_padrao(), categoria=self.categoria, valor=Decimal('1500.00'),
            dias_vencimento=dias,
        )

    def test_dia_normal_gera_uma_data_por_mes(self):
        despesa = self._despesa([10])
        datas = despesa.datas_no_periodo(date(2026, 7, 1), date(2026, 9, 30))
        self.assertEqual(datas, [date(2026, 7, 10), date(2026, 8, 10), date(2026, 9, 10)])

    def test_dia_31_em_mes_curto_cai_no_ultimo_dia(self):
        despesa = self._despesa([31])
        # fevereiro/2026 tem 28 dias (2026 não é bissexto)
        datas = despesa.datas_no_periodo(date(2026, 1, 15), date(2026, 3, 31))
        self.assertIn(date(2026, 1, 31), datas)
        self.assertIn(date(2026, 2, 28), datas)
        self.assertIn(date(2026, 3, 31), datas)

    def test_multiplos_dias_no_mesmo_mes(self):
        despesa = self._despesa([1, 30])
        datas = despesa.datas_no_periodo(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(datas, [date(2026, 7, 1), date(2026, 7, 30)])

    def test_fora_do_periodo_e_excluido(self):
        despesa = self._despesa([1])
        datas = despesa.datas_no_periodo(date(2026, 7, 15), date(2026, 8, 31))
        self.assertNotIn(date(2026, 7, 1), datas)
        self.assertIn(date(2026, 8, 1), datas)

    def test_dias_vencimento_invalido_rejeitado_no_clean(self):
        despesa = DespesaRecorrente(
            descricao='X', empresa=Empresa.get_padrao(), categoria=self.categoria,
            valor=Decimal('10.00'), dias_vencimento=[0, 40],
        )
        with self.assertRaises(ValidationError):
            despesa.full_clean()


class GerarContasRecorrentesCommandTests(TestCase):
    def setUp(self):
        self.categoria = _categoria_saida()
        self.empresa = Empresa.get_padrao()
        ConfiguracaoFinanceira.objects.create(empresa=self.empresa, horizonte_recorrencia_dias=40)

    def test_gera_conta_pagar_dentro_do_horizonte(self):
        DespesaRecorrente.objects.create(
            descricao='Internet', empresa=self.empresa, categoria=self.categoria,
            valor=Decimal('120.00'), dias_vencimento=[5],
        )
        call_command('gerar_contas_recorrentes')
        self.assertGreaterEqual(ContaPagar.objects.filter(origem='recorrente').count(), 1)
        conta = ContaPagar.objects.filter(origem='recorrente').first()
        self.assertEqual(conta.valor, Decimal('120.00'))
        self.assertEqual(conta.status, 'pendente')
        self.assertEqual(conta.empresa, self.empresa)

    def test_rodar_duas_vezes_nao_duplica(self):
        DespesaRecorrente.objects.create(
            descricao='Energia', empresa=self.empresa, categoria=self.categoria,
            valor=Decimal('300.00'), dias_vencimento=[1, 15],
        )
        call_command('gerar_contas_recorrentes')
        total_primeira = ContaPagar.objects.filter(origem='recorrente').count()
        call_command('gerar_contas_recorrentes')
        total_segunda = ContaPagar.objects.filter(origem='recorrente').count()
        self.assertEqual(total_primeira, total_segunda)

    def test_despesa_inativa_nao_gera_conta(self):
        DespesaRecorrente.objects.create(
            descricao='Pausada', empresa=self.empresa, categoria=self.categoria, valor=Decimal('50.00'),
            dias_vencimento=[1], ativo=False,
        )
        call_command('gerar_contas_recorrentes')
        self.assertEqual(ContaPagar.objects.filter(origem='recorrente').count(), 0)


class AlertarVencimentosCommandTests(TestCase):
    def setUp(self):
        self.categoria = _categoria_saida()
        self.empresa = Empresa.get_padrao()
        ConfiguracaoFinanceira.objects.create(empresa=self.empresa, alerta_antecedencia_dias=3, alerta_repeticao_dias=1)
        TelefoneAlertaFinanceiro.objects.create(numero='5586999990000', nome='Equipe')

    def _conta_pagar(self, dias_para_vencer):
        vencimento = timezone.localdate() + timedelta(days=dias_para_vencer)
        return ContaPagar.objects.create(
            numero=ContaPagar.proximo_numero(), empresa=self.empresa, categoria=self.categoria,
            valor=Decimal('200.00'), data_emissao=timezone.localdate(), data_vencimento=vencimento,
        )

    @patch('notificacoes.servico.zapi.enviar_texto')
    def test_sem_telefone_nao_envia(self, mock_enviar):
        TelefoneAlertaFinanceiro.objects.all().delete()
        self._conta_pagar(dias_para_vencer=1)
        call_command('alertar_vencimentos')
        mock_enviar.assert_not_called()

    @patch('notificacoes.servico.zapi.enviar_texto')
    def test_conta_dentro_da_antecedencia_dispara_alerta(self, mock_enviar):
        mock_enviar.return_value = {'messageId': 'abc'}
        conta = self._conta_pagar(dias_para_vencer=1)
        call_command('alertar_vencimentos')
        mock_enviar.assert_called_once()
        self.assertEqual(AlertaFinanceiroEnviado.objects.filter(conta_pagar=conta).count(), 1)

    @patch('notificacoes.servico.zapi.enviar_texto')
    def test_conta_em_atraso_tambem_dispara(self, mock_enviar):
        mock_enviar.return_value = {'messageId': 'abc'}
        self._conta_pagar(dias_para_vencer=-5)
        call_command('alertar_vencimentos')
        mock_enviar.assert_called_once()

    @patch('notificacoes.servico.zapi.enviar_texto')
    def test_conta_fora_da_antecedencia_nao_dispara(self, mock_enviar):
        self._conta_pagar(dias_para_vencer=30)
        call_command('alertar_vencimentos')
        mock_enviar.assert_not_called()

    @patch('notificacoes.servico.zapi.enviar_texto')
    def test_nao_repete_no_mesmo_dia(self, mock_enviar):
        mock_enviar.return_value = {'messageId': 'abc'}
        self._conta_pagar(dias_para_vencer=1)
        call_command('alertar_vencimentos')
        call_command('alertar_vencimentos')
        # alerta_repeticao_dias=1 e o segundo envio é no mesmo instante — não deve repetir
        self.assertEqual(mock_enviar.call_count, 1)

    @patch('notificacoes.servico.zapi.enviar_texto')
    def test_conta_paga_nao_dispara(self, mock_enviar):
        conta = self._conta_pagar(dias_para_vencer=1)
        conta.status = 'paga'
        conta.save(update_fields=['status'])
        call_command('alertar_vencimentos')
        mock_enviar.assert_not_called()


# ─── Fase 4: signals PDV/iFood/PagamentoEvento → ledger ────────────────────────

class PdvSignalTests(TestCase):
    def setUp(self):
        self.conta = _conta(saldo=Decimal('0'))
        ConfiguracaoFinanceira.objects.create(empresa=Empresa.get_padrao(), conta_padrao_vendas=self.conta)

    def test_confirmar_pedido_gera_movimento_entrada(self):
        pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), total=Decimal('80.00'))
        pedido.status = 'confirmado'
        pedido.save()
        mov = MovimentoFinanceiro.objects.get(origem_tipo='pdv', origem_id=str(pedido.id))
        self.assertEqual(mov.valor, Decimal('80.00'))
        self.assertEqual(mov.tipo, 'entrada')
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.saldo_atual, Decimal('80.00'))

    def test_confirmar_sem_conta_padrao_nao_gera_movimento(self):
        ConfiguracaoFinanceira.objects.filter(empresa=Empresa.get_padrao()).update(conta_padrao_vendas=None)
        pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), total=Decimal('50.00'))
        pedido.status = 'confirmado'
        pedido.save()
        self.assertFalse(MovimentoFinanceiro.objects.filter(origem_tipo='pdv').exists())

    def test_salvar_confirmado_duas_vezes_nao_duplica(self):
        pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), total=Decimal('30.00'))
        pedido.status = 'confirmado'
        pedido.save()
        pedido.observacoes = 'atualizado depois'
        pedido.save()  # segundo save() com status ainda 'confirmado' — não deve duplicar
        self.assertEqual(MovimentoFinanceiro.objects.filter(origem_tipo='pdv', origem_id=str(pedido.id)).count(), 1)

    def test_cancelar_apos_confirmado_gera_estorno(self):
        pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), total=Decimal('80.00'))
        pedido.status = 'confirmado'
        pedido.save()
        pedido.status = 'cancelado'
        pedido.save()
        estorno = MovimentoFinanceiro.objects.get(origem_tipo='manual', origem_id=f'estorno-pdv-{pedido.id}')
        self.assertEqual(estorno.tipo, 'saida')
        self.assertEqual(estorno.valor, Decimal('80.00'))
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.saldo_atual, Decimal('0.00'))

    def test_cancelar_sem_nunca_confirmar_nao_gera_estorno(self):
        pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), total=Decimal('80.00'))
        pedido.status = 'cancelado'
        pedido.save()
        self.assertFalse(MovimentoFinanceiro.objects.filter(origem_tipo='manual').exists())

    def test_confirmar_pedido_100_por_cento_brinde_nao_gera_movimento(self):
        # Fase 2 do BRINDES_PERMUTAS.md: pedido com total=0 (só itens de brinde/permuta)
        # não deve virar uma entrada fantasma de R$0,00 no ledger.
        pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), total=Decimal('0.00'))
        pedido.status = 'confirmado'
        pedido.save()
        self.assertFalse(MovimentoFinanceiro.objects.filter(origem_tipo='pdv').exists())


class IfoodSignalTests(TestCase):
    def setUp(self):
        self.conta = _conta(saldo=Decimal('0'))
        self.cfg = ConfiguracaoFinanceira.objects.create(empresa=Empresa.get_padrao(), conta_padrao_vendas=self.conta)

    def _pedido(self, order_id='order-1'):
        return PedidoIFood.objects.create(
            ifood_order_id=order_id, ifood_merchant_id='merch-1', total_valor=Decimal('45.00'),
            empresa=Empresa.get_padrao(),
        )

    def test_concluded_no_ato_gera_movimento_direto(self):
        pedido = self._pedido()
        pedido.status = 'CONCLUDED'
        pedido.save()
        mov = MovimentoFinanceiro.objects.get(origem_tipo='ifood', origem_id=str(pedido.id))
        self.assertEqual(mov.valor, Decimal('45.00'))
        self.assertFalse(ContaReceber.objects.filter(origem_canal='ifood').exists())

    def test_status_intermediario_nao_gera_nada(self):
        pedido = self._pedido()
        pedido.status = 'CONFIRMED'
        pedido.save()
        self.assertFalse(MovimentoFinanceiro.objects.filter(origem_tipo='ifood').exists())

    def test_concluded_repasse_gera_conta_receber_com_vencimento_correto(self):
        self.cfg.recebimento_ifood = 'repasse'
        self.cfg.dias_repasse_ifood = 15
        self.cfg.save()
        pedido = self._pedido()
        pedido.status = 'CONCLUDED'
        pedido.save()

        self.assertFalse(MovimentoFinanceiro.objects.filter(origem_tipo='ifood').exists())
        conta_receber = ContaReceber.objects.get(origem_canal='ifood', origem_id=str(pedido.id))
        self.assertEqual(conta_receber.valor, Decimal('45.00'))
        self.assertEqual(conta_receber.canal, 'ifood')
        self.assertEqual(conta_receber.data_vencimento, pedido.criado_em.date() + timedelta(days=15))

    def test_concluded_duas_vezes_nao_duplica(self):
        pedido = self._pedido()
        pedido.status = 'CONCLUDED'
        pedido.save()
        pedido.save()
        self.assertEqual(MovimentoFinanceiro.objects.filter(origem_tipo='ifood', origem_id=str(pedido.id)).count(), 1)

    def test_cancelled_apos_no_ato_estorna(self):
        pedido = self._pedido()
        pedido.status = 'CONCLUDED'
        pedido.save()
        pedido.status = 'CANCELLED'
        pedido.save()
        self.assertTrue(
            MovimentoFinanceiro.objects.filter(origem_tipo='manual', origem_id=f'estorno-ifood-{pedido.id}').exists()
        )

    def test_cancelled_apos_repasse_cancela_conta_receber(self):
        self.cfg.recebimento_ifood = 'repasse'
        self.cfg.save()
        pedido = self._pedido()
        pedido.status = 'CONCLUDED'
        pedido.save()
        pedido.status = 'CANCELLED'
        pedido.save()

        conta_receber = ContaReceber.objects.get(origem_canal='ifood', origem_id=str(pedido.id))
        self.assertEqual(conta_receber.status, 'cancelada')
        self.assertFalse(MovimentoFinanceiro.objects.filter(origem_tipo='manual').exists())


class PagamentoEventoSignalTests(TestCase):
    def setUp(self):
        self.conta = _conta(saldo=Decimal('0'))
        ConfiguracaoFinanceira.objects.create(empresa=Empresa.get_padrao(), conta_padrao_vendas=self.conta)
        self.cliente = Cliente.objects.create(nome='Cliente Teste', telefone_principal='86999998888')
        self.evento = Evento.objects.create(
            numero=Evento.proximo_numero(), cliente=self.cliente, tipo_evento='aniversario',
            data_evento=date.today() + timedelta(days=10), status='orcamento',
        )

    def test_pagamento_pago_gera_movimento(self):
        pagamento = PagamentoEvento.objects.create(evento=self.evento, valor=Decimal('200.00'), status='pago')
        mov = MovimentoFinanceiro.objects.get(origem_tipo='evento_pagamento', origem_id=str(pagamento.id))
        self.assertEqual(mov.valor, Decimal('200.00'))
        self.assertIn(self.evento.numero, mov.descricao)

    def test_pagamento_pendente_nao_gera_movimento(self):
        PagamentoEvento.objects.create(evento=self.evento, valor=Decimal('200.00'), status='pendente')
        self.assertFalse(MovimentoFinanceiro.objects.filter(origem_tipo='evento_pagamento').exists())

    def test_remover_pagamento_pago_gera_estorno(self):
        pagamento = PagamentoEvento.objects.create(evento=self.evento, valor=Decimal('200.00'), status='pago')
        pagamento_id = pagamento.id
        pagamento.delete()
        estorno = MovimentoFinanceiro.objects.get(
            origem_tipo='manual', origem_id=f'estorno-evento-pagamento-{pagamento_id}',
        )
        self.assertEqual(estorno.tipo, 'saida')
        self.assertEqual(estorno.valor, Decimal('200.00'))

    def test_remover_pagamento_pendente_nao_gera_estorno(self):
        pagamento = PagamentoEvento.objects.create(evento=self.evento, valor=Decimal('200.00'), status='pendente')
        pagamento.delete()
        self.assertFalse(MovimentoFinanceiro.objects.filter(origem_tipo='manual').exists())

    def test_pagamento_pago_de_valor_zero_nao_gera_movimento(self):
        # Fase 2 do BRINDES_PERMUTAS.md: guarda defensiva simétrica à do PDV.
        PagamentoEvento.objects.create(evento=self.evento, valor=Decimal('0.00'), status='pago')
        self.assertFalse(MovimentoFinanceiro.objects.filter(origem_tipo='evento_pagamento').exists())


class ContaReceberViewSetTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = Usuario(name='Admin Financeiro', email='admin-cr@teste.com', role='admin')
        self.admin.set_password('senha-123')
        self.admin.save()
        self.categoria = CategoriaFinanceira.objects.create(nome='Vendas', tipo='entrada')
        self.conta_bancaria = _conta(saldo=Decimal('0'))

    def _token(self):
        resp = UsuarioViewSet.as_view({'post': 'login'})(self.factory.post(
            '/api/v1/usuarios/login/', {'email': 'admin-cr@teste.com', 'password': 'senha-123'}, format='json',
        ))
        return resp.data['token']

    def _auth_header(self):
        return {'HTTP_AUTHORIZATION': f'Token {self._token()}'}

    def test_create_manual_forca_canal_e_origem(self):
        view = ContaReceberViewSet.as_view({'post': 'create'})
        req = self.factory.post('/api/v1/financeiro/contas-receber/', {
            'categoria': self.categoria.id, 'valor': '100.00', 'data_vencimento': '2026-08-10',
        }, format='json', **self._auth_header())
        resp = view(req)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['numero'], 'CR-0001')
        self.assertEqual(resp.data['canal'], 'manual')
        self.assertEqual(resp.data['origem_canal'], 'manual')

    def test_create_exige_login(self):
        view = ContaReceberViewSet.as_view({'post': 'create'})
        req = self.factory.post('/api/v1/financeiro/contas-receber/', {
            'categoria': self.categoria.id, 'valor': '100.00', 'data_vencimento': '2026-08-10',
        }, format='json')
        resp = view(req)
        self.assertEqual(resp.status_code, 401)

    def test_baixa_recebe_e_deriva_status_recebida(self):
        conta_receber = ContaReceber.objects.create(
            numero=ContaReceber.proximo_numero(), empresa=Empresa.get_padrao(), categoria=self.categoria,
            valor=Decimal('150.00'), data_vencimento='2026-08-10',
        )
        view = ContaReceberViewSet.as_view({'post': 'baixa'})
        req = self.factory.post(f'/api/v1/financeiro/contas-receber/{conta_receber.id}/baixa/', {
            'data': '2026-07-24', 'valor': '150.00', 'conta': self.conta_bancaria.id, 'forma': 'pix',
        }, format='json', **self._auth_header())
        resp = view(req, pk=conta_receber.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        conta_receber.refresh_from_db()
        self.assertEqual(conta_receber.status, 'recebida')
        self.conta_bancaria.refresh_from_db()
        self.assertEqual(self.conta_bancaria.saldo_atual, Decimal('150.00'))

    def test_baixa_maior_que_saldo_rejeitada(self):
        conta_receber = ContaReceber.objects.create(
            numero=ContaReceber.proximo_numero(), empresa=Empresa.get_padrao(), categoria=self.categoria,
            valor=Decimal('100.00'), data_vencimento='2026-08-10',
        )
        view = ContaReceberViewSet.as_view({'post': 'baixa'})
        req = self.factory.post(f'/api/v1/financeiro/contas-receber/{conta_receber.id}/baixa/', {
            'data': '2026-07-24', 'valor': '999.00', 'conta': self.conta_bancaria.id, 'forma': 'pix',
        }, format='json', **self._auth_header())
        resp = view(req, pk=conta_receber.id)
        self.assertEqual(resp.status_code, 400)

    def test_resumo_inclui_saldo_de_evento_dinamicamente(self):
        cliente = Cliente.objects.create(nome='Cliente Resumo', telefone_principal='86999997777')
        Evento.objects.create(
            numero=Evento.proximo_numero(), cliente=cliente, tipo_evento='aniversario',
            data_evento=date.today() + timedelta(days=5), status='confirmado', valor_total=Decimal('500.00'),
        )
        view = ContaReceberViewSet.as_view({'get': 'resumo'})
        req = self.factory.get('/api/v1/financeiro/contas-receber/resumo/')
        resp = view(req)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data['a_receber'], Decimal('500.00'))
        self.assertIn('proximos_30_dias', resp.data)
        self.assertIn('recebido_hoje', resp.data)


class MovimentoManualTests(TestCase):
    """Fase 6 — POST /financeiro/movimentos/manual/ (lançamento avulso/estorno)."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = Usuario(name='Admin Financeiro', email='admin-manual@teste.com', role='admin')
        self.admin.set_password('senha-123')
        self.admin.save()
        self.conta = _conta(saldo=Decimal('200.00'))

    def _token(self):
        resp = UsuarioViewSet.as_view({'post': 'login'})(self.factory.post(
            '/api/v1/usuarios/login/', {'email': 'admin-manual@teste.com', 'password': 'senha-123'}, format='json',
        ))
        return resp.data['token']

    def _auth_header(self):
        return {'HTTP_AUTHORIZATION': f'Token {self._token()}'}

    def test_lancamento_manual_entrada_grava_no_ledger(self):
        view = MovimentoFinanceiroViewSet.as_view({'post': 'manual'})
        req = self.factory.post('/api/v1/financeiro/movimentos/manual/', {
            'conta': self.conta.id, 'tipo': 'entrada', 'valor': '50.00', 'descricao': 'Saldo inicial',
        }, format='json', **self._auth_header())
        resp = view(req)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['origem_tipo'], 'manual')
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.saldo_atual, Decimal('250.00'))

    def test_lancamento_manual_saida_estorno(self):
        view = MovimentoFinanceiroViewSet.as_view({'post': 'manual'})
        req = self.factory.post('/api/v1/financeiro/movimentos/manual/', {
            'conta': self.conta.id, 'tipo': 'saida', 'valor': '30.00', 'descricao': 'Estorno pagamento EV-0001',
        }, format='json', **self._auth_header())
        resp = view(req)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.saldo_atual, Decimal('170.00'))

    def test_permite_multiplos_lancamentos_manuais(self):
        view = MovimentoFinanceiroViewSet.as_view({'post': 'manual'})
        for _ in range(2):
            req = self.factory.post('/api/v1/financeiro/movimentos/manual/', {
                'conta': self.conta.id, 'tipo': 'entrada', 'valor': '10.00',
            }, format='json', **self._auth_header())
            resp = view(req)
            self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(MovimentoFinanceiro.objects.filter(origem_tipo='manual').count(), 2)

    def test_categoria_de_tipo_diferente_e_rejeitada(self):
        categoria_entrada = CategoriaFinanceira.objects.create(nome='Vendas', tipo='entrada')
        view = MovimentoFinanceiroViewSet.as_view({'post': 'manual'})
        req = self.factory.post('/api/v1/financeiro/movimentos/manual/', {
            'conta': self.conta.id, 'tipo': 'saida', 'valor': '10.00', 'categoria': categoria_entrada.id,
        }, format='json', **self._auth_header())
        resp = view(req)
        self.assertEqual(resp.status_code, 400)

    def test_exige_login(self):
        view = MovimentoFinanceiroViewSet.as_view({'post': 'manual'})
        req = self.factory.post('/api/v1/financeiro/movimentos/manual/', {
            'conta': self.conta.id, 'tipo': 'entrada', 'valor': '10.00',
        }, format='json')
        resp = view(req)
        self.assertEqual(resp.status_code, 401)

    def test_audita_movimento_manual(self):
        from auditoria.models import LogAuditoria

        view = MovimentoFinanceiroViewSet.as_view({'post': 'manual'})
        req = self.factory.post('/api/v1/financeiro/movimentos/manual/', {
            'conta': self.conta.id, 'tipo': 'entrada', 'valor': '10.00',
        }, format='json', **self._auth_header())
        view(req)
        self.assertTrue(LogAuditoria.objects.filter(acao=LogAuditoria.ACAO_MOVIMENTO_MANUAL).exists())


class SaldoConferidoTests(TestCase):
    """Fase 6 — GET/POST /financeiro/conferencias/."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = Usuario(name='Admin Financeiro', email='admin-conf@teste.com', role='admin')
        self.admin.set_password('senha-123')
        self.admin.save()
        self.conta = _conta(saldo=Decimal('300.00'))

    def _token(self):
        resp = UsuarioViewSet.as_view({'post': 'login'})(self.factory.post(
            '/api/v1/usuarios/login/', {'email': 'admin-conf@teste.com', 'password': 'senha-123'}, format='json',
        ))
        return resp.data['token']

    def _auth_header(self):
        return {'HTTP_AUTHORIZATION': f'Token {self._token()}'}

    def test_saldo_calculado_e_snapshot_do_saldo_atual(self):
        view = SaldoConferidoViewSet.as_view({'post': 'create'})
        req = self.factory.post('/api/v1/financeiro/conferencias/', {
            'conta': self.conta.id, 'data': '2026-07-25', 'saldo_informado': '295.00',
        }, format='json', **self._auth_header())
        resp = view(req)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['saldo_calculado']), Decimal('300.00'))
        self.assertEqual(Decimal(resp.data['diferenca']), Decimal('-5.00'))

    def test_criado_por_preenchido_automaticamente(self):
        view = SaldoConferidoViewSet.as_view({'post': 'create'})
        req = self.factory.post('/api/v1/financeiro/conferencias/', {
            'conta': self.conta.id, 'data': '2026-07-25', 'saldo_informado': '300.00',
        }, format='json', **self._auth_header())
        view(req)
        conferencia = SaldoConferido.objects.latest('id')
        self.assertEqual(conferencia.criado_por, self.admin)

    def test_nova_conferencia_nao_edita_anterior(self):
        SaldoConferido.objects.create(
            conta=self.conta, data='2026-07-20', saldo_informado=Decimal('280.00'), saldo_calculado=Decimal('280.00'),
        )
        view = SaldoConferidoViewSet.as_view({'post': 'create'})
        req = self.factory.post('/api/v1/financeiro/conferencias/', {
            'conta': self.conta.id, 'data': '2026-07-25', 'saldo_informado': '300.00',
        }, format='json', **self._auth_header())
        view(req)
        self.assertEqual(SaldoConferido.objects.filter(conta=self.conta).count(), 2)

    def test_exige_login(self):
        view = SaldoConferidoViewSet.as_view({'post': 'create'})
        req = self.factory.post('/api/v1/financeiro/conferencias/', {
            'conta': self.conta.id, 'data': '2026-07-25', 'saldo_informado': '300.00',
        }, format='json')
        resp = view(req)
        self.assertEqual(resp.status_code, 401)


class FluxoCaixaViewTests(TestCase):
    """Fase 6 — GET /financeiro/fluxo-caixa/?dias=N."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.conta = _conta(saldo=Decimal('500.00'))
        self.categoria_saida = _categoria_saida()
        self.categoria_entrada = CategoriaFinanceira.objects.create(nome='Vendas', tipo='entrada')
        self.hoje = timezone.localdate()

    def test_realizado_bate_com_ledger(self):
        MovimentoFinanceiro.registrar(
            conta=self.conta, tipo='entrada', valor=Decimal('80.00'), origem_tipo='manual',
            data_movimento=self.hoje,
        )
        MovimentoFinanceiro.registrar(
            conta=self.conta, tipo='saida', valor=Decimal('20.00'), origem_tipo='manual',
            data_movimento=self.hoje,
        )
        view = FluxoCaixaView.as_view()
        req = self.factory.get('/api/v1/financeiro/fluxo-caixa/?dias=7')
        resp = view(req)
        self.assertEqual(resp.status_code, 200)
        dia_hoje = next(d for d in resp.data['dias'] if d['data'] == self.hoje)
        self.assertEqual(dia_hoje['entrada_realizada'], Decimal('80.00'))
        self.assertEqual(dia_hoje['saida_realizada'], Decimal('20.00'))

    def test_projetado_inclui_conta_a_pagar_pendente(self):
        vencimento = self.hoje + timedelta(days=3)
        ContaPagar.objects.create(
            numero=ContaPagar.proximo_numero(), empresa=Empresa.get_padrao(), categoria=self.categoria_saida,
            valor=Decimal('120.00'), data_emissao=self.hoje, data_vencimento=vencimento,
        )
        view = FluxoCaixaView.as_view()
        req = self.factory.get('/api/v1/financeiro/fluxo-caixa/?dias=7')
        resp = view(req)
        dia = next(d for d in resp.data['dias'] if d['data'] == vencimento)
        self.assertEqual(dia['saida_projetada'], Decimal('120.00'))

    def test_projetado_inclui_conta_a_receber_pendente(self):
        vencimento = self.hoje + timedelta(days=2)
        ContaReceber.objects.create(
            numero=ContaReceber.proximo_numero(), empresa=Empresa.get_padrao(), categoria=self.categoria_entrada,
            valor=Decimal('90.00'), data_vencimento=vencimento,
        )
        view = FluxoCaixaView.as_view()
        req = self.factory.get('/api/v1/financeiro/fluxo-caixa/?dias=7')
        resp = view(req)
        dia = next(d for d in resp.data['dias'] if d['data'] == vencimento)
        self.assertEqual(dia['entrada_projetada'], Decimal('90.00'))

    def test_conta_paga_nao_entra_mais_no_projetado(self):
        vencimento = self.hoje + timedelta(days=1)
        conta_pagar = ContaPagar.objects.create(
            numero=ContaPagar.proximo_numero(), empresa=Empresa.get_padrao(), categoria=self.categoria_saida,
            valor=Decimal('50.00'), data_emissao=self.hoje, data_vencimento=vencimento,
        )
        MovimentoFinanceiro.registrar(
            conta=self.conta, tipo='saida', valor=Decimal('50.00'),
            origem_tipo='conta_pagar', origem_id=conta_pagar.id, data_movimento=self.hoje,
        )
        conta_pagar.recalcular_valor_pago()

        view = FluxoCaixaView.as_view()
        req = self.factory.get('/api/v1/financeiro/fluxo-caixa/?dias=7')
        resp = view(req)
        dia = next(d for d in resp.data['dias'] if d['data'] == vencimento)
        self.assertEqual(dia['saida_projetada'], Decimal('0'))

    def test_saldos_por_conta_e_ultima_conferencia(self):
        SaldoConferido.objects.create(
            conta=self.conta, data=self.hoje, saldo_informado=Decimal('505.00'), saldo_calculado=Decimal('500.00'),
        )
        view = FluxoCaixaView.as_view()
        req = self.factory.get('/api/v1/financeiro/fluxo-caixa/?dias=7')
        resp = view(req)
        conta_resp = next(c for c in resp.data['contas'] if c['id'] == self.conta.id)
        self.assertEqual(conta_resp['saldo_atual'], Decimal('500.00'))
        self.assertEqual(conta_resp['ultima_conferencia']['diferenca'], Decimal('5.00'))

    def test_conta_sem_conferencia_retorna_none(self):
        view = FluxoCaixaView.as_view()
        req = self.factory.get('/api/v1/financeiro/fluxo-caixa/?dias=7')
        resp = view(req)
        conta_resp = next(c for c in resp.data['contas'] if c['id'] == self.conta.id)
        self.assertIsNone(conta_resp['ultima_conferencia'])

    def test_dias_limitado_a_faixa_valida(self):
        view = FluxoCaixaView.as_view()
        req = self.factory.get('/api/v1/financeiro/fluxo-caixa/?dias=500')
        resp = view(req)
        self.assertEqual(len(resp.data['dias']), 90)


# ─── Fase 4 do multi-empresa (MULTIEMPRESA.md): roteamento por empresa ─────────

class MultiEmpresaRoteamentoSignaisTests(TestCase):
    """
    Critério de pronto da Fase 4: com 2 empresas ativas, os 3 signals de
    venda (PDV, iFood, PagamentoEvento) resolvem a conta/config certa —
    iFood pela empresa do próprio pedido, PDV/Eventos sempre na matriz
    (mono-empresa por escopo), mesmo com a 2ª empresa existindo.
    """

    def setUp(self):
        self.matriz = Empresa.get_padrao()
        self.mangaio = Empresa.objects.create(nome='Mangaio')
        self.conta_matriz = _conta(nome='Caixa Matriz', empresa=self.matriz)
        self.conta_mangaio = _conta(nome='Caixa Mangaio', empresa=self.mangaio)
        ConfiguracaoFinanceira.objects.create(empresa=self.matriz, conta_padrao_vendas=self.conta_matriz)
        ConfiguracaoFinanceira.objects.create(
            empresa=self.mangaio, conta_padrao_vendas=self.conta_mangaio,
            recebimento_ifood='repasse', dias_repasse_ifood=20,
        )

    def test_ifood_matriz_no_ato_bate_na_conta_da_matriz(self):
        pedido = PedidoIFood.objects.create(
            ifood_order_id='order-matriz', ifood_merchant_id='merch-matriz',
            total_valor=Decimal('45.00'), empresa=self.matriz,
        )
        pedido.status = 'CONCLUDED'
        pedido.save()
        mov = MovimentoFinanceiro.objects.get(origem_tipo='ifood', origem_id=str(pedido.id))
        self.assertEqual(mov.conta, self.conta_matriz)
        self.conta_mangaio.refresh_from_db()
        self.assertEqual(self.conta_mangaio.saldo_atual, Decimal('0'))

    def test_ifood_mangaio_repasse_gera_conta_receber_da_mangaio(self):
        pedido = PedidoIFood.objects.create(
            ifood_order_id='order-mangaio', ifood_merchant_id='merch-mangaio',
            total_valor=Decimal('60.00'), empresa=self.mangaio,
        )
        pedido.status = 'CONCLUDED'
        pedido.save()
        self.assertFalse(MovimentoFinanceiro.objects.filter(origem_tipo='ifood', origem_id=str(pedido.id)).exists())
        conta_receber = ContaReceber.objects.get(origem_canal='ifood', origem_id=str(pedido.id))
        self.assertEqual(conta_receber.empresa, self.mangaio)
        self.assertEqual(conta_receber.data_vencimento, pedido.criado_em.date() + timedelta(days=20))

    def test_pdv_continua_na_matriz_mesmo_com_mangaio_existindo(self):
        pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), total=Decimal('30.00'))
        pedido.status = 'confirmado'
        pedido.save()
        mov = MovimentoFinanceiro.objects.get(origem_tipo='pdv', origem_id=str(pedido.id))
        self.assertEqual(mov.conta, self.conta_matriz)

    def test_pagamento_evento_continua_na_matriz_mesmo_com_mangaio_existindo(self):
        cliente = Cliente.objects.create(nome='Cliente Multi', telefone_principal='86999996666')
        evento = Evento.objects.create(
            numero=Evento.proximo_numero(), cliente=cliente, tipo_evento='aniversario',
            data_evento=date.today() + timedelta(days=10), status='orcamento',
        )
        pagamento = PagamentoEvento.objects.create(evento=evento, valor=Decimal('90.00'), status='pago')
        mov = MovimentoFinanceiro.objects.get(origem_tipo='evento_pagamento', origem_id=str(pagamento.id))
        self.assertEqual(mov.conta, self.conta_matriz)


class MultiEmpresaFiltroViewSetTests(TestCase):
    """?empresa=<id>|todas em ContaBancariaViewSet — mesmo padrão vale para os demais ViewSets do app."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.matriz = Empresa.get_padrao()
        self.mangaio = Empresa.objects.create(nome='Mangaio')
        self.conta_matriz = _conta(nome='Caixa Matriz', empresa=self.matriz)
        self.conta_mangaio = _conta(nome='Caixa Mangaio', empresa=self.mangaio)

    def test_lista_sem_parametro_cai_na_empresa_padrao(self):
        from .views import ContaBancariaViewSet

        view = ContaBancariaViewSet.as_view({'get': 'list'})
        resp = view(self.factory.get('/api/v1/financeiro/contas-bancarias/'))
        nomes = [c['nome'] for c in resp.data['results']]
        self.assertIn('Caixa Matriz', nomes)
        self.assertNotIn('Caixa Mangaio', nomes)

    def test_lista_filtra_por_empresa_explicita(self):
        from .views import ContaBancariaViewSet

        view = ContaBancariaViewSet.as_view({'get': 'list'})
        resp = view(self.factory.get(f'/api/v1/financeiro/contas-bancarias/?empresa={self.mangaio.id}'))
        nomes = [c['nome'] for c in resp.data['results']]
        self.assertIn('Caixa Mangaio', nomes)
        self.assertNotIn('Caixa Matriz', nomes)

    def test_lista_todas_devolve_as_duas(self):
        from .views import ContaBancariaViewSet

        view = ContaBancariaViewSet.as_view({'get': 'list'})
        resp = view(self.factory.get('/api/v1/financeiro/contas-bancarias/?empresa=todas'))
        nomes = [c['nome'] for c in resp.data['results']]
        self.assertIn('Caixa Matriz', nomes)
        self.assertIn('Caixa Mangaio', nomes)
