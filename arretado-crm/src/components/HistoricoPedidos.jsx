// ─── ARQUIVO: arretado-crm/src/components/HistoricoPedidos.jsx ───────────────
// Componente reutilizável de histórico unificado de pedidos por cliente.
// Importe e use dentro de ClienteDetail.jsx.

import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { clientesApi } from '../api/services'
import { Spinner } from './ui'
import styles from './HistoricoPedidos.module.css'

// ── Configuração visual dos status ─────────────────────────────────────────
const STATUS_CFG = {
  PLACED:                   { label: 'Aguardando',   color: '#F59E0B', icon: 'clock' },
  CONFIRMED:                { label: 'Confirmado',   color: '#3B82F6', icon: 'circle-check' },
  PREPARATION_STARTED:      { label: 'Em preparo',   color: '#8B5CF6', icon: 'chef-hat' },
  READY_TO_PICKUP:          { label: 'Pronto',       color: '#10B981', icon: 'package' },
  DISPATCHED:               { label: 'A caminho',    color: '#06B6D4', icon: 'moped' },
  CONCLUDED:                { label: 'Concluído',    color: '#16A34A', icon: 'circle-check-filled' },
  CANCELLATION_REQUESTED:   { label: 'Cancelamento', color: '#F97316', icon: 'alert-triangle' },
  CANCELLED:                { label: 'Cancelado',    color: '#EF4444', icon: 'circle-x' },
}

const CANAL_CFG = {
  ifood:   { label: 'iFood',      color: '#EA580C', icon: 'brand-firebase' },
  anotaai: { label: 'Anota AI',   color: '#7C3AED', icon: 'device-mobile' },
  pdv:     { label: 'PDV Próprio',color: '#0EA5E9', icon: 'building-store' },
}

const TABS = ['Todos', 'iFood', 'Anota AI', 'PDV']
const TAB_CANAL = { 'Todos': null, 'iFood': 'ifood', 'Anota AI': 'anotaai', 'PDV': 'pdv' }

function fmtData(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' })
}

