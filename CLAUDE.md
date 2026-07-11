# Arretado Doces — CRM Proprietário

> Arquivo lido automaticamente pelo Claude Code em toda sessão.
> Última atualização: 11/jul/2026.

---

## Visão Geral

CRM proprietário para a **Arretado Doces** — confeitaria em Teresina/PI, Brasil.  
Gerencia clientes, pedidos, múltiplos canais de venda, orçamentos/eventos, catálogo de produtos e precificação.

- **Backend:** Django 4.2 + DRF · Python
- **Frontend:** React + Vite · CSS Modules
- **Banco:** PostgreSQL (prod e dev local via Docker)
- **Deploy:** Gunicorn (`arretado.service`) + Nginx · Ubuntu 24 · VPS `root@2.25.142.171`
- **Código:** `git@github.com:ortextec-create/crm_arretado.git`
- **URL prod:** https://arretado.ortex.solutions
- **Caminho VPS:** `/var/www/crm_arretado/`

---

## Estrutura de Pastas

```
arretado/                        ← raiz Django
├── config/
│   ├── settings.py              ← INSTALLED_APPS: clientes, ifood, pdv, pedidos, eventos, usuarios, notificacoes, fichas, relatorios, dashboard
│   ├── urls.py                  ← rotas: /api/v1/, /api/v1/ifood/, /api/v1/pdv/, /api/v1/eventos/, /api/v1/notificacoes/, /api/v1/fichas/, /api/v1/relatorios/, /api/v1/dashboard/
│   └── wsgi.py
├── clientes/                    ← Fase 1: CRM de clientes
│   ├── models.py                ← Cliente (inclui rg/rg_orgao_emissor/nacionalidade/profissao/estado_civil —
│   │                               opcionais no cadastro, exigidos na emissão de Contrato, ver Contrato.md), Endereço, TagCliente
│   └── views.py                 ← inclui action `historico` (GET /api/v1/clientes/{id}/historico/)
├── ifood/                       ← Fase 2: integração iFood
│   ├── models.py                ← ConfiguracaoIFood, PedidoIFood, ItemPedidoIFood, EventoPollingIFood
│   ├── ifood_client.py          ← IFoodClient (auth, polling, ACK, pedidos)
│   ├── polling_worker.py        ← run_polling(), _processar_config(), _criar_pedido()
│   └── management/commands/ifood_polling.py
├── pedidos/                     ← Fase 3: espelho unificado (só leitura)
│   ├── models.py                ← PedidoUnificado
│   └── apps.py                  ← registra signals do iFood e PDV no ready()
├── pdv/                         ← Fase 3-ext-A: PDV próprio
│   ├── models.py                ← CategoriaProduto, Produto (+ segmento/foto/disponibilidades), PedidoPDV, ItemPedidoPDV,
│   │                               TaxaEntregaBairro (bairro→taxa), ConfiguracaoEntrega (singleton, frete padrão)
│   ├── urls.py                  ← inclui taxas-entrega/ e configuracao-entrega/
│   └── signals.py               ← espelha PedidoPDV → PedidoUnificado
├── eventos/                     ← Fase 4: gestão de eventos/encomendas + orçamentos + contratos
│   ├── models.py                ← Orcamento, ItemOrcamento, Evento, ItemEvento, LocalEvento,
│   │                               Contrato (snapshot, CTR-0001...), ConfiguracaoContrato (singleton — ver Contrato.md),
│   │                               ImagemInspiracao (galeria de imagens de referência do cliente, FK → Orcamento),
│   │                               PagamentoEvento (parcelas de pagamento do Evento, FK → Evento — Evento.sinal_pago
│   │                               é sempre derivado da soma dos pagamentos com status='pago', via
│   │                               Evento.recalcular_sinal_pago(), nunca gravado direto)
│   │                               (Orcamento e Evento têm tipo_entrega/local/endereco_avulso/bairro_entrega/taxa_entrega — ver FRETE.md)
│   ├── pdf_orcamento.py          ← gera PDF (ReportLab, canvas cru, 1 página) — inclui linha "Taxa de entrega" quando houver
│   ├── pdf_contrato.py           ← gera PDF do contrato (ReportLab Platypus, multi-página) — texto e cláusulas vêm de
│   │                               ConfiguracaoContrato.get() + snapshot do Contrato, nunca hardcoded
│   └── views.py                 ← OrcamentoViewSet (converter-em-evento, gerar-contrato, imagens/, itens/{id}/editar/,
│                                    update() restrito a status rascunho/enviado) + EventoViewSet (pagamentos/, pagamentos/{id}/remover/) +
│                                    ContratoViewSet (só leitura + pdf/enviar-whatsapp) + ConfiguracaoContratoViewSet
├── usuarios/                    ← Gestão de usuários + RBAC
│   └── views.py
├── notificacoes/                ← WhatsApp via Z-API
│   ├── models.py                ← HistoricoMensagem · ConfiguracaoWhatsApp (singleton, inclui validade_orcamento_dias)
│   ├── zapi_client.py           ← enviar_texto(), enviar_documento(), status_conexao() · resolve número canônico via phone-exists · lança ZAPIError
│   ├── servico.py               ← notificar() · notificar_documento() — nunca chamar zapi_client diretamente fora daqui
│   ├── views.py                 ← MensagemViewSet (listar, enviar, status-conexao)
│   └── management/commands/lembrar_aniversarios.py
├── fichas/                      ← Catálogo, Fichas Técnicas e Precificação
│   ├── models.py                ← MateriaPrima, FichaTecnica, ItemFichaTecnica, ParametrosNegocio, SnapshotPrecos
│   ├── views.py                 ← MateriaPrimaViewSet, FichaTecnicaViewSet, ParametrosNegocioViewSet,
│   │                               SnapshotPrecosViewSet, AjusteLinearView, DesfazerAjusteView
│   ├── urls.py                  ← router + ajuste-linear/ + desfazer-ajuste/<id>/
│   └── management/commands/importar_planilha.py  ← popula BD a partir do .xlsx
├── relatorios/                  ← Relatórios consolidados por canal
│   ├── views.py                 ← RelatorioIFoodView (resumo + agrupado por dia/mês, export Excel/PDF)
│   └── urls.py                  ← ifood/ (mais canais a adicionar conforme necessário)
├── dashboard/                    ← Dashboard multi-canal (só leitura, sem models próprios)
│   ├── views.py                 ← DashboardResumoView (APIView, GET) — agrega PedidoUnificado (iFood/PDV)
│   │                               + PagamentoEvento/Evento (eventos) num único JSON, ver regras abaixo
│   └── urls.py                  ← resumo/
└── manage.py

arretado-crm/                    ← raiz React
└── src/
    ├── api/
    │   ├── client.js            ← axios base
    │   └── services.js          ← clientesApi, tagsApi, ifoodApi, pdvApi, pedidosApi,
    │                               eventosApi, locaisEventoApi, orcamentosApi, contratosApi, configContratoApi,
    │                               notificacoesApi, usuariosApi, authApi, fichasApi,
    │                               taxasEntregaApi, configEntregaApi, relatoriosApi, dashboardApi
    ├── pages/
    │   ├── Login.jsx
    │   ├── Dashboard.jsx        ← agrega dashboardApi.resumo() (canais + gráfico 7 dias + a receber +
    │   │                          fila operacional + próximos eventos + ticket médio) e clientesApi (recentes)
    │   ├── Clientes.jsx
    │   ├── ClienteDetail.jsx
    │   ├── Tags.jsx
    │   ├── Usuarios.jsx
    │   ├── IFood.jsx
    │   ├── PDV.jsx
    │   ├── CatalogoPDV.jsx      ← catálogo do PDV (gestão de produtos para venda)
    │   ├── Catalogo.jsx         ← catálogo geral (grid de cards, foto, segmento, canais)
    │   ├── FichasTecnicas.jsx   ← composição de ingredientes por produto
    │   ├── CentralPrecos.jsx    ← precificação (matérias, ajuste linear, semáforo, parâmetros)
    │   ├── Relatorios.jsx       ← relatório consolidado iFood (resumo, gráfico por período, export Excel/PDF)
    │   ├── Eventos.jsx
    │   ├── Orcamentos.jsx       ← inclui botão "Emitir Contrato" (status='aprovado') + ModalEmitirContrato
    │   ├── Locais.jsx           ← cadastro de Locais de Evento (LocalEvento)
    │   ├── TaxasEntrega.jsx     ← cadastro de taxas por bairro + frete padrão (ver FRETE.md)
    │   ├── Notificacoes.jsx
    │   ├── Configuracoes.jsx
    │   └── Vinculacoes.jsx
    ├── components/
    │   ├── layout/
    │   │   ├── AppLayout.jsx
    │   │   └── Sidebar.jsx
    │   └── ui/                  ← Btn, Modal, Spinner, Avatar, etc.
    └── App.jsx                  ← rotas do frontend
```

