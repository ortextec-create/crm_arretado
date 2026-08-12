# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).
Versionamento derivado de tags anotadas do Git (`git describe --tags`) — nunca mantido
à mão em arquivo/settings, ver `CLAUDE.md` → "Versão do Sistema". Cada entrada aqui
corresponde a uma tag `vX.Y.Z` criada no checklist de deploy.

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
