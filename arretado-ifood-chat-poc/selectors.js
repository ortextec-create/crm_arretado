/**
 * Seletores do Gestor de Pedidos iFood (gestordepedidos.ifood.com.br).
 *
 * Cada chave tem uma LISTA de candidatos, testados em ordem. O primeiro que
 * encontrar elemento vence. Quando o iFood mudar o HTML, o diagnóstico mostra
 * qual chave quebrou e basta ajustar a lista aqui.
 *
 * Atenção: o iFood usa tanto `data-test-id` (com hífen) quanto `data-testid`.
 *
 * Status em 20/out/2026 (Gestor real, Chrome 154, Windows):
 *   VALIDADOS: chatToggleButton, closeChatButton, closeConversationButton,
 *              messageInput, sendButton, orderCard, orderDetailsChatButton,
 *              conversationPane
 *   QUEBRADOS: conversationListScroll, conversationOrderNumber (lista do
 *              painel "Conversas" mudou; candidatos novos abaixo, a validar)
 */
window.ORTEX_SELECTORS = {
  // Botão do header que abre o painel de conversas — VALIDADO
  chatToggleButton: [
    '[data-test-id="CONSUMER_CHAT_REBORN_HEADER_ENTRY_POINT"]',
    'button[aria-label="Conversas com clientes"]',
  ],

  // Fechar painel — VALIDADO
  closeChatButton: [
    'span.ifdl-icon-close',
    '[aria-label="Fechar"]',
  ],

  // Fechar a conversa aberta — VALIDADO
  closeConversationButton: [
    '[data-testid="close-icon"]',
    '[data-test-id="close-icon"]',
  ],

  // Container com rolagem da lista do painel "Conversas" — QUEBRADO, a validar
  conversationListScroll: [
    '[style*="overflow: auto"]',
    '[style*="overflow-y: auto"]',
    '[style*="overflow: scroll"]',
  ],

  // Número do pedido em cada item da lista / no cabeçalho da conversa.
  // Antes era <h2>; hoje o cabeçalho da conversa é <span aria-label="#4595 Nome">.
  conversationOrderNumber: [
    '[aria-label^="#"]',
    'h2',
  ],

  // Painel da conversa aberta — VALIDADO
  conversationPane: [
    '[data-testid="customer-conversation-pane"]',
    '[data-test-id="customer-conversation-pane"]',
  ],

  // Campo de digitação — VALIDADO
  messageInput: [
    'textarea[aria-label="Campo de mensagem"]',
    'textarea[placeholder*="mensagem" i]',
  ],

  // Botão de enviar — VALIDADO
  sendButton: [
    'button[aria-label="Enviar mensagem"]',
  ],

  // Card de pedido na tela de expedição — VALIDADO
  orderCard: [
    '[data-testid="card"]',
    '[data-test-id="card"]',
  ],

  // Botão de chat nos detalhes do pedido (cria a conversa se não existir) — VALIDADO
  orderDetailsChatButton: [
    '[data-test-id="CONSUMER_CHAT_REBORN_MESSAGING_ORDER_DETAILS_ENTRY_POINT"]',
    '[data-testid="CONSUMER_CHAT_REBORN_MESSAGING_ORDER_DETAILS_ENTRY_POINT"]',
  ],
};

/**
 * Rota de detalhe do pedido no Gestor (vista na URL ao clicar num card):
 *   #/home/order-display/expedition/<ifood_order_id>
 * Permite abrir o pedido direto pelo ID, sem procurar card. A VALIDAR.
 */
window.ORTEX_ROTA_DETALHE = '#/home/order-display/expedition/';
