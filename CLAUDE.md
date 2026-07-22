# Arretado Doces — CRM Proprietário

> Arquivo lido automaticamente pelo Claude Code em toda sessão.
> Última atualização: 22/jul/2026.

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
│   ├── settings.py              ← INSTALLED_APPS: clientes, ifood, pdv, pedidos, eventos, usuarios, notificacoes, fichas, estoque, relatorios, dashboard
│   ├── urls.py                  ← rotas: /api/v1/, /api/v1/ifood/, /api/v1/pdv/, /api/v1/eventos/, /api/v1/notificacoes/, /api/v1/fichas/, /api/v1/estoque/, /api/v1/relatorios/, /api/v1/dashboard/
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
│   ├── models.py                ← CategoriaProduto, Produto (+ segmento/foto/disponibilidades/tipo fabricado|revenda|kit
│   │                               com custo polimórfico, preco_para() por faixa), ItemKit, FaixaPreco (quantidade_minima+canal),
│   │                               DadosFiscaisProduto (unidade/código/EAN/NCM — prepara NFC-e futura), PedidoPDV, ItemPedidoPDV,
│   │                               TaxaEntregaBairro (bairro→taxa), ConfiguracaoEntrega (singleton, frete padrão)
│   ├── urls.py                  ← inclui taxas-entrega/ e configuracao-entrega/
│   ├── management/commands/listar_candidatos_revenda.py ← lista produtos "fabricado" sem FichaTecnica vinculada
│   │                               (candidatos a reclassificar manualmente para "revenda"); só leitura, não altera o banco
│   └── signals.py               ← espelha PedidoPDV → PedidoUnificado
├── eventos/                     ← Fase 4: gestão de eventos/encomendas + orçamentos + contratos
│   ├── models.py                ← Orcamento, ItemOrcamento, Evento, ItemEvento, LocalEvento,
│   │                               Contrato (snapshot, CTR-0001...), ConfiguracaoContrato (singleton — ver Contrato.md),
│   │                               ConfiguracaoAlertaEvento (singleton, janelas/repetição dos 2 alertas de Evento),
│   │                               TelefoneAlertaEvento (telefones internos da equipe que recebem os alertas),
│   │                               AlertaEventoEnviado (rastreia último envio por evento+tipo, controla repetição —
│   │                               ver "Alertas de Evento" abaixo),
│   │                               ImagemInspiracao (galeria de imagens de referência do cliente, FK → Orcamento),
│   │                               PagamentoEvento (parcelas de pagamento do Evento, FK → Evento — Evento.sinal_pago
│   │                               é sempre derivado da soma dos pagamentos com status='pago', via
│   │                               Evento.recalcular_sinal_pago(), nunca gravado direto)
│   │                               (Orcamento e Evento têm tipo_entrega/local/endereco_avulso/bairro_entrega/taxa_entrega — ver FRETE.md)
│   │                               Registrar/remover pagamento (`adicionar_pagamento`/`remover_pagamento` no EventoViewSet) exige
│   │                               login (`TokenAuthentication` + `IsAuthenticated`, única exceção dentro do EventoViewSet — resto
│   │                               continua AllowAny) e grava `auditoria.LogAuditoria` via `registrar()`. O sinal inicial criado
│   │                               junto com o Evento (`EventoCreateSerializer.create`) ou na conversão de Orçamento
│   │                               (`OrcamentoViewSet.converter_em_evento`) também é auditado, mas de forma oportunista — sem
│   │                               exigir login nesses dois fluxos, só captura o ator quando o token vier (ver "O Que NÃO Fazer").
│   │                               Criação, edição (PATCH/PUT), mudança de status (enviar/aprovar/recusar/restaurar no
│   │                               Orçamento; confirmar/iniciar_producao/marcar_pronto/entregar/cancelar no Evento),
│   │                               adicionar/editar item e a conversão de Orçamento em Evento também são auditados
│   │                               (via `AuditoriaCreateMixin`/`AuditoriaUpdateMixin`/`AuditoriaStatusMixin`, ver
│   │                               `auditoria/mixins.py`) e exigem login — exceção oportunista continua só em
│   │                               `converter_em_evento`/`enviar_whatsapp` (AllowAny, captura o ator quando o token vier)
│   ├── pdf_orcamento.py          ← gera PDF (ReportLab, canvas cru, 1 página) — inclui linha "Taxa de entrega" quando houver
│   ├── pdf_contrato.py           ← gera PDF do contrato (ReportLab Platypus, multi-página) — texto e cláusulas vêm de
│   │                               ConfiguracaoContrato.get() + snapshot do Contrato, nunca hardcoded
│   ├── pdf_resumo_cozinha.py     ← gera PDF do resumo de cozinha do Evento (ReportLab Platypus, multi-página,
│   │                               sem timbre) — documento operacional interno (uso da equipe), itens agrupados
│   │                               por categoria, nunca expõe preço — ver "Resumo de Cozinha" abaixo
│   ├── management/commands/alertar_eventos.py ← cron diário: alerta a equipe (WhatsApp, via telefones de
│   │                               TelefoneAlertaEvento) sobre Evento com saldo pendente perto da data (janela/repetição
│   │                               de ConfiguracaoAlertaEvento.get()) e sobre entrega (tipo_entrega=entrega_local) se
│   │                               aproximando — ver "Alertas de Evento" abaixo
│   └── views.py                 ← OrcamentoViewSet (converter-em-evento, gerar-contrato, imagens/, itens/{id}/editar/,
│                                    historico/, update() restrito a status rascunho/enviado) + EventoViewSet
│                                    (pagamentos/, pagamentos/{id}/remover/, historico/) +
│                                    ContratoViewSet (só leitura + pdf/enviar-whatsapp) + ConfiguracaoContratoViewSet +
│                                    ConfiguracaoAlertaEventoViewSet + TelefoneAlertaEventoViewSet
├── usuarios/                    ← Gestão de usuários + RBAC + autenticação real por token
│   ├── models.py                ← Usuario (auth_token, gerar_token(), is_authenticated/is_anonymous — compatibilidade DRF)
│   ├── authentication.py        ← TokenAuthentication (lê "Authorization: Token <valor>", popula request.user)
│   ├── permissions.py           ← IsAdminRole (reusado por auditoria/)
│   └── views.py                 ← login/logout (regenera/invalida auth_token), CRUD instrumentado via auditoria.utils.registrar()
├── auditoria/                   ← Log de auditoria (login, CRUD de usuário, mudança de role/perms) — extensível a outros sistemas críticos
│   ├── models.py                ← LogAuditoria (usuario FK SET_NULL + usuario_nome_snapshot, acao, detalhes JSON, ip, criado_em) ·
│   │                               PresencaEdicao (heartbeat de "quem está vendo/editando agora" — usuario/model/objeto_id,
│   │                               unique_together, atualizado_em auto_now)
│   ├── utils.py                 ← registrar(usuario, acao, detalhes=None, request=None) — único ponto de escrita, nunca lança exceção ·
│   │                               ator_ou_none(request) — helper pra actions oportunistas/mixins (usuario autenticado ou None)
│   ├── mixins.py                ← AuditoriaDestroyMixin (destroy() → registro_excluido, traduz ProtectedError em 400 amigável) ·
│   │                               AuditoriaCreateMixin (perform_create() → registro_criado) ·
│   │                               AuditoriaUpdateMixin (perform_update() → registro_atualizado, só campos alterados do payload) ·
│   │                               AuditoriaStatusMixin (log_mudanca_status(obj, de, para) → status_alterado, chamado manualmente
│   │                               em cada action de status)
│   └── views.py                 ← LogAuditoriaViewSet (só leitura, restrito a IsAdminRole) ·
│                                    PresencaHeartbeatView (APIView, POST presenca/ — heartbeat + devolve quem mais está ativo)
├── notificacoes/                ← WhatsApp via Z-API
│   ├── models.py                ← HistoricoMensagem (tipo inclui alerta_pagamento/alerta_entrega, ver eventos/ →
│   │                               "Alertas de Evento") · ConfiguracaoWhatsApp (singleton, inclui validade_orcamento_dias)
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
├── estoque/                     ← Controle de estoque de insumos e produtos + produção + alertas + importação
│   │                               de nota fiscal (Fases 1-8 concluídas; ver "Importação de Nota Fiscal" abaixo)
│   ├── models.py                ← MovimentoEstoque (ledger, fonte única da verdade — ver Padrões Obrigatórios),
│   │                               Producao (executar() debita insumo/credita produto), ConfiguracaoEstoque (singleton),
│   │                               TelefoneAlertaEstoque, AlertaEstoqueEnviado, ConfiguracaoIA (singleton),
│   │                               ImportacaoNotaFiscal, ItemNotaImportada (staging da importação de nota fiscal)
│   ├── signals.py               ← débito automático de estoque na venda (PedidoPDV confirmado, PedidoIFood
│   │                               CONFIRMED — match por nome via `_debitar_produto`, Evento entregue), registrados
│   │                               em `EstoqueConfig.ready()` — ver "Débito Automático de Estoque" abaixo
│   ├── extracao_nota.py         ← cascata de extração de nota fiscal: extrair_xml() (determinístico),
│   │                               extrair_texto_pdf() (heurística best-effort via pypdf + regex),
│   │                               extrair_ia() (chama claude_client, nunca lança exceção),
│   │                               resolver_materia_prima() (fuzzy match, mesmo padrão de importar_planilha.py)
│   ├── claude_client.py         ← chamada HTTP pura (requests, sem SDK) à API Claude pro fallback de IA
│   │                               multimodal — mesmo padrão de notificacoes/zapi_client.py (ClaudeAPIError,
│   │                               timeout obrigatório, base64 inline no JSON)
│   ├── views.py                 ← MovimentoEstoqueViewSet (só leitura + filtros), RegistrarCompraView,
│   │                               AjusteInventarioView, ProducaoViewSet (list/create + preview/),
│   │                               ConfiguracaoEstoqueViewSet, TelefoneAlertaEstoqueViewSet,
│   │                               ConfiguracaoIAViewSet, ImportacaoNotaFiscalViewSet (create() roda a cascata,
│   │                               editar-item/, confirmar/, descartar/)
│   └── management/commands/alertar_estoque_baixo.py ← cron diário: alerta a equipe (WhatsApp) sobre insumo/produto
│                                     com quantidade_estoque abaixo de estoque_minimo
├── relatorios/                  ← Relatórios consolidados por canal
│   ├── views.py                 ← RelatorioIFoodView (resumo + agrupado por dia/mês, export Excel/PDF)
│   └── urls.py                  ← ifood/ (mais canais a adicionar conforme necessário)
├── dashboard/                    ← Dashboard multi-canal (só leitura, sem models próprios)
│   ├── views.py                 ← DashboardResumoView (APIView, GET) — agrega PedidoUnificado (iFood/PDV)
│   │                               + PagamentoEvento/Evento (eventos) num único JSON, ver regras abaixo
│   │                               (inclui `alertas`: mesma janela de eventos.ConfiguracaoAlertaEvento, sem
│   │                               depender de AlertaEventoEnviado — mostra "o que está na janela agora")
│   └── urls.py                  ← resumo/
└── manage.py

