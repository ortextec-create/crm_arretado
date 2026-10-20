# Ortex – iFood Chat (POC v0.2)

Prova de conceito da extensão Chrome que escreve no chat do **Gestor de Pedidos iFood (web)**.
Não fala com o CRM: tudo é acionado à mão pelo popup.

## O que mudou da v0.1

- **Abre o pedido direto pelo ID iFood** (o código longo que aparece no fim da URL quando você
  clica num pedido). É o caminho que a versão de produção vai usar.
- **Confere a conversa antes de escrever:** se o chat aberto não for do número informado, aborta
  sem escrever nada.
- **Card achado pelo número exato.** A v0.1 podia confundir `0567` com um preço `R$ 105,67`.
- **Diagnóstico mais completo:** lê as mensagens da conversa aberta e de que lado da tela cada
  uma aparece (cliente × loja).

## Atualizar a extensão

1. Substitua os arquivos da pasta antiga por estes (ou descompacte numa pasta nova).
2. `chrome://extensions` → no card da extensão, clique no ícone de **recarregar** (↻).
   Se usou pasta nova: remova a antiga e **Carregar sem compactação** na nova.
3. **Recarregue a aba do Gestor (F5).** Obrigatório depois de atualizar.
4. O popup deve mostrar **"iFood Chat — POC v0.2"**.

## Roteiro de teste

Use um pedido seu em andamento, como na rodada anterior.

### Teste A — Conversa com resposta do cliente (o mais importante)

1. Pelo celular, mande 2 ou 3 mensagens no chat do pedido (ex.: "oi", "tudo certo?").
2. No Gestor, responda uma vez pela própria tela do Gestor (digitando à mão).
3. Deixe essa conversa **aberta** na tela.
4. Extensão → **Diagnosticar página** → salve como `diag-A-conversa.txt`.

### Teste B — Painel de conversas aberto

1. Feche a conversa. Clique no botão de conversas do topo do Gestor (balão de chat) para abrir
   a **lista de conversas**.
2. Com a lista aberta, **Diagnosticar página** → salve como `diag-B-lista.txt`.

### Teste C — Abrir pelo ID (modo seguro)

1. Clique no card do pedido. A URL fica `.../expedition/<código longo>`. Feche os detalhes.
2. Abra a extensão: o campo **ID iFood** já vem preenchido se você estiver nos detalhes do
   pedido; senão, cole o código longo da URL.
3. Preencha também o **Nº do pedido** exatamente como no Gestor, **com zeros** (ex.: `0567`).
4. **Modo seguro** marcado → **Executar teste** → copie o resultado → `teste-C.txt`.
5. Apague o texto do campo.

### Teste D — Trava de segurança

1. Mesmo ID do teste C, mas digite um **número errado** (ex.: `9999`).
2. Modo seguro → Executar. O resultado tem que ser `"erro": "conversa_errada"` e **nada pode
   ser escrito** no campo. Salve como `teste-D.txt`.

### Teste E — Duas janelas (se ainda não fez)

Abra o Gestor numa segunda janela do Chrome e veja se a primeira desloga.

## O que mandar de volta

`diag-A-conversa.txt`, `diag-B-lista.txt`, `teste-C.txt`, `teste-D.txt`, e o resultado do
teste E (e, da rodada anterior: a mensagem enviada chegou no celular?).

> O diagnóstico A inclui o texto do chat. Como o pedido é seu, pode mandar.
