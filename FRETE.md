# Sistema de Frete (Taxa de Entrega por Bairro)

> Documento de referência para o sistema de cálculo de taxa de entrega.
> Implementado em jul/2026. Para padrões técnicos gerais, ver `CLAUDE.md`.

---

## O que é

Sistema simples de cálculo de frete, sem geolocalização ou distância real — baseado em uma
tabela configurável de **bairro → valor da taxa**, usada para sugerir automaticamente a taxa
de entrega no **PDV Próprio** e em **Orçamentos/Eventos**. O valor sugerido é sempre editável
manualmente antes de salvar.

Não depende de nenhuma API externa (Google Maps, etc.) — é 100% administrável pela equipe da
Arretado, direto pela interface.

---

## Onde mora cada peça (backend)

Tudo vive no app `pdv/`, mesmo sendo usado também por `eventos/` — mesma lógica de dependência
já usada para `ItemOrcamento.produto` / `ItemEvento.produto` (FK para `pdv.Produto`).

### `pdv.TaxaEntregaBairro`

Tabela de bairros cadastrados e sua taxa.

| Campo | Tipo | Descrição |
|---|---|---|
| `bairro` | CharField (único) | Nome do bairro |
| `taxa` | DecimalField | Valor da entrega para esse bairro |
| `ativo` | BooleanField | Se `False`, não aparece mais como opção (histórico é preservado) |

`GET/POST/PATCH/DELETE /api/v1/pdv/taxas-entrega/[{id}/]`

### `pdv.ConfiguracaoEntrega` (singleton)

Guarda o **frete padrão** — usado quando a entrega é por bairro mas nenhum bairro cadastrado
foi selecionado (nem manualmente, nem por auto-detecção). Sempre acessado via
`ConfiguracaoEntrega.get()`, nunca instanciado diretamente (mesmo padrão de
`ParametrosNegocio` e `ConfiguracaoWhatsApp`).

| Campo | Tipo | Descrição |
|---|---|---|
| `frete_padrao` | DecimalField | Valor usado como fallback |

`GET/PATCH /api/v1/pdv/configuracao-entrega/1/`

### Campos de entrega nos pedidos/orçamentos/eventos

| Model | Campos |
|---|---|
| `pdv.PedidoPDV` | `taxa_entrega` (já existia), `bairro_entrega` (novo) |
| `eventos.Orcamento` | `tipo_entrega`, `local` (FK `LocalEvento`), `endereco_avulso`, `bairro_entrega`, `taxa_entrega` |
| `eventos.Evento` | os mesmos campos acima (já tinha `tipo_entrega`/`local`/`endereco_avulso`; `bairro_entrega`/`taxa_entrega` são novos) |

Em todos os casos, `taxa_entrega` é um **snapshot** no momento da venda/criação — igual ao
padrão já usado para preço de itens (`preco_unit` snapshotado no pedido). Alterar a tabela
`TaxaEntregaBairro` depois não muda pedidos já criados.

`recalcular_totais()` de `PedidoPDV`, `Orcamento` e `Evento` soma `taxa_entrega` ao total.

---

## Cadastro (frontend)

### Tela "Taxas de Entrega" (`TaxasEntrega.jsx`, rota `/taxas-entrega`, menu Administração)

- Card no topo para configurar o **frete padrão**.
- Lista de bairros cadastrados (nome + valor + ativo/inativo), com criar/editar/excluir.

### Tela "Locais de Evento" (`Locais.jsx`, rota `/locais-evento`, menu Eventos)

CRUD do model `LocalEvento` (nome, endereço, bairro, cidade, referência, ativo) — usado no
select "Local cadastrado" dos Orçamentos/Eventos. Antes dessa tela, esses locais só podiam ser
cadastrados direto no banco/admin.

---

## Como o valor é sugerido automaticamente

O bairro e a taxa são preenchidos automaticamente conforme a fonte disponível, **sempre na
seguinte ordem de prioridade** (a de cima vence):

### No PDV Próprio (`PDV.jsx`, tipo de pedido = "Delivery")

1. **Seleção manual** do bairro no select do modal de novo pedido.
2. **Endereço do cliente** — se um cliente do CRM for selecionado e o bairro do endereço
   principal dele (`Cliente.endereco_principal.bairro`) bater com um bairro cadastrado.
3. **Frete padrão** — se nenhum bairro for encontrado/selecionado.

O campo de taxa continua um input numérico livre — qualquer sugestão automática pode ser
sobrescrita manualmente.

### Em Orçamentos (`Orcamentos.jsx`, tipo de entrega = "Entrega no local")

1. **Local cadastrado** — se o orçamento usa um `LocalEvento` com bairro preenchido, esse
   bairro **sempre tem prioridade**, mesmo que o cliente selecionado já tenha um bairro
   diferente detectado antes.
2. **Endereço do cliente** — só entra em ação quando **nenhum** local está selecionado (modo
   "endereço avulso") e nenhum bairro já foi escolhido manualmente.
3. **Bairro selecionado manualmente** (select "Bairro" que aparece no modo avulso).
4. **Frete padrão** — fallback final.

Essa prioridade existe porque o local do evento é uma informação mais confiável/específica do
que o cadastro geral do cliente (o cliente pode morar num bairro e fazer a festa em outro).

### Em Eventos (`Eventos.jsx`)

Mesma lógica de local cadastrado (prioridade 1 acima), mas **sem** auto-detecção pelo endereço
do cliente — isso só foi implementado em PDV e Orçamentos.

### Na conversão Orçamento → Evento

`OrcamentoViewSet.converter_em_evento` herda `tipo_entrega`, `local`, `endereco_avulso`,
`bairro_entrega` e `taxa_entrega` diretamente do orçamento de origem (a menos que o payload da
conversão informe valores diferentes) — não reseta para "retirada na loja".

---

## PDF do orçamento

`eventos/pdf_orcamento.py` (`gerar_pdf_orcamento`) inclui uma linha **"Taxa de entrega"** entre
o desconto e o total sempre que `orc.taxa_entrega > 0`.

---

## Possíveis evoluções futuras (não implementadas)

- Cálculo por distância real (Google Distance Matrix, usando `latitude`/`longitude` que já
  existem em `clientes.Endereco`) — hoje não é usado.
- Auto-detecção de bairro também em `Eventos.jsx` a partir do cliente (hoje só via local).
- Geocoding automático de endereços cadastrados para preencher lat/lng.