---

## Padrões Obrigatórios

### Backend
- **`CsrfExemptMixin`** em todos os ViewSets (padrão estabelecido no projeto)
- **Canais de venda = apps Django separados** (`ifood/`, `pdv/`, futuramente `anotaai/`)
- **`PedidoUnificado` é espelho** — nunca escrito diretamente por views. Alimentado exclusivamente por signals (`post_save`) dos apps de canal
- **Signals dentro de try/except** — nunca falham o fluxo principal
- **Cron + management commands** em vez de Celery (ex: `ifood_polling`, `lembrar_aniversarios`)
- Número do pedido PDV: método `PedidoPDV.proximo_numero()` — sequencial com zero-fill
- Itens do PDV: snapshot de nome e preço no momento da venda
- **Z-API WhatsApp:** configurado via `.env` (`ZAPI_INSTANCE_ID`, `ZAPI_TOKEN`, `ZAPI_CLIENT_TOKEN`) com fallback para o banco (`ConfiguracaoWhatsApp`). O cliente em `notificacoes/zapi_client.py` resolve o número canônico via `phone-exists` antes de cada envio (trata números BR de 8 e 9 dígitos), lança `ZAPIError` em caso de falha. Sempre use `notificacoes/servico.py` (`notificar()` para texto, `notificar_documento()` para PDF) — nunca chame `zapi_client` diretamente em views ou signals.
- **ConfiguracaoWhatsApp é singleton** — sempre acessado via `ConfiguracaoWhatsApp.get()`. Contém credenciais Z-API, toggles de notificação, templates de mensagem e `validade_orcamento_dias` (prazo padrão de validade de orçamentos, configurável em Configurações).
- **fichas.ParametrosNegocio é singleton** — sempre acessado via `ParametrosNegocio.get()`, nunca instanciado diretamente
- **FichaTecnica → pdv.Produto** é uma FK fraca via `produto_pdv_id` (IntegerField, não ForeignKey) — o produto pode existir sem ficha e vice-versa
- **SnapshotPrecos** é gravado automaticamente antes de qualquer `AjusteLinear` com `confirmar=True`
- **pdv.ConfiguracaoEntrega é singleton** — sempre acessado via `ConfiguracaoEntrega.get()`. Guarda o `frete_padrao` usado quando a entrega é por bairro mas nenhum bairro cadastrado foi selecionado
- **`pdv.TaxaEntregaBairro`** é a tabela configurável de bairro→taxa usada por PDV e Orçamentos/Eventos. Nunca hardcodar valor de frete no código — ver `FRETE.md` para o funcionamento completo do sistema de entrega
- **`eventos.ConfiguracaoContrato` é singleton** — sempre acessado via `ConfiguracaoContrato.get()`. Guarda razão social/CNPJ/representante da CONTRATADA e todos os percentuais/prazos das cláusulas (sinal, multa, juros, prazos de personalização/rescisão/devolução, foro). Nunca hardcodar cláusula numérica no gerador de PDF — ver `Contrato.md`
- **`eventos.Contrato`** é um snapshot gravado no momento da emissão (mesma filosofia de `ItemOrcamento`/`SnapshotPrecos`) — `valor_total`/`percentual_sinal`/`valor_sinal`/`data_quitacao` nunca são recalculados ao reabrir/reimprimir um contrato já emitido
- **Emissão de contrato** (`POST /eventos/orcamentos/{id}/gerar-contrato/`) só é permitida com `Orcamento.status == 'aprovado'` e exige CPF/RG/nacionalidade/profissão/estado civil do cliente preenchidos (podem estar vazios no cadastro normal — são exigidos só neste momento) — ver `Contrato.md`
- **`eventos.ImagemInspiracao`** é a galeria de imagens de referência (uso interno da equipe, nunca entra no PDF/WhatsApp do orçamento) anexada ao `Orcamento` inteiro (não por item). `Evento` **não duplica** essas imagens — `EventoDetailSerializer.imagens_inspiracao` é um `SerializerMethodField` que lê direto de `evento.orcamento_origem.imagens_inspiracao` (mesma filosofia de nunca duplicar o que a relação já entrega, como o Contrato faz com os itens do Orçamento)
- **`MEDIA_URL`/`MEDIA_ROOT`** estão configurados em `config/settings.py` (`/media/`, `BASE_DIR / 'media'`) desde a feature de Imagens de Inspiração — é o único `ImageField` do projeto de fato exercitado em produção. Em prod, o Nginx tem um `location /media/ { alias .../media/; }` próprio (não é servido pelo Django/Gunicorn) — qualquer novo `ImageField`/`FileField` já pode reaproveitar essa infra, não precisa recriar
- **Cuidado com `prefetch_related` + criação de objeto relacionado na mesma request**: se uma view faz `self.get_object()` sobre um queryset com `prefetch_related('algo')` e, na mesma request, cria/deleta um objeto relacionado via `Model.objects.create(fk=obj, ...)` (sem passar pelo manager `obj.algo`), o cache do prefetch fica stale e `obj.algo.all()` (inclusive dentro do serializer) não reflete a mudança. Sempre que fizer isso, chamar `obj.refresh_from_db()` antes de serializar a resposta (foi o que corrigiu `adicionar_imagens`/`remover_imagem` no `OrcamentoViewSet` e `adicionar_pagamento` no `EventoViewSet` — o mesmo padrão de `adicionar_item`/`remover_item` pode estar sujeito ao mesmo problema, não verificado)
- **`eventos.PagamentoEvento`** registra as parcelas de pagamento de um `Evento` (valor/forma_pagamento/status/data_pagamento/observação). `Evento.sinal_pago` **nunca** é gravado direto — é sempre recalculado via `Evento.recalcular_sinal_pago()` (soma dos pagamentos com `status='pago'`), chamado após criar/remover um `PagamentoEvento` (`POST/DELETE /eventos/{id}/pagamentos/...`). O sinal informado na criação do Evento ou na conversão de Orçamento em Evento (`sinal_pago` no body) também vira um `PagamentoEvento` inicial (forma `outro`, status `pago`) em vez de setar o campo diretamente
- **Edição de Orçamento**: `OrcamentoViewSet.update()` só permite `PATCH/PUT` quando `status` é `rascunho` ou `enviado` (400 caso contrário); mesma restrição vale para editar item (`PATCH /eventos/orcamentos/{id}/itens/{item_id}/editar/`). Depois de aprovado/enviado além desses estágios, o orçamento é imutável (mesma filosofia do `Contrato` como snapshot)
- **`dashboard/` é um app só-leitura, sem models** — `DashboardResumoView` (`GET /api/v1/dashboard/resumo/`) apenas agrega dados que já existem em `pedidos.PedidoUnificado` e `eventos.Evento`/`PagamentoEvento`. Regra importante: a receita de **Eventos** no dia (`canais.eventos.recebido_hoje` e a fatia "eventos" do `grafico_7dias`) vem **exclusivamente** de `PagamentoEvento` com `status='pago'` e `data_pagamento` do dia — nunca de `Evento.valor_total` nem do status de entrega (é recebimento efetivo de caixa, não valor do pedido). Já `ticket_medio.eventos` é a exceção: usa `Evento.valor_total` (não `PagamentoEvento`) dos eventos `status='entregue'` nos últimos 30 dias, porque ali a métrica é tamanho médio de venda, não fluxo de caixa. `fila_operacional` cruza os 3 canais lendo só `PedidoUnificado` (o `Evento` já sincroniza pra lá via `EVENTO_STATUS_MAP`), nunca faz query separada em `eventos.Evento`

