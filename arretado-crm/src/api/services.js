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
  // Configuração
  getConfig:      ()          => api.get('/ifood/config/'),
  createConfig:   (data)      => api.post('/ifood/config/', data),
  updateConfig:   (id, data)  => api.patch(`/ifood/config/${id}/`, data),
  statusGeral:    ()          => api.get('/ifood/config/status/'),
  testarConexao:  (id)        => api.post(`/ifood/config/${id}/testar/`),
  pollingManual:  (id)        => api.post(`/ifood/config/${id}/polling-manual/`),
  ativarPolling:  (id)        => api.post(`/ifood/config/${id}/ativar-polling/`),
  pausarPolling:  (id)        => api.post(`/ifood/config/${id}/pausar-polling/`),
  // Pedidos
  listPedidos:    (params={}) => api.get('/ifood/pedidos/', { params }),
  getPedido:      (id)        => api.get(`/ifood/pedidos/${id}/`),
  estatisticas:   ()          => api.get('/ifood/pedidos/estatisticas/'),
  confirmar:      (id)        => api.post(`/ifood/pedidos/${id}/confirmar/`),
  despachar:      (id)        => api.post(`/ifood/pedidos/${id}/despachar/`),
  prontoRetirada: (id)        => api.post(`/ifood/pedidos/${id}/pronto-retirada/`),
  concluir:       (id)        => api.post(`/ifood/pedidos/${id}/concluir/`),
  cancelar:       (id, data)  => api.post(`/ifood/pedidos/${id}/cancelar/`, data),
  motivosCancelamento: (id)   => api.get(`/ifood/pedidos/${id}/motivos-cancelamento/`),
  vincularCliente:(id, clienteId) => api.post(`/ifood/pedidos/${id}/vincular-cliente/`, { cliente_id: clienteId }),
  criarCliente:   (id)        => api.post(`/ifood/pedidos/${id}/criar-cliente/`),
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
  updateFoto:      (id, formData) => api.patch(`/pdv/produtos/${id}/`, formData, { headers: { 'Content-Type': undefined } }),
  removerFoto:     (id)        => api.patch(`/pdv/produtos/${id}/`, { foto: null }),
  listPedidos:     (params={}) => api.get('/pdv/pedidos/', { params }),
  getPedido:       (id)        => api.get(`/pdv/pedidos/${id}/`),
  criarPedido:     (data)      => api.post('/pdv/pedidos/', data),
  updatePedido:    (id, data)  => api.patch(`/pdv/pedidos/${id}/`, data),
  cancelarPedido:  (id)        => api.post(`/pdv/pedidos/${id}/cancelar/`),
  concluirPedido:  (id)        => api.post(`/pdv/pedidos/${id}/concluir/`),
  addItem:         (pedidoId, data)   => api.post(`/pdv/pedidos/${pedidoId}/itens/`, data),
  removeItem:      (pedidoId, itemId) => api.delete(`/pdv/pedidos/${pedidoId}/itens/${itemId}/remover/`),
  estatisticas:    ()                 => api.get('/pdv/pedidos/estatisticas/'),

  faixasPreco: {
    criar:     (produtoId, data)          => api.post(`/pdv/produtos/${produtoId}/faixas-preco/`, data),
    atualizar: (produtoId, faixaId, data) => api.patch(`/pdv/produtos/${produtoId}/faixas-preco/${faixaId}/`, data),
    remover:   (produtoId, faixaId)       => api.delete(`/pdv/produtos/${produtoId}/faixas-preco/${faixaId}/remover/`),
  },
  itensKit: {
    adicionar: (produtoId, data)    => api.post(`/pdv/produtos/${produtoId}/itens-kit/`, data),
    remover:   (produtoId, itemId)  => api.delete(`/pdv/produtos/${produtoId}/itens-kit/${itemId}/`),
  },
  precoPara: (produtoId, { quantidade, canal } = {}) =>
    api.get(`/pdv/produtos/${produtoId}/preco/`, { params: { quantidade, canal } }),
}

