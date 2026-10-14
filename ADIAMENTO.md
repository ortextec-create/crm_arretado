# ADIAMENTO.md — Remarcação e Adiamento de Eventos

> Spec para implementação via Claude Code. Segue os padrões obrigatórios de `CLAUDE.md`.
> Mockup: **pendente** — validar as telas (modais Remarcar / Adiar / Retomar / Encerrar adiamento e o histórico de datas) antes da Fase 5.
> Requisito de revenda: **nenhum valor da Arretado hardcoded**. Prazos e faixas em `ConfiguracaoContrato` / `ConfiguracaoAlertaEvento`; textos de WhatsApp sem nome de empresa.
> As regras contratuais desta spec (prazo máximo, multa, devolução) são decisão de negócio e devem ser revisadas por advogado antes de entrar no PDF do contrato.

---

## Visão Geral

Dois casos que hoje o sistema não representa:

1. **Remarcação** — o evento muda de data, e a nova data já é conhecida. Vira uma **ação com histórico** (`remarcar/`), nunca um PATCH em `data_evento`. O status é mantido.
2. **Adiamento sem data** — o evento sai da operação sem nova data. Vira o **status `adiado`**, que preserva a última data prevista e tem prazo máximo, retomada controlada e encerramento com acerto financeiro.

As duas compartilham o log imutável `RemarcacaoEvento`. O ciclo do adiamento vive em `AdiamentoEvento`.

Peças:

| Peça | Onde | Papel |
|---|---|---|
| `RemarcacaoEvento` | `eventos/models.py` | log imutável de toda mudança de data/hora |
| `AdiamentoEvento` | `eventos/models.py` | um registro por adiamento: motivo, limite, faixa de multa congelada, desfecho |
| Status `adiado` | `Evento.STATUS_CHOICES` | tira o evento da operação sem perder a data |
| `eventos/adiamento.py` | novo módulo | funções puras: faixa de multa, cálculo do acerto, dias úteis |
| `alertar_adiamentos` | management command | avisa a equipe sobre follow-up e limite |
| Aditivo de data | `AditivoContrato` (extensão) | documenta a nova data no contrato |

### Decisões registradas

| Decisão | Valor |
|---|---|
| Mudança de data | só via `remarcar/` (ou `retomar/`); PATCH com `data_evento`/`hora_evento` **diferente** do atual → 400 |
| Status na remarcação | mantido. Em `em_producao`/`pronto` exige `confirmar_producao=true` e permite `voltar_para_confirmado` |
| Data do evento adiado | mantida (última data prevista); `data_evento` continua **não nula** |
| Status de origem do `adiar` | `confirmado`, `em_producao`, `pronto` |
| Status ao retomar | **sempre `confirmado`** — produção feita antes do adiamento não é reaproveitada (pendente de confirmação do Fobs) |
| Prazo máximo | nova data do evento até `data_original + prazo_maximo_adiamento_dias` (default **180**) |
| Prorrogação do prazo | até `prorrogacoes_adiamento_max` vezes (default **1**), cada uma por mais `prazo_maximo_adiamento_dias` |
| Limite vencido | **nada automático**: o cron alerta a equipe; acerto só por ação humana (`encerrar/`) |
| Sinal ao retomar | preservado integralmente, abate da nova data — nenhum lançamento |
| Sinal ao encerrar (rescisão) | multa da Cláusula 11ª pela faixa **congelada no dia do adiamento**, limitada ao total pago; o restante vira `ContaPagar` de devolução |
| Faixa da multa | antecedência = `data_original − data do adiamento`; produção iniciada → faixa "menos de 7 dias" |
| Sinal ao encerrar (força maior) | sem multa (Cláusula 14ª); retenção = custos informados manualmente |
| Evento sem contrato ou contrato sem a cláusula nova | sem cálculo automático; valores informados manualmente (distrato, Cláusula 13ª) |
| Crédito do cliente para uso futuro | **fora de escopo** (exige ledger de crédito próprio) |
| Cobrança automática | `adiado` **não** entra em `cobranca.regua.STATUS_ELEGIVEIS` — a régua para sozinha |
| Aditivo | não é gerado automaticamente; a remarcação devolve `aditivo_sugerido` e o front oferece |

---

## Fase 0 — Pré-requisitos

