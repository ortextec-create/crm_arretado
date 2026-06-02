/**
 * arretado-crm/src/pages/IFood.jsx
 * Versão completa com atualizações para homologação iFood (Junho 2026)
 *
 * Novidades vs versão anterior:
 *  - NegociacaoAlert: alerta laranja com botões Aceitar/Manter (Cenário 4)
 *  - PedidoDetail reescrito:
 *      • Badge de tipo de pedido (Retirada / Entrega / Agendado)
 *      • Seção de agendamento com data/hora formatada (Cenário 1)
 *      • Cupons com valor e responsabilidade iFood/Loja (Cenário 1)
 *      • Observação do pedido em destaque (Cenário 5)
 *      • CPF/CNPJ do cliente (Cenário 5)
 *      • Bandeira do cartão + pago online vs na entrega (Cenário 2)
 *      • Troco com cálculo automático (Cenário 5)
 *  - handleNegociacao: aceitar ou recusar cancelamento da plataforma
 *  - Badge "⚠ Negociação" na listagem de pedidos
 */

import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ifoodApi, clientesApi } from '../api/services'
import Topbar from '../components/layout/Topbar'
import { Btn, Avatar, Spinner, Toast, Modal, Field, Input } from '../components/ui'
import styles from './IFood.module.css'

// ─── STATUS config ────────────────────────────────────────────────────────────
const STATUS_CFG = {
  PLACED:                  { label: 'Aguardando',     color: '#F59E0B', icon: 'clock' },
  CONFIRMED:               { label: 'Confirmado',     color: '#3B82F6', icon: 'circle-check' },
  PREPARATION_STARTED:     { label: 'Preparando',     color: '#8B5CF6', icon: 'chef-hat' },
  READY_TO_PICKUP:         { label: 'Pronto',         color: '#06B6D4', icon: 'package' },
  DISPATCHED:              { label: 'A caminho',      color: '#6366F1', icon: 'motorbike' },
  CONCLUDED:               { label: 'Concluído',      color: '#22C55E', icon: 'circle-check-filled' },
  CANCELLATION_REQUESTED:  { label: 'Negociação',     color: '#F97316', icon: 'alert-triangle' },
  CANCELLED:               { label: 'Cancelado',      color: '#EF4444', icon: 'circle-x' },
}

