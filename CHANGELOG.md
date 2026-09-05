# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).
Versionamento derivado de tags anotadas do Git (`git describe --tags`) — nunca mantido
à mão em arquivo/settings, ver `CLAUDE.md` → "Versão do Sistema". Cada entrada aqui
corresponde a uma tag `vX.Y.Z` criada no checklist de deploy.

## [v1.5.1] - 2026-09-05

### Adicionado
- **Brindes e Permutas** (spec completa em `BRINDES_PERMUTAS.md`, 5 fases): campo `natureza`
  (venda/brinde/permuta, granularidade por item) em `ItemOrcamento`/`ItemEvento`/
  `ItemPedidoPDV` — item não-venda zera `preco_total` mas preserva `preco_unit` como
  referência de preço de tabela. Guard no ledger financeiro evita entrada fantasma de
  R$0,00 para pedido/evento 100% brinde; ranking de produtos mais vendidos passa a
  ignorar item de brinde/permuta. PDF de orçamento/contrato mostra o item com rótulo
  (" — Brinde"/" — Permuta") e o preço de tabela riscado. Seletor de natureza no
  frontend (Orçamentos/Eventos/PDV), com preço travado quando não é venda. PDV Avulso
  (venda 100% brinde/permuta sem Orçamento/Evento) confirmado funcionando sem código
  novo.
- **Eventos — Imagens de Inspiração a qualquer momento**: a galeria de imagens de
  referência, antes exclusiva do Orçamento, agora também pode ser editada direto no
  Evento, em qualquer status — com ou sem orçamento de origem. Quando o Evento veio de
  um Orçamento, a imagem nova continua indo pra galeria do Orçamento (sem duplicar);
  sem orçamento de origem, fica anexada direto ao Evento.
- **Financeiro — KPIs de Contas a Pagar viram filtros clicáveis**: os 4 cards do topo
  (Em atraso / Vence hoje / Próx. 7 dias / Pago no mês) agora filtram a lista ao clicar.

### Corrigido
- **Financeiro**: lista de Contas a Pagar podia colapsar visualmente (~0px de altura)
  quando a seção de Despesas Recorrentes crescia muito, por causa de `flex: 1` +
  `overflow-x: auto` na mesma coluna flex.
- **UI**: modais (`Modal.jsx`, PDV, Catálogo PDV) não fecham mais ao clicar fora —
  evita perda de dados digitados em formulários como Novo Orçamento.

## [v1.5.0] - 2026-08-24

### Adicionado
- **Multi-Empresa — Fase 4** (Financeiro por empresa, spec completa em `MULTIEMPRESA.md`):
  `financeiro.ContaBancaria`/`ContaPagar`/`ContaReceber`/`DespesaRecorrente` ganham FK
  `empresa` (`PROTECT`); `ConfiguracaoFinanceira` deixa de ser singleton global e vira 1 linha
  por empresa (`get(empresa)`); `MovimentoFinanceiro` continua sem FK própria — a empresa é
  sempre a da `ContaBancaria` (property). Signals de venda resolvem a config pela empresa
  certa: iFood pela empresa do próprio pedido (permite a MANGAIO em modo `repasse` e a matriz
  em `no_ato` simultaneamente), PDV/Eventos sempre a matriz (mono-empresa por escopo). Todos
  os endpoints do módulo aceitam `?empresa=<id>`/`?empresa=todas` (consolidado).
  `Financeiro.jsx` passa a consumir o contexto global de empresa ativa (`useAuth()`), com
  badge e chip "Todas as empresas" nas abas de resumo.
- **Multi-Empresa — Fase 5** (Dashboard e Relatórios por empresa): `GET /dashboard/resumo/`,
  `GET /relatorios/ifood/` e `GET /relatorios/produtos-mais-vendidos/` aceitam
  `?empresa=<id>`/`?empresa=todas` (default: empresa ativa do usuário, senão a matriz). PDV,
  Eventos e Estoque — mono-empresa, sem FK própria — são zerados na visão de uma empresa
  não-matriz, que ganha em troca o card "Repasse iFood a receber" (soma de `ContaReceber`
  pendente/parcial da empresa). Campo novo `Empresa.modulos_ocultos` permite esconder, por
  empresa, os itens de menu que ela não usa (a Sidebar filtra por isso — é só UI, nenhuma
  rota deixa de existir); editável na tela `/empresas`. `Dashboard.jsx` e `Relatorios.jsx`
  ganham o mesmo padrão de seletor de empresa já usado no Financeiro.

Com esta entrega, as 6 fases do sistema multi-empresa (`MULTIEMPRESA.md`) estão completas.
Falta apenas cadastrar a MANGAIO de fato pela tela `/empresas`.

## [v1.4.0] - 2026-08-20

### Adicionado
- **Multi-Empresa — Fase 3** (Sistema de Temas, spec completa em `MULTIEMPRESA.md`): fecha o
  ciclo visual do multi-empresa — 100% frontend, sem nenhuma migration. As 12 cores + 3 logos
  cadastrados em `Empresa` (desde a Fase 0) agora são de fato aplicados na interface
  (`src/utils/tema.js::aplicarCoresEmpresa()`), com reset correto ao trocar de empresa/tema/
  logout (campo vazio sempre limpa o override, nunca só pula). Dois temas neutros novos do
  produto — Claro e Escuro (`src/temas.css`, tipografia Inter) — selecionáveis por um controle
  novo no rodapé da Sidebar (`SeletorTema.jsx`), persistidos em `Usuario.preferencia_tema`
  (já existente desde a Fase 2). `Login.jsx` passou a consumir `GET /empresas/branding-login/`
  (endpoint órfão desde a Fase 0) — a tela de login agora reflete nome/logo/cores da empresa
  matriz. `Sidebar.jsx` mostra logo e subtítulo dinâmicos quando a empresa ativa tiver. Como
  pré-requisito do spec, ~150 ocorrências de cor hardcoded em 20 CSS Modules foram convertidas
  para tokens de design system (mesmos valores — mudança invisível para quem nunca trocar de
  tema), incluindo um trio de tokens de status compartilhado (ok/alerta/crítico) que elimina
  duplicação entre Estoque/Financeiro/Central de Preços/Fichas Técnicas/Configurações. Validado
  visualmente nos 3 modos em Login, Dashboard, Financeiro e Estoque — a aparência da Arretado
  (tema "Empresa" sem nenhuma cor cadastrada) permanece pixel-a-pixel idêntica à anterior a esta
  entrega. Faltam as 2 últimas fases do multi-empresa: Financeiro e Dashboard/Relatórios por
  empresa.

