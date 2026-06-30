import { useState, useEffect, useCallback, useRef } from 'react'
import { configWhatsappApi, notificacoesApi } from '../api/services'
import styles from './Configuracoes.module.css'

const PLACEHOLDER_MSG = '{nome} será substituído pelo primeiro nome do cliente.'

function Toggle({ label, checked, onChange }) {
  return (
    <label className={styles.toggle}>
      <span className={styles.toggleLabel}>{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        className={`${styles.toggleBtn} ${checked ? styles.toggleOn : ''}`}
        onClick={() => onChange(!checked)}
      >
        <span className={styles.toggleThumb} />
      </button>
    </label>
  )
}

function StatusBadge({ state }) {
  const map = {
    open:           { label: 'Conectado',       cls: styles.badgeGreen },
    close:          { label: 'Desconectado',     cls: styles.badgeRed   },
    not_configured: { label: 'Não configurado',  cls: styles.badgeGray  },
    error:          { label: 'Erro',             cls: styles.badgeRed   },
  }
  const { label, cls } = map[state] || { label: state, cls: styles.badgeGray }
  return <span className={`${styles.badge} ${cls}`}>{label}</span>
}

export default function Configuracoes() {
  const [form,      setForm]      = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [saving,    setSaving]    = useState(false)
  const [testing,   setTesting]   = useState(false)
  const [connState, setConnState] = useState(null)
  const [toast,     setToast]     = useState(null)
  const pollRef = useRef(null)

  const showToast = (msg, type = 'ok') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3500)
  }

  const refreshConn = useCallback(async () => {
    try {
      const { data } = await notificacoesApi.statusConexao()
      setConnState(data.state === 'open' ? 'open' : 'close')
    } catch {
      setConnState('error')
    }
  }, [])

  const load = useCallback(async () => {
    try {
      const { data } = await configWhatsappApi.get()
      setForm(data)
      setConnState(data.whatsapp_conectado ? 'open' : 'close')
    } catch {
      showToast('Erro ao carregar configurações.', 'err')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    pollRef.current = setInterval(refreshConn, 30_000)
    return () => clearInterval(pollRef.current)
  }, [load, refreshConn])

  const set = (field, value) => setForm(f => ({ ...f, [field]: value }))

  const salvar = async () => {
    setSaving(true)
    try {
      const { data } = await configWhatsappApi.update(form)
      setForm(data)
      showToast('Configurações salvas com sucesso.')
    } catch {
      showToast('Erro ao salvar configurações.', 'err')
    } finally {
      setSaving(false)
    }
  }

  const testar = async () => {
    setTesting(true)
    try {
      const { data } = await configWhatsappApi.testar()
      setConnState(data.ok ? 'open' : 'error')
      showToast(data.ok ? 'Conexão Z-API OK!' : `Falha: ${data.detail || 'erro desconhecido'}`, data.ok ? 'ok' : 'err')
    } catch {
      setConnState('error')
      showToast('Falha ao testar conexão.', 'err')
    } finally {
      setTesting(false)
    }
  }

  if (loading) return <div className={styles.loading}><i className="ti ti-loader-2" /> Carregando…</div>

  return (
    <div className={styles.page}>
      {toast && (
        <div className={`${styles.toast} ${toast.type === 'err' ? styles.toastErr : ''}`}>
          <i className={`ti ti-${toast.type === 'err' ? 'alert-circle' : 'circle-check'}`} />
          {toast.msg}
        </div>
      )}

      <div className={styles.header}>
        <h1 className="serif">Configurações</h1>
        <button className={styles.btnSave} onClick={salvar} disabled={saving}>
          {saving ? <><i className="ti ti-loader-2" /> Salvando…</> : <><i className="ti ti-device-floppy" /> Salvar tudo</>}
        </button>
      </div>

      {/* ── Z-API ─────────────────────────────────────────────── */}
      <section className={styles.card}>
        <div className={styles.cardHeader}>
          <i className="ti ti-brand-whatsapp" />
          <h2>Credenciais Z-API</h2>
          {connState && <StatusBadge state={connState} />}
          {!connState && <span className={`${styles.badge} ${styles.badgeGray}`}>Verificando…</span>}
        </div>

        <div className={styles.grid3}>
          <label className={styles.field}>
            <span>Instance ID</span>
            <input
              type="text"
              value={form.zapi_instance_id}
              onChange={e => set('zapi_instance_id', e.target.value)}
              placeholder="3F44AD8F..."
            />
          </label>
          <label className={styles.field}>
            <span>Token</span>
            <input
              type="password"
              value={form.zapi_token}
              onChange={e => set('zapi_token', e.target.value)}
              placeholder="664FD7CD..."
            />
          </label>
          <label className={styles.field}>
            <span>Client-Token</span>
            <input
              type="password"
              value={form.zapi_client_token}
              onChange={e => set('zapi_client_token', e.target.value)}
              placeholder="F8af9ded..."
            />
          </label>
        </div>

        <button className={styles.btnTest} onClick={testar} disabled={testing}>
          {testing ? <><i className="ti ti-loader-2" /> Testando…</> : <><i className="ti ti-plug" /> Testar conexão</>}
        </button>
      </section>

      {/* ── Notificações de Pedidos ───────────────────────────── */}
      <section className={styles.card}>
        <div className={styles.cardHeader}>
          <i className="ti ti-shopping-bag" />
          <h2>Notificações de Pedidos</h2>
        </div>
        <Toggle
          label="Enviar WhatsApp a cada mudança de status (PDV, iFood e Eventos)"
          checked={form.notificacoes_pedido_ativo}
          onChange={v => set('notificacoes_pedido_ativo', v)}
        />
        <p className={styles.hint}>
          Quando ativo, o cliente recebe uma mensagem automática a cada etapa do pedido
          (confirmado, em preparo, pronto, concluído, cancelado).
        </p>
      </section>

      {/* ── Aniversários ──────────────────────────────────────── */}
      <section className={styles.card}>
        <div className={styles.cardHeader}>
          <i className="ti ti-cake" />
          <h2>Parabéns de Aniversário</h2>
        </div>
        <Toggle
          label="Enviar mensagem de aniversário (cron diário)"
          checked={form.aniversario_ativo}
          onChange={v => set('aniversario_ativo', v)}
        />
        <label className={styles.field} style={{ marginTop: 16 }}>
          <span>Mensagem</span>
          <textarea
            rows={4}
            value={form.mensagem_aniversario}
            onChange={e => set('mensagem_aniversario', e.target.value)}
          />
        </label>
        <p className={styles.hint}>{PLACEHOLDER_MSG}</p>
      </section>

      {/* ── Orçamentos ────────────────────────────────────────── */}
      <section className={styles.card}>
        <div className={styles.cardHeader}>
          <i className="ti ti-file-invoice" />
          <h2>Orçamentos</h2>
        </div>
        <label className={styles.field} style={{ maxWidth: 240 }}>
          <span>Validade padrão (dias)</span>
          <input
            type="number"
            min={1}
            max={365}
            value={form.validade_orcamento_dias}
            onChange={e => set('validade_orcamento_dias', parseInt(e.target.value) || 30)}
          />
        </label>
        <p className={styles.hint}>
          Ao criar um orçamento sem informar a data de validade, ela será preenchida automaticamente
          com esta quantidade de dias a partir de hoje.
        </p>
      </section>

      {/* ── Reengajamento ─────────────────────────────────────── */}
      <section className={styles.card}>
        <div className={styles.cardHeader}>
          <i className="ti ti-user-heart" />
          <h2>Reengajamento de Clientes</h2>
        </div>
        <Toggle
          label="Avisar clientes sem compras há X dias (cron diário)"
          checked={form.reengajamento_ativo}
          onChange={v => set('reengajamento_ativo', v)}
        />
        <label className={styles.field} style={{ marginTop: 16, maxWidth: 200 }}>
          <span>Dias sem compra para disparar</span>
          <input
            type="number"
            min={7}
            max={365}
            value={form.dias_sem_compra}
            onChange={e => set('dias_sem_compra', parseInt(e.target.value) || 30)}
          />
        </label>
        <label className={styles.field} style={{ marginTop: 16 }}>
          <span>Mensagem</span>
          <textarea
            rows={4}
            value={form.mensagem_reengajamento}
            onChange={e => set('mensagem_reengajamento', e.target.value)}
          />
        </label>
        <p className={styles.hint}>{PLACEHOLDER_MSG}</p>
      </section>
    </div>
  )
}