arretado-crm/                    ← raiz React
└── src/
    ├── api/
    │   ├── client.js            ← axios base
    │   └── services.js          ← clientesApi, tagsApi, ifoodApi, pdvApi, pedidosApi,
    │                               eventosApi, locaisEventoApi, orcamentosApi, contratosApi, configContratoApi,
    │                               alertasEventoApi (config + telefones.list/create/remove — ver "Alertas de Evento"),
    │                               notificacoesApi, usuariosApi, authApi, fichasApi,
    │                               taxasEntregaApi, configEntregaApi, relatoriosApi, dashboardApi, auditoriaApi,
    │                               presencaApi (heartbeat de presença — ver Padrões Obrigatórios),
    │                               estoqueApi (movimentos, registrarCompra, ajusteInventario, producoes,
    │                               configuracao, telefonesAlerta)
    ├── utils/
    │   └── auditoriaResumo.js   ← ACAO_LABEL/ACAO_COR/dataFmt/resumo — extraído de Auditoria.jsx,
    │                               reusado também pela aba/seção "Histórico" no modal de Orçamento/Evento
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
    │   ├── Estoque.jsx          ← controle de estoque (4 abas: Insumos, Produtos, Produção, Movimentações) +
    │   │                          modais Registrar Compra (manual), Ajuste de Inventário, Configurações
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
    │   └── ui/                  ← Btn, Modal, Spinner, Avatar, etc. · PresencaAtiva.jsx (badge "Fulano também
    │                               está vendo isso agora", heartbeat a cada 15s via presencaApi — usado no
    │                               modal de detalhe de Orçamento e Evento)
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
- **ConfiguracaoWhatsApp é singleton** — sempre acessado via `ConfiguracaoWhatsApp.get()`. Contém credenciais Z-API, toggles de notificação, templates de mensagem e `validade_orcamento_dias` (prazo padrão de validade de orçamentos, configurável em Configurações). `GET/PATCH /notificacoes/configuracao/` exigem login (o GET expõe `zapi_token`/`zapi_client_token` em texto puro, então diferente das outras duas configs singleton — aqui até a leitura exige `IsAuthenticated`, não só a escrita) e o PATCH audita `config_whatsapp_alterada` em `auditoria.LogAuditoria` (valores dos 3 campos de credencial nunca vão pro log em texto puro, ficam mascarados como `"***"`)
- **fichas.ParametrosNegocio é singleton** — sempre acessado via `ParametrosNegocio.get()`, nunca instanciado diretamente. `PATCH /fichas/parametros/1/` exige login e audita `parametros_negocio_alterados` (antes/depois dos campos alterados) em `auditoria.LogAuditoria`
- **FichaTecnica → pdv.Produto** é uma FK fraca via `produto_pdv_id` (IntegerField, não ForeignKey) — o produto pode existir sem ficha e vice-versa
- **SnapshotPrecos** é gravado automaticamente antes de qualquer `AjusteLinear` com `confirmar=True`. Aplicar o ajuste (`confirmar=true`) e desfazê-lo (`DesfazerAjusteView`) exigem login e auditam `ajuste_linear_aplicado`/`ajuste_linear_desfeito` — o preview (`confirmar=false`) continua `AllowAny`, já que não altera nada
- **pdv.ConfiguracaoEntrega é singleton** — sempre acessado via `ConfiguracaoEntrega.get()`. Guarda o `frete_padrao` usado quando a entrega é por bairro mas nenhum bairro cadastrado foi selecionado. `PATCH /pdv/configuracao-entrega/1/` exige login e audita `config_entrega_alterada` (GET continua `AllowAny`)
- **`pdv.TaxaEntregaBairro`** é a tabela configurável de bairro→taxa usada por PDV e Orçamentos/Eventos. Nunca hardcodar valor de frete no código — ver `FRETE.md` para o funcionamento completo do sistema de entrega
- **`pdv.Produto.tipo`** (`fabricado`/`revenda`/`kit`) define de onde vem o custo (`Produto.custo`, propriedade polimórfica): `fabricado` deriva de `FichaTecnica.custo_total_unitario` (via `produto_pdv_id`, mesma FK fraca já documentada); `revenda` deriva de `materia_prima_origem.custo_unitario` (só preenchível quando `tipo == 'revenda'`, validado no serializer); `kit` soma `custo * quantidade` de cada `ItemKit` em `itens_kit`. `margem_desejada_pct` é opcional e só sugere preço de venda (`preco_sugerido_revenda`) — nunca substitui o campo `preco`, que continua sendo o preço efetivo de venda
- **`pdv.ItemKit`** não pode conter kit-de-kit (`componente.tipo == 'kit'` é rejeitado tanto no `clean()` do model quanto no `ItemKitSerializer.validate_componente`) nem um kit se auto-referenciando
- **`pdv.FaixaPreco`** guarda preço por quantidade mínima e canal opcional (`pdv`/`ifood`/`eventos`/vazio=todos). `Produto.preco_para(quantidade, canal)` resolve a prioridade: faixa específica do canal > faixa geral (`canal=null`) > `preco` base. Nunca hardcodar desconto por quantidade no frontend — sempre resolver via essa property/endpoint
- **`pdv.DadosFiscaisProduto`** é opcional (`OneToOneField` de `Produto`, aninhado e gravável via `ProdutoSerializer.dados_fiscais` com `update_or_create`) e prepara o cadastro para NFC-e futura — ainda não é consumido por nenhuma integração fiscal real (ver pendência de NFC-e)
- **Estoque** (app `estoque/`, fases 1-8 do spec concluídas, incluindo importação de nota fiscal — ver "Importação de Nota Fiscal" abaixo) — controla saldo físico de 3 naturezas: `fichas.MateriaPrima` (campos novos `quantidade_estoque`/`estoque_minimo`), `pdv.Produto` tipo `fabricado` (campo novo `modo_estoque`: `'estoque'` mantém saldo próprio via `Producao`; `'sob_encomenda'` nunca acumula saldo, debita insumo direto na venda) e `pdv.Produto` tipo `revenda` (sempre equivalente a `'estoque'`). `pdv.Produto` tipo `kit` nunca tem saldo próprio — é sempre virtual, decrementa cada `ItemKit.componente` recursivamente. **Política de saldo negativo: sempre permitido** — nenhuma venda/produção/ajuste é bloqueada por saldo insuficiente, o sistema só alerta a equipe (nunca reconsiderar essa regra item a item)
- **`estoque.MovimentoEstoque` é o ledger — fonte única da verdade.** Todo movimento passa por `MovimentoEstoque.registrar()` (nunca `.objects.create()` direto em view/signal/command), que valida exatamente 1 de `materia_prima`/`produto` preenchido, calcula `saldo_posterior` dentro de `transaction.atomic()` com `select_for_update()` (evita race condition entre vendas concorrentes do mesmo item), e atualiza `quantidade_estoque` via `update_fields`. `tipo_movimento='ajuste_inventario'` é o único caso onde `quantidade` é o **saldo absoluto** (contagem física), não um delta. `registrar()` também quantiza `quantidade` (3 casas) e `custo_unitario_snapshot` (4 casas) antes de gravar — consumo calculado por proporção (`item.quantidade * (produzido/rendimento)`) ou `custo_unitario` (divisão não arredondada) frequentemente saem com mais casas decimais do que o `DecimalField` do model aceita; sem quantizar ali, `full_clean()` derruba o movimento com `ValidationError` (bug real encontrado e corrigido durante o desenvolvimento — ver commit desta feature)
- **`estoque.Producao.executar()`** só é permitida quando a `FichaTecnica` tem `produto_pdv_id` vinculado a um `pdv.Produto` com `modo_estoque == 'estoque'` — debita cada insumo da ficha proporcionalmente (`item.quantidade * (quantidade_produzida/rendimento)`) e credita o saldo do produto, os dois via `MovimentoEstoque.registrar()`, dentro da mesma transação
- **Débito Automático de Estoque** (`estoque/signals.py`, registrado em `EstoqueConfig.ready()`, mesmo padrão de `pdv/signals.py`) — 3 signals `post_save` (sender como string, evita import circular): `pdv.PedidoPDV` ao entrar em status `'confirmado'`; `ifood.PedidoIFood` ao entrar em `'CONFIRMED'` (`ItemPedidoIFood` não tem FK pra `Produto`, só nome em texto — resolve por fuzzy match `iexact`→`icontains`, mesmo padrão de `importar_planilha.py`; sem correspondência, só loga `logger.warning` e pula o item, nunca bloqueia o pedido); `eventos.Evento` ao entrar em `'entregue'` (não existe status por item, só do Evento pai). Todos checam `MovimentoEstoque.objects.filter(origem_tipo=..., origem_id=...).exists()` antes de debitar — **idempotência obrigatória**, já que `post_save` dispara em todo `.save()`, não só na transição de status. Helper comum `_debitar_produto()` aplica a regra polimórfica (revenda/fabricado-estoque → débito direto; fabricado-sob_encomenda → débito direto nos insumos da ficha, sem passar por `Producao`; kit → recursivo em `ItemKit`). Estorno automático em cancelamento pós-débito é **fora de escopo** (decisão consciente — ajuste manual de inventário cobre o caso)
- **Alertas de Estoque Baixo** (`estoque.ConfiguracaoEstoque` singleton via `.get()`, `estoque.TelefoneAlertaEstoque`, `estoque.AlertaEstoqueEnviado`) — mesmo padrão de "Alertas de Evento": cron diário (`python manage.py alertar_estoque_baixo`) notifica só telefones internos da equipe sobre `MateriaPrima`/`Produto` com `quantidade_estoque < estoque_minimo` (e `estoque_minimo > 0`), via `notificacoes.servico.notificar()`. Card "Estoque" no Dashboard (`dashboard/views.py::_estoque()`) mostra a mesma contagem, independente de já ter alertado
- **Importação de Nota Fiscal** (fases 6-8, `POST /api/v1/estoque/notas/` — endpoint é o `create()` padrão do `ImportacaoNotaFiscalViewSet`, **não** `/notas/importar/`) — upload de arquivo (XML/PDF/imagem) roda a cascata de extração em `estoque/extracao_nota.py`: `extrair_xml()` (determinístico, parseia `det/prod` da NF-e via `xml.etree.ElementTree` com remoção de namespace) → `extrair_texto_pdf()` (heurística best-effort via `pypdf.extract_text()` + regex, pode falhar em DANFEs complexos — ver Pendências) → `extrair_ia()` (fallback multimodal via `estoque/claude_client.py`, precisa de `ANTHROPIC_API_KEY` no `.env` — ver Pendências). Cada camada devolve `None` em vez de lançar exceção quando não consegue extrair nada; se as 3 falharem, `metodo_extracao='falhou'` e a tela de revisão abre vazia (nunca trava o fluxo). Depois da extração, cada item passa pelo fuzzy match de `resolver_materia_prima()` (`iexact` → `icontains`, mesmo padrão de `importar_planilha.py`) — **nunca cria `MateriaPrima` automaticamente** aqui (diferente do fuzzy match de débito automático da venda), sempre marca `status_match='revisar'` e espera a revisão manual. `estoque.ImportacaoNotaFiscal`/`ItemNotaImportada` são staging — nenhum `MovimentoEstoque` é gravado até `POST /notas/{id}/confirmar/`, que rejeita (400) se algum item não descartado ainda estiver `status_match='revisar'`. `PATCH /notas/{id}/itens/{item_id}/` aceita `{materia_prima}`/`{produto}` (correspondência manual), `{criar_nova_materia_prima: true}` (usa `descricao_extraida` como `nome` via `get_or_create`, `quantidade`/`valor_unitario` reais da nota populam `quantidade_compra`/`valor_compra` — dado real, não placeholder) ou `{quantidade, valor_unitario, descartado}` editados
- **`estoque.ConfiguracaoIA`** é singleton (`.get()`) — guarda `extracao_ia_ativa`/`modelo`/`timeout_segundos`. A API key (`ANTHROPIC_API_KEY`) **nunca** fica no model/banco, só em variável de ambiente — é key da Ortex, custo embutido do lado do Ortex (mesma decisão de negócio documentada no spec original). `PATCH /estoque/configuracao-ia/1/` exige login e audita `config_ia_alterada`
- **`eventos.ConfiguracaoContrato` é singleton** — sempre acessado via `ConfiguracaoContrato.get()`. Guarda razão social/CNPJ/endereço/Instagram/telefone/representante da CONTRATADA e todos os percentuais/prazos das cláusulas (sinal, multa, juros, prazos de personalização/rescisão/devolução, foro). `instagram_contratada`/`telefone_contratada` aparecem no rodapé do PDF (`pdf_contrato.py::_header_footer`), abaixo da linha razão social/CNPJ. Nunca hardcodar cláusula numérica no gerador de PDF — ver `Contrato.md`. `PATCH /eventos/configuracao-contrato/1/` exige login e audita `config_contrato_alterada` (GET continua `AllowAny`)
- **`eventos.Contrato`** é um snapshot gravado no momento da emissão (mesma filosofia de `ItemOrcamento`/`SnapshotPrecos`) — `valor_total`/`percentual_sinal`/`valor_sinal`/`data_quitacao` nunca são recalculados ao reabrir/reimprimir um contrato já emitido
- **Alertas de Evento** (`eventos.ConfiguracaoAlertaEvento`, singleton via `.get()`) — dois alertas de cron diário (`python manage.py alertar_eventos`), notificando só telefones internos da equipe cadastrados em `eventos.TelefoneAlertaEvento` (nunca o cliente): (1) **pagamento pendente**, dispara a partir de `dias_antes_pagamento` dias antes do `data_evento` enquanto `saldo_restante > 0` (`Evento.exclude(status__in=['cancelado','entregue']).annotate(saldo=F('valor_total')-F('sinal_pago')).filter(saldo__gt=0, ...)` — usa `F()` em vez da property Python `saldo_restante`, que não funciona em queryset); (2) **aviso de entrega**, a partir de `dias_antes_entrega` dias antes, só para `tipo_entrega='entrega_local'`. Ambos repetem a cada `repetir_pagamento_dias`/`repetir_entrega_dias` configurável, controlado por `eventos.AlertaEventoEnviado` (1 registro por envio de `(evento, tipo)`, não reaproveita `notificacoes.HistoricoMensagem` pra isso porque `HistoricoMensagem.cliente` é FK pra `Cliente`, não pra `Evento`, e aqui o destinatário é telefone da equipe). `PATCH /eventos/configuracao-alertas/1/` exige login e audita `config_alerta_evento_alterada` (GET continua `AllowAny`); `DELETE /eventos/telefones-alerta/{id}/` exige login e audita `registro_excluido` (mesmo padrão do `TaxaEntregaBairro` — só o DELETE exige login, list/create/update continuam `AllowAny`). O texto das mensagens é fixo no código (não é campo configurável como `mensagem_aniversario`/`mensagem_reengajamento` de `ConfiguracaoWhatsApp`) — só dias/intervalo/telefones são configuráveis, por escolha consciente de escopo. `dashboard.DashboardResumoView` expõe a mesma janela em `resumo['alertas']` (sem olhar `AlertaEventoEnviado` — mostra "o que está na janela agora", independente de já ter mandado WhatsApp)
- **Emissão de contrato** (`POST /eventos/orcamentos/{id}/gerar-contrato/`) só é permitida com `Orcamento.status == 'aprovado'` e exige CPF/RG/nacionalidade/profissão/estado civil do cliente preenchidos (podem estar vazios no cadastro normal — são exigidos só neste momento) — ver `Contrato.md`. Exige login (`IsAuthenticated`, único override de `get_permissions()` no `OrcamentoViewSet` — resto continua `AllowAny`) e grava `contrato_emitido` em `auditoria.LogAuditoria`. `ContratoViewSet.enviar_whatsapp` também exige login (`contrato_enviado` no log) — `list`/`retrieve`/`pdf` continuam `AllowAny`, sem mudança
- **Reenvio de Contrato** — `enviar-whatsapp/` (acima) **não trava por status** de orçamento/evento/contrato (`Contrato.pode_enviar` existe no model mas não é usado por nenhuma view — código morto hoje), então o mesmo endpoint serve tanto para o envio inicial quanto para reenvios. `OrcamentoListSerializer`/`EventoListSerializer` expõem `contrato` (via `ContratoResumoSerializer`: id/numero/status/status_display/contratante_nome — o mais recente, resolvido com `prefetch_related('contratos')` nas duas viewsets). O frontend (`Orcamentos.jsx`/`Eventos.jsx`) mostra um botão "Reenviar Contrato" na coluna de ações da listagem e no modal de detalhe sempre que esse campo não é nulo, abrindo `ModalReenviarContrato` (componente local em cada página) que chama o mesmo `POST /eventos/contratos/{id}/enviar-whatsapp/`
- **`eventos.ImagemInspiracao`** é a galeria de imagens de referência (uso interno da equipe, nunca entra no PDF/WhatsApp do orçamento) anexada ao `Orcamento` inteiro (não por item). `Evento` **não duplica** essas imagens — `EventoDetailSerializer.imagens_inspiracao` é um `SerializerMethodField` que lê direto de `evento.orcamento_origem.imagens_inspiracao` (mesma filosofia de nunca duplicar o que a relação já entrega, como o Contrato faz com os itens do Orçamento)
- **`MEDIA_URL`/`MEDIA_ROOT`** estão configurados em `config/settings.py` (`/media/`, `BASE_DIR / 'media'`) desde a feature de Imagens de Inspiração — é o único `ImageField` do projeto de fato exercitado em produção. Em prod, o Nginx tem um `location /media/ { alias .../media/; }` próprio (não é servido pelo Django/Gunicorn) — qualquer novo `ImageField`/`FileField` já pode reaproveitar essa infra, não precisa recriar
- **Cuidado com `prefetch_related` + criação de objeto relacionado na mesma request**: se uma view faz `self.get_object()` sobre um queryset com `prefetch_related('algo')` e, na mesma request, cria/deleta um objeto relacionado via `Model.objects.create(fk=obj, ...)` (sem passar pelo manager `obj.algo`), o cache do prefetch fica stale e `obj.algo.all()` (inclusive dentro do serializer) não reflete a mudança. Sempre que fizer isso, chamar `obj.refresh_from_db()` antes de serializar a resposta. Já corrigido em `adicionar_imagens`/`remover_imagem` (`OrcamentoViewSet`), `adicionar_pagamento` (`EventoViewSet`), e — bug real reportado por usuário, reproduzido e corrigido — em `adicionar_item`/`remover_item`/`editar_item` de `OrcamentoViewSet`/`EventoViewSet` e `PedidoPDVViewSet`, e em `adicionar_item`/`remover_item` de `FichaTecnicaViewSet`: sem o `refresh_from_db()`, `recalcular_totais()` lia o cache velho de `self.itens.all()` e **persistia** `valor_total`/`total` errado no banco (não era só um problema de exibição — o valor incorreto ficava salvo até a próxima alteração). Qualquer novo endpoint que crie/edite/remova item de uma coleção prefetched e recalcule um total a partir dela precisa do mesmo cuidado
- **`FichaTecnica.custo_ingredientes`** usa `sum(..., Decimal('0'))` com `start` explícito — não tirar esse `start`. `sum()` de um iterável vazio (ficha sem nenhum item) devolve o `int` `0` por padrão; `0 / self.rendimento` em Python 3 é *true division* e vira `float`, e `float + Decimal` (o `embalagem_custo`) explode com `TypeError` em `custo_total_unitario`. Bug real encontrado ao corrigir o `refresh_from_db()` acima (remover o último item de uma ficha passou a de fato zerar `itens.all()`, o que expôs esse cálculo)
- **`auditoria.mixins.AuditoriaDestroyMixin`** — mixin genérico pra auditar o `destroy()` padrão de um `ModelViewSet`: grava `ACAO_REGISTRO_EXCLUIDO` (com `detalhes.model`/`id`/`descricao` + campos extras via `campos_log_exclusao`) e traduz `ProtectedError` (FK `on_delete=PROTECT`) numa resposta 400 amigável em vez do 500 cru do Django. Usar em qualquer novo `ModelViewSet` que precise de DELETE auditado — já aplicado em `Cliente`, `Tag`, `Produto`, `CategoriaProduto`, `TaxaEntregaBairro`, `PedidoPDV`, `Evento`, `Orcamento`, `LocalEvento`, `MateriaPrima`, `FichaTecnica`. A view precisa combinar com `authentication_classes = [TokenAuthentication]` + `get_permissions()` exigindo `IsAuthenticated` na action `destroy` (e nas `remover-*` correspondentes, instrumentadas manualmente com `registrar()` direto, já que não passam por `perform_destroy`). Endpoint `GET /api/v1/auditoria/logs/?model=Cliente` filtra por `detalhes.model`
- **`auditoria.mixins.AuditoriaCreateMixin`/`AuditoriaUpdateMixin`/`AuditoriaStatusMixin`** — mesma filosofia do `AuditoriaDestroyMixin`, hoje aplicados só em `OrcamentoViewSet`/`EventoViewSet` (não em todos os ModelViewSets — só onde criação/edição/status faz sentido auditar). `AuditoriaCreateMixin.perform_create()` grava `ACAO_REGISTRO_CRIADO`; `AuditoriaUpdateMixin.perform_update()` grava `ACAO_REGISTRO_ATUALIZADO` só com os campos de `campos_log_atualizacao` que vieram no payload E mudaram de valor (antes/depois, mesmo padrão das configs singleton). Para usar `AuditoriaUpdateMixin` num `update()` já customizado (como o do `OrcamentoViewSet`, que valida status antes de salvar), a view precisa chamar `self.perform_update(serializer)` em vez de `serializer.save()` direto — mesmo raciocínio vale para `create()`/`self.perform_create(serializer)`. `AuditoriaStatusMixin.log_mudanca_status(obj, de, para)` não é automático — chamar manualmente dentro de cada `@action` de mudança de status, depois do `.save()`; grava `ACAO_STATUS_ALTERADO` genérico (desambiguado por `detalhes.model`, mesmo espírito do `registro_excluido`). Adicionar item usa `ACAO_ITEM_ADICIONADO` (também genérico, cobre `ItemOrcamento` e `ItemEvento`). A conversão de Orçamento em Evento é o único marco de negócio com constante própria: `ACAO_ORCAMENTO_CONVERTIDO`
- **`auditoria.PresencaEdicao`** (heartbeat de presença, `POST /api/v1/auditoria/presenca/` via `PresencaHeartbeatView`) — **não é WebSocket**: é polling REST comum (frontend chama a cada 15s enquanto o modal de Orçamento/Evento estiver aberto), decisão deliberada porque o projeto roda só Gunicorn/WSGI síncrono, sem Channels/Redis/ASGI. O endpoint faz `update_or_create` da presença do usuário autenticado e devolve quem mais está ativo no mesmo `(model, objeto_id)` numa janela de 40s (`JANELA_PRESENCA_SEGUNDOS` em `auditoria/views.py`). `unique_together=('usuario','model','objeto_id')` garante no máximo 1 linha por combinação — a tabela cresce por usuário×objeto já visitado, não por heartbeat, então não precisa de limpeza periódica por ora. É só informativo ("Fulano também está vendo isso agora") — não é uma trava/lock de edição
- **`ifood.ConfiguracaoIFood` não é singleton de verdade** (usa `.objects.first()`, não `.get()`) — `ConfiguracaoIFoodViewSet.destroy()` está bloqueado de propósito (sempre `405`), pra nunca perder client_id/secret/tokens de produção. Se um dia virar singleton de verdade (`.get()` como os outros 3 configs), reavaliar se ainda faz sentido bloquear o DELETE
- **`eventos.PagamentoEvento`** registra as parcelas de pagamento de um `Evento` (valor/forma_pagamento/status/data_pagamento/observação/comprovante). `comprovante` é um `FileField` opcional (imagem ou PDF) enviado no momento do registro do pagamento (`multipart/form-data`, mesmo padrão de `ImagemInspiracao`/`ImageField` de produto — ver upload de `FormData` no frontend). `Evento.sinal_pago` **nunca** é gravado direto — é sempre recalculado via `Evento.recalcular_sinal_pago()` (soma dos pagamentos com `status='pago'`), chamado após criar/remover um `PagamentoEvento` (`POST/DELETE /eventos/{id}/pagamentos/...`). O sinal informado na criação do Evento ou na conversão de Orçamento em Evento (`sinal_pago` no body) também vira um `PagamentoEvento` inicial (forma `outro`, status `pago`) em vez de setar o campo diretamente. Toda criação/remoção de `PagamentoEvento` é auditada via `auditoria.utils.registrar()` — nas actions dedicadas (`adicionar_pagamento`/`remover_pagamento`) o login é obrigatório; no sinal inicial (criação do Evento ou conversão do Orçamento) é oportunista, sem bloquear o fluxo se ninguém estiver logado
- **Edição de Orçamento**: `OrcamentoViewSet.update()` só permite `PATCH/PUT` quando `status` é `rascunho` ou `enviado` (400 caso contrário); mesma restrição vale para editar item (`PATCH /eventos/orcamentos/{id}/itens/{item_id}/editar/`). Depois de aprovado/enviado além desses estágios, o orçamento é imutável (mesma filosofia do `Contrato` como snapshot)
- **Resumo de Cozinha** (`GET /eventos/{id}/resumo-cozinha/`, `eventos/pdf_resumo_cozinha.py::gerar_pdf_resumo_cozinha(evento)`) — PDF operacional interno (não client-facing) com a lista de itens do Evento agrupada por categoria, pra a cozinha montar a produção. Usa ReportLab **Platypus** (não canvas cru como `pdf_orcamento.py`), porque a lista de itens tem tamanho variável e pode quebrar página — e **sem** timbre/marca d'água (`_mesclar_timbre` nunca é chamado aqui). Itens são ordenados por `produto__categoria__ordem`/`produto__categoria__nome`/`nome` na própria query e agrupados em memória com `itertools.groupby` (nunca reordenar em Python depois) — item sem `produto` ou cujo `produto` não tem `categoria` cai no grupo `"Outros"`, sempre por último (a ordenação por `ordem` já garante isso via `NULLS LAST` do Postgres, então o agrupamento em Python não precisa reordenar nada). **Nunca expõe preço** (`preco_unit`/`preco_total`/`valor_total`) — é 100% operacional. Todo texto livre (nome do cliente, endereço do local, observação do item/evento) passa por `xml.sax.saxutils.escape()` antes de virar `Paragraph`, porque a mini-sintaxe XML do ReportLab quebra a geração do PDF se o texto tiver `&`/`<`/`>` sem escapar. Endpoint é `AllowAny` (mesmo padrão de `OrcamentoViewSet.pdf`/`ContratoViewSet.pdf` — é leitura pura, não audita). Botão "Imprimir resumo de cozinha" (`ti-printer`) em dois lugares no frontend — card de detalhe do Evento e linha da lista — ambos chamando `eventosApi.resumoCozinha(id)` (blob) e abrindo com `window.open(url, '_blank')`, mesmo padrão de `handlePdf`/`handleVerPdf` já usado pros outros PDFs do sistema
- **Criação/edição/status/item de Orçamento e Evento exigem login** (`create`, `update`/`partial_update`, `enviar`/`aprovar`/`recusar`/`restaurar` no Orçamento, `confirmar`/`iniciar_producao`/`marcar_pronto`/`entregar`/`cancelar` no Evento, `adicionar_item`/`editar_item`) — mudança de comportamento em relação ao que existia antes desta auditoria (essas actions eram `AllowAny`). Único motivo de exigir login aqui é garantir que sempre exista um ator no log; `converter_em_evento` e `enviar_whatsapp` continuam `AllowAny` de propósito (oportunistas, capturam o ator só quando o token vier)
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
- **Upload de arquivo/imagem via axios**: `api/client.js` fixa `headers: {'Content-Type': 'application/json'}` na instância do axios, e isso **não** é sobrescrito automaticamente quando o corpo é um `FormData` — sem correção, o navegador não define o boundary do multipart e o backend recebe a requisição sem o arquivo (`request.FILES` vazio). Sempre que enviar `FormData`, passar `{ headers: { 'Content-Type': undefined } }` na chamada (ver `orcamentosApi.adicionarImagens`, `pdvApi.updateFoto` e `eventosApi.adicionarPagamento` — este último condicional, só monta `FormData` quando há arquivo de comprovante anexado — em `services.js`) para o navegador definir o header correto.
- **Lightbox de imagem ampliada**: padrão usado em `Orcamentos.jsx`/`Eventos.jsx` para a galeria de `imagens_inspiracao` — clique na thumbnail abre um overlay `position: fixed` (z-index 400, acima do Modal que é 200) com a imagem em `object-fit: contain`, fecha no clique fora ou no X. Reaproveitar esse padrão para qualquer nova galeria de imagens.
- **Confirmação antes de enviar WhatsApp**: todo `handleEnviar*` que dispara `enviarWhatsApp` (orçamento e contrato — envio inicial ou reenvio, em `Orcamentos.jsx` e `Eventos.jsx`) abre um `window.confirm()` com nome/telefone do destinatário antes de chamar a API, pra evitar disparo acidental. Reaproveitar esse padrão em qualquer novo envio de WhatsApp disparado por clique direto de botão.
- **Modal de emitir contrato não fecha sozinho após gerar**: `onGerado` (callback passado a `ModalEmitirContrato`/`ModalEmitirContratoEvento`) deve só recarregar a listagem/detalhe — nunca fechar o modal. O modal só fecha pelo botão "Fechar" explícito do usuário, depois que ele já viu o PDF e/ou enviou por WhatsApp na mesma tela (bug real corrigido em `Eventos.jsx`: o `onGerado` chamava `setEmitirEvento(null)` e fechava o modal antes do usuário conseguir ver o contrato recém-criado).

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
| Catálogo — Revenda/Kit/Faixas de Preço | `Produto.tipo` (fabricado/revenda/kit) com custo polimórfico, `ItemKit`, `FaixaPreco` (quantidade/canal), `DadosFiscaisProduto` (prepara NFC-e), redesign do `Catalogo.jsx` em cards | ✅ Concluída |
| Frete por Bairro | Cálculo de taxa de entrega por bairro no PDV e Orçamentos/Eventos + frete padrão configurável + cadastro de Locais de Evento | ✅ Concluída (ver `FRETE.md`) |
| Relatórios | Relatório consolidado iFood (resumo, agrupamento por dia/mês, export Excel/PDF) — app `relatorios/` | ✅ Concluída (apenas canal iFood por enquanto) |
| Contrato | Emissão de Contrato de Aquisição de Produtos a partir de Orçamento aprovado (PDF com cláusulas configuráveis + envio por WhatsApp) + reenvio por WhatsApp direto da listagem/detalhe de Orçamentos e Eventos (reaproveita o mesmo endpoint `enviar-whatsapp/`) | ✅ Concluída (ver `Contrato.md`) |
| Imagens de Inspiração | Galeria de imagens de referência anexada ao Orçamento (upload múltiplo, lightbox, uso interno, visível também no Evento após conversão) | ✅ Concluída |
| Pagamentos Parciais de Evento | `eventos.PagamentoEvento` (parcelas), `Evento.sinal_pago` derivado, redesign do modal de detalhe do Evento (stepper + abas), edição de Orçamento antes da conversão | ✅ Concluída |
| Dashboard Multi-Canal | App `dashboard/` (só leitura) — vendas do dia e histórico recente consolidado de iFood/PDV/Eventos (+ espaço reservado pra Anota AI), gráfico 7 dias, a receber, fila operacional, próximos eventos, ticket médio | ✅ Concluída |
| Autenticação Real + Auditoria | Token real (`usuarios/authentication.py`) + app `auditoria/` cobrindo os 6 itens da lista priorizada: usuários (login/CRUD/permissões), pagamentos de evento, contrato, Central de Preços, configurações singleton (`ConfiguracaoContrato`/`ConfiguracaoEntrega`/`ConfiguracaoWhatsApp` — esta última também exige login no GET, já que expõe credencial Z-API) e exclusões em geral (`AuditoriaDestroyMixin` genérico, aplicado em `Cliente`/`Tag`/`Endereco`/`Produto`/`CategoriaProduto`/`TaxaEntregaBairro`/`PedidoPDV`/`Evento`/`Orcamento`/`LocalEvento`/`MateriaPrima`/`FichaTecnica` e os respectivos `remover-item`; `ConfiguracaoIFood` teve o DELETE bloqueado de vez, não só auditado) — tela restrita a `role=admin` | ✅ Concluída (lista completa) |
| Auditoria de Criação/Edição/Status + Presença + Histórico no Modal | Extensão da auditoria de Orçamento/Evento: criação, edição (PATCH/PUT), mudança de status e adicionar/editar item agora também são auditados (`AuditoriaCreateMixin`/`AuditoriaUpdateMixin`/`AuditoriaStatusMixin`), exigindo login nessas ações (antes eram `AllowAny`). Presença via heartbeat REST (`auditoria.PresencaEdicao`, `PresencaAtiva.jsx`, polling a cada 15s — não WebSocket) mostrando quem mais está vendo o registro agora. Aba/seção "Histórico" dentro do próprio modal de detalhe (`historico/` em `OrcamentoViewSet`/`EventoViewSet`, `IsAuthenticated` — diferente da tela de Auditoria geral, que é restrita a admin) | ✅ Concluída |
| Alertas de Evento (pagamento pendente / entrega próxima) | Cron diário (`alertar_eventos`) alerta telefones internos da equipe via WhatsApp sobre Evento com saldo pendente perto da data (configurável) e sobre entrega se aproximando (configurável, repete a cada X dias) — `ConfiguracaoAlertaEvento`/`TelefoneAlertaEvento`/`AlertaEventoEnviado`, seção "Alertas de Evento" em Configurações, card "Alertas" no Dashboard | ✅ Concluída |
| Estoque — Fases 1-5 (modelos base, entrada manual/ajuste, produção, débito automático na venda, alertas) | App `estoque/` — `MovimentoEstoque` (ledger), `Producao`, campos novos em `MateriaPrima`/`Produto`, débito automático via signals (PDV/iFood/Eventos), alertas de estoque baixo (`ConfiguracaoEstoque`/`TelefoneAlertaEstoque`/`AlertaEstoqueEnviado`), tela `Estoque.jsx` (4 abas), card "Estoque" no Dashboard | ✅ Concluída (fases 1-5) |
| Estoque — Fases 6-8 (importação de nota fiscal: XML/PDF/IA) | Cascata de extração (XML da NF-e → texto de PDF → IA multimodal), staging (`ImportacaoNotaFiscal`/`ItemNotaImportada`), tela de revisão, fuzzy match, filtros de período/tipo na aba Movimentações | ✅ Concluída |
| Resumo de Cozinha (Evento) | PDF operacional (A4 página cheia, ReportLab Platypus, sem timbre) com itens do Evento agrupados por categoria, pra a equipe de cozinha montar a produção — sem preços. Botão em `Eventos.jsx` (card de detalhe + linha da lista) | ✅ Concluída (só A4 página cheia — meia-folha/térmica fora de escopo por ora) |