const TABS = ['Todos', 'Aguardando', 'Em andamento', 'Concluídos', 'Cancelados']
const TAB_FILTERS = {
  'Todos':        null,
  'Aguardando':   'PLACED',
  'Em andamento': ['CONFIRMED', 'PREPARATION_STARTED', 'READY_TO_PICKUP', 'DISPATCHED'],
  'Concluídos':   'CONCLUDED',
  'Cancelados':   ['CANCELLED', 'CANCELLATION_REQUESTED'],
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function fmtDateTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function fmtMoeda(v) {
  return `R$ ${Number(v || 0).toFixed(2)}`
}

// ─── StatCard ─────────────────────────────────────────────────────────────────
function StatCard({ label, value, icon, accent, warn }) {
  return (
    <div className={`${styles.statCard} ${accent ? styles.statAccent : ''} ${warn ? styles.statWarn : ''}`}>
      <i className={`ti ti-${icon}`} />
      <div>
        <p className={styles.statValue}>{value}</p>
        <p className={styles.statLabel}>{label}</p>
      </div>
    </div>
  )
}

// ─── NegociacaoAlert ──────────────────────────────────────────────────────────
function NegociacaoAlert({ pedido, onAceitar, onRecusar, loading }) {
  if (!pedido?.negociacao_pendente) return null

  const TIPO_LABEL = {
    CANCELLATION_REQUESTED:          'Cancelamento solicitado pela loja',
    CONSUMER_CANCELLATION_REQUESTED: 'Cancelamento solicitado pelo cliente',
    ORDER_CANCELLATION_REQUESTED:    'Cancelamento solicitado',
    NEGOTIATION_REQUESTED:           'Negociação em andamento',
  }
  const label = TIPO_LABEL[pedido.negociacao_tipo] || 'Cancelamento pendente'

  return (
    <div style={{
      background: 'rgba(249,115,22,0.12)',
      border: '1px solid rgba(249,115,22,0.4)',
      borderRadius: 6,
      padding: '12px 16px',
      marginBottom: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <i className="ti ti-alert-triangle" style={{ color: '#F97316', fontSize: 16 }} />
        <span style={{ fontWeight: 700, color: '#F97316', fontSize: 13 }}>{label}</span>
      </div>
      {pedido.negociacao_descricao && (
        <p style={{ fontSize: 12, color: 'var(--muted)', margin: '0 0 10px 24px' }}>
          Motivo: {pedido.negociacao_descricao}
        </p>
      )}
      <div style={{ display: 'flex', gap: 8, marginLeft: 24 }}>
        <button
          disabled={loading}
          onClick={onAceitar}
          style={{
            background: '#22C55E', color: '#fff', border: 'none',
            borderRadius: 4, padding: '6px 14px', fontSize: 12,
            fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? '...' : '✓ Aceitar cancelamento'}
        </button>
        <button
          disabled={loading}
          onClick={onRecusar}
          style={{
            background: 'transparent', color: '#EF4444',
            border: '1px solid #EF4444', borderRadius: 4,
            padding: '6px 14px', fontSize: 12, fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? '...' : '✗ Manter pedido'}
        </button>
      </div>
    </div>
  )
}

// ─── PedidoDetail ─────────────────────────────────────────────────────────────
function PedidoDetail({ pedido, statusCfg, navigate, onCriarCliente, criandoCliente, onVincular, onNegociacao, negociacaoLoading }) {
  const sc  = statusCfg(pedido.status)
  const end = pedido.endereco_entrega || {}

  const BANDEIRA_LABEL = {
    VISA: 'Visa', MASTERCARD: 'Mastercard', ELO: 'Elo',
    AMEX: 'Amex', HIPERCARD: 'Hipercard', HIPER: 'Hiper',
    VR: 'VR', ALELO: 'Alelo', SODEXO: 'Sodexo',
  }
  const bandeiraNome = pedido.payment_brand
    ? (BANDEIRA_LABEL[pedido.payment_brand.toUpperCase()] || pedido.payment_brand)
    : null

  const benefits = Array.isArray(pedido.benefits_raw) ? pedido.benefits_raw : []

  const trocoVal   = Number(pedido.payment_troco  || 0)
  const totalVal   = Number(pedido.total_valor     || 0)
  const trocoLiqui = trocoVal > 0 ? (trocoVal - totalVal) : 0

  return (
    <div className={styles.detail}>

      {/* ── Alerta de Negociação ── */}
      <NegociacaoAlert
        pedido={pedido}
        onAceitar={() => onNegociacao('aceitar', pedido.id)}
        onRecusar={() => onNegociacao('recusar',  pedido.id)}
        loading={negociacaoLoading}
      />

      {/* ── Cabeçalho ── */}
      <div className={styles.detailHeader}>
        <span className={styles.statusBadge}
          style={{ background: sc.color + '22', color: sc.color, borderColor: sc.color + '44', fontSize: 12 }}>
          <i className={`ti ti-${sc.icon}`} /> {sc.label}
        </span>

        {/* Badge tipo pedido */}
        <span style={{
          fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
          background: pedido.order_type === 'TAKEOUT'   ? 'rgba(6,182,212,0.15)'
                    : pedido.order_type === 'SCHEDULED' ? 'rgba(99,102,241,0.15)'
                    : 'rgba(99,102,241,0.10)',
          color:      pedido.order_type === 'TAKEOUT'   ? '#06B6D4'
                    : '#6366F1',
        }}>
          <i className={`ti ti-${pedido.order_type === 'TAKEOUT' ? 'building-store' : 'motorbike'}`}
             style={{ marginRight: 4 }} />
          {pedido.order_type === 'TAKEOUT'   ? 'Retirada no balcão'
          : pedido.order_type === 'SCHEDULED' ? 'Entrega agendada'
          : 'Entrega'}
        </span>

        <span style={{ fontSize: 11, color: 'var(--muted)' }}>
          {fmtDateTime(pedido.ifood_criado_em)}
        </span>
      </div>

      {/* ── Agendamento (Cenário 1) ── */}
      {pedido.agendamento_dt && (
        <div className={styles.detailSection} style={{
          background: 'rgba(99,102,241,0.07)', borderRadius: 6, padding: '10px 14px',
        }}>
          <div className={styles.detailLabel} style={{ color: '#6366F1' }}>
            <i className="ti ti-calendar-event" style={{ marginRight: 4 }} />
            Pedido Agendado
          </div>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--bege)' }}>
            {new Date(pedido.agendamento_dt).toLocaleString('pt-BR', {
              weekday: 'long', day: '2-digit', month: '2-digit',
              year: 'numeric', hour: '2-digit', minute: '2-digit',
            })}
          </span>
        </div>
      )}

      {/* ── Cupons / Benefícios (Cenário 1) ── */}
      {benefits.length > 0 && (
        <div className={styles.detailSection}>
          <div className={styles.detailLabel}>
            <i className="ti ti-ticket" style={{ marginRight: 4 }} />
            Cupons aplicados
          </div>
          {benefits.map((b, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              fontSize: 12, padding: '5px 0',
              borderBottom: i < benefits.length - 1 ? '0.5px solid var(--border)' : 'none',
            }}>
              <span style={{ color: 'var(--bege)' }}>
                🏷 {b.sponsorshipValues?.[0]?.name || b.description || b.type || 'Cupom'}
              </span>
              <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {b.target && (
                  <span style={{
                    fontSize: 10, padding: '1px 6px', borderRadius: 3,
                    background: b.target === 'IFOOD' ? 'rgba(234,29,44,0.15)' : 'rgba(34,197,94,0.15)',
                    color:      b.target === 'IFOOD' ? '#EA1D2C' : '#22C55E',
                    fontWeight: 600,
                  }}>
                    {b.target === 'IFOOD' ? 'iFood' : 'Loja'}
                  </span>
                )}
                <span style={{ color: '#22C55E', fontWeight: 600 }}>
                  − {fmtMoeda(b.value || 0)}
                </span>
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Observação do pedido (Cenário 5) ── */}
      {pedido.observacao_pedido && (
        <div className={styles.detailSection} style={{
          background: 'rgba(245,158,11,0.07)', borderRadius: 6, padding: '10px 14px',
        }}>
          <div className={styles.detailLabel} style={{ color: '#F59E0B' }}>
            <i className="ti ti-notes" style={{ marginRight: 4 }} />
            Observação do pedido
          </div>
          <p style={{ fontSize: 13, color: 'var(--bege)', margin: 0, fontStyle: 'italic' }}>
            "{pedido.observacao_pedido}"
          </p>
        </div>
      )}

      {/* ── Cliente ── */}
      <div className={styles.detailSection}>
        <div className={styles.detailLabel}>Cliente</div>
        {pedido.cliente_nome_crm ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Avatar name={pedido.cliente_nome_crm} />
            <div>
              <div
                style={{ fontSize: 14, fontWeight: 600, color: 'var(--bege)', cursor: 'pointer' }}
                onClick={() => pedido.cliente_crm_id && navigate(`/clientes/${pedido.cliente_crm_id}`)}
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
              {pedido.cliente_cpf && (
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                  <i className="ti ti-id-badge" style={{ fontSize: 11 }} /> CPF/CNPJ: {pedido.cliente_cpf}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className={styles.semClienteBox}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Avatar name={pedido.cliente_nome || '?'} />
              <div>
                <div style={{ fontSize: 14, color: 'var(--bege)' }}>
                  {pedido.cliente_nome || 'Cliente iFood'}
                </div>
                {pedido.cliente_telefone && (
                  <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                    <i className="ti ti-phone" style={{ fontSize: 11 }} /> {pedido.cliente_telefone}
                  </div>
                )}
                {pedido.cliente_cpf && (
                  <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                    <i className="ti ti-id-badge" style={{ fontSize: 11 }} /> CPF/CNPJ: {pedido.cliente_cpf}
                  </div>
                )}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
              <button className={styles.btnMini} onClick={() => onVincular(pedido)}>
                <i className="ti ti-link" /> Vincular ao CRM
              </button>
              <button
                className={styles.btnMini}
                onClick={() => onCriarCliente(pedido)}
                disabled={criandoCliente}
              >
                <i className="ti ti-user-plus" /> Criar no CRM
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Endereço de entrega ── */}
      {pedido.order_type !== 'TAKEOUT' && (end.formattedAddress || end.streetName) && (
        <div className={styles.detailSection}>
          <div className={styles.detailLabel}>Endereço de entrega</div>
          <span style={{ fontSize: 13, color: 'var(--bege)' }}>
            <i className="ti ti-map-pin" style={{ marginRight: 4 }} />
            {end.formattedAddress || `${end.streetName}, ${end.streetNumber} — ${end.neighborhood}`}
          </span>
          {end.complement && (
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
              Complemento: {end.complement}
            </div>
          )}
          {end.reference && (
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
              Referência: {end.reference}
            </div>
          )}
        </div>
      )}

      {/* ── Itens ── */}
      {pedido.itens?.length > 0 && (
        <div className={styles.detailSection}>
          <div className={styles.detailLabel}>Itens</div>
          <div className={styles.itensList}>
            {pedido.itens.map(item => (
              <div key={item.id} className={styles.itemRow}>
                <div style={{ flex: 1 }}>
                  <span className={styles.itemQty}>{item.quantidade}×</span>
                  <span className={styles.itemNome}>{item.nome}</span>
                  {item.observacao && (
                    <div style={{ fontSize: 11, color: '#F59E0B', marginLeft: 20, fontStyle: 'italic' }}>
                      obs: {item.observacao}
                    </div>
                  )}
                  {item.complementos?.length > 0 && (
                    <div style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 20 }}>
                      {item.complementos.map((c, ci) => (
                        <span key={ci}>{c.quantidade > 1 ? `${c.quantidade}× ` : ''}{c.nome} </span>
                      ))}
                    </div>
                  )}
                </div>
                <span className={styles.itemPreco}>{fmtMoeda(item.preco_total)}</span>
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
            <><span style={{ color: 'var(--muted)' }}>Subtotal</span><span>{fmtMoeda(pedido.subtotal)}</span></>
          )}
          {Number(pedido.taxa_entrega) > 0 && (
            <><span style={{ color: 'var(--muted)' }}>Taxa de entrega</span><span>{fmtMoeda(pedido.taxa_entrega)}</span></>
          )}
          {Number(pedido.desconto) > 0 && (
            <><span style={{ color: '#22C55E' }}>Desconto</span>
              <span style={{ color: '#22C55E' }}>− {fmtMoeda(pedido.desconto)}</span></>
          )}
          <>
            <span style={{ fontWeight: 600, color: 'var(--bege)' }}>Total</span>
            <span style={{ fontWeight: 700, color: 'var(--caramelo)', fontSize: 15 }}>
              {fmtMoeda(pedido.total_valor)}
            </span>
          </>
        </div>

        {/* Pagamento detalhado (Cenários 2 e 5) */}
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 5 }}>
          {pedido.payment_method && (
            <div style={{ fontSize: 12, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <i className="ti ti-credit-card" style={{ fontSize: 13 }} />
              <span>
                {bandeiraNome
                  ? `💳 ${bandeiraNome}`
                  : pedido.payment_method}
              </span>
              {pedido.payment_prepaid
                ? <span style={{ marginLeft: 4, color: '#22C55E', fontSize: 11, fontWeight: 600 }}>✓ Pago online</span>
                : <span style={{ marginLeft: 4, color: '#F59E0B', fontSize: 11, fontWeight: 600 }}>Pagar na entrega</span>
              }
            </div>
          )}
          {/* Troco (Cenário 5) */}
          {trocoVal > 0 && (
            <div style={{ fontSize: 12, fontWeight: 600, color: '#F59E0B', display: 'flex', gap: 6, alignItems: 'center' }}>
              <i className="ti ti-coins" style={{ fontSize: 13 }} />
              Troco para: {fmtMoeda(trocoVal)}
              <span style={{ color: 'var(--muted)', fontWeight: 400 }}>
                → troco: {fmtMoeda(trocoLiqui)}
              </span>
            </div>
          )}
        </div>
      </div>

    </div>
  )
}

// ─── ConfigModal ──────────────────────────────────────────────────────────────
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
        client_secret:     '',
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
        <div style={{
          background: 'rgba(234,88,12,0.08)', border: '0.5px solid rgba(234,88,12,0.2)',
          padding: '12px 14px', borderRadius: 2, fontSize: 12, color: '#EA580C',
        }}>
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
            placeholder={config ? '••••••• (deixe vazio para manter)' : 'Informe o secret'}
            value={form.client_secret} onChange={e => set('client_secret', e.target.value)} />
        </Field>
        <Field label="Merchant ID *">
          <Input placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            value={form.merchant_id} onChange={e => set('merchant_id', e.target.value)} />
        </Field>
        <Field label="Intervalo de polling (segundos)">
          <Input type="number" min={30} max={60}
            value={form.polling_intervalo} onChange={e => set('polling_intervalo', Number(e.target.value))} />
        </Field>

        {testResult && (
          <div style={{
            padding: '10px 14px', borderRadius: 4, fontSize: 12,
            background: testResult.ok ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
            color:      testResult.ok ? '#22C55E' : '#EF4444',
            border:     `0.5px solid ${testResult.ok ? '#22C55E' : '#EF4444'}`,
          }}>
            {testResult.ok
              ? `✓ Conexão OK — Merchant: ${testResult.merchant_id}`
              : `✗ Erro: ${testResult.erro}`}
          </div>
        )}

        {config && (
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '10px 14px', background: 'rgba(255,255,255,0.03)',
            borderRadius: 4, border: '0.5px solid var(--border)',
          }}>
            <span style={{ fontSize: 12, color: 'var(--muted)' }}>
              Polling: {config.polling_ativo ? '🟢 Ativo' : '🔴 Pausado'}
            </span>
            <Btn variant="ghost" size="sm" loading={pollingLoading} onClick={togglePolling}>
              {config.polling_ativo ? 'Pausar' : 'Ativar'}
            </Btn>
          </div>
        )}
      </div>
    </Modal>
  )
}

// ─── COMPONENTE PRINCIPAL ─────────────────────────────────────────────────────
export default function IFood() {
  const navigate = useNavigate()
  const pollRef  = useRef(null)

  const [tab,          setTab]          = useState('Todos')
  const [search,       setSearch]       = useState('')
  const [pedidos,      setPedidos]      = useState([])
  const [stats,        setStats]        = useState(null)
  const [statusGeral,  setStatusGeral]  = useState(null)
  const [loading,      setLoading]      = useState(true)
  const [selected,     setSelected]     = useState(null)
  const [config,       setConfig]       = useState(null)

  // Modals
  const [showConfig,   setShowConfig]   = useState(false)
  const [showDetail,   setShowDetail]   = useState(false)
  const [showCancel,   setShowCancel]   = useState(false)
  const [showVincular, setShowVincular] = useState(false)

  const [actionLoading,        setActionLoading]        = useState(null)
  const [negociacaoLoading,    setNegociacaoLoading]    = useState(false)
  const [toast,                setToast]                = useState(null)
  const [cancelReasons,        setCancelReasons]        = useState([])
  const [cancelCode,           setCancelCode]           = useState('')
  const [clientes,             setClientes]             = useState([])
  const [clienteSearch,        setClienteSearch]        = useState('')
  const [pollingManualLoading, setPollingManualLoading] = useState(false)
  const [criandoCliente,       setCriandoCliente]       = useState(false)

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

      if (Array.isArray(statusFilter)) {
        lista = lista.filter(p => statusFilter.includes(p.status))
      }

      setPedidos(lista)
      if (statsRes.status  === 'fulfilled') setStats(statsRes.value.data)
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

  useEffect(() => {
    pollRef.current = setInterval(loadData, 30_000)
    return () => clearInterval(pollRef.current)
  }, [loadData])

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
        case 'confirmar': r = await ifoodApi.confirmar(pedidoId);        break
        case 'despachar': r = await ifoodApi.despachar(pedidoId);        break
        case 'pronto':    r = await ifoodApi.prontoRetirada(pedidoId);   break
        case 'cancelar':  r = await ifoodApi.cancelar(pedidoId, extra);  break
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

  // ── Negociação (Cenário 4) ─────────────────────────────────────────────────
  const handleNegociacao = async (tipo, pedidoId) => {
    setNegociacaoLoading(true)
    try {
      if (tipo === 'aceitar') {
        await ifoodApi.aceitarNegociacao(pedidoId)
        setToast({ message: 'Cancelamento aceito. Pedido será cancelado.', type: 'success' })
      } else {
        await ifoodApi.recusarNegociacao(pedidoId)
        setToast({ message: 'Cancelamento recusado. Pedido mantido.', type: 'success' })
      }
      setShowDetail(false)
      loadData()
    } catch (e) {
      setToast({ message: e?.response?.data?.detail || 'Erro na negociação.', type: 'error' })
    } finally {
      setNegociacaoLoading(false)
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

  const handleCriarCliente = async (pedido) => {
    if (!window.confirm(
      `Criar cliente "${pedido.cliente_nome}" no CRM com os dados do iFood?\nTelefone: ${pedido.cliente_telefone || '(não informado)'}`
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
        const confirma = window.confirm(`${data.detail}\n\nDeseja vincular este pedido ao cliente existente?`)
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

        {/* Stats */}
        {stats && (
          <div className={styles.statsRow}>
            <StatCard label="Pedidos hoje"   value={stats.hoje?.pedidos ?? 0}                       icon="shopping-bag" />
            <StatCard label="Receita hoje"   value={`R$ ${(stats.hoje?.receita ?? 0).toFixed(2)}`} icon="currency-dollar" accent />
            <StatCard label="Aguardando"     value={stats.pendentes ?? 0}                            icon="clock"  warn={stats.pendentes > 0} />
            <StatCard label="Pedidos no mês" value={stats.mes?.pedidos ?? 0}                        icon="calendar" />
            <StatCard label="Receita no mês" value={`R$ ${(stats.mes?.receita ?? 0).toFixed(2)}`}  icon="chart-bar" />
          </div>
        )}

        {/* Tabs */}
        <div className={styles.tabsRow}>
          {TABS.map(t => (
            <button key={t}
              className={`${styles.tab} ${tab === t ? styles.tabActive : ''}`}
              onClick={() => setTab(t)}
            >
              {t}
              {/* Contador de negociações pendentes na aba Cancelados */}
              {t === 'Cancelados' && pedidos.filter(p => p.negociacao_pendente).length > 0 && (
                <span style={{
                  marginLeft: 6, background: '#F97316', color: '#fff',
                  borderRadius: 10, padding: '1px 6px', fontSize: 10, fontWeight: 700,
                }}>
                  {pedidos.filter(p => p.negociacao_pendente).length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Lista de pedidos */}
        {loading ? (
          <div className={styles.center}><Spinner size={26} /></div>
        ) : pedidos.length === 0 ? (
          <div className={styles.center} style={{ color: 'var(--muted)', fontSize: 14 }}>
            Nenhum pedido encontrado.
          </div>
        ) : (
          <div className={styles.pedidosList}>
            {pedidos.map(p => {
              const sc = statusCfg(p.status)
              return (
                <div key={p.id} className={styles.pedidoCard} onClick={() => openDetail(p)}>
                  <div className={styles.pedidoCardTop}>
                    <span className={styles.pedidoId}>#{p.display_id || p.ifood_order_id?.slice(0, 8)}</span>
                    <span className={styles.statusPill}
                      style={{ background: sc.color + '22', color: sc.color, border: `1px solid ${sc.color}44` }}>
                      <i className={`ti ti-${sc.icon}`} style={{ fontSize: 11 }} /> {sc.label}
                    </span>
                    {/* Badge de negociação pendente */}
                    {p.negociacao_pendente && (
                      <span style={{
                        fontSize: 10, padding: '1px 7px', borderRadius: 10,
                        background: 'rgba(249,115,22,0.2)', color: '#F97316', fontWeight: 700,
                        border: '1px solid rgba(249,115,22,0.4)',
                      }}>
                        ⚠ Negociação
                      </span>
                    )}
                  </div>

                  <div className={styles.pedidoCardMid}>
                    <span style={{ fontSize: 13, color: 'var(--bege)' }}>
                      {p.cliente_nome_crm || p.cliente_nome || 'Cliente iFood'}
                    </span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--caramelo)' }}>
                      R$ {Number(p.total_valor || 0).toFixed(2)}
                    </span>
                  </div>

                  <div className={styles.pedidoCardBot}>
                    <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                      <i className={`ti ti-${p.order_type === 'TAKEOUT' ? 'building-store' : 'motorbike'}`}
                         style={{ fontSize: 11, marginRight: 3 }} />
                      {p.order_type === 'TAKEOUT' ? 'Retirada' : 'Entrega'}
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                      {fmtDateTime(p.ifood_criado_em)}
                    </span>
                    <div className={styles.cardActions} onClick={e => e.stopPropagation()}>
                      {p.pode_confirmar && (
                        <button className={styles.actBtn}
                          title="Confirmar"
                          onClick={() => doAction('confirmar', p.id)}>
                          {actionLoading === 'confirmar' + p.id
                            ? <i className="ti ti-loader spin" />
                            : <i className="ti ti-circle-check" />}
                        </button>
                      )}
                      {p.pode_cancelar && (
                        <button className={styles.actBtn} style={{ color: '#EF4444' }}
                          title="Cancelar"
                          onClick={() => openCancel(p)}>
                          <i className="ti ti-circle-x" />
                        </button>
                      )}
                      {!p.cliente_nome_crm && (
                        <button className={styles.actBtn} style={{ color: 'var(--verde)' }}
                          title="Vincular ao CRM"
                          onClick={() => openVincular(p)}>
                          <i className="ti ti-user-plus" />
                        </button>
                      )}
                    </div>
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
                <Btn variant="ghost" icon="circle-x"
                  style={{ marginLeft: 'auto', color: '#EF4444', borderColor: '#EF4444' }}
                  onClick={() => { setShowDetail(false); openCancel(selected) }}>
                  Cancelar
                </Btn>
              )}
              {!selected.cliente_nome_crm && (
                <>
                  <Btn variant="ghost" icon="link"
                    style={{ marginLeft: selected.pode_cancelar ? 0 : 'auto' }}
                    onClick={() => { setShowDetail(false); openVincular(selected) }}>
                    Vincular CRM
                  </Btn>
                  <Btn variant="ghost" icon="user-plus"
                    loading={criandoCliente}
                    onClick={() => handleCriarCliente(selected)}>
                    Criar no CRM
                  </Btn>
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
            onVincular={(p) => { setShowDetail(false); openVincular(p) }}
            onNegociacao={handleNegociacao}
            negociacaoLoading={negociacaoLoading}
          />
        )}
      </Modal>

      {/* ─── MODAL CANCELAMENTO ─── */}
      <Modal
        open={showCancel}
        onClose={() => setShowCancel(false)}
        title="Cancelar pedido"
        width={420}
        footer={
          <>
            <Btn variant="ghost" onClick={() => setShowCancel(false)}>Voltar</Btn>
            <Btn
              loading={actionLoading === 'cancelar' + selected?.id}
              onClick={() => doAction('cancelar', selected?.id, { cancellationCode: cancelCode })}
              style={{ background: '#EF4444', borderColor: '#EF4444' }}
            >
              Confirmar cancelamento
            </Btn>
          </>
        }
      >
        <p style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 14 }}>
          Selecione o motivo do cancelamento do pedido{' '}
          <strong style={{ color: 'var(--bege)' }}>#{selected?.display_id}</strong>:
        </p>
        {cancelReasons.length > 0 ? (
          <Field label="Motivo do cancelamento">
            <select className={styles.select} value={cancelCode}
              onChange={e => setCancelCode(e.target.value)}>
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