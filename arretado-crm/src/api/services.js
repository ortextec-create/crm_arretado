import api from './client'

// ─── CLIENTES ───────────────────────────────────────────────────────────────

export const clientesApi = {
  list:           (params = {}) => api.get('/clientes/', { params }),
  get:            (id)          => api.get(`/clientes/${id}/`),
  create:         (data)        => api.post('/clientes/', data),
  update:         (id, data)    => api.patch(`/clientes/${id}/`, data),
  delete:         (id)          => api.delete(`/clientes/${id}/`),
  ativar:         (id)          => api.post(`/clientes/${id}/ativar/`),
  bloquear:       (id)          => api.post(`/clientes/${id}/bloquear/`),
  addEndereco:    (id, data)    => api.post(`/clientes/${id}/enderecos/`, data),
  updateEndereco: (id, eid, d)  => api.patch(`/clientes/${id}/enderecos/${eid}/`, d),
  removeEndereco: (id, eid)     => api.delete(`/clientes/${id}/enderecos/${eid}/remover/`),
  estatisticas:   ()            => api.get('/clientes/estatisticas/'),
  historico: (id, params = {}) => api.get(`/clientes/${id}/historico/`, { params }),
}

// ─── TAGS ───────────────────────────────────────────────────────────────────

export const tagsApi = {
  list:   ()         => api.get('/tags/'),
  create: (data)     => api.post('/tags/', data),
  update: (id, data) => api.patch(`/tags/${id}/`, data),
  delete: (id)       => api.delete(`/tags/${id}/`),
}

// ─── IFOOD ──────────────────────────────────────────────────────────────────

export const ifoodApi = {
  getConfig:      ()          => api.get('/ifood/config/'),
  createConfig:   (data)      => api.post('/ifood/config/', data),
  updateConfig:   (id, data)  => api.patch(`/ifood/config/${id}/`, data),
  listPedidos:    (params={}) => api.get('/ifood/pedidos/', { params }),
  getPedido:      (id)        => api.get(`/ifood/pedidos/${id}/`),
  confirmar:      (id)        => api.post(`/ifood/pedidos/${id}/confirmar/`),
  despachar:      (id)        => api.post(`/ifood/pedidos/${id}/despachar/`),
  concluir:       (id)        => api.post(`/ifood/pedidos/${id}/concluir/`),
  cancelar:       (id, data)  => api.post(`/ifood/pedidos/${id}/cancelar/`, data),
  statusPolling:  ()          => api.get('/ifood/polling/status/'),
  triggerPolling: ()          => api.post('/ifood/polling/trigger/'),
  aceitarNegociacao: (id)     => api.post(`/ifood/pedidos/${id}/aceitar-negociacao/`),
  recusarNegociacao: (id)     => api.post(`/ifood/pedidos/${id}/recusar-negociacao/`),
}

// ─── PDV ────────────────────────────────────────────────────────────────────

export const pdvApi = {
  listCategorias:  (params={}) => api.get('/pdv/categorias/', { params }),
  criarCategoria:  (data)      => api.post('/pdv/categorias/', data),
  updateCategoria: (id, data)  => api.patch(`/pdv/categorias/${id}/`, data),
  deleteCategoria: (id)        => api.delete(`/pdv/categorias/${id}/`),
  listProdutos:    (params={}) => api.get('/pdv/produtos/', { params }),
  getProduto:      (id)        => api.get(`/pdv/produtos/${id}/`),
  criarProduto:    (data)      => api.post('/pdv/produtos/', data),
  updateProduto:   (id, data)  => api.patch(`/pdv/produtos/${id}/`, data),
  deleteProduto:   (id)        => api.delete(`/pdv/produtos/${id}/`),
  listPedidos:     (params={}) => api.get('/pdv/pedidos/', { params }),
  getPedido:       (id)        => api.get(`/pdv/pedidos/${id}/`),
  criarPedido:     (data)      => api.post('/pdv/pedidos/', data),
  updatePedido:    (id, data)  => api.patch(`/pdv/pedidos/${id}/`, data),
  cancelarPedido:  (id)        => api.post(`/pdv/pedidos/${id}/cancelar/`),
  concluirPedido:  (id)        => api.post(`/pdv/pedidos/${id}/concluir/`),
  addItem:         (pedidoId, data)   => api.post(`/pdv/pedidos/${pedidoId}/itens/`, data),
  removeItem:      (pedidoId, itemId) => api.delete(`/pdv/pedidos/${pedidoId}/itens/${itemId}/remover/`),
  estatisticas:    ()                 => api.get('/pdv/pedidos/estatisticas/'),
}

