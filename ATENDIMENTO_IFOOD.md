# Atendimento iFood via Chat do Gestor de Pedidos

> Spec para implementação pelo Claude Code. Escrito em out/2026.
> Para padrões técnicos gerais, ver `CLAUDE.md` — tudo aqui segue as regras de lá
> (cron em vez de Celery, `.get()` em configurações, `_resolver_empresa()` local por app,
> nada business-specific hardcoded, signals dentro de try/except).

---

## O que é

Mensagens automáticas e personalizadas no **chat do pedido iFood** (o chat nativo entre loja e
consumidor dentro do app do iFood), disparadas a cada movimentação do pedido e em caso de
atraso, e numa fase posterior, respostas assistidas por IA às mensagens do cliente.

### Por que uma extensão de Chrome

O iFood **não oferece API de chat** para integradoras. O chat só existe na interface do
**Gestor de Pedidos web** (`gestordepedidos.ifood.com.br`) e no Widget embutível, nenhum dos
dois programável. A solução de mercado (Avalyo e outras) é uma extensão de Chrome que opera a
interface do Gestor web. Esta feature segue o mesmo caminho:

- **O CRM decide** o que mandar e quando (já conhece cada transição pelo polling).
- **A extensão executa**: busca a fila no CRM, abre o chat do pedido no Gestor e envia.

Existe uma prova de conceito pronta (`arretado-ifood-chat-poc/`, fora do repo) com o
diagnóstico de DOM e o fluxo de abrir conversa/escrever. **A extensão de produção nasce dela.**

### Fluxo

```
PedidoIFood.save()  ──post_save──▶  atendimento/signals.py
  (polling ou view)                   │ status → gatilho
                                      │ modelo ativo? chat ativo? janela ok? já existe?
                                      ▼
                              MensagemChat (status=pendente)        ◀── cron verificar_atrasos_ifood
                                      │                                   (gatilhos de atraso)
                                      │                             ◀── envio manual pelo CRM
                                      ▼
  Extensão (content script, a cada N s) ──▶ background ──POST /extensao/fila/reservar/──▶ Django
                                      │        (status=enviando, reservado_em)
                                      ▼
            abre chat do #pedido no Gestor → escreve → envia
                                      │
                                      ▼
              POST /extensao/fila/{id}/resultado/  ──▶  enviada | falha
```

---

## Fases

| Fase | Entrega | Depende de |
|---|---|---|
| 0 | Calibração com a POC no Gestor real (manual, sem código no CRM) | — |
| 1 | Backend base: app `atendimento/`, fila, gatilhos por status, endpoints da extensão | — (pode correr em paralelo à Fase 0) |
| 2 | Extensão de produção (`extensao-ifood-chat/`) | 0 e 1 |
| 3 | Detecção de atraso (cron) | 1 |
| 4 | Frontend CRM: tela Atendimento + integração em `IFood.jsx` | 1 |
| 5 | Leitura das mensagens do cliente + IA (sugestão → automático) | 0 (diag da conversa aberta), 2, 4 |
| 6 | Testes finais, documentação, deploy | todas |

Cada fase termina com seus testes passando e é deployável sozinha. **A chave geral
`chat_ativo` nasce desligada**, então deployar o backend não manda nada para cliente nenhum
até alguém ligar.

---

## Fase 0 — Calibração (manual)

Feita pelo Fobs na loja, com a POC carregada no Chrome. Não tem código no CRM.

1. **Diagnóstico com o painel fechado** → salvar `diag-1-inicial.json`.
2. **Diagnóstico com uma conversa aberta** → salvar `diag-2-conversa-aberta.json`. É o que
   define os seletores de **leitura** de mensagens da Fase 5.
3. **Modo seguro** em dois pedidos em andamento: um com conversa já existente (fluxo 1, pela
   lista) e um sem (fluxo 2, pelo card). Guardar os `passos` de cada um.
4. **Envio real** para um pedido da equipe.
5. **Duas abas do Gestor** abertas ao mesmo tempo: o iFood permite? Uma derruba a outra?
   (Decide se a extensão pode rodar numa aba dedicada enquanto a equipe opera em outra.)
6. **Eventos de logística que chegam de fato**, em produção (só leitura):
   ```python
   from django.db.models import Count
   from ifood.models import EventoPollingIFood
   EventoPollingIFood.objects.values('full_code').annotate(n=Count('id')).order_by('-n')
   ```
   Confirma se `ARRIVED_AT_ORIGIN`, `COLLECTED` e afins aparecem, e se `DISPATCHED` chega
   também para pedidos `IFOOD_DELIVERY`.

