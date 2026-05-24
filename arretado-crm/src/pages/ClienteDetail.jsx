import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { clientesApi } from '../api/services'
import Topbar from '../components/layout/Topbar'
import { Btn, Avatar, StatusBadge, IntBadge, Spinner, Toast, Modal, Field, Input, Select } from '../components/ui'
import ClienteForm from './ClienteForm'
import styles from './ClienteDetail.module.css'

// ── Fase 3: Histórico unificado ────────────────────────────────────────────
const STATUS_CFG_HIST = {
  PLACED:                 { label: 'Aguardando',   color: '#F59E0B', icon: 'clock' },
  CONFIRMED:              { label: 'Confirmado',   color: '#3B82F6', icon: 'circle-check' },
  PREPARATION_STARTED:    { label: 'Em preparo',   color: '#8B5CF6', icon: 'chef-hat' },
  READY_TO_PICKUP:        { label: 'Pronto',       color: '#10B981', icon: 'package' },
  DISPATCHED:             { label: 'A caminho',    color: '#06B6D4', icon: 'moped' },
  CONCLUDED:              { label: 'Concluído',    color: '#16A34A', icon: 'circle-check-filled' },
  CANCELLATION_REQUESTED: { label: 'Cancelamento', color: '#F97316', icon: 'alert-triangle' },
  CANCELLED:              { label: 'Cancelado',    color: '#EF4444', icon: 'circle-x' },
}

const CANAL_CFG = {
  ifood:   { label: 'iFood',       color: '#EA580C', icon: 'brand-firebase' },
  anotaai: { label: 'Anota AI',    color: '#7C3AED', icon: 'device-mobile' },
  pdv:     { label: 'PDV Próprio', color: '#0EA5E9', icon: 'building-store' },
}

const HIST_TABS    = ['Todos', 'iFood', 'Anota AI', 'PDV']
const HIST_TAB_MAP = { 'Todos': null, 'iFood': 'ifood', 'Anota AI': 'anotaai', 'PDV': 'pdv' }

function fmtData(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' })
}

function fmtHora(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

function fmtMoeda(v) {
  return Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

// ── Constantes legado ──────────────────────────────────────────────────────
const TIPO_LABELS  = { entrega: 'Entrega', cobranca: 'Cobrança', residencial: 'Residencial', comercial: 'Comercial' }
const SEXO_LABELS  = { M: 'Masculino', F: 'Feminino', O: 'Outro', N: 'Prefiro não informar' }
const EMPTY_ADDR   = { tipo: 'entrega', apelido: '', cep: '', logradouro: '', numero: '', complemento: '', bairro: '', cidade: '', estado: '', principal: false }

// ─────────────────────────────────────────────────────────────────────────────
// Sub-componentes
// ─────────────────────────────────────────────────────────────────────────────

function DataRow({ icon, label, value }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '9px 0', borderBottom: '0.5px solid rgba(200,134,10,0.07)' }}>
      <i className={`ti ti-${icon}`} style={{ fontSize: 15, color: 'var(--muted)', marginTop: 1, flexShrink: 0 }} />
      <span style={{ fontSize: 11, color: 'var(--muted)', width: 140, flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: 13, color: 'var(--bege)' }}>{value}</span>
    </div>
  )
}

function MetricCard({ label, value, icon, accent }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '14px 16px',
      background: accent ? 'color-mix(in srgb, var(--caramelo) 6%, var(--surface))' : 'var(--surface)',
      border: `0.5px solid ${accent ? 'rgba(200,145,51,0.25)' : 'var(--border)'}`,
      borderRadius: 10,
    }}>
      <i className={`ti ti-${icon}`} style={{ fontSize: 20, color: accent ? 'var(--caramelo)' : 'var(--muted)', flexShrink: 0 }} />
      <div>
        <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--bege)', lineHeight: 1.2 }}>{value}</p>
        <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{label}</p>
      </div>
    </div>
  )
}

