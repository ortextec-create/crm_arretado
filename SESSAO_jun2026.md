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

---

## Homologação iFood — Correções e Melhorias (17/jun/2026)

### Contexto
Relatório da homologação iFood retornou **40/60 pontos (66,67%)** com dois cenários críticos zerados:
- **Pedido Confirmado (0/10)**: sistema nunca confirmava os pedidos
- **Pedido Despachado Imediato (0/10)**: despacho de pedidos MERCHANT falhava

**Causa raiz**: campos `auto_confirmar` e `auto_despachar` existiam no banco (migrations 0004/0005 já aplicadas) mas estavam `False` (default). Além disso, a lógica de despacho não distinguia pedidos `MERCHANT` de `IFOOD_DELIVERY`.

---

### Alterações de Código

#### `ifood/models.py`
- Adicionado campo `delivery_mode = CharField(max_length=30)` ao `PedidoIFood`
  - Armazena o modo de entrega extraído do payload: `MERCHANT`, `IFOOD_DELIVERY` ou vazio (TAKEOUT/INDOOR)

#### `ifood/polling_worker.py`
- `_criar_pedido`: extrai `delivery_mode` de `detalhe.deliveryMethod.mode` (com fallback em `deliveredBy` e `delivery.deliveredBy`)
- Lógica de despacho automático corrigida:
  - `TAKEOUT` → `ready_to_pickup()`
  - `DELIVERY` + `delivery_mode == 'MERCHANT'` → `dispatch_order()`
  - `DELIVERY` + `IFOOD_DELIVERY` → **sem chamada** (iFood cuida do despacho)
- Bug anterior: chamava `dispatch_order()` para **todo** pedido não-TAKEOUT, inclusive IFOOD_DELIVERY

#### `ifood/serializers.py`
- `delivery_mode` adicionado ao `PedidoIFoodListSerializer` e `PedidoIFoodDetailSerializer`

#### `ifood/ifood_client.py` (alteração anterior desta sessão)
- URLs de cancelamento corrigidas: `v1.0` → `v2.0`
  - `ACCEPT_CANCELLATION_URL`: `/order/v2.0/orders/{id}/cancellation/accept`
  - `DENY_CANCELLATION_URL`:   `/order/v2.0/orders/{id}/cancellation/deny`

#### `arretado-crm/src/pages/IFood.jsx`
- `ConfigModal`: adicionados dois toggles (switches) para `auto_confirmar` e `auto_despachar`
  - `auto_despachar` fica desabilitado (opacity 0.45) quando `auto_confirmar` está desligado
- Novos botões de ação nos cards de pedido:
  - "Marcar como pronto" (status `PREPARATION_STARTED`)
  - "Despachar" (status `READY_TO_PICKUP`, somente não-TAKEOUT)
- Campo "Descrição" adicionado ao modal de cancelamento (exigido pelo iFood)
- Estado `cancelReason` adicionado, passado junto com `cancellationCode`

#### `arretado-crm/src/api/services.js`
- Novos métodos no `ifoodApi`:
  - `statusGeral`, `testarConexao`, `pollingManual`, `ativarPolling`, `pausarPolling`
  - `estatisticas`, `prontoRetirada`, `motivosCancelamento`
  - `vincularCliente`, `criarCliente`, `aceitarNegociacao`, `recusarNegociacao`
- Removidos `statusPolling` e `triggerPolling` (endpoints renomeados)

#### `ifood/views.py`
- Corrigido bug de indentação: action `criar_cliente` estava fora da classe `PedidoIFoodViewSet`
- `EventoPollingViewSet` reposicionado corretamente após o ViewSet de pedidos

---

### Migrations Criadas e Aplicadas

| Migration | Campo | Default |
|---|---|---|
| `0004_configuracaoifood_auto_confirmar` | `auto_confirmar` (BooleanField) | `False` |
| `0005_configuracaoifood_auto_despachar` | `auto_despachar` (BooleanField) | `False` |
| `0006_delivery_mode` | `delivery_mode` (CharField max 30) | `''` |

Todas aplicadas com `python manage.py migrate ifood`.

---

### Deploy em Produção

```bash
# Flags ativados via Django shell
auto_confirmar = True
auto_despachar = True

# Build frontend
cd arretado-crm && npm run build

# Restart
systemctl restart arretado.service          # Gunicorn
systemctl restart arretado-polling.service  # Worker iFood polling
```

**Serviços após deploy:** ambos `active`.

---

### Comportamento Esperado na Próxima Homologação

1. Ao receber evento `PLACED` → worker confirma imediatamente via `POST /order/v1.0/orders/{id}/confirm`
2. Para pedidos `MERCHANT`: após confirmar → `POST /order/v1.0/orders/{id}/dispatch`
3. Para pedidos `IFOOD_DELIVERY`: sem chamada de despacho (iFood gerencia)
4. Para pedidos `TAKEOUT`: após confirmar → `POST /order/v1.0/orders/{id}/readyToPickup`

Os flags podem ser ajustados a qualquer momento via **Página iFood → ⚙ Configuração**.

---

### Arquivos Modificados Nesta Sessão

- `ifood/models.py`
- `ifood/polling_worker.py`
- `ifood/serializers.py`
- `ifood/ifood_client.py`
- `ifood/views.py`
- `ifood/migrations/0004_configuracaoifood_auto_confirmar.py` *(novo)*
- `ifood/migrations/0005_configuracaoifood_auto_despachar.py` *(novo)*
- `ifood/migrations/0006_delivery_mode.py` *(novo)*
- `arretado-crm/src/pages/IFood.jsx`
- `arretado-crm/src/pages/IFood.module.css`
- `arretado-crm/src/api/services.js`
