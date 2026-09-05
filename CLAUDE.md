# Arretado Doces — CRM Proprietário

> Arquivo lido automaticamente pelo Claude Code em toda sessão.
> Última atualização: 18/ago/2026.

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
│   ├── settings.py              ← INSTALLED_APPS: clientes, ifood, pdv, pedidos, eventos, usuarios, notificacoes, fichas, estoque, relatorios, dashboard, financeiro, manutencao, empresas
│   ├── urls.py                  ← rotas: /api/v1/, /api/v1/versao/, /api/v1/ifood/, /api/v1/pdv/, /api/v1/eventos/, /api/v1/notificacoes/, /api/v1/fichas/, /api/v1/estoque/, /api/v1/relatorios/, /api/v1/dashboard/, /api/v1/financeiro/, /api/v1/manutencao/
│   ├── versao.py                ← `obter_versao()` — versão da app via `git describe --tags --always --dirty`
│   │                               (nunca mantida à mão), cacheada por processo com `lru_cache` — ver "Versão
│   │                               do Sistema" abaixo
│   ├── views.py                 ← `VersaoView` (APIView, AllowAny) — único endpoint fora de um app de domínio
│   └── wsgi.py
├── empresas/                    ← Multi-Empresa (Fases 0-5 de 6 concluídas, ver MULTIEMPRESA.md) — model
│   │                               Empresa (multi-tenant por linha), consumido por `ifood/` (Fase 1),
│   │                               `usuarios/` (Fase 2), `financeiro/` (Fase 4) e `dashboard/`/`relatorios/`
│   │                               (Fase 5, ver blocos próprios em cada app abaixo) — falta só cadastrar a
│   │                               MANGAIO de fato (nenhuma fase pendente no código)
│   ├── models.py                ← Empresa (nome/subtitulo/razao_social/cnpj único quando preenchido,
│   │                               `padrao` — exatamente uma True via UniqueConstraint condicional, `ativo`,
│   │                               12 campos de cor hex (`cor_*`, blank — vazio herda o token CSS atual),
│   │                               3 ImageField de logo + 1 FileField de timbre (preparatório, nenhum gerador
│   │                               de PDF lê daqui ainda), `modulos_ocultos` (JSONField, lista de slugs de
│   │                               rota — Fase 5, Sidebar.jsx esconde os itens de menu listados aqui pra
│   │                               empresa ativa; matriz nasce `[]`, menu intocado) · `Empresa.get_padrao()`
│   │                               — nunca resolver a empresa padrão por id fixo em código
│   └── views.py                 ← EmpresaViewSet (CRUD sem DELETE/PUT — `http_method_names` restrito, inativar
│                                    é `ativo=False` — create/update exigem login, list/retrieve AllowAny,
│                                    audita via AuditoriaCreateMixin/UpdateMixin) + action `branding-login`
│                                    (AllowAny, devolve nome/logos/cores da empresa `padrao=True` pra tela de
│                                    login — ainda não consumida pelo frontend, `Login.jsx` intocado nesta fase)
├── clientes/                    ← Fase 1: CRM de clientes
│   ├── models.py                ← Cliente (inclui rg/rg_orgao_emissor/nacionalidade/profissao/estado_civil —
│   │                               opcionais no cadastro, exigidos na emissão de Contrato, ver Contrato.md), Endereço, TagCliente
│   └── views.py                 ← inclui action `historico` (GET /api/v1/clientes/{id}/historico/)
├── ifood/                       ← Fase 2: integração iFood · multi-empresa desde a Fase 1 do MULTIEMPRESA.md
│   │                               (uma linha de ConfiguracaoIFood por empresa/merchant — não é singleton,
│   │                               nunca foi; ver MULTIEMPRESA.md)
│   ├── models.py                ← ConfiguracaoIFood (+ FK `empresa`, PROTECT), PedidoIFood (+ FK `empresa`,
│   │                               PROTECT, denormalizada da config no momento da criação — snapshot),
│   │                               ItemPedidoIFood, EventoPollingIFood
│   ├── ifood_client.py          ← IFoodClient (auth, polling, ACK, pedidos) — instanciado sempre com a
│   │                               ConfiguracaoIFood da empresa do pedido em questão
│   ├── polling_worker.py        ← run_polling(), _processar_config(), _criar_pedido() (grava `empresa =
│   │                               config.empresa` no pedido criado)
│   └── management/commands/ifood_polling.py
├── pedidos/                     ← Fase 3: espelho unificado (só leitura)
│   ├── models.py                ← PedidoUnificado (+ FK `empresa`, PROTECT, `null=True` — iFood propaga a
│   │                               empresa do PedidoIFood; PDV/Eventos são mono-empresa e sempre gravam
│   │                               `Empresa.get_padrao()`, nunca id fixo)
│   └── apps.py                  ← registra signals do iFood e PDV no ready()
├── pdv/                         ← Fase 3-ext-A: PDV próprio
│   ├── models.py                ← CategoriaProduto, Produto (+ segmento/foto/disponibilidades/tipo fabricado|revenda|kit
│   │                               com custo polimórfico, preco_para() por faixa), ItemKit, FaixaPreco (quantidade_minima+canal),
│   │                               DadosFiscaisProduto (unidade/código/EAN/NCM — prepara NFC-e futura), PedidoPDV, ItemPedidoPDV
│   │                               (+ `natureza` venda/brinde/permuta — Fase 1 de `BRINDES_PERMUTAS.md`, ver Padrões Obrigatórios),
│   │                               TaxaEntregaBairro (bairro→taxa), ConfiguracaoEntrega (singleton, frete padrão)
│   ├── urls.py                  ← inclui taxas-entrega/ e configuracao-entrega/
│   ├── management/commands/listar_candidatos_revenda.py ← lista produtos "fabricado" sem FichaTecnica vinculada
│   │                               (candidatos a reclassificar manualmente para "revenda"); só leitura, não altera o banco
│   └── signals.py               ← espelha PedidoPDV → PedidoUnificado
├── eventos/                     ← Fase 4: gestão de eventos/encomendas + orçamentos + contratos
│   ├── models.py                ← Orcamento, ItemOrcamento (+ `natureza` venda/brinde/permuta — Fase 1 de
│   │                               `BRINDES_PERMUTAS.md`, ver Padrões Obrigatórios), Evento, ItemEvento (idem), LocalEvento,
│   │                               Contrato (snapshot, CTR-0001...), ConfiguracaoContrato (singleton — ver Contrato.md),
│   │                               ConfiguracaoAlertaEvento (singleton, janelas/repetição dos 2 alertas de Evento),
│   │                               TelefoneAlertaEvento (telefones internos da equipe que recebem os alertas),
│   │                               AlertaEventoEnviado (rastreia último envio por evento+tipo, controla repetição —
│   │                               ver "Alertas de Evento" abaixo),
│   │                               ImagemInspiracao (galeria de imagens de referência do cliente — FK opcional a
│   │                               Orcamento OU a Evento, exatamente um dos dois preenchido, ver Padrões Obrigatórios),
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
│   ├── pdf_orcamento.py          ← gera PDF (ReportLab, canvas cru, 1 página; a tabela de itens em si é
│   │                               `platypus.Table`, drawn on via `.drawOn()`) — inclui linha "Taxa de entrega"
│   │                               quando houver; bloco "CONDIÇÕES COMERCIAIS" é lista fixa `condicoes` no código
│   │                               (não vem de ConfiguracaoContrato nem de outro model) — ver "O Que NÃO Fazer".
│   │                               Fase 3 de `BRINDES_PERMUTAS.md`: item com `natureza != 'venda'` ganha
│   │                               " — Brinde"/" — Permuta" no nome e `preco_unit` riscado (`Paragraph` com
│   │                               `<strike>`, célula da tabela vira `Paragraph` só nesse caso — resto continua
│   │                               string plana)
│   ├── pdf_contrato.py           ← gera PDF do contrato (ReportLab Platypus, multi-página) — texto e cláusulas vêm de
│   │                               ConfiguracaoContrato.get() + snapshot do Contrato, nunca hardcoded. Fase 3 de
│   │                               `BRINDES_PERMUTAS.md`: mesmo tratamento de `pdf_orcamento.py` na tabela "ANEXO
│   │                               1 — NOTA DE PEDIDOS" (rótulo + `<strike>` no preço de tabela)
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
├── usuarios/                    ← Gestão de usuários + RBAC + autenticação real por token + vínculo multi-empresa
│   │                               (Fase 2 do MULTIEMPRESA.md, ver "Multi-Empresa — Fase 2" abaixo)
│   ├── models.py                ← Usuario (auth_token, gerar_token(), is_authenticated/is_anonymous — compatibilidade DRF,
│   │                               `empresas` M2M → empresas.Empresa, `empresa_ativa` FK SET_NULL, `preferencia_tema`
│   │                               choices empresa/neutro_claro/neutro_escuro — default 'empresa')
│   ├── authentication.py        ← TokenAuthentication (lê "Authorization: Token <valor>", popula request.user)
│   ├── permissions.py           ← IsAdminRole (reusado por auditoria/)
│   └── views.py                 ← login/logout (regenera/invalida auth_token, login devolve empresas/empresa_ativa/
│                                    preferencia_tema "efetivos" — com fallback pra empresa padrão, ver abaixo),
│                                    definir-empresa-ativa/ + preferencia-tema/ (Fase 2), CRUD instrumentado via
│                                    auditoria.utils.registrar()
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
├── relatorios/                  ← Relatórios consolidados por canal — multi-empresa desde a Fase 5 do
│   │                               MULTIEMPRESA.md (ver bloco "Dashboard e Relatórios por empresa" abaixo)
│   ├── views.py                 ← RelatorioIFoodView (resumo + agrupado por dia/mês, export Excel/PDF — só
│   │                               canal iFood) + ProdutosMaisVendidosView (ranking cross-canal iFood+PDV+
│   │                               Eventos, ver "Produtos Mais Vendidos" abaixo — só JSON, sem export) ·
│   │                               ambas aceitam `?empresa=<id>`/`?empresa=todas` (`_resolver_empresa()`,
│   │                               duplicado do mesmo padrão de `dashboard/views.py`/`financeiro/views.py`)
│   └── urls.py                  ← ifood/, produtos-mais-vendidos/ (mais canais a adicionar conforme necessário)
├── dashboard/                    ← Dashboard multi-canal (só leitura, sem models próprios) — multi-empresa
│   │                               desde a Fase 5 do MULTIEMPRESA.md (ver bloco próprio abaixo)
│   ├── views.py                 ← DashboardResumoView (APIView, GET) — agrega PedidoUnificado (iFood/PDV)
│   │                               + PagamentoEvento/Evento (eventos) num único JSON, ver regras abaixo
│   │                               (inclui `alertas`: mesma janela de eventos.ConfiguracaoAlertaEvento, sem
│   │                               depender de AlertaEventoEnviado — mostra "o que está na janela agora") ·
│   │                               aceita `?empresa=<id>`/`?empresa=todas` via `_resolver_empresa()` (mesmo
│   │                               padrão de `financeiro/views.py`, duplicado aqui a propósito)
│   ├── tests.py                 ← DashboardResumoMultiEmpresaTests (Fase 5) — matriz/consolidado/empresa
│   │                               explícita não-matriz, repasse_ifood_a_receber, empresa_ativa por default
│   └── urls.py                  ← resumo/
├── financeiro/                  ← Contas a Pagar/Receber + ledger de caixa (spec completa em FINANCEIRO.md,
│   │                               em andamento — fases 0-6 de 8 concluídas, ver Pendências) + Fase 4 do
│   │                               multi-empresa (MULTIEMPRESA.md — numeração de spec diferente da acima,
│   │                               não confundir): ContaBancaria/ContaPagar/ContaReceber/DespesaRecorrente
│   │                               ganharam FK `empresa` (PROTECT) e ConfiguracaoFinanceira deixou de ser
│   │                               singleton global — vira 1 linha por empresa (`get(empresa)`,
│   │                               `OneToOneField`) — ver bloco dedicado depois de views.py abaixo
│   ├── models.py                ← CategoriaFinanceira (nasce vazia, sem seed — requisito de revenda,
│   │                               **compartilhada** entre empresas — plano de contas único, não ganhou FK),
│   │                               ContaBancaria (saldo_atual só via MovimentoFinanceiro.registrar(), FK
│   │                               `empresa` PROTECT desde a Fase 4 do multi-empresa),
│   │                               Fornecedor (**compartilhado**, sem FK empresa), ConfiguracaoFinanceira
│   │                               (1 linha por empresa desde a Fase 4 — `OneToOneField` `empresa`, inclui
│   │                               conta_padrao_vendas — destino dos movimentos automáticos de venda **da
│   │                               empresa**), TelefoneAlertaFinanceiro (**compartilhado**, equipe única),
│   │                               MovimentoFinanceiro (ledger, fonte única da verdade — **sem** FK empresa
│   │                               própria, `MovimentoFinanceiro.empresa` é property que delega pra
│   │                               `self.conta.empresa`, nunca denormalizar), ContaPagar (obrigação
│   │                               projetada, valor_pago/status sempre derivados via recalcular_valor_pago() —
│   │                               mesma filosofia de Evento.sinal_pago; FK `empresa` PROTECT desde a Fase 4;
│   │                               campo recorrente FK opcional pra DespesaRecorrente,
│   │                               UniqueConstraint(recorrente, data_vencimento) condicional garante
│   │                               idempotência do cron), ContaReceber (obrigação projetada simétrica, FK
│   │                               `empresa` PROTECT desde a Fase 4, só existe pra iFood modo 'repasse' ou
│   │                               lançamento manual — Eventos e PDV NUNCA materializam ContaReceber, ver
│   │                               signals.py; valor_recebido/status derivados via
│   │                               recalcular_valor_recebido(), UniqueConstraint(origem_canal,
│   │                               origem_id) condicional garante idempotência do signal), DespesaRecorrente
│   │                               (molde de despesa mensal, FK `empresa` PROTECT desde a Fase 4 — a ContaPagar
│   │                               gerada pelo cron herda a empresa do molde —, dias_vencimento JSONField com
│   │                               lista de dias do mês — dia inexistente no mês cai no último dia via
│   │                               datas_no_periodo()), AlertaFinanceiroEnviado (rastreia último alerta de
│   │                               vencimento por ContaPagar, controla repetição), SaldoConferido (conferência
│   │                               de saldo — saldo_informado digitado pelo usuário x saldo_calculado, snapshot
│   │                               de ContaBancaria.saldo_atual no momento do POST; sem edição, nova
│   │                               conferência é sempre um registro novo, histórico preservado; diferenca é
│   │                               property; **sem** FK empresa própria — herda implicitamente da conta)
│   ├── signals.py               ← registrado em FinanceiroConfig.ready() — bate no ledger no fluxo normal
│   │                               de venda, mesmo padrão de estoque/signals.py (sender como string,
│   │                               try/except, idempotência via existence check): PedidoPDV ao entrar em
│   │                               'confirmado' → entrada direto (conta_padrao_vendas), 'cancelado' após
│   │                               movimento gravado → estorno automático (origem_tipo='manual',
│   │                               origem_id=f'estorno-pdv-{id}'); PedidoIFood ao entrar em 'CONCLUDED'
│   │                               (nunca em cada evento de polling) → entrada direto se
│   │                               recebimento_ifood='no_ato', ou ContaReceber (canal='ifood',
│   │                               data_vencimento=data_pedido+dias_repasse_ifood) se 'repasse';
│   │                               'CANCELLED' após CONCLUDED → estorna o movimento (modo no_ato) ou cancela
│   │                               a ContaReceber ainda não recebida (modo repasse); PagamentoEvento
│   │                               post_save com status='pago' → entrada direto, post_delete → estorno
│   │                               automático (nunca DELETE do movimento original — ledger imutável). Se
│   │                               conta_padrao_vendas não configurada, loga warning e não grava — nunca
│   │                               cria ContaBancaria automaticamente. Desde a Fase 4 do multi-empresa,
│   │                               `ConfiguracaoFinanceira.get()` exige `empresa`: PDV e PagamentoEvento são
│   │                               mono-empresa (sempre `Empresa.get_padrao()`); iFood resolve tudo pela
│   │                               empresa do próprio pedido (`pedido.empresa`, FK desde a Fase 1) — permite
│   │                               MANGAIO em 'repasse' e a matriz em 'no_ato' simultaneamente, cada uma na
│   │                               sua própria conta_padrao_vendas
│   ├── management/commands/gerar_contas_recorrentes.py ← cron diário: materializa ContaPagar
│   │                               (origem='recorrente') a partir de cada DespesaRecorrente ativa **de
│   │                               qualquer empresa, numa única passada** (Fase 4 do multi-empresa), um
│   │                               vencimento por dia em dias_vencimento dentro do horizonte configurado em
│   │                               ConfiguracaoFinanceira.get(despesa.empresa).horizonte_recorrencia_dias —
│   │                               a ContaPagar gerada herda a empresa do molde — idempotente pela
│   │                               UniqueConstraint(recorrente, data_vencimento)
│   ├── management/commands/alertar_vencimentos.py ← cron diário: alerta a equipe (WhatsApp, via
│   │                               TelefoneAlertaFinanceiro, compartilhados entre empresas) sobre ContaPagar
│   │                               pendente/parcial vencendo em até alerta_antecedencia_dias ou já em atraso
│   │                               — janela/repetição lidas da ConfiguracaoFinanceira **de cada empresa**
│   │                               (Fase 4), controlado por AlertaFinanceiroEnviado (mesmo padrão de
│   │                               alertar_eventos/alertar_estoque_baixo); mensagem ganha o prefixo
│   │                               `[{empresa.nome}]` (sempre, incondicional)
│   └── views.py                 ← CategoriaFinanceiraViewSet/ContaBancariaViewSet/FornecedorViewSet,
│                                    MovimentoFinanceiroViewSet (só leitura + action manual/, lançamento
│                                    avulso/estorno), ConfiguracaoFinanceiraViewSet, TelefoneAlertaFinanceiroViewSet,
│                                    ContaPagarViewSet (baixa/cancelar/resumo), ContaReceberViewSet
│                                    (baixa/resumo — resumo inclui saldo de Evento via query dinâmica, nunca
│                                    materializado como linha), DespesaRecorrenteViewSet (sem DELETE — pausar
│                                    via ativo=False), SaldoConferidoViewSet (só GET/POST, sem PATCH/DELETE),
│                                    FluxoCaixaView (APIView, GET fluxo-caixa/?dias=N — agregador por dia:
│                                    realizado do ledger + projetado de ContaPagar/ContaReceber pendente/parcial,
│                                    + saldos por conta e última conferência de cada uma; não inclui saldo
│                                    dinâmico de Evento, diferente de contas-receber/resumo — fora do escopo
│                                    literal da Fase 6). **Fase 4 do multi-empresa**: todos os endpoints acima
│                                    aceitam `?empresa=<id>` (default: `empresa_ativa` do usuário autenticado,
│                                    senão `Empresa.get_padrao()` — nunca `.objects.first()`, resolvido por
│                                    `_resolver_empresa()`) e `?empresa=todas` (sentinela de consolidado —
│                                    devolve `None`, sem filtro); `contas-receber/resumo/` só soma o saldo
│                                    dinâmico de Evento quando a empresa resolvida é `None` (todas) ou a
│                                    própria matriz (Eventos é mono-empresa); `create`/`update` em
│                                    `ContaBancariaViewSet`/`ContaPagarViewSet`/`ContaReceberViewSet`/
│                                    `DespesaRecorrenteViewSet` validam (`_validar_empresa_vinculo()`) que o
│                                    `?empresa=` explícito está entre as empresas do usuário (mesma regra de
│                                    `usuarios.views._empresas_efetivas`, duplicada aqui a propósito — 3
│                                    linhas, não vale importar função privada de outro app)
├── manutencao/                  ← Backup do banco (pg_dump) + mídia (tarfile) com envio externo pro
│   │                               Backblaze B2 via rclone + alerta de falha via WhatsApp (spec completa
│   │                               em `backup.md`)
│   ├── models.py                ← ConfiguracaoBackup (singleton, pastas/retenção/remote/limites de alerta),
│   │                               TelefoneAlertaBackup (telefones internos da equipe, mesmo padrão de
│   │                               TelefoneAlertaEvento/Estoque/Financeiro)
│   ├── views.py                 ← ConfiguracaoBackupViewSet (GET/PATCH) + TelefoneAlertaBackupViewSet (CRUD)
│   └── management/commands/
│       ├── fazer_backup.py      ← dump do Postgres (`pg_dump -Fc`) + tar.gz de media/ (`tarfile`, nunca
│       │                           subprocess/tar do sistema) + rotação local + envio via `rclone` pro
│       │                           Backblaze B2 + rotação remota — nunca chama `notificar()` (nem sucesso
│       │                           nem falha), quem alerta é o verificar_backup
│       └── verificar_backup.py  ← checa idade/tamanho do backup mais recente, alerta WhatsApp se
│                                   desatualizado/ausente/suspeito de corrompido (sem dedup — repete
│                                   todo dia enquanto quebrado, decisão consciente)
└── manage.py

arretado-crm/                    ← raiz React
└── src/
    ├── api/
    │   ├── client.js            ← axios base
    │   └── services.js          ← clientesApi, tagsApi, ifoodApi, pdvApi, pedidosApi,
    │                               eventosApi, locaisEventoApi, orcamentosApi, contratosApi, configContratoApi,
    │                               alertasEventoApi (config + telefones.list/create/remove — ver "Alertas de Evento"),
    │                               notificacoesApi, usuariosApi (inclui definirEmpresaAtiva/preferenciaTema —
    │                               Multi-Empresa Fase 2), authApi (login/logout/me + atualizarCache — espelha
    │                               empresa_ativa/preferencia_tema no localStorage após trocar, ver abaixo), fichasApi,
    │                               taxasEntregaApi, configEntregaApi, relatoriosApi, dashboardApi, auditoriaApi,
    │                               presencaApi (heartbeat de presença — ver Padrões Obrigatórios),
    │                               estoqueApi (movimentos, registrarCompra, ajusteInventario, producoes,
    │                               configuracao, telefonesAlerta),
    │                               financeiroApi (categorias, contasBancarias, fornecedores, contasPagar
    │                               com baixa/cancelar/resumo, contasReceber com baixa/resumo, recorrentes,
    │                               movimentos com manual, conferencias, fluxoCaixa, configuracao, telefonesAlerta
    │                               — Fase 4 do multi-empresa: `create`/`resumo`/`fluxoCaixa`/`configuracao.get`/
    │                               `configuracao.update` aceitam empresa/empresaId, repassado como `?empresa=`),
    │                               empresasApi (list/create/update, uploadArquivo/removerArquivo por campo
    │                               de logo/timbre — FormData, mesmo padrão de pdvApi.updateFoto —,
    │                               brandingLogin — ver "Multi-Empresa" abaixo),
    │                               sistemaApi (versao — ver "Versão do Sistema" abaixo)
    ├── utils/
    │   ├── auditoriaResumo.js   ← ACAO_LABEL/ACAO_COR/dataFmt/resumo — extraído de Auditoria.jsx,
    │   │                           reusado também pela aba/seção "Histórico" no modal de Orçamento/Evento
    │   └── tema.js              ← Multi-Empresa Fase 3 (temas, ver MULTIEMPRESA.md): `aplicarCoresEmpresa(empresa)`
    │                               (mapeia os 12 campos de cor de `Empresa` pros tokens CSS reais de `index.css`,
    │                               sempre via `setProperty`/`removeProperty` — nunca só pular campo vazio, é o
    │                               que garante reset correto ao trocar de empresa/tema/logout),
    │                               `aplicarModoNeutro(modo)` (seta/limpa `data-theme` na raiz) e `aplicarTema()`
    │                               (helper único que decide entre os dois, usado por `useAuth.jsx` e `Login.jsx`)
    ├── hooks/
    │   └── useAuth.jsx          ← AuthProvider/useAuth — user (cache em localStorage, exceção já existente,
    │                               ver Padrões Obrigatórios) + login/logout + Multi-Empresa Fase 2:
    │                               `empresas`/`empresaAtiva` (derivados de `user.empresas`/`user.empresa_ativa`,
    │                               vindos do payload de login) + `trocarEmpresa(id)`/`definirPreferenciaTema(tema)`
    │                               (chamam a API, depois espelham a resposta em `authApi.atualizarCache()`) +
    │                               Fase 3: `useEffect` que chama `aplicarTema()` (utils/tema.js) toda vez que
    │                               `user` muda (login/logout/troca de empresa/troca de tema) e mantém
    │                               `document.title`/favicon sincronizados com a empresa ativa
    ├── pages/
    │   ├── Login.jsx            ← Multi-Empresa Fase 3: busca `empresasApi.brandingLogin()` no mount e aplica
    │   │                           via `aplicarCoresEmpresa()` (tela pré-login sempre no tema "Empresa" da
    │   │                           `padrao=True`, sem seletor ali) — logo/nome/subtítulo dinâmicos com fallback
    │   │                           pro SVG + texto "Arretado Doces" atual quando a empresa não tem logo
    │   ├── EscolherEmpresa.jsx  ← Multi-Empresa Fase 2: tela pós-login com 2+ empresas vinculadas (rota
    │   │                          própria /escolher-empresa, fora do AppLayout — sem sidebar) — cards por
    │   │                          empresa (logo/cor/nome), escolha chama trocarEmpresa() e navega pro app
    │   ├── Dashboard.jsx        ← agrega dashboardApi.resumo() (canais + gráfico 7 dias + a receber +
    │   │                          fila operacional + próximos eventos + ticket médio) e clientesApi (recentes).
    │   │                          Fase 5 do multi-empresa: consome `useAuth().empresaAtiva`/`empresas` (mesmo
    │   │                          contexto global de Financeiro.jsx), chip "Todas as empresas" no Topbar (só
    │   │                          com 2+ vínculos); `matrizView` (`!resumo.empresa || resumo.empresa.padrao`)
    │   │                          decide o layout — visão de empresa não-matriz esconde os cards PDV/Eventos/
    │   │                          Próximos Eventos e troca "A receber (eventos)" pelo card/painel "Repasse
    │   │                          iFood a receber" (`resumo.repasse_ifood_a_receber`)
    │   ├── Clientes.jsx
    │   ├── ClienteDetail.jsx
    │   ├── Tags.jsx
    │   ├── Usuarios.jsx         ← CRUD + permissões; Multi-Empresa Fase 2: checkbox de vínculo de empresa
    │   │                          no form de criação (`empresas_ids`) e no painel de detalhe do usuário
    │   │                          selecionado (mesmo padrão de toggle das permissões) — só aparece com 2+
    │   │                          empresas ativas cadastradas
    │   ├── IFood.jsx
    │   ├── PDV.jsx
    │   ├── CatalogoPDV.jsx      ← catálogo do PDV (gestão de produtos para venda)
    │   ├── Catalogo.jsx         ← catálogo geral (grid de cards, foto, segmento, canais)
    │   ├── FichasTecnicas.jsx   ← composição de ingredientes por produto
    │   ├── CentralPrecos.jsx    ← precificação (matérias, ajuste linear, semáforo, parâmetros)
    │   ├── Estoque.jsx          ← controle de estoque (4 abas: Insumos, Produtos, Produção, Movimentações) +
    │   │                          modais Registrar Compra (manual), Ajuste de Inventário, Configurações
    │   ├── Relatorios.jsx       ← 2 abas: "Por Canal (iFood)" (relatório original, resumo + gráfico por
    │   │                          período + export Excel/PDF) e "Produtos Mais Vendidos" (ranking cross-canal
    │   │                          iFood+PDV+Eventos, toggle de canais + período + ordenar por quantidade/valor,
    │   │                          só tela — sem export). Fase 5 do multi-empresa: as duas abas ganham filtro
    │   │                          "Empresa" (segmented control, só visível com 2+ vínculos, mesmo componente
    │   │                          `.segControl`/`.segBtn` já usado no agrupamento dia/mês) — empresa ativa vs
    │   │                          "Todas"; exports (Excel/PDF) e a URL de produtos-mais-vendidos propagam
    │   │                          `?empresa=` também
    │   ├── Financeiro.jsx       ← 5 abas: Contas a Pagar (+ seção Despesas Recorrentes), Contas a Receber,
    │   │                          Fluxo de Caixa (gráfico divergente realizado×projetado + cards de conta
    │   │                          com conferência de saldo + lançamento manual), Categorias, Configurações
    │   │                          (config por empresa + telefones de alerta + contas bancárias + fornecedores).
    │   │                          Fase 4 do multi-empresa: consome `useAuth().empresaAtiva`/`empresas`
    │   │                          (mesmo contexto global da Sidebar — **não** replica o seletor local
    │   │                          independente de `IFood.jsx`, que é anterior à Fase 2 e não compartilha
    │   │                          estado); badge discreto com o nome da empresa ativa no cabeçalho; abas
    │   │                          Contas a Pagar/Receber/Fluxo de Caixa ganham chip "Todas as empresas" (só
    │   │                          visível com 2+ vínculos) que troca o `?empresa=` de `empresaAtiva.id` pra
    │   │                          `'todas'` (consolidado); aba Configurações sempre usa `empresaAtiva.id`
    │   │                          (config é sempre de uma empresa específica, sem noção de "todas")
    │   ├── Eventos.jsx
    │   ├── Orcamentos.jsx       ← inclui botão "Emitir Contrato" (status='aprovado') + ModalEmitirContrato
    │   ├── Locais.jsx           ← cadastro de Locais de Evento (LocalEvento)
    │   ├── TaxasEntrega.jsx     ← cadastro de taxas por bairro + frete padrão (ver FRETE.md)
    │   ├── Notificacoes.jsx
    │   ├── Configuracoes.jsx
    │   ├── Vinculacoes.jsx
    │   └── Empresas.jsx         ← Multi-Empresa Fase 0: lista + modal criar/editar (dados básicos, 12
    │                               swatches de cor com preview ao vivo, upload dos 3 logos + timbre depois
    │                               de criada) — rota /empresas, menu Administração, `AdminRoute` (role=admin).
    │                               Fase 5: seção "Módulos visíveis no menu" no modal — checkboxes de
    │                               `MODULOS_OCULTAVEIS` (lista fixa no componente, slugs de rota que fazem
    │                               sentido esconder pra uma empresa mono-canal como a MANGAIO: Eventos,
    │                               Orçamentos, Catálogo, Fichas Técnicas, Central de Preços, Estoque, PDV
    │                               Próprio, Anota AI, Taxas de Entrega — nunca Dashboard/Financeiro/
    │                               Relatórios/Clientes/WhatsApp/Configurações, que são compartilhados/
    │                               multi-empresa por escopo) gravadas em `Empresa.modulos_ocultos`
    ├── components/
    │   ├── layout/
    │   │   ├── AppLayout.jsx
    │   │   ├── Sidebar.jsx      ← Fase 5 do multi-empresa: filtra os itens de `NAV` por
    │   │   │                      `empresaAtiva.modulos_ocultos` (slug = `item.to` sem a barra inicial, ex:
    │   │   │                      `'estoque'`, `'integracoes/pdv'`) — puramente cosmético, `App.jsx` continua
    │   │   │                      registrando todas as rotas
    │   │   ├── Topbar.jsx       ← topbar por página (título + busca/ações) — não é um header global; o
    │   │   │                      projeto não tem chrome compartilhado além da Sidebar (ver Multi-Empresa Fase 2)
    │   │   ├── EmpresaSwitcher.jsx  ← Multi-Empresa Fase 2: pill no rodapé da Sidebar (acima do userPill),
    │   │   │                          só renderiza com 2+ empresas no contexto (`useAuth().empresas`) — spec
    │   │   │                          original previa "switcher no header", mas este projeto não tem header
    │   │   │                          global, só Sidebar; troca chama `trocarEmpresa()` de useAuth.jsx
    │   │   └── SeletorTema.jsx      ← Multi-Empresa Fase 3: segmented control de 3 ícones (empresa/claro/escuro)
    │   │                              no rodapé da Sidebar, acima do `EmpresaSwitcher` — mesmo desvio "sem
    │   │                              header global" já documentado na Fase 2 — sempre visível (não depende
    │   │                              de 2+ empresas), chama `definirPreferenciaTema()` de useAuth.jsx
    │   └── ui/                  ← Btn, Modal, Spinner, Avatar, etc. · PresencaAtiva.jsx (badge "Fulano também
    │                               está vendo isso agora", heartbeat a cada 15s via presencaApi — usado no
    │                               modal de detalhe de Orçamento e Evento)
    ├── index.css                ← tokens do design system (`:root`) — ver Padrões Obrigatórios; Multi-Empresa
    │                               Fase 3 acrescentou tokens novos (companheiros `--*-rgb`, trio de status
    │                               compartilhado, badges de canal/marca externa, tokens de sidebar/tipografia)
    │                               sem alterar nenhum valor existente
    ├── temas.css                 ← Multi-Empresa Fase 3 (novo): blocos `:root[data-theme="neutro-claro"]` e
    │                               `:root[data-theme="neutro-escuro"]` — identidade do produto Ortex (não de
    │                               cliente), por isso vive em CSS e não no banco como as cores de empresa
    └── App.jsx                  ← rotas do frontend — inclui /escolher-empresa (ProtectedRoute, fora do AppLayout)
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
- **Importação de Nota Fiscal** (fases 6-8, `POST /api/v1/estoque/notas/` — endpoint é o `create()` padrão do `ImportacaoNotaFiscalViewSet`, **não** `/notas/importar/`) — upload de arquivo (XML/PDF/imagem) roda a cascata de extração em `estoque/extracao_nota.py`: `extrair_xml()` (determinístico, parseia `det/prod` da NF-e via `xml.etree.ElementTree` com remoção de namespace) → `extrair_texto_pdf()` (heurística best-effort via `pypdf.extract_text()` + regex, pode falhar em DANFEs complexos — ver Pendências) → `extrair_ia()` (fallback multimodal via `estoque/claude_client.py`, precisa de `ANTHROPIC_API_KEY` no `.env` — ver Pendências). Cada camada devolve `None` em vez de lançar exceção quando não consegue extrair nada; se as 3 falharem, `metodo_extracao='falhou'` e a tela de revisão abre vazia (nunca trava o fluxo). Cada camada também captura `fornecedor_cnpj` do emitente (determinístico via `emit/CNPJ` no XML; best-effort via regex no texto do PDF; incluído no prompt da IA) além do já existente `fornecedor_nome` — usado na Fase 5 do Financeiro pra resolver/criar o `Fornecedor` da `ContaPagar` gerada automaticamente (ver abaixo). Depois da extração, cada item passa pelo fuzzy match de `resolver_materia_prima()` (`iexact` → `icontains`, mesmo padrão de `importar_planilha.py`) — **nunca cria `MateriaPrima` automaticamente** aqui (diferente do fuzzy match de débito automático da venda), sempre marca `status_match='revisar'` e espera a revisão manual. `estoque.ImportacaoNotaFiscal`/`ItemNotaImportada` são staging — nenhum `MovimentoEstoque` é gravado até `POST /notas/{id}/confirmar/`, que rejeita (400) se algum item não descartado ainda estiver `status_match='revisar'`. `PATCH /notas/{id}/itens/{item_id}/` aceita `{materia_prima}`/`{produto}` (correspondência manual), `{criar_nova_materia_prima: true}` (usa `descricao_extraida` como `nome` via `get_or_create`, `quantidade`/`valor_unitario` reais da nota populam `quantidade_compra`/`valor_compra` — dado real, não placeholder) ou `{quantidade, valor_unitario, descartado}` editados
- **Nota Fiscal → ContaPagar** (Fase 5 do Financeiro, `estoque/views.py::ImportacaoNotaFiscalViewSet._gerar_conta_pagar_da_nota()`, chamado **depois** de `confirmar()` já ter gravado os `MovimentoEstoque` — não mexe nessa parte) — se `financeiro.ConfiguracaoFinanceira.get().nota_gera_conta_pagar`, cria uma `financeiro.ContaPagar` (`origem='nota_fiscal'`, `nota_fiscal=importacao` via `OneToOneField` — garante que confirmar não duplica, ainda que o guard de status já impeça chamar `confirmar()` duas vezes pela API) com `valor` = soma dos itens não descartados, `data_emissao`/`data_vencimento` = hoje (a extração não captura data de emissão da nota), `categoria=None` sempre (ver decisão abaixo). Fornecedor resolvido em `_resolver_fornecedor()`: CNPJ exato → nome `iexact` → nome `icontains` (só se resultado único) → cria `Fornecedor` novo com os dados extraídos; sem nome nem CNPJ extraídos, `fornecedor=None`. Audita `conta_pagar_gerada_nota`. **Decisão de schema**: `financeiro.ContaPagar.categoria` virou `null=True`/`blank=True` (era obrigatória) — decisão tomada com o usuário nesta sessão, porque a extração de nota fiscal não tem como determinar uma categoria contábil sozinha (diferente de `DespesaRecorrente`, que sempre tem categoria escolhida manualmente); o usuário categoriza depois via `PATCH` (mesmo espírito de `MovimentoFinanceiro.categoria`, já opcional pros signals automáticos de venda)
- **`estoque.ConfiguracaoIA`** é singleton (`.get()`) — guarda `extracao_ia_ativa`/`modelo`/`timeout_segundos`. A API key (`ANTHROPIC_API_KEY`) **nunca** fica no model/banco, só em variável de ambiente — é key da Ortex, custo embutido do lado do Ortex (mesma decisão de negócio documentada no spec original). `PATCH /estoque/configuracao-ia/1/` exige login e audita `config_ia_alterada`
- **`eventos.ConfiguracaoContrato` é singleton** — sempre acessado via `ConfiguracaoContrato.get()`. Guarda razão social/CNPJ/endereço/Instagram/telefone/representante da CONTRATADA e todos os percentuais/prazos das cláusulas (sinal, multa, juros, prazos de personalização/rescisão/devolução, foro). `instagram_contratada`/`telefone_contratada` aparecem no rodapé do PDF (`pdf_contrato.py::_header_footer`), abaixo da linha razão social/CNPJ. Nunca hardcodar cláusula numérica no gerador de PDF — ver `Contrato.md`. `PATCH /eventos/configuracao-contrato/1/` exige login e audita `config_contrato_alterada` (GET continua `AllowAny`)
- **`eventos.Contrato`** é um snapshot gravado no momento da emissão (mesma filosofia de `ItemOrcamento`/`SnapshotPrecos`) — `valor_total`/`percentual_sinal`/`valor_sinal`/`data_quitacao` nunca são recalculados ao reabrir/reimprimir um contrato já emitido
- **Alertas de Evento** (`eventos.ConfiguracaoAlertaEvento`, singleton via `.get()`) — dois alertas de cron diário (`python manage.py alertar_eventos`), notificando só telefones internos da equipe cadastrados em `eventos.TelefoneAlertaEvento` (nunca o cliente): (1) **pagamento pendente**, dispara a partir de `dias_antes_pagamento` dias antes do `data_evento` enquanto `saldo_restante > 0` (`Evento.exclude(status__in=['cancelado','entregue']).annotate(saldo=F('valor_total')-F('sinal_pago')).filter(saldo__gt=0, ...)` — usa `F()` em vez da property Python `saldo_restante`, que não funciona em queryset); (2) **aviso de entrega**, a partir de `dias_antes_entrega` dias antes, só para `tipo_entrega='entrega_local'`. Ambos repetem a cada `repetir_pagamento_dias`/`repetir_entrega_dias` configurável, controlado por `eventos.AlertaEventoEnviado` (1 registro por envio de `(evento, tipo)`, não reaproveita `notificacoes.HistoricoMensagem` pra isso porque `HistoricoMensagem.cliente` é FK pra `Cliente`, não pra `Evento`, e aqui o destinatário é telefone da equipe). `PATCH /eventos/configuracao-alertas/1/` exige login e audita `config_alerta_evento_alterada` (GET continua `AllowAny`); `DELETE /eventos/telefones-alerta/{id}/` exige login e audita `registro_excluido` (mesmo padrão do `TaxaEntregaBairro` — só o DELETE exige login, list/create/update continuam `AllowAny`). O texto das mensagens é fixo no código (não é campo configurável como `mensagem_aniversario`/`mensagem_reengajamento` de `ConfiguracaoWhatsApp`) — só dias/intervalo/telefones são configuráveis, por escolha consciente de escopo. `dashboard.DashboardResumoView` expõe a mesma janela em `resumo['alertas']` (sem olhar `AlertaEventoEnviado` — mostra "o que está na janela agora", independente de já ter mandado WhatsApp)
- **Emissão de contrato** (`POST /eventos/orcamentos/{id}/gerar-contrato/`) só é permitida com `Orcamento.status == 'aprovado'` e exige CPF/RG/nacionalidade/profissão/estado civil do cliente preenchidos (podem estar vazios no cadastro normal — são exigidos só neste momento) — ver `Contrato.md`. Exige login (`IsAuthenticated`, único override de `get_permissions()` no `OrcamentoViewSet` — resto continua `AllowAny`) e grava `contrato_emitido` em `auditoria.LogAuditoria`. `ContratoViewSet.enviar_whatsapp` também exige login (`contrato_enviado` no log) — `list`/`retrieve`/`pdf` continuam `AllowAny`, sem mudança
- **Reenvio de Contrato** — `enviar-whatsapp/` (acima) **não trava por status** de orçamento/evento/contrato (`Contrato.pode_enviar` existe no model mas não é usado por nenhuma view — código morto hoje), então o mesmo endpoint serve tanto para o envio inicial quanto para reenvios. `OrcamentoListSerializer`/`EventoListSerializer` expõem `contrato` (via `ContratoResumoSerializer`: id/numero/status/status_display/contratante_nome — o mais recente, resolvido com `prefetch_related('contratos')` nas duas viewsets). O frontend (`Orcamentos.jsx`/`Eventos.jsx`) mostra um botão "Reenviar Contrato" na coluna de ações da listagem e no modal de detalhe sempre que esse campo não é nulo, abrindo `ModalReenviarContrato` (componente local em cada página) que chama o mesmo `POST /eventos/contratos/{id}/enviar-whatsapp/`
- **`eventos.ImagemInspiracao`** é a galeria de imagens de referência (uso interno da equipe, nunca entra no PDF/WhatsApp do orçamento/contrato) anexada ao `Orcamento` OU ao `Evento` inteiro (não por item) — `orcamento`/`evento` são FKs opcionais e um `CheckConstraint` (`imageminspiracao_exatamente_um_dono`) garante que exatamente um dos dois está preenchido. Um Evento pode adicionar/remover imagem a qualquer momento, em qualquer status (`POST/DELETE /eventos/{id}/imagens/...`, mesma liberdade de status que já valia pra `POST/DELETE /eventos/orcamentos/{id}/imagens/...`) — **sem duplicar a galeria**: quando o Evento tem `orcamento_origem`, a imagem nova continua sendo anexada ao **Orçamento** de origem (`EventoViewSet.adicionar_imagens` resolve `origem = getattr(evento, 'orcamento_origem', None)` e usa `orcamento=origem` nesse caso, `evento=evento` só quando não há origem); `EventoDetailSerializer.get_imagens_inspiracao` espelha essa mesma regra na leitura (lê de `orcamento_origem.imagens_inspiracao` quando existe, senão de `evento.imagens_inspiracao_diretas`). Migration `0015_imageminspiracao_evento_direto` — mesma filosofia de nunca duplicar o que a relação já entrega, como o Contrato faz com os itens do Orçamento
- **`MEDIA_URL`/`MEDIA_ROOT`** estão configurados em `config/settings.py` (`/media/`, `BASE_DIR / 'media'`) desde a feature de Imagens de Inspiração — é o único `ImageField` do projeto de fato exercitado em produção. Em prod, o Nginx tem um `location /media/ { alias .../media/; }` próprio (não é servido pelo Django/Gunicorn) — qualquer novo `ImageField`/`FileField` já pode reaproveitar essa infra, não precisa recriar
- **Cuidado com `prefetch_related` + criação de objeto relacionado na mesma request**: se uma view faz `self.get_object()` sobre um queryset com `prefetch_related('algo')` e, na mesma request, cria/deleta um objeto relacionado via `Model.objects.create(fk=obj, ...)` (sem passar pelo manager `obj.algo`), o cache do prefetch fica stale e `obj.algo.all()` (inclusive dentro do serializer) não reflete a mudança. Sempre que fizer isso, chamar `obj.refresh_from_db()` antes de serializar a resposta. Já corrigido em `adicionar_imagens`/`remover_imagem` (`OrcamentoViewSet`), `adicionar_pagamento` (`EventoViewSet`), e — bug real reportado por usuário, reproduzido e corrigido — em `adicionar_item`/`remover_item`/`editar_item` de `OrcamentoViewSet`/`EventoViewSet` e `PedidoPDVViewSet`, e em `adicionar_item`/`remover_item` de `FichaTecnicaViewSet`: sem o `refresh_from_db()`, `recalcular_totais()` lia o cache velho de `self.itens.all()` e **persistia** `valor_total`/`total` errado no banco (não era só um problema de exibição — o valor incorreto ficava salvo até a próxima alteração). Qualquer novo endpoint que crie/edite/remova item de uma coleção prefetched e recalcule um total a partir dela precisa do mesmo cuidado
- **`FichaTecnica.custo_ingredientes`** usa `sum(..., Decimal('0'))` com `start` explícito — não tirar esse `start`. `sum()` de um iterável vazio (ficha sem nenhum item) devolve o `int` `0` por padrão; `0 / self.rendimento` em Python 3 é *true division* e vira `float`, e `float + Decimal` (o `embalagem_custo`) explode com `TypeError` em `custo_total_unitario`. Bug real encontrado ao corrigir o `refresh_from_db()` acima (remover o último item de uma ficha passou a de fato zerar `itens.all()`, o que expôs esse cálculo)
- **`auditoria.mixins.AuditoriaDestroyMixin`** — mixin genérico pra auditar o `destroy()` padrão de um `ModelViewSet`: grava `ACAO_REGISTRO_EXCLUIDO` (com `detalhes.model`/`id`/`descricao` + campos extras via `campos_log_exclusao`) e traduz `ProtectedError` (FK `on_delete=PROTECT`) numa resposta 400 amigável em vez do 500 cru do Django. Usar em qualquer novo `ModelViewSet` que precise de DELETE auditado — já aplicado em `Cliente`, `Tag`, `Produto`, `CategoriaProduto`, `TaxaEntregaBairro`, `PedidoPDV`, `Evento`, `Orcamento`, `LocalEvento`, `MateriaPrima`, `FichaTecnica`. A view precisa combinar com `authentication_classes = [TokenAuthentication]` + `get_permissions()` exigindo `IsAuthenticated` na action `destroy` (e nas `remover-*` correspondentes, instrumentadas manualmente com `registrar()` direto, já que não passam por `perform_destroy`). Endpoint `GET /api/v1/auditoria/logs/?model=Cliente` filtra por `detalhes.model`
- **`auditoria.mixins.AuditoriaCreateMixin`/`AuditoriaUpdateMixin`/`AuditoriaStatusMixin`** — mesma filosofia do `AuditoriaDestroyMixin`, hoje aplicados só em `OrcamentoViewSet`/`EventoViewSet` (não em todos os ModelViewSets — só onde criação/edição/status faz sentido auditar). `AuditoriaCreateMixin.perform_create()` grava `ACAO_REGISTRO_CRIADO`; `AuditoriaUpdateMixin.perform_update()` grava `ACAO_REGISTRO_ATUALIZADO` só com os campos de `campos_log_atualizacao` que vieram no payload E mudaram de valor (antes/depois, mesmo padrão das configs singleton). Para usar `AuditoriaUpdateMixin` num `update()` já customizado (como o do `OrcamentoViewSet`, que valida status antes de salvar), a view precisa chamar `self.perform_update(serializer)` em vez de `serializer.save()` direto — mesmo raciocínio vale para `create()`/`self.perform_create(serializer)`. `AuditoriaStatusMixin.log_mudanca_status(obj, de, para)` não é automático — chamar manualmente dentro de cada `@action` de mudança de status, depois do `.save()`; grava `ACAO_STATUS_ALTERADO` genérico (desambiguado por `detalhes.model`, mesmo espírito do `registro_excluido`). Adicionar item usa `ACAO_ITEM_ADICIONADO` (também genérico, cobre `ItemOrcamento` e `ItemEvento`). A conversão de Orçamento em Evento é o único marco de negócio com constante própria: `ACAO_ORCAMENTO_CONVERTIDO`
- **`auditoria.PresencaEdicao`** (heartbeat de presença, `POST /api/v1/auditoria/presenca/` via `PresencaHeartbeatView`) — **não é WebSocket**: é polling REST comum (frontend chama a cada 15s enquanto o modal de Orçamento/Evento estiver aberto), decisão deliberada porque o projeto roda só Gunicorn/WSGI síncrono, sem Channels/Redis/ASGI. O endpoint faz `update_or_create` da presença do usuário autenticado e devolve quem mais está ativo no mesmo `(model, objeto_id)` numa janela de 40s (`JANELA_PRESENCA_SEGUNDOS` em `auditoria/views.py`). `unique_together=('usuario','model','objeto_id')` garante no máximo 1 linha por combinação — a tabela cresce por usuário×objeto já visitado, não por heartbeat, então não precisa de limpeza periódica por ora. É só informativo ("Fulano também está vendo isso agora") — não é uma trava/lock de edição
- **`ifood.ConfiguracaoIFood` não é singleton de verdade** (usa `.objects.first()`, não `.get()`) — `ConfiguracaoIFoodViewSet.destroy()` está bloqueado de propósito (sempre `405`), pra nunca perder client_id/secret/tokens de produção. Se um dia virar singleton de verdade (`.get()` como os outros 3 configs), reavaliar se ainda faz sentido bloquear o DELETE
- **`eventos.PagamentoEvento`** registra as parcelas de pagamento de um `Evento` (valor/forma_pagamento/status/data_pagamento/observação/comprovante). `comprovante` é um `FileField` opcional (imagem ou PDF) enviado no momento do registro do pagamento (`multipart/form-data`, mesmo padrão de `ImagemInspiracao`/`ImageField` de produto — ver upload de `FormData` no frontend). `Evento.sinal_pago` **nunca** é gravado direto — é sempre recalculado via `Evento.recalcular_sinal_pago()` (soma dos pagamentos com `status='pago'`), chamado após criar/remover um `PagamentoEvento` (`POST/DELETE /eventos/{id}/pagamentos/...`). O sinal informado na criação do Evento ou na conversão de Orçamento em Evento (`sinal_pago` no body) também vira um `PagamentoEvento` inicial (forma `outro`, status `pago`) em vez de setar o campo diretamente. Toda criação/remoção de `PagamentoEvento` é auditada via `auditoria.utils.registrar()` — nas actions dedicadas (`adicionar_pagamento`/`remover_pagamento`) o login é obrigatório; no sinal inicial (criação do Evento ou conversão do Orçamento) é oportunista, sem bloquear o fluxo se ninguém estiver logado
- **Edição de Orçamento**: `OrcamentoViewSet.update()` só permite `PATCH/PUT` quando `status` é `rascunho` ou `enviado` (400 caso contrário); mesma restrição vale para editar item (`PATCH /eventos/orcamentos/{id}/itens/{item_id}/editar/`). Depois de aprovado/enviado além desses estágios, o orçamento é imutável (mesma filosofia do `Contrato` como snapshot)
- **Brindes e Permutas — Fases 1-5 (completo)** (spec completa em `BRINDES_PERMUTAS.md`) — campo
  `natureza` (choices `venda`/`brinde`/`permuta`, default `venda`) em `eventos.ItemOrcamento`,
  `eventos.ItemEvento` e `pdv.ItemPedidoPDV` (granularidade **por item**, não por pedido/orçamento/evento
  inteiro — o caso real é misto, itens vendidos e itens de brinde no mesmo carrinho). O `save()` dos três
  models zera `preco_total` quando `natureza != 'venda'` (`Decimal('0.00')`) — `preco_unit` continua sempre o
  preço de tabela (snapshot do catálogo no momento em que o item foi adicionado), vira a referência de "valor
  de mercado" que o PDF mostra riscado (Fase 3). Como `recalcular_totais()` dos três (`Orcamento`,
  `Evento`, `PedidoPDV`) já soma `preco_total` sem filtro (`sum(i.preco_total for i in self.itens.all())`), o
  efeito cascateia sozinho — **nenhum desses três métodos foi tocado**. Único ponto de atenção real:
  `OrcamentoViewSet.converter_em_evento` propaga `natureza=item.natureza` na criação de cada `ItemEvento` —
  sem isso, todo item de brinde/permuta de um orçamento convertido viraria venda cobrada no evento (bug real
  evitado, coberto por teste). Débito de estoque **não muda** — já debita por `produto`+`quantidade`, sem
  olhar preço, então brinde/permuta já saem do estoque físico corretamente hoje. Serializers de criação/edição
  de item (`ItemOrcamentoCreateSerializer`, `ItemEventoCreateSerializer`, `ItemPedidoPDVCreateSerializer`) e os
  de leitura (`ItemOrcamentoSerializer`, `ItemEventoSerializer`, `ItemPedidoPDVSerializer`) ganharam o campo —
  sem endpoint novo, só payload (ver Endpoints).
  **Fase 2**: guard de valor zero em `financeiro/signals.py` — `_registrar_venda_pdv()` retorna cedo (antes do
  check de idempotência) quando `pedido.total <= 0` (pedido 100% brinde/permuta), e `_registrar_pagamento_evento()`
  tem a mesma guarda simétrica pra `pagamento.valor <= 0` (defensiva — `PagamentoEvento` não deriva de item, é
  valor digitado manualmente, dificilmente chega a zero pela UI, mas a API/admin permitiria). Sem o guard,
  um pedido 100% brinde geraria uma entrada fantasma de R$0,00 no ledger e no `fluxo-caixa/`. `ContaPagar`/
  `ContaReceber` **não entram** nessa feature — só o ledger direto (PDV `no_ato`/`PagamentoEvento`). Também
  Fase 2: `relatorios.ProdutosMaisVendidosView._qs_pdv()`/`_qs_eventos()` ganharam `natureza='venda'` no
  `.filter()` — item de brinde/permuta não entra mais nem na quantidade nem no valor do ranking (antes da
  Fase 2 já não entrava no valor, porque `preco_total=0`, mas ainda inflava a quantidade). `_qs_ifood()`
  **não mudou** — `ItemPedidoIFood` não tem campo `natureza` (o conceito de brinde/permuta não existe no
  iFood, canal externo), nada a filtrar ali. **Fase 3**: `pdf_orcamento.py`/`pdf_contrato.py` — item com
  `natureza != 'venda'` ganha `" — {label}"` no nome (via `item.get_natureza_display()`) e a célula de
  `preco_unit` na tabela de itens vira um `Paragraph` com `<strike>` (só nesse caso — resto da tabela continua
  string plana, mais leve). `preco_total` já sai `R$ 0,00` sozinho (vem do model). `pdf_resumo_cozinha.py`
  **não muda** — já não expõe preço de item nenhum, brinde/permuta aparecem normalmente na lista de produção
  (decisão do spec). **Fase 4**: seletor de natureza (`components/ui/index.jsx::SeletorNatureza` — `<select>`
  Venda/Brinde/Permuta reusado nos 3 forms — e `NaturezaBadge`, que só renderiza quando `natureza != 'venda'`)
  em `Orcamentos.jsx` (form de criação + `ModalDetalheOrcamento` adicionar/editar item),
  `Eventos.jsx` (carrinho de criação + painel "adicionar itens" do detalhe) e `PDV.jsx` (carrinho). Quando
  `natureza != 'venda'`, o input de preço fica `disabled` (sempre = preço de tabela do produto selecionado,
  nunca editável) e a linha mostra o preço riscado (`textDecoration: 'line-through'`) — mesmo tratamento do
  PDF. `PDV.jsx` nunca teve input de preço editável no carrinho (preço sempre vem do catálogo via
  `adicionarItem(prod)`), então ali o requisito já valia de graça — só faltava o seletor.
  **Bug real encontrado e corrigido nesta fase**: `OrcamentoCreateSerializer.create()` e
  `EventoCreateSerializer.create()` (`eventos/serializers.py`) somavam a variável Python local `total`
  (`preco_unit * quantidade`, sem olhar `natureza`) no `subtotal` do Orçamento/Evento, em vez de
  `item.preco_total` (o valor de fato persistido pelo `save()` do model, já zerado pra brinde/permuta) — só
  a criação inicial **com itens no mesmo payload** batia nesse bug (`POST /orcamentos/`/`POST /eventos/`);
  `adicionar_item`/`editar_item`/`converter_em_evento` (Fase 1) já liam `item.preco_total` corretamente.
  `pdv.PedidoPDVCreateSerializer.create()` já não tinha esse bug (já somava `item.preco_total`, conferido
  antes de mexer). Corrigido substituindo `subtotal += total` por `subtotal += item.preco_total` nos dois
  `create()`, com 2 testes de regressão (`test_criar_orcamento_com_itens_mistos_via_api_subtotal_ignora_brinde`/
  `test_criar_evento_...`) — mesmo padrão de "guardar o bug encontrado como teste" já usado em outras fases
  do projeto. Validado manualmente via Playwright headless (usuário de teste `TESTE Fase4 Brindes`, criado e
  removido na mesma sessão) nos 3 fluxos — screenshots confirmaram badge/riscado/total corretos antes de
  aplicar o fix, e o bug do subtotal foi pego exatamente por essa validação manual, não pelos testes
  automatizados que só cobriam os métodos de item isolados.
  **Fase 5 ("PDV Avulso")**: confirmado sem código novo — saída avulsa de brinde/permuta (sem
  Orçamento/Evento) já é só um `PedidoPDV` comum criado pela tela que já existe, com item(s)
  `natureza=brinde`/`permuta`. `pdv.PedidoPDV.pagamento` já era `blank=True` desde antes (pedido 100%
  brinde/permuta deixa o campo vazio, sem erro de validação); `PDV.jsx::salvar()` nunca exigiu
  `form.pagamento` preenchido. `pdv/signals.py::_sincronizar()` espelha pro `PedidoUnificado` sem
  nenhum tratamento especial por valor — um pedido de `total=0` sincroniza normalmente (numeração
  sequencial e histórico unificado "de graça", como o spec previa). Travado com teste de regressão
  (`test_pedido_avulso_100_por_cento_brinde_sem_pagamento_sincroniza_pedido_unificado`,
  `pdv/tests.py`) — as 5 fases do `BRINDES_PERMUTAS.md` estão completas
