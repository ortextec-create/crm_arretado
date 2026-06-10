# Arretado Doces — CRM Proprietário

> Arquivo lido automaticamente pelo Claude Code em toda sessão.
> Última atualização: 09/jun/2026.

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
│   ├── settings.py              ← INSTALLED_APPS: clientes, ifood, pdv, pedidos, eventos, usuarios, notificacoes, fichas
│   ├── urls.py                  ← rotas: /api/v1/, /api/v1/ifood/, /api/v1/pdv/, /api/v1/eventos/, /api/v1/notificacoes/, /api/v1/fichas/
│   └── wsgi.py
├── clientes/                    ← Fase 1: CRM de clientes
│   ├── models.py                ← Cliente, Endereço, TagCliente
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
│   ├── models.py                ← CategoriaProduto, Produto (+ segmento/foto/disponibilidades), PedidoPDV, ItemPedidoPDV
│   └── signals.py               ← espelha PedidoPDV → PedidoUnificado
├── eventos/                     ← Fase 4: gestão de eventos/encomendas + orçamentos
│   ├── models.py                ← Orcamento, ItemOrcamento, Evento, ItemEvento, LocalEvento
│   └── views.py                 ← OrcamentoViewSet (converter-em-evento) + EventoViewSet
├── usuarios/                    ← Gestão de usuários + RBAC
│   └── views.py
├── notificacoes/                ← WhatsApp via Z-API
│   ├── models.py                ← HistoricoMensagem
│   ├── zapi_client.py           ← enviar_texto(), status_conexao() · resolve número canônico via phone-exists · lança ZAPIError
│   ├── views.py                 ← MensagemViewSet (listar, enviar, status-conexao)
│   └── management/commands/lembrar_aniversarios.py
├── fichas/                      ← Catálogo, Fichas Técnicas e Precificação
│   ├── models.py                ← MateriaPrima, FichaTecnica, ItemFichaTecnica, ParametrosNegocio, SnapshotPrecos
│   ├── views.py                 ← MateriaPrimaViewSet, FichaTecnicaViewSet, ParametrosNegocioViewSet,
│   │                               SnapshotPrecosViewSet, AjusteLinearView, DesfazerAjusteView
│   ├── urls.py                  ← router + ajuste-linear/ + desfazer-ajuste/<id>/
│   └── management/commands/importar_planilha.py  ← popula BD a partir do .xlsx
└── manage.py

arretado-crm/                    ← raiz React
└── src/
    ├── api/
    │   ├── client.js            ← axios base
    │   └── services.js          ← clientesApi, tagsApi, ifoodApi, pdvApi, pedidosApi,
    │                               eventosApi, locaisEventoApi, orcamentosApi,
    │                               notificacoesApi, usuariosApi, authApi, fichasApi
    ├── pages/
    │   ├── Login.jsx
    │   ├── Dashboard.jsx
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
    │   ├── Eventos.jsx
    │   ├── Orcamentos.jsx
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
- **Z-API WhatsApp:** configurado via `.env` (`ZAPI_INSTANCE_ID`, `ZAPI_TOKEN`, `ZAPI_CLIENT_TOKEN`). O cliente em `notificacoes/zapi_client.py` resolve o número canônico via `phone-exists` antes de cada envio (trata números BR de 8 e 9 dígitos), lança `ZAPIError` em caso de falha — views capturam e gravam `status='falha'` no `HistoricoMensagem`.
- **fichas.ParametrosNegocio é singleton** — sempre acessado via `ParametrosNegocio.get()`, nunca instanciado diretamente
- **FichaTecnica → pdv.Produto** é uma FK fraca via `produto_pdv_id` (IntegerField, não ForeignKey) — o produto pode existir sem ficha e vice-versa
- **SnapshotPrecos** é gravado automaticamente antes de qualquer `AjusteLinear` com `confirmar=True`

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
| Orçamentos | Orçamentos pré-evento (ORC-0001) + conversão em Evento | ✅ Concluída |
| Fase 5 | Dashboard e relatórios | ✅ Concluída (`Dashboard.jsx`) |
| WhatsApp | Notificações via Z-API | ✅ Concluída (`notificacoes/` + `zapi_client.py`) |
| Usuários | Gestão de usuários + RBAC | ✅ Concluída |
| Catálogo & Precificação | App `fichas/` + 3 telas de frontend | ✅ Concluída · dados importados em prod |

---

## Pendências Ativas

1. **Anota AI (Fase 3-ext-B)** — criar app `anotaai/` seguindo o padrão de `pdv/`
2. **Fichas técnicas incompletas** — 3 ingredientes com custo zero na planilha original (`Cobertura cappucino`, `Folha decorativa`, `Castanha do Pará`, `Ameixa`) e `Brigadeiro Sensacional` sem quantidades
3. **Foto de produtos** — campo `foto` (ImageField) existe no model mas upload ainda não está no frontend (`Catalogo.jsx`)
4. **PDV Hardware (roadmap):**
   - Curto prazo: impressora térmica TCP/IP (Django imprime via socket ESC/POS) + caixa registradora pelo mesmo cabo
   - Médio prazo: NFC-e (nota fiscal — SEFAZ-PI)
   - Longo prazo: TEF integrado
5. **Variáveis de ambiente em prod para WhatsApp (Z-API):**
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

# Orçamentos
GET/POST      /api/v1/eventos/orcamentos/
GET/PATCH     /api/v1/eventos/orcamentos/{id}/
POST          /api/v1/eventos/orcamentos/{id}/enviar/
POST          /api/v1/eventos/orcamentos/{id}/aprovar/
POST          /api/v1/eventos/orcamentos/{id}/recusar/
POST          /api/v1/eventos/orcamentos/{id}/converter-em-evento/
POST          /api/v1/eventos/orcamentos/{id}/itens/
DELETE        /api/v1/eventos/orcamentos/{id}/itens/{item_id}/remover/

# Eventos
GET/POST /api/v1/eventos/
GET/POST /api/v1/eventos/locais/
POST     /api/v1/eventos/{id}/confirmar/
POST     /api/v1/eventos/{id}/entregar/
GET      /api/v1/eventos/agenda/

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

---

## O Que NÃO Fazer

- Não escrever diretamente no `PedidoUnificado` em views — ele é alimentado só por signals
- Não criar endpoints fora do padrão `ModelViewSet + CsrfExemptMixin`
- Não usar `localStorage` no frontend (exceto `authApi` que já usa — não expandir)
- Não alterar o `Sidebar.jsx` sem atualizar as rotas em `App.jsx`
- Não implementar nada sem antes verificar se já existe no código (usar `grep` ou leitura direta dos arquivos)
- Não usar Celery — o projeto usa cron + management commands
- Não chamar `zapi_client.enviar_texto()` diretamente em signals ou models — sempre passar pela view ou pelo management command, que gravam o `HistoricoMensagem`
- Não instanciar `ParametrosNegocio()` diretamente — sempre usar `ParametrosNegocio.get()`
- Não fazer FK direta de `fichas` para `pdv` — a ligação entre FichaTecnica e Produto é via `produto_pdv_id` (IntegerField fraco)
