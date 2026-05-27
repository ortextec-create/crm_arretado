/**
 * ARQUIVO COMPLETO: arretado-crm/src/pages/IFood.jsx
 * Substitui o arquivo existente.
 *
 * Novidade (criar-cliente):
 *  - Botão "Criar Cliente" no modal de detalhe quando pedido não tem cliente vinculado
 *  - Chama POST /api/v1/ifood/pedidos/{id}/criar-cliente/
 *  - Em caso de 409 (telefone já existe), oferece vincular ao cliente existente
 *  - Lógica encapsulada em handleCriarCliente()
 */
import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ifoodApi, clientesApi } from '../api/services'
import Topbar from '../components/layout/Topbar'
import { Btn, Avatar, Spinner, Toast, Modal, Field, Input } from '../components/ui'
import styles from './IFood.module.css'

// ─── STATUS config ────────────────────────────────────────────────────────────
const STATUS_CFG = {
  PLACED:                 { label: 'Aguardando',     color: '#F59E0B', icon: 'clock' },
  CONFIRMED:              { label: 'Confirmado',     color: '#3B82F6', icon: 'circle-check' },
  PREPARATION_STARTED:    { label: 'Preparando',     color: '#8B5CF6', icon: 'chef-hat' },
  READY_TO_PICKUP:        { label: 'Pronto',         color: '#06B6D4', icon: 'package' },
  DISPATCHED:             { label: 'A caminho',      color: '#6366F1', icon: 'motorbike' },
  CONCLUDED:              { label: 'Concluído',      color: '#22C55E', icon: 'circle-check-filled' },
  CANCELLATION_REQUESTED: { label: 'Canc. solicit.', color: '#F97316', icon: 'alert-triangle' },
  CANCELLED:              { label: 'Cancelado',      color: '#EF4444', icon: 'circle-x' },
}

const TABS = ['Todos', 'Aguardando', 'Em andamento', 'Concluídos', 'Cancelados']
const TAB_FILTERS = {
  'Todos':         null,
  'Aguardando':    'PLACED',
  'Em andamento':  ['CONFIRMED', 'PREPARATION_STARTED', 'READY_TO_PICKUP', 'DISPATCHED'],
  'Concluídos':    'CONCLUDED',
  'Cancelados':    ['CANCELLED', 'CANCELLATION_REQUESTED'],
}

