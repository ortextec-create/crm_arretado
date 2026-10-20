# Ortex – iFood Chat (extensão de produção)

Extensão de Chrome que envia, no chat do **Gestor de Pedidos iFood (web)**, as mensagens que o CRM
enfileira (status do pedido, atraso, envio manual). O CRM decide o que mandar; a extensão só executa.
Spec completa: `ATENDIMENTO_IFOOD.md`, Fase 2.

## Instalar

1. Gere um token no CRM (Atendimento → aba Extensão → Tokens; ou, no servidor,
   `python manage.py gerar_token_extensao --empresa <id> --nome "Computador do caixa"`).
   **O token aparece uma única vez.**
2. Chrome → `chrome://extensions` → ligar **Modo do desenvolvedor** → **Carregar sem compactação** → escolher esta pasta.
3. Abra o Gestor (`gestordepedidos.ifood.com.br`), logado, e recarregue a aba (F5).
4. Clique no ícone da extensão → informe a **URL do CRM** e o **token** → **Salvar e testar**
   (o Chrome pede permissão para a URL do CRM).
5. Deixe o **modo seguro ligado** no primeiro teste: ele preenche a mensagem e não envia (a
   mensagem termina em `falha` com `erro = modo_seguro` no CRM). Só depois desligue.

## Operação

- Chrome aberto no Gestor web, logado. Gestor desktop/Android não servem.
- **A aba designada precisa ficar visível** (janela própria do Chrome, não minimizada, não
  totalmente coberta por outra). Escondida, o Chrome reduz o ciclo para ~1 por minuto e o CRM mostra
  "envios atrasados".
- Recomendado: uma janela do Chrome só para a extensão e outra para a equipe operar.
- Desative a suspensão e o bloqueio de tela do computador nos horários de operação.
- Com mais de uma aba do Gestor, escolha no popup qual processa a fila. Com uma só, ela é designada sozinha.
- Mexer na aba (clique, tecla, rolagem) pausa a extensão por alguns segundos; se acontecer no meio de
  um envio, ele é abortado (`interrompido_por_usuario`) e vira `falha` no CRM.

## Badge do ícone

- **Verde**: conectada, aba designada visível, seletores ok.
- **Amarelo**: pausada por interação, aba oculta, ou nenhuma aba designada.
- **Vermelho**: sem backend, token inválido ou seletor crítico quebrado.
- **Cinza**: sem configuração, ou desligada.

## Erros reportados ao CRM

`rota_nao_abriu`, `painel_nao_abriu`, `conversa_nao_encontrada`, `conversa_errada`,
`conversa_nao_identificada`, `interrompido_por_usuario`, `modo_seguro`, `sem_botao_enviar`, `excecao`.
Cada falha traz o log de `passos` em Atendimento → Fila.

## Quando o iFood mudar a página

Os seletores embutidos (`selectors.js`) podem ser sobrescritos **sem reinstalar** pelo CRM
(`PATCH /api/v1/atendimento/configuracao-extensao/`, só admin). Efeito em até 5 min.

## Arquivos

| Arquivo | Papel |
|---|---|
| `content.js` | Relógio, fluxos de abrir conversa, trava de conversa errada, envio |
| `background.js` | Service worker: toda a rede, aba designada, badge |
| `selectors.js` | Seletores embutidos (fallback) |
| `popup.*` | Configuração, status, escolha da aba, diagnóstico |
