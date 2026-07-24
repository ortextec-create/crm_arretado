from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from usuarios.models import Usuario
from usuarios.views import UsuarioViewSet

from .models import (
    AlertaFinanceiroEnviado,
    CategoriaFinanceira,
    ConfiguracaoFinanceira,
    ContaBancaria,
    ContaPagar,
    DespesaRecorrente,
    Fornecedor,
    MovimentoFinanceiro,
    TelefoneAlertaFinanceiro,
)
from .views import ContaPagarViewSet


def _conta(nome='Caixa da loja', saldo=Decimal('0')):
    return ContaBancaria.objects.create(nome=nome, tipo='caixa', saldo_atual=saldo)


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
            numero=ContaPagar.proximo_numero(), fornecedor=self.fornecedor, categoria=self.categoria,
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
            descricao='Aluguel', categoria=self.categoria, valor=Decimal('1500.00'),
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
            descricao='X', categoria=self.categoria, valor=Decimal('10.00'), dias_vencimento=[0, 40],
        )
        with self.assertRaises(ValidationError):
            despesa.full_clean()


class GerarContasRecorrentesCommandTests(TestCase):
    def setUp(self):
        self.categoria = _categoria_saida()
        ConfiguracaoFinanceira.objects.create(pk=1, horizonte_recorrencia_dias=40)

    def test_gera_conta_pagar_dentro_do_horizonte(self):
        DespesaRecorrente.objects.create(
            descricao='Internet', categoria=self.categoria, valor=Decimal('120.00'), dias_vencimento=[5],
        )
        call_command('gerar_contas_recorrentes')
        self.assertGreaterEqual(ContaPagar.objects.filter(origem='recorrente').count(), 1)
        conta = ContaPagar.objects.filter(origem='recorrente').first()
        self.assertEqual(conta.valor, Decimal('120.00'))
        self.assertEqual(conta.status, 'pendente')

    def test_rodar_duas_vezes_nao_duplica(self):
        DespesaRecorrente.objects.create(
            descricao='Energia', categoria=self.categoria, valor=Decimal('300.00'), dias_vencimento=[1, 15],
        )
        call_command('gerar_contas_recorrentes')
        total_primeira = ContaPagar.objects.filter(origem='recorrente').count()
        call_command('gerar_contas_recorrentes')
        total_segunda = ContaPagar.objects.filter(origem='recorrente').count()
        self.assertEqual(total_primeira, total_segunda)

    def test_despesa_inativa_nao_gera_conta(self):
        DespesaRecorrente.objects.create(
            descricao='Pausada', categoria=self.categoria, valor=Decimal('50.00'),
            dias_vencimento=[1], ativo=False,
        )
        call_command('gerar_contas_recorrentes')
        self.assertEqual(ContaPagar.objects.filter(origem='recorrente').count(), 0)


class AlertarVencimentosCommandTests(TestCase):
    def setUp(self):
        self.categoria = _categoria_saida()
        ConfiguracaoFinanceira.objects.create(pk=1, alerta_antecedencia_dias=3, alerta_repeticao_dias=1)
        TelefoneAlertaFinanceiro.objects.create(numero='5586999990000', nome='Equipe')

    def _conta_pagar(self, dias_para_vencer):
        vencimento = timezone.localdate() + timedelta(days=dias_para_vencer)
        return ContaPagar.objects.create(
            numero=ContaPagar.proximo_numero(), categoria=self.categoria,
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
