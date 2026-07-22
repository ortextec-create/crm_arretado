# FINANCEIRO.md — Contas a Pagar, Contas a Receber e Fluxo de Caixa

> Spec para implementação via Claude Code. Segue os padrões obrigatórios de `CLAUDE.md`.
> Mockup aprovado: `mockup_financeiro.html` (5 abas — Contas a Pagar, Contas a Receber, Fluxo de Caixa, Categorias, Configurações).
> Requisito de revenda: **nenhum valor da Arretado hardcoded** — tudo configurável.

---

## Visão Geral

Novo app Django `financeiro/` com duas camadas, espelhando o padrão já validado no projeto (`Evento` = obrigação, `PagamentoEvento` = baixa, `sinal_pago` sempre derivado):

1. **Obrigação (projetado):** `ContaPagar` e `ContaReceber` — têm vencimento e status, podem nunca acontecer.
2. **Ledger (realizado):** `MovimentoFinanceiro` — fonte única da verdade do que passou pelo caixa. Escrita **exclusivamente** via `MovimentoFinanceiro.registrar()`, mesmo contrato de `estoque.MovimentoEstoque.registrar()`.

A "conciliação" desta fase é interna: fluxo de caixa realizado × projetado + conferência manual de saldo (`SaldoConferido`). Importação de extrato bancário (OFX etc.) está **fora de escopo**.

---

## Fase 0 — Pré-requisitos (executar ANTES de criar o app)

### 0.1 Corrigir bug `itens_json` (Pendência 7 do CLAUDE.md)

`eventos/models.py::sincronizar_evento()` grava `defaults['itens_json']`, campo inexistente em `pedidos.PedidoUnificado` (o campo correto é `itens_snapshot`). Todo `post_save` de `Evento` falha silenciosamente — Evento nunca sincronizou.

- Renomear a chave para `itens_snapshot` (conferir o schema real de `PedidoUnificado` antes; ajustar qualquer outra chave divergente no mesmo `defaults`).
- **Antes de ativar:** verificar que `dashboard/views.py` filtra por `canal` em todas as queries de receita — a receita de Eventos deve continuar vindo **exclusivamente** de `PagamentoEvento` (regra documentada em CLAUDE.md). A entrada de linhas `canal='eventos'` em `PedidoUnificado` não pode gerar dupla contagem em `recebido_hoje`, `grafico_7dias` nem em nenhum agregado. Se alguma query somar sem filtrar canal, corrigir a query junto.
- `fila_operacional` passa a enxergar Eventos — comportamento desejado, validar com teste.
- Backfill: **não** sincronizar eventos antigos retroativamente nesta fase (evita poluir histórico). Apenas eventos salvos a partir da correção.

### 0.2 Atualizar CLAUDE.md (trechos defasados)

- Linha da estrutura de pastas: `estoque/ (Fases 1-5)` → refletir fases 1-8 concluídas.
- Padrões Obrigatórios, bloco Estoque: remover "fases 6-8 de importação de nota fiscal ainda não implementadas".

### 0.3 Setup manual (não é código — lembrar o usuário)

- `ANTHROPIC_API_KEY` no `.env` da VPS (Pendência 9) — necessário para o fallback de IA da importação de nota, que a Fase 5 desta spec utiliza.

---

## Models (`financeiro/models.py`)

### CategoriaFinanceira

| Campo | Tipo | Notas |
|---|---|---|
| nome | CharField(80) | |
| tipo | CharField choices: `entrada` / `saida` | |
| pai | FK self, null=True, on_delete=PROTECT | hierarquia opcional, 1 nível é suficiente |
| ativo | BooleanField default=True | |
| criado_em / atualizado_em | auto | |

`UniqueConstraint(nome, tipo)`. **Nasce vazio** — o usuário cadastra as categorias dele (decisão registrada). Nenhum seed automático.

### ContaBancaria

| Campo | Tipo | Notas |
|---|---|---|
| nome | CharField(60) | ex.: "Nubank", "Caixa da loja" |
| tipo | CharField choices: `banco` / `caixa` | |
| saldo_atual | DecimalField(12,2) default=0 | **atualizado só por `MovimentoFinanceiro.registrar()`** via `update_fields` |
| ativo | BooleanField default=True | |

### Fornecedor