### Frontend
- **Sem `localStorage`** — estado React + context de autenticação *(exceção: `authApi` usa localStorage para sessão — refatorar para cookie/JWT no futuro)*
- **CSS Modules** — cada página tem seu `.module.css`
- **Variáveis CSS do design system:**
  - `--caramelo` → cor primária da marca
  - `--fundo` → background da página
  - `--surface` → background de cards/tabelas
  - `--border` → bordas gerais
  - `--texto` → texto principal
  - `--muted` → texto secundário/placeholder
  - `--hover` → hover em linhas
  - `--verde` → indicadores positivos
- **Tipografia:** `'Playfair Display', serif` em títulos · `'Inter', sans-serif` em corpo
- **Ícones:** Tabler Icons (`ti ti-*`)
- **`services.js`:** um objeto de API por canal — `clientesApi`, `ifoodApi`, `pdvApi`, `notificacoesApi`, `orcamentosApi`, `fichasApi`
- **Novo canal** = novo objeto no `services.js` seguindo o mesmo padrão
- **Busca de cliente CRM** (padrão usado em `Eventos.jsx` e `Orcamentos.jsx`): input com debounce 350ms → `clientesApi.list({ search })` → dropdown com seleção → chip com nome/telefone e botão X para limpar. Nunca usar `<select>` com todos os clientes pré-carregados.
- **Upload de arquivo/imagem via axios**: `api/client.js` fixa `headers: {'Content-Type': 'application/json'}` na instância do axios, e isso **não** é sobrescrito automaticamente quando o corpo é um `FormData` — sem correção, o navegador não define o boundary do multipart e o backend recebe a requisição sem o arquivo (`request.FILES` vazio). Sempre que enviar `FormData`, passar `{ headers: { 'Content-Type': undefined } }` na chamada (ver `orcamentosApi.adicionarImagens` em `services.js`) para o navegador definir o header correto.
- **Lightbox de imagem ampliada**: padrão usado em `Orcamentos.jsx`/`Eventos.jsx` para a galeria de `imagens_inspiracao` — clique na thumbnail abre um overlay `position: fixed` (z-index 400, acima do Modal que é 200) com a imagem em `object-fit: contain`, fecha no clique fora ou no X. Reaproveitar esse padrão para qualquer nova galeria de imagens.

