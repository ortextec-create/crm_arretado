# COBRANCA.md — Régua de Cobrança de Eventos (WhatsApp + Ligações)

> Spec para implementação via Claude Code. Segue os padrões obrigatórios de `CLAUDE.md`.
> Mockup aprovado: `mockup_cobranca.html` (2 abas: Fila de cobrança e Régua e mensagens, mais modais de ligação/pausa/retomada e gaveta de linha do tempo).
> Requisito de revenda: **nenhum valor da Arretado hardcoded**. Nome da empresa via `Empresa.get_padrao()`, Pix/telefone/textos/dias em `ConfiguracaoCobranca`.

---

## Visão Geral

Novo app Django `cobranca/`. Envia mensagens automáticas de WhatsApp ao **cliente** de Eventos com saldo em aberto, separadas em **lembretes** e **cobranças**, e registra as **ligações de cobrança** feitas pela equipe.

Três peças:

1. **Régua** — lista configurável de etapas. Cada etapa = um dia relativo à **data do evento** (negativo = antes, positivo = depois) + um texto. O tipo (lembrete/cobrança) é **derivado** de `ConfiguracaoCobranca.limite_lembrete`, nunca gravado na etapa.
2. **Pausa com prazo** — a equipe combina um prazo de pagamento com o cliente; a régua para até lá. No dia do prazo e no dia seguinte (se não pagou) saem mensagens próprias.
3. **Ligação de cobrança** — registro imutável de cada tentativa (dia, hora, atendente, número, atendeu ou não, prazo combinado, observação). Prazo informado cria a pausa automaticamente.

Um cron diário (`enviar_cobrancas`) executa a régua. Uma tela `Cobranca.jsx` mostra a fila de trabalho da equipe e a configuração.

**Não confundir** com `eventos/management/commands/alertar_eventos.py`: aquele avisa **a equipe** sobre saldo pendente; este fala com **o cliente**. Os dois continuam existindo, independentes.

### Decisões registradas

| Decisão | Valor |
|---|---|
| Âncora da régua | `Evento.data_evento` (não a `data_quitacao` do contrato) |
| Fronteira lembrete × cobrança | `limite_lembrete`, default `-7` → etapas com `dias <= -7` são lembrete, `dias > -7` são cobrança |
| Status elegíveis | `confirmado`, `em_producao`, `pronto`, `entregue` |
| Fora da régua | `orcamento`, `cancelado` |
| Evento entregue com saldo | **continua** recebendo cobrança |
| Onde mora o código | app novo `cobranca/` (não altera models de `eventos/`) |
| Pausa | sempre com prazo (`pausado_ate`), nunca indefinida |
| Ligação | imutável — correção = novo registro |
| Mensagem "tentamos te ligar" | existe, **desligada** por padrão |
| Régua padrão | 3 lembretes + 3 cobranças (ver seed), textos ajustáveis depois pelo usuário |

---

## Fase 0 — Pré-requisitos (executar ANTES de criar o app)

### 0.1 Tipos novos em `notificacoes.HistoricoMensagem.TIPO_CHOICES`

```
('lembrete_pagamento', 'Lembrete de Pagamento (cliente)'),
('cobranca',           'Cobrança (cliente)'),
```

`max_length=20` comporta os dois (`lembrete_pagamento` = 18). Gerar migration em `notificacoes/`. O tipo `lembrete` já existente é genérico — **não reutilizar**. Nenhum dos dois entra em `_TIPOS_COM_TOGGLE` de `servico.py`: quem liga/desliga é `ConfiguracaoCobranca.ativo`.

### 0.2 Ações novas em `auditoria.LogAuditoria.ACAO_CHOICES`

```
cobranca_config_alterada
cobranca_etapa_criada
cobranca_etapa_alterada
cobranca_pausada
cobranca_retomada
cobranca_ligacao_registrada
```

Migration em `auditoria/` + rótulos em `arretado-crm/src/utils/auditoriaResumo.js` (`ACAO_LABEL`/`ACAO_COR`).

### 0.3 Conferir antes de começar

- Telefone do cliente: usar a property já existente `Evento.telefone_display` (`cliente.telefone_principal` → fallback `cliente_telefone`). Nome: `Evento.nome_cliente_display`. Não duplicar essa lógica em `cobranca/`.
- `Empresa.get_padrao()` existe e devolve a matriz (Eventos são mono-empresa).

---

## Models (`cobranca/models.py`)

### ConfiguracaoCobranca (singleton)

Mesmo padrão `.get()` de `ConfiguracaoAlertaEvento` (`get_or_create(pk=1)`).

