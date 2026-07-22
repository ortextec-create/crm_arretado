# Prompt de abertura — Sessão Claude Code: Módulo Financeiro

Copie o bloco abaixo para iniciar a sessão (com `FINANCEIRO.md` já colocado na raiz do repo, ao lado de `CLAUDE.md`):

---

Leia `CLAUDE.md` (referência canônica — verifique o timestamp no disco) e depois `FINANCEIRO.md` na raiz do repo.

Vamos implementar o módulo Financeiro seguindo exatamente a spec, fase a fase:

1. Comece pela **Fase 0** (correção do bug `itens_json` em `eventos/models.py::sincronizar_evento()` + verificação das queries do dashboard + atualização dos trechos defasados do CLAUDE.md). Antes de corrigir, leia o schema real de `pedidos.PedidoUnificado` e as queries de `dashboard/views.py` — a spec exige garantir que a receita de Eventos continua vindo só de `PagamentoEvento` e que nada duplica.
2. Só avance para a fase seguinte quando os critérios de pronto da tabela "Fases de Implementação" estiverem atendidos, com testes.
3. Ao final de cada fase, atualize o `CLAUDE.md` (estrutura de pastas, endpoints, tabela de fases, padrões obrigatórios) antes de encerrar.
4. Respeite rigorosamente a seção "O Que NÃO Fazer" da spec — em especial: escrita no ledger só via `MovimentoFinanceiro.registrar()`, nada de DELETE em movimento, nenhuma categoria hardcoded, nenhuma ContaReceber materializada para Eventos/PDV.
5. Padrões do projeto valem integralmente: `CsrfExemptMixin`, singletons via `.get()`, `proximo_numero()`, mixins de auditoria, cron via management command (sem Celery), testes com `settings_test.py` (SQLite em memória).

Pare e me consulte antes de qualquer decisão que a spec marque como pendente ou que exija desviar dela.

---

## Observações para você (fora do prompt)

- A spec deliberadamente **não inclui**: atualização de custo de insumo pela nota (decisão sua pendente), derivação de `despesa_fixa`, relatório financeiro com export, cards no Dashboard. Cada um vira spec própria depois.
- Itens do checklist "Setup Manual" da spec são seus, não do Claude Code — em especial a `ANTHROPIC_API_KEY` na VPS e o crontab.
- Sugestão de divisão de sessões, se preferir sessões curtas: Fases 0–1 · Fases 2–3 · Fases 4–5 · Fases 6–8.