- **Resumo de Cozinha** (`GET /eventos/{id}/resumo-cozinha/`, `eventos/pdf_resumo_cozinha.py::gerar_pdf_resumo_cozinha(evento)`) — PDF operacional interno (não client-facing) com a lista de itens do Evento agrupada por categoria, pra a cozinha montar a produção. Usa ReportLab **Platypus** (não canvas cru como `pdf_orcamento.py`), porque a lista de itens tem tamanho variável e pode quebrar página — e **sem** timbre/marca d'água (`_mesclar_timbre` nunca é chamado aqui). Itens são ordenados por `produto__categoria__ordem`/`produto__categoria__nome`/`nome` na própria query e agrupados em memória com `itertools.groupby` (nunca reordenar em Python depois) — item sem `produto` ou cujo `produto` não tem `categoria` cai no grupo `"Outros"`, sempre por último (a ordenação por `ordem` já garante isso via `NULLS LAST` do Postgres, então o agrupamento em Python não precisa reordenar nada). **Nunca expõe preço** (`preco_unit`/`preco_total`/`valor_total`) — é 100% operacional. Todo texto livre (nome do cliente, endereço do local, observação do item/evento) passa por `xml.sax.saxutils.escape()` antes de virar `Paragraph`, porque a mini-sintaxe XML do ReportLab quebra a geração do PDF se o texto tiver `&`/`<`/`>` sem escapar. Endpoint é `AllowAny` (mesmo padrão de `OrcamentoViewSet.pdf`/`ContratoViewSet.pdf` — é leitura pura, não audita). Botão "Imprimir resumo de cozinha" (`ti-printer`) em dois lugares no frontend — card de detalhe do Evento e linha da lista — ambos chamando `eventosApi.resumoCozinha(id)` (blob) e abrindo com `window.open(url, '_blank')`, mesmo padrão de `handlePdf`/`handleVerPdf` já usado pros outros PDFs do sistema
- **Criação/edição/status/item de Orçamento e Evento exigem login** (`create`, `update`/`partial_update`, `enviar`/`aprovar`/`recusar`/`restaurar` no Orçamento, `confirmar`/`iniciar_producao`/`marcar_pronto`/`entregar`/`cancelar` no Evento, `adicionar_item`/`editar_item`) — mudança de comportamento em relação ao que existia antes desta auditoria (essas actions eram `AllowAny`). Único motivo de exigir login aqui é garantir que sempre exista um ator no log; `converter_em_evento` e `enviar_whatsapp` continuam `AllowAny` de propósito (oportunistas, capturam o ator só quando o token vier)
- **`dashboard/` é um app só-leitura, sem models** — `DashboardResumoView` (`GET /api/v1/dashboard/resumo/`) apenas agrega dados que já existem em `pedidos.PedidoUnificado` e `eventos.Evento`/`PagamentoEvento`. Multi-empresa desde a Fase 5 (`?empresa=`/`?empresa=todas`, ver bloco "Dashboard e Relatórios por empresa" mais abaixo). Regra importante: a receita de **Eventos** no dia (`canais.eventos.recebido_hoje` e a fatia "eventos" do `grafico_7dias`) vem **exclusivamente** de `PagamentoEvento` com `status='pago'` e `data_pagamento` do dia — nunca de `Evento.valor_total` nem do status de entrega (é recebimento efetivo de caixa, não valor do pedido). Já `ticket_medio.eventos` é a exceção: usa `Evento.valor_total` (não `PagamentoEvento`) dos eventos `status='entregue'` nos últimos 30 dias, porque ali a métrica é tamanho médio de venda, não fluxo de caixa. `fila_operacional` cruza os 3 canais lendo só `PedidoUnificado` (o `Evento` já sincroniza pra lá via `EVENTO_STATUS_MAP`), nunca faz query separada em `eventos.Evento`
- **`relatorios.ProdutosMaisVendidosView`** (`GET /relatorios/produtos-mais-vendidos/`, `AllowAny`, sem model próprio) — ranking de produtos mais vendidos consolidando iFood + PDV + Eventos por quantidade e valor, num período configurável. Multi-empresa desde a Fase 5 (`?empresa=`/`?empresa=todas` — iFood filtra por `pedido__empresa`, PDV/Eventos só entram na soma quando a empresa resolvida é a matriz ou 'todas', ver bloco "Dashboard e Relatórios por empresa"). Só conta venda **de fato concretizada**: iFood `status='CONCLUDED'` (via `ItemPedidoIFood`), PDV `status` em confirmado/em_preparo/pronto/concluido — exclui aberto/cancelado (via `ItemPedidoPDV`), Evento `status='entregue'` (via `ItemEvento`). **Orçamentos ficam de fora de propósito** — `ItemOrcamento` é cotação, não venda fechada, mesmo raciocínio de nunca materializar `ContaReceber` pra Evento. Agrupa por **nome do item normalizado** (`unicodedata` remove acento, lowercase, colapsa espaços) — nunca por `pdv.Produto`, porque `ItemPedidoIFood` nunca tem FK pra `Produto` (só nome em texto, mesma limitação já documentada no débito automático de estoque); então "Bolo de Chocolate" e "BOLO DE CHOCOLATE" agrupam junto entre canais, mas variações reais de nome (ex: com/sem tamanho) ficam separadas — decisão consciente de simplicidade, sem fuzzy match. `canal` aceita múltiplos valores (`?canal=ifood&canal=pdv`, default: todos os 3), `ordenar` é `quantidade` (default) ou `valor`, `limit` entre 1-200 (default 30). Resposta sempre traz o breakdown por canal de cada produto (`produtos[].canais.{ifood,pdv,eventos}`), não só o total agregado. Só JSON — sem export Excel/PDF (diferente de `RelatorioIFoodView`), decisão consciente desta entrega; revisitar se o usuário pedir
- **Módulo Financeiro** (app `financeiro/`, spec completa em `FINANCEIRO.md` — em andamento, fases 0-6 de 8 concluídas) — duas camadas, mesma filosofia de `Evento`/`PagamentoEvento`: `ContaPagar`/`ContaReceber` são a obrigação projetada (tem vencimento e status, pode nunca acontecer); `MovimentoFinanceiro` é o ledger (fonte única da verdade do que passou pelo caixa). Requisito de revenda: **nenhum valor da Arretado hardcoded** — `CategoriaFinanceira` nasce vazia, sem seed automático
- **Financeiro por empresa** (Fase 4 do multi-empresa, `MULTIEMPRESA.md` — numeração de spec diferente das
  fases do `FINANCEIRO.md` acima, não confundir) — caixa e obrigações são por CNPJ. `financeiro.ContaBancaria`/
  `ContaPagar`/`ContaReceber`/`DespesaRecorrente` ganharam FK `empresa` (`PROTECT`, ciclo `null=True` → data
  migration atribuindo `Empresa.get_padrao()` → `null=False`, mesmo ciclo da Fase 1 do iFood).
  `financeiro.ConfiguracaoFinanceira` **deixou de ser singleton global** — ganhou `OneToOneField` `empresa` e
  `ConfiguracaoFinanceira.get()` virou **`ConfiguracaoFinanceira.get(empresa)`** (`get_or_create(empresa=...)`,
  abandona a convenção antiga de `pk=1`) — todo call site precisou ser atualizado (`financeiro/signals.py`,
  os 2 crons, `financeiro/views.py`, e o único ponto fora do app: `estoque/views.py::_gerar_conta_pagar_da_nota()`,
  que resolve sempre `Empresa.get_padrao()` porque Estoque continua mono-empresa por escopo).
  `financeiro.MovimentoFinanceiro` **não ganhou campo próprio** — só uma property `empresa` (`return
  self.conta.empresa`); filtro de queryset é sempre via `conta__empresa`, nunca denormalizar.
  `CategoriaFinanceira`/`Fornecedor`/`TelefoneAlertaFinanceiro` continuam **compartilhados** entre empresas
  (plano de contas único, equipe única — sem FK). Sinais de venda (`financeiro/signals.py`) resolvem a
  `ConfiguracaoFinanceira`/`conta_padrao_vendas` **da empresa certa**: PDV e `PagamentoEvento` são mono-empresa
  (sempre `Empresa.get_padrao()`, canais mono-empresa por escopo do multi-empresa); iFood usa `pedido.empresa`
  (FK já existente desde a Fase 1) — permite a MANGAIO operar em `repasse` e a matriz em `no_ato`
  simultaneamente, cada uma batendo na sua própria conta. Todos os ViewSets do app (exceto
  `CategoriaFinanceiraViewSet`/`FornecedorViewSet`/`TelefoneAlertaFinanceiroViewSet`, que ficam sem filtro por
  serem compartilhados) e o `FluxoCaixaView` aceitam `?empresa=<id>` (helper `financeiro/views.py::
  _resolver_empresa()` — `?empresa=` explícito > `empresa_ativa` do usuário autenticado > `Empresa.get_padrao()`,
  nunca `.objects.first()`) e `?empresa=todas` (sentinela de consolidado, devolve `None` — sem filtro).
  `contas-receber/resumo/` só soma o saldo dinâmico de `Evento` quando a empresa resolvida é `None` (todas) ou
  a própria matriz (Eventos é mono-empresa, não faz sentido aparecer no resumo isolado da MANGAIO). Actions
  `IsAuthenticated` de criação (`ContaBancariaViewSet`/`ContaPagarViewSet`/`ContaReceberViewSet`/
  `DespesaRecorrenteViewSet`.`perform_create()`, e a action `manual/` de `MovimentoFinanceiroViewSet`) validam
  via `_validar_empresa_vinculo()` (duplica a lógica de 3 linhas de `usuarios.views._empresas_efetivas` — não
  importa a função privada de outro app) que o `?empresa=` resolvido está entre as empresas do usuário (admin
  vê todas as ativas). `ConfiguracaoFinanceiraSerializer.validate_conta_padrao_vendas()` rejeita uma conta
  bancária de empresa diferente da configuração. Frontend: `Financeiro.jsx` consome `useAuth().empresaAtiva`/
  `empresas` (contexto global já existente desde a Fase 2, não um seletor local como o de `IFood.jsx`) — ver
  bloco próprio na Estrutura de Pastas acima