function fmtHora(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

function fmtMoeda(v) {
  return Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

// ── Cards de métricas ───────────────────────────────────────────────────────
function MetricCard({ label, value, icon, accent }) {
  return (
    <div className={`${styles.metricCard} ${accent ? styles.metricAccent : ''}`}>
      <i className={`ti ti-${icon}`} />
      <div>
        <p className={styles.metricValue}>{value}</p>
        <p className={styles.metricLabel}>{label}</p>
      </div>
    </div>
  )
}

// ── Linha de pedido ─────────────────────────────────────────────────────────
function PedidoRow({ pedido }) {
  const navigate = useNavigate()
  const sc = STATUS_CFG[pedido.status] || { label: pedido.status, color: '#9CA3AF', icon: 'circle' }
  const cc = CANAL_CFG[pedido.canal] || { label: pedido.canal, color: '#9CA3AF', icon: 'circle' }

  const handleClick = () => {
    if (pedido.canal === 'ifood') {
      navigate('/integracoes/ifood', { state: { openPedidoId: pedido.origem_id } })
    }
  }

  return (
    <div className={styles.row} onClick={handleClick} title="Ver pedido">
      <div className={styles.rowCanal}>
        <span className={styles.canalBadge} style={{ background: cc.color + '22', color: cc.color }}>
          <i className={`ti ti-${cc.icon}`} />
          {cc.label}
        </span>
      </div>

      <div className={styles.rowNumero}>
        <span className={styles.numero}>#{pedido.numero}</span>
        <span className={styles.hora}>{fmtHora(pedido.data)}</span>
      </div>

      <div className={styles.rowData}>{fmtData(pedido.data)}</div>

      <div className={styles.rowTipo}>
        {pedido.tipo === 'DELIVERY' ? '🛵 Delivery' : pedido.tipo === 'TAKEOUT' ? '🏠 Retirada' : pedido.tipo === 'INDOOR' ? '🪑 Mesa' : pedido.tipo_label}
      </div>

      <div className={styles.rowTotal}>{fmtMoeda(pedido.total)}</div>

      <div className={styles.rowStatus}>
        <span className={styles.statusBadge} style={{ background: sc.color + '22', color: sc.color, borderColor: sc.color + '44' }}>
          <i className={`ti ti-${sc.icon}`} />
          {sc.label}
        </span>
      </div>

      <div className={styles.rowAcao}>
        <i className="ti ti-chevron-right" style={{ color: 'var(--muted)', fontSize: 14 }} />
      </div>
    </div>
  )
}

// ── Componente principal ────────────────────────────────────────────────────
export default function HistoricoPedidos({ clienteId }) {
  const [tab, setTab]           = useState('Todos')
  const [pedidos, setPedidos]   = useState([])
  const [metricas, setMetricas] = useState(null)
  const [loading, setLoading]   = useState(true)
  const [erro, setErro]         = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setErro(null)
    try {
      const canal = TAB_CANAL[tab]
      const params = canal ? { canal } : {}
      const { data } = await clientesApi.historico(clienteId, params)
      setPedidos(data.pedidos || [])
      setMetricas(data.metricas || null)
    } catch (e) {
      setErro('Não foi possível carregar o histórico.')
    } finally {
      setLoading(false)
    }
  }, [clienteId, tab])

  useEffect(() => { load() }, [load])

  return (
    <div className={styles.wrapper}>
      {/* ── Métricas ── */}
      {metricas && (
        <div className={styles.metricsRow}>
          <MetricCard
            icon="shopping-bag"
            label="Total de pedidos"
            value={metricas.total_pedidos}
          />
          <MetricCard
            icon="currency-dollar"
            label="Total gasto"
            value={fmtMoeda(metricas.total_gasto)}
            accent
          />
          <MetricCard
            icon="chart-bar"
            label="Ticket médio"
            value={fmtMoeda(metricas.ticket_medio)}
          />
          <MetricCard
            icon="calendar"
            label="Último pedido"
            value={fmtData(metricas.ultimo_pedido_em)}
          />
        </div>
      )}

      {/* ── Distribuição por canal ── */}
      {metricas && (
        <div className={styles.canalDistrib}>
          {Object.entries(metricas.por_canal).map(([canal, qtd]) => {
            const cc = CANAL_CFG[canal] || { label: canal, color: '#9CA3AF', icon: 'circle' }
            return (
              <div key={canal} className={styles.canalItem}>
                <i className={`ti ti-${cc.icon}`} style={{ color: cc.color }} />
                <span style={{ color: 'var(--bege)' }}>{qtd}</span>
                <span style={{ color: 'var(--muted)', fontSize: 11 }}>{cc.label}</span>
              </div>
            )
          })}
        </div>
      )}

      {/* ── Tabs ── */}
      <div className={styles.tabs}>
        {TABS.map(t => (
          <button
            key={t}
            className={`${styles.tab} ${tab === t ? styles.tabActive : ''}`}
            onClick={() => setTab(t)}
          >
            {t}
            {t !== 'Todos' && metricas && (
              <span className={styles.tabCount}>
                {metricas.por_canal[TAB_CANAL[t]] ?? 0}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Tabela ── */}
      {loading ? (
        <div className={styles.center}><Spinner size={22} /></div>
      ) : erro ? (
        <div className={styles.center} style={{ color: '#EF4444' }}>
          <i className="ti ti-alert-circle" style={{ fontSize: 22 }} />
          <p style={{ fontSize: 13, marginTop: 6 }}>{erro}</p>
        </div>
      ) : pedidos.length === 0 ? (
        <div className={styles.empty}>
          <i className="ti ti-shopping-bag-x" />
          <p>Nenhum pedido encontrado{tab !== 'Todos' ? ` em ${tab}` : ''}.</p>
        </div>
      ) : (
        <div className={styles.table}>
          <div className={styles.thead}>
            <span>Canal</span>
            <span>Pedido</span>
            <span>Data</span>
            <span>Tipo</span>
            <span>Valor</span>
            <span>Status</span>
            <span></span>
          </div>
          {pedidos.map(p => (
            <PedidoRow key={`${p.canal}-${p.id}`} pedido={p} />
          ))}
        </div>
      )}
    </div>
  )
}