### 0.1 Ações novas em `auditoria.LogAuditoria.ACAO_CHOICES`

```
evento_remarcado
evento_adiado
evento_retomado
adiamento_prorrogado
adiamento_encerrado
```

Migration em `auditoria/` + rótulos em `arretado-crm/src/utils/auditoriaResumo.js` (`ACAO_LABEL`/`ACAO_COR`). As mudanças de status continuam logadas também por `log_mudanca_status()`.

### 0.2 `ContaPagar.ORIGEM_CHOICES`

Acrescentar `('devolucao_evento', 'Devolução de evento')`. `max_length=12` **não comporta** (16 caracteres) → `AlterField` para `max_length=20`.

### 0.3 `AlertaEventoEnviado` — tipos novos

`adiamento_contato`, `adiamento_limite`, `adiamento_vencido` (até 17 caracteres — conferir `max_length` do campo `tipo`). São alertas **da equipe**, então reaproveitar `AlertaEventoEnviado` é correto (diferente da cobrança, que fala com o cliente).

### 0.4 Conferir antes de começar

- `PedidoUnificado.STATUS_CHOICES`: escolher o mapeamento de `adiado` em `EVENTO_STATUS_MAP`. Se não houver status adequado, usar `'pendente'` e confirmar que Dashboard/Relatórios não somam `pendente` de Eventos como receita (receita de Eventos vem de `PagamentoEvento` — regra já documentada).
- Todos os pontos que filtram `Evento` por status (ver "Exclusões"). Rodar `grep -rn "status__in\|exclude(status" eventos/ dashboard/ relatorios/ cobranca/` e listar no PR.

---

## Models (`eventos/models.py`)

### Evento — alterações

| Mudança | Detalhe |
|---|---|
| `STATUS_CHOICES` | acrescentar `('adiado', 'Adiado')` (entre `pronto` e `entregue` na lista; não entra no stepper) |
| `pode_remarcar` | `status in ('orcamento', 'confirmado', 'em_producao', 'pronto')` |
| `pode_adiar` | `status in ('confirmado', 'em_producao', 'pronto')` |
| `pode_retomar` | `status == 'adiado'` |
| `pode_cancelar` | passa a excluir `adiado` — sair de `adiado` para `cancelado` só via `adiamento/encerrar/` |
| `adiamento_vigente` | property: `self.adiamentos.filter(encerrado_em__isnull=True).first()` |

Nenhum campo novo em `Evento`. Tudo do adiamento vive em `AdiamentoEvento`.

### RemarcacaoEvento (log imutável)

| Campo | Tipo | Notas |
|---|---|---|
| evento | FK `Evento`, PROTECT, related_name=`remarcacoes` | |
| origem | choices `remarcacao` / `retomada` | `retomada` quando vem de `retomar/` |
| adiamento | FK `AdiamentoEvento`, null, PROTECT | preenchido quando `origem='retomada'` |
| data_anterior / hora_anterior | DateField / TimeField null | snapshot |
| data_nova / hora_nova | DateField / TimeField null | |
| status_anterior / status_novo | CharField(20) | snapshot |
| motivo | CharField(300) | obrigatório |
| solicitado_por | choices `cliente` / `empresa` | |
| criado_por | FK `usuarios.Usuario`, null, SET_NULL | |
| criado_por_nome | CharField(150) | snapshot |
| criado_em | auto_now_add | |

Sem PATCH/PUT/DELETE. `ordering = ['-criado_em']`.

### AdiamentoEvento