- **Dashboard e Relatórios por empresa** (Fase 5 do multi-empresa, `MULTIEMPRESA.md`) — `dashboard/views.py::DashboardResumoView`
  e os dois endpoints de `relatorios/views.py` (`RelatorioIFoodView`, `ProdutosMaisVendidosView`) aceitam
  `?empresa=<id>`/`?empresa=todas` via um `_resolver_empresa()` local em cada app (mesmo contrato de
  `financeiro/views.py::_resolver_empresa()` — `?empresa=` explícito > `empresa_ativa` do usuário autenticado
  > `Empresa.get_padrao()`, `'todas'` devolve `None` — duplicado a propósito, nunca importado entre apps). As
  três views ganharam `authentication_classes = [TokenAuthentication]` (mantendo `permission_classes = [AllowAny]`,
  mesmo padrão oportunista de `OrcamentoViewSet.converter_em_evento` — captura `request.user.empresa_ativa`
  quando o token vier, sem exigir login). `PedidoUnificado` (iFood/PDV) e `ifood.PedidoIFood`/`ItemPedidoIFood`
  têm FK `empresa` própria (desde a Fase 1) e filtram naturalmente; `eventos.Evento`/`PagamentoEvento` e o
  estoque (`MateriaPrima`/`Produto`) são mono-empresa **sem FK própria** — por isso o dashboard usa o gate
  explícito `eventos_habilitado = empresa is None or empresa.padrao` (e `relatorios` usa
  `mono_empresa_habilitado` equivalente pro PDV/Eventos de `ProdutosMaisVendidosView`) pra zerar esses blocos
  numa visão de empresa não-matriz, em vez de simplesmente não filtrar e vazar dado da matriz. Visão de uma
  empresa não-matriz (ex: MANGAIO) ganha o card/campo `repasse_ifood_a_receber` no dashboard (soma de
  `financeiro.ContaReceber` `canal='ifood'` `pendente`/`parcial` da empresa, calculado sempre — inclusive pra
  matriz/consolidado, onde normalmente é zero se ela opera em `no_ato`). `empresas.Empresa.modulos_ocultos`
  (`JSONField`, lista de slugs de rota — novo campo desta fase, migration `0003_modulos_ocultos_fase5`) some
  com itens do menu que a empresa não usa: `Sidebar.jsx` filtra `NAV` por
  `!empresaAtiva?.modulos_ocultos?.includes(item.to.replace(/^\//, ''))` — puramente cosmético, `App.jsx`
  continua registrando todas as rotas (não é controle de acesso, ver "O Que NÃO Fazer"); `Empresas.jsx` edita
  a lista via checkboxes de `MODULOS_OCULTAVEIS` (constante fixa no componente — Eventos, Orçamentos, Locais
  de Evento, Catálogo, Fichas Técnicas, Central de Preços, Estoque, PDV Próprio, Catálogo PDV, Anota AI,
  Taxas de Entrega; nunca Dashboard/Financeiro/Relatórios/Clientes/WhatsApp/Configurações, que são
  compartilhados ou já multi-empresa). Frontend: `Dashboard.jsx`/`Relatorios.jsx` consomem
  `useAuth().empresaAtiva`/`empresas` com o mesmo chip/segmented-control "Todas as empresas" já usado em
  `Financeiro.jsx`; `Dashboard.jsx` calcula `matrizView` (`!resumo.empresa || resumo.empresa.padrao`) pra
  decidir o layout (esconde cards PDV/Eventos/Próximos Eventos, troca "A receber (eventos)" pelo painel de
  repasse iFood).
