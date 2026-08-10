# Sistema Multi-Empresa + Temas (MANGAIO)

> Spec para implementação via Claude Code. Padrões técnicos gerais em `CLAUDE.md` —
> este documento assume que o `CLAUDE.md` foi lido antes.
> Planejado em ago/2026. Mockup aprovado: `mockup_temas_multiempresa.html`.

---

## O que é

O CRM hoje atende uma única empresa (**Arretado Doces** — a "matriz"). Este spec adiciona
suporte a **múltiplas empresas (CNPJs) do mesmo dono** dentro do mesmo deploy e mesmo banco.

A primeira empresa nova é a **MANGAIO** (restaurante, **canal exclusivamente iFood**) —
o que delimita o escopo: só os módulos que a MANGAIO usa viram multi-empresa agora
(iFood, Financeiro, Dashboard, Relatórios, Clientes em modo compartilhado). PDV, Eventos,
Orçamentos, Contratos, Estoque, Fichas e Frete **continuam como estão**, pertencendo
implicitamente à matriz.

Junto vem o **sistema de temas**: cada usuário escolhe entre o tema da empresa ativa
(cores cadastradas no model `Empresa`) e dois modos neutros do produto (claro e noturno).

### Arquitetura escolhida (decisões fechadas — não reabrir)

- **Multi-tenant por linha** (FK `empresa`) no mesmo banco. **Não** usar `django-tenants`,
  schemas separados ou segunda instância Django.
- Model `Empresa` novo, em app novo `empresas/`.
- Módulos compartilhados: Clientes, Usuários, Auditoria, Notificações (Z-API única),
  Backup, infra. Módulos separados por empresa: iFood, Financeiro. Dashboard/Relatórios:
  compartilhados com filtro por empresa + visão consolidada.
- Multi-empresa é **feature de revenda**: nenhum nome, cor ou CNPJ da Arretado ou da
  MANGAIO pode ser hardcoded em código. Tudo vem do banco.

### Requisito inegociável de UI

**A UI atual da Arretado é o tema default e não pode mudar em nenhum pixel.** Os valores
atuais dos tokens CSS (`--caramelo`, `--surface`, `--fundo`, `--border`, `--muted`, etc.)
passam a ser o fallback de `:root` — sem tema aplicado, tudo renderiza exatamente como
hoje. Os temas novos são **camadas adicionais** (atributo `data-theme` + variáveis
injetadas), nunca uma reescrita. Critério objetivo: usuário da matriz que nunca tocar no
seletor de tema não percebe nenhuma diferença visual após o deploy.

---

## Fase 0 — App `empresas/` + model `Empresa`

### `empresas.Empresa`

| Campo | Tipo | Descrição |
|---|---|---|
| `nome` | CharField(80) | Nome fantasia exibido na UI ("Arretado Doces", "Mangaio") |
| `subtitulo` | CharField(80), blank | Linha sob o nome na sidebar ("Cozinha Brasileira") |
| `razao_social` | CharField(160), blank | Razão social |
| `cnpj` | CharField(18), blank, unique quando preenchido | CNPJ formatado |
| `padrao` | BooleanField, default False | Empresa matriz/default. **Exatamente uma** com `padrao=True` (constraint condicional `UniqueConstraint(fields=['padrao'], condition=Q(padrao=True))`) |
| `ativo` | BooleanField, default True | Inativa some dos seletores; histórico preservado |
| `criado_em` | DateTimeField auto | — |

### Branding (mesma tabela, seção visual)

Cores como `CharField(7)` com validator de hex (`^#[0-9A-Fa-f]{6}$`), todas `blank=True`.
Campo vazio → o frontend usa o valor default do token (ou seja, empresa sem cores
cadastradas renderiza com a UI atual da Arretado — comportamento seguro por construção).