---

## Status das Fases

| Fase | Descrição | Status |
|---|---|---|
| Fase 1 | CRM de Clientes (cadastro, endereços, tags) | ✅ Concluída |
| Fase 2 | Integração iFood (polling, pedidos, ações) | ✅ Concluída |
| Fase 3 | Histórico unificado de pedidos | ✅ Concluída |
| Fase 3-ext-A | PDV Próprio (backend + frontend) | ✅ Concluída |
| Fase 3-ext-B | Anota AI | 🔲 Pendente |
| Fase 4 | Vinculação manual de pedidos a clientes | ✅ Concluída (`Vinculacoes.jsx`) |
| Orçamentos | Orçamentos pré-evento (ORC-0001) + conversão em Evento + envio de PDF por WhatsApp | ✅ Concluída |
| Fase 5 | Dashboard e relatórios | ✅ Concluída (`Dashboard.jsx`) |
| WhatsApp | Notificações via Z-API | ✅ Concluída (`notificacoes/` + `zapi_client.py`) |
| Usuários | Gestão de usuários + RBAC | ✅ Concluída |
| Catálogo & Precificação | App `fichas/` + 3 telas de frontend | ✅ Concluída · dados importados em prod |
| Frete por Bairro | Cálculo de taxa de entrega por bairro no PDV e Orçamentos/Eventos + frete padrão configurável + cadastro de Locais de Evento | ✅ Concluída (ver `FRETE.md`) |
| Relatórios | Relatório consolidado iFood (resumo, agrupamento por dia/mês, export Excel/PDF) — app `relatorios/` | ✅ Concluída (apenas canal iFood por enquanto) |
| Contrato | Emissão de Contrato de Aquisição de Produtos a partir de Orçamento aprovado (PDF com cláusulas configuráveis + envio por WhatsApp) | ✅ Concluída (ver `Contrato.md`) |
| Imagens de Inspiração | Galeria de imagens de referência anexada ao Orçamento (upload múltiplo, lightbox, uso interno, visível também no Evento após conversão) | ✅ Concluída |
| Pagamentos Parciais de Evento | `eventos.PagamentoEvento` (parcelas), `Evento.sinal_pago` derivado, redesign do modal de detalhe do Evento (stepper + abas), edição de Orçamento antes da conversão | ✅ Concluída |
| Dashboard Multi-Canal | App `dashboard/` (só leitura) — vendas do dia e histórico recente consolidado de iFood/PDV/Eventos (+ espaço reservado pra Anota AI), gráfico 7 dias, a receber, fila operacional, próximos eventos, ticket médio | ✅ Concluída |