| Campo | Tipo | Default | Notas |
|---|---|---|---|
| ativo | BooleanField | **False** | nasce desligado — o deploy nunca dispara mensagem sozinho |
| ativo_desde | DateField, null | None | **read-only na API**. Gravado pela view no PATCH que muda `ativo` de False→True (= `timezone.localdate()`). Ver regra "Primeira ativação" |
| limite_lembrete | IntegerField | -7 | validar `-60 ≤ x ≤ 60` |
| dias_semana_envio | JSONField | `[0,1,2,3,4,5]` | `date.weekday()` (0 = segunda). Lista não vazia, ints 0–6, sem repetição |
| chave_pix | CharField(120), blank | `''` | vazio → `{chave_pix}` renderiza vazio (o usuário ajusta o texto) |
| favorecido_pix | CharField(120), blank | `''` | |
| telefone_contato | CharField(30), blank | `''` | alimenta `{telefone_empresa}` |
| intervalo_envio_segundos | PositiveSmallIntegerField | 3 | `time.sleep()` entre envios no cron (reduz risco de bloqueio Z-API). Máx. 30 |
| notificar_equipe_ultima_etapa | BooleanField | True | quando a última etapa ativa é enviada, avisa os `eventos.TelefoneAlertaEvento` ativos |
| msg_prazo_hoje_ativo | BooleanField | True | |
| msg_prazo_hoje | TextField | `MSG_PRAZO_HOJE_DEFAULT` | |
| msg_prazo_vencido_ativo | BooleanField | True | |
| msg_prazo_vencido | TextField | `MSG_PRAZO_VENCIDO_DEFAULT` | |
| msg_ligacao_nao_atendida_ativo | BooleanField | **False** | |
| msg_ligacao_nao_atendida | TextField | `MSG_LIGACAO_NAO_ATENDIDA_DEFAULT` | |
| atualizado_em | auto_now | | |

Os `MSG_*_DEFAULT` são constantes no topo de `models.py` (mesmo padrão de `MSG_ANIVERSARIO_DEFAULT`), **sem nome de empresa** — usam `{empresa}` quando precisam.

### EtapaRegua

| Campo | Tipo | Notas |
|---|---|---|
| dias | IntegerField | relativo a `data_evento`. `-60 ≤ dias ≤ 60` |
| mensagem | TextField | máx. 1000 caracteres (validar no serializer) |
| ativo | BooleanField default=True | desativar no lugar de excluir |
| criado_em / atualizado_em | auto | |

- `UniqueConstraint(fields=['dias'])` — vale também entre etapas inativas (a UI mostra o conflito). Checar `.exists()` explícito no serializer antes, com mensagem amigável ("Já existe uma etapa em D−7").
- **Sem DELETE.** Envios antigos apontam para a etapa (PROTECT).
- `ordering = ['dias']`.
- Property `tipo` → `'lembrete' if self.dias <= ConfiguracaoCobranca.get().limite_lembrete else 'cobranca'`. Em listas, resolver `limite` uma vez e passar adiante (função `tipo_da_etapa(dias, limite)` em `regua.py`) — nunca 1 query por etapa.

**Seed** (data migration `RunPython`, só cria se a tabela estiver vazia, reversível com no-op):

| dias | Rótulo derivado (limite -7) | Texto |
|---|---|---|
| -12 | L1 | ver "Textos padrão" |
| -9 | L2 | |
| -7 | L3 | |
| -6 | C1 | |
| -3 | C2 | |
| 3 | C3 | |

Rótulos `L1/L2/C1…` são **calculados** na serialização (ordem por `dias` dentro do tipo, só etapas ativas), nunca gravados.

### PausaCobranca

| Campo | Tipo | Notas |
|---|---|---|
| evento | FK `eventos.Evento`, PROTECT, related_name=`pausas_cobranca` | |
| pausado_ate | DateField | obrigatório, `>= hoje` na criação |
| motivo | CharField(300) | obrigatório |
| origem | choices `manual` / `ligacao` | |
| ligacao | OneToOneField `LigacaoCobranca`, null, PROTECT | preenchido quando `origem='ligacao'` |
| criado_por | FK `usuarios.Usuario`, null, SET_NULL | |
| criado_por_nome | CharField(150) | snapshot (padrão de `LogAuditoria`) |
| criado_em | auto_now_add | |
| encerrada_em | DateTimeField, null | preenchido em retomada antecipada ou substituição |
| encerrada_por / encerrada_por_nome | FK SET_NULL + snapshot | |
| motivo_encerramento | CharField(300), blank | `'Substituída por nova pausa'` quando automático |

- **Vigente** (derivado, nunca flag): `encerrada_em IS NULL AND pausado_ate >= hoje`. Helper `pausa_vigente(evento, hoje)` em `regua.py`.
- **Uma vigente por evento.** Criar pausa nova encerra a vigente anterior na mesma `transaction.atomic()` (motivo `'Substituída por nova pausa'`). Renegociar = estender prazo.
- Sem PATCH/DELETE. Encerrar antes do prazo só via action `encerrar/` (exige motivo).

### LigacaoCobranca

