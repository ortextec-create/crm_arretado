import datetime
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from clientes.models import Cliente
from notificacoes.models import HistoricoMensagem
from .models import Orcamento, ItemOrcamento, Contrato
from .views import OrcamentoViewSet, ContratoViewSet


class GerarContratoTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
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

    def _post(self, data):
        view = OrcamentoViewSet.as_view({'post': 'gerar_contrato'})
        req = self.factory.post(
            f'/api/v1/eventos/orcamentos/{self.orc.id}/gerar-contrato/', data, format='json',
        )
        return view(req, pk=self.orc.id)

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
        )
        resp = view(req, pk=contrato.id)
        resp.render()
        self.assertEqual(resp.status_code, 200, resp.data)

        contrato.refresh_from_db()
        self.assertEqual(contrato.status, 'enviado')

        msg = HistoricoMensagem.objects.filter(cliente=self.cliente, tipo='contrato').first()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.status, 'enviado')
