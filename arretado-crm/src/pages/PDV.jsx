import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import styles from './PDV.module.css'
import { pdvApi, clientesApi } from '../api/services'

// ─── Helpers ─────────────────────────────────────────────────────────────────

const fmtMoeda = v => `R$ ${Number(v || 0).toFixed(2)}`
const fmtTime  = s => s ? new Date(s).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '—'
const fmtData  = s => s ? new Date(s).toLocaleDateString('pt-BR') : '—'

const STATUS_CFG = {
  aberto:     { label: 'Aberto',     color: '#3B82F6', icon: 'circle-dot' },
  confirmado: { label: 'Confirmado', color: '#8B5CF6', icon: 'circle-check' },
  em_preparo: { label: 'Em preparo', color: '#F59E0B', icon: 'flame' },
  pronto:     { label: 'Pronto',     color: '#10B981', icon: 'bell-ringing' },
  concluido:  { label: 'Concluído',  color: '#6B7280', icon: 'circle-check-filled' },
  cancelado:  { label: 'Cancelado',  color: '#EF4444', icon: 'circle-x' },
}

const TIPO_CFG = {
  balcao:   { label: 'Balcão',   icon: 'building-store' },
  retirada: { label: 'Retirada', icon: 'home' },
  delivery: { label: 'Delivery', icon: 'motorbike' },
  mesa:     { label: 'Mesa',     icon: 'armchair' },
}

// ─── Toast ────────────────────────────────────────────────────────────────────

function Toast({ toast, onClose }) {
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(onClose, 3500)
    return () => clearTimeout(t)
  }, [toast, onClose])
  if (!toast) return null
  return (
    <div className={`${styles.toast} ${toast.type === 'error' ? styles.toastError : styles.toastSuccess}`}>
      <i className={`ti ti-${toast.type === 'error' ? 'alert-circle' : 'check'}`} />
      {toast.message}
    </div>
  )
}

// ─── Kanban Card ──────────────────────────────────────────────────────────────

function PedidoCard({ pedido, onCard, onAcao }) {
  const [loadingAcao, setLoadingAcao] = useState(false)
  const tc = TIPO_CFG[pedido.tipo]     || { label: pedido.tipo,   icon: 'circle' }
  const sc = STATUS_CFG[pedido.status] || { label: pedido.status, color: '#9CA3AF', icon: 'circle' }

  let primaryAcao = null
  if      (pedido.pode_confirmar)             primaryAcao = { label: 'Confirmar',       fn: pdvApi.confirmar,      cls: styles.acaoConfirmar }
  else if (pedido.status === 'confirmado')    primaryAcao = { label: 'Iniciar Preparo',  fn: pdvApi.iniciarPreparo, cls: styles.acaoPreparo   }
  else if (pedido.status === 'em_preparo')    primaryAcao = { label: 'Marcar Pronto',    fn: pdvApi.marcarPronto,   cls: styles.acaoPronto    }
  else if (pedido.pode_concluir)              primaryAcao = { label: 'Concluir',         fn: pdvApi.concluir,       cls: styles.acaoConcluir  }

  const handleAcao = async (e) => {
    e.stopPropagation()
    setLoadingAcao(true)
    await onAcao(primaryAcao.fn, pedido)
    setLoadingAcao(false)
  }

  return (
    <div className={styles.card} onClick={() => onCard(pedido)}>
      <div className={styles.cardHead}>
        <span className={styles.cardNum}>#{pedido.numero}</span>
        <span className={styles.cardTipo}>
          <i className={`ti ti-${tc.icon}`} /> {tc.label}
        </span>
        <span className={styles.cardTime}>{fmtTime(pedido.criado_em)}</span>
      </div>

      <div className={styles.cardCliente}>
        {pedido.cliente_nome_crm || pedido.cliente_nome || 'Cliente avulso'}
        {pedido.cliente_nome_crm && (
          <span className={styles.crmTag}><i className="ti ti-link" /></span>
        )}
      </div>

      <div className={styles.cardMeta}>
        <span className={styles.cardItens}>
          {pedido.itens?.length ?? 0} {pedido.itens?.length === 1 ? 'item' : 'itens'}
        </span>
        <span className={styles.cardValor}>{fmtMoeda(pedido.total)}</span>
      </div>

      {primaryAcao ? (
        <button
          className={`${styles.cardAcao} ${primaryAcao.cls}`}
          onClick={handleAcao}
          disabled={loadingAcao}
        >
          {loadingAcao
            ? <><i className="ti ti-loader-2 spin" /> Aguarde…</>
            : primaryAcao.label
          }
        </button>
      ) : (
        <div className={styles.cardStatus} style={{ color: sc.color }}>
          <i className={`ti ti-${sc.icon}`} /> {sc.label}
        </div>
      )}
    </div>
  )
}