| Campo | Tipo | Notas |
|---|---|---|
| evento | FK `eventos.Evento`, PROTECT, related_name=`ligacoes_cobranca` | |
| data_hora | DateTimeField | default `timezone.now`; editável no POST; **rejeitar futuro** |
| atendente | FK `usuarios.Usuario`, null, SET_NULL | default = usuário logado; pode escolher outro usuário ativo |
| atendente_nome | CharField(150) | snapshot |
| telefone_discado | CharField(30) | snapshot (principal, secundário ou digitado) |
| atendeu | BooleanField | obrigatório no payload (não ter default no serializer) |
| prazo_pagamento | DateField, null | só aceito se `atendeu=True`; `>= data de hoje` |
| observacao | TextField, blank | |
| registrado_por / registrado_por_nome | FK SET_NULL + snapshot | quem digitou (pode diferir do atendente) |
| criado_em | auto_now_add | |

**Imutável**: sem PATCH/PUT/DELETE. Correção = novo registro.

### EnvioCobranca (log imutável de WhatsApp)

| Campo | Tipo | Notas |
|---|---|---|
| evento | FK `eventos.Evento`, PROTECT, related_name=`envios_cobranca` | |
| tipo | choices `lembrete` / `cobranca` / `prazo_hoje` / `prazo_vencido` / `ligacao_nao_atendida` | **snapshot** do tipo no momento do envio |
| etapa | FK `EtapaRegua`, null, PROTECT | só para `lembrete`/`cobranca` |
| dias_etapa | IntegerField, null | snapshot de `etapa.dias` |
| rotulo_etapa | CharField(5), blank | snapshot (`L2`, `C1`…) |
| data_evento_referencia | DateField | `evento.data_evento` no momento — chave de remarcação |
| pausa | FK `PausaCobranca`, null, PROTECT | para `prazo_hoje`/`prazo_vencido` e puladas por pausa |
| ligacao | FK `LigacaoCobranca`, null, PROTECT | para `ligacao_nao_atendida` |
| status | choices `enviado` / `falha` / `pulada` | |
| motivo_pulada | choices `atraso` / `pausa` / `mesmo_dia`, blank | só quando `pulada` |
| telefone | CharField(30), blank | |
| mensagem_renderizada | TextField, blank | texto exato enviado (vazio em `pulada`) |
| saldo_no_envio | DecimalField(10,2), null | |
| historico | FK `notificacoes.HistoricoMensagem`, null, SET_NULL | |
| criado_em | auto_now_add, db_index | |

Constraints (todas condicionais; **sempre** checar `.exists()` antes de criar — regra do projeto):

- `UniqueConstraint(evento, etapa, data_evento_referencia)` com `condition=Q(etapa__isnull=False) & Q(status__in=['enviado','pulada'])` — cada etapa sai (ou é pulada) uma vez por data do evento. `falha` **não** ocupa a vaga → o cron tenta de novo no próximo dia de envio.
- `UniqueConstraint(pausa, tipo)` com `condition=Q(pausa__isnull=False) & Q(tipo__in=['prazo_hoje','prazo_vencido']) & Q(status='enviado')`.
- `UniqueConstraint(ligacao)` com `condition=Q(ligacao__isnull=False) & Q(status='enviado')`.

Índice: `Index(fields=['evento', '-criado_em'])`.

> **PROTECT em `evento`**: um Evento com histórico de cobrança não pode ser excluído — o `AuditoriaDestroyMixin` (já presente em `EventoViewSet`) traduz o `ProtectedError` em 400 amigável. Cancelar o evento continua possível e tira o evento da régua.

---

## Variáveis e renderização (`cobranca/mensagens.py`)

Função pura `render(texto, contexto) -> str` com `re.sub(r'\{(\w+)\}', ...)`. **Nunca** `str.format()`/`format_map()` (chave com `.` ou `[` vira acesso a atributo; chave literal com `{}` derruba o envio). Variável ausente no contexto → string vazia (validação já impede variável desconhecida no texto salvo).

`montar_contexto(evento, cfg, hoje, pausa=None) -> dict`:

| Variável | Valor |
|---|---|
| `{primeiro_nome}` | primeira palavra de `evento.nome_cliente_display` |
| `{nome}` | `evento.nome_cliente_display` |
| `{numero_evento}` | `evento.numero` |
| `{tipo_evento}` | `evento.get_tipo_evento_display()` |
| `{data_evento}` | `dd/mm/aaaa` |
| `{valor_total}` / `{valor_pago}` / `{saldo}` | `1.600,00` (pt-BR, sem "R$" — o texto traz o "R$") ; `valor_pago` = `sinal_pago` |
| `{data_limite}` | `data_evento + limite_lembrete` em `dd/mm/aaaa` (calculado, nunca gravado) |
| `{dias_para_limite}` | `max((data_limite - hoje).days, 0)` |
| `{dias_em_atraso}` | `max((hoje - data_limite).days, 0)` |
| `{dias_para_evento}` | `max((data_evento - hoje).days, 0)` |
| `{prazo_combinado}` | `pausa.pausado_ate` em `dd/mm/aaaa` — **só** nas mensagens de prazo |
| `{chave_pix}` / `{favorecido_pix}` / `{telefone_empresa}` | de `ConfiguracaoCobranca` |
| `{empresa}` | `Empresa.get_padrao().nome` |