---

## Pendências Ativas

1. **Anota AI (Fase 3-ext-B)** — criar app `anotaai/` seguindo o padrão de `pdv/`
2. **Fichas técnicas incompletas** — 3 ingredientes com custo zero na planilha original (`Cobertura cappucino`, `Folha decorativa`, `Castanha do Pará`, `Ameixa`) e `Brigadeiro Sensacional` sem quantidades
3. **PDV Hardware (roadmap):**
   - Curto prazo: impressora térmica TCP/IP (Django imprime via socket ESC/POS) + caixa registradora pelo mesmo cabo
   - Médio prazo: NFC-e (nota fiscal — SEFAZ-PI)
   - Longo prazo: TEF integrado
4. **Relatórios cobrem só iFood** — `relatorios/` tem apenas `RelatorioIFoodView`; expandir para PDV e Eventos/Orçamentos seguindo o mesmo padrão (resumo + agrupado + export Excel/PDF)
5. **Logging/observabilidade** — hoje é rudimentar: sem `LOGGING` dict em `config/settings.py` (usa o padrão implícito do Django), sem Sentry/monitoramento de erros. Só alguns apps chamam `logger.info/warning/error` (`notificacoes/`, `ifood/` — bem detalhado em `polling_worker.py`/`ifood_client.py`/`views.py` —, e uns warnings pontuais em `pdv/signals.py`, `eventos/signals.py`, `pedidos/apps.py`, `pedidos/views.py`); `clientes`, `fichas`, `relatorios`, `dashboard` não logam nada. `usuarios` agora grava eventos de segurança/negócio (login, CRUD, mudança de role/perms) em `auditoria.LogAuditoria` via `auditoria/utils.py::registrar()` — isso é **auditoria de negócio** ("quem fez o quê"), não logging operacional (`logger.info/warning/error`); a pendência de `LOGGING` dict/Sentry abaixo continua válida e é um conceito separado. Gunicorn (`arretado.service`) e o worker (`arretado-polling.service`) não redirecionam pra arquivo — tudo vai pro stdout/stderr, só acessível via `journalctl -u arretado`/`journalctl -u arretado-polling` na VPS; sem persistência em arquivo nem rotação. Considerar no futuro: `LOGGING` dict com `RotatingFileHandler`/`TimedRotatingFileHandler` e/ou integração com Sentry
6. **Divergência de receita "hoje" entre o card iFood do Dashboard e o menu iFood** — investigado, causa raiz identificada, correção ainda não decidida com o usuário. Ver `IFOOD_RECEITA_DASHBOARD.md`
7. **Variáveis de ambiente em prod para WhatsApp (Z-API):**
   ```
   ZAPI_INSTANCE_ID=3F44AD8FFA071145A7847A94F00847F6
   ZAPI_TOKEN=664FD7CD1788EFA5660A875F
   ZAPI_CLIENT_TOKEN=<client-token>
   ```