| Campo | Tipo | Notas |
|---|---|---|
| evento | FK `Evento`, PROTECT, related_name=`adiamentos` | |
| adiado_em | DateField | `timezone.localdate()` na criação |
| data_original | DateField | snapshot de `evento.data_evento` no momento |
| status_antes | CharField(20) | snapshot |
| motivo | CharField(300) | obrigatório |
| solicitado_por | choices `cliente` / `empresa` | |
| limite | DateField | `data_original + prazo_maximo_adiamento_dias` (snapshot da config — mudar a config depois não altera adiamentos existentes) |
| prorrogacoes | PositiveSmallIntegerField, default 0 | |
| retomar_contato_em | DateField, null | follow-up da equipe; default `hoje + dias_followup_adiamento` |
| antecedencia_dias | IntegerField | snapshot: `(data_original - adiado_em).days` |
| producao_iniciada | BooleanField | snapshot: `status_antes in ('em_producao', 'pronto')` |
| multa_pct | DecimalField(5,2), null | snapshot da faixa no dia do adiamento; `null` quando não há contrato com `possui_clausula_adiamento` |
| encerrado_em | DateTimeField, null | |
| desfecho | choices `retomado` / `rescisao` / `forca_maior` / `acordo_manual`, blank | |
| valor_pago_no_encerramento | DecimalField(10,2), null | snapshot |
| valor_multa | DecimalField(10,2), null | valor final aplicado |
| valor_multa_sugerido | DecimalField(10,2), null | valor calculado pelo sistema (auditoria compara os dois) |
| valor_retido_producao | DecimalField(10,2), null | Parágrafo 2º da Cl. 11ª / Cl. 14ª |
| valor_devolucao | DecimalField(10,2), null | |
| conta_pagar | OneToOneField `financeiro.ContaPagar`, null, PROTECT | devolução gerada |
| observacao_encerramento | TextField, blank | |
| criado_por / criado_por_nome, encerrado_por / encerrado_por_nome | FK SET_NULL + snapshot | |
| criado_em | auto_now_add | |

- **Vigente** (derivado): `encerrado_em IS NULL`. **Uma vigente por evento**: `UniqueConstraint(fields=['evento'], condition=Q(encerrado_em__isnull=True))` + `.exists()` explícito antes de criar.
- Sem DELETE. Campos de encerramento só são gravados pelas actions `retomar/` e `encerrar/`.
- `limite` só muda via `prorrogar/` (auditado).

### Configurações — campos novos

`ConfiguracaoContrato` (regras contratuais, usadas no PDF):

| Campo | Tipo | Default |
|---|---|---|
| prazo_maximo_adiamento_dias | PositiveIntegerField | 180 |
| prorrogacoes_adiamento_max | PositiveSmallIntegerField | 1 |
| dias_followup_adiamento | PositiveIntegerField | 30 |

`ConfiguracaoAlertaEvento` (alertas da equipe):

| Campo | Tipo | Default |
|---|---|---|
| ativo_adiamento | BooleanField | True |
| dias_antes_limite_adiamento | PositiveIntegerField | 15 |
| repetir_adiamento_dias | PositiveIntegerField | 7 |

Expor nos serializers existentes (`ConfiguracaoContratoSerializer`, `ConfiguracaoAlertaEventoSerializer`) — auditoria já coberta por `config_contrato_alterada` / `config_alerta_evento_alterada`.

### Contrato — flag da cláusula

| Campo | Tipo | Default | Notas |
|---|---|---|---|
| possui_clausula_adiamento | BooleanField | False | migration deixa `False` nos contratos existentes; `gerar-contrato/` grava `True` nos novos |

Sem a flag, o sistema não calcula multa no encerramento (o cliente não assinou essa regra).

### AditivoContrato — extensão para data

| Campo | Tipo | Notas |
|---|---|---|
| data_evento_anterior / hora_evento_anterior | DateField null / TimeField null | referência antes deste aditivo |
| data_evento_nova / hora_evento_nova | DateField null / TimeField null | `null` = aditivo só de valor |
| data_quitacao_nova | DateField, null | `data_evento_nova - cfg.prazo_quitacao_dias` |

Aditivos antigos ficam com esses campos nulos (só valor), sem migração de dados.

---

## Regras puras (`eventos/adiamento.py`)

Funções sem efeito colateral, recebem `hoje`/`cfg` como argumento:

- `faixa_multa_pct(antecedencia_dias, producao_iniciada, cfg) -> Decimal`
  - `producao_iniciada` ou `antecedencia_dias < 7` → `cfg.multa_rescisao_abaixo_7_dias_pct`
  - `< 30` → `multa_rescisao_abaixo_30_dias_pct`
  - `<= 60` → `multa_rescisao_30_60_dias_pct`
  - `> 60` → `multa_rescisao_acima_60_dias_pct`
