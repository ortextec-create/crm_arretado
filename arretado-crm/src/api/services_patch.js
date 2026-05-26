/**
 * PATCH: arretado-crm/src/api/services.js — Fase 4
 *
 * Adicione o objeto `pedidosApi` ao final do arquivo services.js existente,
 * antes do `export { clientesApi, tagsApi, ifoodApi, pdvApi, authApi }`.
 * Atualize também o export para incluir `pedidosApi`.
 */

// ─── Pedidos Unificados (Fase 4 — vinculação manual) ──────────────────────

export const pedidosApi = {
  /**
   * Lista pedidos unificados com filtros opcionais.
   * @param {Object} params - { canal, status, sem_cliente, search, page }
   */
  listar: (params = {}) =>
    api.get('/pedidos/', { params }),

  /**
   * Detalhe de um pedido unificado.
   */
  detalhe: (id) =>
    api.get(`/pedidos/${id}/`),

  /**
   * Conta pedidos sem cliente vinculado por canal.
   * Usado para o badge de alerta no Sidebar.
   */
  semCliente: () =>
    api.get('/pedidos/sem-cliente/'),

  /**
   * Vincula um cliente CRM a um pedido unificado.
   * Propaga ao modelo nativo do canal automaticamente.
   * @param {number} pedidoId
   * @param {number|null} clienteId - null para desvincular
   */
  vincularCliente: (pedidoId, clienteId) =>
    api.post(`/pedidos/${pedidoId}/vincular-cliente/`, { cliente_id: clienteId }),
};

// ─── Export atualizado ────────────────────────────────────────────────────
// Substitua a linha de export existente por:
// export { clientesApi, tagsApi, ifoodApi, pdvApi, pedidosApi, authApi };