| Campo | Tipo | Notas |
|---|---|---|
| nome | CharField(120) | |
| cnpj | CharField(18), blank | opcional |
| telefone / email | blank | opcionais |
| categoria_padrao | FK CategoriaFinanceira, null=True, SET_NULL | pré-preenche o form |
| ativo | BooleanField default=True | |

### ConfiguracaoFinanceira (singleton)

Mesmo padrão `.get()` de `ConfiguracaoEntrega`/`ConfiguracaoEstoque`.

| Campo | Tipo | Default | Notas |
|---|---|---|---|
| recebimento_ifood | choices: `no_ato` / `repasse` | `no_ato` | decisão registrada — usuário ainda vai coletar o ciclo real |
| dias_repasse_ifood | PositiveSmallIntegerField | 30 | só usado se `repasse` |
| nota_gera_conta_pagar | BooleanField | True | nota confirmada no Estoque vira ContaPagar |
| alerta_antecedencia_dias | PositiveSmallIntegerField | 2 | alerta de vencimento |
| alerta_repeticao_dias | PositiveSmallIntegerField | 1 | repetição se em atraso |
| horizonte_recorrencia_dias | PositiveSmallIntegerField | 40 | até quando o cron gera contas futuras |

### TelefoneAlertaFinanceiro / AlertaFinanceiroEnviado

Cópia estrutural de `TelefoneAlertaEstoque` / `AlertaEstoqueEnviado` (telefones internos da equipe; rastreio de último envio por conta+tipo para controlar repetição). Manter o padrão de lista própria por módulo.

### ContaPagar

| Campo | Tipo | Notas |
|---|---|---|
| numero | CharField(12) | `CP-0001` via `proximo_numero()` (padrão do projeto) |
| fornecedor | FK Fornecedor, null=True, PROTECT | |
| descricao | CharField(160), blank | |
| categoria | FK CategoriaFinanceira, PROTECT, limit tipo=`saida` | validar no serializer |
| valor | DecimalField(12,2) | > 0 |
| data_emissao | DateField | |
| data_vencimento | DateField, db_index | |
| status | choices: `pendente` / `parcial` / `paga` / `cancelada` | **derivado** — ver regra abaixo |
| origem | choices: `manual` / `nota_fiscal` / `recorrente` | |
| nota_fiscal | OneToOneField `estoque.ImportacaoNotaFiscal`, null=True, PROTECT | idempotência da Fase 5 |
| recorrente | FK DespesaRecorrente, null=True, PROTECT | |
| anexo | FileField, blank | boleto/nota — mesmo padrão de `comprovante` de PagamentoEvento |
| observacao | TextField, blank | |
| valor_pago | DecimalField(12,2) default=0 | **derivado** — nunca gravado direto |

Regra (mesma filosofia de `Evento.sinal_pago`): `recalcular_valor_pago()` soma os `MovimentoFinanceiro` com `origem_tipo='conta_pagar'` e `origem_id=self.id`, atualiza `valor_pago` e deriva `status` (`paga` se `valor_pago >= valor`, `parcial` se `0 < valor_pago < valor`, senão mantém `pendente`). Chamado após cada baixa. `cancelada` só via action explícita e só se `valor_pago == 0`.

`UniqueConstraint(recorrente, data_vencimento)` condicional (`recorrente__isnull=False`) — idempotência do cron.

### DespesaRecorrente

| Campo | Tipo | Notas |
|---|---|---|
| descricao | CharField(120) | |
| fornecedor | FK, null=True, PROTECT | |
| categoria | FK CategoriaFinanceira, PROTECT | |
| valor | DecimalField(12,2) | |
| valor_tipo | choices: `fixo` / `estimado` | estimado = valor varia (ex.: energia); a baixa registra o real |
| dias_vencimento | JSONField (lista de ints 1–31) | ex.: `[1, 30]` — Caju da planilha real |
| ativo | BooleanField default=True | pausar = `ativo=False`, nunca deletar com contas geradas (PROTECT cobre) |

Dia inexistente no mês (31 em fevereiro) → usar o último dia do mês.

### ContaReceber

| Campo | Tipo | Notas |
|---|---|---|
| numero | CharField(12) | `CR-0001` via `proximo_numero()` |
| cliente | FK `clientes.Cliente`, null=True, SET_NULL | |
| cliente_nome | CharField(120), blank | snapshot |
| canal | choices: `ifood` / `manual` | ver regra de canais abaixo |
| referencia | CharField(60), blank | nº do pedido |
| categoria | FK, null=True, limit tipo=`entrada` | |
| valor | DecimalField(12,2) | |
| data_vencimento | DateField, db_index | |
| status | choices: `pendente` / `parcial` / `recebida` / `cancelada` | derivado, mesma regra de ContaPagar |
| origem_canal / origem_id | CharField(20) / CharField(64) | idempotência |
| valor_recebido | DecimalField(12,2) default=0 | derivado |

