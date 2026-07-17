from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from eventos.models import Evento, ItemEvento
from fichas.models import FichaTecnica, ItemFichaTecnica, MateriaPrima
from ifood.models import ItemPedidoIFood, PedidoIFood
from pdv.models import ItemKit, ItemPedidoPDV, PedidoPDV, Produto
from usuarios.models import Usuario
from usuarios.views import UsuarioViewSet

from .claude_client import ClaudeAPIError
from .extracao_nota import extrair_ia, extrair_texto_pdf, extrair_xml, resolver_materia_prima
from .models import ImportacaoNotaFiscal, ItemNotaImportada, MovimentoEstoque, Producao
from .views import ImportacaoNotaFiscalViewSet


def _materia(nome='Farinha', quantidade_estoque=Decimal('10'), **kwargs):
    return MateriaPrima.objects.create(
        nome=nome, unidade_compra='1kg', quantidade_compra=Decimal('1000'),
        unidade_medida='g', valor_compra=Decimal('10.00'),
        quantidade_estoque=quantidade_estoque, **kwargs,
    )


class MovimentoEstoqueRegistrarTests(TestCase):
    def test_entrada_aumenta_saldo(self):
        materia = _materia(quantidade_estoque=Decimal('5'))
        mov = MovimentoEstoque.registrar(
            materia_prima=materia, tipo_movimento='entrada_compra', quantidade=Decimal('3'),
        )
        materia.refresh_from_db()
        self.assertEqual(materia.quantidade_estoque, Decimal('8'))
        self.assertEqual(mov.saldo_anterior, Decimal('5'))
        self.assertEqual(mov.saldo_posterior, Decimal('8'))

    def test_saida_diminui_saldo_e_permite_negativo(self):
        materia = _materia(quantidade_estoque=Decimal('2'))
        MovimentoEstoque.registrar(
            materia_prima=materia, tipo_movimento='saida_venda', quantidade=Decimal('5'),
        )
        materia.refresh_from_db()
        self.assertEqual(materia.quantidade_estoque, Decimal('-3'))

    def test_ajuste_inventario_e_absoluto_nao_delta(self):
        materia = _materia(quantidade_estoque=Decimal('100'))
        MovimentoEstoque.registrar(
            materia_prima=materia, tipo_movimento='ajuste_inventario', quantidade=Decimal('7'),
        )
        materia.refresh_from_db()
        self.assertEqual(materia.quantidade_estoque, Decimal('7'))

    def test_exige_exatamente_um_fk_nenhum_preenchido(self):
        with self.assertRaises(ValidationError):
            MovimentoEstoque.registrar(tipo_movimento='entrada_compra', quantidade=Decimal('1'))

    def test_exige_exatamente_um_fk_ambos_preenchidos(self):
        materia = _materia()
        produto = Produto.objects.create(nome='Brigadeiro', preco=Decimal('5'), tipo='revenda',
                                          materia_prima_origem=materia)
        with self.assertRaises(ValidationError):
            MovimentoEstoque.registrar(
                materia_prima=materia, produto=produto,
                tipo_movimento='entrada_compra', quantidade=Decimal('1'),
            )


class ProducaoTests(TestCase):
    def setUp(self):
        self.materia = _materia(nome='Chocolate', quantidade_estoque=Decimal('10'))
        self.ficha = FichaTecnica.objects.create(nome='Brigadeiro Gourmet', rendimento=50)
        ItemFichaTecnica.objects.create(ficha=self.ficha, materia_prima=self.materia, quantidade=Decimal('5'))
        self.produto = Produto.objects.create(
            nome='Brigadeiro Gourmet', preco=Decimal('3'), tipo='fabricado',
            modo_estoque='estoque', quantidade_estoque=Decimal('0'),
        )
        self.ficha.produto_pdv_id = self.produto.id
        self.ficha.save(update_fields=['produto_pdv_id'])

    def test_executar_debita_insumo_e_credita_produto(self):
        producao = Producao.objects.create(ficha_tecnica=self.ficha, quantidade_produzida=Decimal('10'))
        producao.executar()

        self.materia.refresh_from_db()
        self.produto.refresh_from_db()
        # consumo = 5 * (10/50) = 1
        self.assertEqual(self.materia.quantidade_estoque, Decimal('9'))
        self.assertEqual(self.produto.quantidade_estoque, Decimal('10'))

    def test_executar_rejeita_produto_sob_encomenda(self):
        self.produto.modo_estoque = 'sob_encomenda'
        self.produto.save(update_fields=['modo_estoque'])
        producao = Producao.objects.create(ficha_tecnica=self.ficha, quantidade_produzida=Decimal('10'))
        with self.assertRaises(ValidationError):
            producao.executar()

    def test_executar_rejeita_sem_produto_vinculado(self):
        self.ficha.produto_pdv_id = None
        self.ficha.save(update_fields=['produto_pdv_id'])
        producao = Producao.objects.create(ficha_tecnica=self.ficha, quantidade_produzida=Decimal('10'))
        with self.assertRaises(ValidationError):
            producao.executar()


