/**
 * Seletores embutidos do Gestor de Pedidos iFood (gestordepedidos.ifood.com.br).
 *
 * Cada chave tem uma LISTA de candidatos, testados em ordem; o primeiro que acha elemento vence.
 * Estes são o fallback: `GET /atendimento/extensao/config/` devolve `seletores` que sobrescrevem
 * chave a chave (conserto sem reinstalar). Validados em 20/out/2026 (ver ATENDIMENTO_IFOOD.md,
 * "Seletores validados"). O iFood usa tanto `data-test-id` quanto `data-testid`.
 */
window.ORTEX_SELECTORS = {
  // Botão do header que abre o painel "Conversas". NÃO usar o aria-label (muda com não lidas).
  chatToggleButton: [
    '[data-test-id="CONSUMER_CHAT_REBORN_HEADER_ENTRY_POINT"]',
  ],

  // Título do painel "Conversas" (h1 com texto "Conversas")
  conversationPanelTitle: [
    '.sendbird-channel-list h1',
  ],

  // Fechar painel (há várias ocorrências; o código escolhe a visível mais próxima do painel)
  closeChatButton: [
    'span.ifdl-icon-close',
  ],

  // Fechar a conversa aberta
  closeConversationButton: [
    '[data-testid="close-icon"]',
    '[data-test-id="close-icon"]',
  ],

  // Rolagem da lista do painel (só existe com o painel aberto)
  conversationListScroll: [
    '[style*="overflow: auto"]',
    '[style*="overflow-y: auto"]',
  ],

  // Número do pedido em cada item da lista: h2 com texto exato "#NNNN"
  conversationOrderNumber: [
    '.sendbird-channel-list h2',
    'h2',
  ],

  // Cabeçalho da conversa aberta: aria-label "#NNNN Nome" (busca subindo a partir de messageInput)
  conversationHeader: [
    '[aria-label^="#"]',
  ],

  conversationPane: [
    '[data-testid="customer-conversation-pane"]',
    '[data-test-id="customer-conversation-pane"]',
  ],

  messageInput: [
    'textarea[aria-label="Campo de mensagem"]',
  ],

  sendButton: [
    'button[aria-label="Enviar mensagem"]',
  ],

  // Botão de chat nos detalhes do pedido (abre a conversa existente ou cria uma)
  orderDetailsChatButton: [
    '[data-test-id="CONSUMER_CHAT_REBORN_MESSAGING_ORDER_DETAILS_ENTRY_POINT"]',
    '[data-testid="CONSUMER_CHAT_REBORN_MESSAGING_ORDER_DETAILS_ENTRY_POINT"]',
  ],

  // Só diagnóstico (fluxo por card está desligado: formato do número no card não confirmado)
  orderCard: [
    '[data-testid="card"]',
    '[data-test-id="card"]',
  ],
};

// Rota de detalhe do pedido: #/home/order-display/expedition/<ifood_order_id>
window.ORTEX_ROTA_DETALHE = '#/home/order-display/expedition/';

// Chaves cuja quebra deixa a extensão inútil (badge vermelho)
window.ORTEX_SELETORES_CRITICOS = ['messageInput', 'sendButton', 'chatToggleButton'];