---

## Pendências Ativas

1. **Anota AI (Fase 3-ext-B)** — criar app `anotaai/` seguindo o padrão de `pdv/`
2. **Fichas técnicas incompletas** — 3 ingredientes com custo zero na planilha original (`Cobertura cappucino`, `Folha decorativa`, `Castanha do Pará`, `Ameixa`) e `Brigadeiro Sensacional` sem quantidades
3. **Foto de produtos** — campo `foto` (ImageField) existe no model mas upload ainda não está no frontend (`Catalogo.jsx`)
4. **PDV Hardware (roadmap):**
   - Curto prazo: impressora térmica TCP/IP (Django imprime via socket ESC/POS) + caixa registradora pelo mesmo cabo
   - Médio prazo: NFC-e (nota fiscal — SEFAZ-PI)
   - Longo prazo: TEF integrado
5. **Relatórios cobrem só iFood** — `relatorios/` tem apenas `RelatorioIFoodView`; expandir para PDV e Eventos/Orçamentos seguindo o mesmo padrão (resumo + agrupado + export Excel/PDF)
6. **Variáveis de ambiente em prod para WhatsApp (Z-API):**
   ```
   ZAPI_INSTANCE_ID=3F44AD8FFA071145A7847A94F00847F6
   ZAPI_TOKEN=664FD7CD1788EFA5660A875F
   ZAPI_CLIENT_TOKEN=<client-token>
   ```