// ─── COMPONENTE PRINCIPAL ─────────────────────────────────────────────────────
export default function IFood() {
  const navigate = useNavigate()
  const pollRef  = useRef(null)

  const [tab, setTab]           = useState('Todos')
  const [search, setSearch]     = useState('')
  const [pedidos, setPedidos]   = useState([])
  const [stats, setStats]       = useState(null)
  const [statusGeral, setStatusGeral] = useState(null)
  const [loading, setLoading]   = useState(true)
  const [selected, setSelected] = useState(null)
  const [config, setConfig]     = useState(null)

  // Modals
  const [showConfig,   setShowConfig]   = useState(false)
  const [showDetail,   setShowDetail]   = useState(false)
  const [showCancel,   setShowCancel]   = useState(false)
  const [showVincular, setShowVincular] = useState(false)

  const [actionLoading,        setActionLoading]        = useState(null)
  const [toast,                setToast]                = useState(null)
  const [cancelReasons,        setCancelReasons]        = useState([])
  const [cancelCode,           setCancelCode]           = useState('')
  const [clientes,             setClientes]             = useState([])
  const [clienteSearch,        setClienteSearch]        = useState('')
  const [pollingManualLoading, setPollingManualLoading] = useState(false)

  // ── NOVO: estado para criar cliente ──
  const [criandoCliente, setCriandoCliente] = useState(false)

  // ── Carregamento de dados ─────────────────────────────────────────────────
  const loadData = useCallback(async () => {
    try {
      const params = {}
      if (search) params.search = search
      const statusFilter = TAB_FILTERS[tab]
      if (typeof statusFilter === 'string') params.status = statusFilter

      const [pedRes, statsRes, statusRes] = await Promise.allSettled([
        ifoodApi.listPedidos(params),
        ifoodApi.estatisticas(),
        ifoodApi.statusGeral(),
      ])

      let lista = pedRes.status === 'fulfilled'
        ? (pedRes.value.data.results ?? pedRes.value.data)
        : []

      // Filtro client-side para arrays de status
      if (Array.isArray(statusFilter)) {
        lista = lista.filter(p => statusFilter.includes(p.status))
      }

      setPedidos(lista)
      if (statsRes.status === 'fulfilled')  setStats(statsRes.value.data)
      if (statusRes.status === 'fulfilled') {
        setStatusGeral(statusRes.value.data)
        if (!statusRes.value.data.configurado) setShowConfig(true)
      }
    } catch {
      setPedidos([])
    } finally {
      setLoading(false)
    }
  }, [tab, search])

  useEffect(() => { loadData() }, [loadData])

  // Auto-refresh a cada 30s
  useEffect(() => {
    pollRef.current = setInterval(loadData, 30_000)
    return () => clearInterval(pollRef.current)
  }, [loadData])

  // Debounce busca
  useEffect(() => {
    const t = setTimeout(loadData, 400)
    return () => clearTimeout(t)
  }, [search])

  const loadConfig = async () => {
    try {
      const r = await ifoodApi.getConfig()
      const configs = r.data.results ?? r.data
      setConfig(configs[0] || null)
    } catch { setConfig(null) }
  }

  useEffect(() => { loadConfig() }, [])

  // ── Ações ──────────────────────────────────────────────────────────────────
  const openDetail = async (pedido) => {
    setSelected(pedido)
    setShowDetail(true)
    try {
      const r = await ifoodApi.getPedido(pedido.id)
      setSelected(r.data)
    } catch {}
  }

  const doAction = async (action, pedidoId, extra = {}) => {
    setActionLoading(action + pedidoId)
    try {
      let r
      switch (action) {
        case 'confirmar': r = await ifoodApi.confirmar(pedidoId);           break
        case 'despachar': r = await ifoodApi.despachar(pedidoId);           break
        case 'pronto':    r = await ifoodApi.prontoRetirada(pedidoId);      break
        case 'cancelar':  r = await ifoodApi.cancelar(pedidoId, extra);     break
        default: return
      }
      setToast({ message: `Pedido atualizado: ${r.data.status}`, type: 'success' })
      setShowDetail(false)
      setShowCancel(false)
      loadData()
    } catch (e) {
      setToast({ message: e?.response?.data?.detail || 'Erro ao executar ação.', type: 'error' })
    } finally {
      setActionLoading(null)
    }
  }

  const openCancel = async (pedido) => {
    setSelected(pedido)
    setShowCancel(true)
    try {
      const r = await ifoodApi.motivosCancelamento(pedido.id)
      setCancelReasons(r.data)
      if (r.data[0]) setCancelCode(r.data[0].code || r.data[0].cancelCodeId)
    } catch { setCancelReasons([]) }
  }

  const openVincular = async (pedido) => {
    setSelected(pedido)
    setShowVincular(true)
    setClienteSearch('')
    try {
      const r = await clientesApi.list({ search: pedido.cliente_nome?.split(' ')[0] || '' })
      setClientes(r.data.results ?? r.data)
    } catch { setClientes([]) }
  }

  const vincularCliente = async (clienteId) => {
    try {
      await ifoodApi.vincularCliente(selected.id, clienteId)
      setToast({ message: 'Cliente vinculado com sucesso!', type: 'success' })
      setShowVincular(false)
      loadData()
    } catch {
      setToast({ message: 'Erro ao vincular.', type: 'error' })
    }
  }

  // ── NOVO: Criar cliente a partir dos dados do pedido iFood ────────────────
  const handleCriarCliente = async (pedido) => {
    if (!window.confirm(
      `Criar cliente "${pedido.cliente_nome}" no CRM com os dados do iFood?\n` +
      `Telefone: ${pedido.cliente_telefone || '(não informado)'}`
    )) return

    setCriandoCliente(true)
    try {
      const res = await ifoodApi.criarCliente(pedido.id)
      setToast({ message: res.data.detail, type: 'success' })
      setShowDetail(false)
      loadData()
    } catch (err) {
      const data     = err.response?.data
      const httpCode = err.response?.status

      if (httpCode === 409 && data?.cliente_existente) {
        // Telefone já existe no CRM — oferece vincular ao existente
        const confirma = window.confirm(
          `${data.detail}\n\nDeseja vincular este pedido ao cliente existente?`
        )
        if (confirma) {
          try {
            await ifoodApi.vincularCliente(pedido.id, data.cliente_existente.id)
            setToast({ message: 'Cliente existente vinculado com sucesso!', type: 'success' })
            setShowDetail(false)
            loadData()
          } catch {
            setToast({ message: 'Erro ao vincular o cliente existente.', type: 'error' })
          }
        }
      } else {
        setToast({ message: data?.detail || 'Erro ao criar cliente.', type: 'error' })
      }
    } finally {
      setCriandoCliente(false)
    }
  }

  const pollingManual = async () => {
    if (!config) return
    setPollingManualLoading(true)
    try {
      const r = await ifoodApi.pollingManual(config.id)
      setToast({ message: `Polling: ${r.data.eventos} eventos, ${r.data.pedidos_novos} novos.`, type: 'success' })
      loadData()
    } catch {
      setToast({ message: 'Erro no polling manual.', type: 'error' })
    } finally {
      setPollingManualLoading(false)
    }
  }

  const statusCfg = (s) => STATUS_CFG[s] || { label: s, color: '#9CA3AF', icon: 'circle' }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className={styles.page}>
      <Topbar
        title="iFood"
        search={search}
        onSearch={setSearch}
        actions={
          <>
            {statusGeral?.polling_ativo
              ? <div className={styles.pollingBadge}><span className={styles.dot} />Polling ativo</div>
              : <div className={styles.pollingBadgeOff}><span className={styles.dotOff} />Polling pausado</div>
            }
            <Btn variant="ghost" icon="refresh" size="sm" loading={pollingManualLoading} onClick={pollingManual}>
              Atualizar
            </Btn>
            <Btn variant="ghost" icon="settings" size="sm" onClick={() => { loadConfig(); setShowConfig(true) }}>
              Configurar
            </Btn>
          </>
        }
      />

      <div className={styles.content}>

        {/* ─── Stats ─── */}
        {stats && (
          <div className={styles.statsRow}>
            <StatCard label="Pedidos hoje"  value={stats.hoje?.pedidos ?? 0}                          icon="shopping-bag" />
            <StatCard label="Receita hoje"  value={`R$ ${(stats.hoje?.receita ?? 0).toFixed(2)}`}    icon="currency-dollar" accent />
            <StatCard label="Aguardando"    value={stats.pendentes ?? 0}                               icon="clock"  warn={stats.pendentes > 0} />
            <StatCard label="Pedidos no mês" value={stats.mes?.pedidos ?? 0}                          icon="calendar" />
            <StatCard label="Receita no mês" value={`R$ ${(stats.mes?.receita ?? 0).toFixed(2)}`}    icon="chart-bar" />
          </div>
        )}

        {/* ─── Tabs ─── */}
        <div className={styles.tabsRow}>
          {TABS.map(t => (
            <button
              key={t}
              className={`${styles.tab} ${tab === t ? styles.tabActive : ''}`}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ))}
        </div>

        {/* ─── Tabela ─── */}
        {loading ? (
          <div className={styles.center}><Spinner size={26} /></div>
        ) : pedidos.length === 0 ? (
          <div className={styles.empty}>
            <i className="ti ti-shopping-bag-x" />
            <p>Nenhum pedido encontrado.</p>
            {!statusGeral?.configurado && (
              <Btn size="sm" icon="settings" onClick={() => setShowConfig(true)}>Configurar iFood</Btn>
            )}
          </div>
        ) : (
          <div className={styles.table}>
            <div className={styles.thead}>
              <span>Pedido</span>
              <span>Cliente</span>
              <span>Itens</span>
              <span>Tipo</span>
              <span>Valor</span>
              <span>Status</span>
              <span>Ações</span>
            </div>

            {pedidos.map(p => {
              const sc = statusCfg(p.status)
              return (
                <div key={p.id} className={styles.trow} onClick={() => openDetail(p)}>
                  <div>
                    <div className={styles.orderId}>#{p.display_id || p.ifood_order_id?.slice(0, 8)}</div>
                    <div className={styles.sub}>{fmtTime(p.ifood_criado_em)}</div>
                  </div>
                  <div>
                    <div className={styles.name}>{p.cliente_nome_crm || p.cliente_nome || 'Desconhecido'}</div>
                    {p.cliente_nome_crm && <div className={styles.crm}><i className="ti ti-link" />CRM</div>}
                  </div>
                  <div className={styles.sub}>— itens</div>
                  <div>
                    <span className={styles.typeBadge}>
                      {p.order_type === 'DELIVERY' ? '🛵 Delivery'
                        : p.order_type === 'TAKEOUT' ? '🏠 Retirada'
                        : '🪑 Mesa'}
                    </span>
                  </div>
                  <div className={styles.valor}>R$ {Number(p.total_valor).toFixed(2)}</div>
                  <div>
                    <span className={styles.statusBadge}
                      style={{ background: sc.color + '22', color: sc.color, borderColor: sc.color + '44' }}>
                      <i className={`ti ti-${sc.icon}`} />{sc.label}
                    </span>
                  </div>
                  <div className={styles.actions} onClick={e => e.stopPropagation()}>
                    {p.pode_confirmar && (
                      <button className={styles.actBtn} style={{ color: '#3B82F6' }}
                        onClick={() => doAction('confirmar', p.id)}
                        disabled={actionLoading === 'confirmar' + p.id}>
                        {actionLoading === 'confirmar' + p.id
                          ? <i className="ti ti-loader spin" />
                          : <i className="ti ti-circle-check" />}
                      </button>
                    )}
                    {p.pode_cancelar && (
                      <button className={styles.actBtn} style={{ color: '#EF4444' }}
                        onClick={() => openCancel(p)}>
                        <i className="ti ti-circle-x" />
                      </button>
                    )}
                    {!p.cliente_nome_crm && (
                      <button className={styles.actBtn} style={{ color: 'var(--verde)' }}
                        onClick={() => openVincular(p)} title="Vincular ao CRM">
                        <i className="ti ti-user-plus" />
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ─── MODAL DETALHE ─── */}
      <Modal
        open={showDetail}
        onClose={() => setShowDetail(false)}
        title={`Pedido #${selected?.display_id || ''}`}
        width={560}
        footer={
          selected && (
            <div style={{ display: 'flex', gap: 8, width: '100%', flexWrap: 'wrap' }}>
              {selected.pode_confirmar && (
                <Btn icon="circle-check"
                  loading={actionLoading === 'confirmar' + selected.id}
                  onClick={() => doAction('confirmar', selected.id)}>
                  Confirmar
                </Btn>
              )}
              {selected.status === 'CONFIRMED' && (
                <Btn variant="ghost" icon="chef-hat"
                  onClick={() => doAction('confirmar', selected.id)}>
                  Iniciar Preparo
                </Btn>
              )}
              {selected.status === 'PREPARATION_STARTED' && (
                <Btn variant="ghost" icon="package"
                  onClick={() => doAction('pronto', selected.id)}>
                  Pronto p/ Retirada
                </Btn>
              )}
              {selected.status === 'READY_TO_PICKUP' && (
                <Btn variant="ghost" icon="motorbike"
                  onClick={() => doAction('despachar', selected.id)}>
                  Despachar
                </Btn>
              )}
              {selected.pode_cancelar && (
                <Btn variant="danger-btn" icon="circle-x" style={{ marginLeft: 'auto' }}
                  onClick={() => { setShowDetail(false); openCancel(selected) }}>
                  Cancelar
                </Btn>
              )}

              {/* Botões de cliente — só aparecem se não há cliente vinculado */}
              {!selected.cliente_nome_crm && (
                <>
                  <Btn variant="ghost" icon="link" style={{ marginLeft: selected.pode_cancelar ? 0 : 'auto' }}
                    onClick={() => { setShowDetail(false); openVincular(selected) }}>
                    Vincular CRM
                  </Btn>
                  {selected.cliente_nome && (
                    <Btn variant="ghost" icon="user-plus"
                      loading={criandoCliente}
                      onClick={() => handleCriarCliente(selected)}>
                      Criar Cliente
                    </Btn>
                  )}
                </>
              )}
            </div>
          )
        }
      >
        {selected && (
          <PedidoDetail
            pedido={selected}
            statusCfg={statusCfg}
            navigate={navigate}
            onCriarCliente={handleCriarCliente}
            criandoCliente={criandoCliente}
            onVincular={() => { setShowDetail(false); openVincular(selected) }}
          />
        )}
      </Modal>

      {/* ─── MODAL CANCELAMENTO ─── */}
      <Modal
        open={showCancel}
        onClose={() => setShowCancel(false)}
        title="Cancelar Pedido"
        width={420}
        footer={
          <>
            <Btn variant="ghost" onClick={() => setShowCancel(false)}>Voltar</Btn>
            <Btn variant="danger-btn" icon="circle-x"
              loading={actionLoading === 'cancelar' + selected?.id}
              onClick={() => doAction('cancelar', selected?.id, { cancellationCode: cancelCode })}>
              Confirmar Cancelamento
            </Btn>
          </>
        }
      >
        <p style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 16 }}>
          Pedido <strong style={{ color: 'var(--bege)' }}>#{selected?.display_id}</strong> de {selected?.cliente_nome}
        </p>
        {cancelReasons.length > 0 ? (
          <Field label="Motivo do cancelamento">
            <select className={styles.select} value={cancelCode} onChange={e => setCancelCode(e.target.value)}>
              {cancelReasons.map(r => (
                <option key={r.code || r.cancelCodeId} value={r.code || r.cancelCodeId}>
                  {r.description}
                </option>
              ))}
            </select>
          </Field>
        ) : (
          <Field label="Código de cancelamento">
            <Input value={cancelCode} onChange={e => setCancelCode(e.target.value)} placeholder="501" />
          </Field>
        )}
      </Modal>

      {/* ─── MODAL VINCULAR CLIENTE ─── */}
      <Modal
        open={showVincular}
        onClose={() => setShowVincular(false)}
        title="Vincular ao CRM"
        width={460}
        footer={<Btn variant="ghost" onClick={() => setShowVincular(false)}>Fechar</Btn>}
      >
        <p style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 14 }}>
          Selecione o cliente CRM para vincular ao pedido{' '}
          <strong style={{ color: 'var(--bege)' }}>#{selected?.display_id}</strong>
        </p>
        <Field label="Buscar cliente">
          <Input
            placeholder="Nome ou telefone..."
            value={clienteSearch}
            onChange={async e => {
              setClienteSearch(e.target.value)
              try {
                const r = await clientesApi.list({ search: e.target.value })
                setClientes(r.data.results ?? r.data)
              } catch {}
            }}
          />
        </Field>
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {clientes.slice(0, 8).map(c => (
            <button key={c.id} className={styles.clienteRow} onClick={() => vincularCliente(c.id)}>
              <Avatar name={c.nome} size="sm" />
              <div>
                <div style={{ fontSize: 13, color: 'var(--bege)' }}>{c.nome}</div>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>{c.telefone_principal}</div>
              </div>
              <i className="ti ti-link" style={{ marginLeft: 'auto', color: 'var(--muted)' }} />
            </button>
          ))}
          {clientes.length === 0 && clienteSearch.length > 1 && (
            <p style={{ fontSize: 12, color: 'var(--muted)', textAlign: 'center', padding: '12px 0' }}>
              Nenhum cliente encontrado.
            </p>
          )}
        </div>
      </Modal>

      {/* ─── MODAL CONFIGURAÇÃO ─── */}
      <ConfigModal
        open={showConfig}
        onClose={() => setShowConfig(false)}
        config={config}
        onSaved={() => { loadConfig(); loadData(); setShowConfig(false) }}
        setToast={setToast}
      />

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}

// ─── PEDIDO DETAIL COMPONENT ──────────────────────────────────────────────────

function PedidoDetail({ pedido, statusCfg, navigate, onCriarCliente, criandoCliente, onVincular }) {
  const sc  = statusCfg(pedido.status)
  const end = pedido.endereco_entrega || {}

  return (
    <div className={styles.detail}>

      {/* Cabeçalho status + data */}
      <div className={styles.detailHeader}>
        <span className={styles.statusBadge}
          style={{ background: sc.color + '22', color: sc.color, borderColor: sc.color + '44', fontSize: 12 }}>
          <i className={`ti ti-${sc.icon}`} />{sc.label}
        </span>
        <span style={{ fontSize: 11, color: 'var(--muted)' }}>{fmtDateTime(pedido.ifood_criado_em)}</span>
      </div>

      {/* ── Seção cliente ── */}
      <div className={styles.detailSection}>
        <div className={styles.detailLabel}>Cliente</div>

        {pedido.cliente_nome_crm ? (
          /* Cliente já vinculado ao CRM */
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Avatar name={pedido.cliente_nome_crm} />
            <div>
              <div
                style={{ fontSize: 14, fontWeight: 600, color: 'var(--bege)', cursor: 'pointer' }}
                onClick={() => pedido.cliente_id && navigate(`/clientes/${pedido.cliente_id}`)}
              >
                {pedido.cliente_nome_crm}
                <i className="ti ti-external-link" style={{ fontSize: 11, marginLeft: 4, color: 'var(--muted)' }} />
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                <i className="ti ti-link" style={{ fontSize: 11 }} /> Vinculado ao CRM
              </div>
              {pedido.cliente_telefone && (
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                  <i className="ti ti-phone" style={{ fontSize: 11 }} /> {pedido.cliente_telefone}
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Sem cliente CRM — exibe dados do iFood + botões de ação */
          <div className={styles.semClienteBox}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Avatar name={pedido.cliente_nome || '?'} />
              <div>
                <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--texto)' }}>
                  {pedido.cliente_nome || 'Desconhecido'}
                </div>
                {pedido.cliente_telefone && (
                  <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                    <i className="ti ti-phone" style={{ fontSize: 11 }} /> {pedido.cliente_telefone}
                  </div>
                )}
                <div className={styles.semClienteTag}>
                  <i className="ti ti-unlink" />Sem cadastro no CRM
                </div>
              </div>
            </div>

            {/* Botões inline de Vincular / Criar — complementam os do footer */}
            <div className={styles.clienteAcoesMini}>
              <button className={styles.btnAcaoMini} onClick={onVincular} title="Buscar cliente existente">
                <i className="ti ti-link" /> Vincular existente
              </button>
              {pedido.cliente_nome && (
                <button
                  className={`${styles.btnAcaoMini} ${styles.btnAcaoMiniPrimary}`}
                  onClick={() => onCriarCliente(pedido)}
                  disabled={criandoCliente}
                  title="Criar novo cliente com dados do iFood"
                >
                  <i className="ti ti-user-plus" />
                  {criandoCliente ? 'Criando...' : 'Criar novo cliente'}
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Endereço de entrega ── */}
      {pedido.order_type === 'DELIVERY' && (end.streetName || end.formattedAddress) && (
        <div className={styles.detailSection}>
          <div className={styles.detailLabel}>Endereço de entrega</div>
          <div style={{ fontSize: 13, color: 'var(--texto)', lineHeight: 1.5 }}>
            {end.streetName
              ? `${end.streetName}, ${end.streetNumber || 'S/N'}${end.complement ? ` — ${end.complement}` : ''}`
              : end.formattedAddress}
            {end.neighborhood && <span style={{ color: 'var(--muted)' }}> · {end.neighborhood}</span>}
            {end.city && (
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                {end.city}{end.state ? `/${end.state}` : ''}{end.postalCode ? ` — CEP ${end.postalCode}` : ''}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Itens ── */}
      {pedido.itens?.length > 0 && (
        <div className={styles.detailSection}>
          <div className={styles.detailLabel}>Itens do pedido</div>
          <div className={styles.itensList}>
            {pedido.itens.map((item, i) => (
              <div key={item.id || i} className={styles.itemRow}>
                <span className={styles.itemQtd}>{item.quantidade}×</span>
                <div className={styles.itemInfo}>
                  <span className={styles.itemNome}>{item.nome}</span>
                  {item.observacao && (
                    <span className={styles.itemObs}>{item.observacao}</span>
                  )}
                  {item.complementos?.length > 0 && (
                    <div className={styles.complementos}>
                      {item.complementos.map((c, ci) => (
                        <span key={ci} className={styles.complementoTag}>
                          {c.quantidade > 1 ? `${c.quantidade}× ` : ''}{c.nome}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <span className={styles.itemPreco}>R$ {Number(item.preco_total).toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Totais ── */}
      <div className={styles.detailSection}>
        <div className={styles.detailLabel}>Totais</div>
        <div className={styles.totaisGrid}>
          {Number(pedido.subtotal) > 0 && (
            <><span style={{ color: 'var(--muted)' }}>Subtotal</span><span>R$ {Number(pedido.subtotal).toFixed(2)}</span></>
          )}
          {Number(pedido.taxa_entrega) > 0 && (
            <><span style={{ color: 'var(--muted)' }}>Taxa de entrega</span><span>R$ {Number(pedido.taxa_entrega).toFixed(2)}</span></>
          )}
          {Number(pedido.desconto) > 0 && (
            <><span style={{ color: 'var(--verde)' }}>Desconto</span><span style={{ color: 'var(--verde)' }}>− R$ {Number(pedido.desconto).toFixed(2)}</span></>
          )}
          <><span style={{ fontWeight: 600, color: 'var(--bege)' }}>Total</span><span style={{ fontWeight: 700, color: 'var(--caramelo)', fontSize: 15 }}>R$ {Number(pedido.total_valor).toFixed(2)}</span></>
        </div>
        {pedido.payment_method && (
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8 }}>
            <i className="ti ti-credit-card" style={{ fontSize: 12, marginRight: 4 }} />
            {pedido.payment_method}
          </div>
        )}
      </div>

    </div>
  )
}

// ─── CONFIG MODAL ──────────────────────────────────────────────────────────────

function ConfigModal({ open, onClose, config, onSaved, setToast }) {
  const [form, setForm]             = useState({ client_id: '', client_secret: '', merchant_id: '', polling_intervalo: 30 })
  const [saving, setSaving]         = useState(false)
  const [testing, setTesting]       = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [pollingLoading, setPollingLoading] = useState(false)

  useEffect(() => {
    if (config) {
      setForm({
        client_id:         config.client_id || '',
        client_secret:     '',   // nunca pré-preenche por segurança
        merchant_id:       config.merchant_id || '',
        polling_intervalo: config.polling_intervalo || 30,
      })
    }
    setTestResult(null)
  }, [config, open])

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const save = async () => {
    setSaving(true)
    try {
      const payload = { ...form }
      if (!payload.client_secret) delete payload.client_secret
      if (config) await ifoodApi.updateConfig(config.id, payload)
      else        await ifoodApi.createConfig(payload)
      setToast({ message: 'Configuração salva!', type: 'success' })
      onSaved()
    } catch {
      setToast({ message: 'Erro ao salvar configuração.', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const testar = async () => {
    if (!config) { setToast({ message: 'Salve a configuração primeiro.', type: 'error' }); return }
    setTesting(true); setTestResult(null)
    try {
      const r = await ifoodApi.testarConexao(config.id)
      setTestResult(r.data)
    } catch (e) {
      setTestResult({ ok: false, erro: e?.response?.data?.erro || 'Falha na conexão' })
    } finally {
      setTesting(false)
    }
  }

  const togglePolling = async () => {
    if (!config) return
    setPollingLoading(true)
    try {
      if (config.polling_ativo) await ifoodApi.pausarPolling(config.id)
      else                      await ifoodApi.ativarPolling(config.id)
      setToast({ message: config.polling_ativo ? 'Polling pausado.' : 'Polling ativado!', type: 'success' })
      onSaved()
    } catch {
      setToast({ message: 'Erro ao alterar polling.', type: 'error' })
    } finally {
      setPollingLoading(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Configuração iFood" width={500}
      footer={
        <>
          <Btn variant="ghost" onClick={onClose}>Fechar</Btn>
          <Btn variant="ghost" icon="plug" loading={testing} onClick={testar}>Testar conexão</Btn>
          <Btn icon="device-floppy" loading={saving} onClick={save}>Salvar</Btn>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

        <div style={{ background: 'rgba(234,88,12,0.08)', border: '0.5px solid rgba(234,88,12,0.2)', padding: '12px 14px', borderRadius: 2, fontSize: 12, color: '#EA580C' }}>
          <i className="ti ti-info-circle" /> As credenciais são obtidas no{' '}
          <a href="https://developer.ifood.com.br" target="_blank" rel="noreferrer"
            style={{ color: '#EA580C', textDecoration: 'underline' }}>
            Portal do Desenvolvedor iFood
          </a>.
        </div>

        <Field label="Client ID *">
          <Input placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            value={form.client_id} onChange={e => set('client_id', e.target.value)} />
        </Field>
        <Field label="Client Secret *">
          <Input type="password"
            placeholder={config ? '(mantém o atual se deixar em branco)' : 'Seu client secret'}
            value={form.client_secret} onChange={e => set('client_secret', e.target.value)} />
        </Field>
        <Field label="Merchant ID *">
          <Input placeholder="ID do restaurante no iFood"
            value={form.merchant_id} onChange={e => set('merchant_id', e.target.value)} />
        </Field>
        <Field label="Intervalo de polling (segundos)">
          <Input type="number" min={15} max={120}
            value={form.polling_intervalo} onChange={e => set('polling_intervalo', e.target.value)} />
        </Field>

        {testResult && (
          <div style={{
            padding: '10px 14px', borderRadius: 2, fontSize: 12,
            background: testResult.ok ? 'rgba(143,188,139,0.1)' : 'rgba(192,90,58,0.1)',
            color:      testResult.ok ? 'var(--verde)'          : 'var(--danger)',
            border:     `0.5px solid ${testResult.ok ? 'rgba(143,188,139,0.3)' : 'rgba(192,90,58,0.3)'}`,
          }}>
            {testResult.ok
              ? <><i className="ti ti-circle-check" /> Conexão bem-sucedida! Token válido até {new Date(testResult.expira_em).toLocaleString('pt-BR')}</>
              : <><i className="ti ti-circle-x" /> {testResult.erro || 'Falha na autenticação'}</>
            }
          </div>
        )}

        {config && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 8, borderTop: '0.5px solid var(--border)' }}>
            <div>
              <div style={{ fontSize: 13, color: 'var(--bege)' }}>Polling automático</div>
              <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                {config.polling_ativo
                  ? `Ativo — último: ${config.ultimo_polling ? new Date(config.ultimo_polling).toLocaleTimeString('pt-BR') : 'nunca'}`
                  : 'Pausado'}
              </div>
            </div>
            <Btn
              variant={config.polling_ativo ? 'danger-btn' : 'ghost'}
              size="sm"
              loading={pollingLoading}
              icon={config.polling_ativo ? 'player-pause' : 'player-play'}
              onClick={togglePolling}
            >
              {config.polling_ativo ? 'Pausar' : 'Ativar'}
            </Btn>
          </div>
        )}

      </div>
    </Modal>
  )
}

// ─── STAT CARD ────────────────────────────────────────────────────────────────
function StatCard({ label, value, icon, accent, warn }) {
  return (
    <div className={`${styles.statCard} ${accent ? styles.statAccent : ''} ${warn ? styles.statWarn : ''}`}>
      <i className={`ti ti-${icon} ${styles.statIcon}`} />
      <div className={styles.statLabel}>{label}</div>
      <div className={styles.statValue}>{value}</div>
    </div>
  )
}

// ─── UTILS ────────────────────────────────────────────────────────────────────
function fmtTime(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}
function fmtDateTime(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}