function PedidoHistRow({ pedido, onClickPedido }) {
  const sc = STATUS_CFG_HIST[pedido.status] || { label: pedido.status, color: '#9CA3AF', icon: 'circle' }
  const cc = CANAL_CFG[pedido.canal]        || { label: pedido.canal,  color: '#9CA3AF', icon: 'circle' }

  return (
    <div
      onClick={() => onClickPedido(pedido)}
      style={{
        display: 'grid',
        gridTemplateColumns: '100px 110px 110px 120px 110px 1fr 24px',
        alignItems: 'center',
        padding: '11px 16px',
        borderBottom: '0.5px solid var(--border)',
        cursor: 'pointer',
        transition: 'background 0.1s',
        fontSize: 13,
        color: 'var(--bege)',
      }}
      onMouseEnter={e => e.currentTarget.style.background = 'color-mix(in srgb, var(--caramelo) 4%, transparent)'}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      {/* Canal */}
      <div>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 500,
          background: cc.color + '22', color: cc.color,
        }}>
          <i className={`ti ti-${cc.icon}`} style={{ fontSize: 12 }} />
          {cc.label}
        </span>
      </div>

      {/* Número */}
      <div>
        <div style={{ fontFamily: 'monospace', fontSize: 12 }}>#{pedido.numero}</div>
        <div style={{ fontSize: 11, color: 'var(--muted)' }}>{fmtHora(pedido.data)}</div>
      </div>

      {/* Data */}
      <div style={{ fontSize: 12, color: 'var(--muted)' }}>{fmtData(pedido.data)}</div>

      {/* Tipo */}
      <div style={{ fontSize: 12 }}>
        {pedido.tipo === 'DELIVERY' ? '🛵 Delivery'
          : pedido.tipo === 'TAKEOUT' ? '🏠 Retirada'
          : pedido.tipo === 'INDOOR'  ? '🪑 Mesa'
          : pedido.tipo_label}
      </div>

      {/* Valor */}
      <div style={{ fontWeight: 600 }}>{fmtMoeda(pedido.total)}</div>

      {/* Status */}
      <div>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 500,
          background: sc.color + '22', color: sc.color,
          border: `0.5px solid ${sc.color}44`,
        }}>
          <i className={`ti ti-${sc.icon}`} style={{ fontSize: 12 }} />
          {sc.label}
        </span>
      </div>

      {/* Seta */}
      <div><i className="ti ti-chevron-right" style={{ color: 'var(--muted)', fontSize: 14 }} /></div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Componente principal
// ─────────────────────────────────────────────────────────────────────────────