class DebitoVendaPDVTests(TestCase):
    def setUp(self):
        self.produto = Produto.objects.create(
            nome='Coca-Cola Lata', preco=Decimal('6'), tipo='revenda',
            materia_prima_origem=_materia(nome='Coca-Cola (compra)'),
            quantidade_estoque=Decimal('20'),
        )

    def _criar_pedido(self, status='aberto'):
        pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), status=status)
        ItemPedidoPDV.objects.create(pedido=pedido, produto=self.produto, nome=self.produto.nome,
                                      preco_unit=Decimal('6'), quantidade=3)
        return pedido

    def test_confirmar_debita_estoque(self):
        pedido = self._criar_pedido(status='aberto')
        pedido.status = 'confirmado'
        pedido.save(update_fields=['status'])

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.quantidade_estoque, Decimal('17'))
        self.assertEqual(
            MovimentoEstoque.objects.filter(origem_tipo='pedido_pdv', origem_id=pedido.id).count(), 1,
        )

    def test_salvar_de_novo_nao_duplica_debito(self):
        pedido = self._criar_pedido(status='aberto')
        pedido.status = 'confirmado'
        pedido.save(update_fields=['status'])
        # qualquer save subsequente (ex: mudar observação) não deve debitar de novo
        pedido.observacoes = 'nota qualquer'
        pedido.save(update_fields=['observacoes'])

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.quantidade_estoque, Decimal('17'))
        self.assertEqual(
            MovimentoEstoque.objects.filter(origem_tipo='pedido_pdv', origem_id=pedido.id).count(), 1,
        )

    def test_status_aberto_nao_debita(self):
        self._criar_pedido(status='aberto')
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.quantidade_estoque, Decimal('20'))


class DebitoVendaKitTests(TestCase):
    def test_venda_de_kit_debita_componentes_recursivamente(self):
        brigadeiro = Produto.objects.create(
            nome='Brigadeiro Gourmet', preco=Decimal('3'), tipo='fabricado',
            modo_estoque='estoque', quantidade_estoque=Decimal('50'),
        )
        refrigerante = Produto.objects.create(
            nome='Coca-Cola Lata', preco=Decimal('6'), tipo='revenda',
            materia_prima_origem=_materia(nome='Coca-Cola (compra)'),
            quantidade_estoque=Decimal('20'),
        )
        cesta = Produto.objects.create(nome='Cesta Presente', preco=Decimal('50'), tipo='kit')
        ItemKit.objects.create(kit=cesta, componente=brigadeiro, quantidade=2)
        ItemKit.objects.create(kit=cesta, componente=refrigerante, quantidade=1)

        pedido = PedidoPDV.objects.create(numero=PedidoPDV.proximo_numero(), status='aberto')
        ItemPedidoPDV.objects.create(pedido=pedido, produto=cesta, nome=cesta.nome,
                                      preco_unit=Decimal('50'), quantidade=1)
        pedido.status = 'confirmado'
        pedido.save(update_fields=['status'])

        brigadeiro.refresh_from_db()
        refrigerante.refresh_from_db()
        self.assertEqual(brigadeiro.quantidade_estoque, Decimal('48'))
        self.assertEqual(refrigerante.quantidade_estoque, Decimal('19'))