`UniqueConstraint(origem_canal, origem_id)` condicional (`origem_canal != 'manual'`) — padrão de idempotência do projeto.

**Regra de canais (crítica — evita dupla contagem):**
- **PDV:** nunca gera ContaReceber. Venda de balcão é recebida no ato → signal grava `MovimentoFinanceiro` direto.
- **iFood `no_ato`:** idem PDV — movimento direto no status terminal.
- **iFood `repasse`:** signal gera ContaReceber com `data_vencimento = data_pedido + dias_repasse_ifood`. Baixa manual.
- **Eventos:** **nunca materializa ContaReceber.** O saldo restante de eventos confirmados é consultado dinamicamente (`Evento.valor_total - sinal_pago` de eventos não cancelados/entregues) — evita sincronizar dois registros. A entrada de caixa de Eventos vem de `PagamentoEvento` (ver signals). Na aba Contas a Receber do frontend, eventos aparecem via query, com link "Registrar recebimento" abrindo o fluxo de `PagamentoEvento` **já existente** (não criar fluxo paralelo de baixa).

### MovimentoFinanceiro (o ledger)

| Campo | Tipo | Notas |
|---|---|---|
| conta | FK ContaBancaria, PROTECT | |
| tipo | choices: `entrada` / `saida` | |
| valor | DecimalField(12,2) | sempre > 0; o sinal vem de `tipo` |
| data_movimento | DateField, db_index | |
| categoria | FK, null=True, PROTECT | |
| fornecedor / cliente | FKs, null=True, SET_NULL | |
| descricao | CharField(200), blank | |
| forma_pagamento | choices: `pix` / `boleto` / `cartao` / `dinheiro` / `outro`, blank | |
| origem_tipo | choices: `conta_pagar` / `conta_receber` / `pdv` / `ifood` / `evento_pagamento` / `manual` | |
| origem_id | CharField(64), blank | |
| comprovante | FileField, blank | |
| saldo_posterior | DecimalField(12,2) | calculado dentro de `registrar()` |
| criado_em | auto | |
| criado_por | FK Usuario, null=True, SET_NULL | + `criado_por_nome_snapshot` (padrão LogAuditoria) |

**`MovimentoFinanceiro.registrar()` — único ponto de escrita.** Contrato idêntico a `MovimentoEstoque.registrar()`:
- `transaction.atomic()` + `select_for_update()` na `ContaBancaria` (race condition entre baixas concorrentes);
- quantizar `valor` a 2 casas antes de `full_clean()` (lição documentada do módulo Estoque);
- calcular `saldo_posterior`, atualizar `ContaBancaria.saldo_atual` via `update_fields`;
- validar `valor > 0`;
- **nunca** `.objects.create()` direto em view/signal/command.

Idempotência: `UniqueConstraint(origem_tipo, origem_id)` **condicional** — vale só para `origem_tipo in ('pdv', 'ifood', 'evento_pagamento')`. Baixas de conta (`conta_pagar`/`conta_receber`) podem ter vários movimentos (pagamento parcial) e `manual` é livre.

Exclusão de movimento: **não implementar DELETE.** Ledger é imutável — erro se corrige com movimento manual inverso (estorno). Documentar no O Que NÃO Fazer.

### SaldoConferido

| Campo | Tipo | Notas |
|---|---|---|
| conta | FK ContaBancaria, PROTECT | |
| data | DateField | |
| saldo_informado | DecimalField(12,2) | digitado pelo usuário (app do banco) |
| saldo_calculado | DecimalField(12,2) | snapshot no momento da conferência |
| criado_por | FK Usuario, null=True, SET_NULL | |

`diferenca` = property (`saldo_informado - saldo_calculado`). Sem edição — nova conferência substitui a leitura anterior na UI (histórico preservado no banco).

---

## Signals (`financeiro/signals.py`, registrados em `FinanceiroConfig.ready()`)

Todos com try/except + `logger.warning` (nunca quebrar o fluxo de venda), e **todos idempotentes** pela constraint condicional.