- **`financeiro.MovimentoFinanceiro` é o ledger — fonte única da verdade.** Todo movimento passa por `MovimentoFinanceiro.registrar()` (nunca `.objects.create()` direto em view/signal/command), mesmo contrato de `estoque.MovimentoEstoque.registrar()`: `transaction.atomic()` + `select_for_update()` na `ContaBancaria` (evita race condition entre baixas/vendas concorrentes), quantiza `valor` a 2 casas antes de `full_clean()`, calcula `saldo_posterior` e atualiza `ContaBancaria.saldo_atual` via `update_fields`. `UniqueConstraint(origem_tipo, origem_id)` é **condicional** — só se aplica quando `origem_tipo in ('pdv','ifood','evento_pagamento')` (idempotência dos signals de venda, ver `financeiro/signals.py`); baixas de conta (`conta_pagar`/`conta_receber`, permitem múltiplos movimentos parciais) e `manual` (livre — usado pelos estornos automáticos) ficam de fora da constraint. Violar essa constraint condicional é pego por `full_clean()` como `ValidationError` (Django valida `UniqueConstraint` com `condition` no nível do model, não só no banco) — `registrar()` não faz try/except em cima disso, quem chama é quem decide como tratar (os signals de venda fazem um `.exists()` explícito antes de chamar, mesmo padrão de `estoque.signals`). **Não implementar DELETE de `MovimentoFinanceiro`** — ledger imutável, erro se corrige com um movimento manual inverso (estorno), nunca apagando o original. `POST /financeiro/movimentos/manual/` (Fase 6, exige login) é o endpoint pra isso — chama `MovimentoFinanceiro.registrar()` com `origem_tipo='manual'` (fora da constraint condicional, permite múltiplos lançamentos livremente), audita `movimento_manual`
- **`financeiro.ContaPagar`** é a obrigação projetada (`CP-0001` via `proximo_numero()`, mesmo padrão de `Orcamento`/`Contrato`/`Evento`). `valor_pago`/`status` **nunca** são gravados direto — sempre via `recalcular_valor_pago()` (soma os `MovimentoFinanceiro` com `origem_tipo='conta_pagar'`/`origem_id=self.id`/`tipo='saida'`; deriva `paga` se `valor_pago >= valor`, `parcial` se `0 < valor_pago < valor`, senão mantém `pendente`) — mesma filosofia de `Evento.sinal_pago`. `cancelar/` só é permitido com `valor_pago == 0`. `PATCH` só é permitido com `status == 'pendente'` (mesma restrição de `Orcamento.update()` — depois de qualquer baixa, a conta fica imutável nesses campos). Campo `recorrente` (FK pra `DespesaRecorrente`, opcional, `PROTECT`) é preenchido só pelo cron `gerar_contas_recorrentes` — nunca pela API (`read_only_fields` no serializer); `UniqueConstraint(recorrente, data_vencimento)` condicional (`recorrente__isnull=False`) garante que o cron nunca duplica a mesma competência. **Cuidado com ordem de operações na migration**: quando o autodetector do Django gera `AddConstraint` referenciando um campo que só existe depois de um `AddField` posterior na mesma migration, ele pode ordenar o `AddConstraint` **antes** do `AddField` (bug real encontrado nesta feature — `FieldDoesNotExist: ContaPagar has no field named 'recorrente'` ao rodar `migrate`) — sempre conferir a ordem das `operations` geradas quando `makemigrations` cria constraint condicional sobre campo novo, e mover o `AddConstraint` pra depois do `AddField` correspondente se necessário. `categoria` é **opcional** (`null=True`/`blank=True`, decisão da Fase 5 — ver "Nota Fiscal → ContaPagar" abaixo) — `ContaPagar` gerada automaticamente por nota fiscal nasce sem categoria, `DespesaRecorrente` sempre tem (copiada do molde); o serializer trata `categoria=None` como válido (`validate_categoria` só valida `tipo == 'saida'` quando uma categoria é de fato informada)
- **`financeiro.ContaReceber`** espelha `ContaPagar` pro lado de entradas, mas **só existe pra iFood no modo `repasse` ou lançamento manual avulso** — `CR-0001` via `proximo_numero()`. `valor_recebido`/`status` nunca gravados direto, sempre via `recalcular_valor_recebido()` (mesma filosofia). `canal` (`ifood`/`manual`) é read-only na API — `POST /financeiro/contas-receber/` sempre cria `canal='manual'`/`origem_canal='manual'` via `perform_create()`, os registros `canal='ifood'` só nascem no signal. `UniqueConstraint(origem_canal, origem_id)` condicional (`origem_canal != 'manual'`) garante idempotência do signal, mesmo padrão de `MovimentoFinanceiro`. **Eventos e PDV nunca materializam `ContaReceber`** (ver "O Que NÃO Fazer") — o saldo de Eventos é sempre consultado dinamicamente (`Evento.valor_total - sinal_pago`, eventos não `cancelado`/`entregue`) tanto em `contas-receber/resumo/` quanto em qualquer tela futura; PDV e iFood `no_ato` batem direto no ledger porque o dinheiro já entrou no caixa, sem passar por obrigação projetada
- **`financeiro.DespesaRecorrente`** é o molde de uma despesa que se repete todo mês (aluguel, energia, assinatura). `dias_vencimento` é um `JSONField` com lista de dias do mês (ex.: `[1, 30]`); `datas_no_periodo(data_inicio, data_fim)` resolve os vencimentos reais dentro de uma janela, varrendo mês a mês — **dia inexistente no mês (31 em fevereiro) cai no último dia daquele mês, nunca rola pro mês seguinte**. Sem endpoint de `DELETE` (só `GET/POST/PATCH`) — pausar é `ativo=False`; `categoria`/`fornecedor` são `PROTECT`, então excluir com contas já geradas quebraria de qualquer forma
- **`financeiro.ConfiguracaoFinanceira` é singleton** — sempre acessado via `ConfiguracaoFinanceira.get()`. `conta_padrao_vendas` (FK `ContaBancaria`) é o destino de todo movimento automático gravado pelos signals de venda (`pdv.PedidoPDV` confirmado, `ifood.PedidoIFood` concluído no modo `no_ato`, `eventos.PagamentoEvento` pago) — sem ela configurada, o signal correspondente loga warning e **não grava nada** (nunca cria `ContaBancaria` sozinho). `PATCH /financeiro/configuracao/1/` exige login e audita `config_financeira_alterada` (GET continua `AllowAny`)
- **Baixa de `ContaPagar`/`ContaReceber`** (`POST .../baixa/`) exige login, cria um `MovimentoFinanceiro` (`saida`/`entrada` respectivamente) e chama `recalcular_valor_pago()`/`recalcular_valor_recebido()` — rejeita (400) valor de baixa maior que o saldo restante e conta já quitada/cancelada. Audita `baixa_registrada`. Os dois compartilham o mesmo `BaixaContaSerializer` (campos `data`/`valor`/`conta`/`forma`/`comprovante`) — genérico o bastante pra servir os dois lados do ledger sem duplicar validação
- **Contas a Pagar Recorrentes** (`financeiro.DespesaRecorrente`/`AlertaFinanceiroEnviado`) — dois crons diários, mesma filosofia dos módulos Eventos/Estoque: (1) `gerar_contas_recorrentes` materializa uma `ContaPagar` (`origem='recorrente'`) por vencimento de cada `DespesaRecorrente` ativa dentro do horizonte configurado (`ConfiguracaoFinanceira.get().horizonte_recorrencia_dias`), idempotente via `get_or_create`-like check na `UniqueConstraint(recorrente, data_vencimento)`; (2) `alertar_vencimentos` notifica só telefones internos da equipe cadastrados em `financeiro.TelefoneAlertaFinanceiro` (nunca o fornecedor) sobre `ContaPagar` `pendente`/`parcial` vencendo em até `alerta_antecedencia_dias` dias **ou** já em atraso (mesmo filtro cobre os dois casos — `data_vencimento <= hoje + antecedencia` inclui datas passadas), repetindo a cada `alerta_repeticao_dias`, controlado por `AlertaFinanceiroEnviado` (1 registro por envio, FK direta pra `ContaPagar` — mais simples que `AlertaEventoEnviado`/`AlertaEstoqueEnviado` porque aqui só existe um tipo de alerta, não dois/dois). Texto da mensagem é fixo no código (mesma escolha consciente de escopo de "Alertas de Evento"). `notificacoes.HistoricoMensagem.tipo` ganhou o choice `alerta_vencimento`
- **Signals de Venda → Ledger** (`financeiro/signals.py`, registrado em `FinanceiroConfig.ready()`, mesmo padrão de `estoque/signals.py` e `pdv/signals.py`: `post_save`/`post_delete` com sender como string, sempre em try/except, idempotente via `.exists()` antes de gravar) — 3 gatilhos: (1) `pdv.PedidoPDV` ao entrar em `'confirmado'` (mesmo gatilho do débito de estoque) → `MovimentoFinanceiro` `entrada` direto na `conta_padrao_vendas`; ao entrar em `'cancelado'` **depois** de já ter gerado esse movimento → estorno automático (`origem_tipo='manual'`, `origem_id=f'estorno-pdv-{id}'`, nunca duplica graças ao mesmo padrão de idempotência); (2) `ifood.PedidoIFood` ao entrar em `'CONCLUDED'` (nunca em cada evento de polling — só nessa transição terminal) → `entrada` direto se `ConfiguracaoFinanceira.recebimento_ifood == 'no_ato'`, ou cria `ContaReceber` (`canal='ifood'`, `data_vencimento = data_pedido + dias_repasse_ifood`) se `'repasse'`; ao entrar em `'CANCELLED'` → estorna o movimento (modo `no_ato`) ou cancela a `ContaReceber` ainda não recebida (modo `repasse`, só se `valor_recebido == 0`); (3) `eventos.PagamentoEvento` — `post_save` com `status='pago'` → `entrada` direto (mesma regra dos outros dois); `post_delete` (fluxo existente `remover_pagamento`, e também dispara em cascade-delete de `Evento`) → estorno automático (`origem_tipo='manual'`, `origem_id=f'estorno-evento-pagamento-{id}'`), **nunca** apaga o movimento original. Todos os 3 verificam a existência do movimento/estorno antes de gravar — essencial porque `post_save` dispara em **todo** `.save()`, não só na transição de status
- **`financeiro.SaldoConferido`** (Fase 6) — conferência de saldo (usuário digita o saldo informado pelo app do banco, o sistema calcula a diferença contra o ledger). `saldo_calculado` é sempre o snapshot de `ContaBancaria.saldo_atual` **no momento do POST** (`SaldoConferidoViewSet.perform_create()` — nunca vem do payload, é `read_only` no serializer) — nunca recalculado depois, mesmo que o saldo real da conta mude com o tempo. `diferenca` (`saldo_informado - saldo_calculado`) é property, não campo. Sem `PATCH`/`DELETE` (`http_method_names = ['get', 'post', ...]`) — uma nova conferência é sempre um registro novo, o histórico completo fica no banco, a UI mostra só a mais recente por conta (`ordering = ['-data', '-criado_em']`). `POST /financeiro/conferencias/` exige login
- **`POST /financeiro/movimentos/manual/`** (Fase 6, action em `MovimentoFinanceiroViewSet`, exige login) — único jeito de criar um `MovimentoFinanceiro` fora dos signals automáticos e das baixas de conta: lançamento avulso (ex.: saldo inicial de uma conta nova) ou estorno manual de qualquer situação não coberta pelos estornos automáticos dos signals. Sempre `origem_tipo='manual'` (fora da `UniqueConstraint` condicional, permite múltiplos lançamentos livremente) — chama `MovimentoFinanceiro.registrar()` como qualquer outro caminho de escrita, nunca `.objects.create()`. Audita `movimento_manual`
- **`GET /financeiro/fluxo-caixa/?dias=N`** (Fase 6, `FluxoCaixaView`, `AllowAny`, `N` limitado a 1-90, default 14) — agregador sem model próprio: por dia, entre hoje e hoje+N-1, `entrada_realizada`/`saida_realizada` somam `MovimentoFinanceiro` com aquele `data_movimento` (bate exatamente com o ledger); `entrada_projetada`/`saida_projetada` somam o saldo restante (`valor - valor_recebido`/`valor - valor_pago`) de `ContaReceber`/`ContaPagar` `pendente`/`parcial` com aquele `data_vencimento` — já inclui `ContaPagar` de origem `recorrente` e `nota_fiscal` automaticamente, é a mesma query genérica por status, sem tratamento especial por origem. Resposta também traz `saldos_por_conta` (na chave `contas`) com a última `SaldoConferido` de cada `ContaBancaria` ativa (`None` se nunca conferida). **Não inclui o saldo dinâmico de Evento** (diferente de `contas-receber/resumo/`) — decisão de escopo desta sessão, para não estender o agregador além do que o texto da Fase 6 do `FINANCEIRO.md` pedia; revisitar se o usuário quiser ver eventos no fluxo de caixa também
- **Módulo de Backup** (app `manutencao/`, spec completa em `backup.md`, fases 1-5 concluídas e envio externo configurado em 30/jul/2026) — cron diário `fazer_backup` (03:00) faz `pg_dump -Fc` do Postgres inteiro + `tarfile` de `MEDIA_ROOT`, salva local em `ConfiguracaoBackup.pasta_backup_db`/`pasta_backup_media` (padrão `/var/backups/arretado/{db,media}`), rotaciona local (`retencao_local_dias`, padrão 14) e envia pro Backblaze B2 via `rclone` (remote `backup-remoto`, bucket `arretado-backups`), rotacionando remoto (`retencao_remota_dias`, padrão 90). Cron `verificar_backup` (08:00) checa idade/tamanho do backup mais recente e alerta `TelefoneAlertaBackup` via WhatsApp se algo estiver errado — **sem dedup de alerta** (repete todo dia enquanto quebrado, diferente de `AlertaEventoEnviado`/`AlertaEstoqueEnviado`/`AlertaFinanceiroEnviado`, decisão consciente porque backup quebrado é o único problema que fica invisível até o dia em que se precisa dele). `fazer_backup` nunca chama `notificar()` — só `verificar_backup` alerta, fonte única de verdade sobre "o backup está ok". O `rclone.conf` (`/root/.config/rclone/rclone.conf`, fora do repo) está **sem senha de criptografia** de propósito — o arquivo já é `600 root:root`, mesmo nível de proteção do crontab que precisaria da senha de qualquer forma; ver `backup.md` se um dia precisar reconfigurar. **Restauração é sempre manual, nunca um management command** (decisão consciente, ver "O Que NÃO Fazer") — `pg_restore -h localhost -p 5432 -U arretado_user -d arretado_db --clean --if-exists --no-owner /var/backups/arretado/db/crm_db_TIMESTAMP.dump` (com `arretado.service` parado antes e religado depois) para o banco, `tar xzf /var/backups/arretado/media/media_TIMESTAMP.tar.gz -C /var/www/crm_arretado/ --overwrite` pra mídia; se o backup local também tiver sumido, baixar primeiro do B2 com `rclone copy backup-remoto:arretado-backups/{db,media}/ /var/backups/arretado/{db,media}/`
- **Multi-Empresa** (app `empresas/`, spec completa em `MULTIEMPRESA.md`, 6 fases — Fases 0 e 1 implementadas até aqui) — `empresas.Empresa` é multi-tenant **por linha** (FK `empresa`, mesmo banco), nunca `django-tenants`/schema separado. **Exatamente uma** `Empresa` tem `padrao=True` (`UniqueConstraint` condicional `Q(padrao=True)`), resolvida sempre via `Empresa.get_padrao()` — nunca por id fixo em código. Os 12 campos `cor_*` são hex opcionais (`blank=True`) — vazio significa "usa o valor default do token CSS", então a empresa matriz nasce (via data migration, `nome='Empresa Principal'`) sem nenhuma cor cadastrada e a UI continua idêntica à atual; o usuário renomeia/preenche depois pelo painel (`/empresas`, menu Administração, `role=admin`). `EmpresaViewSet` não tem `DELETE` nem `PUT` (`http_method_names` restrito) — inativar é sempre `ativo=False`, mesma filosofia de `DespesaRecorrente`/`ConfiguracaoIFood`. `create`/`update` exigem login e auditam via `AuditoriaCreateMixin`/`AuditoriaUpdateMixin` (genéricos, `registro_criado`/`registro_atualizado`); `list`/`retrieve`/`branding-login` continuam `AllowAny`. O serializer bloqueia (400) tanto criar uma 2ª empresa com `padrao=True` (a `UniqueConstraint` condicional já é detectada automaticamente pelo DRF como `UniqueValidator`, respeitando a condição) quanto desmarcar `padrao` da única empresa que o tem, sem promover outra na mesma requisição — hoje **não existe** endpoint de troca atômica de empresa padrão (fora de escopo da Fase 0; o campo `padrao` nem aparece editável no formulário do frontend, só como badge "Padrão" somente-leitura). `logo_horizontal`/`logo_negativo`/`logo_simbolo`/`timbre` reaproveitam a infra `/media/` já existente — `timbre` é campo **preparatório**, nenhum gerador de PDF lê dele nesta entrega.
- **Multi-Empresa — Fase 1 (iFood)** — `ifood.ConfiguracaoIFood` ganhou FK `empresa` (`PROTECT`) — uma linha por empresa/merchant (a config já não era singleton de verdade antes disso, então múltiplas linhas simultâneas já eram suportadas pela arquitetura; agora cada uma pertence a uma `Empresa`). `ifood.PedidoIFood` ganhou FK `empresa` (`PROTECT`) **denormalizada** — `polling_worker.py::_criar_pedido()` grava `empresa=config.empresa` no momento da criação, snapshot que nunca muda depois (mesma filosofia de `ItemOrcamento`/`SnapshotPrecos`). `pedidos.PedidoUnificado` ganhou FK `empresa` (`PROTECT`, `null=True` por decisão de escopo — ver `MULTIEMPRESA.md`): o signal do iFood (`pedidos/models.py::sincronizar_pedido_ifood`) propaga `pedido_ifood.empresa`; os signals de PDV (`pdv/signals.py`) e Eventos (`eventos/models.py::sincronizar_evento`) — mono-empresa por escopo desta entrega — gravam sempre `Empresa.get_padrao()`, resolvida em runtime, nunca id fixo. **Nenhum ponto resolve a credencial de uma ação de pedido (confirmar/cancelar/despachar/pronto-retirada/negociação/motivos-cancelamento) via `ConfiguracaoIFood.objects.first()`** — `ifood/views.py::PedidoIFoodViewSet._get_client(pedido)` sempre filtra `ConfiguracaoIFood.objects.filter(empresa=pedido.empresa)`, essencial pra ter dois merchants (matriz + MANGAIO) operando no mesmo worker sem misturar credencial. `GET /ifood/config/status/` e `GET /ifood/pedidos/estatisticas/` aceitam `?empresa=<id>` (default: `Empresa.get_padrao()` via helper `ifood/views.py::_resolver_config_por_empresa()` — nunca `.objects.first()`); `GET /ifood/pedidos/` aceita `?empresa=<id>` sem default (sem o parâmetro, lista de todas as empresas, com `empresa_nome` no serializer pra badge no frontend). `IFood.jsx` só mostra o seletor de empresa no topo quando existe mais de uma `Empresa` ativa — hoje (12/ago/2026) a MANGAIO ainda não foi cadastrada, então o seletor fica invisível e o comportamento é idêntico ao anterior à fase. Nada em Financeiro/Dashboard/Usuários/temas foi alterado nesta fase (Fases 2-5, ainda não iniciadas) — Estoque também não foi tocado, o fuzzy match sem correspondência da MANGAIO logando warning é o comportamento correto e esperado, não um bug.
- **Multi-Empresa — Fase 2 (Usuários × Empresas + empresa ativa)** — `usuarios.Usuario` ganhou `empresas` (M2M →
  `empresas.Empresa`, `blank=True` — nunca choice com nome de empresa), `empresa_ativa` (FK `SET_NULL`, `null=True`)
  e `preferencia_tema` (choices `empresa`/`neutro_claro`/`neutro_escuro`, default `'empresa'` — a aplicação real do
  tema é Fase 3, aqui só o campo/persistência existem). Migration de dados (`usuarios/migrations/0004_...`) vinculou
  todos os usuários existentes à empresa `padrao=True` e setou `empresa_ativa` pra ela — comportamento pós-deploy
  idêntico ao anterior à fase. **Login nunca é bloqueado por falta de vínculo**: `usuarios/views.py::_empresas_efetivas()`
  resolve o conjunto de empresas que o usuário enxerga — `role=admin` sempre vê **todas** as `Empresa.objects.filter(ativo=True)`
  (mesma exceção de `definir-empresa-ativa/` abaixo); demais roles veem só `usuario.empresas.filter(ativo=True)`, e
  sem nenhuma vinculada (usuário legado, ou cuja única empresa virou `ativo=False`) cai na empresa padrão
  (`Empresa.get_padrao()`) — nunca persistido automaticamente, só usado pra montar a resposta. `_empresa_ativa_efetiva()`
  usa `usuario.empresa_ativa` se ainda estiver no conjunto efetivo, senão cai no primeiro item. `POST /usuarios/login/`
  devolve `empresas`/`empresa_ativa`/`preferencia_tema` **sempre a versão efetiva** (com fallback aplicado), nunca o
  estado bruto do banco — `data.update(_payload_empresas(usuario))` sobrescreve de propósito os campos homônimos que
  `UsuarioSerializer` já monta a partir do banco. `POST /usuarios/definir-empresa-ativa/` (`IsAuthenticated`, body
  `{"empresa": id}`) valida que a empresa está entre as vinculadas do usuário — **exceto `role=admin`, que pode ativar
  qualquer empresa `ativo=True`** (decisão fechada do spec) — grava `Usuario.empresa_ativa` e audita
  `ACAO_EMPRESA_ALTERNADA` (`detalhes={'de':..., 'para':...}`, afeta o que o usuário enxerga de dados financeiros nas
  próximas fases). `POST /usuarios/preferencia-tema/` (`IsAuthenticated`, body `{"tema": ...}`) só grava o campo —
  **não audita** (cosmético, mesma decisão do spec). `UsuarioSerializer` expõe `empresas`/`empresa_ativa` (nested,
  read-only, via `empresas.EmpresaResumoSerializer` — resumo com `id`+branding, reusado também no payload de login)
  e aceita escrita por `empresas_ids` (`PrimaryKeyRelatedField(many=True, source='empresas')`) no create/update — o
  `create()`/`update()` do serializer faz `.set()` manual no M2M porque o serializer já sobrescreve os dois métodos
  (não usa o `create()`/`update()` genérico do `ModelSerializer`, que trataria M2M sozinho). `empresa_ativa` e
  `preferencia_tema` são **sempre read-only** no `UsuarioSerializer` geral — só mudam via os dois endpoints dedicados
  acima, nunca por `PATCH /usuarios/{id}/` direto (nem por um admin editando outro usuário). Frontend: `useAuth.jsx`
  expõe `empresas`/`empresaAtiva` (derivados do `user` já cacheado) e `trocarEmpresa(id)`/`definirPreferenciaTema(tema)`
  (chamam a API e depois espelham a resposta via `authApi.atualizarCache()` — **não** é uma nova forma de persistir
  em `localStorage`, é só manter coerente o mesmo objeto `auth_user` que a exceção já documentada do projeto usa pra
  sobreviver a um F5). `Login.jsx` navega pra `/escolher-empresa` quando o login devolve 2+ `empresas` (senão vai
  direto pra `/`); `EscolherEmpresa.jsx` é rota própria fora do `AppLayout` (sem sidebar). `EmpresaSwitcher.jsx` (pill
  no rodapé da Sidebar, acima do `userPill`) só renderiza com 2+ empresas no contexto — **o spec original previa o
  switcher "no header"**, mas este projeto não tem header/topbar global (só `Sidebar.jsx` + um `Topbar.jsx` por
  página) — decisão desta sessão: colocar na Sidebar, único chrome realmente compartilhado por todo o app.
  `Usuarios.jsx` ganhou checkbox de vínculo de empresa no form de criação e no painel de detalhe do usuário
  selecionado (toggle, mesmo padrão das permissões) — só aparece com 2+ empresas ativas cadastradas (mesmo critério
  usado em `IFood.jsx` Fase 1). **Fora desta fase:** aplicação de tema de fato (Fase 3), Financeiro/Dashboard
  filtrados por empresa (Fases 4-5) — `preferencia_tema` já existe no banco mas nenhuma tela lê/aplica o valor ainda.
