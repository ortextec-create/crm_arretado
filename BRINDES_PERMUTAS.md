# Brindes e Permutas (Itens sem Faturamento)

> Spec para implementação via Claude Code. Segue os padrões obrigatórios de `CLAUDE.md`.
> Sem mockup prévio — desenho definido em sessão de arquitetura (Claude.ai), decisões registradas abaixo.
> Requisito de revenda: nenhuma regra específica do negócio Arretado hardcoded (a distinção
> venda/brinde/permuta é genérica, útil pra qualquer cliente de resale).

---

## O que é

Hoje todo item de Orçamento/Evento/PDV é sempre uma venda faturada. Surgiu a necessidade de
registrar itens que saem do estoque **sem gerar receita**, em dois sabores distintos:

- **Brinde** — saída sem contrapartida nenhuma (cortesia, mimo, item extra num evento).
- **Permuta** — saída com contrapartida, só que não é dinheiro (produto trocado por serviço de
  um fornecedor — ex.: bolos em troca de fotografia de casamento).

Os dois têm em comum "não fatura em R$" (mesmo mecanismo de cálculo), mas divergem no que vale
registrar como observação (permuta idealmente descreve o que foi recebido em troca).

Aplica-se em dois contextos:
1. **Dentro de um Orçamento/Evento** — item avulso marcado como brinde/permuta, misturado com
   itens vendidos normalmente no mesmo pedido (ex.: 10 docinhos vendidos + 1 bolo de brinde).
2. **Avulso, sem Orçamento/Evento** — reaproveita o PDV Próprio (decisão desta sessão, ver
   "PDV Avulso" abaixo).

---

## Onde mora cada peça (backend)

### Campo novo `natureza` em `ItemOrcamento`, `ItemEvento` e `ItemPedidoPDV`

Os três models (`eventos.ItemOrcamento`, `eventos.ItemEvento`, `pdv.ItemPedidoPDV`) já têm a
mesma estrutura (`produto`, `nome`, `preco_unit`, `quantidade`, `preco_total`, `observacao`) e o
mesmo padrão de `save()`. Adicionar o mesmo campo aos três:

| Campo | Tipo | Notas |
|---|---|---|
| `natureza` | CharField choices: `venda` / `brinde` / `permuta` | default `venda` |

Granularidade é **por item**, não por pedido/orçamento/evento inteiro — o caso real é misto
(pedido com itens vendidos e itens de brinde juntos).

### Efeito no cálculo de totais (mudança central da feature)

O `save()` dos três models passa a zerar `preco_total` quando `natureza != 'venda'`:

```python
def save(self, *args, **kwargs):
    self.preco_total = (self.preco_unit * self.quantidade) if self.natureza == 'venda' else Decimal('0')
    super().save(*args, **kwargs)
```

`preco_unit` continua sendo sempre o preço de tabela (snapshot do catálogo no momento em que o
item foi adicionado) — vira a referência de "valor de mercado" exibida riscada no PDF (ver
abaixo). Só `preco_total` (o que efetivamente compõe o total cobrado) zera.

Como `Orcamento.recalcular_totais()` / `Evento.recalcular_totais()` / `PedidoPDV.recalcular_totais()`
já fazem `subtotal = sum(i.preco_total for i in self.itens.all())` — soma pura, sem filtro —,
zerar no item cascateia sozinho, **sem tocar em nenhum desses três métodos**:

- `subtotal` / `valor_total` já saem corretos
- `Evento.saldo_restante` (`valor_total - sinal_pago`) já sai correto
- Dashboard (`ticket_medio`, que usa `valor_total`/`Evento.valor_total`) já sai correto
- PDF (que imprime `preco_unit` × `quantidade` × `preco_total` por linha) já mostra a linha
  zerada automaticamente

### Conversão Orçamento → Evento (único ponto de atenção real)

`OrcamentoViewSet.converter_em_evento` cria cada `ItemEvento` via `.objects.create(...)`
passando `preco_unit`/`quantidade`/`preco_total` do item de origem. Como o `save()` de
`ItemEvento` recalcula `preco_total` a partir de `natureza` (e não confia no valor passado),
é **obrigatório** propagar `natureza=item.natureza` nessa chamada — sem isso, todo item de
brinde/permuta de um orçamento convertido viraria venda no evento.

### Débito de estoque — sem mudança