Validação (`validar_texto(texto, permitir_prazo: bool)`):

- Variável fora da lista → 400 `{"mensagem": ["Variável desconhecida: {xyz}"]}`.
- `{prazo_combinado}` em `EtapaRegua.mensagem` ou em `msg_ligacao_nao_atendida` → 400 (não existe pausa nesses contextos).
- Texto vazio → 400.

Formatação WhatsApp (`*negrito*`) passa direto, sem tratamento.

### Textos padrão

**Etapas (seed):**

- **-12** — `Oi, {primeiro_nome}! Tudo bem? 😊\nPassando para lembrar que o saldo do seu evento *{tipo_evento}* de *{data_evento}* ({numero_evento}) deve ser quitado até *{data_limite}*.\n💰 Saldo: *R$ {saldo}*\nPix: {chave_pix} ({favorecido_pix})\nSe já tiver pago, é só desconsiderar. Qualquer dúvida, estamos por aqui! 🍬\n— {empresa}`
- **-9** — `Oi, {primeiro_nome}! Faltam só {dias_para_limite} dias para o prazo do saldo do seu evento ({numero_evento}) 🗓️\n💰 *R$ {saldo}* até *{data_limite}*\nPix: {chave_pix}\nDepois de pagar, envie o comprovante por aqui para darmos baixa. Obrigado! 💛`
- **-7** — `Bom dia, {primeiro_nome}! ☀️\nHoje é o último dia para quitar o saldo do seu evento de *{data_evento}*.\n💰 *R$ {saldo}* · Pix: {chave_pix}\nAssim que recebermos, seguimos com tudo certinho para o seu dia! 🎉`
- **-6** — `Oi, {primeiro_nome}. Ainda não identificamos o pagamento do saldo do evento {numero_evento}, que venceu em {data_limite}.\n💰 Valor em aberto: *R$ {saldo}*\nPix: {chave_pix} ({favorecido_pix})\nSe já pagou, pode nos enviar o comprovante? Pode ter sido só um desencontro 🙏`
- **-3** — `Olá, {primeiro_nome}. O saldo de *R$ {saldo}* do seu evento de *{data_evento}* está em aberto há {dias_em_atraso} dias.\nPara garantirmos a produção e a entrega no prazo, precisamos da quitação o quanto antes.\nPix: {chave_pix}\nSe precisar combinar outra forma, fale com a gente pelo {telefone_empresa}.`
- **3** — `Olá, {primeiro_nome}. Consta em aberto o valor de *R$ {saldo}* referente ao evento {numero_evento} ({data_evento}), vencido em {data_limite}.\nPedimos que regularize ou entre em contato pelo {telefone_empresa} para combinarmos a melhor forma.\nPix: {chave_pix}\nAgradecemos a compreensão. — {empresa}`

**Especiais:**

- `MSG_PRAZO_HOJE_DEFAULT` — `Oi, {primeiro_nome}! Passando para lembrar que hoje é o prazo que combinamos para o saldo do evento {numero_evento}: *R$ {saldo}*.\nPix: {chave_pix}\nObrigado! 💛`
- `MSG_PRAZO_VENCIDO_DEFAULT` — `Olá, {primeiro_nome}. O prazo combinado ({prazo_combinado}) para o saldo de *R$ {saldo}* do evento {numero_evento} venceu e ainda não identificamos o pagamento.\nPode nos dar um retorno?\nPix: {chave_pix}`
- `MSG_LIGACAO_NAO_ATENDIDA_DEFAULT` — `Oi, {primeiro_nome}! Tentamos falar com você por telefone sobre o saldo do evento {numero_evento} (*R$ {saldo}*).\nQuando puder, nos chame por aqui ou no {telefone_empresa}. Obrigado!`

Os textos evitam ameaça e exposição (CDC art. 42). Multa/juros **não** entram por padrão (só valem com contrato — evento sem contrato receberia valor sem base).

---

## Motor da régua (`cobranca/regua.py`)

Funções puras (recebem `hoje` como argumento — nunca chamar `timezone.localdate()` dentro delas; facilita teste):

- `tipo_da_etapa(dias, limite) -> 'lembrete'|'cobranca'`
- `rotulos(etapas_ativas, limite) -> dict[etapa_id, 'L1'…]`
- `data_da_etapa(evento, etapa) -> date` = `data_evento + timedelta(days=etapa.dias)`
- `pausa_vigente(evento, hoje) -> PausaCobranca|None`
- `eventos_elegiveis()` → queryset: `status__in=STATUS_ELEGIVEIS`, `annotate(saldo=F('valor_total') - F('sinal_pago')).filter(saldo__gt=0)` (mesma técnica de `alertar_eventos` — nunca a property Python `saldo_restante` no filtro). `select_related('cliente')`.
- `decidir_do_dia(evento, etapas_ativas, cfg, hoje) -> Decisao` — devolve **no máximo uma** mensagem a enviar + a lista de registros `pulada` a gravar. Não envia nada, não grava nada.