export const taxasEntregaApi = {
  list:   (params={}) => api.get('/pdv/taxas-entrega/', { params }),
  create: (data)      => api.post('/pdv/taxas-entrega/', data),
  update: (id, data)  => api.patch(`/pdv/taxas-entrega/${id}/`, data),
  remove: (id)        => api.delete(`/pdv/taxas-entrega/${id}/`),
}

export const configEntregaApi = {
  get:    ()     => api.get('/pdv/configuracao-entrega/1/'),
  update: (data) => api.patch('/pdv/configuracao-entrega/1/', data),
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
// O backend valida email + senha (hash bcrypt) e retorna um token real
// (Usuario.auth_token, validado por usuarios.authentication.TokenAuthentication),
// não mais um valor derivado do id.

export const authApi = {
  login: async (email, password) => {
    // Chama o endpoint real de autenticação
    const res = await api.post('/usuarios/login/', { email, password })
    const { token, ...user } = res.data

    // Persiste sessão no localStorage (mesmo padrão anterior)
    localStorage.setItem('auth_user', JSON.stringify(user))
    localStorage.setItem('auth_token', token)

    return user
  },

  logout: async () => {
    try {
      await api.post('/usuarios/logout/')
    } catch {
      // mesmo se o backend falhar, a sessão local é limpa de qualquer forma
    } finally {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_user')
    }
  },

  me: () => {
    const raw = localStorage.getItem('auth_user')
    return raw ? JSON.parse(raw) : null
  },
}

// ─── AUDITORIA (restrito a role=admin) ───────────────────────────────────────

export const auditoriaApi = {
  listar: (params = {}) => api.get('/auditoria/logs/', { params }),
}

// ─── NOTIFICAÇÕES WHATSAPP ────────────────────────────────────────────────────

export const notificacoesApi = {
  listar:         (params = {}) => api.get('/notificacoes/mensagens/', { params }),
  enviar:         (data)        => api.post('/notificacoes/mensagens/enviar/', data),
  statusConexao:  ()            => api.get('/notificacoes/mensagens/status-conexao/'),
}

export const configWhatsappApi = {
  get:    ()     => api.get('/notificacoes/configuracao/'),
  update: (data) => api.patch('/notificacoes/configuracao/', data),
  testar: ()     => api.post('/notificacoes/configuracao/testar/'),
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
  adicionarPagamento: (id, data, config={}) => api.post(`/eventos/${id}/pagamentos/`, data, config),
  removerPagamento:   (id, pagamentoId) => api.delete(`/eventos/${id}/pagamentos/${pagamentoId}/remover/`),
  agenda:          (mes)   => api.get('/eventos/agenda/', { params: { mes } }),
  estatisticas:    ()      => api.get('/eventos/estatisticas/'),
}

// ─── ORÇAMENTOS ──────────────────────────────────────────────────────────────

export const orcamentosApi = {
  list:            (params) => api.get('/eventos/orcamentos/', { params }),
  detail:          (id)     => api.get(`/eventos/orcamentos/${id}/`),
  create:          (data)   => api.post('/eventos/orcamentos/', data),
  update:          (id, d)  => api.patch(`/eventos/orcamentos/${id}/`, d),
  delete:          (id)     => api.delete(`/eventos/orcamentos/${id}/`),
  enviar:          (id)     => api.post(`/eventos/orcamentos/${id}/enviar/`),
  aprovar:         (id)     => api.post(`/eventos/orcamentos/${id}/aprovar/`),
  recusar:         (id)     => api.post(`/eventos/orcamentos/${id}/recusar/`),
  restaurar:       (id)     => api.post(`/eventos/orcamentos/${id}/restaurar/`),
  pdf:             (id)     => api.get(`/eventos/orcamentos/${id}/pdf/`, { responseType: 'blob' }),
  converterEmEvento: (id, data) => api.post(`/eventos/orcamentos/${id}/converter-em-evento/`, data),
  adicionarItem:   (id, data)   => api.post(`/eventos/orcamentos/${id}/itens/`, data),
  editarItem:      (id, itemId, data) => api.patch(`/eventos/orcamentos/${id}/itens/${itemId}/editar/`, data),
  removerItem:     (id, itemId) => api.delete(`/eventos/orcamentos/${id}/itens/${itemId}/remover/`),
  adicionarImagens: (id, formData) => api.post(`/eventos/orcamentos/${id}/imagens/`, formData, {
    headers: { 'Content-Type': undefined },
  }),
  removerImagem:    (id, imgId)    => api.delete(`/eventos/orcamentos/${id}/imagens/${imgId}/remover/`),
  enviarWhatsApp:  (id, data)   => api.post(`/eventos/orcamentos/${id}/enviar-whatsapp/`, data),
  gerarContrato:   (id, data)   => api.post(`/eventos/orcamentos/${id}/gerar-contrato/`, data),
}

// ─── CONTRATOS ───────────────────────────────────────────────────────────────

export const contratosApi = {
  list:           (params) => api.get('/eventos/contratos/', { params }),
  detail:         (id)     => api.get(`/eventos/contratos/${id}/`),
  pdf:            (id)     => api.get(`/eventos/contratos/${id}/pdf/`, { responseType: 'blob' }),
  enviarWhatsApp: (id, data) => api.post(`/eventos/contratos/${id}/enviar-whatsapp/`, data),
}

export const configContratoApi = {
  get:    ()     => api.get('/eventos/configuracao-contrato/1/'),
  update: (data) => api.patch('/eventos/configuracao-contrato/1/', data),
}

// ─── FICHAS / PRECIFICAÇÃO ────────────────────────────────────────────────────

export const fichasApi = {
  // Matérias-primas
  listarMaterias:        (params) => api.get('/fichas/materias-primas/', { params }),
  getMateriaDetalhe:     (id)     => api.get(`/fichas/materias-primas/${id}/`),
  criarMateria:          (data)   => api.post('/fichas/materias-primas/', data),
  atualizarMateria:      (id, d)  => api.patch(`/fichas/materias-primas/${id}/`, d),
  atualizarPrecoMateria: (id, d)  => api.post(`/fichas/materias-primas/${id}/atualizar-preco/`, d),

  // Fichas técnicas
  listarFichas:   (params) => api.get('/fichas/fichas/', { params }),
  detalharFicha:  (id)     => api.get(`/fichas/fichas/${id}/`),
  criarFicha:     (data)   => api.post('/fichas/fichas/', data),
  atualizarFicha: (id, d)  => api.patch(`/fichas/fichas/${id}/`, d),
  resumoFicha:    (id)     => api.get(`/fichas/fichas/${id}/resumo/`),
  adicionarItemFicha: (id, d)   => api.post(`/fichas/fichas/${id}/adicionar-item/`, d),
  removerItemFicha:   (id, iid) => api.delete(`/fichas/fichas/${id}/remover-item/${iid}/`),

  // Parâmetros do negócio
  getParametros:    ()     => api.get('/fichas/parametros/1/'),
  salvarParametros: (data) => api.patch('/fichas/parametros/1/', data),

  // Ajuste linear
  previewAjuste:  (data) => api.post('/fichas/ajuste-linear/', { ...data, confirmar: false }),
  aplicarAjuste:  (data) => api.post('/fichas/ajuste-linear/', { ...data, confirmar: true }),
  desfazerAjuste: (id)   => api.post(`/fichas/desfazer-ajuste/${id}/`),

  // Snapshots
  listarSnapshots: (params) => api.get('/fichas/snapshots/', { params }),

  // Produtos (para semáforo — reutiliza pdvApi mas com segmento)
  listarProdutos:  (params) => api.get('/pdv/produtos/', { params }),
  atualizarProduto:(id, d)  => api.patch(`/pdv/produtos/${id}/`, d),
}

// ─── RELATÓRIOS ───────────────────────────────────────────────────────────────

export const relatoriosApi = {
  ifood: (params = {}) => api.get('/relatorios/ifood/', { params }),
}

// ─── DASHBOARD ────────────────────────────────────────────────────────────────

export const dashboardApi = {
  resumo: () => api.get('/dashboard/resumo/'),
}