8. **`ANTHROPIC_API_KEY` não configurada em produção** — o fallback de IA da importação de nota fiscal (`estoque/claude_client.py`) já está implementado e testado (mock), mas sem a chave real no `.env` da VPS ele sempre falha graciosamente (`metodo_extracao='falhou'`, cai pra digitação manual). Precisa que o usuário forneça a chave (key da Ortex, custo embutido do lado do Ortex — decisão de negócio, não algo que a IA gera sozinha)
9. **Cascata "texto de PDF" (`estoque/extracao_nota.py::extrair_texto_pdf`) é heurística best-effort** — sem notas fiscais reais de fornecedores da Arretado pra calibrar o regex, pode não reconhecer o layout de DANFEs mais complexos (cai pra IA automaticamente quando isso acontece, nunca trava o fluxo). Revisitar/ajustar a heurística conforme notas reais forem importadas e falharem

---

## Endpoints Principais

```
# Clientes
GET/POST             /api/v1/clientes/
GET/PUT/PATCH/DELETE /api/v1/clientes/{id}/        ← DELETE exige login · audita registro_excluido
GET                  /api/v1/clientes/{id}/historico/
GET/POST             /api/v1/tags/                 ← DELETE (/{id}/) exige login · audita registro_excluido

# iFood
GET  /api/v1/ifood/pedidos/
POST /api/v1/ifood/pedidos/{id}/confirmar/
POST /api/v1/ifood/pedidos/{id}/vincular-cliente/
GET  /api/v1/ifood/config/status/
DELETE /api/v1/ifood/config/{id}/   ← sempre bloqueado (405) — não é singleton de verdade, nunca deletar (ver "O Que NÃO Fazer")

# PDV
GET/POST /api/v1/pdv/pedidos/                       ← DELETE (/{id}/) exige login · audita registro_excluido
GET/POST /api/v1/pdv/produtos/                       ← DELETE (/{id}/) exige login · audita (ProtectedError → 400 se usado em kit)
GET/POST /api/v1/pdv/categorias/                     ← DELETE (/{id}/) exige login · audita registro_excluido
POST     /api/v1/pdv/pedidos/{id}/confirmar/
POST     /api/v1/pdv/pedidos/{id}/concluir/
DELETE   /api/v1/pdv/pedidos/{id}/itens/{item_id}/remover/            ← exige login · audita registro_excluido

# Catálogo — tipo de produto (fabricado/revenda/kit), faixas de preço e dados fiscais
GET    /api/v1/pdv/produtos/{id}/preco/?quantidade=&canal=        ← resolve preço via Produto.preco_para()
POST   /api/v1/pdv/produtos/{id}/faixas-preco/
PATCH  /api/v1/pdv/produtos/{id}/faixas-preco/{faixa_id}/
DELETE /api/v1/pdv/produtos/{id}/faixas-preco/{faixa_id}/remover/ ← exige login · audita registro_excluido
POST   /api/v1/pdv/produtos/{id}/itens-kit/                       ← só quando produto.tipo == 'kit'
DELETE /api/v1/pdv/produtos/{id}/itens-kit/{item_id}/             ← exige login · audita registro_excluido
                                                                    ← dados_fiscais é aninhado e gravável direto no
                                                                      PATCH de /pdv/produtos/{id}/ (campo "dados_fiscais")

# Frete (ver FRETE.md)
GET/POST/PATCH/DELETE /api/v1/pdv/taxas-entrega/[{id}/]     ← cadastro de bairro→taxa · DELETE exige login · audita registro_excluido
GET/PATCH             /api/v1/pdv/configuracao-entrega/1/   ← singleton, campo frete_padrao · PATCH exige login · audita config_entrega_alterada

# Orçamentos
GET/POST      /api/v1/eventos/orcamentos/                               ← POST exige login · audita registro_criado
GET/PATCH/DELETE /api/v1/eventos/orcamentos/{id}/                       ← PATCH exige login, só permitido com status rascunho/enviado, audita registro_atualizado (só campos alterados) · DELETE exige login, audita registro_excluido (400 amigável se já tiver Contrato — PROTECT)
POST          /api/v1/eventos/orcamentos/{id}/enviar/                   ← exige login · audita status_alterado
POST          /api/v1/eventos/orcamentos/{id}/aprovar/                  ← exige login · audita status_alterado
POST          /api/v1/eventos/orcamentos/{id}/recusar/                  ← exige login · audita status_alterado
POST          /api/v1/eventos/orcamentos/{id}/restaurar/                ← exige login · audita status_alterado
POST          /api/v1/eventos/orcamentos/{id}/converter-em-evento/      ← body opcional "sinal_pago" vira 1º PagamentoEvento · continua AllowAny (oportunista) · audita orcamento_convertido_em_evento
POST          /api/v1/eventos/orcamentos/{id}/itens/                    ← exige login · audita item_adicionado
PATCH         /api/v1/eventos/orcamentos/{id}/itens/{item_id}/editar/   ← exige login · só com status rascunho/enviado · audita registro_atualizado
DELETE        /api/v1/eventos/orcamentos/{id}/itens/{item_id}/remover/  ← exige login · audita registro_excluido
POST          /api/v1/eventos/orcamentos/{id}/imagens/                  ← multipart, campo "imagens" (um ou mais arquivos)
DELETE        /api/v1/eventos/orcamentos/{id}/imagens/{imagem_id}/remover/ ← exige login · audita registro_excluido
GET           /api/v1/eventos/orcamentos/{id}/pdf/
GET           /api/v1/eventos/orcamentos/{id}/historico/                ← exige login · trilha de auditoria deste orçamento (não confundir com clientes/{id}/historico/, que é histórico de pedidos)
POST          /api/v1/eventos/orcamentos/{id}/enviar-whatsapp/   ← gera PDF + envia via Z-API + grava HistoricoMensagem + muda status para 'enviado' (continua AllowAny, audita status_alterado de forma oportunista)
POST          /api/v1/eventos/orcamentos/{id}/gerar-contrato/    ← exige login · só com status='aprovado' · body: cpf/rg/rg_orgao_emissor/nacionalidade/profissao/estado_civil/endereco_avulso · audita contrato_emitido

# Contratos (ver Contrato.md)
GET           /api/v1/eventos/contratos/                        ← só leitura (contrato só é criado via gerar-contrato/ acima)
GET           /api/v1/eventos/contratos/{id}/
GET           /api/v1/eventos/contratos/{id}/pdf/
POST          /api/v1/eventos/contratos/{id}/enviar-whatsapp/    ← exige login · audita contrato_enviado · não trava por status
                                                                    (usado tanto no envio inicial quanto no reenvio via listagem de Orçamentos/Eventos)
GET/PATCH     /api/v1/eventos/configuracao-contrato/1/           ← singleton · PATCH exige login · audita config_contrato_alterada

# Alertas de Evento (ver "Alertas de Evento" em Padrões Obrigatórios)
GET/PATCH             /api/v1/eventos/configuracao-alertas/1/       ← singleton · PATCH exige login · audita config_alerta_evento_alterada
GET/POST              /api/v1/eventos/telefones-alerta/             ← telefones internos da equipe (não é o cliente)
GET/PATCH/DELETE      /api/v1/eventos/telefones-alerta/{id}/        ← DELETE exige login · audita registro_excluido

# Eventos
GET/POST              /api/v1/eventos/                                  ← POST exige login · aceita "sinal_pago" opcional (vira 1º PagamentoEvento) · audita registro_criado
GET/PUT/PATCH/DELETE  /api/v1/eventos/{id}/                              ← PUT/PATCH exigem login, audita registro_atualizado (só campos alterados) · DELETE exige login · audita registro_excluido
GET/POST              /api/v1/eventos/locais/
GET/PATCH/DELETE      /api/v1/eventos/locais/{id}/                       ← DELETE exige login · audita registro_excluido
DELETE                /api/v1/eventos/{id}/itens/{item_id}/remover/      ← exige login · audita registro_excluido
POST                  /api/v1/eventos/{id}/itens/                       ← exige login · audita item_adicionado
POST                  /api/v1/eventos/{id}/confirmar/                    ← exige login · audita status_alterado
POST                  /api/v1/eventos/{id}/iniciar-producao/             ← exige login · audita status_alterado
POST                  /api/v1/eventos/{id}/marcar-pronto/                ← exige login · audita status_alterado
POST                  /api/v1/eventos/{id}/entregar/                     ← exige login · audita status_alterado
POST                  /api/v1/eventos/{id}/cancelar/                     ← exige login · audita status_alterado
POST                  /api/v1/eventos/{id}/pagamentos/                  ← exige login (IsAuthenticated) · cria PagamentoEvento + recalcula sinal_pago (multipart opcional, campo "comprovante") + audita em auditoria.LogAuditoria
DELETE                /api/v1/eventos/{id}/pagamentos/{pagamento_id}/remover/ ← exige login (IsAuthenticated) · audita em auditoria.LogAuditoria
GET                   /api/v1/eventos/{id}/historico/                    ← exige login · trilha de auditoria deste evento (não confundir com clientes/{id}/historico/, que é histórico de pedidos)
GET                   /api/v1/eventos/{id}/resumo-cozinha/               ← AllowAny · PDF operacional (itens agrupados por categoria, sem preço) · ver "Resumo de Cozinha"
GET                   /api/v1/eventos/agenda/

# Notificações WhatsApp
GET  /api/v1/notificacoes/mensagens/
POST /api/v1/notificacoes/mensagens/enviar/
GET  /api/v1/notificacoes/mensagens/status-conexao/
GET/PATCH /api/v1/notificacoes/configuracao/          ← singleton · GET e PATCH exigem login (só aqui GET também é restrito — expõe credencial Z-API) · PATCH audita config_whatsapp_alterada
POST      /api/v1/notificacoes/configuracao/testar/   ← exige login · testa conexão Z-API, não muda nada, não audita

# Usuários
GET/POST              /api/v1/usuarios/
GET/PUT/PATCH/DELETE  /api/v1/usuarios/{id}/
POST                  /api/v1/usuarios/login/           ← AllowAny — retorna dados do usuário + "token" (Usuario.auth_token)
POST                  /api/v1/usuarios/logout/           ← autenticado — invalida o token no servidor
POST                  /api/v1/usuarios/{id}/redefinir-senha/

# Auditoria (restrito a role=admin)
GET /api/v1/auditoria/logs/   ← query params: usuario, acao, model (filtra detalhes.model — só relevante com acao=registro_excluido), data_inicio, data_fim

# Presença (heartbeat — qualquer usuário logado, não é restrito a admin)
POST /api/v1/auditoria/presenca/   ← exige login · body {"model", "objeto_id"} · devolve quem mais está ativo no mesmo (model, objeto_id) numa janela de 40s (polling REST, não WebSocket)

# Catálogo / Fichas / Precificação
GET/POST         /api/v1/fichas/materias-primas/
PATCH/DELETE     /api/v1/fichas/materias-primas/{id}/                  ← DELETE exige login, audita (400 amigável se usada em ficha/produto de revenda — PROTECT)
POST             /api/v1/fichas/materias-primas/{id}/atualizar-preco/   ← exige login · audita preco_materia_atualizado
GET/POST         /api/v1/fichas/fichas/
GET/PATCH/DELETE /api/v1/fichas/fichas/{id}/                           ← DELETE exige login · audita registro_excluido
GET              /api/v1/fichas/fichas/{id}/resumo/
POST             /api/v1/fichas/fichas/{id}/adicionar-item/
DELETE           /api/v1/fichas/fichas/{id}/remover-item/{item_id}/    ← exige login · audita registro_excluido
GET/PATCH        /api/v1/fichas/parametros/1/                          ← PATCH exige login · audita parametros_negocio_alterados
POST             /api/v1/fichas/ajuste-linear/                         ← exige login só quando "confirmar":true (preview continua livre) · audita ajuste_linear_aplicado
POST             /api/v1/fichas/desfazer-ajuste/{snapshot_id}/         ← exige login · audita ajuste_linear_desfeito
GET              /api/v1/fichas/snapshots/

# Estoque (fases 1-5 — ver Padrões Obrigatórios)
GET              /api/v1/estoque/movimentos/                    ← só leitura · filtros: materia_prima, produto, tipo_movimento, origem_tipo, data_inicio, data_fim
POST             /api/v1/estoque/compras/registrar/              ← exige login · body: tipo_item (materia_prima|produto — só revenda), item_id, quantidade, valor_total (opcional), numero_nota (opcional) · audita entrada_estoque_registrada
POST             /api/v1/estoque/ajuste-inventario/              ← exige login · body: tipo_item, item_id, saldo_contado (absoluto, não delta), motivo, observacao (opcional) · audita ajuste_inventario_registrado
GET/POST         /api/v1/estoque/producoes/                      ← POST exige login · body: ficha_tecnica, quantidade_produzida · rejeita se produto vinculado não estiver em modo_estoque="estoque" · audita producao_registrada
GET              /api/v1/estoque/producoes/preview/              ← query params: ficha_tecnica, quantidade · devolve consumo previsto por insumo + suficiente:bool (não bloqueia, só avisa)
GET/PATCH        /api/v1/estoque/configuracao/1/                 ← singleton · PATCH exige login · audita config_estoque_alterada
GET/POST         /api/v1/estoque/telefones-alerta/                ← telefones internos da equipe (não é o cliente)
GET/PATCH/DELETE /api/v1/estoque/telefones-alerta/{id}/           ← DELETE exige login · audita registro_excluido
GET/PATCH        /api/v1/estoque/configuracao-ia/1/                ← singleton · PATCH exige login · audita config_ia_alterada

# Importação de Nota Fiscal (fases 6-8)
GET/POST      /api/v1/estoque/notas/                            ← POST (multipart, campo "arquivo") exige login · roda a cascata de extração + fuzzy match
GET           /api/v1/estoque/notas/{id}/                       ← leitura
PATCH         /api/v1/estoque/notas/{id}/itens/{item_id}/       ← exige login · {materia_prima}|{produto}|{criar_nova_materia_prima:true}|{quantidade,valor_unitario,descartado}
POST          /api/v1/estoque/notas/{id}/confirmar/              ← exige login · rejeita (400) item pendente de revisão · gera MovimentoEstoque por item · audita entrada_nota_confirmada
POST          /api/v1/estoque/notas/{id}/descartar/               ← exige login · não gera movimento

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
python manage.py avisar_sem_compras
# dias sem compra vem só de ConfiguracaoWhatsApp.get().dias_sem_compra (painel) — não aceita flag --dias

# Alertas de Evento — pagamento pendente / entrega próxima (cron diário — ex: 08:00)
python manage.py alertar_eventos
# janelas/repetição vêm de ConfiguracaoAlertaEvento.get() (painel) · precisa de ao menos 1
# eventos.TelefoneAlertaEvento ativo, senão não notifica ninguém

# Importar planilha de precificação
python manage.py importar_planilha --arquivo PLANILHA_DE_PRECIFICACAO_ARRETADO.xlsx
# flags: --dry-run | --apenas-materias | --sobrescrever

# Alertas de Estoque Baixo (cron diário — ex: 08:30)
python manage.py alertar_estoque_baixo
# limite/repetição vêm de ConfiguracaoEstoque.get() (painel) · precisa de ao menos 1
# estoque.TelefoneAlertaEstoque ativo, senão não notifica ninguém

# Testes automatizados (clientes, eventos, fichas, pdv, auditoria, usuarios, notificacoes, pedidos, estoque)
python manage.py test --settings=config.settings_test
# settings_test.py roda contra SQLite em memória — o usuário do Postgres em produção
# não tem permissão CREATE DATABASE, então `manage.py test` direto (sem --settings) falha

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
- Nginx: `client_max_body_size 10m;` no bloco `server` (porta 443) — adicionado na feature de importação de nota fiscal, pra permitir upload de foto de nota fiscal por celular (default do Nginx é 1MB, insuficiente)
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
- Não preencher `Produto.materia_prima_origem`/`margem_desejada_pct` em produto que não seja `tipo == 'revenda'` (validado em `ProdutoSerializer.validate`, não duplicar a regra em outro lugar)
- Não permitir kit-de-kit — `ItemKit.componente` nunca pode ter `tipo == 'kit'` (regra já existe em `ItemKit.clean()` e `ItemKitSerializer.validate_componente`)
- Não hardcodar desconto por quantidade/canal no frontend — sempre resolver via `Produto.preco_para()` (endpoint `/pdv/produtos/{id}/preco/`) em vez de recalcular a lógica de faixas no cliente
- Ao sugerir automaticamente o bairro/taxa de entrega, o bairro do **Local de Evento** (quando selecionado) tem prioridade sobre o bairro do endereço do cliente — nunca inverter essa ordem (ver `FRETE.md`)
- Não instanciar `ConfiguracaoContrato()` diretamente — sempre usar `ConfiguracaoContrato.get()`
- Não instanciar `ConfiguracaoAlertaEvento()` diretamente — sempre usar `ConfiguracaoAlertaEvento.get()`
- Os 2 alertas de Evento (`alertar_eventos`) só notificam telefones de `eventos.TelefoneAlertaEvento` — nunca enviar essas mensagens pro cliente do evento (decisão já confirmada com o usuário)
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
- Não expor `Usuario.auth_token` em list/retrieve/update — só é devolvido explicitamente no payload de `/usuarios/login/`
- Não criar `LogAuditoria` fora de `auditoria/utils.py::registrar()` — é o único ponto de escrita, sempre dentro de try/except (nunca pode derrubar login/CRUD)
- Não checar `usuario.role == 'admin'` cru em views novas — usar `usuarios.permissions.IsAdminRole` (reusa a mesma regra em qualquer app)
- Não estender `authentication_classes`/`permission_classes` globalmente em `config/settings.py` por causa da autenticação real — cada app opta localmente, na própria classe da view. A lista de sistemas críticos priorizada com o usuário (usuários, pagamentos, contrato, preços, configs singleton, exclusões) já está toda instrumentada; ações novas em qualquer desses apps devem seguir o mesmo padrão local (`get_permissions()` por action), não abrir mão dele
- Ao adicionar `TokenAuthentication` a uma viewset só para capturar o ator em auditoria, **não** assuma que isso exige login — `authentication_classes` só popula `request.user` quando o header vem; `permission_classes` (`AllowAny` vs `IsAuthenticated`) é quem decide se a ação é bloqueada sem login. Ver `EventoViewSet.get_permissions()`/`OrcamentoViewSet.get_permissions()` (create/update/status/adicionar_item/historico exigem `IsAuthenticated`) vs. `converter_em_evento`/`enviar_whatsapp` (continuam `AllowAny`, capturam o ator de forma oportunista via `ator_ou_none(request)`)
- Não confundir os dois endpoints `historico/` do projeto: `clientes/{id}/historico/` é histórico de **pedidos** do cliente entre canais (iFood/PDV/Eventos, pra métricas), enquanto `eventos/orcamentos/{id}/historico/` e `eventos/{id}/historico/` são trilha de **auditoria** (quem criou/editou/mudou status) daquele registro específico — mesmo nome, conceitos e implementações totalmente diferentes
- `auditoria.PresencaEdicao`/`PresencaAtiva.jsx` é só informativo ("Fulano também está vendo isso agora") — não implementar nenhuma trava/lock de edição em cima disso (ex: bloquear salvar se outro usuário estiver com o modal aberto). Se um dia precisar de trava de verdade, é uma feature nova, não uma extensão da presença
- Não trocar o heartbeat de presença por WebSocket/Django Channels sem antes confirmar com o usuário — decisão deliberada de manter só polling REST, já que o projeto roda Gunicorn/WSGI síncrono sem Channels/Redis/ASGI
- Ao criar um novo `ModelViewSet` com DELETE que deva ser auditado, usar `auditoria.mixins.AuditoriaDestroyMixin` em vez de escrever `registrar()` manualmente no `destroy()` — ele já trata `ProtectedError` (FK `on_delete=PROTECT`) como 400 amigável em vez de deixar vazar um 500. Para exclusão de item filho via `@action` customizada (`remover-item`, `remover-imagem` etc.), não dá pra usar o mixin (não passa por `perform_destroy`) — chamar `registrar()` manualmente ali, sempre **antes** de `.delete()` (o objeto perde o `pk` depois)
- Nunca remover o bloqueio de `DELETE` em `ifood.ConfiguracaoIFoodViewSet` — essa config não é um singleton de verdade (usa `.objects.first()`), então excluir a linha derruba client_id/secret/tokens de produção sem aviso
- Não escrever `quantidade_estoque` direto em `MateriaPrima`/`Produto` fora de `estoque.MovimentoEstoque.registrar()` — nem em view, nem em signal, nem em management command (mesma regra já aplicada a `PedidoUnificado` e `Evento.sinal_pago`)
- Não bloquear venda, produção ou ajuste de inventário por saldo insuficiente — a política de estoque é sempre permitir e alertar, em toda a aplicação, sem exceção por item
- Não chamar `Producao.executar()` para produto com `modo_estoque == 'sob_encomenda'` — esse caso debita insumo direto no signal de venda (`estoque/signals.py::_debitar_produto`), sem passar por produção formal
- Ao gravar `quantidade`/`custo_unitario_snapshot` em `MovimentoEstoque`, não montar o valor manualmente sem quantizar — sempre deixar `MovimentoEstoque.registrar()` fazer isso (já quantiza `quantidade` a 3 casas e `custo_unitario_snapshot` a 4 casas); consumo proporcional e `custo_unitario` são divisões que saem com dezenas de casas decimais e derrubam `full_clean()` se não quantizados (bug real já corrigido — ver Padrões Obrigatórios)
- Não implementar estoque de kit físico pré-montado — kit é sempre virtual (decrementa os componentes recursivamente), decisão consciente de escopo
- Não implementar reversão automática de estoque em cancelamento de pedido/evento pós-débito — fora de escopo por decisão consciente; ajuste manual de inventário cobre o caso
- Não criar `MateriaPrima` automaticamente no fuzzy match da importação de nota fiscal (`resolver_materia_prima()`) — diferente do fuzzy match de débito automático da venda, aqui sempre marca `status_match='revisar'` e espera revisão manual explícita (`criar_nova_materia_prima: true` no PATCH do item)
- Não gravar `MovimentoEstoque` direto a partir da extração da nota fiscal — sempre passar pela tela de revisão e pelo endpoint `confirmar/` (`ImportacaoNotaFiscal`/`ItemNotaImportada` são só staging)
- Não guardar `ANTHROPIC_API_KEY` em model/banco — sempre variável de ambiente (mesmo padrão de `ZAPI_*`)
- Não usar SDK `anthropic` — `estoque/claude_client.py` chama a API Claude via `requests` puro, mesmo espírito leve de `notificacoes/zapi_client.py`
- Endpoint de upload de nota fiscal é `POST /api/v1/estoque/notas/` (o `create()` padrão do ViewSet) — não `/notas/importar/` (bug real já cometido e corrigido durante o desenvolvimento: o frontend chamava uma URL que não existia)