- **Versão do Sistema** (`config/versao.py`, `config/views.py::VersaoView`) — a versão da aplicação é **sempre derivada do Git** (`git describe --tags --always --dirty`, `subprocess` puro), nunca mantida à mão em arquivo/settings. `obter_versao()` roda uma vez por worker do Gunicorn (`functools.lru_cache`) e não recalcula até o próximo restart. `GET /api/v1/versao/` (`AllowAny`, sem auditoria — é leitura pública, mesmo espírito de `branding-login/`) devolve `{versao, commit, commit_data, branch}`; `Sidebar.jsx` mostra no rodapé (substituiu o texto fixo `"CRM v1.0"`), com commit/data no `title` (hover). Cada release recebe uma **tag anotada** `vX.Y.Z` (`git tag -a vX.Y.Z -m "..."`, depois `git push origin vX.Y.Z` — tags não sobem com `git push` sem `--tags`/tag explícita) **e** uma entrada nova no `CHANGELOG.md` (formato Keep a Changelog) — os dois sempre juntos, no mesmo commit/momento do deploy. Baseline: `v1.0.0` tageada no commit que já estava em produção antes deste sistema existir (11/ago/2026). **Pegadinha de infra encontrada nesta feature:** o Gunicorn roda como `www-data` (`User=www-data` em `arretado.service`) mas o repositório é dono por `root` — o Git bloqueia qualquer comando (`detected dubious ownership in repository`) quando o usuário do processo difere do dono do diretório, desde o Git 2.35.2. Corrigido com `git config --system --add safe.directory /var/www/crm_arretado` (grava em `/etc/gitconfig`, libera pra todos os usuários da VPS — já aplicado em produção, não precisa recriar). Sem isso, `obter_versao()` cai silenciosamente no fallback `'desconhecida'` (nunca lança exceção — `_git()` engole qualquer erro do `subprocess`), então o sintoma é só a versão aparecer errada, sem erro nenhum nos logs

### Frontend
- **Sem `localStorage`** — estado React + context de autenticação *(exceção: `authApi` usa localStorage para sessão — refatorar para cookie/JWT no futuro)*
- **CSS Modules** — cada página tem seu `.module.css`
- **Variáveis CSS do design system** (`src/index.css`, nomes reais — corrigido nesta sessão, a lista
  anterior citava nomes conceituais que nunca existiram no CSS, ex. `--fundo`/`--muted`/`--hover`):
  - `--caramelo`/`--caramelo-light`/`--caramelo-pale` → cor primária da marca (+ `--caramelo-rgb` pra
    opacidade via `rgba(var(--caramelo-rgb), X)`, `--caramelo-texto` → cor do texto sobre botão primário)
  - `--bg`/`--bg-alt` → background da página · `--surface`/`--surface-raised`/`--surface-hover` → cards/tabelas
  - `--border`/`--border-strong`/`--border-accent` → bordas
  - `--texto`/`--texto-sec`/`--texto-muted`/`--texto-faint` → hierarquia de texto
  - `--verde` → indicadores positivos · `--danger`/`--warning` → estado (+ `--verde-rgb`/`--danger-rgb`)
  - **Multi-Empresa Fase 3** (temas, ver MULTIEMPRESA.md) acrescentou, sem alterar nenhum valor
    existente: trio de status compartilhado `--status-{ok,alerta,critico}-{bg,fg}` (substituiu hex cru
    repetido em Estoque/FichasTecnicas/Financeiro/CentralPrecos/Configuracoes), badges de canal
    `--canal-{ifood,pdv,eventos}-{bg,fg}` (Dashboard), badges de marca externa `--badge-{ifood,anotaai}-{bg,fg}`
    e `--whatsapp`/`--whatsapp-rgb`/`--whatsapp-hover` (**nunca** seguem tema de empresa nem tema neutro —
    identidade de terceiro, sempre fixos), tokens de sidebar `--sidebar-{bg,border,texto,texto-mut,ativo,ativo-bg}`
    (sidebar tem esquema de cor independente do conteúdo — necessário pra uma empresa poder ter sidebar
    escura sobre conteúdo claro, como o mockup da MANGAIO) e `--font-display`/`--font-body`
  - **Nunca perseguir 100% dos hex hardcoded que ainda restam** nos CSS Modules (ex. a família `#EF4444`/
    `#3B82F6`/`#F59E0B`/`#10B981`/`#6B7280` de status de ação do PDV, semáforo neutro do CentralPrecos,
    badges verde/vermelho de texto do Configuracoes) — decisão consciente da Fase 3: só converter
    duplicatas exatas de token já existente e os trios semânticos mais repetidos; o resto é cor
    decorativa local de baixo risco, sem tema de empresa nem alto ganho de DRY, revisitar só se algo
    ficar de fato ilegível no tema escuro
