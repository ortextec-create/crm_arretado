from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from eventos.models import Evento, ItemEvento
from fichas.models import FichaTecnica, ItemFichaTecnica, MateriaPrima
from ifood.models import ItemPedidoIFood, PedidoIFood
from pdv.models import ItemKit, ItemPedidoPDV, PedidoPDV, Produto

from .models import MovimentoEstoque, Producao


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