| Campo | Token CSS correspondente | Valor MANGAIO (cadastrar via painel, nunca hardcoded) |
|---|---|---|
| `cor_fundo` | `--fundo` | `#F2E9D8` |
| `cor_surface` | `--surface` | `#FBF6EB` |
| `cor_surface_alt` | `--surface-alt` | `#F7EFDF` |
| `cor_borda` | `--border` | `#E2D7BE` |
| `cor_texto` | `--texto` | `#17382F` |
| `cor_muted` | `--muted` | `#5C6B4F` |
| `cor_primaria` | `--primaria` | `#AE4A2A` (terracota — botões/ações) |
| `cor_primaria_texto` | `--primaria-texto` | `#FBF6EB` |
| `cor_acento` | `--acento` | `#D4A35A` (dourado — chips/destaques) |
| `cor_sidebar` | `--sidebar-bg` | `#0F1F17` (verde-mata) |
| `cor_sidebar_texto` | `--sidebar-texto` | `#D8D2C0` |
| `cor_sidebar_ativo` | `--sidebar-ativo` | `#D4A35A` |

| Campo | Tipo | Descrição |
|---|---|---|
| `logo_horizontal` | ImageField, blank | Logo para fundos claros |
| `logo_negativo` | ImageField, blank | Logo para fundos escuros (sidebar/modo noturno) |
| `logo_simbolo` | ImageField, blank | Símbolo quadrado (favicon/avatar/tela de escolha) |
| `timbre` | FileField, blank | Timbre A4 para documentos — **campo preparatório, nenhum gerador de PDF lê dele nesta entrega** |

Uploads reaproveitam a infra `/media/` existente (Nginx já serve — ver `CLAUDE.md`,
seção `MEDIA_URL`). Não recriar nada.

### Migração de dados

Data migration cria **uma** `Empresa` com `padrao=True`, `nome='Empresa Principal'` e
todos os demais campos vazios. O usuário renomeia e preenche CNPJ/cores/logos pelo painel
(requisito de revenda: a migration não conhece "Arretado"). A MANGAIO é cadastrada
manualmente pela tela, nunca por migration/seed.

### Endpoints

```
GET/POST/PATCH        /api/v1/empresas/[{id}/]         # CRUD (sem DELETE — inativar via ativo=False)
GET                   /api/v1/empresas/branding-login/  # AllowAny; devolve nome/logos/cores da empresa padrao=True (tela de login)
```

- `CsrfExemptMixin` como todo ViewSet do projeto. `POST/PATCH` exigem login
  (`get_permissions()` por action, padrão local) e auditam via
  `AuditoriaCreateMixin`/`AuditoriaUpdateMixin`.
- **Sem endpoint DELETE** — FKs de pedido/financeiro apontarão pra cá com `PROTECT`;
  inativação é `ativo=False` (mesma filosofia de `DespesaRecorrente`).

### Frontend (Fase 0)

- `empresasApi` em `services.js` (list, create, update, brandingLogin).
- Seção "Empresas" em `Configuracoes.jsx` (ou tela própria `Empresas.jsx` + rota
  `/empresas`, menu Administração — decidir pelo espaço disponível no menu): lista +
  modal de criar/editar com preview das cores (swatches ao vivo) e upload dos 3 logos.
  Modal com prop `open` explícita, tokens de design, sem `localStorage` (padrões do projeto).

**Critério de pronto:** empresa matriz existente via migration; MANGAIO cadastrável pela
tela com cores e logos; auditoria registrando criação/edição; nenhuma outra parte do
sistema alterada ainda.

---

## Fase 1 — iFood multi-empresa

O worker de polling **já itera** sobre as configurações (`polling_worker.py::run_polling()`
→ `_processar_config()`) e `ConfiguracaoIFood` **não** é singleton (usa `.objects.first()`)
— a fundação já existe. O trabalho aqui é identificar cada config/pedido com a empresa.

### Mudanças de model