- **Sistema de Temas** (Multi-Empresa Fase 3, `src/temas.css` + `src/utils/tema.js` — ver MULTIEMPRESA.md)
  — três modos, persistidos em `Usuario.preferencia_tema` (nunca `localStorage`): **Empresa** (default)
  aplica as 12 cores de `empresaAtiva` como overrides inline via `aplicarCoresEmpresa()` (campo vazio ⇒
  `removeProperty` ⇒ cai no valor default do token, nunca só "pula" o campo — é o que garante reset
  correto ao trocar de empresa/tema/logout); **Claro**/**Escuro** (`neutro_claro`/`neutro_escuro`) aplicam
  `data-theme` na raiz e limpam qualquer override de cor de empresa — são paletas estáticas do produto
  (Inter, não Playfair/DM Sans), identidade Ortex, não de cliente, por isso vivem em `temas.css` e não no
  banco. `useAuth.jsx` reaplica o tema (+ `document.title` + favicon) num `useEffect` sempre que `user`
  muda; `Login.jsx` aplica o branding da empresa `padrao=True` incondicionalmente (tela pré-login não tem
  seletor). Seletor de tema: `SeletorTema.jsx`, rodapé da Sidebar (mesmo desvio "sem header global" já
  documentado no `EmpresaSwitcher` da Fase 2).
- **Tipografia:** tema de empresa → `'Playfair Display', serif` em títulos (`.serif`, via `--font-display`)
  · `'DM Sans', sans-serif` no corpo (via `--font-body`); temas neutros trocam os dois pra `'Inter', sans-serif`
- **Ícones:** Tabler Icons (`ti ti-*`)
- **`services.js`:** um objeto de API por canal — `clientesApi`, `ifoodApi`, `pdvApi`, `notificacoesApi`, `orcamentosApi`, `fichasApi`
- **Novo canal** = novo objeto no `services.js` seguindo o mesmo padrão
- **Busca de cliente CRM** (padrão usado em `Eventos.jsx` e `Orcamentos.jsx`): input com debounce 350ms → `clientesApi.list({ search })` → dropdown com seleção → chip com nome/telefone e botão X para limpar. Nunca usar `<select>` com todos os clientes pré-carregados.
- **Upload de arquivo/imagem via axios**: `api/client.js` fixa `headers: {'Content-Type': 'application/json'}` na instância do axios, e isso **não** é sobrescrito automaticamente quando o corpo é um `FormData` — sem correção, o navegador não define o boundary do multipart e o backend recebe a requisição sem o arquivo (`request.FILES` vazio). Sempre que enviar `FormData`, passar `{ headers: { 'Content-Type': undefined } }` na chamada (ver `orcamentosApi.adicionarImagens`, `pdvApi.updateFoto` e `eventosApi.adicionarPagamento` — este último condicional, só monta `FormData` quando há arquivo de comprovante anexado — em `services.js`) para o navegador definir o header correto.
- **Lightbox de imagem ampliada**: padrão usado em `Orcamentos.jsx`/`Eventos.jsx` para a galeria de `imagens_inspiracao` — clique na thumbnail abre um overlay `position: fixed` (z-index 400, acima do Modal que é 200) com a imagem em `object-fit: contain`, fecha no clique fora ou no X. Reaproveitar esse padrão para qualquer nova galeria de imagens.
- **Confirmação antes de enviar WhatsApp**: todo `handleEnviar*` que dispara `enviarWhatsApp` (orçamento e contrato — envio inicial ou reenvio, em `Orcamentos.jsx` e `Eventos.jsx`) abre um `window.confirm()` com nome/telefone do destinatário antes de chamar a API, pra evitar disparo acidental. Reaproveitar esse padrão em qualquer novo envio de WhatsApp disparado por clique direto de botão.
- **Modal de emitir contrato não fecha sozinho após gerar**: `onGerado` (callback passado a `ModalEmitirContrato`/`ModalEmitirContratoEvento`) deve só recarregar a listagem/detalhe — nunca fechar o modal. O modal só fecha pelo botão "Fechar" explícito do usuário, depois que ele já viu o PDF e/ou enviou por WhatsApp na mesma tela (bug real corrigido em `Eventos.jsx`: o `onGerado` chamava `setEmitirEvento(null)` e fechava o modal antes do usuário conseguir ver o contrato recém-criado).
- **Gráfico divergente (entrada acima/saída abaixo de uma linha base)**: padrão introduzido em `Financeiro.jsx` (aba Fluxo de Caixa) para visualizar `entrada_realizada`/`entrada_projetada`/`saida_realizada`/`saida_projetada` por dia — reaproveita a mesma estrutura de barra empilhada com `title` nativo como tooltip já usada no gráfico de 7 dias do `Dashboard.jsx` (`stackedChart`/`stackedCol`/`stackedBar`), só que espelhada (entrada cresce para cima a partir de uma linha base, saída para baixo) e com "realizado" (cor sólida) e "projetado" (mesma cor com opacity reduzida, nunca uma cor nova) empilhados no mesmo lado — identidade por cor, realizado×projetado por opacidade, nunca o contrário. Reaproveitar essa estrutura para qualquer novo gráfico financeiro/fluxo de caixa em vez de introduzir uma lib de gráficos nova.
- **Teste manual de UI que grava no banco de produção**: este projeto não tem banco de dev/staging separado — o Vite (`npm run dev`) sempre fala com o Django/Postgres real via proxy (`vite.config.js` → `localhost:8000`). Ao testar fluxos de criação manualmente (curl ou navegador), usar prefixo `"TESTE "` nos nomes/descrições criados e **sempre limpar depois** (via Django shell quando o endpoint não tem `DELETE`, como `ContaBancaria`/`ContaPagar`/`ContaReceber`/`DespesaRecorrente`/`SaldoConferido`) — nunca deixar dado de teste órfão em produção. Se testar um app que nunca rodou em produção antes (ex.: Financeiro fases 0-6 até 25/jul/2026), o `arretado.service` pode estar rodando havia dias sem esse código carregado — sempre confirmar com o usuário antes de `migrate` + `systemctl restart arretado`, mesmo que não seja um `npm run build`.

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
| Produtos Mais Vendidos | Ranking cross-canal (iFood+PDV+Eventos) por quantidade/valor, período configurável, agrupado por nome de item normalizado — `ProdutosMaisVendidosView`, aba nova em `Relatorios.jsx` | ✅ Concluída (só JSON, sem export Excel/PDF) |
| Contrato | Emissão de Contrato de Aquisição de Produtos a partir de Orçamento aprovado (PDF com cláusulas configuráveis + envio por WhatsApp) + reenvio por WhatsApp direto da listagem/detalhe de Orçamentos e Eventos (reaproveita o mesmo endpoint `enviar-whatsapp/`) | ✅ Concluída (ver `Contrato.md`) |
| Imagens de Inspiração | Galeria de imagens de referência anexada ao Orçamento OU ao Evento (upload múltiplo, lightbox, uso interno) — Evento pode adicionar/remover a qualquer momento, com ou sem orçamento de origem (05/set/2026) | ✅ Concluída |
| Pagamentos Parciais de Evento | `eventos.PagamentoEvento` (parcelas), `Evento.sinal_pago` derivado, redesign do modal de detalhe do Evento (stepper + abas), edição de Orçamento antes da conversão | ✅ Concluída |
| Dashboard Multi-Canal | App `dashboard/` (só leitura) — vendas do dia e histórico recente consolidado de iFood/PDV/Eventos (+ espaço reservado pra Anota AI), gráfico 7 dias, a receber, fila operacional, próximos eventos, ticket médio | ✅ Concluída |
| Autenticação Real + Auditoria | Token real (`usuarios/authentication.py`) + app `auditoria/` cobrindo os 6 itens da lista priorizada: usuários (login/CRUD/permissões), pagamentos de evento, contrato, Central de Preços, configurações singleton (`ConfiguracaoContrato`/`ConfiguracaoEntrega`/`ConfiguracaoWhatsApp` — esta última também exige login no GET, já que expõe credencial Z-API) e exclusões em geral (`AuditoriaDestroyMixin` genérico, aplicado em `Cliente`/`Tag`/`Endereco`/`Produto`/`CategoriaProduto`/`TaxaEntregaBairro`/`PedidoPDV`/`Evento`/`Orcamento`/`LocalEvento`/`MateriaPrima`/`FichaTecnica` e os respectivos `remover-item`; `ConfiguracaoIFood` teve o DELETE bloqueado de vez, não só auditado) — tela restrita a `role=admin` | ✅ Concluída (lista completa) |
| Auditoria de Criação/Edição/Status + Presença + Histórico no Modal | Extensão da auditoria de Orçamento/Evento: criação, edição (PATCH/PUT), mudança de status e adicionar/editar item agora também são auditados (`AuditoriaCreateMixin`/`AuditoriaUpdateMixin`/`AuditoriaStatusMixin`), exigindo login nessas ações (antes eram `AllowAny`). Presença via heartbeat REST (`auditoria.PresencaEdicao`, `PresencaAtiva.jsx`, polling a cada 15s — não WebSocket) mostrando quem mais está vendo o registro agora. Aba/seção "Histórico" dentro do próprio modal de detalhe (`historico/` em `OrcamentoViewSet`/`EventoViewSet`, `IsAuthenticated` — diferente da tela de Auditoria geral, que é restrita a admin) | ✅ Concluída |
| Alertas de Evento (pagamento pendente / entrega próxima) | Cron diário (`alertar_eventos`) alerta telefones internos da equipe via WhatsApp sobre Evento com saldo pendente perto da data (configurável) e sobre entrega se aproximando (configurável, repete a cada X dias) — `ConfiguracaoAlertaEvento`/`TelefoneAlertaEvento`/`AlertaEventoEnviado`, seção "Alertas de Evento" em Configurações, card "Alertas" no Dashboard | ✅ Concluída |
| Estoque — Fases 1-5 (modelos base, entrada manual/ajuste, produção, débito automático na venda, alertas) | App `estoque/` — `MovimentoEstoque` (ledger), `Producao`, campos novos em `MateriaPrima`/`Produto`, débito automático via signals (PDV/iFood/Eventos), alertas de estoque baixo (`ConfiguracaoEstoque`/`TelefoneAlertaEstoque`/`AlertaEstoqueEnviado`), tela `Estoque.jsx` (4 abas), card "Estoque" no Dashboard | ✅ Concluída (fases 1-5) |
| Estoque — Fases 6-8 (importação de nota fiscal: XML/PDF/IA) | Cascata de extração (XML da NF-e → texto de PDF → IA multimodal), staging (`ImportacaoNotaFiscal`/`ItemNotaImportada`), tela de revisão, fuzzy match, filtros de período/tipo na aba Movimentações | ✅ Concluída |
| Resumo de Cozinha (Evento) | PDF operacional (A4 página cheia, ReportLab Platypus, sem timbre) com itens do Evento agrupados por categoria, pra a equipe de cozinha montar a produção — sem preços. Botão em `Eventos.jsx` (card de detalhe + linha da lista) | ✅ Concluída (só A4 página cheia — meia-folha/térmica fora de escopo por ora) |
| Módulo Financeiro — Fases 0-7 (bug fix pré-requisito, models base, `MovimentoFinanceiro.registrar()`, `ContaPagar` + baixa/cancelar/resumo, `DespesaRecorrente` + crons, `ContaReceber` + signals PDV/iFood/PagamentoEvento, integração Estoque → nota fiscal vira `ContaPagar`, fluxo de caixa + conferência de saldo + lançamento manual, frontend `Financeiro.jsx`) | Spec completa em `FINANCEIRO.md` (9 fases, 0-8). App `financeiro/`: `CategoriaFinanceira`/`ContaBancaria`/`Fornecedor`/`ConfiguracaoFinanceira`/`TelefoneAlertaFinanceiro`, ledger `MovimentoFinanceiro` (mesmo contrato de `MovimentoEstoque`) + action `movimentos/manual/`, `ContaPagar`/`ContaReceber` (obrigação projetada, `valor_pago`/`valor_recebido`/`status` derivados), `DespesaRecorrente` + `AlertaFinanceiroEnviado` + crons `gerar_contas_recorrentes`/`alertar_vencimentos`, signals de venda (PDV/iFood/PagamentoEvento) batendo automaticamente no ledger com estorno em cancelamento, `estoque.ImportacaoNotaFiscal.fornecedor_cnpj` + geração automática de `ContaPagar` na confirmação da nota, `SaldoConferido` (conferências/) + `fluxo-caixa/` (agregador realizado x projetado + saldos por conta) + `Financeiro.jsx` (5 abas, `financeiroApi` em `services.js`, rota `/financeiro` + item de menu) | 🔄 Em andamento (fases 0-7 de 8 — falta só a Fase 8, testes finais + revisão do CLAUDE.md canônico) |
| Sistema de Backup (Banco + Mídia) | App `manutencao/` (spec completa em `backup.md`) — `ConfiguracaoBackup`/`TelefoneAlertaBackup`, cron `fazer_backup` (pg_dump + tarfile de media/ + rotação local + envio pro Backblaze B2 via rclone + rotação remota) e `verificar_backup` (alerta WhatsApp sem dedup se backup ausente/velho/corrompido) | ✅ Concluída (fases 1-5 — envio externo configurado com Backblaze B2 em 30/jul/2026; restauração é sempre manual, ver Padrões Obrigatórios) |
| Multi-Empresa + Temas — Fases 0-5 de 6 (app `empresas/` + model `Empresa`; iFood multi-empresa; Usuários × Empresas + empresa ativa; sistema de temas; Financeiro por empresa; Dashboard/Relatórios por empresa) | Spec completa em `MULTIEMPRESA.md` (6 fases, 0-5). Fase 0: app `empresas/`: model `Empresa` (multi-tenant por linha, branding em 12 campos de cor + 3 logos + timbre preparatório, `padrao` único via constraint condicional), `EmpresaViewSet` (CRUD sem DELETE/PUT, auditado) + `branding-login/`, tela `Empresas.jsx` (rota `/empresas`, menu Administração, `role=admin`). Fase 1: FK `empresa` (`PROTECT`) em `ifood.ConfiguracaoIFood`/`ifood.PedidoIFood` e `pedidos.PedidoUnificado` (`null=True`); credencial de ação de pedido sempre resolvida pela empresa do pedido (nunca `.objects.first()`); `IFood.jsx` com seletor de empresa (só visível com 2+ empresas ativas). Fase 2: `usuarios.Usuario` ganhou `empresas` (M2M) + `empresa_ativa` (FK) + `preferencia_tema`; login devolve empresas/empresa_ativa/tema "efetivos" (fallback pra empresa padrão, nunca bloqueia); `POST /usuarios/definir-empresa-ativa/` (audita `empresa_alternada`, admin pode ativar qualquer empresa) + `POST /usuarios/preferencia-tema/` (não audita); `useAuth.jsx` (`trocarEmpresa`/`definirPreferenciaTema`), `EscolherEmpresa.jsx` (rota pós-login com 2+ empresas), `EmpresaSwitcher.jsx` (pill na Sidebar — projeto não tem header global), checkbox de vínculo em `Usuarios.jsx`. Fase 3 (100% frontend, sem migration): tokens novos em `index.css` (rgb companheiros, trio de status compartilhado, badges de canal/marca externa, tokens de sidebar, `--font-display`/`--font-body`) + conversão mecânica de ~150 ocorrências de hex/rgb cru pra `var()` em 20 CSS Modules + `ui.module.css` (auditoria feita por agente, valores idênticos — zero mudança visual); `temas.css` (novo, paletas `neutro-claro`/`neutro-escuro`); `utils/tema.js` (`aplicarCoresEmpresa`/`aplicarModoNeutro`/`aplicarTema`); `useAuth.jsx` aplica o tema (+ título + favicon) num `useEffect`; `Login.jsx` consome `brandingLogin()` (órfão desde a Fase 0); `Sidebar.jsx` mostra logo/subtítulo dinâmicos da empresa ativa; `SeletorTema.jsx` novo (rodapé da Sidebar). Validado visualmente via Playwright headless (usuário de teste `TESTE Fase3 Temas`, criado e removido na mesma sessão) nos 3 modos, em Login/Dashboard/Financeiro/Estoque — matriz byte-idêntica confirmada, troca de tema instantânea sem reload. Fase 4 (Financeiro por empresa, ver "Financeiro por empresa" em Padrões Obrigatórios): FK `empresa` (`PROTECT`) em `ContaBancaria`/`ContaPagar`/`ContaReceber`/`DespesaRecorrente`; `ConfiguracaoFinanceira` deixou de ser singleton global (`OneToOneField` `empresa`, `get(empresa)`); `MovimentoFinanceiro` sem FK própria (property `empresa` via `conta`); signals de venda resolvem a config pela empresa certa (iFood por `pedido.empresa`, PDV/Eventos sempre a matriz); todos os ViewSets aceitam `?empresa=<id>`/`?empresa=todas`; `Financeiro.jsx` consome o contexto global (`useAuth().empresaAtiva`/`empresas`), badge + chip "Todas as empresas" nas abas de resumo. 76 testes de `financeiro` + suíte completa verde. Fase 5 (Dashboard/Relatórios por empresa, ver "Dashboard e Relatórios por empresa" em Padrões Obrigatórios): `dashboard/resumo/` e os dois endpoints de `relatorios/` aceitam `?empresa=<id>`/`?empresa=todas` via `_resolver_empresa()` (mesmo padrão duplicado em cada app, nunca importado entre apps); PDV/Eventos/Estoque (mono-empresa, sem FK própria) zeram/somem numa visão de empresa não-matriz e o dashboard ganha o card `repasse_ifood_a_receber` (soma de `ContaReceber` `canal='ifood'` pendente/parcial da empresa); `Empresa.modulos_ocultos` (JSONField novo, lista de slugs de rota) some com itens de menu que a empresa ativa não usa — `Sidebar.jsx` filtra por isso, `Empresas.jsx` ganhou a seção "Módulos visíveis no menu" pra editar; `Dashboard.jsx`/`Relatorios.jsx` consomem `useAuth().empresaAtiva`/`empresas` com o mesmo padrão de chip/segmented control já usado em Financeiro.jsx/aba "Por dia/mês". 11 testes novos (`dashboard/tests.py` + 2 classes em `relatorios/tests.py`) + suíte completa verde. **Deploy das Fases 4-5 concluído em 24/ago/2026** (commits `3bd1b3d`/`bc828a1`, tag `v1.5.0`) — `migrate`+`restart arretado arretado-polling`+`npm run build` real feitos e verificados em produção | 🔄 Em andamento (fases 0-5 de 6 implementadas e deployadas — falta só o cadastro real da MANGAIO pela tela `/empresas`, nenhuma fase de código pendente) |
| Brindes e Permutas — Fases 1-5 (completo) (campo `natureza` venda/brinde/permuta por item, zera `preco_total` sem faturar; guard financeiro + filtro no ranking; PDF com valor riscado; seletor no frontend; PDV avulso) | Spec completa em `BRINDES_PERMUTAS.md` (5 fases). Fase 1 (ver "Brindes e Permutas — Fases 1-5" em Padrões Obrigatórios): `natureza` novo em `eventos.ItemOrcamento`/`eventos.ItemEvento`/`pdv.ItemPedidoPDV`, `save()` dos três zera `preco_total` quando `natureza != 'venda'` (preserva `preco_unit` como referência de valor de tabela); `recalcular_totais()` dos três não precisou mudar (já soma sem filtro); `converter_em_evento` propaga `natureza`. Fase 2: guard `if pedido.total <= 0: return` em `financeiro/signals.py::_registrar_venda_pdv()` (+ guarda simétrica em `_registrar_pagamento_evento()`, defensiva); `relatorios.ProdutosMaisVendidosView._qs_pdv()`/`_qs_eventos()` ganharam `natureza='venda'` no filtro (iFood não tem o campo, nada a mudar lá). Fase 3: `pdf_orcamento.py`/`pdf_contrato.py` — nome do item ganha `" — Brinde"/" — Permuta"`, `preco_unit` riscado via `Paragraph`+`<strike>` (só na célula do item afetado); `pdf_resumo_cozinha.py` não muda (já não expõe preço). Fase 4: `SeletorNatureza`/`NaturezaBadge` novos em `components/ui/index.jsx`, integrados em `Orcamentos.jsx`/`Eventos.jsx`/`PDV.jsx` (preço trava quando não-venda, badge+riscado na lista) — **bug real encontrado e corrigido durante a validação manual via Playwright**: `OrcamentoCreateSerializer.create()`/`EventoCreateSerializer.create()` somavam a variável local `total` (ignorando `natureza`) em vez de `item.preco_total` no subtotal, só na criação com itens já no payload inicial (`adicionar_item`/`editar_item`/`converter_em_evento` já estavam corretos desde a Fase 1); `pdv.PedidoPDVCreateSerializer` já não tinha o bug. Fase 5 ("PDV Avulso"): confirmado sem código novo — `PedidoPDV.pagamento` já era opcional, sincronização com `PedidoUnificado` já funciona pra pedido de `total=0`, travado com 1 teste de regressão. Deploy das Fases 1-4 em produção em 24/ago/2026 (commits `661cd27`/`5ab6832`/`53f6f58`/`6484b5e`, sem tag). 21 testes novos ao todo (incluindo os 2 de regressão do bug do subtotal e o da Fase 5) + suíte completa (335) verde | ✅ Concluída (5 de 5 fases, todo o código já deployado em produção — Fase 5 não precisou de deploy próprio, sem mudança de runtime) |

---

## Pendências Ativas

1. **Anota AI (Fase 3-ext-B)** — criar app `anotaai/` seguindo o padrão de `pdv/`
2. **Fichas técnicas incompletas** — 3 ingredientes com custo zero na planilha original (`Cobertura cappucino`, `Folha decorativa`, `Castanha do Pará`, `Ameixa`) e `Brigadeiro Sensacional` sem quantidades
3. **PDV Hardware (roadmap):**
   - Curto prazo: impressora térmica TCP/IP (Django imprime via socket ESC/POS) + caixa registradora pelo mesmo cabo
   - Médio prazo: NFC-e (nota fiscal — SEFAZ-PI)
   - Longo prazo: TEF integrado
4. **Relatório de canal (`RelatorioIFoodView`, resumo + agrupado + export Excel/PDF) cobre só iFood** — expandir para PDV e Eventos/Orçamentos seguindo o mesmo padrão. (O ranking de produtos mais vendidos, `ProdutosMaisVendidosView`, já cobre os 3 canais desde 18/ago/2026 — pendência diferente, não confundir: ali falta só export Excel/PDF, aqui falta o relatório de canal inteiro pra PDV/Eventos)
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
# Versão do Sistema (ver Padrões Obrigatórios)
GET /api/v1/versao/    ← AllowAny · {versao, commit, commit_data, branch}, derivado de `git describe`

# Clientes
GET/POST             /api/v1/clientes/
GET/PUT/PATCH/DELETE /api/v1/clientes/{id}/        ← DELETE exige login · audita registro_excluido
GET                  /api/v1/clientes/{id}/historico/
GET/POST             /api/v1/tags/                 ← DELETE (/{id}/) exige login · audita registro_excluido

# iFood (multi-empresa desde a Fase 1 do MULTIEMPRESA.md — ver Padrões Obrigatórios)
GET  /api/v1/ifood/pedidos/                       ← aceita ?empresa=<id> (sem parâmetro: todas as empresas, com empresa_nome no payload)
GET  /api/v1/ifood/pedidos/estatisticas/          ← aceita ?empresa=<id> (default: Empresa.get_padrao())
POST /api/v1/ifood/pedidos/{id}/confirmar/
POST /api/v1/ifood/pedidos/{id}/vincular-cliente/
GET  /api/v1/ifood/config/status/                 ← aceita ?empresa=<id> (default: Empresa.get_padrao(), nunca .objects.first())
DELETE /api/v1/ifood/config/{id}/   ← sempre bloqueado (405) — não é singleton de verdade, nunca deletar (ver "O Que NÃO Fazer")

# PDV
GET/POST /api/v1/pdv/pedidos/                       ← DELETE (/{id}/) exige login · audita registro_excluido · itens do payload aceitam "natureza" (venda/brinde/permuta, default venda — ver Brindes e Permutas)
GET/POST /api/v1/pdv/produtos/                       ← DELETE (/{id}/) exige login · audita (ProtectedError → 400 se usado em kit)
GET/POST /api/v1/pdv/categorias/                     ← DELETE (/{id}/) exige login · audita registro_excluido
POST     /api/v1/pdv/pedidos/{id}/confirmar/
POST     /api/v1/pdv/pedidos/{id}/concluir/
POST     /api/v1/pdv/pedidos/{id}/itens/                              ← aceita "natureza" (idem acima)
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
POST          /api/v1/eventos/orcamentos/{id}/itens/                    ← exige login · aceita "natureza" (venda/brinde/permuta, default venda — ver Brindes e Permutas) · audita item_adicionado
PATCH         /api/v1/eventos/orcamentos/{id}/itens/{item_id}/editar/   ← exige login · idem "natureza" · só com status rascunho/enviado · audita registro_atualizado
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
POST                  /api/v1/eventos/{id}/itens/                       ← exige login · aceita "natureza" (venda/brinde/permuta, default venda — ver Brindes e Permutas) · audita item_adicionado
POST                  /api/v1/eventos/{id}/confirmar/                    ← exige login · audita status_alterado
POST                  /api/v1/eventos/{id}/iniciar-producao/             ← exige login · audita status_alterado
POST                  /api/v1/eventos/{id}/marcar-pronto/                ← exige login · audita status_alterado
POST                  /api/v1/eventos/{id}/entregar/                     ← exige login · audita status_alterado
POST                  /api/v1/eventos/{id}/cancelar/                     ← exige login · audita status_alterado
POST                  /api/v1/eventos/{id}/pagamentos/                  ← exige login (IsAuthenticated) · cria PagamentoEvento + recalcula sinal_pago (multipart opcional, campo "comprovante") + audita em auditoria.LogAuditoria
DELETE                /api/v1/eventos/{id}/pagamentos/{pagamento_id}/remover/ ← exige login (IsAuthenticated) · audita em auditoria.LogAuditoria
POST                  /api/v1/eventos/{id}/imagens/                       ← multipart, campo "imagens" (um ou mais arquivos) · AllowAny · qualquer status · vai pro Orçamento de origem se houver, senão direto pro Evento
DELETE                /api/v1/eventos/{id}/imagens/{imagem_id}/remover/   ← exige login · audita registro_excluido
GET                   /api/v1/eventos/{id}/historico/                    ← exige login · trilha de auditoria deste evento (não confundir com clientes/{id}/historico/, que é histórico de pedidos)
GET                   /api/v1/eventos/{id}/resumo-cozinha/               ← AllowAny · PDF operacional (itens agrupados por categoria, sem preço) · ver "Resumo de Cozinha"
GET                   /api/v1/eventos/agenda/

# Notificações WhatsApp
GET  /api/v1/notificacoes/mensagens/
POST /api/v1/notificacoes/mensagens/enviar/
GET  /api/v1/notificacoes/mensagens/status-conexao/
GET/PATCH /api/v1/notificacoes/configuracao/          ← singleton · GET e PATCH exigem login (só aqui GET também é restrito — expõe credencial Z-API) · PATCH audita config_whatsapp_alterada
POST      /api/v1/notificacoes/configuracao/testar/   ← exige login · testa conexão Z-API, não muda nada, não audita

# Usuários (Multi-Empresa Fase 2 — ver Padrões Obrigatórios)
GET/POST              /api/v1/usuarios/                  ← aceita "empresas_ids" (lista de ids) no POST/PATCH
GET/PUT/PATCH/DELETE  /api/v1/usuarios/{id}/
POST                  /api/v1/usuarios/login/           ← AllowAny — retorna dados do usuário + "token" (Usuario.auth_token)
                                                            + empresas/empresa_ativa/preferencia_tema "efetivos"
POST                  /api/v1/usuarios/logout/           ← autenticado — invalida o token no servidor
POST                  /api/v1/usuarios/{id}/redefinir-senha/
POST                  /api/v1/usuarios/definir-empresa-ativa/  ← exige login · body {"empresa": id} · admin ativa
                                                                   qualquer empresa ativa=True, demais só vinculadas ·
                                                                   audita empresa_alternada
POST                  /api/v1/usuarios/preferencia-tema/       ← exige login · body {"tema": "empresa"|"neutro_claro"|
                                                                   "neutro_escuro"} · não audita (cosmético)

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

# Relatórios (Fase 5 do multi-empresa — ver Padrões Obrigatórios: as duas rotas abaixo também
# aceitam ?empresa=<id>/?empresa=todas, default empresa_ativa do usuário autenticado senão Empresa.get_padrao())
GET /api/v1/relatorios/ifood/                    ← query params: data_inicio, data_fim, agrupamento (dia|mes), formato (json|excel|pdf), empresa
GET /api/v1/relatorios/produtos-mais-vendidos/   ← query params: canal (repetível: ifood|pdv|eventos, default todos), data_inicio, data_fim, ordenar (quantidade|valor), limit (1-200, default 30), empresa · só JSON

# Dashboard (Fase 5 do multi-empresa — ver Padrões Obrigatórios)
GET /api/v1/dashboard/resumo/                    ← aceita ?empresa=<id>/?empresa=todas (default: empresa_ativa
                                                     do usuário autenticado, senão Empresa.get_padrao()); agrega
                                                     canais (iFood/PDV/Eventos/Anota AI), total recebido hoje +
                                                     comparativo vs ontem, gráfico 7 dias, a receber, fila
                                                     operacional, próximos eventos, ticket médio e
                                                     repasse_ifood_a_receber (empresa não-matriz)

# Financeiro (fases 0-6 de 8 — ver FINANCEIRO.md — + Fase 4 do multi-empresa, ver MULTIEMPRESA.md e Padrões Obrigatórios)
# Fase 4: todos os endpoints abaixo (exceto categorias/fornecedores/telefones-alerta, compartilhados) aceitam
# ?empresa=<id> (default: empresa_ativa do usuário autenticado, senão Empresa.get_padrao()) e ?empresa=todas
# (consolidado, sem filtro) — omitido nas linhas abaixo por repetição, mesma regra em todas
GET/POST         /api/v1/financeiro/categorias/                  ← POST exige login
GET/PATCH/DELETE /api/v1/financeiro/categorias/{id}/              ← DELETE exige login · audita registro_excluido
GET/POST         /api/v1/financeiro/contas-bancarias/             ← POST exige login · sem DELETE (PROTECT do ledger, desativar via ativo=False)
GET/PATCH        /api/v1/financeiro/contas-bancarias/{id}/        ← PATCH exige login
GET/POST         /api/v1/financeiro/fornecedores/                 ← busca por ?search= (nome/cnpj) · POST exige login
GET/PATCH/DELETE /api/v1/financeiro/fornecedores/{id}/            ← DELETE exige login · audita registro_excluido
GET/POST         /api/v1/financeiro/contas-pagar/                 ← filtros: status, categoria, fornecedor, mes (YYYY-MM), search · POST exige login · audita registro_criado
GET/PATCH        /api/v1/financeiro/contas-pagar/{id}/            ← PATCH exige login · só com status='pendente' · audita registro_atualizado
POST             /api/v1/financeiro/contas-pagar/{id}/baixa/      ← exige login · body: data, valor, conta, forma, comprovante (multipart opcional) · audita baixa_registrada
POST             /api/v1/financeiro/contas-pagar/{id}/cancelar/   ← exige login · só se valor_pago == 0 · audita status_alterado
GET              /api/v1/financeiro/contas-pagar/resumo/          ← cards: em_atraso, vence_hoje, proximos_7_dias, total_mes {pago, pendente}
GET              /api/v1/financeiro/movimentos/                  ← só leitura (ledger, imutável) · filtros: conta, tipo, categoria, data_inicio, data_fim
POST             /api/v1/financeiro/movimentos/manual/            ← exige login · lançamento avulso/estorno · origem_tipo='manual' · audita movimento_manual
GET/PATCH        /api/v1/financeiro/configuracao/1/               ← 1 linha por empresa (Fase 4) · pk na URL é ignorado, resolve por ?empresa= · PATCH exige login · audita config_financeira_alterada
GET/POST         /api/v1/financeiro/telefones-alerta/
GET/PATCH/DELETE /api/v1/financeiro/telefones-alerta/{id}/        ← DELETE exige login · audita registro_excluido
GET/POST         /api/v1/financeiro/recorrentes/                  ← POST exige login
GET/PATCH        /api/v1/financeiro/recorrentes/{id}/             ← PATCH exige login (inclui ativo=False para pausar) · sem DELETE
GET/POST         /api/v1/financeiro/contas-receber/                ← filtros: canal, status, mes (YYYY-MM), search · POST exige login (sempre cria canal='manual')
GET/PATCH        /api/v1/financeiro/contas-receber/{id}/           ← PATCH exige login
POST             /api/v1/financeiro/contas-receber/{id}/baixa/     ← exige login · mesmo BaixaContaSerializer da baixa de ContaPagar · audita baixa_registrada
GET              /api/v1/financeiro/contas-receber/resumo/         ← recebido_hoje, a_receber, proximos_30_dias — inclui saldo de Evento via query dinâmica (nunca materializado como linha), só quando a empresa filtrada é a matriz ou 'todas'
GET/POST         /api/v1/financeiro/conferencias/                  ← POST exige login · saldo_calculado é sempre snapshot de ContaBancaria.saldo_atual no momento (nunca vem do payload) · sem PATCH/DELETE
GET              /api/v1/financeiro/fluxo-caixa/?dias=N            ← N entre 1-90 (default 14) · por dia: entrada/saida realizada (ledger) e projetada (ContaPagar/ContaReceber pendente/parcial) · + saldos por conta e última conferência de cada uma

# Backup (ver backup.md e Padrões Obrigatórios)
GET/PATCH             /api/v1/manutencao/configuracao-backup/1/      ← singleton · exige login
GET/POST              /api/v1/manutencao/telefones-alerta/           ← exige login
GET/PATCH/DELETE      /api/v1/manutencao/telefones-alerta/{id}/      ← exige login · DELETE audita registro_excluido

# Multi-Empresa — Fase 0 (ver MULTIEMPRESA.md e Padrões Obrigatórios)
GET/POST/PATCH        /api/v1/empresas/[{id}/]           ← sem DELETE/PUT · POST/PATCH exigem login · audita registro_criado/registro_atualizado
GET                   /api/v1/empresas/branding-login/   ← AllowAny · nome/logos/cores da empresa padrao=True (tela de login, ainda não consumido pelo frontend)
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

# Gerar Contas a Pagar Recorrentes (cron diário — ex: 07:00)
python manage.py gerar_contas_recorrentes
# horizonte vem de ConfiguracaoFinanceira.get().horizonte_recorrencia_dias · idempotente
# (não duplica se rodar mais de uma vez no mesmo dia)

# Alertas de Vencimento Financeiro (cron diário — ex: 08:30)
python manage.py alertar_vencimentos
# antecedência/repetição vêm de ConfiguracaoFinanceira.get() (painel) · precisa de ao menos 1
# financeiro.TelefoneAlertaFinanceiro ativo, senão não notifica ninguém

# Backup do banco + mídia (cron diário — 03:00)
python manage.py fazer_backup
# config vem de ConfiguracaoBackup.get() (pastas/retenção/remote) · pg_dump -Fc + tarfile de media/
# + rclone copy pro Backblaze B2 (remote "backup-remoto") · nunca notifica

# Verificação do backup + alerta (cron diário — 08:00, 5h de folga sobre o fazer_backup)
python manage.py verificar_backup
# checa idade/tamanho do backup mais recente · alerta manutencao.TelefoneAlertaBackup via
# WhatsApp se ausente/desatualizado/corrompido · sem dedup, repete todo dia enquanto quebrado

# Restauração (SEMPRE manual — não existe management command pra isso, de propósito)
# Banco:
PGPASSWORD='<senha>' pg_restore -h localhost -p 5432 -U arretado_user -d arretado_db --clean --if-exists --no-owner /var/backups/arretado/db/crm_db_TIMESTAMP.dump
# Mídia:
tar xzf /var/backups/arretado/media/media_TIMESTAMP.tar.gz -C /var/www/crm_arretado/ --overwrite
# Se o backup local também tiver sumido, baixar do B2 primeiro:
rclone copy backup-remoto:arretado-backups/db/ /var/backups/arretado/db/
rclone copy backup-remoto:arretado-backups/media/ /var/backups/arretado/media/
# Parar `arretado.service` antes de restaurar o banco e religar depois

# Testes automatizados (clientes, eventos, fichas, pdv, auditoria, usuarios, notificacoes, pedidos, estoque, financeiro, relatorios)
python manage.py test --settings=config.settings_test
# settings_test.py roda contra SQLite em memória — o usuário do Postgres em produção
# não tem permissão CREATE DATABASE, então `manage.py test` direto (sem --settings) falha
# settings_test.py também isola MEDIA_ROOT num tempfile.mkdtemp() — sem isso, testes com
# FileField/ImageField (ImagemInspiracao, ImportacaoNotaFiscal) gravam de verdade no media/
# real (só o banco é isolado por padrão, não o filesystem). Bug real encontrado 18/ago/2026:
# rodar os testes como root criava diretórios em media/ com dono root:root, e o próximo
# upload real de usuário (processo www-data do Gunicorn) quebrava com PermissionError —
# ver "O Que NÃO Fazer"

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
systemctl restart arretado-polling   # ver "Atenção" abaixo — nunca esquecer este

# Se o deploy marca uma nova versão (ver "Versão do Sistema" em Padrões Obrigatórios):
git tag -a vX.Y.Z -m "Descrição curta da release"
git push origin vX.Y.Z
# + adicionar a entrada correspondente no CHANGELOG.md (commit separado ou junto do
# último commit da feature, antes de tagear)
```

**Atenção:** `npm run build` grava direto em `arretado-crm/dist/`, que é o `root` servido pelo Nginx (`/etc/nginx/sites-available/arretado`) — o build já é o deploy do frontend, não existe ambiente de teste isolado. Sempre confirmar com o usuário antes de rodar build na VPS.

**Atenção — `arretado-polling` também precisa reiniciar, sempre que o deploy mexe em models.** `systemctl restart arretado` (Gunicorn) sozinho não é suficiente: o worker `arretado-polling` é um processo de longa duração separado, que só recarrega o código Python quando o systemd o reinicia — ele não é stateless por request como o Gunicorn. **Incidente real (12-17/ago/2026):** o deploy da Fase 1 do Multi-Empresa adicionou o campo obrigatório `empresa` em `ifood.PedidoIFood` e só reiniciou `arretado`, esquecendo do `arretado-polling` — o worker ficou rodando a classe de modelo antiga em memória, todo `INSERT` de pedido novo saiu sem a coluna `empresa_id` e o Postgres rejeitou (`NotNullViolation`) silenciosamente por **5 dias**, sem nenhum pedido iFood novo sendo capturado (245 pedidos reais perdidos, recuperados depois via re-fetch na API do iFood + replay do histórico de `EventoPollingIFood` — ver `project_multiempresa_spec` na memória). Regra: qualquer deploy que rode `migrate` deve reiniciar os dois serviços juntos, não só o `arretado`.

Infra já configurada em produção (não precisa recriar):
- Nginx: `location /media/ { alias /var/www/crm_arretado/media/; }` (serve uploads de `ImageField`/`FileField`) e `proxy_set_header X-Forwarded-Proto $scheme;` no bloco `/api/`
- Nginx: `client_max_body_size 10m;` no bloco `server` (porta 443) — adicionado na feature de importação de nota fiscal, pra permitir upload de foto de nota fiscal por celular (default do Nginx é 1MB, insuficiente)
- Django: `MEDIA_URL`/`MEDIA_ROOT` e `SECURE_PROXY_SSL_HEADER` em `config/settings.py` (para URLs absolutas de imagem saírem com `https://` corretamente atrás do proxy reverso)
- Git: `safe.directory = /var/www/crm_arretado` em `/etc/gitconfig` (`--system`) — necessário pro Gunicorn (`www-data`) rodar `git describe` em `config/versao.py::obter_versao()`, já que o repo é dono por `root` (ver "Versão do Sistema" em Padrões Obrigatórios)

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
- Ao adicionar/remover linha da lista `condicoes` em `pdf_orcamento.py` (bloco "CONDIÇÕES COMERCIAIS"), ajustar o piso `cond_y = max(y - 10, N)` na mesma proporção (±11pt por linha) — esse piso é o que impede o bloco de colidir com a área de assinatura (`sig_y = 98`, fixa) no cenário de orçamento mais longo (muitos itens/observações empurram `y` pra baixo); esquecer de ajustar faz a última linha sobrepor "Teresina, ____/____/________" nesse cenário (bug real corrigido ao adicionar 2 linhas nesta sessão — piso subiu de 162 para 184)
- Não criar `ImagemInspiracao` por item de Orçamento — a galeria pertence ao Orçamento inteiro (decisão já confirmada com o usuário)
- Não esquecer de propagar `natureza=item.natureza` em `OrcamentoViewSet.converter_em_evento` ao criar cada `ItemEvento` — sem isso, todo item de brinde/permuta de um orçamento convertido vira venda cobrada no evento gerado (ver "Brindes e Permutas — Fases 1-5")
- Não montar `preco_total` de `ItemOrcamento`/`ItemEvento`/`ItemPedidoPDV` manualmente sem passar pelo `save()` do model — é ele quem decide zerar ou não com base em `natureza`; nunca setar `preco_total` direto num `.update()`/`.objects.filter().update()` em massa
- Não deixar `financeiro/signals.py` gravar `MovimentoFinanceiro` de um pedido/pagamento com valor `<= 0` — o guard já existe em `_registrar_venda_pdv()`/`_registrar_pagamento_evento()`, replicar o mesmo padrão em qualquer novo signal de venda que a feature de Brindes e Permutas venha a tocar
- Não contar item `brinde`/`permuta` em `relatorios.ProdutosMaisVendidosView` — `_qs_pdv()`/`_qs_eventos()` sempre filtram `natureza='venda'`; não remover esse filtro nem replicá-lo em `_qs_ifood()` (o campo não existe em `ItemPedidoIFood`, iFood não tem esse conceito)
- Não esconder item de brinde/permuta do PDF (`pdf_orcamento.py`/`pdf_contrato.py`) — decisão do spec é transparência total: mostrar com rótulo + preço de tabela riscado, nunca omitir a linha
- Não deixar o usuário editar `preco_unit` no frontend quando `natureza != 'venda'` — input sempre `disabled` nos 3 forms (`Orcamentos.jsx`/`Eventos.jsx`/`PDV.jsx`), preço trava no valor de tabela do produto/catálogo, mesma regra do backend (nunca aceitar preço arbitrário de brinde/permuta)
- Ao somar `preco_total` de item recém-criado num `create()` de serializer com itens aninhados (`OrcamentoCreateSerializer`/`EventoCreateSerializer`/`PedidoPDVCreateSerializer`), sempre usar `item.preco_total` (o valor persistido pelo `save()` do model, já ajustado por `natureza`) — nunca uma variável local `preco_unit * quantidade` calculada antes de criar o item, que ignora brinde/permuta e infla o subtotal (bug real já corrigido em `eventos/serializers.py`, ver "Brindes e Permutas — Fases 1-5")
- Não incluir as imagens de `ImagemInspiracao` no PDF do orçamento nem na mensagem de WhatsApp — é uso interno da equipe, nunca client-facing
- Não duplicar `ImagemInspiracao` para o Evento na conversão — o Evento só **lê** via `orcamento_origem`, nunca copia as imagens; e quando o Evento adiciona uma nova imagem (`POST /eventos/{id}/imagens/`) e tem `orcamento_origem`, ela é anexada ao **Orçamento**, não ao Evento — nunca criar com `evento=` nesse caso (`ImagemInspiracao.evento` só é usado quando não há orçamento de origem, ver Padrões Obrigatórios)
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
- Não gravar `financeiro.ContaBancaria.saldo_atual` direto — sempre via `MovimentoFinanceiro.registrar()` (mesma regra de `MovimentoEstoque`/`PedidoUnificado`/`Evento.sinal_pago`)
- Não gravar `financeiro.ContaPagar.valor_pago`/`status` direto — sempre via `recalcular_valor_pago()`, chamado depois de cada baixa
- Não implementar DELETE de `financeiro.MovimentoFinanceiro` — ledger imutável; erro se corrige com um lançamento manual inverso (estorno), nunca apagando o original
- Não semear `financeiro.CategoriaFinanceira` com valores hardcoded — requisito de revenda, o cadastro nasce vazio e é o usuário quem cadastra
- Não permitir `PATCH` em `financeiro.ContaPagar` quando `status` não for `pendente` — depois da primeira baixa, os campos de valor/vencimento ficam imutáveis (mesma filosofia de `Orcamento`)
- Não instanciar `ConfiguracaoFinanceira()` diretamente — sempre usar `ConfiguracaoFinanceira.get(empresa)` (desde a Fase 4 do multi-empresa, o argumento é obrigatório — não é mais singleton global)
- Não gravar `financeiro.ContaPagar.recorrente` fora do cron `gerar_contas_recorrentes` — é `read_only` no serializer, a API nunca deixa o usuário setar esse campo na criação manual
- Não criar `ContaPagar` de uma `DespesaRecorrente` sem checar a `UniqueConstraint(recorrente, data_vencimento)` primeiro — o cron sempre confere `ContaPagar.objects.filter(recorrente=..., data_vencimento=...).exists()` antes de criar, nunca confia só na constraint pra evitar duplicata silenciosa
- Não implementar `DELETE` em `financeiro.DespesaRecorrente` — pausar é `ativo=False`; `categoria`/`fornecedor` são `PROTECT` e travariam a exclusão de qualquer forma se já tiver `ContaPagar` gerada
- Não materializar `financeiro.ContaReceber` para Eventos nem para PDV — Eventos consultam saldo dinamicamente (`Evento.valor_total - sinal_pago`); PDV e iFood `no_ato` batem direto no ledger via signal. Criar registro ali é dupla contagem (mesma regra do saldo de Evento no Dashboard)
- Não gravar `financeiro.ContaReceber.canal`/`origem_canal`/`origem_id` a partir da API — são `read_only` no serializer; `POST /financeiro/contas-receber/` sempre força `canal='manual'`/`origem_canal='manual'` em `perform_create()`, os registros `canal='ifood'` só nascem no signal
- Não gravar movimento de `ifood.PedidoIFood` em cada evento de polling — o signal financeiro só age na transição pra status terminal (`CONCLUDED`), nunca em `CONFIRMED`/`PREPARATION_STARTED`/etc (mesma lição de idempotência já aplicada no débito de estoque, mas aqui o gatilho é status diferente — CONCLUDED, não CONFIRMED)
- Não criar `financeiro.ContaBancaria` automaticamente dentro de um signal — sem `ConfiguracaoFinanceira.conta_padrao_vendas` configurada, o signal correspondente (PDV confirmado, iFood `no_ato` concluído, PagamentoEvento pago) loga warning e não grava nada; configurar a conta é passo manual do usuário
- Não mexer na geração de `MovimentoEstoque` dentro do `confirmar()` da nota fiscal — a `ContaPagar` é acrescentada **depois**, em método próprio (`_gerar_conta_pagar_da_nota()`), sem alterar o fluxo de estoque já existente
- Não criar `financeiro.MateriaPrima`/`Fornecedor` automaticamente sem nenhum dado extraído — `_resolver_fornecedor()` só cria um `Fornecedor` novo quando há `fornecedor_nome` **ou** `fornecedor_cnpj` extraído da nota; sem nenhum dos dois, a `ContaPagar` nasce com `fornecedor=None`
- Não gravar `financeiro.ContaPagar.categoria` automaticamente na geração por nota fiscal — nasce sempre `None`, é o usuário quem categoriza depois via `PATCH` (mesma razão de `CategoriaFinanceira` nunca ter seed automático: a extração não tem como adivinhar categoria contábil)
- Não fazer `DELETE` do `MovimentoFinanceiro` original ao estornar cancelamento de PDV/iFood ou remoção de `PagamentoEvento` — sempre um movimento manual inverso novo (`origem_tipo='manual'`, `origem_id=f'estorno-{...}'`), ledger continua imutável
- Não permitir `PATCH`/`DELETE` em `financeiro.SaldoConferido` — uma conferência nova é sempre um registro novo, nunca uma correção da anterior; o histórico completo fica no banco, a UI só mostra a mais recente por conta
- Não aceitar `saldo_calculado` vindo do payload em `POST /financeiro/conferencias/` — é sempre o snapshot de `ContaBancaria.saldo_atual` no momento do POST (`read_only` no serializer, preenchido em `perform_create()`), nunca calculado pelo cliente
- Não somar o saldo dinâmico de Evento em `GET /financeiro/fluxo-caixa/` — diferente de `contas-receber/resumo/`, o agregador de fluxo de caixa só olha `ContaPagar`/`ContaReceber` (decisão de escopo da Fase 6, ver Padrões Obrigatórios)
- Não instanciar `ConfiguracaoBackup()` diretamente — sempre usar `ConfiguracaoBackup.get()`
- Não colocar a senha do banco na linha de comando do `pg_dump`/`pg_restore` — usar `PGPASSWORD` via variável de ambiente (mesma regra já aplicada ao `pg_dump` de `fazer_backup.py`)
- Não usar `subprocess`/`tar` do sistema para compactar a mídia no backup — usar `tarfile` (stdlib), mesmo padrão já usado em `fazer_backup.py`
- Não fazer `fazer_backup` chamar `notificar()` — responsabilidade exclusiva do `verificar_backup`, pra não mandar WhatsApp de "backup ok" todo dia
- Não criar um management command `restaurar_backup` — restauração é sempre manual (`pg_restore`/`tar` direto, documentado em Padrões Obrigatórios e `backup.md`), decisão consciente pra evitar que algo tão raro e arriscado seja disparado sem querer
- Não incluir o `.env` no backup — contém chaves (Z-API, `ANTHROPIC_API_KEY` futura); guardar `.env` é procedimento manual separado, fora deste sistema
- Não adicionar dedup de alerta (`AlertaBackupEnviado`) ao `verificar_backup` — repetição diária enquanto o backup estiver quebrado é decisão consciente (é o único problema do sistema que fica invisível até o dia em que se precisa dele)
- Não resolver a empresa padrão por id fixo em código (`Empresa.objects.get(pk=1)`) — sempre `Empresa.get_padrao()`
- Não permitir duas empresas com `padrao=True`, nem desmarcar a única com `padrao=True` sem promover outra na mesma requisição — os dois casos são bloqueados no `EmpresaSerializer.validate()`/`UniqueConstraint` condicional; não contornar essa validação em nenhum endpoint novo
- Não implementar `DELETE`/`PUT` em `empresas.Empresa` — inativar é sempre `ativo=False` (mesma filosofia de `DespesaRecorrente`/`ConfiguracaoIFood`); FKs de outros apps vão apontar pra cá com `PROTECT` nas próximas fases
- Não hardcodar nome/cor/CNPJ de nenhuma empresa (Arretado ou futuras) em código, CSS ou serializer — é requisito de revenda do multi-empresa (ver `MULTIEMPRESA.md`); campo de cor vazio já cai no token CSS atual por construção, não duplicar a paleta da Arretado em nenhum lugar
- Não resolver `empresa` em `dashboard/views.py`/`relatorios/views.py` por caminho diferente de `_resolver_empresa()` (`?empresa=` explícito > `empresa_ativa` do usuário > `Empresa.get_padrao()`) — mesmo padrão duplicado em cada app (não importar de `financeiro/views.py`, ver CLAUDE.md sobre não importar função privada de outro app)
- Não somar `Evento`/`PagamentoEvento`/estoque (`MateriaPrima`/`Produto`) sem o gate `eventos_habilitado`/`matrizView` em `dashboard/views.py` — esses 3 são mono-empresa (sem FK `empresa` própria), então filtrar por empresa não os zera sozinho; sem o gate explícito, a visão de uma empresa não-matriz (ex: MANGAIO) mostraria dados de eventos/estoque da matriz
- Não materializar `Empresa.modulos_ocultos` como controle de acesso — é só filtro de UI na Sidebar (`App.jsx` continua registrando todas as rotas); não bloquear nenhum endpoint com base nesse campo
- Não gravar `financeiro.ContaBancaria`/`ContaPagar`/`ContaReceber`/`DespesaRecorrente.empresa` fora do que `financeiro/views.py::_resolver_empresa()` resolve (`?empresa=` explícito > `empresa_ativa` do usuário > `Empresa.get_padrao()`) — os 4 campos são `read_only` nos serializers de propósito, nunca aceitos do payload
- Não denormalizar `empresa` em `financeiro.MovimentoFinanceiro` — é sempre a `property` que delega pra `self.conta.empresa` (mesma regra do "O Que NÃO Fazer" do `MULTIEMPRESA.md` — ver Padrões Obrigatórios)
- Não permitir `financeiro.ConfiguracaoFinanceira.conta_padrao_vendas` apontando pra uma `ContaBancaria` de empresa diferente — validado em `ConfiguracaoFinanceiraSerializer.validate_conta_padrao_vendas()`
- Não resolver `conta_padrao_vendas`/config financeira de um pedido iFood via `Empresa.get_padrao()` — sempre `pedido.empresa` (permite MANGAIO e matriz em modos de recebimento diferentes simultaneamente); PDV e `PagamentoEvento` continuam sempre `Empresa.get_padrao()` (mono-empresa por escopo)
- Não bloquear login por falta de vínculo de empresa — `usuarios.Usuario` sem nenhuma `empresas` vinculada (ou cuja única empresa virou `ativo=False`) sempre cai na empresa padrão via `_empresas_efetivas()`; nunca retornar 403/404 nesse caso
- Não permitir `definir-empresa-ativa/` pra empresa fora do vínculo do usuário — exceto `role=admin`, que pode ativar qualquer empresa `ativo=True` (checar sempre `usuario.empresas.filter(pk=empresa.pk).exists()` antes, exceto pra admin)
- Não auditar `preferencia-tema/` (cosmético) — auditar sempre `definir-empresa-ativa/` (`empresa_alternada`, afeta dado financeiro que o usuário enxerga nas próximas fases)
- Não deixar `empresa_ativa`/`preferencia_tema` editáveis por `PATCH /usuarios/{id}/` direto (nem por admin editando outro usuário) — só mudam via os dois endpoints dedicados (`UsuarioSerializer` mantém os dois como `read_only`)
- Não usar `localStorage` como fonte da verdade de empresa ativa/tema — o padrão é sempre gravar no backend primeiro (`usuariosApi.definirEmpresaAtiva`/`preferenciaTema`) e só depois espelhar a resposta via `authApi.atualizarCache()` (mantém o mesmo objeto `auth_user` já cacheado coerente após F5 — não é uma fonte de verdade nova, é o mesmo padrão já existente do cache de sessão)
- Não confundir os 12 campos de cor de `Empresa` com os nomes de token do `MULTIEMPRESA.md` (tabela conceitual da Fase 0) — os tokens **reais** em `index.css` têm nomes diferentes (`--bg` não `--fundo`, `--caramelo` não `--primaria`, etc.); o mapeamento de fato vive em `src/utils/tema.js::aplicarCoresEmpresa()`, único lugar que faz essa tradução
- Não setar cor de empresa/tema neutro direto via `document.documentElement.style`/`dataset` em nenhum componente novo — sempre pelas funções de `utils/tema.js` (`aplicarCoresEmpresa`/`aplicarModoNeutro`/`aplicarTema`), chamadas só em `useAuth.jsx` (autenticado) e `Login.jsx` (pré-login) — nenhum outro lugar
- Ao adicionar um campo de cor `#fff`/token novo pensando em tema de empresa, sempre usar o valor hex **atual** como default em `:root` — nunca um valor novo "mais bonito" — e sempre em par `--x-bg`/`--x-fg` (nunca hex único embutido), pra que `temas.css` consiga redefinir a dupla sem reescrever estrutura
- Não redefinir `--badge-{ifood,anotaai}-*`/`--whatsapp*` dentro de `temas.css` — são identidade de marca de terceiro, sempre fixos nos dois temas neutros (só o `:root` base os define)
- Não perseguir 100% dos hex hardcoded restantes nos CSS Modules como um objetivo desta fase — famílias como `#EF4444`/`#3B82F6`/`#F59E0B`/`#10B981`/`#6B7280` (ações do PDV), semáforo neutro do CentralPrecos e badges de texto do Configuracoes ficaram de propósito fora (decisão consciente, ver Padrões Obrigatórios) — só revisitar se ficarem de fato ilegíveis no tema escuro
- Não resolver credencial de ação de pedido iFood (confirmar/cancelar/despachar/pronto-retirada/negociação) via `ConfiguracaoIFood.objects.first()` — sempre `ConfiguracaoIFood.objects.filter(empresa=pedido.empresa)` (ver `ifood/views.py::PedidoIFoodViewSet._get_client()`); com dois merchants ativos (matriz + MANGAIO), `.first()` mistura credencial de uma empresa com pedido de outra
- Não materializar `pdv.PedidoPDV`/`eventos.Evento` com empresa diferente da padrão — PDV e Eventos são mono-empresa por decisão de escopo do `MULTIEMPRESA.md` (Fases 3-ext-A e 4 do produto, não do multi-empresa), sempre gravam `Empresa.get_padrao()` no `PedidoUnificado`, nunca a empresa "ativa" de um usuário (esse conceito só existe a partir da Fase 2 do multi-empresa)
- Não hardcodar a versão do sistema em nenhum arquivo/settings/variável — `obter_versao()` sempre deriva de `git describe --tags`; criar uma release é sempre `git tag -a` + push da tag + entrada no `CHANGELOG.md`, nunca editar um número em código
- Não esquecer da tag ao fazer um deploy que o usuário considera uma "versão nova" — sem tag, `git describe` só mostra `vX.Y.Z-N-g<hash>` (commits à frente da última tag), o que é informativo mas não é uma versão "oficial"; perguntar ao usuário se o deploy atual merece uma tag antes de criar uma (nem todo commit/deploy precisa virar release)
- Não reiniciar só `arretado.service` num deploy que muda `models.py` de qualquer app usado pelo `arretado-polling` (hoje: `ifood`, `clientes`, `pedidos`, `empresas`) — reiniciar os dois serviços juntos (`systemctl restart arretado arretado-polling`), sempre. Incidente real: esquecer o `arretado-polling` fez o worker rodar 5 dias com o modelo antigo em memória, perdendo 245 pedidos reais do iFood (ver "Deploy VPS (checklist)")
- Não rodar `manage.py test` esperando que o filesystem fique isolado igual ao banco — só o banco vira SQLite em memória; `MEDIA_ROOT` é isolado à parte em `settings_test.py` (`tempfile.mkdtemp()`, já corrigido) porque testes com `FileField`/`ImageField` gravam de verdade no disco. Se algum dia criar um `settings_test.py` novo do zero (outro app, outro ambiente), lembrar de isolar `MEDIA_ROOT` também — bug real já causou `PermissionError` em upload de usuário real em produção (ver "Como Rodar")