- `calcular_acerto(valor_pago, valor_contrato, multa_pct, valor_retido_producao, desfecho) -> dict`
  - `rescisao`: `multa = min(valor_contrato * multa_pct / 100, valor_pago)`; `devolucao = max(valor_pago - multa - retido, 0)`
  - `forca_maior`: `multa = 0`; `devolucao = max(valor_pago - retido, 0)`
  - `acordo_manual`: não calcula — devolve os valores informados
  - Quantizar em 2 casas, `ROUND_HALF_UP`.
- `somar_dias_uteis(data, n) -> date` — pula sábado e domingo (feriados fora de escopo; documentar).
- `data_referencia_contrato(evento) -> (date, time)` — data do último `AditivoContrato` com `data_evento_nova`, senão `Contrato.data_evento`. Mesmo papel de `_valor_referencia_contrato()` para valor.

`valor_pago` = soma de `PagamentoEvento` com `status='pago'` (= `evento.sinal_pago`, que já é derivado). `valor_contrato` = `_valor_referencia_contrato()`.

---

## Actions (`EventoViewSet`)

Todas exigem login (padrão de `get_permissions()`), rodam em `transaction.atomic()` e terminam com `log_mudanca_status()` quando o status muda.

```
POST /api/v1/eventos/{id}/remarcar/
     body {data_evento, hora_evento?, motivo, solicitado_por,
           confirmar_producao?, voltar_para_confirmado?}
     → 400 se !pode_remarcar · data no passado · data igual à atual (data e hora)
     → 400 `producao_iniciada` se status em em_producao/pronto e confirmar_producao != true
     → cria RemarcacaoEvento(origem='remarcacao'), atualiza data/hora (update_fields),
       status → 'confirmado' se voltar_para_confirmado
     → audita evento_remarcado · notifica cliente
     → resposta: EventoDetail + {aditivo_sugerido: bool}

POST /api/v1/eventos/{id}/adiar/
     body {motivo, solicitado_por, retomar_contato_em?}
     → 400 se !pode_adiar ou já existe adiamento vigente
     → cria AdiamentoEvento (snapshots: data_original, status_antes, limite, antecedencia_dias,
       producao_iniciada, multa_pct se contrato com possui_clausula_adiamento)
     → status → 'adiado' · audita evento_adiado · notifica cliente

POST /api/v1/eventos/{id}/retomar/
     body {data_evento, hora_evento?, motivo?}
     → 400 se !pode_retomar · data no passado
     → 400 `fora_do_prazo` se data_evento > adiamento.limite (front oferece prorrogar)
     → RemarcacaoEvento(origem='retomada', adiamento=vigente)
     → adiamento: encerrado_em, desfecho='retomado'
     → status → 'confirmado' · audita evento_retomado · notifica cliente
     → resposta: EventoDetail + {aditivo_sugerido: bool}

POST /api/v1/eventos/{id}/adiamento/prorrogar/
     body {motivo}
     → 400 se não há vigente · prorrogacoes >= cfg.prorrogacoes_adiamento_max
     → limite += prazo_maximo_adiamento_dias · prorrogacoes += 1 · audita adiamento_prorrogado

POST /api/v1/eventos/{id}/adiamento/contato/
     body {retomar_contato_em, observacao?}
     → atualiza o follow-up (data >= hoje) · audita registro_atualizado

GET  /api/v1/eventos/{id}/adiamento/simular-encerramento/?desfecho=rescisao&retido=0
     → AllowAny, sem efeito colateral · devolve o cálculo de calcular_acerto + vencimento da devolução

POST /api/v1/eventos/{id}/adiamento/encerrar/
     body {desfecho: rescisao|forca_maior|acordo_manual,
           valor_multa?, valor_retido_producao?, valor_devolucao?, observacao}
     → 400 se não há vigente
     → 400 `sem_clausula` se desfecho='rescisao' e multa_pct is null (forçar acordo_manual)
     → grava sugerido (calcular_acerto) e final (payload, ou o sugerido se omitido)
     → 400 se valor_multa + valor_retido_producao + valor_devolucao != valor_pago
     → valor_devolucao > 0 → ContaPagar(origem='devolucao_evento', empresa=Empresa.get_padrao(),
       descricao='Devolução — {numero} ({cliente})', valor=valor_devolucao,
       data_emissao=hoje, data_vencimento=somar_dias_uteis(hoje, cfg.prazo_devolucao_dias),
       categoria=None)
     → status → 'cancelado' · adiamento encerrado · audita adiamento_encerrado
       (detalhes: sugerido × final) · notifica cliente
```