| Model | Mudança |
|---|---|
| `ifood.ConfiguracaoIFood` | + FK `empresa` → `empresas.Empresa` (`PROTECT`, `null=True` na 1ª migration → data migration atribui a `padrao=True` → 2ª migration `null=False`) |
| `ifood.PedidoIFood` | + FK `empresa` (`PROTECT`) — **denormalizada** a partir da config em `polling_worker.py::_criar_pedido()`, snapshot no momento da criação |
| `pedidos.PedidoUnificado` | + FK `empresa` (`PROTECT`, `null=True` — pedidos históricos de PDV/Eventos são atribuídos à matriz pela data migration) |

- Signal `ifood → PedidoUnificado` propaga `empresa` do `PedidoIFood`.
- Signals de PDV e Eventos → `PedidoUnificado` passam a preencher `empresa` com a empresa
  `padrao=True` (resolvida em runtime via `Empresa.objects.get(padrao=True)`, nunca id
  hardcoded). PDV/Eventos seguem mono-empresa por decisão de escopo.
- Estoque: **nenhuma mudança.** O débito automático do pedido iFood da MANGAIO fará fuzzy
  match por nome, não encontrará produto cadastrado, logará `warning` e seguirá — é o
  comportamento existente e desejado (ver `CLAUDE.md`, "Débito Automático de Estoque").

### Frontend/telas

- `IFood.jsx`: a tela de configuração passa a listar **uma config por empresa** (select de
  empresa no topo do card de credenciais). Pedidos listados ganham a coluna/badge da empresa
  quando o usuário tem vínculo com mais de uma.
- Cadastrar a config da MANGAIO = criar segunda linha de `ConfiguracaoIFood` com as
  credenciais do merchant dela. A homologação iFood da MANGAIO é processo à parte
  (fora deste spec), mas o sistema precisa aceitar as duas configs ativas simultâneas.

**Critério de pronto:** pedidos dos dois merchants entrando simultaneamente pelo mesmo
worker, cada um com `empresa` correta em `PedidoIFood` e `PedidoUnificado`; ACK e ações de
pedido funcionando com as credenciais da config correta (o client já resolve por config —
verificar que nenhum ponto usa `.objects.first()` para escolher credencial de envio de ação).

---

## Fase 2 — Usuários × Empresas + empresa ativa

### Mudanças em `usuarios.Usuario`

| Campo | Tipo | Descrição |
|---|---|---|
| `empresas` | M2M → `empresas.Empresa`, blank | Empresas que o usuário pode acessar. **Nunca** um choice `arretado/mangaio/ambos` — nomes de empresa não entram em código |
| `empresa_ativa` | FK → `empresas.Empresa`, `SET_NULL`, null | Última empresa escolhida (persistida no banco — **não** usar `localStorage`, regra do projeto) |
| `preferencia_tema` | CharField choices: `empresa` (default) / `neutro_claro` / `neutro_escuro` | Tema escolhido pelo usuário |

Data migration: todos os usuários existentes vinculados à empresa `padrao=True`, com
`empresa_ativa` apontando pra ela — comportamento pós-deploy idêntico ao atual.

### Fluxo de login

`POST /usuarios/login/` passa a devolver, além do token:
`empresas` (id/nome/logos/cores das vinculadas), `empresa_ativa`, `preferencia_tema`.

- **1 empresa vinculada** → frontend entra direto nela.
- **2+ empresas** → tela `EscolherEmpresa.jsx` (cards com logo + cor de cada empresa)
  antes do app. A escolha chama o endpoint abaixo e segue.
- **0 empresas** (usuário legado sem vínculo por algum motivo) → tratar como vinculado à
  empresa padrão, nunca bloquear o login.

### Endpoints novos

```
POST /api/v1/usuarios/definir-empresa-ativa/   # body: {empresa: id} — IsAuthenticated
POST /api/v1/usuarios/preferencia-tema/        # body: {tema: 'empresa'|'neutro_claro'|'neutro_escuro'} — IsAuthenticated
```