// ─── Kanban Column ────────────────────────────────────────────────────────────

function KanbanCol({ title, accentColor, icon, pedidos, onCard, onAcao, emptyMsg }) {
  return (
    <div className={styles.kanbanCol}>
      <div className={styles.colHeader} style={{ borderTopColor: accentColor }}>
        <i className={`ti ti-${icon}`} style={{ color: accentColor, fontSize: 15 }} />
        <span className={styles.colTitle}>{title}</span>
        {pedidos.length > 0 && (
          <span className={styles.colCount} style={{ background: accentColor + '22', color: accentColor }}>
            {pedidos.length}
          </span>
        )}
      </div>
      <div className={styles.colCards}>
        {pedidos.length === 0 ? (
          <div className={styles.colEmpty}>
            <i className={`ti ti-${icon}`} style={{ opacity: 0.2, fontSize: 24 }} />
            <span>{emptyMsg}</span>
          </div>
        ) : (
          pedidos.map(p => (
            <PedidoCard key={p.id} pedido={p} onCard={onCard} onAcao={onAcao} />
          ))
        )}
      </div>
    </div>
  )
}

// ─── Modal: Novo Pedido ───────────────────────────────────────────────────────

function ModalNovoPedido({ produtos, categorias, clientes, onClose, onSaved, showToast }) {
  const [form, setForm] = useState({
    tipo: 'balcao', pagamento: 'pix', desconto: 0, taxa_entrega: 0,
    cliente: '', cliente_nome: '', cliente_telefone: '', observacoes: '',
  })
  const [itens, setItens]                   = useState([])
  const [catFilter, setCatFilter]           = useState(null)
  const [search, setSearch]                 = useState('')
  const [saving, setSaving]                 = useState(false)
  const [clienteSearch, setClienteSearch]   = useState('')

  const prodsFiltrados = produtos.filter(p =>
    p.ativo &&
    (!catFilter || p.categoria === catFilter) &&
    (!search || p.nome.toLowerCase().includes(search.toLowerCase()))
  )

  const adicionarItem = (prod) => {
    setItens(prev => {
      const idx = prev.findIndex(i => i.produto === prod.id)
      if (idx >= 0) {
        const novo = [...prev]
        novo[idx] = { ...novo[idx], quantidade: novo[idx].quantidade + 1 }
        return novo
      }
      return [...prev, { produto: prod.id, nome: prod.nome, preco_unit: prod.preco, quantidade: 1, observacao: '' }]
    })
  }

  const removerItem = (idx) => setItens(prev => prev.filter((_, i) => i !== idx))

  const alterarQtd = (idx, delta) => setItens(prev => {
    const novo = [...prev]
    const nova = novo[idx].quantidade + delta
    if (nova <= 0) return prev.filter((_, i) => i !== idx)
    novo[idx] = { ...novo[idx], quantidade: nova }
    return novo
  })

  const subtotal = itens.reduce((s, i) => s + Number(i.preco_unit) * i.quantidade, 0)
  const total    = subtotal - Number(form.desconto || 0) + Number(form.taxa_entrega || 0)

  const salvar = async () => {
    if (itens.length === 0) { showToast('Adicione ao menos um item.', 'error'); return }
    setSaving(true)
    try {
      const payload = {
        ...form,
        cliente: form.cliente || null,
        itens: itens.map(i => ({
          produto:    i.produto,
          nome:       i.nome,
          preco_unit: i.preco_unit,
          quantidade: i.quantidade,
          observacao: i.observacao,
        })),
      }
      await pdvApi.criarPedido(payload)
      showToast('Pedido criado com sucesso!', 'success')
      onSaved()
      onClose()
    } catch {
      showToast('Erro ao criar pedido.', 'error')
    } finally {
      setSaving(false)
    }
  }

  const clientesFiltrados = clientes.filter(c =>
    !clienteSearch || c.nome.toLowerCase().includes(clienteSearch.toLowerCase()) ||
    c.telefone_principal?.includes(clienteSearch)
  ).slice(0, 6)

  return (
    <div className={styles.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className={styles.modalNovo}>

        <div className={styles.modalHeader}>
          <span className={styles.modalTitle}>
            <i className="ti ti-receipt-2" /> Novo Pedido PDV
          </span>
          <button className={styles.closeBtn} onClick={onClose}><i className="ti ti-x" /></button>
        </div>

        <div className={styles.modalNovoCols}>

          {/* Col Esquerda: Catálogo */}
          <div className={styles.catalogo}>
            <div className={styles.catalogoSearch}>
              <i className="ti ti-search" />
              <input
                placeholder="Buscar produto…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
            <div className={styles.catTabs}>
              <button
                className={`${styles.catTab} ${!catFilter ? styles.catTabActive : ''}`}
                onClick={() => setCatFilter(null)}
              >Todos</button>
              {categorias.map(c => (
                <button
                  key={c.id}
                  className={`${styles.catTab} ${catFilter === c.id ? styles.catTabActive : ''}`}
                  onClick={() => setCatFilter(catFilter === c.id ? null : c.id)}
                >{c.nome}</button>
              ))}
            </div>
            <div className={styles.prodGrid}>
              {prodsFiltrados.map(p => (
                <div key={p.id} className={styles.prodCard} onClick={() => adicionarItem(p)}>
                  <p className={styles.prodNome}>{p.nome}</p>
                  <p className={styles.prodPreco}>{fmtMoeda(p.preco)}</p>
                </div>
              ))}
              {prodsFiltrados.length === 0 && (
                <p className={styles.emptySmall}>Nenhum produto encontrado.</p>
              )}
            </div>
          </div>

          {/* Col Direita: Carrinho + Dados */}
          <div className={styles.carrinho}>

            <div className={styles.itensList}>
              {itens.length === 0
                ? <p className={styles.emptySmall} style={{ padding: '24px 0', textAlign: 'center' }}>
                    Clique em um produto para adicionar.
                  </p>
                : itens.map((item, idx) => (
                  <div key={idx} className={styles.itemRow}>
                    <div className={styles.itemNome}>{item.nome}</div>
                    <div className={styles.itemCtrl}>
                      <button onClick={() => alterarQtd(idx, -1)}><i className="ti ti-minus" /></button>
                      <span>{item.quantidade}</span>
                      <button onClick={() => alterarQtd(idx, +1)}><i className="ti ti-plus" /></button>
                    </div>
                    <div className={styles.itemPreco}>{fmtMoeda(Number(item.preco_unit) * item.quantidade)}</div>
                    <button className={styles.itemDel} onClick={() => removerItem(idx)}>
                      <i className="ti ti-trash" />
                    </button>
                  </div>
                ))
              }
            </div>

            <div className={styles.totaisBox}>
              <div className={styles.totaisRow}><span>Subtotal</span><span>{fmtMoeda(subtotal)}</span></div>
              <div className={styles.totaisRow}>
                <span>Desconto</span>
                <input type="number" min="0" step="0.01"
                  value={form.desconto}
                  onChange={e => setForm(f => ({ ...f, desconto: e.target.value }))}
                  className={styles.totaisInput}
                />
              </div>
              <div className={styles.totaisRow}>
                <span>Taxa de entrega</span>
                <input type="number" min="0" step="0.01"
                  value={form.taxa_entrega}
                  onChange={e => setForm(f => ({ ...f, taxa_entrega: e.target.value }))}
                  className={styles.totaisInput}
                />
              </div>
              <div className={`${styles.totaisRow} ${styles.totaisTotal}`}>
                <span>Total</span><span>{fmtMoeda(total)}</span>
              </div>
            </div>

            <div className={styles.dadosPedido}>
              <div className={styles.dadosRow}>
                <label>Tipo</label>
                <select value={form.tipo} onChange={e => setForm(f => ({ ...f, tipo: e.target.value }))}>
                  <option value="balcao">Balcão</option>
                  <option value="retirada">Retirada</option>
                  <option value="delivery">Delivery</option>
                  <option value="mesa">Mesa</option>
                </select>
              </div>
              <div className={styles.dadosRow}>
                <label>Pagamento</label>
                <select value={form.pagamento} onChange={e => setForm(f => ({ ...f, pagamento: e.target.value }))}>
                  <option value="dinheiro">Dinheiro</option>
                  <option value="pix">PIX</option>
                  <option value="credito">Cartão de Crédito</option>
                  <option value="debito">Cartão de Débito</option>
                  <option value="outro">Outro</option>
                </select>
              </div>
              <div className={styles.dadosRow}>
                <label>Cliente (CRM)</label>
                <div className={styles.clienteSearch}>
                  <input
                    placeholder="Buscar no CRM…"
                    value={clienteSearch}
                    onChange={e => { setClienteSearch(e.target.value); setForm(f => ({ ...f, cliente: '' })) }}
                  />
                  {clienteSearch && !form.cliente && (
                    <div className={styles.clienteDropdown}>
                      {clientesFiltrados.map(c => (
                        <div key={c.id} className={styles.clienteOption}
                          onClick={() => {
                            setForm(f => ({ ...f, cliente: c.id, cliente_nome: c.nome, cliente_telefone: c.telefone_principal }))
                            setClienteSearch(c.nome)
                          }}
                        >
                          <span>{c.nome}</span>
                          <span style={{ fontSize: 11, color: 'var(--muted)' }}>{c.telefone_principal}</span>
                        </div>
                      ))}
                      {clientesFiltrados.length === 0 && <div className={styles.clienteOption} style={{ color: 'var(--muted)' }}>Nenhum encontrado</div>}
                    </div>
                  )}
                </div>
              </div>
              {!form.cliente && (
                <>
                  <div className={styles.dadosRow}>
                    <label>Nome avulso</label>
                    <input placeholder="Nome do cliente" value={form.cliente_nome}
                      onChange={e => setForm(f => ({ ...f, cliente_nome: e.target.value }))} />
                  </div>
                  <div className={styles.dadosRow}>
                    <label>Telefone</label>
                    <input placeholder="(86) 9 9999-9999" value={form.cliente_telefone}
                      onChange={e => setForm(f => ({ ...f, cliente_telefone: e.target.value }))} />
                  </div>
                </>
              )}
              <div className={styles.dadosRow}>
                <label>Observações</label>
                <textarea rows={2} value={form.observacoes}
                  onChange={e => setForm(f => ({ ...f, observacoes: e.target.value }))} />
              </div>
            </div>

            <button className={styles.btnCriar} onClick={salvar} disabled={saving}>
              {saving ? <i className="ti ti-loader-2 spin" /> : <i className="ti ti-check" />}
              {saving ? 'Salvando…' : 'Criar Pedido'}
            </button>

          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Modal: Detalhe do Pedido ─────────────────────────────────────────────────

function ModalDetalhe({ pedido, onClose, onUpdated, showToast }) {
  const navigate      = useNavigate()
  const [loading, setLoading] = useState(false)
  const sc = STATUS_CFG[pedido.status] || { label: pedido.status, color: '#9CA3AF', icon: 'circle' }
  const tc = TIPO_CFG[pedido.tipo]     || { label: pedido.tipo,   icon: 'circle' }

  const acao = async (endpoint) => {
    setLoading(true)
    try {
      await endpoint(pedido.id)
      showToast('Status atualizado!', 'success')
      onUpdated()
      onClose()
    } catch {
      showToast('Erro ao atualizar status.', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className={styles.modalDetalhe}>
        <div className={styles.modalHeader}>
          <span className={styles.modalTitle}>
            <i className="ti ti-receipt" /> Pedido #{pedido.numero}
          </span>
          <button className={styles.closeBtn} onClick={onClose}><i className="ti ti-x" /></button>
        </div>

        <div className={styles.detalheBody}>
          <div className={styles.detalheRow}>
            <span className={styles.statusBadge} style={{ background: sc.color + '22', color: sc.color, border: `0.5px solid ${sc.color}44` }}>
              <i className={`ti ti-${sc.icon}`} />{sc.label}
            </span>
            <span className={styles.tipoBadge}>
              <i className={`ti ti-${tc.icon}`} />{tc.label}
            </span>
            <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 'auto' }}>
              {fmtData(pedido.criado_em)} {fmtTime(pedido.criado_em)}
            </span>
          </div>

          {(pedido.cliente_nome_crm || pedido.cliente_nome) && (
            <div className={styles.detalheSection}>
              <span className={styles.detalheLabel}>Cliente</span>
              <p>{pedido.cliente_nome_crm || pedido.cliente_nome}</p>
              {pedido.cliente_telefone && <p style={{ color: 'var(--muted)', fontSize: 12 }}>{pedido.cliente_telefone}</p>}
              {pedido.cliente && (
                <button className={styles.crmLink} onClick={() => navigate(`/clientes/${pedido.cliente}`)}>
                  <i className="ti ti-external-link" /> Ver no CRM
                </button>
              )}
            </div>
          )}

          {pedido.itens?.length > 0 && (
            <div className={styles.detalheSection}>
              <span className={styles.detalheLabel}>Itens</span>
              {pedido.itens.map(item => (
                <div key={item.id} className={styles.detalheItem}>
                  <span className={styles.detalheItemQty}>{item.quantidade}x</span>
                  <span style={{ flex: 1 }}>{item.nome}</span>
                  <span>{fmtMoeda(item.preco_total)}</span>
                </div>
              ))}
            </div>
          )}

          <div className={styles.detalheTotais}>
            <div className={styles.totaisRow}><span>Subtotal</span><span>{fmtMoeda(pedido.subtotal)}</span></div>
            {Number(pedido.desconto) > 0 && (
              <div className={styles.totaisRow} style={{ color: 'var(--verde)' }}>
                <span>Desconto</span><span>- {fmtMoeda(pedido.desconto)}</span>
              </div>
            )}
            {Number(pedido.taxa_entrega) > 0 && (
              <div className={styles.totaisRow}><span>Taxa de entrega</span><span>{fmtMoeda(pedido.taxa_entrega)}</span></div>
            )}
            <div className={`${styles.totaisRow} ${styles.totaisTotal}`}>
              <span>Total</span><span>{fmtMoeda(pedido.total)}</span>
            </div>
            {pedido.pagamento_display && (
              <div className={styles.totaisRow} style={{ color: 'var(--muted)', fontSize: 12 }}>
                <span>Pagamento</span><span>{pedido.pagamento_display}</span>
              </div>
            )}
          </div>

          {pedido.observacoes && (
            <div className={styles.detalheSection}>
              <span className={styles.detalheLabel}>Observações</span>
              <p style={{ fontSize: 13, color: 'var(--muted)' }}>{pedido.observacoes}</p>
            </div>
          )}

          <div className={styles.detalheAcoes}>
            {pedido.pode_confirmar && (
              <button className={`${styles.btnAcao} ${styles.btnConfirmar}`} disabled={loading}
                onClick={() => acao(pdvApi.confirmar)}>
                <i className="ti ti-circle-check" /> Confirmar
              </button>
            )}
            {pedido.status === 'confirmado' && (
              <button className={`${styles.btnAcao} ${styles.btnPreparo}`} disabled={loading}
                onClick={() => acao(pdvApi.iniciarPreparo)}>
                <i className="ti ti-flame" /> Iniciar Preparo
              </button>
            )}
            {pedido.status === 'em_preparo' && (
              <button className={`${styles.btnAcao} ${styles.btnPronto}`} disabled={loading}
                onClick={() => acao(pdvApi.marcarPronto)}>
                <i className="ti ti-bell-ringing" /> Marcar Pronto
              </button>
            )}
            {pedido.pode_concluir && (
              <button className={`${styles.btnAcao} ${styles.btnConcluir}`} disabled={loading}
                onClick={() => acao(pdvApi.concluir)}>
                <i className="ti ti-check" /> Concluir
              </button>
            )}
            {pedido.pode_cancelar && (
              <button className={`${styles.btnAcao} ${styles.btnCancelar}`} disabled={loading}
                onClick={() => acao(pdvApi.cancelar)}>
                <i className="ti ti-circle-x" /> Cancelar
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Página principal ─────────────────────────────────────────────────────────

export default function PDV() {
  const [search,     setSearch]     = useState('')
  const [pedidos,    setPedidos]    = useState([])
  const [stats,      setStats]      = useState(null)
  const [loading,    setLoading]    = useState(true)
  const [produtos,   setProdutos]   = useState([])
  const [categorias, setCategorias] = useState([])
  const [clientes,   setClientes]   = useState([])
  const [selected,   setSelected]   = useState(null)
  const [showNovo,   setShowNovo]   = useState(false)
  const [toast,      setToast]      = useState(null)
  const pollRef = useRef(null)

  const showToast = (message, type = 'success') => setToast({ message, type })

  const loadPedidos = useCallback(async () => {
    try {
      const [pedRes, statsRes] = await Promise.allSettled([
        pdvApi.listPedidos({ page_size: 200 }),
        pdvApi.estatisticas(),
      ])
      const lista = pedRes.status === 'fulfilled' ? (pedRes.value.data.results ?? pedRes.value.data) : []
      setPedidos(lista)
      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data)
    } catch { /* silêncio */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    Promise.allSettled([
      pdvApi.listProdutos({ ativo: 'true', page_size: 200 }),
      pdvApi.listCategorias(),
      clientesApi.list({ status: 'ativo', page_size: 300 }),
    ]).then(([prods, cats, clis]) => {
      if (prods.status === 'fulfilled') setProdutos(prods.value.data.results ?? prods.value.data)
      if (cats.status === 'fulfilled')  setCategorias(cats.value.data.results ?? cats.value.data)
      if (clis.status === 'fulfilled')  setClientes(clis.value.data.results ?? clis.value.data)
    })
  }, [])

  useEffect(() => {
    setLoading(true)
    loadPedidos()
  }, [loadPedidos])

  useEffect(() => {
    pollRef.current = setInterval(loadPedidos, 30_000)
    return () => clearInterval(pollRef.current)
  }, [loadPedidos])

  const onAcao = async (fn, pedido) => {
    try {
      await fn(pedido.id)
      showToast('Status atualizado!', 'success')
      await loadPedidos()
    } catch {
      showToast('Erro ao atualizar status.', 'error')
    }
  }

  const filtrar = useCallback((arr) => {
    if (!search.trim()) return arr
    const s = search.toLowerCase()
    return arr.filter(p =>
      p.numero?.toString().includes(s) ||
      (p.cliente_nome_crm || '').toLowerCase().includes(s) ||
      (p.cliente_nome     || '').toLowerCase().includes(s) ||
      (p.cliente_telefone || '').includes(s)
    )
  }, [search])

  const abertos     = filtrar(pedidos.filter(p => p.status === 'aberto'))
  const emAndamento = filtrar(pedidos.filter(p => ['confirmado', 'em_preparo'].includes(p.status)))
  const prontos     = filtrar(pedidos.filter(p => p.status === 'pronto'))
  const historico   = filtrar(pedidos.filter(p => ['concluido', 'cancelado'].includes(p.status)))

  const nConcluidos = historico.filter(p => p.status === 'concluido').length
  const nCancelados = historico.filter(p => p.status === 'cancelado').length
  const nAtivos     = pedidos.filter(p => !['concluido', 'cancelado'].includes(p.status)).length

  return (
    <div className={styles.page}>
      <Toast toast={toast} onClose={() => setToast(null)} />

      {/* ── Header ── */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h1 className={styles.headerTitle}>
            <i className="ti ti-building-store" /> PDV
          </h1>
          <div className={styles.searchBox}>
            <i className="ti ti-search" />
            <input
              placeholder="Buscar pedido ou cliente…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
            {search && (
              <button className={styles.searchClear} onClick={() => setSearch('')}>
                <i className="ti ti-x" />
              </button>
            )}
          </div>
        </div>

        {stats && (
          <div className={styles.statsInline}>
            <span className={styles.statChip}>
              <i className="ti ti-receipt" /> {stats.hoje?.pedidos ?? 0} hoje
            </span>
            <span className={`${styles.statChip} ${styles.statChipAccent}`}>
              <i className="ti ti-currency-dollar" /> {fmtMoeda(stats.hoje?.receita ?? 0)}
            </span>
            {nAtivos > 0 && (
              <span className={`${styles.statChip} ${styles.statChipWarn}`}>
                <i className="ti ti-clock" /> {nAtivos} em aberto
              </span>
            )}
            <span className={styles.statDivider} />
            <span className={styles.statChip} title="Pedidos no mês">
              <i className="ti ti-calendar" /> {stats.mes?.pedidos ?? 0} no mês
            </span>
            <span className={styles.statChip} title="Receita no mês">
              <i className="ti ti-chart-bar" /> {fmtMoeda(stats.mes?.receita ?? 0)}
            </span>
          </div>
        )}

        <div className={styles.headerActions}>
          <button
            className={styles.btnAtualizar}
            onClick={loadPedidos}
            title="Atualizar pedidos"
          >
            <i className={`ti ti-refresh${loading ? ' spin' : ''}`} />
          </button>
          <button className={styles.btnNovo} onClick={() => setShowNovo(true)}>
            <i className="ti ti-plus" /> Novo Pedido
          </button>
        </div>
      </div>

      {/* ── Kanban ── */}
      {loading && pedidos.length === 0 ? (
        <div className={styles.loadingCenter}>
          <i className="ti ti-loader-2 spin" style={{ fontSize: 28, color: 'var(--caramelo)' }} />
        </div>
      ) : (
        <div className={styles.kanban}>
          <KanbanCol
            title="Abertos"
            icon="circle-dot"
            accentColor="#3B82F6"
            pedidos={abertos}
            onCard={setSelected}
            onAcao={onAcao}
            emptyMsg="Sem pedidos abertos"
          />
          <KanbanCol
            title="Em andamento"
            icon="flame"
            accentColor="#F59E0B"
            pedidos={emAndamento}
            onCard={setSelected}
            onAcao={onAcao}
            emptyMsg="Sem pedidos em preparo"
          />
          <KanbanCol
            title="Prontos"
            icon="bell-ringing"
            accentColor="#10B981"
            pedidos={prontos}
            onCard={setSelected}
            onAcao={onAcao}
            emptyMsg="Sem pedidos prontos"
          />
        </div>
      )}

      {/* ── Histórico do dia ── */}
      {historico.length > 0 && (
        <div className={styles.histStrip}>
          <span className={styles.histLabel}>
            <i className="ti ti-history" />
            {nConcluidos > 0 && <span>{nConcluidos} concluído{nConcluidos !== 1 ? 's' : ''}</span>}
            {nConcluidos > 0 && nCancelados > 0 && <span className={styles.histSep}>·</span>}
            {nCancelados > 0 && <span className={styles.histCancel}>{nCancelados} cancelado{nCancelados !== 1 ? 's' : ''}</span>}
          </span>
          <div className={styles.histList}>
            {historico.map(p => (
              <button
                key={p.id}
                className={`${styles.histChip} ${p.status === 'cancelado' ? styles.histChipCanceled : ''}`}
                onClick={() => setSelected(p)}
                title={`${p.cliente_nome_crm || p.cliente_nome || 'Avulso'} · ${fmtMoeda(p.total)}`}
              >
                #{p.numero}
                <span className={styles.histChipName}>{p.cliente_nome_crm || p.cliente_nome || 'Avulso'}</span>
                <span className={styles.histChipVal}>{fmtMoeda(p.total)}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Modais ── */}
      {showNovo && (
        <ModalNovoPedido
          produtos={produtos}
          categorias={categorias}
          clientes={clientes}
          onClose={() => setShowNovo(false)}
          onSaved={loadPedidos}
          showToast={showToast}
        />
      )}
      {selected && (
        <ModalDetalhe
          pedido={selected}
          onClose={() => setSelected(null)}
          onUpdated={loadPedidos}
          showToast={showToast}
        />
      )}
    </div>
  )
}