export default function ClienteDetail() {
  const { id }   = useParams()
  const navigate = useNavigate()

  // ── Estado base ────────────────────────────────────────────────────────────
  const [cliente,     setCliente]     = useState(null)
  const [loading,     setLoading]     = useState(true)
  const [showEdit,    setShowEdit]    = useState(false)
  const [showAddrForm,setShowAddrForm]= useState(false)
  const [editAddr,    setEditAddr]    = useState(null)
  const [addrForm,    setAddrForm]    = useState(EMPTY_ADDR)
  const [savingAddr,  setSavingAddr]  = useState(false)
  const [toast,       setToast]       = useState(null)

  // ── Estado Fase 3: Histórico ───────────────────────────────────────────────
  const [histTab,     setHistTab]     = useState('Todos')
  const [historico,   setHistorico]   = useState([])
  const [metricas,    setMetricas]    = useState(null)
  const [histLoading, setHistLoading] = useState(true)
  const [histErro,    setHistErro]    = useState(null)

  // ── Carregamento do cliente ────────────────────────────────────────────────
  const load = useCallback(() => {
    setLoading(true)
    clientesApi.get(id)
      .then(r  => setCliente(r.data))
      .catch(() => navigate('/clientes'))
      .finally(() => setLoading(false))
  }, [id, navigate])

  useEffect(() => { load() }, [load])

  // ── Carregamento do histórico ──────────────────────────────────────────────
  const loadHistorico = useCallback(async () => {
    setHistLoading(true)
    setHistErro(null)
    try {
      const canal  = HIST_TAB_MAP[histTab]
      const params = canal ? { canal } : {}
      const { data } = await clientesApi.historico(id, params)
      setHistorico(data.pedidos  || [])
      setMetricas(data.metricas  || null)
    } catch {
      setHistErro('Não foi possível carregar o histórico.')
    } finally {
      setHistLoading(false)
    }
  }, [id, histTab])

  useEffect(() => { loadHistorico() }, [loadHistorico])

  // ── Handlers ───────────────────────────────────────────────────────────────
  const handleSaveCliente = async (form) => {
    await clientesApi.update(id, form)
    setToast({ message: 'Dados atualizados com sucesso!', type: 'success' })
    load()
  }

  const handleStatusAction = async (action) => {
    try {
      if (action === 'ativar') await clientesApi.ativar(id)
      else                      await clientesApi.bloquear(id)
      setToast({ message: 'Status alterado com sucesso.', type: 'success' })
      load()
    } catch {
      setToast({ message: 'Erro ao alterar status.', type: 'error' })
    }
  }

  const openAddrForm = (addr = null) => {
    setEditAddr(addr)
    setAddrForm(addr ? { ...addr } : { ...EMPTY_ADDR })
    setShowAddrForm(true)
  }

  const saveAddr = async () => {
    setSavingAddr(true)
    try {
      if (editAddr) await clientesApi.updateEndereco(id, editAddr.id, addrForm)
      else          await clientesApi.addEndereco(id, addrForm)
      setShowAddrForm(false)
      setToast({ message: 'Endereço salvo.', type: 'success' })
      load()
    } catch {
      setToast({ message: 'Erro ao salvar endereço.', type: 'error' })
    } finally {
      setSavingAddr(false)
    }
  }

  const removeAddr = async (eid) => {
    if (!confirm('Remover este endereço?')) return
    try {
      await clientesApi.removeEndereco(id, eid)
      setToast({ message: 'Endereço removido.', type: 'success' })
      load()
    } catch {
      setToast({ message: 'Erro ao remover.', type: 'error' })
    }
  }

  const handleClickPedidoHist = (pedido) => {
    if (pedido.canal === 'ifood') {
      navigate('/integracoes/ifood', { state: { openPedidoId: pedido.origem_id } })
    }
  }

  const setA = (k, v) => setAddrForm(f => ({ ...f, [k]: v }))

  // ── Loading / not found ────────────────────────────────────────────────────
  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Topbar title="Cliente" />
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spinner size={28} />
      </div>
    </div>
  )

  if (!cliente) return null

  // ─────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className={styles.page}>
      <Topbar
        title="Perfil do Cliente"
        actions={
          <>
            <Btn variant="ghost" icon="arrow-left" size="sm" onClick={() => navigate('/clientes')}>
              Voltar
            </Btn>
            <Btn variant="ghost" icon="edit" size="sm" onClick={() => setShowEdit(true)}>Editar</Btn>
            {cliente.status === 'bloqueado'
              ? <Btn icon="lock-open" size="sm" onClick={() => handleStatusAction('ativar')}>Ativar</Btn>
              : <Btn variant="danger-btn" icon="lock" size="sm" onClick={() => handleStatusAction('bloquear')}>Bloquear</Btn>
            }
          </>
        }
      />

      <div className={styles.content}>
        <div className={styles.grid}>

          {/* ── COLUNA ESQUERDA — dados principais ── */}
          <div>

            {/* Header card */}
            <div className={styles.headerCard}>
              <Avatar name={cliente.nome} size="xl" />
              <div className={styles.headerInfo}>
                <h2 className="serif">{cliente.nome}</h2>
                <div className={styles.headerMeta}>
                  <StatusBadge status={cliente.status} />
                  {cliente.tem_integracao_ifood   && <IntBadge type="ifood" />}
                  {cliente.tem_integracao_anotaai && <IntBadge type="anotaai" />}
                </div>
                {(cliente.tags || []).length > 0 && (
                  <div className={styles.headerTags}>
                    {cliente.tags.map(t => (
                      <span key={t.id} style={{
                        padding: '2px 10px', fontSize: 11, borderRadius: 20,
                        border: `0.5px solid ${t.cor}50`, color: t.cor,
                      }}>
                        {t.nome}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Dados Pessoais */}
            <div className={styles.dataCard}>
              <div className={styles.cardTitle}>Dados Pessoais</div>
              <div className={styles.dataGrid}>
                <DataRow icon="phone"          label="Telefone Principal"  value={cliente.telefone_principal} />
                <DataRow icon="phone-call"     label="Telefone Secundário" value={cliente.telefone_secundario || '—'} />
                <DataRow icon="mail"           label="E-mail"              value={cliente.email || '—'} />
                <DataRow icon="id"             label="CPF"                 value={cliente.cpf || '—'} />
                <DataRow icon="cake"           label="Nascimento"          value={cliente.data_nascimento || '—'} />
                <DataRow icon="gender-bigender"label="Sexo"                value={SEXO_LABELS[cliente.sexo] || '—'} />
              </div>
              {cliente.observacoes && (
                <div className={styles.obs}>
                  <i className="ti ti-notes" />
                  <span>{cliente.observacoes}</span>
                </div>
              )}
            </div>

            {/* Integrações */}
            <div className={styles.dataCard}>
              <div className={styles.cardTitle}>Integrações Externas</div>
              <div className={styles.dataGrid}>
                <DataRow icon="brand-firebase" label="ID iFood"   value={cliente.ifood_customer_id    || 'Não vinculado'} />
                <DataRow icon="device-mobile"  label="ID Anota AI" value={cliente.anotaai_customer_id || 'Não vinculado'} />
              </div>
            </div>

          </div>

          {/* ── COLUNA DIREITA — endereços + auditoria ── */}
          <div>
            <div className={styles.addrHeader}>
              <h3 className="serif">Endereços</h3>
              <Btn variant="ghost" icon="plus" size="sm" onClick={() => openAddrForm()}>Adicionar</Btn>
            </div>

            {(cliente.enderecos || []).length === 0 && (
              <div className={styles.emptyAddr}>
                <i className="ti ti-map-pin-off" />
                <p>Nenhum endereço cadastrado.</p>
                <Btn size="sm" icon="plus" onClick={() => openAddrForm()}>Adicionar Endereço</Btn>
              </div>
            )}

            {(cliente.enderecos || []).map(end => (
              <div key={end.id} className={styles.addrCard}>
                <div className={styles.addrTop}>
                  <span className={styles.addrTipo}>{TIPO_LABELS[end.tipo] || end.tipo}</span>
                  {end.apelido && <span className={styles.addrApelido}>{end.apelido}</span>}
                  {end.principal && (
                    <span className={styles.addrPrincipal}>
                      <i className="ti ti-star-filled" /> Principal
                    </span>
                  )}
                  <div style={{ marginLeft: 'auto', display: 'flex', gap: 5 }}>
                    <button className={styles.addrBtn} onClick={() => openAddrForm(end)}>
                      <i className="ti ti-edit" />
                    </button>
                    <button className={`${styles.addrBtn} ${styles.addrBtnDanger}`} onClick={() => removeAddr(end.id)}>
                      <i className="ti ti-trash" />
                    </button>
                  </div>
                </div>
                <p className={styles.addrText}>
                  {end.logradouro}, {end.numero}{end.complemento ? `, ${end.complemento}` : ''}
                </p>
                <p className={styles.addrSub}>
                  {end.bairro} — {end.cidade}/{end.estado} — CEP {end.cep}
                </p>
              </div>
            ))}

            {/* Auditoria */}
            <div className={styles.dataCard} style={{ marginTop: 16 }}>
              <div className={styles.cardTitle}>Auditoria</div>
              <div className={styles.dataGrid}>
                <DataRow icon="calendar-plus"  label="Cadastrado em"  value={new Date(cliente.criado_em).toLocaleString('pt-BR')} />
                <DataRow icon="calendar-event" label="Atualizado em"  value={new Date(cliente.atualizado_em).toLocaleString('pt-BR')} />
              </div>
            </div>
          </div>
        </div>

        {/* ════════════════════════════════════════════════════════════════════
            FASE 3 — Histórico de Pedidos Unificado
            ════════════════════════════════════════════════════════════════════ */}
        <div className={styles.historicoSection}>
          <div className={styles.sectionTitle}>
            <i className="ti ti-clock-history" />
            Histórico de Pedidos
          </div>

          {/* Cards de métricas */}
          {metricas && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 12 }}>
                <MetricCard icon="shopping-bag"    label="Total de pedidos" value={metricas.total_pedidos} />
                <MetricCard icon="currency-dollar" label="Total gasto"      value={fmtMoeda(metricas.total_gasto)} accent />
                <MetricCard icon="chart-bar"       label="Ticket médio"     value={fmtMoeda(metricas.ticket_medio)} />
                <MetricCard icon="calendar"        label="Último pedido"    value={fmtData(metricas.ultimo_pedido_em)} />
              </div>

              {/* Distribuição por canal */}
              <div style={{
                display: 'flex', gap: 20, padding: '10px 14px',
                background: 'var(--surface)', border: '0.5px solid var(--border)',
                borderRadius: 8, marginBottom: 12,
              }}>
                {Object.entries(metricas.por_canal).map(([canal, qtd]) => {
                  const cc = CANAL_CFG[canal] || { label: canal, color: '#9CA3AF', icon: 'circle' }
                  return (
                    <div key={canal} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                      <i className={`ti ti-${cc.icon}`} style={{ color: cc.color, fontSize: 15 }} />
                      <span style={{ color: 'var(--bege)', fontWeight: 600 }}>{qtd}</span>
                      <span style={{ color: 'var(--muted)', fontSize: 11 }}>{cc.label}</span>
                    </div>
                  )
                })}
              </div>
            </>
          )}

          {/* Tabs por canal */}
          <div style={{ display: 'flex', gap: 4, borderBottom: '0.5px solid var(--border)', marginBottom: 0 }}>
            {HIST_TABS.map(t => (
              <button
                key={t}
                onClick={() => setHistTab(t)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '8px 14px', fontSize: 13, background: 'none', border: 'none',
                  borderBottom: `2px solid ${histTab === t ? 'var(--caramelo)' : 'transparent'}`,
                  color: histTab === t ? 'var(--caramelo)' : 'var(--muted)',
                  cursor: 'pointer', marginBottom: '-0.5px', transition: 'color 0.15s',
                }}
              >
                {t}
                {t !== 'Todos' && metricas && (
                  <span style={{
                    fontSize: 10, padding: '1px 6px', borderRadius: 10,
                    background: histTab === t ? 'color-mix(in srgb, var(--caramelo) 20%, transparent)' : 'var(--border)',
                    color: histTab === t ? 'var(--caramelo)' : 'var(--muted)',
                  }}>
                    {metricas.por_canal[HIST_TAB_MAP[t]] ?? 0}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Conteúdo da tabela */}
          {histLoading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
              <Spinner size={22} />
            </div>
          ) : histErro ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 40, gap: 8, color: '#EF4444' }}>
              <i className="ti ti-alert-circle" style={{ fontSize: 22 }} />
              <p style={{ fontSize: 13 }}>{histErro}</p>
            </div>
          ) : historico.length === 0 ? (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              padding: 40, gap: 8, color: 'var(--muted)',
              border: '0.5px dashed var(--border)', borderTop: 'none', borderRadius: '0 0 10px 10px',
            }}>
              <i className="ti ti-shopping-bag-x" style={{ fontSize: 28, opacity: 0.4 }} />
              <p style={{ fontSize: 13 }}>
                Nenhum pedido encontrado{histTab !== 'Todos' ? ` em ${histTab}` : ''}.
              </p>
            </div>
          ) : (
            <div style={{ border: '0.5px solid var(--border)', borderTop: 'none', borderRadius: '0 0 10px 10px', overflow: 'hidden' }}>
              {/* Cabeçalho da tabela */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: '100px 110px 110px 120px 110px 1fr 24px',
                padding: '8px 16px',
                fontSize: 11, color: 'var(--muted)',
                textTransform: 'uppercase', letterSpacing: '0.04em',
                background: 'color-mix(in srgb, var(--surface) 60%, transparent)',
                borderBottom: '0.5px solid var(--border)',
              }}>
                <span>Canal</span>
                <span>Pedido</span>
                <span>Data</span>
                <span>Tipo</span>
                <span>Valor</span>
                <span>Status</span>
                <span></span>
              </div>

              {historico.map(p => (
                <PedidoHistRow
                  key={`${p.canal}-${p.id}`}
                  pedido={p}
                  onClickPedido={handleClickPedidoHist}
                />
              ))}
            </div>
          )}
        </div>
        {/* ═════════════════════════ FIM FASE 3 ════════════════════════════ */}

      </div>

      {/* ── Modals ── */}
      <ClienteForm
        open={showEdit}
        onClose={() => setShowEdit(false)}
        onSave={handleSaveCliente}
        initial={cliente}
      />

      <Modal
        open={showAddrForm}
        onClose={() => setShowAddrForm(false)}
        title={editAddr ? 'Editar Endereço' : 'Novo Endereço'}
        width={520}
        footer={
          <>
            <Btn variant="ghost" onClick={() => setShowAddrForm(false)}>Cancelar</Btn>
            <Btn loading={savingAddr} icon="check" onClick={saveAddr}>Salvar Endereço</Btn>
          </>
        }
      >
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <Field label="Tipo">
            <Select value={addrForm.tipo} onChange={e => setA('tipo', e.target.value)}>
              <option value="entrega">Entrega</option>
              <option value="cobranca">Cobrança</option>
              <option value="residencial">Residencial</option>
              <option value="comercial">Comercial</option>
            </Select>
          </Field>
          <Field label="Apelido (ex: Casa, Trabalho)">
            <Input placeholder="Casa" value={addrForm.apelido} onChange={e => setA('apelido', e.target.value)} />
          </Field>
          <Field label="CEP *">
            <Input placeholder="00000-000" value={addrForm.cep} onChange={e => setA('cep', e.target.value)} />
          </Field>
          <div style={{ gridColumn: '1 / -1' }}>
            <Field label="Logradouro *">
              <Input placeholder="Rua, Avenida..." value={addrForm.logradouro} onChange={e => setA('logradouro', e.target.value)} />
            </Field>
          </div>
          <Field label="Número *">
            <Input placeholder="123" value={addrForm.numero} onChange={e => setA('numero', e.target.value)} />
          </Field>
          <Field label="Complemento">
            <Input placeholder="Apto, Bloco..." value={addrForm.complemento} onChange={e => setA('complemento', e.target.value)} />
          </Field>
          <Field label="Bairro *">
            <Input placeholder="Bairro" value={addrForm.bairro} onChange={e => setA('bairro', e.target.value)} />
          </Field>
          <Field label="Cidade *">
            <Input placeholder="Teresina" value={addrForm.cidade} onChange={e => setA('cidade', e.target.value)} />
          </Field>
          <Field label="Estado *">
            <Input placeholder="PI" maxLength={2} value={addrForm.estado} onChange={e => setA('estado', e.target.value.toUpperCase())} />
          </Field>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 20 }}>
            <input
              type="checkbox" id="principal"
              checked={addrForm.principal}
              onChange={e => setA('principal', e.target.checked)}
              style={{ accentColor: 'var(--caramelo)', width: 14, height: 14 }}
            />
            <label htmlFor="principal" style={{ fontSize: 13, color: 'var(--muted)', cursor: 'pointer' }}>
              Endereço principal
            </label>
          </div>
        </div>
      </Modal>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