### Bloqueio de PATCH de data

`EventoDetailSerializer.validate()`: se `data_evento` ou `hora_evento` vierem no payload **com valor diferente** do atual → 400 `{"data_evento": ["Use Remarcar para mudar a data do evento."]}`. Valor igual passa (o formulário de edição pode reenviar o objeto inteiro).

### Lançamentos financeiros

- Retomada: nenhum. O sinal continua em `PagamentoEvento`.
- Encerramento: **nenhum `MovimentoFinanceiro` novo**. A parte retida já entrou como receita quando o sinal foi pago. A devolução sai do caixa quando a `ContaPagar` receber baixa pelo fluxo normal (`MovimentoFinanceiro.registrar()`).

### Notificações ao cliente (`_notificar_evento`)

Textos como constantes no topo de `views.py`, sem nome de empresa:

- Remarcado / retomado: `📅 Sua encomenda #{numero} foi remarcada para {data}{hora}. Qualquer dúvida, estamos por aqui!`
- Adiado: `⏸️ Sua encomenda #{numero} foi adiada. Assim que tiver a nova data, é só nos avisar.`
- Encerrado: reaproveita o texto de cancelamento existente.

---

## Exclusões de `adiado`

| Onde | Mudança |
|---|---|
| `agenda/` | `.exclude(status__in=['cancelado', 'adiado'])` |
| `estatisticas/` → `eventos_mes` | excluir `adiado` |
| `estatisticas/` → `por_status` | **manter** `adiado` (KPI "Adiados") — remover o filtro `data_evento__gte=hoje` só para essa chave |
| `alertar_eventos` (pagamento e entrega) | `.exclude(status__in=['cancelado', 'entregue', 'adiado'])` |
| Resumo de cozinha / produção | excluir `adiado` |
| `adicionar_item` e edição de itens | já bloqueado (só `orcamento`/`confirmado`) — manter |
| `gerar-aditivo/` | rejeitar `adiado` (`evento_adiado`) — aditivo de data sai na retomada |
| `cobranca.regua.STATUS_ELEGIVEIS` | **não alterar** — `adiado` fica fora por não estar na lista |
| `EVENTO_STATUS_MAP` | acrescentar `adiado` (ver 0.4) |

Retomada com nova data: a régua de cobrança recomeça sozinha, porque a chave `data_evento_referencia` muda.

---

## Contrato e aditivo

### Cláusula nova no PDF (`pdf_contrato.py`)

Só quando `contrato.possui_clausula_adiamento`. Entra como **Parágrafo 3º da Cláusula 11ª** (não renumera as cláusulas seguintes). Texto proposto, montado com valores do singleton:

> Parágrafo 3º: A CONTRATANTE poderá solicitar o adiamento do evento, por escrito, sem incidência da multa desta cláusula, desde que a nova data seja realizada em até {prazo_maximo_adiamento_dias} dias após a data originalmente contratada, sujeita à disponibilidade do CONTRATADO e formalizada por termo aditivo. Não sendo realizada nova data dentro desse prazo, o adiamento será considerado rescisão unilateral por iniciativa da CONTRATANTE, aplicando-se a multa desta cláusula conforme a antecedência entre a comunicação do adiamento e a data originalmente contratada, observados os Parágrafos 1º e 2º.

**Revisar com advogado antes da Fase 3.**

### Aditivo de data

- `gerar-aditivo/` passa a aceitar mudança de **data e/ou valor**. `sem_alteracao` só quando valor **e** data forem iguais às referências (`_valor_referencia_contrato()` e `data_referencia_contrato()`).
- Grava `data_evento_anterior/nova`, `hora_*`, `data_quitacao_nova` quando a data mudou.
- `pdf_aditivo.py`: Cláusula 1ª muda conforme o que mudou ("alteração da data do evento", "alteração de itens/quantitativos" ou ambos); nova cláusula "Da nova data" com data, hora e nova data de quitação. Sempre do snapshot do aditivo.
- `aditivo_disponivel` (serializer) passa a considerar a divergência de data.
- Novo campo no serializer: `contrato_divergente` (bool) + `contrato_divergencia: ['data'|'valor']`.

---

## Management Command

