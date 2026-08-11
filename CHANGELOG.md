# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).
Versionamento derivado de tags anotadas do Git (`git describe --tags`) — nunca mantido
à mão em arquivo/settings, ver `CLAUDE.md` → "Versão do Sistema". Cada entrada aqui
corresponde a uma tag `vX.Y.Z` criada no checklist de deploy.

## [v1.0.0] - 2026-08-10

Baseline — estado do sistema em produção antes da introdução do versionamento por Git.
Cobre todas as fases já concluídas até essa data (ver "Status das Fases" no `CLAUDE.md`
para o detalhamento completo): CRM de Clientes, iFood, PDV Próprio, Orçamentos/Eventos,
Contratos, Dashboard, WhatsApp, Usuários/RBAC, Catálogo & Precificação, Frete por Bairro,
Relatórios iFood, Imagens de Inspiração, Pagamentos Parciais de Evento, Auditoria completa
(criação/edição/status/presença/histórico), Alertas de Evento, Estoque (fases 1-8, incluindo
importação de nota fiscal), Resumo de Cozinha, Módulo Financeiro (fases 0-7) e Sistema de
Backup (Banco + Mídia via Backblaze B2).