`estoque/signals.py::_debitar_pedido_pdv` e o débito de Evento iteram os itens e debitam por
`produto` + `quantidade`, sem olhar preço nenhum. Brinde e permuta já debitam estoque
normalmente hoje, de graça — o produto físico sai do estoque independente de ser vendido,
dado ou trocado.

### Impacto no Financeiro — um guard pequeno

`financeiro/signals.py::_registrar_venda_pdv` (e o signal de `PagamentoEvento`) grava
`MovimentoFinanceiro` com o valor do pedido/pagamento sem checar se é zero — hoje nunca
acontece de ser zero porque toda venda tem preço. Com brinde/permuta possíveis, um `PedidoPDV`
inteiro de brinde teria `total = 0`. Sem guard, isso geraria uma entrada fantasma de R$0,00 no
ledger (inofensiva, mas suja o extrato e o `fluxo-caixa/`). Adicionar no início do signal:

```python
if pedido.total <= 0:
    return
```

Nenhuma outra parte do módulo Financeiro muda — `ContaReceber`/`ContaPagar` não entram nessa
feature.

---

## PDF (Orçamento e Contrato)

Decisão desta sessão: itens de brinde/permuta **aparecem no PDF**, com transparência total pro
cliente — mostra o valor de tabela riscado + rótulo, e total R$ 0,00.

- **`pdf_orcamento.py`** (canvas cru, ReportLab): na linha do item, desenhar o texto do
  `preco_unit` com uma linha por cima (ou usar o próprio `canvas.line()` sobre o texto) e
  acrescentar `" — Brinde"` / `" — Permuta"` ao lado do nome. Total da linha impresso como
  `R$ 0,00`.
- **`pdf_contrato.py`** (ReportLab Platypus): mais simples — a tag `<strike>` já é nativa do
  `Paragraph` do ReportLab, só envolver o trecho do valor.
- **`pdf_resumo_cozinha.py`** — sem mudança (já não expõe preço de nenhum item, brinde/permuta
  aparecem na lista de produção normalmente).

---

## PDV Avulso (sem Orçamento/Evento)

Decisão desta sessão: **reaproveitar o PDV Próprio** — não criar um registro dedicado novo.
Uma saída avulsa de brinde/permuta é um `PedidoPDV` normal, criado pela tela que já existe,
com item(s) marcados `natureza=brinde`/`permuta`.

- `PedidoPDV.pagamento` já é opcional (`blank=True` no model atual) — um pedido 100%
  brinde/permuta simplesmente deixa o campo vazio.
- Pedido misto (parte vendida + parte brinde no mesmo carrinho) reflete a forma de pagamento
  só da parte vendida — que já é o único valor que sobra em `total` depois do cálculo acima.
- Ganha de graça: numeração sequencial (`proximo_numero()`), sincronização com
  `pedidos.PedidoUnificado`, nenhuma tela nova pra construir.

---

## Frontend

Um seletor pequeno por item (Venda / Brinde / Permuta) ao lado do preço, nos três lugares que já
têm o form de adicionar/editar item:

- `Orcamentos.jsx` (modal de item do Orçamento)
- `Eventos.jsx` (modal de item do Evento)
- `PDV.jsx` (carrinho do pedido)

Quando `natureza != 'venda'`: o input de preço fica desabilitado/cinza (sempre = preço de
tabela do produto, não editável), e a linha do item na lista mostra o valor riscado + badge
"Brinde"/"Permuta" — mesmo tratamento visual do PDF.

Campo `observacao` (já existe nos três models, 300 caracteres) é o lugar pra descrever a
permuta em texto livre (ex.: "Permuta — fotografia do evento, Fornecedor XYZ") — decisão desta
sessão de **não** criar vínculo estruturado com `financeiro.Fornecedor` por ora.

---

## Relatórios / Dashboard

**Decisão default proposta (confirmar antes da Fase 2):** itens `brinde`/`permuta` ficam **fora**
do ranking de `relatorios.ProdutosMaisVendidosView` — ele mede venda concretizada, mesmo
raciocínio já usado pra excluir itens de Orçamento (cotação não é venda fechada). Ajustar o
filtro de quantidade/valor pra considerar só `natureza='venda'` nos três canais.

Nenhum card novo no Dashboard nesta entrega — visibilidade gerencial de "quanto saiu de graça/em
permuta no período" fica registrada como evolução futura (ver abaixo), não faz parte do escopo
mínimo.