class DebitoVendaSobEncomendaTests(TestCase):
    def test_venda_sob_encomenda_debita_insumo_direto(self):
        materia = _materia(nome='Farinha de Trigo', quantidade_estoque=Decimal('20'))
        ficha = FichaTecnica.objects.create(nome='Torta de Frango', rendimento=10)
        ItemFichaTecnica.objects.create(ficha=ficha, materia_prima=materia, quantidade=Decimal('2'))
        produto = Produto.objects.create(
            nome='Torta de Frango', preco=Decimal('80'), tipo='fabricado',
            modo_estoque='sob_encomenda', quantidade_estoque=Decimal('0'),
        )
        ficha.produto_pdv_id = produto.id
        ficha.save(update_fields=['produto_pdv_id'])

        evento = Evento.objects.create(
            numero=Evento.proximo_numero(), tipo_evento='aniversario',
            data_evento='2026-08-01', status='pronto',
        )
        ItemEvento.objects.create(evento=evento, produto=produto, nome=produto.nome,
                                   preco_unit=Decimal('80'), quantidade=5, preco_total=Decimal('400'))
        evento.status = 'entregue'
        evento.save(update_fields=['status'])

        materia.refresh_from_db()
        produto.refresh_from_db()
        # consumo = 2 * (5/10) = 1; produto sob_encomenda nunca acumula saldo
        self.assertEqual(materia.quantidade_estoque, Decimal('19'))
        self.assertEqual(produto.quantidade_estoque, Decimal('0'))


class DebitoVendaIFoodTests(TestCase):
    def test_confirmed_debita_por_match_de_nome(self):
        produto = Produto.objects.create(
            nome='Brigadeiro Gourmet', preco=Decimal('3'), tipo='revenda',
            materia_prima_origem=_materia(nome='Chocolate (compra)'),
            quantidade_estoque=Decimal('30'),
        )
        pedido = PedidoIFood.objects.create(ifood_order_id='abc-123', ifood_merchant_id='merch-1')
        ItemPedidoIFood.objects.create(pedido=pedido, nome='Brigadeiro Gourmet', quantidade=4)

        pedido.status = 'CONFIRMED'
        pedido.save(update_fields=['status'])

        produto.refresh_from_db()
        self.assertEqual(produto.quantidade_estoque, Decimal('26'))

    def test_sem_correspondencia_nao_falha_e_nao_debita(self):
        pedido = PedidoIFood.objects.create(ifood_order_id='abc-456', ifood_merchant_id='merch-1')
        ItemPedidoIFood.objects.create(pedido=pedido, nome='Produto Que Nao Existe', quantidade=2)

        pedido.status = 'CONFIRMED'
        pedido.save(update_fields=['status'])  # não deve lançar exceção

        self.assertEqual(
            MovimentoEstoque.objects.filter(origem_tipo='pedido_ifood', origem_id=pedido.id).count(), 0,
        )


NFE_XML_EXEMPLO = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe>
    <infNFe>
      <ide><nNF>8821</nNF></ide>
      <emit><xNome>Distribuidora Center Doces</xNome></emit>
      <det nItem="1">
        <prod>
          <xProd>Choc. Fracionado 70% 1kg</xProd>
          <qCom>3.0000</qCom>
          <vUnCom>42.50</vUnCom>
        </prod>
      </det>
      <det nItem="2">
        <prod>
          <xProd>Leite Cond. Moca 395g</xProd>
          <qCom>24.0000</qCom>
          <vUnCom>6.80</vUnCom>
        </prod>
      </det>
    </infNFe>
  </NFe>
