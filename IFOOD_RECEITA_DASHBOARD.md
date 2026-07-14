# Divergência de Receita "Hoje" — Dashboard vs Menu iFood

> Investigação feita em 14/jul/2026 (Claude Code). Correção **ainda não decidida** com o usuário —
> ver item 6 de "Pendências Ativas" em `CLAUDE.md`. Este documento existe só para registrar o
> diagnóstico e as opções, não é uma spec de implementação como `Contrato.md`/`FRETE.md`.

---

## 1. Sintoma relatado

O card de iFood no Dashboard (`GET /api/v1/dashboard/resumo/` → `canais.ifood`) mostra pedidos/valor
sempre **menor** do que o total "real" exibido no menu iFood (`IFood.jsx`, card "Receita hoje").

---

## 2. Causa raiz

Não é bug de sincronização — é **critério de status diferente** entre as duas queries:

- **Dashboard** (`dashboard/views.py::DashboardResumoView._canal_dia`):
  ```python
  PedidoUnificado.objects.filter(canal='ifood', status='concluido', pedido_em__date=dia)
      .aggregate(Sum('total'))
  ```
  Soma **só pedidos com `status='concluido'`** (equivalente ao `CONCLUDED` do iFood).

- **Menu iFood** (`ifood/views.py::PedidoIFoodViewSet.estatisticas`, card "Receita hoje" em `IFood.jsx:887`):
  ```python
  qs_hoje = PedidoIFood.objects.filter(ifood_criado_em__date=hoje)
  qs_hoje.aggregate(Sum('total_valor'))
  ```
  Soma **todos os pedidos criados hoje, sem filtro de status** — inclusive pedidos ainda em
  andamento (`PLACED`/`CONFIRMED`/`PREPARATION_STARTED`/`READY_TO_PICKUP`/`DISPATCHED`) e até
  **cancelados** (`CANCELLED`/`CANCELLATION_REQUESTED`).

A contagem de **pedidos** em si bate certinho entre as duas fontes (o signal
`pedidos/apps.py::on_pedido_ifood_save` → `sincronizar_pedido_ifood` nunca perdeu registro nos
testes feitos). A divergência é só no **valor somado**.

### Evidência (consulta feita em 14/jul/2026, dia com 53 pedidos)

| | Pedidos | Receita |
|---|---|---|
| Dashboard (só `status='concluido'`) | 49 | R$ 1.285,71 |
| Menu iFood (todos os status) | 53 | R$ 1.382,63 |

Diferença de R$ 96,92 = 2 pedidos `DISPATCHED` (a caminho, não concluídos) + 2 pedidos
`CANCELLED`/`CANCELLATION_REQUESTED` que o menu iFood está somando como receita.

```python
# Query usada para gerar a tabela acima:
PedidoUnificado.objects.filter(canal='ifood', pedido_em__date=hoje).values('status').annotate(c=Count('id'))
# → cancelado: 2, concluido: 49, em_entrega: 2

PedidoIFood.objects.filter(ifood_criado_em__date=hoje).values('status').annotate(c=Count('id'))
# → CANCELLATION_REQUESTED: 1, CANCELLED: 1, CONCLUDED: 49, DISPATCHED: 2
```

---

## 3. Qual dos dois está "certo"?

Do ponto de vista de negócio, o **Dashboard é o mais correto**: mostra receita efetivamente
concluída, consistente com a filosofia já usada em Eventos (`dashboard.recebido_hoje` de Eventos
também só conta `PagamentoEvento` com `status='pago'`, nunca valor bruto do pedido — ver
`CLAUDE.md` → regra do Dashboard).

O card "Receita hoje" do menu iFood, ao não excluir cancelamentos e pedidos ainda não concluídos,
infla o número — um pedido cancelado nunca devolveu receita nenhuma.

---

## 4. Opções de correção (nenhuma aplicada ainda)

1. **(Recomendado)** Alterar `ifood/views.py::PedidoIFoodViewSet.estatisticas` para excluir
   `CANCELLED`/`CANCELLATION_REQUESTED` do cálculo de `receita`, e opcionalmente separar
   "confirmado/em andamento" de "concluído" nas duas seções (`hoje` e `mes`) — alinharia o menu
   iFood ao mesmo critério do Dashboard.
2. Deixar como está e só deixar documentado que os dois números respondem perguntas diferentes
   ("quanto entrou de fato" vs "quanto foi pedido hoje, incluindo cancelamentos").
3. Adicionar um terceiro número no menu iFood ("pedidos em andamento") em vez de mesclar tudo em
   "Receita hoje", deixando a métrica de receita já nascer sem cancelamento.

Nenhuma dessas opções foi implementada — aguardando decisão do usuário.
