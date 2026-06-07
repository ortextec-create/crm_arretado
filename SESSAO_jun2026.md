# Sessão de Desenvolvimento — Junho 2026

Resumo de tudo implementado nesta sessão para atualização do projeto no Claude Web.

---

## 1. Correções de Inicialização

- Aplicada migration pendente: `python manage.py migrate notificacoes`
- Variáveis de ambiente carregadas corretamente via `.env` na inicialização local

---

## 2. WhatsApp — Migração de Provedor

### Tentativas anteriores (descartadas)

| Provedor | Motivo do descarte |
|---|---|
| Evolution API (self-hosted) | Instância não conectava na VPS |
| Twilio Sandbox | WABA restrita — não criava templates; destinatários precisavam de opt-in |

### Solução adotada: Z-API

Serviço SaaS brasileiro. Conecta qualquer número WhatsApp via QR code, envia texto livre sem necessidade de aprovação Meta.

**Credenciais configuradas:**
```
ZAPI_INSTANCE_ID=3F44AD8FFA071145A7847A94F00847F6
ZAPI_TOKEN=664FD7CD1788EFA5660A875F
ZAPI_CLIENT_TOKEN=F8af9ded3cdbd44c79851ce92179af411S
```

**Arquivo criado:** `notificacoes/zapi_client.py`
- `enviar_texto(numero, texto)` — resolve número canônico via `phone-exists` antes de enviar (trata números BR 8 e 9 dígitos)
- `status_conexao()` — verifica se o celular está conectado
- Credenciais lidas do banco (`ConfiguracaoWhatsApp`) com fallback para `.env`
- Lança `ZAPIError` em caso de falha

---

## 3. Serviço Central de Notificações

**Arquivo criado:** `notificacoes/servico.py`

```python
notificar(telefone, mensagem, cliente=None, tipo='pedido') -> bool
_fone_pedido(pedido) -> str
```

- Envia via Z-API **e** grava `HistoricoMensagem` automaticamente
- Verifica toggles do banco por tipo (`pedido`, `aniversario`, `reengajamento`)
- Nunca lança exceção — seguro para usar em qualquer fluxo
- Regra: nunca chamar `zapi_client` diretamente em signals ou models

---

## 4. Notificações Automáticas por Movimento de Pedido

Cada mudança de status dispara WhatsApp para o cliente (número vinculado ou snapshot do pedido).

### PDV (`pdv/views.py`)

| Ação | Mensagem |
|---|---|
| Confirmar | ✅ Pedido #X confirmado! |
| Iniciar preparo | 👨‍🍳 Entrou em preparo! |
| Marcar pronto | 🎉 Pronto para retirada! |
| Concluir | 💚 Obrigado pela preferência! |
| Cancelar | ❌ Pedido cancelado. |

### iFood (`ifood/views.py`)

| Ação | Mensagem |
|---|---|
| Confirmar | ✅ Pedido iFood confirmado! |
| Despachar | 🛵 Saiu para entrega! |
| Pronto retirada | 🎉 Pronto para retirada! |
| Cancelar | ❌ Pedido cancelado. |

### Eventos (`eventos/views.py`)

| Ação | Mensagem |
|---|---|
| Confirmar | ✅ Encomenda #X confirmada para DD/MM/YYYY! |
| Iniciar produção | 👨‍🍳 Entrou em produção! |
| Marcar pronto | 🎉 Pronta, aguardando entrega! |
| Entregar | 💚 Entregue, obrigado! |
| Cancelar | ❌ Encomenda cancelada. |

**Helper em cada views.py:**
```python
from notificacoes.servico import notificar, _fone_pedido

def _notificar_pdv(pedido, mensagem):
    notificar(_fone_pedido(pedido), mensagem, cliente=pedido.cliente, tipo='pedido')
```

---

## 5. Notificações Programadas (Cron)

### `lembrar_aniversarios` (atualizado)

- Migrado de Evolution API para Z-API via `servico.notificar`
- Usa template e toggle (`aniversario_ativo`) da `ConfiguracaoWhatsApp`
- Ignora clientes sem telefone cadastrado

### `avisar_sem_compras` (novo)

- Arquivo: `notificacoes/management/commands/avisar_sem_compras.py`
- Busca clientes com pedido histórico mas sem compra nos últimos N dias
- N configurável pela tela (padrão: 30 dias)
- Anti-spam: não reenvia para quem recebeu nos últimos 7 dias
- Usa `PedidoUnificado` para calcular última compra
- Usa template e toggle (`reengajamento_ativo`) da `ConfiguracaoWhatsApp`