`STATUS_ELEGIVEIS = ('confirmado', 'em_producao', 'pronto', 'entregue')` — constante em `regua.py`, única fonte.

### Regras de decisão (por evento, por dia)

Executar na ordem; a primeira que produzir mensagem encerra o evento no dia (**no máximo 1 WhatsApp por evento por dia**).

1. **Sem telefone resolvido** → nada (log `warning`; a fila mostra "sem telefone").
2. **Pausa vigente:**
   - Etapas ativas com `data_da_etapa <= hoje`, ainda sem `EnvioCobranca` (`enviado`/`pulada`) para `(evento, etapa, data_evento)` → registrar `pulada` / `motivo_pulada='pausa'` / `pausa=vigente`.
   - Se `pausado_ate == hoje` e `msg_prazo_hoje_ativo` e ainda não enviado `prazo_hoje` para essa pausa → **enviar `prazo_hoje`**.
   - Encerrar (não seguir para a régua).
3. **Pausa recém-vencida** — a pausa mais recente do evento com `encerrada_em IS NULL`, `pausado_ate < hoje`, sem `prazo_vencido` enviado para ela, e sem pausa mais nova:
   - Se `msg_prazo_vencido_ativo` → **enviar `prazo_vencido`**; etapas pendentes com data `<= hoje` → `pulada` / `mesmo_dia`. Encerrar.
   - Se desativada → seguir para o passo 4 normalmente.
   - Pausas que venceram **antes de `ativo_desde`** são ignoradas (ver "Primeira ativação").
4. **Régua normal:**
   - Pendentes = etapas ativas com `ativo_desde <= data_da_etapa <= hoje` e sem `EnvioCobranca` `enviado`/`pulada` para `(evento, etapa, data_evento)`.
   - Nenhuma → nada.
   - **Atraso**: se houver mais de uma pendente, só a de maior `dias` é enviada; as demais → `pulada` / `atraso`. O cliente nunca recebe a régua acumulada.
   - Enviar a escolhida com `tipo = tipo_da_etapa(dias, limite)` (snapshot).
5. **Última etapa:** se o envio do passo 4 foi da etapa ativa de maior `dias` e `notificar_equipe_ultima_etapa` → avisar `eventos.TelefoneAlertaEvento` ativos (`notificar(..., tipo='alerta_pagamento')`): `Régua de cobrança concluída sem pagamento — {numero} ({nome}) · saldo R$ {saldo}`. Uma vez só (consequência da constraint da etapa).

### Primeira ativação (`ativo_desde`)

Quando o módulo é ligado pela primeira vez, eventos antigos com saldo (inclusive dados mal lançados de meses atrás) **não** podem receber mensagem de etapa que "já passou". Regra: etapa com `data_da_etapa < ativo_desde` nunca é enviada nem registrada como pulada — simplesmente não existe para aquele evento. Desligar e religar **atualiza** `ativo_desde` (mesmo efeito: não despeja atrasados acumulados durante o período desligado). Esses eventos continuam aparecendo na Fila para ação manual (ligação).

### Remarcação

A chave de idempotência inclui `data_evento_referencia`. Mudou `Evento.data_evento` → nenhum envio anterior conta para a nova data → a régua recomeça (respeitando a regra de atraso: sai só a etapa mais recente já vencida, se houver). Pausas não são afetadas (são por data absoluta).

### Saldo no momento do envio

Imediatamente antes de cada envio: `evento.refresh_from_db()` e recalcular saldo (`valor_total - sinal_pago`). Se `<= 0`, não envia nem registra nada. Cobre pagamento lançado entre a montagem do queryset e o envio.

---

## Management Command (cron)

### `enviar_cobrancas` (diário — 09:30)

```
python manage.py enviar_cobrancas [--dry-run] [--evento EV-123] [--data AAAA-MM-DD]
```

1. `cfg = ConfiguracaoCobranca.get()`. `ativo=False` → escreve "Cobrança automática desligada" e sai.
2. `hoje = timezone.localdate()` (ou `--data`, só com `--dry-run` — nunca enviar de verdade com data simulada).
3. `hoje.weekday() not in cfg.dias_semana_envio` → sai. Etapas do dia bloqueado viram pendentes e saem no próximo dia liberado pela regra de atraso.
4. Para cada evento elegível: `decidir_do_dia()` → gravar `pulada`s → enviar a mensagem (se houver) via `notificacoes.servico.notificar(telefone, texto, cliente=evento.cliente, tipo=...)` → gravar `EnvioCobranca` com `status='enviado'` ou `'falha'` e FK para o `HistoricoMensagem` criado.
   - Para obter o `HistoricoMensagem`: `notificar()` hoje devolve só `bool`. **Não alterar a assinatura.** Buscar o registro logo depois por `telefone` + `tipo` + `enviado_em__gte=inicio_do_envio`, `.order_by('-enviado_em').first()`. Se não achar, deixar `historico=None` (não é crítico).
   - Mapeamento de `tipo` para `HistoricoMensagem.tipo`: `lembrete`/`prazo_hoje` → `lembrete_pagamento`; `cobranca`/`prazo_vencido`/`ligacao_nao_atendida` → `cobranca`.
   - Cada evento em `try/except` próprio — um erro não para o lote (log `exception`).
   - `time.sleep(cfg.intervalo_envio_segundos)` entre envios reais (não no dry-run).
