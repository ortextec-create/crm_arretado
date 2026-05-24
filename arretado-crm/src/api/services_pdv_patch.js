// ═══════════════════════════════════════════════════════════════════════════════
// PATCH 1: src/api/services.js
// Adicione o objeto pdvApi no final do arquivo (antes dos exports existentes)
// ═══════════════════════════════════════════════════════════════════════════════

export const pdvApi = {
  // Categorias
  listCategorias: (params = {}) => api.get('/pdv/categorias/', { params }),
  criarCategoria: (data)        => api.post('/pdv/categorias/', data),
  editarCategoria:(id, data)    => api.patch(`/pdv/categorias/${id}/`, data),
  deletarCategoria:(id)         => api.delete(`/pdv/categorias/${id}/`),

  // Produtos
  listProdutos:   (params = {}) => api.get('/pdv/produtos/', { params }),
  getProduto:     (id)          => api.get(`/pdv/produtos/${id}/`),
  criarProduto:   (data)        => api.post('/pdv/produtos/', data),
  editarProduto:  (id, data)    => api.patch(`/pdv/produtos/${id}/`, data),
  deletarProduto: (id)          => api.delete(`/pdv/produtos/${id}/`),
  ativarProduto:  (id)          => api.post(`/pdv/produtos/${id}/ativar/`),
  desativarProduto:(id)         => api.post(`/pdv/produtos/${id}/desativar/`),

  // Pedidos
  listPedidos:    (params = {}) => api.get('/pdv/pedidos/', { params }),
  getPedido:      (id)          => api.get(`/pdv/pedidos/${id}/`),
  criarPedido:    (data)        => api.post('/pdv/pedidos/', data),
  confirmar:      (id)          => api.post(`/pdv/pedidos/${id}/confirmar/`),
  iniciarPreparo: (id)          => api.post(`/pdv/pedidos/${id}/iniciar-preparo/`),
  marcarPronto:   (id)          => api.post(`/pdv/pedidos/${id}/marcar-pronto/`),
  concluir:       (id)          => api.post(`/pdv/pedidos/${id}/concluir/`),
  cancelar:       (id)          => api.post(`/pdv/pedidos/${id}/cancelar/`),
  adicionarItem:  (id, data)    => api.post(`/pdv/pedidos/${id}/itens/`, data),
  removerItem:    (id, itemId)  => api.delete(`/pdv/pedidos/${id}/itens/${itemId}/remover/`),
  estatisticas:   ()            => api.get('/pdv/pedidos/estatisticas/'),
}


// ═══════════════════════════════════════════════════════════════════════════════
// PATCH 2: src/App.jsx
// ═══════════════════════════════════════════════════════════════════════════════

// 1. Adicione o import no topo:
import PDV from './pages/PDV'

// 2. Substitua a Route do PDV (que hoje usa <Placeholder>):
// DE:
//   <Route path="integracoes/pdv" element={<Placeholder title="PDV Próprio" />} />
// PARA:
//   <Route path="integracoes/pdv" element={<PDV />} />


// ═══════════════════════════════════════════════════════════════════════════════
// PATCH 3: src/components/layout/Sidebar.jsx
// Remova o `dot: true` do item PDV para não mostrar o badge de integração
// (PDV é nosso, não precisa do indicador de integração externa):
// ═══════════════════════════════════════════════════════════════════════════════

// DE:
//   { to: '/integracoes/pdv', icon: 'building-store', label: 'PDV Próprio' },
// Já está sem dot — nenhuma alteração necessária neste arquivo.