- `definir-empresa-ativa/` valida que a empresa está entre as vinculadas do usuário
  (exceção: `role=admin` pode ativar qualquer empresa ativa=True — decisão fechada),
  grava `Usuario.empresa_ativa` e audita **`empresa_alternada`** (constante nova em
  `auditoria`, com `detalhes={'de': ..., 'para': ...}`). Troca de empresa afeta o que o
  usuário enxerga de dados financeiros — por isso audita; troca de tema não audita
  (cosmético).
- `preferencia-tema/` só grava o campo. Sem auditoria.

### Controle de acesso por vínculo

Regra geral desta entrega (aplicada nas fases 3–5 conforme cada endpoint é tocado):
endpoints **empresa-aware** filtram o queryset pelas empresas vinculadas ao usuário
autenticado; `role=admin` enxerga todas. Endpoints que hoje são `AllowAny` e continuam
`AllowAny` (padrão do projeto) usam o parâmetro `?empresa=` sem filtro de vínculo — o
controle fino por vínculo só se aplica onde já existe `IsAuthenticated`. Não estender
autenticação global por causa disso (regra do `CLAUDE.md` mantida).

### Switcher no header

`AppLayout.jsx` ganha o switcher de empresa (pill com nome/cor, visível só quando o
usuário tem 2+ vínculos) — troca chama `definir-empresa-ativa/`, atualiza o
`EmpresaContext` e o tema (se `preferencia_tema='empresa'`) sem recarregar a página.

**Critério de pronto:** usuário com vínculo único não vê nada de novo além do (eventual)
seletor de tema; usuário com dois vínculos passa pela tela de escolha e alterna pelo
header; troca auditada; admin alterna livremente.

---

## Fase 3 — Sistema de temas (UI Arretado preservada)

### Arquitetura de temas no frontend

1. **Fallback = UI atual.** Os tokens existentes em `:root` **não mudam de valor**. Todo o
   trabalho é aditivo.
2. **Auditoria de cores hardcoded (pré-requisito da fase):** varrer os CSS Modules atrás
   de hex/rgb crus fora dos tokens e movê-los para variáveis **com o mesmo valor atual**
   (mudança invisível por definição). Sem isso o modo noturno quebra em pontos aleatórios.
   Entregar essa varredura como commit separado, antes de qualquer tema novo.
3. **Temas neutros (estáticos):** blocos `[data-theme="neutro-claro"]` e
   `[data-theme="neutro-escuro"]` num CSS global novo (`temas.css`), redefinindo só os
   tokens. Paleta de referência aprovada no mockup (claro: fundo `#F6F7FB`, surface
   `#FFFFFF`, texto `#0F172A`, primária `#4F46E5`; noturno: fundo `#0B1120`, surface
   `#131C31`, texto `#E7ECF5`, primária `#818CF8`; tipografia Inter nos dois). Esses
   valores são **identidade do produto Ortex**, não de cliente — podem viver no CSS.
4. **Tema de empresa (dinâmico):** as cores vêm do objeto `Empresa` retornado no login.
   Um helper `aplicarTema(empresa | modoNeutro)` no `EmpresaContext` injeta as variáveis
   via `document.documentElement.style.setProperty('--token', valor)` (e limpa ao trocar).
   Campo de cor vazio no cadastro → token não é sobrescrito → cai no valor default
   (UI Arretado). Consequência importante: **a matriz pode ficar com todos os campos de
   cor vazios** e o "tema da empresa" dela é simplesmente a UI atual — preservação por
   construção, sem duplicar a paleta Arretado no banco.
5. **Seletor de tema:** no header (`AppLayout.jsx`), 3 opções — Empresa / Claro / Noturno
   — persistindo via `preferencia-tema/`. Aplicado também um `data-theme` na raiz para os
   modos neutros.
6. **Tipografia:** temas de empresa mantêm Playfair Display + DM Sans (padrão atual);
   temas neutros trocam para Inter via token `--font-display`/`--font-body` (criar esses
   dois tokens no audit do item 2, apontando para as fontes atuais como default).

### Marca viva