5. `--dry-run`: imprime a decisão de cada evento (enviaria X / pularia Y), não grava nada, não envia nada.
6. Resumo final: `N enviados · N falhas · N pulados`.

Idempotente: rodar 2× no mesmo dia não reenvia (constraints + `.exists()`).

---

## Ações síncronas fora do cron

- **Ligação não atendida** (`POST ligacoes/` com `atendeu=false`): se `cfg.ativo` **e** `msg_ligacao_nao_atendida_ativo` **e** saldo > 0 → envia na hora e grava `EnvioCobranca(tipo='ligacao_nao_atendida', ligacao=...)`. Falha no WhatsApp **não** falha o registro da ligação (resposta 201 com `whatsapp_enviado: false`).
- **Ligação com prazo** (`atendeu=true`, `prazo_pagamento` preenchido, `pausar=true` no payload — default `true`): na mesma `transaction.atomic()` cria `LigacaoCobranca` + `PausaCobranca(origem='ligacao', ligacao=..., pausado_ate=prazo_pagamento, motivo=observacao or 'Prazo combinado por telefone')`, encerrando a pausa vigente anterior.

---

## Endpoints (`/api/v1/cobranca/`)

Rota registrada em `config/urls.py`. Todos os ViewSets com `CsrfExemptMixin` + `TokenAuthentication`; login exigido via `get_permissions()` nas actions de escrita (padrão de `EventoViewSet`).

```
# Configuração
GET/PATCH  configuracao/1/                    ← singleton, pk ignorado · PATCH exige login, audita cobranca_config_alterada
                                                 (só campos alterados) · ativo False→True grava ativo_desde

# Etapas da régua
GET        etapas/                            ← inclui tipo e rotulo derivados + limite atual no payload
POST       etapas/                            ← exige login, audita cobranca_etapa_criada
PATCH      etapas/{id}/                       ← exige login, audita cobranca_etapa_alterada · sem PUT/DELETE
POST       etapas/preview/                    ← AllowAny, sem efeito colateral
                                                 body {mensagem, evento_id?, tipo_especial?} → {texto, variaveis_invalidas}
                                                 sem evento_id: usa o evento elegível mais próximo; nenhum → contexto fictício marcado

# Fila e linha do tempo (só leitura)
GET        fila/                              ← filtros: fase (lembrete|cobranca|pausado|prazo_hoje|pos_evento|sem_ligacao), search
GET        eventos/{evento_id}/linha-do-tempo/

# Logs
GET        envios/                            ← só leitura · filtros: evento, tipo, status, data_inicio, data_fim

# Ligações
GET        ligacoes/                          ← filtros: evento, atendente, atendeu, data_inicio, data_fim
POST       ligacoes/                          ← exige login · audita cobranca_ligacao_registrada (+ cobranca_pausada se criou pausa)
                                                 body {evento, data_hora?, atendente?, telefone_discado, atendeu,
                                                       prazo_pagamento?, pausar?=true, observacao?}

# Pausas
GET        pausas/                            ← filtros: evento, vigente=true
POST       pausas/                            ← exige login, audita cobranca_pausada · body {evento, pausado_ate, motivo}
POST       pausas/{id}/encerrar/              ← exige login, audita cobranca_retomada · body {motivo} · 400 se já encerrada/vencida
```

### Payload de `fila/` (por evento)

```
{ evento_id, numero, cliente_id, nome, tipo_evento, data_evento, status,
  valor_total, valor_pago, saldo,
  dias_para_evento,                         // negativo = já aconteceu
  telefone, sem_telefone,
  fase: { codigo: lembrete|cobranca|pausado|aguardando|concluida, texto: "Cobrança 1 de 3" },
  etapas: [{ id, rotulo, dias, data, situacao: enviada|pulada|pendente|futura }],
  pausa_vigente: { id, pausado_ate, motivo } | null,
  ultimo_contato: { canal: whatsapp|ligacao, quando, atendeu? } | null,
  proxima_acao: { texto, urgente: bool },
  total_ligacoes }
```

Ordenação (urgência): prazo combinado vencendo hoje → régua concluída sem pagamento → em cobrança → pausados → em lembrete → aguardando; empate por `data_evento` ascendente. Calcular em Python (volume pequeno), com `prefetch_related('envios_cobranca', 'pausas_cobranca', 'ligacoes_cobranca')` — e **sem** criar nada na mesma request (armadilha do prefetch stale documentada no CLAUDE.md não se aplica, mas não introduzir escrita aqui).

O resumo do topo da tela (em aberto, já em cobrança, prazos de hoje, pós-evento) é calculado no frontend a partir de `fila/`.

### Payload de `linha-do-tempo/`