1. **`pdv.PedidoPDV`** — no status terminal de confirmação (mesmo gatilho usado pelo débito de estoque em `estoque/signals.py` — conferir e reutilizar o mesmo ponto): `registrar()` entrada, `origem_tipo='pdv'`, `origem_id=pedido.id`, conta = ContaBancaria padrão (ver nota abaixo), categoria null (usuário pode categorizar depois — fora de escopo v1 categorizar automático).
2. **`ifood.PedidoIFood`** — apenas em transição para status **terminal** (CONCLUDED — não em cada update de polling; lição de idempotência do projeto):
   - config `no_ato` → `registrar()` entrada direto, `origem_tipo='ifood'`;
   - config `repasse` → criar ContaReceber (`origem_canal='ifood'`, `origem_id=pedido.id`).
3. **`eventos.PagamentoEvento`** — `post_save` com `status='pago'` → `registrar()` entrada, `origem_tipo='evento_pagamento'`, `origem_id=pagamento.id`. Remoção de pagamento (fluxo existente `remover_pagamento`) → movimento de estorno (saída de mesmo valor, descricao "Estorno pagamento EV-xxxx"), **não** delete do movimento original.
4. **Cancelamento** de PedidoPDV/PedidoIFood após movimento gravado → movimento de estorno automático, mesma regra.

**Conta padrão dos signals:** os movimentos automáticos precisam de uma `ContaBancaria` destino. Adicionar `conta_padrao_vendas` (FK, null=True) em `ConfiguracaoFinanceira`. Se null → signal loga warning e **não grava** (setup manual documentado). Nunca criar conta automaticamente.

---

## Integração com Estoque (nota fiscal → ContaPagar)

Em `ImportacaoNotaFiscalViewSet.confirmar()`, **após** a geração dos `MovimentoEstoque` (não mexer nessa parte), se `ConfiguracaoFinanceira.get().nota_gera_conta_pagar`:

1. Criar `ContaPagar` com `origem='nota_fiscal'`, `nota_fiscal=importacao` (OneToOne garante idempotência — confirmar duas vezes não duplica), `valor` = soma dos itens não descartados, `data_emissao`/`data_vencimento` = data da nota (ou hoje, se ausente), `descricao` = "NF {numero_nota}".
2. **Fornecedor:** a cascata de extração precisa passar a capturar o emitente — no `extrair_xml()`, ler `emit/xNome` e `emit/CNPJ` da NF-e; nos caminhos PDF/IA, incluir os campos no prompt/regex como opcionais. Novos campos em `ImportacaoNotaFiscal`: `fornecedor_nome_extraido`, `fornecedor_cnpj_extraido` (blank). Resolução no confirmar: CNPJ exato → nome `iexact` → nome `icontains` (único) → senão criar `Fornecedor` novo com os dados extraídos. Mesmo espírito do `resolver_materia_prima()`.
3. Auditar: `registrar(usuario, 'conta_pagar_gerada_nota', detalhes={...})`.

Sem dado de fornecedor extraído → ContaPagar criada com `fornecedor=None` e descricao preservando o que houver.

---

## Management Commands (cron)

### `gerar_contas_recorrentes` (diário — ex.: 07:00)

Para cada `DespesaRecorrente` ativa, gerar `ContaPagar` (`origem='recorrente'`) para cada vencimento dentro de `hoje + horizonte_recorrencia_dias`. Idempotente pela `UniqueConstraint(recorrente, data_vencimento)` — `get_or_create`, nunca duplicar. Sem flags de configuração no comando: tudo vem do singleton (padrão do projeto — igual `lembrar_reengajamento`).

### `alertar_vencimentos` (diário — ex.: 08:30)

Mesma mecânica de `alertar_eventos` / `alertar_estoque_baixo`:
- contas `pendente`/`parcial` com vencimento em até `alerta_antecedencia_dias` OU em atraso;
- envia WhatsApp via `notificacoes.servico.notificar()` para `TelefoneAlertaFinanceiro` ativos (mínimo 1, senão não notifica ninguém — documentar);
- `AlertaFinanceiroEnviado` controla repetição (`alerta_repeticao_dias`);
- registrar tipo novo em `HistoricoMensagem.tipo`: `alerta_vencimento`.

---

## Endpoints (`/api/v1/financeiro/`)