- Sidebar: logo/nome/subtítulo da empresa ativa (logo negativo quando o fundo da sidebar
  for escuro — usar `logo_negativo` se preenchido, senão `logo_horizontal`).
- `document.title` = `"{nome} · CRM"`; favicon = `logo_simbolo` quando preenchido
  (fallback: favicon atual).
- Tela de login: branding da empresa `padrao=True` via `branding-login/` (hoje = visual
  atual da Arretado; nada muda até alguém cadastrar cores).

### O modo noturno e imagens

Logos e fotos não são invertidos. O único cuidado é o par `logo_horizontal`/`logo_negativo`
já previsto. Gráficos usam tokens (`--chart-*` — criar no audit) e acompanham o tema.

**Critério de pronto:** os 4 estados do mockup reproduzidos no app real; screenshot do
app da matriz com tema "Empresa" **byte-idêntico visualmente** ao de antes da fase (é o
teste de regressão da entrega); troca de tema instantânea, sem reload, sem `localStorage`.

---

## Fase 4 — Financeiro por empresa

A separação que importa de verdade: caixa e obrigações são por CNPJ.

### Mudanças de model (todas com o ciclo `null=True` → data migration p/ matriz → `null=False`)

| Model | Mudança |
|---|---|
| `financeiro.ContaBancaria` | + FK `empresa` (`PROTECT`) |
| `financeiro.ContaPagar` | + FK `empresa` (`PROTECT`) |
| `financeiro.ContaReceber` | + FK `empresa` (`PROTECT`) |
| `financeiro.DespesaRecorrente` | + FK `empresa` (`PROTECT`) — a `ContaPagar` gerada pelo cron herda a empresa do molde |
| `financeiro.MovimentoFinanceiro` | **sem campo próprio** — a empresa é a da `ContaBancaria` do movimento (property `empresa`). Não denormalizar |
| `financeiro.ConfiguracaoFinanceira` | deixa de ser singleton global: + FK `empresa` (`OneToOneField`, `PROTECT`); `get()` vira **`get(empresa)`** (cria a linha da empresa on-demand, mesmo espírito do singleton atual). Data migration liga a linha existente à matriz |
| `financeiro.CategoriaFinanceira` | **compartilhada** (plano de contas único entre empresas — simplifica consolidado). Sem mudança |
| `financeiro.Fornecedor` | **compartilhado**. Sem mudança |
| `financeiro.TelefoneAlertaFinanceiro` | **compartilhado** (equipe única). Sem mudança |

O contrato de `MovimentoFinanceiro.registrar()` **não muda** (atomicidade, quantização,
`select_for_update()`, ledger imutável — tudo igual). A conta bancária já carrega a empresa.

### Signals de venda → ledger

`financeiro/signals.py` passa a resolver a config **da empresa do pedido**:

- `ifood.PedidoIFood` `CONCLUDED` → `ConfiguracaoFinanceira.get(pedido.empresa)`; usa a
  `conta_padrao_vendas` **daquela** empresa (que é uma `ContaBancaria` da mesma empresa —
  validar no serializer da config: `conta_padrao_vendas.empresa == empresa`). Modo
  `no_ato`/`repasse` e `dias_repasse_ifood` também são lidos da config da empresa — a
  MANGAIO pode operar `repasse` e a matriz `no_ato` sem conflito.
- `pdv.PedidoPDV` e `eventos.PagamentoEvento` → `ConfiguracaoFinanceira.get(empresa_padrao)`
  (canais mono-empresa por escopo).
- `ContaReceber` criada pelo signal iFood herda `empresa = pedido.empresa`.
- Regra existente mantida: config sem `conta_padrao_vendas` → warning e não grava, por
  empresa. A MANGAIO sem conta configurada não bloqueia nada da matriz e vice-versa.

### Views/relatórios financeiros

- Todos os ViewSets do financeiro aceitam `?empresa=<id>`; sem o parâmetro, default =
  `empresa_ativa` do usuário autenticado (quando houver auth na action); listas filtradas
  pelo vínculo do usuário (regra da Fase 2).
