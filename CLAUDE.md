# Arretado Doces — CRM Proprietário

> Arquivo lido automaticamente pelo Claude Code em toda sessão.
> Última atualização: junho de 2026.

---

## Visão Geral

CRM proprietário para a **Arretado Doces** — confeitaria em Teresina/PI, Brasil.  
Gerencia clientes, pedidos e múltiplos canais de venda (iFood, PDV próprio, futuramente Anota AI).

- **Backend:** Django 4.2 + DRF · Python
- **Frontend:** React + Vite · CSS Modules
- **Banco:** SQLite (dev) · PostgreSQL (prod)
- **Deploy:** Gunicorn + Nginx · Ubuntu 24 · VPS
- **URL prod:** https://arretado.ortex.solutions

---

## Estrutura de Pastas

```
arretado/                        ← raiz Django
├── config/
│   ├── settings.py              ← INSTALLED_APPS: clientes, ifood, pdv, pedidos, notificacoes
│   ├── urls.py                  ← rotas: /api/v1/, /api/v1/ifood/, /api/v1/pdv/, /api/v1/notificacoes/
│   └── wsgi.py
├── clientes/                    ← Fase 1: CRM de clientes
│   ├── models.py                ← Cliente, Endereço, TagCliente
│   └── views.py                 ← inclui action `historico` (GET /api/v1/clientes/{id}/historico/)
├── ifood/                       ← Fase 2: integração iFood
│   ├── models.py                ← ConfiguracaoIFood, PedidoIFood, ItemPedidoIFood, EventoPollingIFood
│   ├── polling_worker.py
│   └── management/commands/ifood_polling.py
├── pedidos/                     ← Fase 3: espelho unificado (só leitura)
│   ├── models.py                ← PedidoUnificado
│   └── apps.py                  ← registra signals do iFood e PDV no ready()
├── pdv/                         ← Fase 3-ext: PDV próprio
│   ├── models.py                ← CategoriaProduto, Produto, PedidoPDV, ItemPedidoPDV
│   └── signals.py               ← espelha PedidoPDV → PedidoUnificado
├── notificacoes/                ← WhatsApp via Evolution API (self-hosted)
│   ├── models.py                ← HistoricoMensagem
│   └── management/commands/lembrar_aniversarios.py
└── manage.py

arretado-crm/                    ← raiz React
└── src/
    ├── api/
    │   ├── client.js            ← axios base
    │   └── services.js          ← clientesApi, tagsApi, ifoodApi, pdvApi, notificacoesApi, authApi
    ├── pages/
    │   ├── Login.jsx
    │   ├── Dashboard.jsx
    │   ├── Clientes.jsx
    │   ├── ClienteDetail.jsx
    │   ├── Tags.jsx
    │   ├── Usuarios.jsx
    │   ├── IFood.jsx
    │   ├── PDV.jsx
    │   ├── Notificacoes.jsx
    │   └── Vinculacoes.jsx
    ├── components/
    │   ├── layout/
    │   │   ├── AppLayout.jsx
    │   │   └── Sidebar.jsx
    │   ├── ui/                  ← Btn, Modal, Spinner, Avatar, etc.
    │   └── HistoricoPedidos.jsx
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

### Frontend
- **Sem `localStorage`** — estado React + context de autenticação
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
- **`services.js`:** um objeto de API por canal — `clientesApi`, `ifoodApi`, `pdvApi`, `notificacoesApi`
- **Novo canal** = novo objeto no `services.js` seguindo o mesmo padrão

---

## Status das Fases

| Fase | Descrição | Status |
|---|---|---|
| Fase 1 | CRM de Clientes (cadastro, endereços, tags) | ✅ Concluída |
| Fase 2 | Integração iFood (polling, pedidos, ações) | ✅ Concluída |
| Fase 3 | Histórico unificado de pedidos | ✅ Concluída |
| Fase 3-ext-A | PDV Próprio (backend + frontend) | ✅ Concluída · `migrate pdv` pendente em prod |
| Fase 3-ext-B | Anota AI | 🔲 Pendente |
| Fase 4 | Vinculação manual de pedidos a clientes | ✅ Concluída (`Vinculacoes.jsx`) |
| Fase 5 | Dashboard e relatórios | ✅ Concluída (`Dashboard.jsx`) |
| WhatsApp | Notificações via Evolution API | ✅ Concluída (`notificacoes/`) |
| Usuários | Gestão de usuários + RBAC | ✅ Concluída (`Usuarios.jsx` + API real) |

---

## Pendências Ativas

1. **`python manage.py migrate pdv`** — aplicar em produção (app PDV concluído mas migration ainda não rodada em prod)
2. **Anota AI (Fase 3-ext-B)** — criar app `anotaai/` seguindo o padrão de `pdv/`
3. **PDV Hardware (roadmap):**
   - Curto prazo: impressora térmica TCP/IP (Django imprime via socket ESC/POS) + caixa registradora pelo mesmo cabo
   - Médio prazo: NFC-e (nota fiscal — SEFAZ-PI)
   - Longo prazo: TEF integrado

---

## Endpoints Principais

```
# Clientes
GET/POST   /api/v1/clientes/
GET/PUT/PATCH/DELETE /api/v1/clientes/{id}/
GET        /api/v1/clientes/{id}/historico/   ← histórico unificado multi-canal
GET/POST   /api/v1/tags/

# iFood
GET        /api/v1/ifood/pedidos/
POST       /api/v1/ifood/pedidos/{id}/confirmar/
POST       /api/v1/ifood/pedidos/{id}/vincular-cliente/
GET        /api/v1/ifood/config/status/

# PDV
GET/POST   /api/v1/pdv/pedidos/
GET/POST   /api/v1/pdv/produtos/
GET/POST   /api/v1/pdv/categorias/
POST       /api/v1/pdv/pedidos/{id}/confirmar/
POST       /api/v1/pdv/pedidos/{id}/concluir/

# Notificações WhatsApp
GET        /api/v1/notificacoes/mensagens/
POST       /api/v1/notificacoes/mensagens/enviar/
```

---

## Como Rodar

```bash
# Backend
cd arretado/
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Worker iFood (processo separado)
python manage.py ifood_polling

# Aniversários WhatsApp (cron diário)
python manage.py lembrar_aniversarios

# Frontend
cd arretado-crm/
npm install
npm run dev
```

---

## O Que NÃO Fazer

- Não escrever diretamente no `PedidoUnificado` em views — ele é alimentado só por signals
- Não criar endpoints fora do padrão `ModelViewSet + CsrfExemptMixin`
- Não usar `localStorage` no frontend
- Não alterar o `Sidebar.jsx` sem atualizar as rotas em `App.jsx`
- Não implementar nada sem antes verificar se já existe no código (usar `grep` ou leitura direta dos arquivos)
- Não usar Celery — o projeto usa cron + management commands