---

## Fases de Implementação

| Fase | Conteúdo | Critério de pronto |
|---|---|---|
| 1 | Campo `natureza` + migration nos 3 models (`ItemOrcamento`, `ItemEvento`, `ItemPedidoPDV`) + `save()` ajustado + propagação na conversão Orçamento→Evento | testes: item brinde/permuta zera `preco_total`; `recalcular_totais()` bate; conversão propaga `natureza` |
| 2 | Guard de valor zero em `financeiro/signals.py` (PDV e PagamentoEvento) + filtro `natureza='venda'` em `ProdutosMaisVendidosView` | teste: pedido 100% brinde não gera `MovimentoFinanceiro`; ranking não inclui brinde/permuta |
| 3 | PDF: `pdf_orcamento.py` e `pdf_contrato.py` (valor riscado + rótulo) | geração visual conferida manualmente (não dá pra testar layout automaticamente) |
| 4 | Frontend: seletor de natureza em `Orcamentos.jsx`/`Eventos.jsx`/`PDV.jsx` + badge visual na listagem de itens | fluxo manual: criar item de cada natureza nos 3 lugares, conferir total e PDF |
| 5 | Atualização do `CLAUDE.md` canônico (estrutura, endpoints, padrões, "O Que NÃO Fazer") | seção nova coerente com o código |

---

## Endpoints Afetados (sem endpoint novo — só payload)

```
POST   /api/v1/eventos/orcamentos/{id}/itens/                 ← aceita "natureza" (default "venda")
PATCH  /api/v1/eventos/orcamentos/{id}/itens/{item_id}/editar/ ← idem
POST   /api/v1/eventos/{id}/itens/                             ← idem
POST   /api/v1/pdv/pedidos/                                    ← itens do payload aceitam "natureza"
```

Serializers (`ItemOrcamentoCreateSerializer`, `ItemEventoCreateSerializer`,
`ItemPedidoPDVCreateSerializer`) ganham o campo — sem endpoint novo, sem action nova.

---

## O Que NÃO Fazer

- Não permitir editar `preco_unit`/`preco_total` livremente quando `natureza != 'venda'` no
  frontend — preço sempre trava no valor de tabela do produto, o campo é só informativo.
- Não esquecer de propagar `natureza` em `converter_em_evento` — sem isso, item de brinde num
  orçamento vira venda cobrada no evento gerado.
- Não contar item `brinde`/`permuta` em `ProdutosMaisVendidosView` — filtrar por
  `natureza='venda'` nos três canais.
- Não deixar o signal financeiro gravar `MovimentoFinanceiro` de valor zero — guard
  `if valor <= 0: return` no início de `_registrar_venda_pdv` (e equivalente, se necessário, no
  signal de `PagamentoEvento`).
- Não criar vínculo estruturado com `financeiro.Fornecedor` para permuta nesta entrega — decisão
  consciente, `observacao` de texto livre é suficiente por ora (revisitar se o usuário pedir
  relatório por fornecedor permutado).
- Não criar um registro/tela dedicada para saída avulsa — decisão desta sessão foi reaproveitar
  o `PedidoPDV` existente, não construir um fluxo paralelo.
- Não esconder o item de brinde/permuta do PDF — decisão desta sessão foi mostrar com
  transparência (valor riscado + rótulo), não omitir.

---

## Possíveis evoluções futuras (não implementadas)

- Vínculo estruturado de permuta com `financeiro.Fornecedor` + valor de referência do serviço
  recebido, habilitando relatório "quanto foi permutado com cada fornecedor".
- Card/aba dedicado no Dashboard ou Relatórios: "Brindes & Permutas do período" (quantidade +
  valor de tabela dado/trocado), pra visibilidade gerencial do custo de marketing via brinde.
- Registro contábil formal de permuta como troca de obrigações (ContaPagar do serviço recebido,
  baixada via "quitado por permuta" em vez de movimento em caixa) — hoje o módulo Financeiro
  assume baixa sempre = movimento de caixa; formalizar permuta como ContaPagar quitada por bens
  é uma mudança de escopo maior, fora desta entrega.
- Implicação fiscal de permuta (nota fiscal de troca) — depende da definição de NFC-e/gateway
  (Focus NFe), já é pendência separada em aberto no CLAUDE.md.