**Saída da fase:** `selectors.js` ajustado, e a seção [Seletores validados](#seletores-validados)
deste spec preenchida. **A Fase 2 não começa sem isso.**

---

## Fase 1 — Backend base

### Novo app `atendimento/`

Registrado em `INSTALLED_APPS` e roteado em `/api/v1/atendimento/`. Os signals são conectados em
`AtendimentoConfig.ready()`, com sender como string (`'ifood.PedidoIFood'`), mesmo padrão de
`estoque/signals.py`.

### `atendimento.ConfiguracaoAtendimento` (1 linha por empresa)

Sempre via `ConfiguracaoAtendimento.get(empresa)` (argumento obrigatório, cria com defaults se
não existir; mesmo contrato de `ConfiguracaoFinanceira.get(empresa)`).

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `empresa` | OneToOne `empresas.Empresa` (PROTECT) | — | |
| `chat_ativo` | BooleanField | `False` | Chave geral. Desligada, nenhum gatilho automático entra na fila |
| `janela_maxima_horas` | PositiveIntegerField | `6` | Pedido com `ifood_criado_em` mais antigo que isso não gera mensagem automática (protege contra reprocessamento de eventos antigos após queda) |
| `expiracao_minutos` | PositiveIntegerField | `20` | Mensagem automática não enviada nesse prazo vira `expirada` |
| `atraso_tolerancia_min` | PositiveIntegerField | `10` | Minutos além da previsão antes de disparar atraso (Fase 3) |
| `modo_ia` | CharField choices `desligado`/`sugestao`/`automatico` | `desligado` | Fase 5 |
| `ia_modelo` | CharField | `'claude-haiku-4-5'` | Fase 5 |
| `ia_timeout_segundos` | PositiveIntegerField | `30` | Fase 5 |
| `ia_instrucoes_tom` | TextField | `''` | Tom de voz da marca, editável (Fase 5) |
| `ia_contexto_loja` | TextField | `''` | Endereço, horários, políticas: o que a IA pode afirmar (Fase 5) |

`PATCH` exige login e audita `config_atendimento_alterada` via `auditoria.utils.registrar()`.

### `atendimento.ConfiguracaoExtensao` (singleton global)

Configuração técnica da extensão, igual para todas as empresas. Sempre via `.get()`.

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `seletores` | JSONField | `{}` | Sobrescreve os seletores embutidos na extensão, chave a chave. Vazio usa os embutidos |
| `tempos_ms` | JSONField | `{}` | Sobrescreve os sleeps da extensão, chave a chave |
| `intervalo_segundos` | PositiveIntegerField | `5` | Intervalo de busca da fila |
| `pausa_interacao_segundos` | PositiveIntegerField | `15` | Extensão não age se houve clique/tecla humana na aba nesse intervalo |
| `lease_segundos` | PositiveIntegerField | `120` | Mensagem em `enviando` há mais que isso vira `incerta` |

Motivo de existir: **quando o iFood mudar o HTML, o conserto é um PATCH aqui, não reinstalar a
extensão em cada loja cliente.** `PATCH` exige `IsAdminRole` e audita.

### `atendimento.ModeloMensagemChat`

| Campo | Tipo | Descrição |
|---|---|---|
| `empresa` | FK `Empresa` (PROTECT) | |
| `gatilho` | CharField choices (ver tabela abaixo) | |
| `texto` | TextField | Aceita as variáveis abaixo |
| `ativo` | BooleanField | |
| `atualizado_em` | DateTimeField auto_now | |

`UniqueConstraint(empresa, gatilho)`. Os padrões são criados de forma preguiçosa por
`ModeloMensagemChat.garantir_padroes(empresa)` (chamado pelo `.get()` da configuração), a partir
de um dicionário `MODELOS_PADRAO` em `atendimento/modelos_padrao.py`. Os textos padrão são
genéricos e usam `{loja}`, **nunca o nome de uma empresa**. Sem DELETE: desativar via `ativo=False`.

**Gatilhos:**

| Gatilho | Origem | Ativo por padrão |
|---|---|---|
| `confirmado` | status `CONFIRMED` | sim |
| `em_preparo` | status `PREPARATION_STARTED` | sim |
| `pronto_retirada` | status `READY_TO_PICKUP` e `order_type == 'TAKEOUT'` | sim |
| `pronto_entrega` | status `READY_TO_PICKUP` e `order_type != 'TAKEOUT'` | sim |
| `saiu_entrega` | status `DISPATCHED` | sim |
| `concluido` | status `CONCLUDED` (pede avaliação) | sim |
| `cancelado` | status `CANCELLED` | **não** |
| `entregador_chegou` | evento `ARRIVED_AT_ORIGIN` (se a Fase 0 confirmar que chega) | **não** |
| `atraso_antes_despacho` | cron (Fase 3) | sim |
| `atraso_apos_despacho` | cron (Fase 3) | sim |
| `manual` | envio pelo CRM | — (não tem modelo) |
| `ia` | resposta da IA (Fase 5) | — (não tem modelo) |

**Variáveis** (substituição por `str.replace` de cada chave conhecida; chave desconhecida fica
como está, nunca levanta exceção):

| Variável | Valor |
|---|---|
| `{loja}` | `pedido.empresa.nome` |
| `{nome}` | `pedido.cliente_nome` |
| `{primeiro_nome}` | primeira palavra de `cliente_nome`, capitalizada |
| `{pedido}` | `pedido.display_id` |
| `{itens_resumo}` | até 2 itens (`"2x Bolo de pote, 1x Brigadeiro"`) + `" e mais N"` se houver |
| `{previsao}` | `previsao_entrega` em `HH:MM` local; `"em breve"` se nula |
| `{minutos_atraso}` | inteiro, só nos gatilhos de atraso; `""` nos demais |

Renderização em `atendimento/render.py::renderizar(texto, pedido, extra=None)`, função pura e
testável. O texto é renderizado **na criação** da `MensagemChat` e gravado já pronto (snapshot).
Editar o modelo depois não altera mensagens já enfileiradas.

**Textos padrão** (`MODELOS_PADRAO`):

| Gatilho | Texto |
|---|---|
| `confirmado` | `Oi, {primeiro_nome}! Aqui é da {loja} 😊 Seu pedido #{pedido} foi confirmado e já vai pra produção.` |
| `em_preparo` | `{primeiro_nome}, seu pedido #{pedido} já está sendo preparado! 👩‍🍳` |
| `pronto_retirada` | `Seu pedido #{pedido} está pronto para retirada. Te esperamos! 🎉` |
| `pronto_entrega` | `Seu pedido #{pedido} está pronto e aguardando o entregador. 🛵` |
| `saiu_entrega` | `Seu pedido #{pedido} saiu para entrega! Previsão: {previsao}.` |
| `concluido` | `Pedido entregue! Esperamos que goste, {primeiro_nome}. Se puder, avalie a gente no iFood, ajuda demais! 💛` |
| `cancelado` | `Seu pedido #{pedido} foi cancelado. Sentimos muito pelo transtorno.` |
| `entregador_chegou` | `O entregador já chegou na loja para buscar seu pedido #{pedido}!` |
| `atraso_antes_despacho` | `{primeiro_nome}, seu pedido #{pedido} está levando um pouco mais que o previsto (uns {minutos_atraso} min). Já estamos finalizando, obrigado pela paciência!` |
| `atraso_apos_despacho` | `Seu pedido #{pedido} já está a caminho, mas atrasou cerca de {minutos_atraso} min. Desculpe! Estamos acompanhando.` |

### `atendimento.MensagemChat`

Fila de saída **e** registro de entrada. Sem DELETE (histórico de atendimento).

| Campo | Tipo | Descrição |
|---|---|---|
| `empresa` | FK `Empresa` (PROTECT) | Denormalizada de `pedido.empresa` na criação |
| `pedido` | FK `ifood.PedidoIFood` (PROTECT), `related_name='mensagens_chat'` | |
| `direcao` | CharField `saida`/`entrada` | |
| `origem` | CharField `automatico`/`manual`/`ia`/`cliente`/`loja_gestor` | `loja_gestor` = alguém da equipe digitou direto no Gestor (Fase 5) |
| `gatilho` | CharField (choices de `ModeloMensagemChat` + `manual`/`ia`), blank em entrada | |
| `texto` | TextField | Já renderizado |
| `status` | CharField (ver máquina abaixo) | |
| `tentativas` | PositiveSmallIntegerField | `0` |
| `reservado_em` | DateTimeField null | Quando a extensão pegou |
| `enviado_em` | DateTimeField null | |
| `expira_em` | DateTimeField null | `criado_em + expiracao_minutos` nas automáticas; `null` em manual/ia |
| `erro` | TextField blank | |
| `passos` | JSONField default list | Log de passos devolvido pela extensão |
| `autor` | FK `usuarios.Usuario` (SET_NULL) null | Em `manual` e em `ia` aprovada |
| `hash_entrada` | CharField(64) null, unique | Dedup de mensagens recebidas (Fase 5) |
| `criado_em` | DateTimeField auto_now_add | |

`UniqueConstraint(pedido, gatilho)` condicional a `direcao='saida'` e `gatilho` fora de
(`manual`, `ia`): **uma mensagem automática por gatilho por pedido.** Sempre checar `.exists()`
antes de criar (regra do `CLAUDE.md`), sem depender só da constraint.

Índices: `(status, criado_em)` e `(pedido, criado_em)`.

**Máquina de status (saída):**

```
sugerida ──aprovar──▶ pendente ──reservar──▶ enviando ──resultado ok──▶ enviada
   │                    │  │                    │
   └─cancelar─▶ cancelada  │                    ├──resultado erro──▶ falha
                cancelar◀──┘                    └──lease vencido───▶ incerta
              pendente com expira_em < agora ──▶ expirada
```

- **Entrega no máximo uma vez.** `incerta` e `falha` **nunca** voltam a `pendente`
  sozinhas. A extensão pode ter enviado e morrido antes de reportar; reenviar sozinho arrisca
  mensagem duplicada para o cliente. Reenvio é ação humana (`reenviar/`), que cria uma
  `MensagemChat` **nova** (`origem='manual'`).
- Entrada: status único `recebida`.

### Gatilho por status: `atendimento/signals.py`

`post_save` em `'ifood.PedidoIFood'`, todo o corpo em try/except com `logger.warning`:

1. Mapeia `instance.status` (+ `order_type` no caso de `READY_TO_PICKUP`) para um gatilho. Sem
   mapeamento, retorna.
2. `cfg = ConfiguracaoAtendimento.get(instance.empresa)`. Se `not cfg.chat_ativo`, retorna.
3. Se `instance.ifood_criado_em` for mais antigo que `janela_maxima_horas`, retorna.
4. Modelo do gatilho inexistente ou `ativo=False`, retorna.
5. Já existe `MensagemChat(pedido, gatilho, direcao='saida')`? Retorna (idempotência; o
   `post_save` dispara em todo `.save()`, inclusive `update_fields=['atualizado_em']`).
6. Cria `MensagemChat(status='pendente', origem='automatico', texto=renderizar(...), expira_em=...)`.
7. Se `status == 'CANCELLED'`: marca todas as `pendente` daquele pedido (exceto a de
   `cancelado`) como `cancelada`.

O signal **só grava no banco**, nunca faz HTTP. Roda dentro do `transaction.atomic()` do polling
sem atrasá-lo, e some junto num rollback.

Observação: o caminho de negociação do `polling_worker.py` usa `.update()` (não dispara signal).
Hoje ele só grava `CANCELLATION_REQUESTED`, que não tem gatilho, então **não precisa mudar**.

### Mudanças em `ifood/`

**Novos campos em `PedidoIFood`, todos `null=True` (ver incidente dos 245 pedidos no `CLAUDE.md`):**

| Campo | Fonte no payload de detalhe | Uso |
|---|---|---|
| `previsao_preparo_inicio` | `preparationStartDateTime` | Atraso antes do despacho |
| `previsao_entrega` | `delivery.deliveryDateTime`, senão `takeout.takeoutDateTime`, senão `schedule.scheduledDateTimeEnd` | `{previsao}` e atraso |
| `entregador_chegou_em` | `createdAt` do evento `ARRIVED_AT_ORIGIN` | Atribuição do atraso (cozinha × logística) |
| `coletado_em` | `createdAt` do evento `COLLECTED` | Idem |

- `_criar_pedido()` preenche `previsao_*` com o mesmo `_parse_dt()` já existente. Campo
  ausente no payload grava `None`, nunca quebra a criação.
- `_processar_evento_pedido()`: para `ARRIVED_AT_ORIGIN`/`COLLECTED` (e aliases que a Fase 0
  revelar), grava o timestamp no pedido existente com `save(update_fields=[...])`, **sem mexer
  em `status`**. Quando `entregador_chegou_em` passa de `None` para preenchido, chama
  explicitamente `atendimento.servico.enfileirar(pedido, 'entregador_chegou')` logo depois do
  `save()` (import local dentro da função, em try/except).
- Expor os 4 campos novos em `PedidoIFoodDetailSerializer` (read-only).

**Remover as notificações WhatsApp de pedidos iFood:** as chamadas `_notificar_ifood(...)` em
`confirmar`, `cancelar`, `despachar` e `pronto_retirada` de `ifood/views.py`, e o helper. Motivo:
o iFood não expõe o telefone do consumidor (`cliente_telefone` guarda um 0800 mascarado ou o
`localizer`). A mensagem cai em número inválido ou, pior, no telefone de um `Cliente` CRM
vinculado errado. O chat substitui. **PDV e Eventos continuam com WhatsApp, sem mudança.**

### `atendimento/servico.py`

Ponto único de criação de mensagem de saída. Signal, cron e views chamam só isto:

```python
enfileirar(pedido, gatilho, *, extra=None, origem='automatico', texto=None, autor=None,
           status='pendente') -> MensagemChat | None
```

Aplica as checagens dos passos 2 a 6 do signal para `origem='automatico'`. Para
`manual`/`ia`, pula modelo, janela e unicidade, e usa `texto` como veio. Nunca lança exceção:
loga e devolve `None`.

### Autenticação da extensão: `atendimento.TokenExtensao`

| Campo | Tipo | Descrição |
|---|---|---|
| `nome` | CharField | Ex.: "Computador do caixa" |
| `token_hash` | CharField(64) unique | SHA-256 do token. **Token em texto puro nunca é gravado** |
| `prefixo` | CharField(8) | Primeiros 8 caracteres, para identificar na tela |
| `empresas` | M2M `Empresa` | Um Gestor pode operar mais de uma loja |
| `ativo` | BooleanField | Revogar = `False`, nunca DELETE |
| `criado_por` | FK `Usuario` SET_NULL | |
| `criado_em` | DateTimeField | |
| `ultimo_heartbeat` | DateTimeField null | |
| `versao_extensao` | CharField blank | Do heartbeat |
| `ultimo_diagnostico` | JSONField default dict | Do heartbeat: `{aba_ok, seletores_ok: {chave: bool}, url}` |

- Token gerado com `secrets.token_urlsafe(32)` e devolvido **uma única vez** na resposta da
  criação.
- `atendimento/authentication.py::TokenExtensaoAuthentication` lê o header
  `X-Extensao-Token`, faz o hash, busca `TokenExtensao(ativo=True)` e coloca o token em
  `request.auth`. Usada **só** nos endpoints `/extensao/`.
- Management command `gerar_token_extensao --empresa <id> [--empresa <id>] --nome "..."`
  imprime o token, para testar a Fase 2 antes da Fase 4 existir.

### Endpoints

**Extensão** (`TokenExtensaoAuthentication`, sem login de usuário). As mensagens retornadas são
sempre filtradas por `request.auth.empresas`:

```
GET  /api/v1/atendimento/extensao/config/
     → {intervalo_segundos, pausa_interacao_segundos, seletores, tempos_ms}

POST /api/v1/atendimento/extensao/heartbeat/
     body {versao, aba_ok, seletores_ok, url} → grava em TokenExtensao · 204

POST /api/v1/atendimento/extensao/fila/reservar/
     → 200 {id, display_id, texto, empresa_nome} | 204 (fila vazia)

POST /api/v1/atendimento/extensao/fila/{id}/resultado/
     body {ok: bool, passos: [...], erro: ""} → enviada | falha · 204
     (rejeita 409 se a mensagem não estiver em 'enviando')
```

`reservar/`, tudo dentro de `transaction.atomic()`:

1. **Varredura:** `enviando` com `reservado_em < agora - lease_segundos` vira `incerta`;
   `pendente` com `expira_em < agora` vira `expirada`.
2. Seleciona a `pendente` mais antiga das empresas do token, com
   `select_for_update(skip_locked=True)`. Duas extensões nunca pegam a mesma.
3. Grava `status='enviando'`, `reservado_em=agora`, `tentativas += 1`.

**Uma mensagem por chamada:** a extensão processa em série.

**CRM** (`TokenAuthentication` + `IsAuthenticated`; aceitam `?empresa=<id>` via
`_resolver_empresa()` local deste app):

```
GET/PATCH  /api/v1/atendimento/configuracao/                 ← audita PATCH
GET        /api/v1/atendimento/modelos/                      ← garante padrões antes de listar
PATCH      /api/v1/atendimento/modelos/{id}/                 ← texto, ativo · audita
POST       /api/v1/atendimento/modelos/preview/              ← {texto, pedido_id?} → {renderizado}
                                                               (sem pedido_id usa dados fictícios)
GET        /api/v1/atendimento/mensagens/                    ← filtros: pedido, status, direcao, data_inicio, data_fim
POST       /api/v1/atendimento/mensagens/manual/             ← {pedido, texto} → pendente, origem=manual, autor
POST       /api/v1/atendimento/mensagens/{id}/cancelar/      ← só pendente/sugerida
POST       /api/v1/atendimento/mensagens/{id}/reenviar/      ← só falha/incerta/expirada → cria nova manual
GET        /api/v1/atendimento/status-extensao/              ← {online, ultimo_heartbeat, versao, seletores_ok}
                                                               online = heartbeat de algum token da empresa < 60 s
GET/PATCH  /api/v1/atendimento/configuracao-extensao/        ← IsAdminRole · audita PATCH
GET/POST   /api/v1/atendimento/tokens/                       ← IsAdminRole · POST devolve o token uma vez · audita
POST       /api/v1/atendimento/tokens/{id}/revogar/          ← IsAdminRole · audita
```

`mensagens/manual/` rejeita (400) pedido com `status` em `CONCLUDED`/`CANCELLED` há mais de 24 h:
o iFood fecha o chat depois de um tempo.

### Critérios de aceite da Fase 1

- [ ] Migrations aplicam limpo; campos novos de `PedidoIFood` são todos nullable.
- [ ] Testes (`python manage.py test atendimento --settings=config.settings_test`):
  - signal cria exatamente uma mensagem por gatilho, mesmo com N `save()` seguidos;
  - nada é criado com `chat_ativo=False`, com modelo inativo ou com pedido fora da janela;
  - `CANCELLED` cancela as pendentes do pedido;
  - `renderizar()` cobre todas as variáveis e não quebra com variável desconhecida, `cliente_nome` vazio ou `previsao_entrega` nula;
  - `reservar/` com duas chamadas concorrentes nunca devolve a mesma mensagem;
  - lease vencido vira `incerta` e **não** volta para a fila;
  - token inválido ou revogado → 401; token de uma empresa nunca vê fila de outra;
  - `_criar_pedido()` com payload sem os campos de previsão grava `None` sem erro.
- [ ] `ifood/views.py` sem nenhuma chamada a `notificar` para pedidos iFood.
- [ ] Deploy com `systemctl restart arretado arretado-polling` (migration em `ifood`).

---

## Fase 2 — Extensão de produção

Pasta nova na raiz do repo: `extensao-ifood-chat/` (irmã de `arretado-crm/`). Parte da POC.

```
extensao-ifood-chat/
├── manifest.json        ← MV3
├── selectors.js         ← seletores embutidos (fallback), lista de candidatos por chave
├── content.js           ← loop, fluxos de abrir conversa/escrever, pausa por interação, diagnóstico
├── background.js        ← service worker: única peça que fala com o backend
├── popup.html / popup.js← config (URL, token), status, modo seguro, diagnóstico
├── icons/
└── README.md            ← instalação e operação
```

### `manifest.json`

- `permissions`: `storage`, `scripting`, `tabs`.
- `host_permissions`: `https://gestordepedidos.ifood.com.br/*` **e a URL do backend**. A URL
  é por instalação (revenda), então usar `optional_host_permissions: ["https://*/*"]` e
  pedir permissão para a origem informada no popup com `chrome.permissions.request()`
  ao salvar.
- `content_scripts` só em `gestordepedidos.ifood.com.br`.

### Quem faz o quê

- **O content script dirige o relógio.** `setInterval` com `intervalo_segundos` enquanto a aba
  do Gestor estiver aberta. Motivo: o service worker MV3 dorme, e `chrome.alarms` tem período
  mínimo de 30 s.
- **O background faz toda a rede.** O content script manda mensagens (`chrome.runtime.sendMessage`)
  e o background chama o backend com o header `X-Extensao-Token`. Fetch direto do content script
  esbarra em CORS; **nunca liberar CORS no Django para a origem do iFood**.
- **Configuração** em `chrome.storage.local`: `backendUrl`, `token`, `modoSeguro`, `ativo`.

### Ciclo (content script)

1. Se `ativo == false`, ou a aba não é a ativa da janela, ou houve interação humana há menos de
   `pausa_interacao_segundos`, pula o ciclo.
2. A cada 30 s: `heartbeat/` com `seletores_ok` (resultado do diagnóstico leve: cada chave
   testada sem clicar em nada).
3. A cada 5 min, ou ao iniciar: `config/`. Mescla `seletores`/`tempos_ms` remotos **por cima**
   dos embutidos, chave a chave.
4. `fila/reservar/`. Com 204, fim do ciclo.
5. Executa o fluxo da POC (fecha painel → fluxo 1 pela lista → fallback fluxo 2 pelo card →
   escreve → envia) e reporta em `fila/{id}/resultado/` com `passos`.
6. Nunca processa duas mensagens em paralelo (flag `processando`). Espera 2,5 s entre mensagens.

### Pausa por interação humana

- O content script escuta `mousedown`, `keydown` e `wheel` com `isTrusted === true` (cliques
  da própria extensão são `isTrusted === false`) e guarda `ultimoHumanoEm`.
- Se acontecer evento humano **no meio** de um fluxo, aborta antes do clique de enviar e
  reporta `ok: false, erro: 'interrompido_por_usuario'`. A mensagem vira `falha` e o atendente
  decide se reenvia.

### Modo seguro

Mantido da POC como opção no popup: preenche e **não envia**, e reporta
`ok: false, erro: 'modo_seguro'`. Serve para validar o pipeline ponta a ponta em produção sem
falar com cliente.

### Badge do ícone

Verde: conectado, aba ok, seletores ok. Amarelo: pausada (interação humana ou aba inativa).
Vermelho: sem backend, token inválido ou seletor crítico (`messageInput`, `sendButton`,
`chatToggleButton`) quebrado.

### Critérios de aceite da Fase 2

- [ ] Com token gerado pelo management command, a extensão envia em modo seguro uma mensagem
      enfileirada pelo signal, e a `MensagemChat` termina em `falha` com `erro='modo_seguro'`
      e `passos` preenchidos.
- [ ] Envio real para pedido da equipe pelos dois fluxos (lista e card).
- [ ] Clicar na página durante um fluxo aborta sem enviar.
- [ ] Fechar e reabrir a aba retoma sozinha; matar a extensão no meio de um envio deixa a
      mensagem em `incerta` após o lease, e ela não é reenviada.
- [ ] Mudar um seletor via `configuracao-extensao/` tem efeito em até 5 min sem reinstalar.

---

## Fase 3 — Detecção de atraso

Management command `atendimento/management/commands/verificar_atrasos_ifood.py`, cron **a cada
minuto**. Fora do `ifood_polling` de propósito: o worker de polling é crítico e não ganha
responsabilidade nova.

```
* * * * * cd /var/www/crm_arretado && venv/bin/python manage.py verificar_atrasos_ifood
```

Para cada empresa com `chat_ativo=True`, sobre os `PedidoIFood` dentro da janela, com
`previsao_entrega` não nula e `agora > previsao_entrega + atraso_tolerancia_min`:

| Gatilho | Condição de status |
|---|---|
| `atraso_antes_despacho` | `CONFIRMED`, `PREPARATION_STARTED` ou `READY_TO_PICKUP`, e `order_type != 'TAKEOUT'` |
| `atraso_apos_despacho` | `DISPATCHED` |

- `extra={'minutos_atraso': int((agora - previsao_entrega).total_seconds() // 60)}`.
- Enfileira via `servico.enfileirar()`, que já garante uma mensagem por gatilho por pedido.
- Pedido `TAKEOUT` não recebe aviso de atraso nesta versão (o cliente vem buscar; não há
  previsão confiável de quando).
- Se `READY_TO_PICKUP` e `entregador_chegou_em` nulo, o atraso é da logística, não da cozinha.
  O texto padrão serve aos dois casos, e o CRM mostra a atribuição na tela (Fase 4).
- Saída do command: contagem por gatilho, para o log do cron. Nunca lança exceção por pedido
  individual.

### Critérios de aceite da Fase 3

- [ ] Testes com `timezone.now()` mockado: dispara uma vez, não dispara dentro da tolerância,
      não dispara sem previsão, não dispara para `TAKEOUT`, não dispara com chat desligado.
- [ ] Rodar o command duas vezes seguidas não duplica.

---

## Fase 4 — Frontend CRM

### Nova página `Atendimento.jsx` (rota `/atendimento`)

Item de menu no grupo do iFood na `Sidebar.jsx`, com rota correspondente em `App.jsx`. Nova chave
`atendimento` em `MODULOS_OCULTAVEIS` (empresas sem iFood escondem). Consome
`useAuth().empresaAtiva`. Quatro abas:

1. **Fila:** tabela das últimas mensagens (pedido, gatilho, texto, status com badge, horário,
   erro). Filtros por status/direção. Ações `cancelar` (pendente/sugerida) e `reenviar`
   (falha/incerta/expirada, com `window.confirm`). Atualiza a cada 10 s enquanto a aba estiver
   aberta.
2. **Mensagens:** um card por gatilho com toggle `ativo`, textarea do texto, chips clicáveis
   que inserem as variáveis e preview ao vivo (`modelos/preview/`, debounce 400 ms).
3. **Configuração:** chave geral `chat_ativo` em destaque (com aviso de que liga envio real
   para clientes), janela, expiração, tolerância de atraso. Seção IA (Fase 5) desabilitada
   até lá.
4. **Extensão:** status online/offline (`status-extensao/`, a cada 15 s), versão, seletores
   com ✓/✗; tokens (listar, criar mostrando o token **uma vez** num modal com botão copiar,
   revogar). Só `role=admin`: editor JSON de `configuracao-extensao/`. Link para o README de
   instalação.

### Mudanças em `IFood.jsx`

- **Card do pedido:** badge "Atrasado X min" quando `previsao_entrega + tolerância` passou e o
  pedido não está concluído/cancelado. Calcular no frontend com os campos do serializer, sem
  endpoint novo. Tooltip "aguardando entregador" quando `READY_TO_PICKUP` sem
  `entregador_chegou_em`.
- **Detalhe do pedido:** seção "Chat" com as `MensagemChat` do pedido em ordem cronológica
  (balões saída/entrada, status miúdo) e campo de envio manual (`mensagens/manual/`, com
  `window.confirm`).
- **Topo da página:** indicador discreto da extensão (online/offline), para a equipe perceber
  quando o Chrome do caixa fechou.

`services.js`: novo objeto `atendimentoApi`, seguindo o padrão dos demais.

### Critérios de aceite da Fase 4

- [ ] Todos os fluxos acima funcionando com `empresaAtiva` trocada (Arretado ↔ outra empresa).
- [ ] Teste manual com prefixo `"TESTE "` e limpeza depois (o banco é o de produção).
- [ ] Build só com aviso prévio ao Fobs (regra do `CLAUDE.md`).

---

## Fase 5 — Mensagens do cliente + IA

**Bloqueada até a Fase 0 entregar o `diag-2-conversa-aberta.json`.** Sem ele não se sabe a
estrutura dos balões nem como o Gestor marca conversa não lida.

### Leitura (extensão)

- A cada ciclo sem mensagem para enviar, o content script verifica o indicador de não lidas
  (seletor a definir na calibração).
- Havendo não lida: abre a conversa, lê os últimos 10 balões (`autor`: `cliente`/`loja`, `texto`,
  `horario_exibido`) e envia para
  `POST /api/v1/atendimento/extensao/mensagens-recebidas/` com
  `{display_id, mensagens: [...]}`. Depois fecha a conversa.
- **Efeito colateral importante:** abrir a conversa a marca como lida no Gestor, então a equipe
  perde o badge de não lida do iFood. Por isso a tela de Atendimento passa a ser o lugar onde a
  equipe vê conversas aguardando humano.

### Backend

- `mensagens-recebidas/` resolve o pedido por `display_id` entre as empresas do token, o mais
  recente com `ifood_criado_em` nas últimas 24 h. Grava cada balão como `MensagemChat(direcao=
  'entrada')` com `hash_entrada = sha256(pedido_id|autor|texto|horario_exibido)`, ignorando hash
  repetido.
- Balão `autor='loja'` que não corresponde a nenhuma `MensagemChat` enviada é alguém da equipe
  digitando no Gestor: grava como `saida`, `origem='loja_gestor'`, `status='enviada'`, e põe a
  conversa em modo humano.
- Novo model `atendimento.ConversaChat`: `pedido` OneToOne, `modo` (`bot`/`humano`),
  `aguardando_humano` (bool), `ultima_entrada_em`. Modo humano dura até o atendente devolver
  pela tela ou até o pedido concluir.

### IA: `atendimento/ia_client.py`

HTTP puro via `requests` à API de Messages da Anthropic, **mesmo padrão de
`estoque/claude_client.py`** (sem SDK; `ANTHROPIC_API_KEY` só no ambiente; lança erro próprio
`IAAtendimentoError`, que o chamador captura). Não importa nada de `estoque/`: a configuração
vem de `ConfiguracaoAtendimento`.

- **Nunca chamar a IA dentro do request da extensão.** `mensagens-recebidas/` só grava e
  responde 204. O management command `responder_chat_ia` (cron a cada minuto) processa as
  entradas sem resposta.
- **Sem tool use nesta versão.** O contexto é montado inteiro no prompt:
  - pedido: status legível, itens, `observacao_pedido`, previsão, minutos de atraso, se o
    entregador já chegou;
  - `ia_contexto_loja` e `ia_instrucoes_tom`;
  - as últimas 10 `MensagemChat` do pedido.
- **Resposta exigida em JSON puro:**
  `{"acao": "responder" | "transferir", "texto": "...", "motivo": "..."}`.
- **Regras fixas no prompt** (são regras de segurança, não valores de negócio, então podem
  ficar no código):
  - nunca prometer reembolso, desconto, brinde nem prazo que não esteja no contexto;
  - nunca dizer que cancelou ou alterou o pedido: cancelamento é pelo app do iFood;
  - alergênicos só se constarem do contexto, sempre com ressalva;
  - reclamação de produto (errado, faltando, estragado), cliente irritado ou qualquer dúvida
    fora do contexto → `transferir`;
  - respostas curtas, em português, no tom de `ia_instrucoes_tom`.
- **Destino da resposta, conforme `modo_ia`:**
  - `desligado`: nada; só marca `aguardando_humano=True`.
  - `sugestao` (**primeiro modo a ligar**): cria `MensagemChat(origem='ia', status='sugerida')`.
    O atendente aprova (pode editar o texto) em `POST /mensagens/{id}/aprovar/` → `pendente`,
    `autor`.
  - `automatico`: `responder` vai direto para `pendente`; `transferir` nunca envia e marca
    `aguardando_humano=True`.
  - Conversa em `modo='humano'`: a IA não é chamada.
- Falha da IA (sem chave, timeout, JSON inválido) → `aguardando_humano=True`, log, segue.

### Frontend

- Aba **Conversas** em `Atendimento.jsx`: conversas com `aguardando_humano` primeiro,
  sugestões da IA com botões aprovar/editar/descartar, e botão "devolver para o bot".
- Seção IA da aba Configuração habilitada: `modo_ia`, modelo, tom, contexto da loja.

### Critérios de aceite da Fase 5

- [ ] Mesma mensagem lida duas vezes não duplica.
- [ ] Equipe digitando direto no Gestor põe a conversa em modo humano e a IA para.
- [ ] Testes do `ia_client` com `requests` mockado: JSON válido, inválido, timeout, sem chave.
- [ ] Uma semana em modo `sugestao` antes de qualquer empresa ir para `automatico` (decisão
      operacional, não técnica; registrar no `CHANGELOG.md` quando acontecer).
- [ ] `ANTHROPIC_API_KEY` configurada em produção (pendência atual do `CLAUDE.md`).

---

## Fase 6 — Fechamento

- [ ] `python manage.py test --settings=config.settings_test` inteiro passando.
- [ ] `CLAUDE.md` atualizado: app `atendimento/` na árvore, padrões novos, endpoints, crons
      (`verificar_atrasos_ifood`, `responder_chat_ia`), linhas novas em "O Que NÃO Fazer",
      linha na tabela de status, remoção do WhatsApp de pedidos iFood.
- [ ] Este arquivo com a seção de seletores validados preenchida e "Implementado em ...".
- [ ] Tag anotada + `CHANGELOG.md` (perguntar a versão ao Fobs).

---

## Seletores validados

> Preencher ao fim da Fase 0, com data. Até lá, os seletores da POC são **hipótese**
> (vieram de documentação pública de outra integração).

| Chave | Seletor | Validado em |
|---|---|---|
| `chatToggleButton` | | |
| `closeChatButton` | | |
| `closeConversationButton` | | |
| `conversationListScroll` | | |
| `conversationOrderNumber` | | |
| `messageInput` | | |
| `sendButton` | | |
| `orderCard` | | |
| `orderDetailsChatButton` | | |
| `unreadIndicator` (Fase 5) | | |
| `messageBubble` (Fase 5) | | |
| `messageBubbleAuthor` (Fase 5) | | |

---

## Operação

- A extensão só funciona com **Chrome aberto no Gestor web, logado**. Gestor desktop ou Android
  não servem.
- Recomendação: **uma aba dedicada** à extensão, que a equipe não usa para operar, se a Fase 0
  confirmar que o Gestor aceita duas abas. Se não aceitar, a pausa por interação humana é a
  proteção, e o envio fica mais lento nos horários de pico.
- Instalação nesta versão: "Carregar sem compactação" em `chrome://extensions`. Publicação na
  Chrome Web Store (não listada) fica para depois.

## Riscos conhecidos

- **O iFood muda o HTML sem aviso.** Mitigação: seletores remotos, diagnóstico no heartbeat e
  status visível no CRM.
- **Termos de uso do Portal do Parceiro não verificados** quanto a automação da interface.
  Outras empresas operam assim abertamente, mas isso não é garantia. Ler antes de vender como
  recurso para outros clientes Ortex.
- **Entrega no máximo uma vez:** em falha no meio do envio, a mensagem fica `incerta` em vez de
  arriscar duplicar. Alguma mensagem pode não chegar; nenhuma chega em dobro.
- **Ler conversas tira o badge de não lida do Gestor** (Fase 5). Ver acima.

## Fora do escopo

- WhatsApp para pedidos iFood (removido nesta feature; PDV e Eventos seguem com Z-API).
- Responder avaliações do iFood via Review API (feature separada, futura).
- Disputas/negociação com análise de imagem (feature separada, futura).
- Aviso interno de atraso por WhatsApp para a equipe (só badge no CRM nesta versão).
- Atraso de pedidos `TAKEOUT`.
- **Correção do vínculo de cliente por telefone no polling.** `_criar_pedido()` usa o
  `localizer`/0800 como se fosse telefone e casa `Cliente` por sufixo de 8 dígitos, o que pode
  vincular o pedido ao cliente errado. Não afeta esta feature (as mensagens usam
  `cliente_nome` do próprio pedido, não o CRM), mas merece correção própria.

---

## O Que NÃO Fazer

- Não fazer HTTP dentro do signal de `PedidoIFood`: o signal só grava `MensagemChat`.
- Não criar `MensagemChat` de saída fora de `atendimento/servico.py::enfileirar()`.
- Não devolver `incerta`/`falha` para `pendente` automaticamente; reenvio é sempre uma
  mensagem nova criada por humano.
- Não deixar a extensão processar mensagens em paralelo nem reservar mais de uma por vez.
- Não reservar sem `select_for_update(skip_locked=True)`.
- Não liberar CORS no Django para `gestordepedidos.ifood.com.br`; a rede da extensão passa pelo
  background.
- Não gravar o token da extensão em texto puro; só o SHA-256.
- Não usar `TokenExtensaoAuthentication` fora de `/extensao/`, nem `TokenAuthentication` de
  usuário dentro.
- Não deixar um token ver fila ou pedidos de empresa fora de `token.empresas`.
- Não hardcodar nome de loja nos textos padrão; sempre `{loja}`.
- Não re-renderizar texto de mensagem já enfileirada; o texto é snapshot na criação.
- Não colocar responsabilidade nova no `ifood_polling` (atraso e IA são crons próprios).
- Não criar campo não-nulo em `PedidoIFood`, e não deployar migration de `ifood` sem reiniciar
  `arretado-polling`.
- Não usar `chrome.alarms` para o loop de 5 s (mínimo de 30 s no MV3); o relógio é do content
  script.
- Não clicar em nada na página no diagnóstico do heartbeat; ele só testa seletores.
- Não permitir que a IA cancele, altere pedido ou prometa compensação; regras fixas no prompt.
- Não usar o SDK `anthropic`; `requests` puro, como em `estoque/claude_client.py`.
- Não importar `estoque.claude_client` nem `estoque.ConfiguracaoIA` no atendimento.
- Não ligar `modo_ia='automatico'` como padrão em nenhuma empresa.
- Não ligar `chat_ativo` em migration, seed ou default; é decisão do usuário na tela.
- Não implementar DELETE em `MensagemChat`, `ModeloMensagemChat` ou `TokenExtensao`.
