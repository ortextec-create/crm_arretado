import { useState, useEffect, useCallback, useRef } from 'react'
import { configWhatsappApi, notificacoesApi, configContratoApi } from '../api/services'
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

  const [formContrato,   setFormContrato]   = useState(null)
  const [savingContrato, setSavingContrato] = useState(false)

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

  const loadContrato = useCallback(async () => {
    try {
      const { data } = await configContratoApi.get()
      setFormContrato(data)
    } catch {
      showToast('Erro ao carregar configurações de contrato.', 'err')
    }
  }, [])

  useEffect(() => {
    load()
    loadContrato()
    pollRef.current = setInterval(refreshConn, 30_000)
    return () => clearInterval(pollRef.current)
  }, [load, loadContrato, refreshConn])

  const set = (field, value) => setForm(f => ({ ...f, [field]: value }))
  const setContrato = (field, value) => setFormContrato(f => ({ ...f, [field]: value }))

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

  const salvarContrato = async () => {
    setSavingContrato(true)
    try {
      const { data } = await configContratoApi.update(formContrato)
      setFormContrato(data)
      showToast('Configurações de contrato salvas com sucesso.')
    } catch {
      showToast('Erro ao salvar configurações de contrato.', 'err')
    } finally {
      setSavingContrato(false)
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

      {/* ── Contrato ──────────────────────────────────────────── */}
      {formContrato && (
        <section className={styles.card}>
          <div className={styles.cardHeader}>
            <i className="ti ti-file-signature" />
            <h2>Contrato</h2>
          </div>

          <p className={styles.subLabel}>Dados da CONTRATADA</p>
          <div className={styles.grid3}>
            <label className={styles.field}>
              <span>Razão social</span>
              <input
                type="text"
                value={formContrato.razao_social_contratada}
                onChange={e => setContrato('razao_social_contratada', e.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span>CNPJ</span>
              <input
                type="text"
                value={formContrato.cnpj_contratada}
                onChange={e => setContrato('cnpj_contratada', e.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span>Endereço</span>
              <input
                type="text"
                value={formContrato.endereco_contratada}
                onChange={e => setContrato('endereco_contratada', e.target.value)}
              />
            </label>
          </div>

          <p className={styles.subLabel}>Representante legal</p>
          <div className={styles.grid3}>
            <label className={styles.field}>
              <span>Nome</span>
              <input
                type="text"
                value={formContrato.representante_nome}
                onChange={e => setContrato('representante_nome', e.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span>Nacionalidade</span>
              <input
                type="text"
                value={formContrato.representante_nacionalidade}
                onChange={e => setContrato('representante_nacionalidade', e.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span>Estado civil</span>
              <input
                type="text"
                value={formContrato.representante_estado_civil}
                onChange={e => setContrato('representante_estado_civil', e.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span>Profissão</span>
              <input
                type="text"
                value={formContrato.representante_profissao}
                onChange={e => setContrato('representante_profissao', e.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span>RG</span>
              <input
                type="text"
                value={formContrato.representante_rg}
                onChange={e => setContrato('representante_rg', e.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span>CPF</span>
              <input
                type="text"
                value={formContrato.representante_cpf}
                onChange={e => setContrato('representante_cpf', e.target.value)}
              />
            </label>
          </div>
          <label className={styles.field} style={{ marginTop: 14 }}>
            <span>Endereço do representante</span>
            <input
              type="text"
              value={formContrato.representante_endereco}
              onChange={e => setContrato('representante_endereco', e.target.value)}
            />
          </label>

          <p className={styles.subLabel}>Condições financeiras</p>
          <div className={styles.grid3}>
            <label className={styles.field}>
              <span>Sinal (%)</span>
              <input
                type="number" min={0} max={100} step="0.01"
                value={formContrato.percentual_sinal}
                onChange={e => setContrato('percentual_sinal', e.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span>Quitação (dias antes do evento)</span>
              <input
                type="number" min={0}
                value={formContrato.prazo_quitacao_dias}
                onChange={e => setContrato('prazo_quitacao_dias', parseInt(e.target.value) || 0)}
              />
            </label>
            <label className={styles.field}>
              <span>Multa por inadimplência (%)</span>
              <input
                type="number" min={0} step="0.01"
                value={formContrato.multa_inadimplencia_pct}
                onChange={e => setContrato('multa_inadimplencia_pct', e.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span>Juros de mora (% ao mês)</span>
              <input
                type="number" min={0} step="0.01"
                value={formContrato.juros_mora_pct_mes}
                onChange={e => setContrato('juros_mora_pct_mes', e.target.value)}
              />
            </label>
          </div>

          <p className={styles.subLabel}>Prazos (dias)</p>
          <div className={styles.grid3}>
            <label className={styles.field}>
              <span>Personalização</span>
              <input
                type="number" min={0}
                value={formContrato.prazo_personalizacao_dias}
                onChange={e => setContrato('prazo_personalizacao_dias', parseInt(e.target.value) || 0)}
              />
            </label>
            <label className={styles.field}>
              <span>Aumento de quantidade</span>
              <input
                type="number" min={0}
                value={formContrato.prazo_aumento_quantidade_dias}
                onChange={e => setContrato('prazo_aumento_quantidade_dias', parseInt(e.target.value) || 0)}
              />
            </label>
            <label className={styles.field}>
              <span>Aviso prévio de rescisão</span>
              <input
                type="number" min={0}
                value={formContrato.prazo_aviso_rescisao_dias}
                onChange={e => setContrato('prazo_aviso_rescisao_dias', parseInt(e.target.value) || 0)}
              />
            </label>
            <label className={styles.field}>
              <span>Devolução de valores</span>
              <input
                type="number" min={0}
                value={formContrato.prazo_devolucao_dias}
                onChange={e => setContrato('prazo_devolucao_dias', parseInt(e.target.value) || 0)}
              />
            </label>
          </div>

          <p className={styles.subLabel}>Multas de rescisão (por antecedência)</p>
          <div className={styles.grid3}>
            <label className={styles.field}>
              <span>Acima de 60 dias (%)</span>
              <input
                type="number" min={0} step="0.01"
                value={formContrato.multa_rescisao_acima_60_dias_pct}
                onChange={e => setContrato('multa_rescisao_acima_60_dias_pct', e.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span>Entre 30 e 60 dias (%)</span>
              <input
                type="number" min={0} step="0.01"
                value={formContrato.multa_rescisao_30_60_dias_pct}
                onChange={e => setContrato('multa_rescisao_30_60_dias_pct', e.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span>Menos de 30 dias (%)</span>
              <input
                type="number" min={0} step="0.01"
                value={formContrato.multa_rescisao_abaixo_30_dias_pct}
                onChange={e => setContrato('multa_rescisao_abaixo_30_dias_pct', e.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span>Menos de 7 dias / pós-produção (%)</span>
              <input
                type="number" min={0} step="0.01"
                value={formContrato.multa_rescisao_abaixo_7_dias_pct}
                onChange={e => setContrato('multa_rescisao_abaixo_7_dias_pct', e.target.value)}
              />
            </label>
          </div>

          <p className={styles.subLabel}>Foro</p>
          <div className={styles.grid3}>
            <label className={styles.field}>
              <span>Comarca</span>
              <input
                type="text"
                value={formContrato.foro_comarca}
                onChange={e => setContrato('foro_comarca', e.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span>Estado</span>
              <input
                type="text"
                value={formContrato.foro_estado}
                onChange={e => setContrato('foro_estado', e.target.value)}
              />
            </label>
          </div>

          <button className={styles.btnTest} onClick={salvarContrato} disabled={savingContrato}>
            {savingContrato
              ? <><i className="ti ti-loader-2" /> Salvando…</>
              : <><i className="ti ti-device-floppy" /> Salvar dados do contrato</>}
          </button>
        </section>
      )}
    </div>
  )
}