### `alertar_adiamentos` (diário — 08:45)

```
python manage.py alertar_adiamentos [--dry-run]
```

Para a equipe (`TelefoneAlertaEvento` ativos), via `notificar()`. Sai se `ConfiguracaoAlertaEvento.ativo_adiamento=False` ou sem telefones. Para cada `AdiamentoEvento` vigente:

| Tipo (`AlertaEventoEnviado`) | Quando | Mensagem |
|---|---|---|
| `adiamento_contato` | `retomar_contato_em <= hoje` | `⏸️ Follow-up de evento adiado — {numero} ({nome}) · adiado em {adiado_em} · limite {limite}` |
| `adiamento_limite` | `0 <= limite - hoje <= dias_antes_limite_adiamento` | `⚠️ Evento adiado chegando ao limite — {numero} ({nome}) · limite {limite} ({n} dias)` |
| `adiamento_vencido` | `limite < hoje` | `🔴 Limite de adiamento vencido — {numero} ({nome}) · decidir: prorrogar ou encerrar` |

Repetição por `_deve_enviar(evento, tipo, repetir_adiamento_dias)` (mesma mecânica de `alertar_eventos`). Um evento gera no máximo **um** alerta por dia — o mais grave (vencido > limite > contato). Cada evento em `try/except` próprio.

Não envia nada ao cliente. Não encerra nada.

---

## Serializers

- `EventoDetailSerializer`: `pode_remarcar`, `pode_adiar`, `pode_retomar`, `adiamento_vigente` (com `limite`, `dias_para_limite`, `prorrogacoes_restantes`, `multa_pct`, `retomar_contato_em`), `remarcacoes` (histórico), `data_original` (data do primeiro `RemarcacaoEvento`, senão `data_evento`), `contrato_divergente`.
- `EventoListSerializer`: `adiado_limite` (data) para a coluna/badge.
- `RemarcacaoEventoSerializer` e `AdiamentoEventoSerializer` só leitura.

---

## Frontend

- **Modal do evento (`Eventos.jsx`)** — `ACOES`: Remarcar (`ti-calendar-event`), Adiar (`ti-player-pause`), Retomar (`ti-player-play`), Encerrar adiamento (`ti-ban`, `variant: 'danger'`). Cancelar some quando `adiado`.
- **Status `adiado`**: badge no lugar do stepper (mesmo tratamento de `cancelado`): "Adiado desde {adiado_em} · limite {limite}" + aviso quando vencido.
- **Seção "Histórico de datas"**: `remarcacoes` + adiamentos, com data original destacada ("Remarcado 2x · data original 12/out").
- **Banner `contrato_divergente`**: "Contrato com data desatualizada" + botão Emitir aditivo.
- **Modal Remarcar**: data, hora, motivo, solicitado por; em `em_producao`/`pronto`, aviso de produção perecível + checkbox de confirmação + opção "voltar para Confirmado". Sucesso com `aditivo_sugerido` → oferece Emitir aditivo.
- **Modal Adiar**: motivo, solicitado por, data de follow-up (default da config); mostra o limite e, havendo cláusula, a faixa de multa que fica congelada.
- **Modal Retomar**: nova data/hora; `fora_do_prazo` → oferece Prorrogar.
- **Modal Encerrar adiamento**: desfecho em rádio; quadro do acerto vindo de `simular-encerramento/` (total pago, multa sugerida e %, retido produção, devolução, vencimento); valores editáveis com aviso quando diferem do sugerido; observação obrigatória. Sem `window.confirm()`.
- **Lista de eventos**: filtro/aba "Adiados" ordenada por `limite`.
- **Configurações**: campos novos nas seções Contrato e Alertas de Evento.
- `eventosApi`: `remarcar`, `adiar`, `retomar`, `prorrogarAdiamento`, `contatoAdiamento`, `simularEncerramento`, `encerrarAdiamento`.
- Cálculo do acerto **nunca** no frontend — sempre `simular-encerramento/`.

---

## Fases de Implementação

