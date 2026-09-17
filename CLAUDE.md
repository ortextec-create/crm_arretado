# Arretado Doces — CRM Proprietário

> Arquivo lido automaticamente pelo Claude Code em toda sessão.
> Última atualização: 14/set/2026 — reduzido de ~200KB para enxuto. O histórico de implementação
> de cada feature grande (fases, decisões, bugs encontrados, datas de deploy) vive nos specs
> dedicados (`MULTIEMPRESA.md`, `FINANCEIRO.md`, `BRINDES_PERMUTAS.md`, `Contrato.md`, `FRETE.md`,
> `backup.md`, `IFOOD_RECEITA_DASHBOARD.md`) e na memória do Claude Code (`MEMORY.md` e arquivos
> `project_*.md`) — este arquivo documenta só o estado atual e as regras vigentes. Se precisar do
> "porquê" de uma decisão antiga, procure lá antes de perguntar ao usuário.

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
│   ├── versao.py                ← `obter_versao()` — versão via `git describe --tags --always --dirty`, cacheada por processo (`lru_cache`) — ver "Versão do Sistema"
│   ├── views.py                 ← `VersaoView` (APIView, AllowAny)
│   └── wsgi.py
├── empresas/                    ← Multi-Empresa (ver MULTIEMPRESA.md) — model Empresa (multi-tenant
│   │                               por linha), consumido por ifood/, usuarios/, financeiro/,
│   │                               dashboard/, relatorios/ — falta só cadastrar a MANGAIO de fato
│   ├── models.py                ← Empresa (cnpj único quando preenchido, `padrao` — exatamente uma
│   │                               True via UniqueConstraint condicional, `ativo`, 12 campos de cor
│   │                               hex `cor_*` opcionais — vazio herda o token CSS, 3 logos + 1
│   │                               timbre (preparatório, nenhum PDF lê ainda), `modulos_ocultos`
│   │                               JSONField — Sidebar.jsx esconde itens de menu listados aqui) ·
│   │                               `Empresa.get_padrao()` — nunca resolver por id fixo em código
│   └── views.py                 ← EmpresaViewSet (CRUD sem DELETE/PUT — inativar é `ativo=False`,
│                                    audita create/update) + action `branding-login` (AllowAny)
├── clientes/                    ← CRM de clientes
│   ├── models.py                ← Cliente (rg/rg_orgao_emissor/nacionalidade/profissao/estado_civil
│   │                               opcionais no cadastro, exigidos só na emissão de Contrato — ver
│   │                               Contrato.md), Endereço, TagCliente
│   └── views.py                 ← inclui action `historico` (GET /clientes/{id}/historico/ —
│                                    histórico de PEDIDOS, não confundir com auditoria)
├── ifood/                       ← integração iFood · multi-empresa desde a Fase 1 do
│   │                               MULTIEMPRESA.md (1 ConfiguracaoIFood por empresa/merchant, nunca
│   │                               foi singleton)
│   ├── models.py                ← ConfiguracaoIFood (+ FK `empresa` PROTECT), PedidoIFood (+ FK
│   │                               `empresa` PROTECT, denormalizada — snapshot no momento da
│   │                               criação), ItemPedidoIFood, EventoPollingIFood
│   ├── ifood_client.py          ← IFoodClient — sempre instanciado com a ConfiguracaoIFood da
│   │                               empresa do pedido em questão
│   ├── polling_worker.py        ← run_polling()/_processar_config()/_criar_pedido() (grava
│   │                               `empresa = config.empresa` no pedido criado)
│   └── management/commands/ifood_polling.py
├── pedidos/                     ← espelho unificado (só leitura)
│   ├── models.py                ← PedidoUnificado (+ FK `empresa` PROTECT, `null=True` — iFood
│   │                               propaga a empresa do PedidoIFood; PDV/Eventos são mono-empresa e
│   │                               sempre gravam `Empresa.get_padrao()`, nunca id fixo)
│   └── apps.py                  ← registra signals do iFood e PDV no ready()
├── pdv/                         ← PDV próprio
│   ├── models.py                ← CategoriaProduto, Produto (+ segmento/foto/tipo
│   │                               fabricado|revenda|kit com custo polimórfico, `preco_para()` por
│   │                               faixa, `modo_estoque`), ItemKit, FaixaPreco (quantidade_minima+
│   │                               canal), DadosFiscaisProduto (prepara NFC-e futura), PedidoPDV,
│   │                               ItemPedidoPDV (+ `natureza` venda/brinde/permuta — ver
│   │                               BRINDES_PERMUTAS.md), TaxaEntregaBairro, ConfiguracaoEntrega
│   │                               (singleton, frete padrão)
│   ├── urls.py                  ← inclui taxas-entrega/ e configuracao-entrega/
│   ├── management/commands/listar_candidatos_revenda.py ← só leitura, lista produtos "fabricado"
│   │                               sem FichaTecnica vinculada (candidatos a virar "revenda")
│   └── signals.py               ← espelha PedidoPDV → PedidoUnificado
├── eventos/                     ← gestão de eventos/encomendas + orçamentos + contratos
│   ├── models.py                ← Orcamento, ItemOrcamento (+ natureza), Evento, ItemEvento (+
│   │                               natureza), LocalEvento, Contrato (snapshot, CTR-0001... — ver
│   │                               Contrato.md), AditivoContrato (snapshot, ADT-0001..., emitido
│   │                               quando o Evento muda de valor depois do Contrato já emitido —
│   │                               ver Contrato.md § 9), ConfiguracaoContrato (singleton),
│   │                               ConfiguracaoAlertaEvento (singleton), TelefoneAlertaEvento,
│   │                               AlertaEventoEnviado, ImagemInspiracao (galeria — FK opcional a
│   │                               Orcamento OU a Evento, exatamente um dos dois via
│   │                               CheckConstraint), PagamentoEvento (Evento.sinal_pago sempre
│   │                               derivado via `recalcular_sinal_pago()`, nunca gravado direto).
│   │                               Orcamento/Evento têm tipo_entrega/local/endereco_avulso/
│   │                               bairro_entrega/taxa_entrega (ver FRETE.md).
│   │                               `Evento.observacoes_cozinha` — orientações internas de produção,
│   │                               só sai no resumo de cozinha, nunca client-facing.
│   │                               Criação/edição/status/item de Orçamento e Evento exigem login e
│   │                               são auditados (`AuditoriaCreateMixin`/`UpdateMixin`/`StatusMixin`)
│   │                               — exceção oportunista só em `converter_em_evento`/
│   │                               `enviar_whatsapp` (AllowAny, captura o ator quando o token vier)
│   ├── pdf_orcamento.py         ← ReportLab canvas cru, 1 página (tabela de itens via
│   │                               `platypus.Table.drawOn()`). "CONDIÇÕES COMERCIAIS" é lista fixa
│   │                               no código. Item com `natureza != 'venda'` ganha rótulo no nome e
│   │                               `preco_unit` riscado (`<strike>`)
│   ├── pdf_contrato.py          ← ReportLab Platypus multi-página — texto/cláusulas sempre de
│   │                               `ConfiguracaoContrato.get()` + snapshot do Contrato, nunca
│   │                               hardcoded. Mesmo tratamento de brinde/permuta na tabela "ANEXO 1"
│   ├── pdf_aditivo.py           ← PDF curto do Termo Aditivo (reaproveita paleta/helpers de
│   │                               pdf_contrato.py) — lê só do snapshot gravado em AditivoContrato
│   │                               (itens_snapshot + totais), nunca do Evento ao vivo
│   ├── pdf_resumo_cozinha.py    ← PDF operacional interno (Platypus, sem timbre) — itens agrupados
│   │                               por categoria via `itertools.groupby`, nunca reordenar em Python
│   │                               depois; item sem categoria cai em "Outros", sempre por último.
│   │                               Nunca expõe preço. Caixa "ORIENTAÇÕES PARA A COZINHA" quando
│   │                               `observacoes_cozinha` preenchido. `?imagens=1` inclui folha
│   │                               separada com imagens de inspiração (PageBreak). Todo texto livre
│   │                               passa por `xml.sax.saxutils.escape()` antes de virar `Paragraph`
│   ├── management/commands/alertar_eventos.py ← cron diário: alerta a equipe (WhatsApp) sobre
│   │                               Evento com saldo pendente perto da data e sobre entrega próxima
│   └── views.py                 ← OrcamentoViewSet (converter-em-evento, gerar-contrato, imagens/,
│                                    itens/{id}/editar/, historico/) + EventoViewSet (pagamentos/,
│                                    gerar-contrato — reemite com dados atuais do evento, diferente do
│                                    de Orçamento —, gerar-aditivo, historico/) + ContratoViewSet +
│                                    AditivoContratoViewSet (só leitura + pdf/enviar-whatsapp, mesmo
│                                    padrão de ContratoViewSet — ver Contrato.md § 9) +
│                                    ConfiguracaoContratoViewSet + ConfiguracaoAlertaEventoViewSet +
│                                    TelefoneAlertaEventoViewSet
├── usuarios/                    ← gestão de usuários + RBAC + autenticação real por token +
│   │                               vínculo multi-empresa (ver MULTIEMPRESA.md)
│   ├── models.py                ← Usuario (auth_token, gerar_token(), `empresas` M2M →
│   │                               empresas.Empresa, `empresa_ativa` FK SET_NULL,
│   │                               `preferencia_tema` choices empresa/neutro_claro/neutro_escuro)
│   ├── authentication.py        ← TokenAuthentication (lê "Authorization: Token <valor>")
│   ├── permissions.py           ← IsAdminRole (reusado por auditoria/)
│   └── views.py                 ← login/logout (devolve empresas/empresa_ativa/preferencia_tema
│                                    "efetivos", com fallback pra empresa padrão),
│                                    definir-empresa-ativa/ + preferencia-tema/, CRUD auditado
├── auditoria/                   ← log de auditoria + presença
│   ├── models.py                ← LogAuditoria (usuario FK SET_NULL + snapshot do nome, acao,
│   │                               detalhes JSON) · PresencaEdicao (heartbeat de "quem está
│   │                               vendo/editando agora")
│   ├── utils.py                 ← `registrar()` — único ponto de escrita, nunca lança exceção ·
│   │                               `ator_ou_none()` — pra actions oportunistas
│   ├── mixins.py                ← AuditoriaDestroyMixin (traduz ProtectedError em 400 amigável) ·
│   │                               CreateMixin/UpdateMixin (só campos alterados) ·
│   │                               StatusMixin (chamado manualmente em cada action de status)
│   └── views.py                 ← LogAuditoriaViewSet (só leitura, IsAdminRole) ·
│                                    PresencaHeartbeatView (POST presenca/, janela de 40s)
├── notificacoes/                ← WhatsApp via Z-API
│   ├── models.py                ← HistoricoMensagem · ConfiguracaoWhatsApp (singleton, inclui
│   │                               `validade_orcamento_dias`)
│   ├── zapi_client.py           ← enviar_texto()/enviar_documento()/status_conexao() · resolve
│   │                               número canônico via phone-exists · lança ZAPIError
│   ├── servico.py               ← `notificar()`/`notificar_documento()` — nunca chamar zapi_client
│   │                               direto fora daqui
│   ├── views.py                 ← MensagemViewSet
│   └── management/commands/lembrar_aniversarios.py
├── fichas/                      ← Catálogo, Fichas Técnicas e Precificação
│   ├── models.py                ← MateriaPrima, FichaTecnica, ItemFichaTecnica, ParametrosNegocio
│   │                               (singleton), SnapshotPrecos
│   ├── views.py                 ← MateriaPrimaViewSet, FichaTecnicaViewSet,
│   │                               ParametrosNegocioViewSet, SnapshotPrecosViewSet,
│   │                               AjusteLinearView, DesfazerAjusteView
│   ├── urls.py                  ← router + ajuste-linear/ + desfazer-ajuste/<id>/
│   └── management/commands/importar_planilha.py  ← popula BD a partir do .xlsx
├── estoque/                     ← controle de estoque de insumos e produtos + produção + alertas +
│   │                               importação de nota fiscal
│   ├── models.py                ← MovimentoEstoque (ledger, fonte única da verdade),
│   │                               Producao (executar() debita insumo/credita produto),
│   │                               ConfiguracaoEstoque (singleton), TelefoneAlertaEstoque,
│   │                               AlertaEstoqueEnviado, ConfiguracaoIA (singleton),
│   │                               ImportacaoNotaFiscal, ItemNotaImportada (staging)
│   ├── signals.py               ← débito automático de estoque na venda (PedidoPDV confirmado,
│   │                               PedidoIFood CONFIRMED, Evento entregue) — idempotente via
│   │                               existence check em `origem_tipo`/`origem_id`
│   ├── extracao_nota.py         ← cascata: extrair_xml() (determinístico) → extrair_texto_pdf()
│   │                               (heurística best-effort) → extrair_ia() (fallback multimodal,
│   │                               nunca lança exceção) → resolver_materia_prima() (fuzzy match)
│   ├── claude_client.py         ← chamada HTTP pura (requests, sem SDK) à API Claude
│   └── views.py                 ← MovimentoEstoqueViewSet, RegistrarCompraView,
│                                    AjusteInventarioView, ProducaoViewSet, ConfiguracaoEstoqueViewSet,
│                                    TelefoneAlertaEstoqueViewSet, ConfiguracaoIAViewSet,
│                                    ImportacaoNotaFiscalViewSet (create() roda a cascata,
│                                    editar-item/, confirmar/, descartar/)
├── relatorios/                  ← relatórios consolidados por canal — multi-empresa desde a Fase 5
│   │                               do MULTIEMPRESA.md
│   ├── views.py                 ← RelatorioIFoodView (resumo + agrupado por dia/mês, export
│   │                               Excel/PDF — só canal iFood) + ProdutosMaisVendidosView (ranking
│   │                               cross-canal iFood+PDV+Eventos — só JSON) + RelatorioEventosView
│   │                               (lista de Eventos no período + resumo + agrupado por dia/mês,
│   │                               export Excel/PDF — mono-empresa, só retorna dado quando a
│   │                               empresa resolvida é a matriz ou 'todas', mesmo gate de
│   │                               `mono_empresa_habilitado` de `ProdutosMaisVendidosView`) · todas
│   │                               aceitam `?empresa=<id>`/`?empresa=todas`
│   └── urls.py                  ← ifood/, produtos-mais-vendidos/, eventos/
├── dashboard/                    ← dashboard multi-canal (só leitura, sem models próprios) —
│   │                               multi-empresa desde a Fase 5 do MULTIEMPRESA.md
│   ├── views.py                 ← DashboardResumoView (agrega PedidoUnificado + PagamentoEvento/
│   │                               Evento num único JSON) · aceita `?empresa=<id>`/`?empresa=todas`
│   ├── tests.py
│   └── urls.py                  ← resumo/
├── financeiro/                  ← Contas a Pagar/Receber + ledger de caixa (spec completa em
│   │                               FINANCEIRO.md) + Fase 4 do multi-empresa (ver MULTIEMPRESA.md)
│   ├── models.py                ← CategoriaFinanceira (compartilhada, sem seed), ContaBancaria (+
│   │                               FK `empresa` PROTECT), Fornecedor (compartilhado),
│   │                               ConfiguracaoFinanceira (1 linha por empresa,
│   │                               `get(empresa)`), TelefoneAlertaFinanceiro (compartilhado),
│   │                               MovimentoFinanceiro (ledger, `empresa` é property que delega
│   │                               pra `conta.empresa`), ContaPagar (valor_pago/status derivados,
│   │                               FK `recorrente` opcional), ContaReceber (idem, só existe pra
│   │                               iFood modo 'repasse' ou lançamento manual), DespesaRecorrente
│   │                               (dias_vencimento JSONField), AlertaFinanceiroEnviado,
│   │                               SaldoConferido (snapshot de saldo, sem edição)
│   ├── signals.py               ← bate no ledger no fluxo normal de venda (PDV confirmado, iFood
│   │                               CONCLUDED, PagamentoEvento pago) + estorno automático em
│   │                               cancelamento/remoção — nunca cria ContaBancaria sozinho
│   ├── management/commands/gerar_contas_recorrentes.py ← cron diário, idempotente pela
│   │                               UniqueConstraint(recorrente, data_vencimento)
│   ├── management/commands/alertar_vencimentos.py ← cron diário
│   └── views.py                 ← CategoriaFinanceiraViewSet/ContaBancariaViewSet/
│                                    FornecedorViewSet, MovimentoFinanceiroViewSet (só leitura +
│                                    manual/), ConfiguracaoFinanceiraViewSet,
│                                    TelefoneAlertaFinanceiroViewSet, ContaPagarViewSet
│                                    (baixa/cancelar/resumo), ContaReceberViewSet (baixa/resumo),
│                                    DespesaRecorrenteViewSet (sem DELETE), SaldoConferidoViewSet
│                                    (só GET/POST), FluxoCaixaView. Todos aceitam
│                                    `?empresa=<id>`/`?empresa=todas`
├── manutencao/                  ← Backup do banco (pg_dump) + mídia (tarfile), envio pro Backblaze
│   │                               B2 via rclone + alerta de falha via WhatsApp (spec completa em
│   │                               backup.md)
│   ├── models.py                ← ConfiguracaoBackup (singleton), TelefoneAlertaBackup
│   ├── views.py                 ← ConfiguracaoBackupViewSet + TelefoneAlertaBackupViewSet
│   └── management/commands/
│       ├── fazer_backup.py      ← pg_dump -Fc + tarfile de media/ + rotação local + rclone pro B2
│       │                           + rotação remota — nunca notifica (sucesso ou falha)
│       └── verificar_backup.py  ← checa idade/tamanho do backup mais recente, alerta WhatsApp se
│                                   desatualizado/ausente/corrompido — sem dedup, decisão consciente
└── manage.py

arretado-crm/                    ← raiz React
└── src/
    ├── api/
    │   ├── client.js            ← axios base
    │   └── services.js          ← clientesApi, tagsApi, ifoodApi, pdvApi, pedidosApi, eventosApi,
    │                               locaisEventoApi, orcamentosApi, contratosApi, aditivosApi,
    │                               configContratoApi,
    │                               alertasEventoApi, notificacoesApi, usuariosApi (inclui
    │                               definirEmpresaAtiva/preferenciaTema), authApi (login/logout/me
    │                               + atualizarCache), fichasApi, taxasEntregaApi, configEntregaApi,
    │                               relatoriosApi, dashboardApi, auditoriaApi, presencaApi,
    │                               estoqueApi, financeiroApi, empresasApi, sistemaApi (versao)
    ├── utils/
    │   ├── auditoriaResumo.js   ← ACAO_LABEL/ACAO_COR/dataFmt/resumo — reusado pela aba
    │   │                           "Histórico" no modal de Orçamento/Evento
    │   └── tema.js              ← `aplicarCoresEmpresa(empresa)` (mapeia os 12 campos de cor pros
    │                               tokens CSS de index.css, sempre via setProperty/removeProperty),
    │                               `aplicarModoNeutro(modo)`, `aplicarTema()` — ver MULTIEMPRESA.md
    ├── hooks/
    │   └── useAuth.jsx          ← AuthProvider/useAuth — user (cache em localStorage, única
    │                               exceção do projeto) + login/logout + `empresas`/`empresaAtiva` +
    │                               `trocarEmpresa(id)`/`definirPreferenciaTema(tema)` + useEffect
    │                               que aplica tema/título/favicon sempre que `user` muda
    ├── pages/
    │   ├── Login.jsx            ← busca `empresasApi.brandingLogin()` no mount, aplica via
    │   │                           `aplicarCoresEmpresa()` — sem seletor, sempre tema da empresa
    │   │                           `padrao=True`
    │   ├── EscolherEmpresa.jsx  ← rota própria pós-login com 2+ empresas vinculadas, fora do
    │   │                           AppLayout (sem sidebar)
    │   ├── Dashboard.jsx        ← agrega dashboardApi.resumo() + clientesApi (recentes) · consome
    │   │                           `useAuth().empresaAtiva`/`empresas`, chip "Todas as empresas" ·
    │   │                           `matrizView` decide o layout (visão não-matriz esconde
    │   │                           PDV/Eventos e troca "A receber" por "Repasse iFood a receber")
    │   ├── Clientes.jsx / ClienteDetail.jsx / Tags.jsx
    │   ├── Usuarios.jsx         ← CRUD + permissões + checkbox de vínculo de empresa
    │   ├── IFood.jsx / PDV.jsx
    │   ├── CatalogoPDV.jsx      ← catálogo do PDV (gestão de produtos para venda)
    │   ├── Catalogo.jsx         ← catálogo geral (grid de cards, foto, segmento, canais)
    │   ├── FichasTecnicas.jsx   ← composição de ingredientes por produto
    │   ├── CentralPrecos.jsx    ← precificação (matérias, ajuste linear, semáforo, parâmetros)
    │   ├── Estoque.jsx          ← 4 abas: Insumos, Produtos, Produção, Movimentações + modais
    │   │                           Registrar Compra, Ajuste de Inventário, Configurações
    │   ├── Relatorios.jsx       ← 2 abas: "Por Canal (iFood)" (export Excel/PDF) e "Produtos Mais
    │   │                           Vendidos" (ranking cross-canal, só tela) · filtro "Empresa"
    │   ├── Financeiro.jsx       ← 5 abas: Contas a Pagar (+ Recorrentes), Contas a Receber, Fluxo
    │   │                           de Caixa, Categorias, Configurações · consome
    │   │                           `useAuth().empresaAtiva`/`empresas` (mesmo contexto global da
    │   │                           Sidebar — diferente do seletor local de IFood.jsx, anterior à
    │   │                           Fase 2 do multi-empresa)
    │   ├── Eventos.jsx / Orcamentos.jsx (botão "Emitir Contrato"; Eventos.jsx também tem "Emitir
    │   │                               Aditivo", só visível quando `evento.aditivo_disponivel`)
    │   ├── Locais.jsx           ← cadastro de LocalEvento
    │   ├── TaxasEntrega.jsx     ← taxas por bairro + frete padrão (ver FRETE.md)
    │   ├── Notificacoes.jsx / Configuracoes.jsx / Vinculacoes.jsx
    │   └── Empresas.jsx         ← lista + modal criar/editar (12 swatches de cor, upload de logos
    │                               + timbre), rota /empresas (Administração, role=admin) · seção
    │                               "Módulos visíveis no menu" (checkboxes de MODULOS_OCULTAVEIS)
    ├── components/
    │   ├── layout/
    │   │   ├── AppLayout.jsx
    │   │   ├── Sidebar.jsx      ← filtra `NAV` por `empresaAtiva.modulos_ocultos` — puramente
    │   │   │                      cosmético, `App.jsx` continua registrando todas as rotas
    │   │   ├── Topbar.jsx       ← topbar por página — projeto não tem chrome compartilhado além
    │   │   │                      da Sidebar
    │   │   ├── EmpresaSwitcher.jsx  ← pill no rodapé da Sidebar, só com 2+ empresas no contexto
    │   │   └── SeletorTema.jsx      ← segmented control de 3 ícones (empresa/claro/escuro), rodapé
    │   │                              da Sidebar, sempre visível
    │   └── ui/                  ← Btn, Modal, Spinner, Avatar etc. · PresencaAtiva.jsx (badge
    │                               "Fulano também está vendo isso agora", heartbeat a cada 15s)
    ├── index.css                ← tokens do design system (`:root`) — ver Padrões Obrigatórios
    ├── temas.css                ← blocos `:root[data-theme="neutro-claro"]`/`"neutro-escuro"` —
    │                               identidade do produto Ortex, não de cliente
    └── App.jsx                  ← rotas do frontend — inclui /escolher-empresa (fora do AppLayout)
```

---

## Padrões Obrigatórios

### Backend
- **`CsrfExemptMixin`** em todos os ViewSets (padrão estabelecido no projeto)
- **Canais de venda = apps Django separados** (`ifood/`, `pdv/`, futuramente `anotaai/`)
- **`PedidoUnificado` é espelho** — nunca escrito diretamente por views. Alimentado exclusivamente por signals (`post_save`) dos apps de canal
- **Signals dentro de try/except** — nunca falham o fluxo principal
- **Cron + management commands** em vez de Celery
- Número do pedido PDV: `PedidoPDV.proximo_numero()` — sequencial com zero-fill
- Itens do PDV: snapshot de nome e preço no momento da venda
- **Z-API WhatsApp:** configurado via `.env` (`ZAPI_INSTANCE_ID`, `ZAPI_TOKEN`, `ZAPI_CLIENT_TOKEN`) com fallback pro banco (`ConfiguracaoWhatsApp`). `notificacoes/zapi_client.py` resolve o número canônico via `phone-exists`, lança `ZAPIError`. Sempre usar `notificacoes/servico.py` (`notificar()`/`notificar_documento()`) — nunca chamar `zapi_client` direto em views ou signals
- **`ConfiguracaoWhatsApp` é singleton** — sempre via `.get()`. `GET/PATCH /notificacoes/configuracao/` exigem login (GET expõe credenciais Z-API em texto puro); PATCH audita `config_whatsapp_alterada` (credenciais mascaradas como `"***"` no log)
- **`fichas.ParametrosNegocio` é singleton** — sempre via `.get()`. `PATCH /fichas/parametros/1/` exige login e audita
- **`FichaTecnica` → `pdv.Produto`** é FK fraca via `produto_pdv_id` (IntegerField, não ForeignKey)
- **`SnapshotPrecos`** é gravado automaticamente antes de qualquer `AjusteLinear` com `confirmar=True`. Aplicar/desfazer exigem login e auditam; preview (`confirmar=false`) continua `AllowAny`
- **`pdv.ConfiguracaoEntrega` é singleton** — sempre via `.get()`. `PATCH /pdv/configuracao-entrega/1/` exige login e audita
- **`pdv.TaxaEntregaBairro`** é a tabela configurável de bairro→taxa usada por PDV e Orçamentos/Eventos. Nunca hardcodar frete — ver `FRETE.md`
- **`pdv.Produto.tipo`** (`fabricado`/`revenda`/`kit`) define de onde vem o custo (propriedade polimórfica): `fabricado` ← `FichaTecnica.custo_total_unitario`; `revenda` ← `materia_prima_origem.custo_unitario` (só preenchível se `tipo == 'revenda'`); `kit` soma `custo * quantidade` de cada `ItemKit`. `margem_desejada_pct` só sugere preço, nunca substitui `preco`
- **`pdv.ItemKit`** não pode conter kit-de-kit (`componente.tipo == 'kit'` rejeitado no model e no serializer)
- **`pdv.FaixaPreco`** guarda preço por quantidade mínima e canal opcional. `Produto.preco_para(quantidade, canal)` resolve: faixa do canal > faixa geral > `preco` base. Nunca hardcodar desconto no frontend
- **`pdv.DadosFiscaisProduto`** é opcional, aninhado e gravável via `ProdutoSerializer.dados_fiscais` — prepara NFC-e futura, ainda não consumido por integração fiscal real
- **Estoque** controla saldo físico de 3 naturezas: `MateriaPrima`, `Produto` fabricado (`modo_estoque`: `'estoque'` mantém saldo via `Producao`, `'sob_encomenda'` debita insumo direto na venda) e `Produto` revenda (sempre `'estoque'`). Kit nunca tem saldo próprio — sempre virtual, decrementa `ItemKit` recursivamente. **Política de saldo negativo: sempre permitido** — nenhuma venda/produção/ajuste é bloqueada por saldo insuficiente, o sistema só alerta
- **`estoque.MovimentoEstoque` é o ledger — fonte única da verdade.** Todo movimento passa por `MovimentoEstoque.registrar()` (nunca `.objects.create()` direto), que valida exatamente 1 de `materia_prima`/`produto`, calcula `saldo_posterior` dentro de `transaction.atomic()` com `select_for_update()`. `tipo_movimento='ajuste_inventario'` é o único caso onde `quantidade` é o saldo absoluto, não delta. `registrar()` quantiza `quantidade` (3 casas) e `custo_unitario_snapshot` (4 casas) antes de gravar — sem isso, `full_clean()` derruba o movimento com `ValidationError` quando o consumo calculado sai com mais casas decimais do que o `DecimalField` aceita
- **`estoque.Producao.executar()`** só é permitida quando a `FichaTecnica` tem `produto_pdv_id` vinculado a um Produto com `modo_estoque == 'estoque'` — debita insumo proporcionalmente e credita o produto, tudo via `MovimentoEstoque.registrar()` na mesma transação
- **Débito Automático de Estoque** (`estoque/signals.py`, `EstoqueConfig.ready()`) — 3 signals `post_save` (sender como string): `PedidoPDV` em `'confirmado'`; `PedidoIFood` em `'CONFIRMED'` (match por nome via fuzzy `iexact`→`icontains`, sem correspondência só loga warning); `Evento` em `'entregue'`. Todos checam `MovimentoEstoque.objects.filter(origem_tipo=..., origem_id=...).exists()` antes de debitar — idempotência obrigatória (`post_save` dispara em todo `.save()`). Estorno automático em cancelamento pós-débito é fora de escopo (ajuste manual de inventário cobre o caso)
- **Alertas de Estoque Baixo** (`ConfiguracaoEstoque.get()`, `TelefoneAlertaEstoque`, `AlertaEstoqueEnviado`) — cron diário `alertar_estoque_baixo` notifica só telefones internos sobre item com `quantidade_estoque < estoque_minimo`
- **Importação de Nota Fiscal** — `POST /api/v1/estoque/notas/` (é o `create()` padrão, **não** `/notas/importar/`) roda a cascata `extrair_xml()` → `extrair_texto_pdf()` → `extrair_ia()` (`estoque/claude_client.py`, precisa de `ANTHROPIC_API_KEY`). Cada camada devolve `None` em vez de lançar exceção; se as 3 falharem, `metodo_extracao='falhou'` e a revisão é manual. Cada camada também captura `fornecedor_cnpj`/`fornecedor_nome` do emitente. Fuzzy match de `resolver_materia_prima()` **nunca cria `MateriaPrima` automaticamente** — sempre marca `status_match='revisar'`. `ImportacaoNotaFiscal`/`ItemNotaImportada` são staging — nenhum `MovimentoEstoque` é gravado até `POST /notas/{id}/confirmar/`, que rejeita (400) item pendente de revisão
- **Nota Fiscal → ContaPagar** (`ImportacaoNotaFiscalViewSet._gerar_conta_pagar_da_nota()`, chamado depois de `confirmar()` já gravar os movimentos) — se `ConfiguracaoFinanceira.get().nota_gera_conta_pagar`, cria `ContaPagar` (`origem='nota_fiscal'`, `OneToOneField` pra `ImportacaoNotaFiscal`) com `categoria=None` sempre (extração não determina categoria contábil — usuário categoriza depois via PATCH). Fornecedor resolvido por CNPJ exato → nome `iexact` → nome `icontains` (só resultado único) → cria novo; sem nome/CNPJ, `fornecedor=None`
- **`estoque.ConfiguracaoIA`** é singleton — `extracao_ia_ativa`/`modelo`/`timeout_segundos`. `ANTHROPIC_API_KEY` nunca fica no model/banco, só em variável de ambiente (key da Ortex)
- **`eventos.ConfiguracaoContrato` é singleton** — sempre via `.get()`. Nunca hardcodar cláusula numérica no gerador de PDF — ver `Contrato.md`. `PATCH` exige login e audita
- **`eventos.Contrato`** é snapshot gravado na emissão — valores nunca recalculados ao reabrir
- **Alertas de Evento** (`ConfiguracaoAlertaEvento.get()`, `TelefoneAlertaEvento`, `AlertaEventoEnviado`) — cron diário `alertar_eventos`: (1) pagamento pendente a partir de `dias_antes_pagamento` dias antes (usa `F()` em queryset, não a property Python `saldo_restante`); (2) aviso de entrega a partir de `dias_antes_entrega`, só `tipo_entrega='entrega_local'`. Repetem por `repetir_*_dias`, controlado por `AlertaEventoEnviado`. Texto fixo no código, só dias/intervalo/telefones configuráveis. Nunca notificar o cliente, só a equipe
- **Emissão de contrato** (`POST /eventos/orcamentos/{id}/gerar-contrato/`) só com `Orcamento.status == 'aprovado'` e exige CPF/RG/nacionalidade/profissão/estado civil do cliente — ver `Contrato.md`. Exige login e audita `contrato_emitido`. `POST /eventos/{id}/gerar-contrato/` (`EventoViewSet`) reemite um Contrato NOVO com os dados ATUAIS do evento (nunca substitui o existente) — útil quando o evento já divergiu do orçamento que o gerou
- **`eventos.AditivoContrato`** (spec completa em `Contrato.md` § 9) — snapshot imutável emitido quando um Evento com Contrato já emitido tem valor/itens alterados a pedido do cliente antes do evento acontecer (`POST /eventos/{id}/gerar-aditivo/`, exige login, audita `aditivo_emitido`). Rejeita (400) evento sem contrato, evento `cancelado`/`entregue`, ou quando `Evento.valor_total` não mudou desde o contrato/último aditivo (`_valor_referencia_contrato()` — nunca comparar direto contra `Contrato.valor_total`, tem que considerar o último aditivo já emitido). Nunca reler itens/totais ao vivo do Evento pra reimprimir um aditivo já emitido — sempre do `itens_snapshot`/campos `*_novo` gravados nele. `AditivoContratoViewSet` só leitura + `pdf/`/`enviar-whatsapp/` (audita `aditivo_enviado`), mesmo padrão de `ContratoViewSet`
- **`eventos.ImagemInspiracao`** — galeria interna (nunca no PDF/WhatsApp), FK opcional a `Orcamento` OU `Evento` (`CheckConstraint` garante exatamente um). Quando o Evento tem `orcamento_origem`, imagem nova vai pro **Orçamento** de origem, nunca duplica a galeria — `EventoViewSet.adicionar_imagens`/`EventoDetailSerializer.get_imagens_inspiracao` resolvem a mesma regra
- **`MEDIA_URL`/`MEDIA_ROOT`** configurados em `config/settings.py` (`/media/`). Nginx tem `location /media/` próprio — qualquer novo `ImageField`/`FileField` já reaproveita essa infra
- **Cuidado com `prefetch_related` + criação de objeto relacionado na mesma request**: se uma view faz `get_object()` sobre queryset com `prefetch_related('algo')` e cria/deleta relacionado via `Model.objects.create(fk=obj, ...)` (sem passar pelo manager `obj.algo`), o cache do prefetch fica stale e `recalcular_totais()`/serializer leem o valor velho — **persistindo** total errado no banco, não só exibindo errado. Sempre chamar `obj.refresh_from_db()` antes de serializar (já corrigido em várias actions de item/imagem/pagamento — bug real recorrente, checar sempre que criar endpoint novo que recalcula total a partir de coleção prefetched)
- **`FichaTecnica.custo_ingredientes`** usa `sum(..., Decimal('0'))` com `start` explícito — nunca tirar. `sum()` de iterável vazio devolve `int 0`, e `0 / rendimento` em Python 3 é *true division* (vira `float`), que explode `TypeError` ao somar com `Decimal` (bug real já corrigido)
- **`auditoria.mixins.AuditoriaDestroyMixin`** — usar em qualquer novo `ModelViewSet` com DELETE auditado (traduz `ProtectedError` em 400 amigável). Combinar com `TokenAuthentication` + `IsAuthenticated` na action `destroy`
- **`AuditoriaCreateMixin`/`UpdateMixin`/`StatusMixin`** — hoje só em `OrcamentoViewSet`/`EventoViewSet`. Para usar `UpdateMixin` num `update()` já customizado, a view precisa chamar `self.perform_update(serializer)` em vez de `serializer.save()` direto. `StatusMixin.log_mudanca_status()` não é automático — chamar manualmente após cada `.save()` de mudança de status
- **`auditoria.PresencaEdicao`** é polling REST (não WebSocket — projeto roda só Gunicorn/WSGI síncrono, sem Channels/Redis/ASGI). Só informativo, não é trava/lock de edição
- **`ifood.ConfiguracaoIFood` não é singleton de verdade** (`.objects.first()`) — `destroy()` sempre bloqueado (405), pra nunca perder credencial de produção
- **`eventos.PagamentoEvento`** — `comprovante` é `FileField` opcional (multipart). `Evento.sinal_pago` **nunca** é gravado direto — sempre via `recalcular_sinal_pago()`. O sinal informado na criação/conversão vira um `PagamentoEvento` inicial, não seta o campo diretamente
- **Edição de Orçamento**: `update()` só permite PATCH/PUT quando `status` é `rascunho`/`enviado` — depois é imutável (mesma filosofia de `Contrato`)
- **Brindes e Permutas** (spec completa em `BRINDES_PERMUTAS.md`, feature completa) — campo `natureza` (`venda`/`brinde`/`permuta`, default `venda`) em `ItemOrcamento`/`ItemEvento`/`ItemPedidoPDV`, granularidade por item. `save()` zera `preco_total` quando `natureza != 'venda'`, `preco_unit` continua o preço de tabela (referência riscada no PDF). `recalcular_totais()` dos 3 já soma sem filtro — efeito cascateia sozinho. `converter_em_evento` propaga `natureza` — sem isso, brinde vira venda cobrada no evento. `financeiro/signals.py` tem guard de valor `<= 0`. `ProdutosMaisVendidosView` filtra `natureza='venda'` em PDV/Eventos (iFood não tem o campo). PDFs mostram o item com rótulo + preço riscado, nunca omitem a linha. Ao somar `preco_total` em `create()` de serializer com itens aninhados, sempre usar `item.preco_total` (valor persistido pelo `save()`), nunca uma variável local `preco_unit * quantidade` (bug real já corrigido em `eventos/serializers.py`)
- **Resumo de Cozinha** (`GET /eventos/{id}/resumo-cozinha/`) — ver `eventos/pdf_resumo_cozinha.py` acima. `EventoListSerializer.n_imagens_inspiracao` existe só pra o frontend decidir se pergunta "incluir imagens?" antes de imprimir
- **Criação/edição/status/item de Orçamento e Evento exigem login** — único motivo é garantir que sempre exista um ator no log de auditoria; `converter_em_evento`/`enviar_whatsapp` continuam `AllowAny` (oportunistas)
- **`dashboard/` é um app só-leitura, sem models** — `DashboardResumoView` só agrega dados que já existem em `pedidos.PedidoUnificado` e `eventos.Evento`/`PagamentoEvento`. A receita de **Eventos** no dia vem exclusivamente de `PagamentoEvento` pago com `data_pagamento` de hoje — nunca de `Evento.valor_total` nem status de entrega. Já `ticket_medio.eventos` é a exceção (usa `valor_total` dos entregues nos últimos 30 dias)
- **`relatorios.ProdutosMaisVendidosView`** — ranking cross-canal (iFood+PDV+Eventos), só venda de fato concretizada (exclui Orçamentos, que são cotação). Agrupa por nome normalizado (`unicodedata`), nunca por `pdv.Produto` (iFood não tem FK pra Produto). Só JSON, sem export
- **`relatorios.RelatorioEventosView`** — lista de `Evento` no período (todos os status, sem excluir `cancelado` — o usuário decide o que fazer com eles na tela/export) + resumo + agrupado por dia/mês, mesmo padrão de export Excel/PDF do `RelatorioIFoodView`. Filtra por `Evento.data_evento` (não `criado_em`). "Valor recebido" é sempre `Evento.sinal_pago` (campo já derivado via `recalcular_sinal_pago()`) — nunca soma ao vivo de `PagamentoEvento` nem `Evento.valor_total`. Eventos é mono-empresa (sem FK própria) — usa o mesmo gate `mono_empresa_habilitado = empresa is None or empresa.padrao` de `ProdutosMaisVendidosView`, devolvendo queryset vazia quando a empresa resolvida não é a matriz
- **Módulo Financeiro** (spec completa em `FINANCEIRO.md`) — `ContaPagar`/`ContaReceber` são obrigação projetada; `MovimentoFinanceiro` é o ledger, fonte única da verdade. **Nenhum valor hardcoded** — `CategoriaFinanceira` nasce vazia
- **Financeiro por empresa** (ver `MULTIEMPRESA.md`) — `ContaBancaria`/`ContaPagar`/`ContaReceber`/`DespesaRecorrente` têm FK `empresa` (PROTECT). `ConfiguracaoFinanceira.get(empresa)` — argumento obrigatório, não é mais singleton global. `MovimentoFinanceiro.empresa` é property (`self.conta.empresa`), nunca denormalizar. `CategoriaFinanceira`/`Fornecedor`/`TelefoneAlertaFinanceiro` continuam compartilhados. Sinais de venda resolvem a config da empresa certa (PDV/PagamentoEvento sempre `Empresa.get_padrao()`; iFood usa `pedido.empresa`). Todos os ViewSets aceitam `?empresa=<id>`/`?empresa=todas` via `_resolver_empresa()` (duplicado por app, nunca importado entre apps)
- **`financeiro.MovimentoFinanceiro` é o ledger — fonte única da verdade.** Sempre via `MovimentoFinanceiro.registrar()`, mesmo contrato de `MovimentoEstoque.registrar()`. `UniqueConstraint(origem_tipo, origem_id)` condicional (só `pdv`/`ifood`/`evento_pagamento`) garante idempotência dos signals de venda; baixas de conta e `manual` ficam fora. **Nunca implementar DELETE** — ledger imutável, corrige com movimento manual inverso
- **`financeiro.ContaPagar`** — `valor_pago`/`status` só via `recalcular_valor_pago()`. `cancelar/` só com `valor_pago == 0`. PATCH só com `status == 'pendente'`. `recorrente` é `read_only` — só o cron grava. **Cuidado com ordem de operações na migration**: quando o autodetector gera `AddConstraint` referenciando campo que só existe depois de um `AddField` posterior na mesma migration, ele pode ordenar errado (`FieldDoesNotExist` ao migrar) — sempre conferir a ordem das `operations` quando `makemigrations` cria constraint condicional sobre campo novo
- **`financeiro.ContaReceber`** — só existe pra iFood modo `repasse` ou lançamento manual. `canal` é read-only na API. **Eventos e PDV nunca materializam `ContaReceber`** — saldo de Eventos é sempre dinâmico (`valor_total - sinal_pago`)
- **`financeiro.DespesaRecorrente`** — molde de despesa mensal, `dias_vencimento` JSONField, dia inexistente no mês cai no último dia (nunca rola pro mês seguinte). Sem DELETE — pausar via `ativo=False`
- **`financeiro.ConfiguracaoFinanceira` é singleton por empresa** — sempre via `.get(empresa)`. `conta_padrao_vendas` é o destino dos movimentos automáticos — sem configurar, o signal loga warning e não grava (nunca cria `ContaBancaria` sozinho)
- **Baixa de `ContaPagar`/`ContaReceber`** exige login, cria `MovimentoFinanceiro` + recalcula. Rejeita valor maior que o saldo restante e conta já quitada/cancelada
- **`POST /financeiro/movimentos/manual/`** — único jeito de criar movimento fora dos signals/baixas. Sempre `origem_tipo='manual'`, chama `registrar()` normalmente
- **`GET /financeiro/fluxo-caixa/?dias=N`** (N 1-90) — agregador: realizado do ledger + projetado de `ContaPagar`/`ContaReceber` pendente/parcial + saldos por conta. **Não inclui saldo dinâmico de Evento** (diferente de `contas-receber/resumo/`)
- **Módulo de Backup** (spec completa em `backup.md`) — cron `fazer_backup` (pg_dump + tarfile + rclone pro B2), cron `verificar_backup` alerta sem dedup (decisão consciente — backup quebrado é o único problema invisível até precisar dele). `fazer_backup` nunca notifica. **Restauração é sempre manual**, nunca management command — ver `backup.md` para os comandos de `pg_restore`/`tar`
- **Multi-Empresa** (spec completa em `MULTIEMPRESA.md`, 6 fases — 0-5 implementadas e deployadas, falta só cadastrar a MANGAIO) — `empresas.Empresa` é multi-tenant por linha (FK `empresa`, mesmo banco), nunca schema separado. Exatamente uma `Empresa` tem `padrao=True`, sempre via `Empresa.get_padrao()`. `EmpresaViewSet` sem DELETE/PUT. Credencial de ação de pedido iFood sempre resolvida por `ConfiguracaoIFood.objects.filter(empresa=pedido.empresa)`, nunca `.first()`. `Empresa.modulos_ocultos` é puramente cosmético (Sidebar), nunca controle de acesso. Login nunca bloqueia por falta de vínculo de empresa — cai na empresa padrão via `_empresas_efetivas()`
- **Versão do Sistema** (`config/versao.py`) — sempre derivada do Git (`git describe --tags --always --dirty`), nunca mantida à mão. Cada release: tag anotada `vX.Y.Z` + entrada no `CHANGELOG.md`, sempre juntos. Requer `git config --system --add safe.directory /var/www/crm_arretado` (já aplicado em prod) — sem isso, `obter_versao()` cai silenciosamente no fallback `'desconhecida'`

### Frontend
- **Sem `localStorage`** — estado React + context de autenticação *(exceção: `authApi` usa localStorage para sessão)*
- **CSS Modules** — cada página tem seu `.module.css`
- **Variáveis CSS do design system** (`src/index.css`):
  - `--caramelo`/`--caramelo-light`/`--caramelo-pale` (+ `--caramelo-rgb`, `--caramelo-texto`) → cor primária
  - `--bg`/`--bg-alt` → background · `--surface`/`--surface-raised`/`--surface-hover` → cards/tabelas
  - `--border`/`--border-strong`/`--border-accent` → bordas
  - `--texto`/`--texto-sec`/`--texto-muted`/`--texto-faint` → hierarquia de texto
  - `--verde` → positivo · `--danger`/`--warning` → estado (+ `-rgb`)
  - Tema de empresa (ver `MULTIEMPRESA.md`): `--status-{ok,alerta,critico}-{bg,fg}`, badges de canal
    `--canal-{ifood,pdv,eventos}-{bg,fg}`, badges de marca `--badge-{ifood,anotaai}-{bg,fg}` e
    `--whatsapp*` (**nunca** seguem tema de empresa/neutro — identidade de terceiro fixa), tokens de
    sidebar `--sidebar-{bg,border,texto,texto-mut,ativo,ativo-bg}`, `--font-display`/`--font-body`
  - **Nunca perseguir 100% dos hex hardcoded restantes** nos CSS Modules — decisão consciente, só
    converter duplicatas exatas de token já existente; revisitar só se algo ficar ilegível no escuro
- **Sistema de Temas** (ver `MULTIEMPRESA.md`) — três modos, persistidos em `Usuario.preferencia_tema`
  (nunca `localStorage`): **Empresa** (default, `aplicarCoresEmpresa()` — campo vazio sempre
  `removeProperty`, nunca só "pula"), **Claro**/**Escuro** (`data-theme`, paletas estáticas Ortex em
  `temas.css`). Setar cor/tema só via `utils/tema.js`, nunca `document.documentElement.style` direto
  em componente novo
- **Tipografia:** tema de empresa → `'Playfair Display'` em títulos, `'DM Sans'` no corpo · temas neutros → `'Inter'` nos dois
- **Ícones:** Tabler Icons (`ti ti-*`)
- **`services.js`:** um objeto de API por canal — novo canal = novo objeto seguindo o mesmo padrão
- **Busca de cliente CRM**: input com debounce 350ms → `clientesApi.list({ search })` → dropdown → chip com X pra limpar. Nunca `<select>` com todos os clientes pré-carregados
- **Upload de arquivo/imagem via axios**: `api/client.js` fixa `Content-Type: application/json`, não sobrescrito automaticamente com `FormData` — sempre passar `{ headers: { 'Content-Type': undefined } }` na chamada, senão o backend recebe `request.FILES` vazio
- **Lightbox de imagem ampliada**: overlay `position: fixed` (z-index 400, acima do Modal 200), `object-fit: contain`, fecha no clique fora/X — reaproveitar pra qualquer nova galeria
- **Confirmação antes de enviar WhatsApp**: todo `handleEnviar*` abre `window.confirm()` com nome/telefone antes de chamar a API
- **Modal de emitir contrato não fecha sozinho após gerar** — `onGerado` só recarrega, nunca fecha o modal (o usuário fecha explicitamente depois de ver o PDF)
- **Gráfico divergente** (entrada acima/saída abaixo de uma linha base, `Financeiro.jsx` aba Fluxo de Caixa) — reaproveita a estrutura de barra empilhada do gráfico 7 dias do Dashboard, realizado (cor sólida) × projetado (mesma cor, opacity reduzida) — identidade por cor, realizado×projetado por opacidade, nunca o contrário. Reusar em vez de introduzir lib de gráficos nova
- **Teste manual de UI grava no banco de produção** — este projeto não tem banco de dev/staging separado (Vite fala com o Django/Postgres real). Usar prefixo `"TESTE "` e **sempre limpar depois** (via Django shell quando o endpoint não tem DELETE). Confirmar com o usuário antes de `migrate` + `systemctl restart arretado` num app recém-deployado

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
| Orçamentos | Orçamentos pré-evento (ORC-0001) + conversão em Evento + WhatsApp | ✅ Concluída |
| Fase 5 | Dashboard e relatórios | ✅ Concluída (`Dashboard.jsx`) |
| WhatsApp | Notificações via Z-API | ✅ Concluída |
| Usuários | Gestão de usuários + RBAC | ✅ Concluída |
| Catálogo & Precificação | App `fichas/` + 3 telas | ✅ Concluída · dados importados em prod |
| Catálogo — Revenda/Kit/Faixas de Preço | `Produto.tipo`, `ItemKit`, `FaixaPreco`, `DadosFiscaisProduto` | ✅ Concluída |
| Frete por Bairro | Taxa por bairro no PDV/Orçamentos/Eventos + Locais de Evento | ✅ Concluída (ver `FRETE.md`) |
| Relatórios | Relatório consolidado iFood (resumo, agrupamento, export) | ✅ Concluída (só iFood por enquanto) |
| Produtos Mais Vendidos | Ranking cross-canal por quantidade/valor | ✅ Concluída (só JSON) |
| Contrato | Emissão a partir de Orçamento aprovado + reenvio WhatsApp | ✅ Concluída (ver `Contrato.md`) |
| Aditivo de Contrato | Documenta alteração de valor/itens de Evento com Contrato já emitido, antes do evento acontecer | ✅ Concluída (14/set/2026, ver `Contrato.md` § 9) |
| Imagens de Inspiração | Galeria anexada ao Orçamento OU Evento | ✅ Concluída |
| Pagamentos Parciais de Evento | `PagamentoEvento`, `sinal_pago` derivado | ✅ Concluída |
| Dashboard Multi-Canal | App `dashboard/` (só leitura) | ✅ Concluída |
| Autenticação Real + Auditoria | Token real + app `auditoria/` cobrindo os itens críticos | ✅ Concluída |
| Auditoria de Criação/Edição/Status + Presença + Histórico no Modal | Extensão da auditoria + heartbeat de presença + aba Histórico | ✅ Concluída |
| Alertas de Evento | Pagamento pendente / entrega próxima via WhatsApp | ✅ Concluída |
| Estoque — Fases 1-5 | Modelos base, entrada/ajuste, produção, débito automático, alertas | ✅ Concluída |
| Estoque — Fases 6-8 | Importação de nota fiscal (XML/PDF/IA) | ✅ Concluída |
| Resumo de Cozinha | PDF operacional A4, `observacoes_cozinha`, folha de imagens opcional | ✅ Concluída |
| Módulo Financeiro | Fases 0-7 de 8 (ver `FINANCEIRO.md`) | 🔄 Falta só a Fase 8 (testes finais) |
| Sistema de Backup | App `manutencao/` (ver `backup.md`) | ✅ Concluída (fases 1-5) |
| Multi-Empresa + Temas | Fases 0-5 de 6 (ver `MULTIEMPRESA.md`) | 🔄 Deployado 24/ago/2026 (v1.5.0) — falta só cadastrar a MANGAIO |
| Brindes e Permutas | Campo `natureza` por item, 5 de 5 fases (ver `BRINDES_PERMUTAS.md`) | ✅ Concluída (v1.5.1) |

---

## Pendências Ativas

1. **Anota AI (Fase 3-ext-B)** — criar app `anotaai/` seguindo o padrão de `pdv/`
2. **Fichas técnicas incompletas** — alguns ingredientes com custo zero/sem quantidade na planilha original
3. **PDV Hardware (roadmap):** impressora térmica ESC/POS + caixa registradora (curto prazo) · NFC-e SEFAZ-PI (médio prazo) · TEF integrado (longo prazo)
4. **Relatório de canal (`RelatorioIFoodView`) cobre só iFood** — expandir pra PDV. Eventos já ganhou relatório próprio (`RelatorioEventosView`, 17/set/2026). (`ProdutosMaisVendidosView` já cobre os 3 canais — pendência diferente, falta só export Excel/PDF nesse)
5. **Logging/observabilidade rudimentar** — sem `LOGGING` dict/Sentry, sem persistência em arquivo (tudo no stdout do Gunicorn, só via `journalctl`). Considerar `RotatingFileHandler` e/ou Sentry
6. **Divergência de receita "hoje" entre o card iFood do Dashboard e o menu iFood** — causa raiz identificada, correção pendente de decisão do usuário. Ver `IFOOD_RECEITA_DASHBOARD.md`
7. **Variáveis de ambiente em prod para WhatsApp (Z-API)** — `ZAPI_INSTANCE_ID`/`ZAPI_TOKEN`/`ZAPI_CLIENT_TOKEN` já configuradas
8. **`ANTHROPIC_API_KEY` não configurada em produção** — fallback de IA da importação de nota fiscal cai sempre em `metodo_extracao='falhou'` sem ela (key da Ortex, decisão de negócio)
9. **Cascata "texto de PDF" é heurística best-effort** — sem notas reais de fornecedores pra calibrar o regex, pode não reconhecer DANFEs complexos (cai pra IA automaticamente, nunca trava o fluxo)

---

## Endpoints Principais

```
# Versão do Sistema
GET /api/v1/versao/    ← AllowAny · {versao, commit, commit_data, branch}, derivado de `git describe`

# Clientes
GET/POST             /api/v1/clientes/
GET/PUT/PATCH/DELETE /api/v1/clientes/{id}/        ← DELETE exige login · audita registro_excluido
GET                  /api/v1/clientes/{id}/historico/
GET/POST             /api/v1/tags/                 ← DELETE (/{id}/) exige login · audita registro_excluido

# iFood (multi-empresa — ver MULTIEMPRESA.md)
GET  /api/v1/ifood/pedidos/                       ← aceita ?empresa=<id> (sem parâmetro: todas as empresas)
GET  /api/v1/ifood/pedidos/estatisticas/          ← aceita ?empresa=<id> (default: Empresa.get_padrao())
POST /api/v1/ifood/pedidos/{id}/confirmar/
POST /api/v1/ifood/pedidos/{id}/vincular-cliente/
GET  /api/v1/ifood/config/status/                 ← aceita ?empresa=<id>
DELETE /api/v1/ifood/config/{id}/   ← sempre bloqueado (405) — não é singleton de verdade

# PDV
GET/POST /api/v1/pdv/pedidos/                       ← DELETE (/{id}/) exige login · itens aceitam "natureza" (venda/brinde/permuta, default venda)
GET/POST /api/v1/pdv/produtos/                       ← DELETE (/{id}/) exige login
GET/POST /api/v1/pdv/categorias/                     ← DELETE (/{id}/) exige login
POST     /api/v1/pdv/pedidos/{id}/confirmar/
POST     /api/v1/pdv/pedidos/{id}/concluir/
POST     /api/v1/pdv/pedidos/{id}/itens/
DELETE   /api/v1/pdv/pedidos/{id}/itens/{item_id}/remover/            ← exige login

# Catálogo — tipo de produto, faixas de preço e dados fiscais
GET    /api/v1/pdv/produtos/{id}/preco/?quantidade=&canal=        ← Produto.preco_para()
POST   /api/v1/pdv/produtos/{id}/faixas-preco/
PATCH  /api/v1/pdv/produtos/{id}/faixas-preco/{faixa_id}/
DELETE /api/v1/pdv/produtos/{id}/faixas-preco/{faixa_id}/remover/ ← exige login
POST   /api/v1/pdv/produtos/{id}/itens-kit/                       ← só quando produto.tipo == 'kit'
DELETE /api/v1/pdv/produtos/{id}/itens-kit/{item_id}/             ← exige login
                                                                    ← dados_fiscais aninhado, gravável no PATCH de /pdv/produtos/{id}/

# Frete (ver FRETE.md)
GET/POST/PATCH/DELETE /api/v1/pdv/taxas-entrega/[{id}/]     ← DELETE exige login
GET/PATCH             /api/v1/pdv/configuracao-entrega/1/   ← singleton, PATCH exige login

# Orçamentos
GET/POST      /api/v1/eventos/orcamentos/                               ← POST exige login
GET/PATCH/DELETE /api/v1/eventos/orcamentos/{id}/                       ← PATCH só rascunho/enviado · DELETE exige login (400 se tiver Contrato — PROTECT)
POST          /api/v1/eventos/orcamentos/{id}/enviar/
POST          /api/v1/eventos/orcamentos/{id}/aprovar/
POST          /api/v1/eventos/orcamentos/{id}/recusar/
POST          /api/v1/eventos/orcamentos/{id}/restaurar/
POST          /api/v1/eventos/orcamentos/{id}/converter-em-evento/      ← body opcional "sinal_pago" · AllowAny (oportunista)
POST          /api/v1/eventos/orcamentos/{id}/itens/                    ← aceita "natureza"
PATCH         /api/v1/eventos/orcamentos/{id}/itens/{item_id}/editar/   ← só rascunho/enviado
DELETE        /api/v1/eventos/orcamentos/{id}/itens/{item_id}/remover/
POST          /api/v1/eventos/orcamentos/{id}/imagens/                  ← multipart, campo "imagens"
DELETE        /api/v1/eventos/orcamentos/{id}/imagens/{imagem_id}/remover/
GET           /api/v1/eventos/orcamentos/{id}/pdf/
GET           /api/v1/eventos/orcamentos/{id}/historico/                ← trilha de auditoria (não confundir com clientes/{id}/historico/)
POST          /api/v1/eventos/orcamentos/{id}/enviar-whatsapp/   ← AllowAny (oportunista)
POST          /api/v1/eventos/orcamentos/{id}/gerar-contrato/    ← só status='aprovado' · body: cpf/rg/rg_orgao_emissor/nacionalidade/profissao/estado_civil/endereco_avulso

# Contratos (ver Contrato.md)
GET           /api/v1/eventos/contratos/
GET           /api/v1/eventos/contratos/{id}/
GET           /api/v1/eventos/contratos/{id}/pdf/
POST          /api/v1/eventos/contratos/{id}/enviar-whatsapp/    ← não trava por status (envio inicial e reenvio)
POST          /api/v1/eventos/{id}/gerar-contrato/               ← EventoViewSet — reemite com dados atuais do evento
GET/PATCH     /api/v1/eventos/configuracao-contrato/1/           ← singleton

# Aditivo de Contrato (ver Contrato.md § 9)
POST          /api/v1/eventos/{id}/gerar-aditivo/                ← exige login · 400 sem_contrato/evento_cancelado/evento_entregue/sem_alteracao
GET           /api/v1/eventos/aditivos/
GET           /api/v1/eventos/aditivos/{id}/
GET           /api/v1/eventos/aditivos/{id}/pdf/
POST          /api/v1/eventos/aditivos/{id}/enviar-whatsapp/     ← exige login

# Alertas de Evento
GET/PATCH             /api/v1/eventos/configuracao-alertas/1/       ← singleton
GET/POST              /api/v1/eventos/telefones-alerta/             ← telefones internos, não é o cliente
GET/PATCH/DELETE      /api/v1/eventos/telefones-alerta/{id}/        ← DELETE exige login

# Eventos
GET/POST              /api/v1/eventos/                                  ← aceita "sinal_pago" opcional
GET/PUT/PATCH/DELETE  /api/v1/eventos/{id}/
GET/POST              /api/v1/eventos/locais/
GET/PATCH/DELETE      /api/v1/eventos/locais/{id}/
DELETE                /api/v1/eventos/{id}/itens/{item_id}/remover/
POST                  /api/v1/eventos/{id}/itens/                       ← aceita "natureza"
POST                  /api/v1/eventos/{id}/confirmar/
POST                  /api/v1/eventos/{id}/iniciar-producao/
POST                  /api/v1/eventos/{id}/marcar-pronto/
POST                  /api/v1/eventos/{id}/entregar/
POST                  /api/v1/eventos/{id}/cancelar/
POST                  /api/v1/eventos/{id}/pagamentos/                  ← multipart opcional, campo "comprovante"
DELETE                /api/v1/eventos/{id}/pagamentos/{pagamento_id}/remover/
POST                  /api/v1/eventos/{id}/imagens/                       ← multipart, AllowAny, qualquer status
DELETE                /api/v1/eventos/{id}/imagens/{imagem_id}/remover/
GET                   /api/v1/eventos/{id}/historico/                    ← trilha de auditoria
GET                   /api/v1/eventos/{id}/resumo-cozinha/               ← AllowAny · ?imagens=1 inclui folha separada
GET                   /api/v1/eventos/agenda/

# Notificações WhatsApp
GET  /api/v1/notificacoes/mensagens/
POST /api/v1/notificacoes/mensagens/enviar/
GET  /api/v1/notificacoes/mensagens/status-conexao/
GET/PATCH /api/v1/notificacoes/configuracao/          ← singleton · GET e PATCH exigem login (só aqui GET também restrito)
POST      /api/v1/notificacoes/configuracao/testar/

# Usuários (ver MULTIEMPRESA.md)
GET/POST              /api/v1/usuarios/                  ← aceita "empresas_ids" no POST/PATCH
GET/PUT/PATCH/DELETE  /api/v1/usuarios/{id}/
POST                  /api/v1/usuarios/login/           ← AllowAny — devolve token + empresas/empresa_ativa/preferencia_tema "efetivos"
POST                  /api/v1/usuarios/logout/
POST                  /api/v1/usuarios/{id}/redefinir-senha/
POST                  /api/v1/usuarios/definir-empresa-ativa/  ← body {"empresa": id} · admin ativa qualquer empresa
POST                  /api/v1/usuarios/preferencia-tema/       ← body {"tema": ...} · não audita

# Auditoria (restrito a role=admin)
GET /api/v1/auditoria/logs/   ← query params: usuario, acao, model, data_inicio, data_fim

# Presença (heartbeat — qualquer usuário logado)
POST /api/v1/auditoria/presenca/   ← body {"model", "objeto_id"} · janela de 40s

# Catálogo / Fichas / Precificação
GET/POST         /api/v1/fichas/materias-primas/
PATCH/DELETE     /api/v1/fichas/materias-primas/{id}/
POST             /api/v1/fichas/materias-primas/{id}/atualizar-preco/
GET/POST         /api/v1/fichas/fichas/
GET/PATCH/DELETE /api/v1/fichas/fichas/{id}/
GET              /api/v1/fichas/fichas/{id}/resumo/
POST             /api/v1/fichas/fichas/{id}/adicionar-item/
DELETE           /api/v1/fichas/fichas/{id}/remover-item/{item_id}/
GET/PATCH        /api/v1/fichas/parametros/1/
POST             /api/v1/fichas/ajuste-linear/                         ← exige login só quando "confirmar":true
POST             /api/v1/fichas/desfazer-ajuste/{snapshot_id}/
GET              /api/v1/fichas/snapshots/

# Estoque
GET              /api/v1/estoque/movimentos/                    ← só leitura · filtros: materia_prima, produto, tipo_movimento, origem_tipo, data_inicio, data_fim
POST             /api/v1/estoque/compras/registrar/
POST             /api/v1/estoque/ajuste-inventario/              ← saldo_contado é absoluto, não delta
GET/POST         /api/v1/estoque/producoes/
GET              /api/v1/estoque/producoes/preview/
GET/PATCH        /api/v1/estoque/configuracao/1/
GET/POST         /api/v1/estoque/telefones-alerta/
GET/PATCH/DELETE /api/v1/estoque/telefones-alerta/{id}/
GET/PATCH        /api/v1/estoque/configuracao-ia/1/

# Importação de Nota Fiscal
GET/POST      /api/v1/estoque/notas/                            ← POST (multipart, "arquivo") roda a cascata + fuzzy match
GET           /api/v1/estoque/notas/{id}/
PATCH         /api/v1/estoque/notas/{id}/itens/{item_id}/       ← {materia_prima}|{produto}|{criar_nova_materia_prima:true}|{quantidade,valor_unitario,descartado}
POST          /api/v1/estoque/notas/{id}/confirmar/              ← rejeita (400) item pendente de revisão
POST          /api/v1/estoque/notas/{id}/descartar/

# Relatórios (ver MULTIEMPRESA.md — aceitam ?empresa=<id>/?empresa=todas)
GET /api/v1/relatorios/ifood/                    ← data_inicio, data_fim, agrupamento (dia|mes), formato (json|excel|pdf), empresa
GET /api/v1/relatorios/produtos-mais-vendidos/   ← canal (repetível), data_inicio, data_fim, ordenar (quantidade|valor), limit (1-200), empresa · só JSON
GET /api/v1/relatorios/eventos/                  ← data_inicio, data_fim (filtram Evento.data_evento), agrupamento (dia|mes), formato (json|excel|pdf), empresa

# Dashboard
GET /api/v1/dashboard/resumo/                    ← aceita ?empresa=<id>/?empresa=todas

# Financeiro (ver FINANCEIRO.md e MULTIEMPRESA.md — todos aceitam ?empresa=<id>/?empresa=todas, exceto categorias/fornecedores/telefones)
GET/POST         /api/v1/financeiro/categorias/
GET/PATCH/DELETE /api/v1/financeiro/categorias/{id}/
GET/POST         /api/v1/financeiro/contas-bancarias/             ← sem DELETE
GET/PATCH        /api/v1/financeiro/contas-bancarias/{id}/
GET/POST         /api/v1/financeiro/fornecedores/                 ← ?search= (nome/cnpj)
GET/PATCH/DELETE /api/v1/financeiro/fornecedores/{id}/
GET/POST         /api/v1/financeiro/contas-pagar/                 ← filtros: status, categoria, fornecedor, mes (YYYY-MM), search
GET/PATCH        /api/v1/financeiro/contas-pagar/{id}/            ← só status='pendente'
POST             /api/v1/financeiro/contas-pagar/{id}/baixa/      ← multipart opcional (comprovante)
POST             /api/v1/financeiro/contas-pagar/{id}/cancelar/   ← só se valor_pago == 0
GET              /api/v1/financeiro/contas-pagar/resumo/
GET              /api/v1/financeiro/movimentos/                  ← só leitura, filtros: conta, tipo, categoria, data_inicio, data_fim
POST             /api/v1/financeiro/movimentos/manual/
GET/PATCH        /api/v1/financeiro/configuracao/1/               ← 1 linha por empresa, pk ignorado, resolve por ?empresa=
GET/POST         /api/v1/financeiro/telefones-alerta/
GET/PATCH/DELETE /api/v1/financeiro/telefones-alerta/{id}/
GET/POST         /api/v1/financeiro/recorrentes/
GET/PATCH        /api/v1/financeiro/recorrentes/{id}/             ← sem DELETE
GET/POST         /api/v1/financeiro/contas-receber/                ← POST sempre cria canal='manual'
GET/PATCH        /api/v1/financeiro/contas-receber/{id}/
POST             /api/v1/financeiro/contas-receber/{id}/baixa/
GET              /api/v1/financeiro/contas-receber/resumo/         ← inclui saldo de Evento só quando empresa=matriz/todas
GET/POST         /api/v1/financeiro/conferencias/                  ← saldo_calculado é sempre snapshot, sem PATCH/DELETE
GET              /api/v1/financeiro/fluxo-caixa/?dias=N            ← N 1-90 (default 14)

# Backup (ver backup.md)
GET/PATCH             /api/v1/manutencao/configuracao-backup/1/      ← singleton
GET/POST              /api/v1/manutencao/telefones-alerta/
GET/PATCH/DELETE      /api/v1/manutencao/telefones-alerta/{id}/

# Multi-Empresa (ver MULTIEMPRESA.md)
GET/POST/PATCH        /api/v1/empresas/[{id}/]           ← sem DELETE/PUT
GET                   /api/v1/empresas/branding-login/   ← AllowAny
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

# Crons diários (horários sugeridos)
python manage.py lembrar_aniversarios          # 09:00 — dias sem compra vem só de ConfiguracaoWhatsApp
python manage.py avisar_sem_compras            # 10:00
python manage.py alertar_eventos               # 08:00 — janelas de ConfiguracaoAlertaEvento
python manage.py alertar_estoque_baixo         # 08:30 — limites de ConfiguracaoEstoque
python manage.py gerar_contas_recorrentes      # 07:00 — idempotente
python manage.py alertar_vencimentos           # 08:30 — janelas de ConfiguracaoFinanceira
python manage.py fazer_backup                  # 03:00
python manage.py verificar_backup              # 08:00

# Importar planilha de precificação
python manage.py importar_planilha --arquivo PLANILHA_DE_PRECIFICACAO_ARRETADO.xlsx
# flags: --dry-run | --apenas-materias | --sobrescrever

# Restauração (SEMPRE manual — ver backup.md)
PGPASSWORD='<senha>' pg_restore -h localhost -p 5432 -U arretado_user -d arretado_db --clean --if-exists --no-owner /var/backups/arretado/db/crm_db_TIMESTAMP.dump
tar xzf /var/backups/arretado/media/media_TIMESTAMP.tar.gz -C /var/www/crm_arretado/ --overwrite
# Se o backup local sumiu, baixar do B2 primeiro:
rclone copy backup-remoto:arretado-backups/db/ /var/backups/arretado/db/
rclone copy backup-remoto:arretado-backups/media/ /var/backups/arretado/media/
# Parar arretado.service antes de restaurar o banco e religar depois

# Testes automatizados
python manage.py test --settings=config.settings_test
# settings_test.py roda contra SQLite em memória (Postgres de prod não tem CREATE DATABASE) e isola
# MEDIA_ROOT num tempfile.mkdtemp() — sem isso, FileField/ImageField gravam de verdade no media/ real

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

# Se o deploy marca uma nova versão:
git tag -a vX.Y.Z -m "Descrição curta da release"
git push origin vX.Y.Z
# + entrada correspondente no CHANGELOG.md
```

**Atenção:** `npm run build` grava direto em `arretado-crm/dist/`, servido pelo Nginx — não existe ambiente de teste isolado. Sempre confirmar com o usuário antes de rodar build na VPS.

**Atenção — `arretado-polling` também precisa reiniciar, sempre que o deploy mexe em models.** `systemctl restart arretado` sozinho não recarrega o worker de longa duração. Incidente real: um deploy que adicionou campo obrigatório em `ifood.PedidoIFood` sem reiniciar o polling perdeu 245 pedidos reais por 5 dias (`NotNullViolation` silencioso). Regra: qualquer deploy que rode `migrate` reinicia os dois serviços juntos (`systemctl restart arretado arretado-polling`).

Infra já configurada em produção (não precisa recriar):
- Nginx: `location /media/` (serve uploads) e `proxy_set_header X-Forwarded-Proto $scheme;` no bloco `/api/`
- Nginx: `client_max_body_size 10m;` (upload de foto de nota fiscal por celular)
- Django: `MEDIA_URL`/`MEDIA_ROOT` e `SECURE_PROXY_SSL_HEADER` em `config/settings.py`
- Git: `safe.directory = /var/www/crm_arretado` em `/etc/gitconfig` (`--system`) — necessário pro Gunicorn (`www-data`) rodar `git describe` com o repo dono por `root`

---

## O Que NÃO Fazer

- Não escrever diretamente no `PedidoUnificado` em views — ele é alimentado só por signals
- Não criar endpoints fora do padrão `ModelViewSet + CsrfExemptMixin`
- Não usar `localStorage` no frontend (exceto `authApi`, já existente — não expandir)
- Não alterar o `Sidebar.jsx` sem atualizar as rotas em `App.jsx`
- Não implementar nada sem antes verificar se já existe no código (`grep`/leitura direta)
- Não usar Celery — o projeto usa cron + management commands
- Não chamar `zapi_client` diretamente em signals, models ou views — sempre `notificacoes/servico.py`
- Não instanciar `ParametrosNegocio()`/`ConfiguracaoWhatsApp()`/`ConfiguracaoEntrega()`/`ConfiguracaoContrato()`/`ConfiguracaoAlertaEvento()`/`ConfiguracaoBackup()` diretamente — sempre `.get()`
- A validade padrão dos orçamentos vem de `ConfiguracaoWhatsApp.get().validade_orcamento_dias` — não usar settings
- Não fazer FK direta de `fichas` pra `pdv` — ligação via `produto_pdv_id` (IntegerField fraco)
- Não hardcodar taxa de entrega — sempre `TaxaEntregaBairro`/`ConfiguracaoEntrega.frete_padrao`
- Não preencher `materia_prima_origem`/`margem_desejada_pct` fora de `tipo == 'revenda'`
- Não permitir kit-de-kit em `ItemKit.componente`
- Não hardcodar desconto por quantidade/canal no frontend — sempre `Produto.preco_para()`
- Bairro do **Local de Evento** tem prioridade sobre bairro do cliente pra sugerir taxa de entrega — nunca inverter (ver `FRETE.md`)
- Não criar `ItemContrato` — o PDF lê os itens direto de `contrato.orcamento.itens`
- Não permitir `gerar-contrato/` sem `status == 'aprovado'` e CPF/RG/nacionalidade/profissão/estado civil preenchidos
- Não emitir `AditivoContrato` sem checar `_valor_referencia_contrato()` (último aditivo do contrato, senão `Contrato.valor_total`) — comparar direto contra `Contrato.valor_total` ignora aditivos anteriores e permite gerar um aditivo "sem alteração real" depois do primeiro
- Não reler itens/totais ao vivo do Evento pra reimprimir um `AditivoContrato` já emitido — sempre do snapshot gravado nele (`itens_snapshot`, `*_novo`), senão o documento muda de conteúdo se o evento for editado de novo depois
- Não pedir CPF/RG/endereço do CONTRATANTE de novo no fluxo de aditivo — já estão no `Contrato` original, aditivo só documenta a mudança de valor/itens
- Ao mesclar o PDF do contrato com o timbre, reler o `PdfReader` do timbre a cada página — reutilizar o objeto duplica a 1ª página em PDFs multi-página
- Ao ajustar a lista `condicoes` em `pdf_orcamento.py`, ajustar o piso `cond_y` na mesma proporção (±11pt por linha) — senão a última linha sobrepõe a área de assinatura em orçamento longo
- Não criar `ImagemInspiracao` por item de Orçamento — a galeria pertence ao registro inteiro
- Não esquecer de propagar `natureza=item.natureza` em `converter_em_evento` — sem isso, brinde/permuta vira venda cobrada
- Não montar `preco_total` de item manualmente sem passar pelo `save()` do model
- Não deixar signal de venda gravar `MovimentoFinanceiro` com valor `<= 0` — replicar o guard já existente
- Não contar item `brinde`/`permuta` em `ProdutosMaisVendidosView` — filtro `natureza='venda'` só em PDV/Eventos, nunca em `_qs_ifood()` (campo não existe lá)
- Não esconder item de brinde/permuta do PDF — sempre mostrar com rótulo + preço riscado
- Não deixar o usuário editar `preco_unit` no frontend quando `natureza != 'venda'` — input sempre `disabled`
- Ao somar `preco_total` num `create()` de serializer com itens aninhados, sempre `item.preco_total`, nunca `preco_unit * quantidade` calculado antes
- Não incluir imagens de `ImagemInspiracao` no PDF do orçamento nem no WhatsApp — uso interno
- Não duplicar `ImagemInspiracao` pro Evento na conversão — Evento só lê via `orcamento_origem`
- Não incluir `observacoes_cozinha` em documento client-facing — só no resumo de cozinha
- Não gravar `Evento.sinal_pago` diretamente — sempre via `recalcular_sinal_pago()`
- Não permitir PATCH/PUT em Orçamento fora de `rascunho`/`enviado`
- Não somar `Evento.valor_total` nem status de entrega pra receita de Eventos do dia no Dashboard — só `PagamentoEvento` pago
- Não criar model no app `dashboard/` — é agregador só-leitura
- **Nunca rodar `npm run build`/`vite build` na VPS sem avisar antes** — não existe build isolado, tratar todo build como deploy real
- Não expor `Usuario.auth_token` fora do payload de login
- Não criar `LogAuditoria` fora de `auditoria/utils.py::registrar()`
- Não checar `usuario.role == 'admin'` cru em views novas — usar `IsAdminRole`
- Não estender `authentication_classes`/`permission_classes` globalmente em settings — cada app opta localmente por `get_permissions()`
- `TokenAuthentication` numa viewset não implica login obrigatório — quem bloqueia é `permission_classes`
- Não confundir os dois endpoints `historico/`: `clientes/{id}/historico/` é histórico de pedidos; `orcamentos/{id}/historico/`/`eventos/{id}/historico/` é trilha de auditoria
- `PresencaEdicao`/`PresencaAtiva.jsx` é só informativo — não implementar trava/lock de edição em cima disso
- Não trocar o heartbeat de presença por WebSocket/Channels sem confirmar antes — decisão deliberada (Gunicorn/WSGI síncrono)
- Ao criar DELETE auditado num ViewSet novo, usar `AuditoriaDestroyMixin` em vez de `registrar()` manual — já trata `ProtectedError` como 400
- Nunca remover o bloqueio de DELETE em `ifood.ConfiguracaoIFoodViewSet` — não é singleton de verdade
- Não escrever `quantidade_estoque` fora de `MovimentoEstoque.registrar()`
- Não bloquear venda/produção/ajuste por saldo insuficiente — política é sempre permitir e alertar
- Não chamar `Producao.executar()` pra produto `modo_estoque == 'sob_encomenda'`
- Ao gravar `quantidade`/`custo_unitario_snapshot` em `MovimentoEstoque`, sempre deixar `registrar()` quantizar
- Não implementar estoque de kit físico pré-montado — kit é sempre virtual
- Não implementar reversão automática de estoque em cancelamento pós-débito — fora de escopo
- Não criar `MateriaPrima` automaticamente no fuzzy match da importação de nota fiscal — sempre `status_match='revisar'`
- Não gravar `MovimentoEstoque` direto a partir da extração — sempre via tela de revisão + `confirmar/`
- Não guardar `ANTHROPIC_API_KEY` em model/banco — só variável de ambiente
- Não usar SDK `anthropic` — `claude_client.py` usa `requests` puro
- Endpoint de nota fiscal é `POST /api/v1/estoque/notas/`, não `/notas/importar/`
- Não gravar `saldo_atual`/`valor_pago`/`valor_recebido`/`status` derivado diretamente — sempre via `registrar()`/`recalcular_*()`
- Não implementar DELETE de `MovimentoFinanceiro` — ledger imutável, corrige com lançamento inverso
- Não semear `CategoriaFinanceira` com valores hardcoded
- Não permitir PATCH em `ContaPagar` fora de `status='pendente'`
- Não instanciar `ConfiguracaoFinanceira()` direto — sempre `.get(empresa)` (argumento obrigatório desde a Fase 4)
- Não gravar `ContaPagar.recorrente` fora do cron `gerar_contas_recorrentes`
- Não checar `UniqueConstraint` sem checar `.exists()` explícito antes — nunca confiar só na constraint pra evitar duplicata silenciosa
- Não implementar DELETE em `DespesaRecorrente` — pausar via `ativo=False`
- Não materializar `ContaReceber` para Eventos nem PDV — dupla contagem
- Não gravar `ContaReceber.canal`/`origem_canal`/`origem_id` a partir da API — read-only
- Não gravar movimento de `PedidoIFood` em cada evento de polling — só na transição pra `CONCLUDED`
- Não criar `ContaBancaria` automaticamente dentro de um signal — configurar `conta_padrao_vendas` é passo manual
- Não mexer na geração de `MovimentoEstoque` dentro do `confirmar()` da nota — `ContaPagar` é acrescentada depois, em método próprio
- Não criar `Fornecedor` sem nenhum dado extraído (nome ou CNPJ)
- Não gravar `ContaPagar.categoria` automaticamente na geração por nota fiscal — nasce `None`
- Não fazer DELETE do `MovimentoFinanceiro` original ao estornar — sempre um movimento manual inverso novo
- Não permitir PATCH/DELETE em `SaldoConferido` — conferência nova é sempre registro novo
- Não aceitar `saldo_calculado` vindo do payload — sempre snapshot no momento do POST
- Não somar saldo dinâmico de Evento em `fluxo-caixa/` — fora do escopo desse agregador
- Não colocar senha do banco na linha de comando do `pg_dump`/`pg_restore` — usar `PGPASSWORD` via env
- Não usar `subprocess`/`tar` do sistema pra compactar mídia no backup — usar `tarfile` (stdlib)
- Não fazer `fazer_backup` chamar `notificar()` — responsabilidade exclusiva do `verificar_backup`
- Não criar management command `restaurar_backup` — restauração é sempre manual
- Não incluir o `.env` no backup — guardar chaves é procedimento manual separado
- Não adicionar dedup de alerta ao `verificar_backup` — repetição diária é decisão consciente
- Não resolver a empresa padrão por id fixo (`Empresa.objects.get(pk=1)`) — sempre `Empresa.get_padrao()`
- Não permitir duas empresas com `padrao=True`, nem desmarcar a única sem promover outra na mesma requisição
- Não implementar DELETE/PUT em `empresas.Empresa` — inativar via `ativo=False`
- Não hardcodar nome/cor/CNPJ de nenhuma empresa em código, CSS ou serializer — requisito de revenda
- Não resolver `empresa` em `dashboard/`/`relatorios/` por caminho diferente de `_resolver_empresa()` local a cada app
- Não somar Evento/PagamentoEvento/estoque sem o gate `eventos_habilitado`/`matrizView` em `dashboard/views.py` — são mono-empresa sem FK própria
- Não materializar `modulos_ocultos` como controle de acesso — é só filtro de UI
- Não gravar `empresa` de `ContaBancaria`/`ContaPagar`/`ContaReceber`/`DespesaRecorrente` fora do que `_resolver_empresa()` resolve — campos são `read_only` de propósito
- Não denormalizar `empresa` em `MovimentoFinanceiro` — sempre a property que delega pra `conta.empresa`
- Não permitir `conta_padrao_vendas` de empresa diferente da configuração
- Não resolver config financeira de pedido iFood via `Empresa.get_padrao()` — sempre `pedido.empresa`
- Não bloquear login por falta de vínculo de empresa — cai na empresa padrão
- Não permitir `definir-empresa-ativa/` fora do vínculo do usuário — exceto `role=admin`
- Não auditar `preferencia-tema/` (cosmético) — auditar sempre `definir-empresa-ativa/`
- Não deixar `empresa_ativa`/`preferencia_tema` editáveis por `PATCH /usuarios/{id}/` direto
- Não usar `localStorage` como fonte da verdade de empresa ativa/tema — backend primeiro, depois espelha via `atualizarCache()`
- Não confundir os 12 campos de cor de `Empresa` com nomes conceituais do spec — o mapeamento real vive em `utils/tema.js::aplicarCoresEmpresa()`
- Não setar cor/tema direto via `document.documentElement` em componente novo — sempre pelas funções de `utils/tema.js`
- Ao adicionar token de cor novo, usar o hex **atual** como default em `:root` (nunca um "mais bonito"), sempre em par `--x-bg`/`--x-fg`
- Não redefinir `--badge-{ifood,anotaai}-*`/`--whatsapp*` em `temas.css` — identidade de terceiro, sempre fixos
- Não perseguir 100% dos hex hardcoded restantes nos CSS Modules como objetivo de fase — decisão consciente
- Não resolver credencial de ação de pedido iFood via `.objects.first()` — sempre `ConfiguracaoIFood.objects.filter(empresa=pedido.empresa)`
- Não materializar `PedidoPDV`/`Evento` com empresa diferente da padrão — PDV e Eventos são mono-empresa por escopo
- Não hardcodar a versão do sistema em nenhum arquivo — sempre `git describe` + tag + `CHANGELOG.md`
- Não esquecer da tag ao fazer um deploy que o usuário considera "versão nova" — perguntar antes de criar
- Não reiniciar só `arretado.service` num deploy que muda `models.py` de app usado pelo `arretado-polling` (`ifood`, `clientes`, `pedidos`, `empresas`) — sempre reiniciar os dois juntos
- Não rodar `manage.py test` esperando filesystem isolado igual ao banco — só o banco vira SQLite em memória, `MEDIA_ROOT` precisa isolamento próprio em `settings_test.py`