**Cron sugerido:**
```
0  9 * * * cd /var/www/arretado && venv/bin/python manage.py lembrar_aniversarios
0 10 * * * cd /var/www/arretado && venv/bin/python manage.py avisar_sem_compras
```

---

## 6. ConfiguracaoWhatsApp — Modelo Singleton

**Arquivo:** `notificacoes/models.py`  
**Migration:** `0003_add_configuracao_whatsapp.py`

| Campo | Tipo | Padrão |
|---|---|---|
| `zapi_instance_id` | CharField | — |
| `zapi_token` | CharField | — |
| `zapi_client_token` | CharField | — |
| `notificacoes_pedido_ativo` | BooleanField | True |
| `aniversario_ativo` | BooleanField | True |
| `reengajamento_ativo` | BooleanField | True |
| `dias_sem_compra` | PositiveIntegerField | 30 |
| `mensagem_aniversario` | TextField | template padrão |
| `mensagem_reengajamento` | TextField | template padrão |

Uso: `ConfiguracaoWhatsApp.get()` — cria com defaults se não existir.

**Endpoints:**
```
GET   /api/v1/notificacoes/configuracao/         → retorna config
PATCH /api/v1/notificacoes/configuracao/         → atualiza parcialmente
POST  /api/v1/notificacoes/configuracao/testar/  → testa conexão Z-API
```

---

## 7. Tela de Configurações (Frontend)

**Arquivos criados:**
- `arretado-crm/src/pages/Configuracoes.jsx`
- `arretado-crm/src/pages/Configuracoes.module.css`

**Rota:** `/configuracoes` (já existia no Sidebar em Administração)

**Seções da tela:**

1. **Credenciais Z-API** — campos Instance ID, Token, Client-Token + botão "Testar conexão" com badge de status (Conectado / Desconectado / Erro)
2. **Notificações de Pedidos** — toggle on/off
3. **Parabéns de Aniversário** — toggle + editor de mensagem (suporta `{nome}`)
4. **Reengajamento de Clientes** — toggle + campo de dias + editor de mensagem

Botão "Salvar tudo" persiste todas as seções de uma vez via `PATCH`.

**`services.js` — adicionado:**
```js
export const configWhatsappApi = {
  get:    ()     => api.get('/notificacoes/configuracao/'),
  update: (data) => api.patch('/notificacoes/configuracao/', data),
  testar: ()     => api.post('/notificacoes/configuracao/testar/'),
}
```

---

## 8. Model `HistoricoMensagem` — Novos Tipos

**Migration:** `0002_add_tipos_mensagem.py`

Tipos adicionados: `pedido`, `reengajamento`  
Tipos existentes mantidos: `manual`, `aniversario`, `lembrete`

---

## 9. Dependências Adicionadas

```
twilio==9.10.9   # instalado mas não usado (tentativa anterior)
```

Z-API usa apenas `requests` (já era dependência).

---

## 10. Pendências de Produção

1. `python manage.py migrate notificacoes` — aplicar migrations 0002 e 0003
2. Configurar credenciais Z-API pela tela `/configuracoes` (não mais pelo `.env`)
3. Configurar cron para `lembrar_aniversarios` e `avisar_sem_compras`
4. Variáveis `.env` do Twilio podem ser removidas futuramente (não usadas)

---

## Arquivos Modificados / Criados

### Novos
- `notificacoes/zapi_client.py`
- `notificacoes/servico.py`
- `notificacoes/management/commands/avisar_sem_compras.py`
- `notificacoes/migrations/0002_add_tipos_mensagem.py`
- `notificacoes/migrations/0003_add_configuracao_whatsapp.py`
- `arretado-crm/src/pages/Configuracoes.jsx`
- `arretado-crm/src/pages/Configuracoes.module.css`

### Modificados
- `notificacoes/models.py` — `ConfiguracaoWhatsApp` + novos tipos
- `notificacoes/views.py` — `ConfiguracaoWhatsAppViewSet` + migração para Z-API
- `notificacoes/serializers.py` — `ConfiguracaoWhatsAppSerializer`
- `notificacoes/urls.py` — rotas de configuração
- `notificacoes/management/commands/lembrar_aniversarios.py` — Z-API + banco
- `pdv/views.py` — notificações por status
- `ifood/views.py` — notificações por status
- `eventos/views.py` — notificações por status
- `config/settings.py` — vars Twilio + Z-API
- `arretado-crm/src/App.jsx` — rota `/configuracoes`
- `arretado-crm/src/api/services.js` — `configWhatsappApi`
- `requirements.txt` — twilio adicionado