| Fase | Conteúdo | Critério de pronto |
|---|---|---|
| 0 | Ações de auditoria + rótulos, `ContaPagar.origem` (+ `max_length`), tipos de `AlertaEventoEnviado`, decisão do `EVENTO_STATUS_MAP` | migrations limpas; comportamento inalterado |
| 1 | Status `adiado`, `RemarcacaoEvento`, `AdiamentoEvento`, campos de config, `Contrato.possui_clausula_adiamento`, `adiamento.py`, bloqueio de PATCH de data | testes: faixas da multa nos 4 limites (6/7, 29/30, 60/61 dias) e produção iniciada; `calcular_acerto` com multa > pago, força maior, retido > pago; `somar_dias_uteis` atravessando fim de semana; PATCH com data diferente → 400, com data igual → 200 |
| 2 | Actions + exclusões + notificações | testes: remarcar cria log e mantém status; remarcar em `pronto` sem confirmação → 400; adiar 2x → 400; retomar volta a `confirmado` e encerra adiamento; retomar após limite → `fora_do_prazo`; prorrogar além do máximo → 400; encerrar rescisão gera `ContaPagar` com vencimento em dias úteis; soma ≠ pago → 400; `sem_clausula` → 400; `cancelar` em `adiado` → 400; agenda/`alertar_eventos` ignoram `adiado`; régua de cobrança ignora `adiado` e recomeça na retomada |
| 3 | Cláusula no PDF do contrato + aditivo de data | testes: contrato antigo sem o parágrafo, novo com; aditivo só de data, só de valor e ambos; `sem_alteracao` com data e valor iguais; `contrato_divergente` |
| 4 | `alertar_adiamentos` | testes: um alerta por dia por evento (o mais grave); repetição respeita `repetir_adiamento_dias`; desligado não envia |
| 5 | Frontend (após mockup aprovado) | modais, badge, histórico, filtro, configurações |
| 6 | Testes finais + `CLAUDE.md` (estrutura, endpoints, status, cron, "O Que NÃO Fazer") | suite verde; CLAUDE.md coerente |

---

## O Que NÃO Fazer

- **Não** mudar `data_evento`/`hora_evento` por PATCH — sempre `remarcar/` ou `retomar/`.
- **Não** tornar `data_evento` nulo.
- **Não** apagar nem editar `RemarcacaoEvento`; nem apagar `AdiamentoEvento`.
- **Não** recalcular `multa_pct`, `limite`, `antecedencia_dias` de um adiamento existente a partir da config atual — são snapshot.
- **Não** encerrar adiamento automaticamente no cron, nem mandar mensagem ao cliente sobre o limite.
- **Não** permitir `cancelar/` em evento `adiado` — o acerto financeiro tem que passar por `encerrar/`.
- **Não** calcular multa para contrato sem `possui_clausula_adiamento` nem para evento sem contrato.
- **Não** criar `MovimentoFinanceiro` no encerramento — a devolução sai pela baixa da `ContaPagar`.
- **Não** gravar `ContaPagar.status`/`valor_pago` direto — derivados.
- **Não** acrescentar `adiado` em `cobranca.regua.STATUS_ELEGIVEIS`.
- **Não** gerar aditivo automaticamente na remarcação.
- **Não** reler data do Evento ao vivo para reimprimir aditivo — snapshot.
- **Não** fazer o cálculo do acerto no frontend.
- **Não** hardcodar prazos, percentuais ou nome da empresa — config e variáveis.
- **Não** usar Celery — cron + management command.

---

## Fora de Escopo

- Crédito do cliente reutilizável em outro evento/orçamento.
- Taxa de remarcação.
- Feriados no cálculo de dias úteis.
- Termo de distrato em PDF (Cláusula 13ª).
- Reserva de capacidade/agenda por dia e conflito de datas na remarcação.
- Mensagem automática ao cliente perto do limite do adiamento.

---

## Setup Manual (pós-implementação)

1. Deploy com `migrate` → reiniciar **os dois** serviços: `systemctl restart arretado arretado-polling`.
2. Configurações → Contrato: revisar prazo máximo, prorrogações e follow-up. Configurações → Alertas de Evento: revisar alertas de adiamento.
3. Rodar `python manage.py alertar_adiamentos --dry-run` na VPS.
4. Crontab (conferir fuso com `timedatectl`):
   `45 8 * * * cd /var/www/crm_arretado && venv/bin/python manage.py alertar_adiamentos >> /var/log/arretado/adiamentos.log 2>&1`
5. Nova versão: tag anotada + entrada no `CHANGELOG.md`.