---

## Endpoints Principais

```
# Clientes
GET/POST             /api/v1/clientes/
GET/PUT/PATCH/DELETE /api/v1/clientes/{id}/
GET                  /api/v1/clientes/{id}/historico/
GET/POST             /api/v1/tags/

# iFood
GET  /api/v1/ifood/pedidos/
POST /api/v1/ifood/pedidos/{id}/confirmar/
POST /api/v1/ifood/pedidos/{id}/vincular-cliente/
GET  /api/v1/ifood/config/status/

# PDV
GET/POST /api/v1/pdv/pedidos/
GET/POST /api/v1/pdv/produtos/
GET/POST /api/v1/pdv/categorias/
POST     /api/v1/pdv/pedidos/{id}/confirmar/
POST     /api/v1/pdv/pedidos/{id}/concluir/

# Frete (ver FRETE.md)
GET/POST/PATCH/DELETE /api/v1/pdv/taxas-entrega/[{id}/]     ← cadastro de bairro→taxa
GET/PATCH             /api/v1/pdv/configuracao-entrega/1/   ← singleton, campo frete_padrao

# Orçamentos
GET/POST      /api/v1/eventos/orcamentos/
GET/PATCH     /api/v1/eventos/orcamentos/{id}/                          ← PATCH só permitido com status rascunho/enviado
POST          /api/v1/eventos/orcamentos/{id}/enviar/
POST          /api/v1/eventos/orcamentos/{id}/aprovar/
POST          /api/v1/eventos/orcamentos/{id}/recusar/
POST          /api/v1/eventos/orcamentos/{id}/converter-em-evento/      ← body opcional "sinal_pago" vira 1º PagamentoEvento
POST          /api/v1/eventos/orcamentos/{id}/itens/
PATCH         /api/v1/eventos/orcamentos/{id}/itens/{item_id}/editar/   ← só com status rascunho/enviado
DELETE        /api/v1/eventos/orcamentos/{id}/itens/{item_id}/remover/
POST          /api/v1/eventos/orcamentos/{id}/imagens/                  ← multipart, campo "imagens" (um ou mais arquivos)
DELETE        /api/v1/eventos/orcamentos/{id}/imagens/{imagem_id}/remover/
GET           /api/v1/eventos/orcamentos/{id}/pdf/
POST          /api/v1/eventos/orcamentos/{id}/enviar-whatsapp/   ← gera PDF + envia via Z-API + grava HistoricoMensagem + muda status para 'enviado'
POST          /api/v1/eventos/orcamentos/{id}/gerar-contrato/    ← só com status='aprovado' · body: cpf/rg/rg_orgao_emissor/nacionalidade/profissao/estado_civil/endereco_avulso

# Contratos (ver Contrato.md)
GET           /api/v1/eventos/contratos/                        ← só leitura (contrato só é criado via gerar-contrato/ acima)
GET           /api/v1/eventos/contratos/{id}/
GET           /api/v1/eventos/contratos/{id}/pdf/
POST          /api/v1/eventos/contratos/{id}/enviar-whatsapp/
GET/PATCH     /api/v1/eventos/configuracao-contrato/1/           ← singleton

# Eventos
GET/POST              /api/v1/eventos/                                  ← POST aceita "sinal_pago" opcional (vira 1º PagamentoEvento)
GET/POST              /api/v1/eventos/locais/
GET/PATCH/DELETE      /api/v1/eventos/locais/{id}/
POST                  /api/v1/eventos/{id}/confirmar/
POST                  /api/v1/eventos/{id}/entregar/
POST                  /api/v1/eventos/{id}/pagamentos/                  ← cria PagamentoEvento + recalcula sinal_pago
DELETE                /api/v1/eventos/{id}/pagamentos/{pagamento_id}/remover/
GET                   /api/v1/eventos/agenda/

# Notificações WhatsApp
GET  /api/v1/notificacoes/mensagens/
POST /api/v1/notificacoes/mensagens/enviar/
GET  /api/v1/notificacoes/mensagens/status-conexao/

# Catálogo / Fichas / Precificação
GET/POST         /api/v1/fichas/materias-primas/
PATCH            /api/v1/fichas/materias-primas/{id}/
POST             /api/v1/fichas/materias-primas/{id}/atualizar-preco/
GET/POST         /api/v1/fichas/fichas/
GET/PATCH        /api/v1/fichas/fichas/{id}/
GET              /api/v1/fichas/fichas/{id}/resumo/
POST             /api/v1/fichas/fichas/{id}/adicionar-item/
DELETE           /api/v1/fichas/fichas/{id}/remover-item/{item_id}/
GET/PATCH        /api/v1/fichas/parametros/1/
POST             /api/v1/fichas/ajuste-linear/
POST             /api/v1/fichas/desfazer-ajuste/{snapshot_id}/
GET              /api/v1/fichas/snapshots/

# Relatórios
GET /api/v1/relatorios/ifood/                    ← query params: data_inicio, data_fim, agrupamento (dia|mes), formato (json|excel|pdf)

# Dashboard
GET /api/v1/dashboard/resumo/                    ← sem parâmetros; agrega canais (iFood/PDV/Eventos/Anota AI),
                                                     total recebido hoje + comparativo vs ontem, gráfico 7 dias,
                                                     a receber, fila operacional, próximos eventos e ticket médio
```