Lista única ordenada por data/hora decrescente, mesclando: `EnvioCobranca` (todos os status, com `mensagem_renderizada`), `LigacaoCobranca`, `PausaCobranca` (criação e encerramento como itens separados) e `PagamentoEvento` com `status='pago'` (mostra quando o cliente pagou no meio da régua). Cada item: `{tipo, data_hora, titulo, detalhe, autor?, mensagem?}`. Cabeçalho com totais do evento e `etapas` (mesmo formato da fila).

---

## Frontend

Referência visual: `mockup_cobranca.html` (aprovado).

- `pages/Cobranca.jsx` + `Cobranca.module.css` — 2 abas:
  - **Fila de cobrança**: 4 cartões de resumo, chips de filtro com contagem, tabela (cliente/evento, data com "em N dias"/"há N dias", saldo, pill da fase + barrinhas das etapas, último contato, próxima ação, ações Registrar ligação / Pausar ou Retomar / Linha do tempo). Tabela com `overflow-x: auto` no mobile.
  - **Régua e mensagens**: eixo visual (dia do evento fixo, data limite ajustável com `input[type=range]`, zonas lembrete/cobrança, etapas clicáveis), editor da etapa (dias, ativa, texto, chips de variáveis que inserem no cursor, prévia em balão), lista de etapas + "Adicionar etapa", mensagens especiais em `<details>` com toggle, card Geral (envio automático, dias da semana, Pix, favorecido, telefone de contato).
- **Modais** (`Modal` existente, prop `open` explícita): Registrar ligação (data/hora, atendente, número discado em rádio, Atendeu/Não atendeu, prazo + "pausar até o prazo" só quando atendeu, observação, aviso de imutabilidade); Pausar com prazo; Retomar.
- **Gaveta de linha do tempo**: valores, pausa vigente, ações, régua do evento com datas reais, histórico.
- `cobrancaApi` em `services.js` (configuracao, etapas, preview, fila, linhaDoTempo, envios, ligacoes, pausas, encerrarPausa).
- Rota `/cobranca` em `App.jsx` + item em `Sidebar.jsx` (seção Eventos, ícone `ti-coin`) + slug `cobranca` em `MODULOS_OCULTAVEIS` (`Empresas.jsx`).
- **Prévia** do editor chama `etapas/preview/` com debounce 400 ms — nunca reimplementar a renderização no frontend (fonte única é `mensagens.py`).
- Ao mover a data limite, as pills/rótulos se atualizam localmente; salvar envia `limite_lembrete` no PATCH da configuração.
- Ligar o envio automático pela primeira vez abre confirmação **na própria página** (não `window.confirm`): "A partir de hoje, clientes com saldo em aberto passam a receber WhatsApp automático. Etapas com data anterior a hoje não serão enviadas."
- Selects de atendente: `usuariosApi` (ativos), default o usuário logado (`useAuth`).
- Badge no **modal do Evento** (`Eventos.jsx`) e no **`ClienteDetail.jsx`**: "Cobrança: Lembrete 2 de 3 · próxima em 12/10" / "Pausado até 09/10" / "2 ligações · última em 05/10", com link para a gaveta. Ler de `fila/` filtrado (ou endpoint leve `eventos/{id}/linha-do-tempo/` cabeçalho) — sem lógica de régua no frontend.
- `--surface` em modal/card, Tabler Icons, CSS Modules, sem `localStorage`.

---

## Fases de Implementação

| Fase | Conteúdo | Critério de pronto |
|---|---|---|
| 0 | Tipos novos em `HistoricoMensagem` + ações em `LogAuditoria` + rótulos em `auditoriaResumo.js` | migrations aplicam limpas; nada mais muda de comportamento |
| 1 | App `cobranca/`: models + migrations + seed das 6 etapas + admin + `mensagens.py` (render, contexto, validação) | testes: render com todas as variáveis; variável desconhecida/`{prazo_combinado}` em etapa rejeitada; `str.format` não usado; seed não duplica ao rodar 2× |
| 2 | `regua.py` + command `enviar_cobrancas` (`--dry-run`, `--evento`, `--data`) | testes: (a) 2 execuções no mesmo dia não duplicam; (b) atraso de 3 dias envia só a etapa mais recente e pula as outras; (c) pausa vigente pula etapas e envia `prazo_hoje` no dia; (d) dia seguinte envia `prazo_vencido` e nada mais; (e) `ativo_desde` ignora etapas anteriores; (f) remarcação recomeça; (g) `falha` é reenviada no próximo dia; (h) dia bloqueado não envia e o seguinte envia só a mais recente; (i) saldo zerado entre query e envio não envia; (j) status fora de `STATUS_ELEGIVEIS` não entra; (k) evento entregue com saldo entra; (l) aviso à equipe na última etapa sai uma vez |
| 3 | API: configuracao, etapas, preview, pausas, ligacoes, envios + auditoria | testes: ligação com prazo cria pausa e encerra a anterior (atômico); ligação imutável (PATCH/DELETE → 405); `prazo_pagamento` com `atendeu=false` → 400; `data_hora` futura → 400; não atendida envia WhatsApp só com toggle ligado; `ativo` False→True grava `ativo_desde`; dias duplicado → 400 amigável |
| 4 | `fila/` + `linha-do-tempo/` | fases e próxima ação batem com o motor (reusar funções de `regua.py`, nunca lógica paralela); ordenação por urgência; pagamentos aparecem na linha do tempo |
| 5 | Frontend `Cobranca.jsx` completo + `cobrancaApi` + rota + sidebar + `MODULOS_OCULTAVEIS` | 2 abas, modais e gaveta conforme mockup |
| 6 | Badges no modal do Evento e no `ClienteDetail` + testes finais + `CLAUDE.md` (estrutura, endpoints, padrões, cron, fases, "O Que NÃO Fazer") | suite verde; CLAUDE.md canônico atualizado |