```
# Categorias
GET/POST             categorias/                          ← POST exige login
GET/PATCH/DELETE     categorias/{id}/                     ← DELETE exige login · AuditoriaDestroyMixin · PROTECT vira 400 amigável

# Contas bancárias
GET/POST             contas-bancarias/                    ← POST exige login
GET/PATCH            contas-bancarias/{id}/               ← sem DELETE (PROTECT do ledger); desativar via ativo=False

# Fornecedores
GET/POST             fornecedores/                        ← busca por ?search= (nome/cnpj)
GET/PATCH/DELETE     fornecedores/{id}/                   ← DELETE exige login · AuditoriaDestroyMixin

# Contas a pagar
GET/POST             contas-pagar/                        ← filtros: status, categoria, fornecedor, mes (YYYY-MM), search · POST exige login · AuditoriaCreateMixin
GET/PATCH            contas-pagar/{id}/                   ← PATCH exige login · AuditoriaUpdateMixin · só status pendente
POST                 contas-pagar/{id}/baixa/             ← exige login · body: data, valor, conta, forma, comprovante (multipart) · chama registrar() + recalcular_valor_pago() · audita baixa_registrada
POST                 contas-pagar/{id}/cancelar/          ← exige login · só se valor_pago == 0 · AuditoriaStatusMixin
GET                  contas-pagar/resumo/                 ← cards: em_atraso, vence_hoje, proximos_7_dias, total_mes {pago, pendente}

# Despesas recorrentes
GET/POST             recorrentes/                         ← POST exige login
GET/PATCH            recorrentes/{id}/                    ← PATCH exige login (inclui ativo=False para pausar)

# Contas a receber
GET/POST             contas-receber/                      ← filtros: canal, status, mes, search · POST (manual) exige login
POST                 contas-receber/{id}/baixa/           ← exige login · mesma mecânica da baixa de pagar
GET                  contas-receber/resumo/               ← recebido_hoje, a_receber, proximos_30_dias — inclui eventos via query dinâmica

# Ledger
GET                  movimentos/                          ← só leitura · filtros: conta, tipo, categoria, periodo · sem DELETE (imutável)
POST                 movimentos/manual/                   ← exige login · lançamento avulso/estorno · origem_tipo='manual' · audita movimento_manual

# Fluxo de caixa
GET                  fluxo-caixa/?dias=14                 ← por dia: {entrada_realizada, entrada_projetada, saida_realizada, saida_projetada}
                                                             realizado = MovimentoFinanceiro · projetado = contas pendentes/parciais no período
                                                             + saldos por conta + última conferência

# Conferência de saldo
GET/POST             conferencias/                        ← POST exige login · grava snapshot do saldo calculado

# Configuração
GET/PATCH            configuracao/1/                      ← singleton · PATCH exige login · audita config_financeira_alterada
GET/POST             telefones-alerta/
GET/PATCH/DELETE     telefones-alerta/{id}/               ← DELETE exige login
```

Padrões: `CsrfExemptMixin + AllowAny` como base (leituras), com `TokenAuthentication + IsAuthenticated` nas ações de escrita listadas — mesmo desenho de Orçamento/Evento pós-auditoria.

---

## Frontend

- `Financeiro.jsx` + `Financeiro.module.css` — 5 abas conforme mockup aprovado (`mockup_financeiro.html` é a referência visual): Contas a Pagar (cards resumo, chips de status, tabela com badge de origem, modal de baixa, seção de recorrentes), Contas a Receber (chips por canal, eventos via query dinâmica, hint sobre config iFood), Fluxo de Caixa (barras realizado×projetado + cards de conta com conferência), Categorias (estado vazio primeiro), Configurações.
- `financeiroApi` em `services.js` (padrão dos demais).
- Rota em `App.jsx` + item na `Sidebar.jsx` (ícone `ti-cash`).
- `--surface` para fundos de modal/card (nunca `--surface-alt`/`--fundo` — regra do projeto). Tabler Icons. Sem `localStorage`.
- Uploads (anexo/comprovante): `FormData`, mesmo padrão de `ImagemInspiracao`.
- Estado vazio de Categorias orienta o cadastro (copy do mockup).

---

## Fases de Implementação

