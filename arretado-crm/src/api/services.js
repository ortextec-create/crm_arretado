import api from './client'

// ─── CLIENTES ───────────────────────────────────────────────────────────────

  // ─── ADIÇÃO AO arretado-crm/src/api/services.js ─────────────────────────────
// Adicione dentro de `clientesApi`, após `estatisticas`:

/*
  historico: (id, params = {}) => api.get(`/clientes/${id}/historico/`, { params }),
*/

// Versão completa do clientesApi com o método novo:
export const clientesApi = {
  list:            (params = {}) => api.get('/clientes/', { params }),
  get:             (id)          => api.get(`/clientes/${id}/`),
  create:          (data)        => api.post('/clientes/', data),
  update:          (id, data)    => api.patch(`/clientes/${id}/`, data),
  delete:          (id)          => api.delete(`/clientes/${id}/`),
  ativar:          (id)          => api.post(`/clientes/${id}/ativar/`),
  bloquear:        (id)          => api.post(`/clientes/${id}/bloquear/`),
  addEndereco:     (id, data)    => api.post(`/clientes/${id}/enderecos/`, data),
  updateEndereco:  (id, eid, d)  => api.patch(`/clientes/${id}/enderecos/${eid}/`, d),
  removeEndereco:  (id, eid)     => api.delete(`/clientes/${id}/enderecos/${eid}/remover/`),
  estatisticas:    ()            => api.get('/clientes/estatisticas/'),

  // ── FASE 3: Histórico unificado ──────────────────────────────────────────
  historico: (id, params = {}) => api.get(`/clientes/${id}/historico/`, { params }),
}

// ─── TAGS ───────────────────────────────────────────────────────────────────

export const tagsApi = {
  list: () => api.get('/tags/'),
  create: (data) => api.post('/tags/', data),
  update: (id, data) => api.patch(`/tags/${id}/`, data),
  delete: (id) => api.delete(`/tags/${id}/`),
}

// ─── AUTH (Django session / token) ──────────────────────────────────────────
// The backend uses DRF browsable API auth. For token auth, add
// rest_framework.authtoken to INSTALLED_APPS and expose /api/auth/token/.
// For now we use a local mock that stores credentials in localStorage.

export const authApi = {
  login: async (email, password) => {
    // Replace with real token endpoint when available:
    // return api.post('/auth/login/', { email, password })
    if (email && password) {
      const fakeUser = { id: 1, name: 'Edvan Santos', email, role: 'admin' }
      localStorage.setItem('auth_user', JSON.stringify(fakeUser))
      localStorage.setItem('auth_token', 'demo_token')
      return fakeUser
    }
    throw new Error('Credenciais inválidas')
  },
  logout: () => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
  },
  me: () => {
    const user = localStorage.getItem('auth_user')
    return user ? JSON.parse(user) : null
  },
}


// ─── IFOOD ──────────────────────────────────────────────────────────────────

export const ifoodApi = {
  // Config
  getConfig: ()           => api.get('/ifood/config/'),
  createConfig: (data)    => api.post('/ifood/config/', data),
  updateConfig: (id, data)=> api.patch(`/ifood/config/${id}/`, data),
  testarConexao: (id)     => api.post(`/ifood/config/${id}/testar/`),
  ativarPolling: (id)     => api.post(`/ifood/config/${id}/ativar-polling/`),
  pausarPolling: (id)     => api.post(`/ifood/config/${id}/pausar-polling/`),
  pollingManual: (id)     => api.post(`/ifood/config/${id}/polling-manual/`),
  statusGeral: ()         => api.get('/ifood/config/status/'),

  // Pedidos
  listPedidos: (params={})=> api.get('/ifood/pedidos/', { params }),
  getPedido: (id)         => api.get(`/ifood/pedidos/${id}/`),
  confirmar: (id)         => api.post(`/ifood/pedidos/${id}/confirmar/`),
  cancelar: (id, data)    => api.post(`/ifood/pedidos/${id}/cancelar/`, data),
  despachar: (id)         => api.post(`/ifood/pedidos/${id}/despachar/`),
  prontoRetirada: (id)    => api.post(`/ifood/pedidos/${id}/pronto-retirada/`),
  vincularCliente:(id,cid)=> api.post(`/ifood/pedidos/${id}/vincular-cliente/`, { cliente_id: cid }),
  motivosCancelamento:(id)=> api.get(`/ifood/pedidos/${id}/motivos-cancelamento/`),
  estatisticas: ()        => api.get('/ifood/pedidos/estatisticas/'),


}