</nfeProc>"""


class ExtrairXMLTests(TestCase):
    def test_extrai_itens_numero_e_fornecedor(self):
        dados = extrair_xml('nota.xml', NFE_XML_EXEMPLO.encode('utf-8'))
        self.assertIsNotNone(dados)
        self.assertEqual(dados['numero_nota'], '8821')
        self.assertEqual(dados['fornecedor_nome'], 'Distribuidora Center Doces')
        self.assertEqual(len(dados['itens']), 2)
        self.assertEqual(dados['itens'][0]['descricao'], 'Choc. Fracionado 70% 1kg')
        self.assertEqual(dados['itens'][0]['quantidade'], Decimal('3.0000'))
        self.assertEqual(dados['itens'][0]['valor_unitario'], Decimal('42.50'))

    def test_ignora_arquivo_sem_extensao_xml(self):
        self.assertIsNone(extrair_xml('nota.pdf', NFE_XML_EXEMPLO.encode('utf-8')))

    def test_xml_invalido_retorna_none(self):
        self.assertIsNone(extrair_xml('nota.xml', b'isso nao e xml'))

    def test_xml_sem_det_retorna_none(self):
        xml_vazio = '<?xml version="1.0"?><root></root>'
        self.assertIsNone(extrair_xml('nota.xml', xml_vazio.encode('utf-8')))


TEXTO_PDF_EXEMPLO = (
    "DANFE - Distribuidora Center Doces\n"
    "001 Choc. Fracionado 70% 1kg UN 3,00 42,5000 127,50\n"
    "002 Leite Cond. Moca 395g UN 24,00 6,8000 163,20\n"
    "003 linha qualquer sem numeros suficientes\n"
)


class ExtrairTextoPdfTests(TestCase):
    @patch('pypdf.PdfReader')
    def test_extrai_itens_com_heuristica(self, mock_reader):
        pagina = type('Pagina', (), {'extract_text': lambda self: TEXTO_PDF_EXEMPLO})()
        mock_reader.return_value.pages = [pagina]

        dados = extrair_texto_pdf('nota.pdf', b'conteudo-pdf-fake')
        self.assertIsNotNone(dados)
        self.assertEqual(len(dados['itens']), 2)
        self.assertEqual(dados['itens'][0]['quantidade'], Decimal('3.00'))
        self.assertEqual(dados['itens'][0]['valor_unitario'], Decimal('42.5000'))

    @patch('pypdf.PdfReader')
    def test_pdf_sem_texto_retorna_none(self, mock_reader):
        pagina = type('Pagina', (), {'extract_text': lambda self: ''})()
        mock_reader.return_value.pages = [pagina]
        self.assertIsNone(extrair_texto_pdf('nota.pdf', b'conteudo-pdf-fake'))

    def test_ignora_arquivo_sem_extensao_pdf(self):
        self.assertIsNone(extrair_texto_pdf('nota.xml', b'qualquer coisa'))


class ResolverMateriaPrimaTests(TestCase):
    def test_match_exato(self):
        materia = _materia(nome='Chocolate 70%')
        self.assertEqual(resolver_materia_prima('Chocolate 70%', MateriaPrima), materia)

    def test_match_parcial(self):
        materia = _materia(nome='Chocolate 70%')
        self.assertEqual(resolver_materia_prima('Chocolate Fracionado', MateriaPrima), materia)

    def test_sem_match(self):
        self.assertIsNone(resolver_materia_prima('Item Totalmente Desconhecido XYZ', MateriaPrima))


class ExtrairIATests(TestCase):
    @patch('estoque.claude_client.extrair_nota_fiscal')
    def test_falha_da_api_vira_none_sem_lancar(self, mock_extrair):
        mock_extrair.side_effect = ClaudeAPIError('sem API key')
        self.assertIsNone(extrair_ia('nota.jpg', b'fake', 'image/jpeg'))

    @patch('estoque.claude_client.extrair_nota_fiscal')
    def test_sucesso_normaliza_decimais(self, mock_extrair):
        mock_extrair.return_value = {
            'numero_nota': '123', 'fornecedor_nome': 'Fornecedor X',
            'itens': [{'descricao': 'Item A', 'quantidade': 2, 'valor_unitario': 10.5}],
        }
        dados = extrair_ia('nota.jpg', b'fake', 'image/jpeg')
        self.assertIsNotNone(dados)
        self.assertEqual(dados['itens'][0]['quantidade'], Decimal('2'))
        self.assertEqual(dados['itens'][0]['valor_unitario'], Decimal('10.5'))


class ImportacaoNotaFiscalViewSetTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = Usuario(name='Admin Teste', email='admin-nf@teste.com', role='admin')
        self.admin.set_password('senha-123')
        self.admin.save()
        self.materia = _materia(nome='Chocolate 70%', quantidade_estoque=Decimal('0'))

    def _token(self):
        resp = UsuarioViewSet.as_view({'post': 'login'})(self.factory.post(
            '/api/v1/usuarios/login/', {'email': 'admin-nf@teste.com', 'password': 'senha-123'}, format='json',
        ))
        return resp.data['token']

    def _auth_header(self):
        return {'HTTP_AUTHORIZATION': f'Token {self._token()}'}

    def _criar_importacao(self):
        return ImportacaoNotaFiscal.objects.create(metodo_extracao='xml', numero_nota='123', status='em_revisao')

    def test_confirmar_rejeita_item_pendente_de_revisao(self):
        importacao = self._criar_importacao()
        ItemNotaImportada.objects.create(
            importacao=importacao, descricao_extraida='Item Desconhecido',
            quantidade=Decimal('1'), valor_unitario=Decimal('5'), status_match='revisar',
        )
        view = ImportacaoNotaFiscalViewSet.as_view({'post': 'confirmar'})
        req = self.factory.post(f'/api/v1/estoque/notas/{importacao.id}/confirmar/', **self._auth_header())
        resp = view(req, pk=importacao.id)
        self.assertEqual(resp.status_code, 400)
        importacao.refresh_from_db()
        self.assertEqual(importacao.status, 'em_revisao')

    def test_confirmar_gera_movimento_e_atualiza_custo(self):
        importacao = self._criar_importacao()
        ItemNotaImportada.objects.create(
            importacao=importacao, descricao_extraida='Chocolate 70%', quantidade=Decimal('3'),
            valor_unitario=Decimal('42.50'), materia_prima=self.materia, status_match='encontrado',
        )
        view = ImportacaoNotaFiscalViewSet.as_view({'post': 'confirmar'})
        req = self.factory.post(f'/api/v1/estoque/notas/{importacao.id}/confirmar/', **self._auth_header())
        resp = view(req, pk=importacao.id)
        self.assertEqual(resp.status_code, 200)

        importacao.refresh_from_db()
        self.materia.refresh_from_db()
        self.assertEqual(importacao.status, 'confirmada')
        self.assertEqual(self.materia.quantidade_estoque, Decimal('3.000'))
        self.assertEqual(self.materia.valor_compra, Decimal('127.50'))
        self.assertEqual(
            MovimentoEstoque.objects.filter(origem_tipo='nota_fiscal', origem_id=importacao.id).count(), 1,
        )

    def test_confirmar_ignora_item_descartado(self):
        importacao = self._criar_importacao()
        ItemNotaImportada.objects.create(
            importacao=importacao, descricao_extraida='Item Descartado', quantidade=Decimal('1'),
            valor_unitario=Decimal('5'), status_match='revisar', descartado=True,
        )
        view = ImportacaoNotaFiscalViewSet.as_view({'post': 'confirmar'})
        req = self.factory.post(f'/api/v1/estoque/notas/{importacao.id}/confirmar/', **self._auth_header())
        resp = view(req, pk=importacao.id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(MovimentoEstoque.objects.filter(origem_tipo='nota_fiscal').count(), 0)

    def test_editar_item_cria_nova_materia_prima(self):
        importacao = self._criar_importacao()
        item = ItemNotaImportada.objects.create(
            importacao=importacao, descricao_extraida='Corante Gel Vermelho', quantidade=Decimal('2'),
            valor_unitario=Decimal('11.30'), status_match='revisar',
        )
        view = ImportacaoNotaFiscalViewSet.as_view({'patch': 'editar_item'})
        req = self.factory.patch(
            f'/api/v1/estoque/notas/{importacao.id}/itens/{item.id}/',
            {'criar_nova_materia_prima': True}, format='json', **self._auth_header(),
        )
        resp = view(req, pk=importacao.id, item_id=item.id)
        self.assertEqual(resp.status_code, 200)

        item.refresh_from_db()
        self.assertEqual(item.status_match, 'encontrado')
        self.assertIsNotNone(item.materia_prima)
        self.assertEqual(item.materia_prima.nome, 'Corante Gel Vermelho')
        self.assertEqual(item.materia_prima.valor_compra, Decimal('22.60'))

    def test_bloqueia_sem_token_401(self):
        importacao = self._criar_importacao()
        view = ImportacaoNotaFiscalViewSet.as_view({'post': 'confirmar'})
        req = self.factory.post(f'/api/v1/estoque/notas/{importacao.id}/confirmar/')
        resp = view(req, pk=importacao.id)
        self.assertEqual(resp.status_code, 401)