| Fase | Conteúdo | Critério de pronto |
|---|---|---|
| 0 | Pré-requisitos (bug `itens_json` + verificação dashboard + CLAUDE.md) | testes de sync Evento→PedidoUnificado passando; receita não duplica |
| 1 | App `financeiro/`: models base (Categoria, ContaBancaria, Fornecedor, Configuracao, Telefones) + `MovimentoFinanceiro.registrar()` + migrations + admin | testes de `registrar()`: atomicidade, quantização, saldo, constraint |
| 2 | ContaPagar + baixa + cancelar + resumo + auditoria | baixa parcial deriva `parcial`; total deriva `paga`; movimento gravado |
| 3 | DespesaRecorrente + `gerar_contas_recorrentes` + `alertar_vencimentos` | cron roda 2× sem duplicar; dia 31 em mês curto cai no último dia |
| 4 | ContaReceber + signals PDV/iFood/PagamentoEvento + estornos | idempotência por constraint; troca de config iFood não retroage |
| 5 | Integração Estoque: emitente na extração + ContaPagar na confirmação | confirmar 2× não duplica (OneToOne); fornecedor resolvido/criado |
| 6 | Fluxo de caixa (endpoint agregador) + SaldoConferido | projetado inclui recorrentes já geradas; realizado bate com ledger |
| 7 | Frontend `Financeiro.jsx` completo + services + rota + sidebar | 5 abas funcionais conforme mockup |
| 8 | Testes finais + atualização do CLAUDE.md (estrutura, endpoints, fases, padrões) | suite verde; CLAUDE.md canônico atualizado |

Cada fase deve terminar com o CLAUDE.md coerente com o código (lição do projeto: doc canônica sempre atualizada na própria sessão).

---

## O Que NÃO Fazer

- **Nunca** `MovimentoFinanceiro.objects.create()` fora de `registrar()` — mesmo em teste de outra feature.
- **Nunca** gravar `ContaBancaria.saldo_atual`, `ContaPagar.valor_pago`, `ContaReceber.valor_recebido` ou `status` derivado diretamente — sempre via `registrar()` + `recalcular_*()`.
- **Não** implementar DELETE de `MovimentoFinanceiro` — ledger imutável; correção é estorno (`movimentos/manual/`).
- **Não** materializar ContaReceber para Eventos nem para PDV — Eventos via query dinâmica + `PagamentoEvento`; PDV é movimento direto. Criar registro ali = dupla contagem.
- **Não** gravar movimento de iFood em cada evento de polling — só na transição terminal (CONCLUDED).
- **Não** criar `ContaBancaria` automaticamente em signal — sem `conta_padrao_vendas` configurada, logar warning e pular.
- **Não** semear categorias hardcoded — requisito de revenda; cadastro nasce vazio.
- **Não** mexer na geração de `MovimentoEstoque` dentro do `confirmar()` da nota — a ContaPagar é acrescentada **depois**, sem alterar o fluxo existente.
- **Não** criar fluxo de baixa paralelo para saldo de Evento — reutilizar `adicionar_pagamento` existente.
- **Não** usar Celery — cron + management command (padrão do projeto).

---

## Fora de Escopo (desta spec)

- Importação de extrato bancário (OFX/CNAB) e conciliação automática — futuro, se necessário.
- Importação da planilha do contador — decisão registrada: o sistema é a fonte da verdade.
- Atualização de custo de insumo pela nota + política de preço de venda — **spec separada** (decisões pendentes com o usuário).
- Relatório financeiro com export Excel/PDF (padrão `relatorios/`) — fase futura.
- Cards de Financeiro no Dashboard multi-canal — fase futura.
- Derivar `ParametrosNegocio.despesa_fixa` das despesas reais — decisão pendente com o usuário.
- Baixa em lote de ContaReceber (repasse iFood consolidado) — só se o modo `repasse` for ativado.
- NFC-e.

---

## Setup Manual (pós-implementação — checklist para o usuário)

1. `ANTHROPIC_API_KEY` no `.env` da VPS (se ainda não feito na Fase 0).
2. Cadastrar contas bancárias (Nubank, Caixa da loja) e definir `conta_padrao_vendas` em Configurações.
3. Cadastrar categorias (o usuário vai levantar a lista — decisão registrada).
4. Cadastrar despesas recorrentes conhecidas.
5. Telefones de alerta financeiro (mínimo 1, senão nenhum alerta sai).
6. Crontab na VPS: `gerar_contas_recorrentes` (07:00) e `alertar_vencimentos` (08:30).
7. Saldo inicial de cada conta: lançamento manual (`movimentos/manual/`) com descrição "Saldo inicial".