Cada fase termina com o `CLAUDE.md` coerente com o código.

---

## O Que NÃO Fazer

- **Não** chamar `zapi_client` direto — sempre `notificacoes.servico.notificar()`.
- **Não** alterar a assinatura de `notificar()` para devolver o `HistoricoMensagem` — buscar o registro depois (ver command).
- **Não** gravar o tipo (lembrete/cobrança) na `EtapaRegua` — é sempre derivado de `limite_lembrete`. No `EnvioCobranca` ele é snapshot, de propósito.
- **Não** gravar rótulos `L1/C2` em lugar nenhum além do snapshot do envio.
- **Não** gravar `data_limite` — sempre `data_evento + limite_lembrete`.
- **Não** usar `Contrato.data_quitacao` nem `ConfiguracaoContrato.prazo_quitacao_dias` na régua — âncora é `data_evento` (decisão registrada).
- **Não** enviar mais de 1 WhatsApp por evento por dia, nem despejar etapas atrasadas acumuladas.
- **Não** enviar etapa com data anterior a `ativo_desde`.
- **Não** usar `str.format()`/`format_map()` para renderizar mensagem.
- **Não** renderizar mensagem no frontend — prévia vem de `etapas/preview/`.
- **Não** usar a property `saldo_restante` em filtro de queryset — `annotate(F())`.
- **Não** incluir Eventos `orcamento`/`cancelado`. **Não** excluir `entregue`.
- **Não** implementar DELETE em `EtapaRegua`, `PausaCobranca`, `LigacaoCobranca` nem `EnvioCobranca`; nem PATCH em ligação/envio/pausa.
- **Não** criar pausa sem prazo (`pausado_ate` obrigatório) nem com prazo no passado.
- **Não** confiar só nas `UniqueConstraint` — `.exists()` explícito antes de criar.
- **Não** acrescentar campo em `eventos.Evento` para a cobrança — tudo vive em `cobranca/`.
- **Não** reaproveitar `AlertaEventoEnviado`/`alertar_eventos` — são da equipe, não do cliente.
- **Não** hardcodar nome da empresa, Pix ou telefone em texto padrão — variáveis.
- **Não** usar Celery — cron + management command.
- **Não** usar `window.confirm()` para ligar o envio automático — confirmação na página.

---

## Fora de Escopo (desta spec)

- Cobrança de `ContaReceber` manual, PDV ou iFood — só Eventos.
- Ler respostas do cliente / comprovantes recebidos no WhatsApp (webhook de mensagem recebida) e dar baixa automática.
- Pix copia-e-cola / QR Code dinâmico com valor, link de pagamento.
- Multa e juros nas mensagens (variáveis condicionais a contrato).
- Relatório de efetividade da régua (taxa de pagamento por etapa) e export Excel/PDF.
- Cards de cobrança no Dashboard.
- Opt-out do cliente ("não quero receber") — tratar manualmente com pausa por enquanto.
- Mensagem com PDF anexo (contrato/aditivo) na régua.
- Horário de envio configurável pela tela — o horário é o do cron.

---

## Setup Manual (pós-implementação — checklist para o usuário)

1. Deploy com `migrate` → reiniciar **os dois** serviços: `systemctl restart arretado arretado-polling`.
2. Em **Cobrança → Régua e mensagens**: preencher chave Pix, favorecido e telefone de contato; revisar os 6 textos e as 3 mensagens especiais.
3. Conferir se há telefones em **Alertas de Evento** (`TelefoneAlertaEvento`) — sem eles, o aviso de régua concluída não sai.
4. Rodar `python manage.py enviar_cobrancas --dry-run` na VPS e conferir a lista antes de ligar.
5. Crontab da VPS (conferir fuso do servidor — `timedatectl`; o horário abaixo assume America/Fortaleza):
   `30 9 * * * cd /var/www/crm_arretado && venv/bin/python manage.py enviar_cobrancas >> /var/log/arretado/cobranca.log 2>&1`
6. Ligar **Envio automático** na tela (grava `ativo_desde` = hoje).
7. Nova versão: tag anotada + entrada no `CHANGELOG.md`.