---

## Como Rodar

```bash
# Backend (ativar venv primeiro)
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Worker iFood (processo separado)
python manage.py ifood_polling

# Aniversários WhatsApp (cron diário — ex: 09:00)
python manage.py lembrar_aniversarios

# Reengajamento WhatsApp (cron diário — ex: 10:00)
python manage.py avisar_sem_compras --dias 30

# Importar planilha de precificação
python manage.py importar_planilha --arquivo PLANILHA_DE_PRECIFICACAO_ARRETADO.xlsx
# flags: --dry-run | --apenas-materias | --sobrescrever

# Frontend
cd arretado-crm/
npm install
npm run dev
```

---

## Deploy VPS (checklist)

```bash
# No WSL — upload de arquivos se necessário
scp arquivo root@2.25.142.171:/var/www/crm_arretado/

# Na VPS
cd /var/www/crm_arretado
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
cd arretado-crm && npm ci && npm run build && cd ..
systemctl restart arretado
```

**Atenção:** `npm run build` grava direto em `arretado-crm/dist/`, que é o `root` servido pelo Nginx (`/etc/nginx/sites-available/arretado`) — o build já é o deploy do frontend, não existe ambiente de teste isolado. Sempre confirmar com o usuário antes de rodar build na VPS.

Infra já configurada em produção (não precisa recriar):
- Nginx: `location /media/ { alias /var/www/crm_arretado/media/; }` (serve uploads de `ImageField`/`FileField`) e `proxy_set_header X-Forwarded-Proto $scheme;` no bloco `/api/`
- Django: `MEDIA_URL`/`MEDIA_ROOT` e `SECURE_PROXY_SSL_HEADER` em `config/settings.py` (para URLs absolutas de imagem saírem com `https://` corretamente atrás do proxy reverso)