- `contas-pagar/resumo/`, `contas-receber/resumo/` e `fluxo-caixa/` aceitam
  `?empresa=<id>` **ou** `?empresa=todas` (consolidado soma tudo que o usuário pode ver).
  O saldo dinâmico de Eventos dentro de `contas-receber/resumo/` pertence à matriz —
  aparece só quando ela está no filtro.
- Cron `gerar_contas_recorrentes` e `alertar_vencimentos`: sem mudança de agendamento;
  processam todas as empresas numa passada. **Mensagem de alerta de vencimento ganha o
  prefixo `[{empresa.nome}]`** — com dois CNPJs alimentando os mesmos telefones, alerta
  sem nome de empresa é adivinhação. (Alertas de estoque/eventos/backup seguem
  mono-empresa e não mudam.)

### Frontend

- `Financeiro.jsx`: respeita a empresa ativa do contexto; badge/watermark discreto com o
  nome da empresa no topo da tela (reforço anti-CNPJ-errado além da cor); aba
  Configurações mostra a config **da empresa ativa**; cadastro de conta bancária ganha o
  campo empresa (pré-preenchido com a ativa).
- Filtro "Todas (consolidado)" nas abas de fluxo de caixa e resumos, quando o usuário
  tem 2+ vínculos.

**Critério de pronto:** venda iFood da MANGAIO batendo na conta bancária da MANGAIO;
venda PDV/Evento continuando na matriz; fluxo de caixa por empresa e consolidado
conferindo na soma; teste automatizado novo cobrindo o roteamento por empresa dos 3
signals (suíte `financeiro` já existe — estender).

---

## Fase 5 — Dashboard e Relatórios com filtro de empresa

- `dashboard/resumo/` aceita `?empresa=<id|todas>`; default = empresa ativa. Toda a
  agregação já lê `PedidoUnificado` (que agora tem `empresa`) + `PagamentoEvento` (matriz).
  Na visão MANGAIO: cards de PDV/Eventos ficam zerados/ocultos e entra o card "Repasse
  iFood a receber" (soma de `ContaReceber` `canal='ifood'` pendente/parcial da empresa) —
  layout conforme mockup aprovado.
- `relatorios/ifood/` aceita `?empresa=` (resumo/agrupado/exports).
- Sidebar dinâmica por empresa ativa: itens de módulos que a empresa não usa somem
  (mesma transição do mockup). A definição de "quais módulos" **não** é hardcoded por
  nome de empresa: campo novo `Empresa.modulos_ocultos` (JSONField, lista de slugs de
  rota, default `[]`) editável no cadastro da empresa — a matriz fica `[]` (menu atual
  completo, UI preservada), a MANGAIO recebe via painel a lista dos módulos que não usa.
  `Sidebar.jsx` filtra por esse campo (e `App.jsx` mantém todas as rotas — ocultar item
  de menu não é permissão; é só UI).

**Critério de pronto:** dashboard alternando entre matriz/MANGAIO/consolidado com números
conferindo com os relatórios; menu da MANGAIO reduzido conforme cadastro; menu da matriz
idêntico ao atual.

---

## Ordem de implementação e dependências

```
Fase 0 (Empresa) ──► Fase 1 (iFood) ──► Fase 2 (Usuários/empresa ativa) ──► Fase 3 (Temas)
                                                        │
                                                        └──► Fase 4 (Financeiro) ──► Fase 5 (Dash/Relatórios)
```

Fases 3 e 4 são independentes entre si e podem ser sessões separadas de Claude Code.
Cada fase termina com migrations aplicadas, testes verdes e atualização do `CLAUDE.md`
(Estrutura de Pastas + Padrões Obrigatórios + Status das Fases + O Que NÃO Fazer).

---

## O Que NÃO Fazer