## [v1.3.0] - 2026-08-18

### Adicionado
- **Multi-Empresa — Fase 2** (Usuários × Empresas + empresa ativa, spec completa em
  `MULTIEMPRESA.md`): `usuarios.Usuario` ganha `empresas` (M2M → `empresas.Empresa`),
  `empresa_ativa` (FK `SET_NULL`) e `preferencia_tema` (choices — aplicação visual do tema
  fica pra Fase 3). Login nunca é bloqueado por falta de vínculo: sem nenhuma empresa
  vinculada, o usuário cai na empresa padrão em runtime; `role=admin` sempre enxerga/pode
  ativar qualquer empresa ativa, não só as vinculadas. Novos endpoints
  `POST /usuarios/definir-empresa-ativa/` (audita `empresa_alternada`) e
  `POST /usuarios/preferencia-tema/` (cosmético, não audita). Frontend: `EscolherEmpresa.jsx`
  (tela pós-login quando o usuário tem 2+ empresas), `EmpresaSwitcher.jsx` (pill de troca na
  Sidebar — o projeto não tem header global, só sidebar), checkbox de vínculo de empresa em
  `Usuarios.jsx` (criação e edição). Todos os 6 usuários existentes vinculados à empresa
  matriz via data migration — comportamento pós-deploy idêntico ao anterior à fase. Próximas
  3 fases (Temas de fato, Financeiro, Dashboard/Relatórios) ainda não iniciadas.

## [v1.2.0] - 2026-08-12

### Adicionado
- **Multi-Empresa — Fase 1** (iFood, spec completa em `MULTIEMPRESA.md`): FK `empresa` (`PROTECT`)
  em `ifood.ConfiguracaoIFood` e `ifood.PedidoIFood` (denormalizada — snapshot da empresa da
  config no momento da criação do pedido), e FK `empresa` (`PROTECT`, `null=True`) em
  `pedidos.PedidoUnificado`. Credencial de ação de pedido (confirmar/cancelar/despachar/
  pronto-retirada/negociação) agora sempre resolvida pela empresa do pedido — nunca mais por
  `ConfiguracaoIFood.objects.first()` —, permitindo dois merchants iFood simultâneos no mesmo
  worker de polling. `GET /ifood/config/status/`, `GET /ifood/pedidos/estatisticas/` e
  `GET /ifood/pedidos/` aceitam `?empresa=<id>`. PDV e Eventos continuam mono-empresa, sempre
  gravando `Empresa.get_padrao()` no `PedidoUnificado`. `IFood.jsx` ganha seletor de empresa no
  topo da tela (só visível com 2+ empresas ativas — hoje ainda invisível, MANGAIO não cadastrada).
  2255 pedidos históricos e a configuração existente migrados para a empresa matriz sem perda de
  dados. Próximas 4 fases (Usuários/empresa ativa, Temas, Financeiro, Dashboard/Relatórios)
  ainda não iniciadas.

## [v1.1.0] - 2026-08-11

### Adicionado
- **Multi-Empresa — Fase 0** (app `empresas/`, spec completa em `MULTIEMPRESA.md`): model `Empresa`
  (multi-tenant por linha, branding em 12 cores hex opcionais + 3 logos + timbre preparatório,
  `padrao=True` único e protegido por constraint condicional), `EmpresaViewSet` (CRUD sem
  DELETE/PUT, auditado) + `branding-login/`, tela `Empresas.jsx` (`/empresas`, menu Administração,
  admin-only). Empresa matriz criada via data migration, sem cores/logos — UI da Arretado
  permanece idêntica. Próximas 5 fases (iFood, Usuários/empresa ativa, temas, Financeiro,
  Dashboard) ainda não iniciadas.
- **Versão do Sistema**: `GET /api/v1/versao/` e rodapé da Sidebar agora derivam a versão de
  `git describe --tags` (nunca mantida à mão). `CHANGELOG.md` (este arquivo) passa a documentar
  cada release a partir daqui.

## [v1.0.0] - 2026-08-10

Baseline — estado do sistema em produção antes da introdução do versionamento por Git.
Cobre todas as fases já concluídas até essa data (ver "Status das Fases" no `CLAUDE.md`
para o detalhamento completo): CRM de Clientes, iFood, PDV Próprio, Orçamentos/Eventos,
Contratos, Dashboard, WhatsApp, Usuários/RBAC, Catálogo & Precificação, Frete por Bairro,
Relatórios iFood, Imagens de Inspiração, Pagamentos Parciais de Evento, Auditoria completa
(criação/edição/status/presença/histórico), Alertas de Evento, Estoque (fases 1-8, incluindo
importação de nota fiscal), Resumo de Cozinha, Módulo Financeiro (fases 0-7) e Sistema de
Backup (Banco + Mídia via Backblaze B2).