---

## O Que NÃO Fazer

- Não escrever diretamente no `PedidoUnificado` em views — ele é alimentado só por signals
- Não criar endpoints fora do padrão `ModelViewSet + CsrfExemptMixin`
- Não usar `localStorage` no frontend (exceto `authApi` que já usa — não expandir)
- Não alterar o `Sidebar.jsx` sem atualizar as rotas em `App.jsx`
- Não implementar nada sem antes verificar se já existe no código (usar `grep` ou leitura direta dos arquivos)
- Não usar Celery — o projeto usa cron + management commands
- Não chamar `zapi_client` diretamente em signals, models ou views — sempre usar `notificacoes/servico.py` (`notificar()` para texto, `notificar_documento()` para PDF), que gravam o `HistoricoMensagem`
- Não instanciar `ParametrosNegocio()` diretamente — sempre usar `ParametrosNegocio.get()`
- Não instanciar `ConfiguracaoWhatsApp()` diretamente — sempre usar `ConfiguracaoWhatsApp.get()`
- A validade padrão dos orçamentos vem de `ConfiguracaoWhatsApp.get().validade_orcamento_dias` — não usar `settings.VALIDADE_ORCAMENTO_DIAS`
- Não fazer FK direta de `fichas` para `pdv` — a ligação entre FichaTecnica e Produto é via `produto_pdv_id` (IntegerField fraco)
- Não instanciar `ConfiguracaoEntrega()` diretamente — sempre usar `ConfiguracaoEntrega.get()`
- Não hardcodar valor de taxa de entrega no código — sempre vem de `TaxaEntregaBairro` ou do `frete_padrao` de `ConfiguracaoEntrega`
- Ao sugerir automaticamente o bairro/taxa de entrega, o bairro do **Local de Evento** (quando selecionado) tem prioridade sobre o bairro do endereço do cliente — nunca inverter essa ordem (ver `FRETE.md`)
- Não instanciar `ConfiguracaoContrato()` diretamente — sempre usar `ConfiguracaoContrato.get()`
- Não criar `ItemContrato` — o PDF do contrato lê os itens direto de `contrato.orcamento.itens`
- Não permitir `gerar-contrato/` em orçamento que não esteja `status == 'aprovado'`, nem sem CPF/RG/nacionalidade/profissão/estado civil preenchidos
- Ao mesclar o PDF do contrato com o timbre (`pdf_contrato.py::_mesclar_timbre`), reler o `PdfReader` do timbre a cada página — reutilizar o mesmo objeto entre iterações faz o `pypdf` duplicar o conteúdo da primeira página em todas (só aparece em PDFs multi-página; `pdf_orcamento.py` nunca bateu nisso por ser sempre 1 página)
- Não criar `ImagemInspiracao` por item de Orçamento — a galeria pertence ao Orçamento inteiro (decisão já confirmada com o usuário)
- Não incluir as imagens de `ImagemInspiracao` no PDF do orçamento nem na mensagem de WhatsApp — é uso interno da equipe, nunca client-facing
- Não duplicar `ImagemInspiracao` para o Evento na conversão — o Evento só **lê** via `orcamento_origem`, nunca copia as imagens
- Não gravar `Evento.sinal_pago` diretamente — sempre criar/remover um `PagamentoEvento` e chamar `evento.recalcular_sinal_pago()`
- Não permitir `PATCH/PUT` em `Orcamento` (nem editar item) quando `status` não for `rascunho` ou `enviado`
- Não somar `Evento.valor_total` nem olhar status de entrega para calcular a receita de Eventos do dia no Dashboard — vem exclusivamente de `PagamentoEvento` pago com `data_pagamento` de hoje
- Não criar nenhum model no app `dashboard/` — é um agregador só-leitura; qualquer novo dado exibido ali deve vir de um app de canal já existente
- **Nunca rodar `npm run build`/`vite build` na VPS sem avisar antes** — o Nginx serve o frontend direto de `arretado-crm/dist/` (`root` no vhost), então qualquer build "de teste" já sobrescreve o que está em produção. Não existe build isolado nesse projeto; tratar todo `build` como deploy real