- **Não alterar nenhum valor dos tokens CSS atuais em `:root`** — a UI da Arretado é o
  default intocável; temas novos só existem como `data-theme`/variáveis injetadas por cima
- Não criar choice/enum com nomes de empresa (`arretado`, `mangaio`) em nenhum model,
  serializer, CSS ou componente — empresa é sempre registro do banco (requisito de revenda)
- Não hardcodar as cores da MANGAIO (nem da Arretado) em código — cores de empresa vivem
  só no model `Empresa`; as únicas paletas em CSS são os dois modos neutros (identidade
  do produto)
- Não usar `localStorage` para empresa ativa nem preferência de tema — persistência é no
  `Usuario` via API (regra existente do projeto; exceção continua sendo só o `authApi`)
- Não usar `django-tenants`/schemas/segunda instância — multi-tenant é por linha, decisão fechada
- Não implementar DELETE de `Empresa` — inativar via `ativo=False`; FKs são `PROTECT`
- Não permitir duas empresas com `padrao=True` — constraint condicional + validação no serializer
- Não resolver a empresa padrão por id fixo em código — sempre `Empresa.objects.get(padrao=True)`
  (helper `Empresa.get_padrao()` para não repetir a query em todo signal)
- Não escolher credencial iFood via `.objects.first()` em nenhum ponto novo — a config
  correta é sempre a do pedido/empresa em questão
- Não denormalizar `empresa` em `MovimentoFinanceiro` — a empresa do movimento é a da
  `ContaBancaria` (property), fonte única
- Não mudar o contrato de `MovimentoFinanceiro.registrar()` nem de
  `MovimentoEstoque.registrar()` — a fase financeira só troca **qual** config/conta é
  resolvida, nunca **como** o ledger grava
- Não permitir `conta_padrao_vendas` de uma empresa apontando para `ContaBancaria` de
  outra — validar no serializer da `ConfiguracaoFinanceira`
- Não materializar `ContaReceber` para Eventos/PDV (regra existente — continua valendo
  por empresa)
- Não tocar em `estoque/` nesta entrega — o fuzzy match sem correspondência da MANGAIO
  logando warning é comportamento correto, não bug a "corrigir"
- Não filtrar rota/permissão pelo `modulos_ocultos` — é ocultação de menu (UI), não RBAC;
  permissão continua sendo papel do sistema de roles/vínculos
- Não auditar troca de tema (cosmético); **auditar sempre** troca de empresa ativa
  (`empresa_alternada`)
- Não bloquear login de usuário sem vínculo de empresa — tratar como vinculado à padrão
- Não gerar PDF com timbre da empresa nesta entrega — `Empresa.timbre` é campo
  preparatório; `pdf_contrato.py`/`pdf_orcamento.py` continuam intocados
- Não incluir as credenciais iFood de uma empresa na resposta de outra — serializers de
  `ConfiguracaoIFood` filtrados pelo mesmo critério de vínculo dos dados financeiros
- Não rodar `npm run build` na VPS sem avisar (regra existente — vale dobrado aqui, a
  fase de temas mexe em CSS global)

---

## Fora de escopo (desta entrega)

- **NFC-e / Focus NFe** — a arquitetura por empresa já nasce compatível (`ConfiguracaoNFCe`
  futura será por empresa, alinhada ao painel multi-empresa do Focus NFe), mas emissão
  fiscal é projeto próprio com pré-requisitos administrativos (e-CNPJ, CSC, SEFAZ-PI)
- Catálogo/Estoque/Fichas por empresa (cardápio próprio da MANGAIO no CRM)
- PDV e Eventos multi-empresa
- Instância Z-API separada por empresa (campo futuro se a MANGAIO quiser número próprio
  de WhatsApp)
- RBAC granular por empresa além do vínculo (ex.: admin de uma empresa só)
- Timbre/documentos PDF por empresa (campo já criado, geradores intocados)
- Anota AI (pendência independente — quando vier, o app `anotaai/` já nasce com FK
  `empresa` no padrão da Fase 1)