// ─── PEDIDOS UNIFICADOS ──────────────────────────────────────────────────────

export const pedidosApi = {
  listar:          (params = {}) => api.get('/pedidos/', { params }),
  detalhe:         (id)          => api.get(`/pedidos/${id}/`),
  semCliente:      ()            => api.get('/pedidos/sem-cliente/'),
  vincularCliente: (pedidoId, clienteId) =>
    api.post(`/pedidos/${pedidoId}/vincular-cliente/`, { cliente_id: clienteId }),
}

// ─── USUÁRIOS ────────────────────────────────────────────────────────────────

export const usuariosApi = {
  listar:              (params = {}) => api.get('/usuarios/', { params }),
  criar:               (data)        => api.post('/usuarios/', data),
  atualizar:           (id, data)    => api.patch(`/usuarios/${id}/`, data),
  atualizarPermissoes: (id, perms)   => api.patch(`/usuarios/${id}/`, { perms }),
  remover:             (id)          => api.delete(`/usuarios/${id}/`),
  redefinirSenha:      (id, password) => api.post(`/usuarios/${id}/redefinir-senha/`, { password }),
}

// ─── AUTH ─────────────────────────────────────────────────────────────────────
// Conectado ao endpoint real: POST /api/v1/usuarios/login/
// O backend valida email + senha (hash bcrypt), retorna os dados do usuário ou 401.

export const authApi = {
  login: async (email, password) => {
    // Chama o endpoint real de autenticação
    const res = await api.post('/usuarios/login/', { email, password })
    const user = res.data

    // Persiste sessão no localStorage (mesmo padrão anterior)
    localStorage.setItem('auth_user', JSON.stringify(user))
    // Token simples baseado no id — em produção substituir por JWT ou DRF Token
    localStorage.setItem('auth_token', `user_${user.id}`)

    return user
  },

  logout: () => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
  },

  me: () => {
    const raw = localStorage.getItem('auth_user')
    return raw ? JSON.parse(raw) : null
  },
}

// ─── EVENTOS ─────────────────────────────────────────────────────────────────

export const locaisEventoApi = {
  list:   (params) => api.get('/eventos/locais/', { params }),
  create: (data)   => api.post('/eventos/locais/', data),
  update: (id, d)  => api.patch(`/eventos/locais/${id}/`, d),
  remove: (id)     => api.delete(`/eventos/locais/${id}/`),
}

export const eventosApi = {
  list:            (params) => api.get('/eventos/', { params }),
  detail:          (id)     => api.get(`/eventos/${id}/`),
  create:          (data)   => api.post('/eventos/', data),
  update:          (id, d)  => api.patch(`/eventos/${id}/`, d),
  confirmar:       (id)     => api.post(`/eventos/${id}/confirmar/`),
  iniciarProducao: (id)     => api.post(`/eventos/${id}/iniciar-producao/`),
  marcarPronto:    (id)     => api.post(`/eventos/${id}/marcar-pronto/`),
  entregar:        (id)     => api.post(`/eventos/${id}/entregar/`),
  cancelar:        (id)     => api.post(`/eventos/${id}/cancelar/`),
  adicionarItem:   (id, data)   => api.post(`/eventos/${id}/itens/`, data),
  removerItem:     (id, itemId) => api.delete(`/eventos/${id}/itens/${itemId}/remover/`),
  agenda:          (mes)   => api.get('/eventos/agenda/', { params: { mes } }),
  estatisticas:    ()      => api.get('/eventos/estatisticas/'),
}