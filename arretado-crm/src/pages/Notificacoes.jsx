import { useState, useEffect, useCallback } from 'react'
import { notificacoesApi, clientesApi } from '../api/services'
import styles from './Notificacoes.module.css'

const TIPO_LABEL   = { manual: 'Manual', aniversario: 'Aniversário', lembrete: 'Lembrete' }
const STATUS_COR   = { enviado: 'var(--verde)', falha: '#ef4444', pendente: 'var(--muted)' }
const STATUS_LABEL = { enviado: 'Enviado', falha: 'Falha', pendente: 'Pendente' }

function dataFmt(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function Notificacoes() {
  const [mensagens, setMensagens]   = useState([])
  const [loading, setLoading]       = useState(true)
  const [conexao, setConexao]       = useState(null)

  const [filtroTipo, setFiltroTipo]     = useState('')
  const [filtroStatus, setFiltroStatus] = useState('')

  const [modalAberto, setModalAberto] = useState(false)
  const [clientes, setClientes]       = useState([])
  const [buscaCliente, setBuscaCliente] = useState('')
  const [clienteSel, setClienteSel]   = useState(null)
  const [telefone, setTelefone]       = useState('')
  const [mensagem, setMensagem]       = useState('')
  const [enviando, setEnviando]       = useState(false)
  const [erro, setErro]               = useState('')
  const [sucesso, setSucesso]         = useState('')

  const carregar = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (filtroTipo)   params.tipo   = filtroTipo
      if (filtroStatus) params.status = filtroStatus
      const res = await notificacoesApi.listar(params)
      setMensagens(res.data.results ?? res.data)
    } catch {
      // silencia — tabela aparece vazia
    } finally {
      setLoading(false)
    }
  }, [filtroTipo, filtroStatus])

  useEffect(() => { carregar() }, [carregar])

  useEffect(() => {
    notificacoesApi.statusConexao()
      .then(r => setConexao(r.data.state ?? r.data.instance?.state ?? 'unknown'))
      .catch(() => setConexao('error'))
  }, [])

  const buscarClientes = async (q) => {
    if (q.length < 2) { setClientes([]); return }
    const res = await clientesApi.list({ search: q, page_size: 8 })
    setClientes(res.data.results ?? res.data)
  }

  const selecionarCliente = (c) => {
    setClienteSel(c)
    setTelefone(c.telefone_principal)
    setBuscaCliente(c.nome)
    setClientes([])
  }

  const limparModal = () => {
    setClienteSel(null)
    setBuscaCliente('')
    setTelefone('')
    setMensagem('')
    setClientes([])
    setErro('')
    setSucesso('')
  }

  const fecharModal = () => {
    setModalAberto(false)
    limparModal()
  }

  const handleEnviar = async (e) => {
    e.preventDefault()
    setErro('')
    setSucesso('')
    setEnviando(true)
    try {
      const payload = { mensagem, tipo: 'manual' }
      if (clienteSel) payload.cliente_id = clienteSel.id
      else            payload.telefone   = telefone
      await notificacoesApi.enviar(payload)
      setSucesso('Mensagem enviada com sucesso!')
      carregar()
      setTimeout(fecharModal, 1500)
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.response?.data?.non_field_errors?.[0]
      setErro(detail || 'Erro ao enviar mensagem.')
    } finally {
      setEnviando(false)
    }
  }

  const corConexao = conexao === 'open' ? 'var(--verde)' : conexao === 'not_configured' ? 'var(--muted)' : '#ef4444'
  const labelConexao = { open: 'Conectado', close: 'Desconectado', connecting: 'Conectando…', not_configured: 'Não configurado', error: 'Erro', unknown: 'Desconhecido' }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={`${styles.title} serif`}>Notificações WhatsApp</h1>
          <p className={styles.sub}>Mensagens enviadas via Evolution API</p>
        </div>
        <div className={styles.headerActions}>
          {conexao !== null && (
            <span className={styles.conexaoBadge} style={{ color: corConexao }}>
              <i className="ti ti-brand-whatsapp" />
              {labelConexao[conexao] ?? conexao}
            </span>
          )}
          <button className={styles.btnPrimary} onClick={() => setModalAberto(true)}>
            <i className="ti ti-send" /> Nova mensagem
          </button>
        </div>
      </div>

      <div className={styles.filtros}>
        <select value={filtroTipo} onChange={e => setFiltroTipo(e.target.value)} className={styles.select}>
          <option value="">Todos os tipos</option>
          {Object.entries(TIPO_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <select value={filtroStatus} onChange={e => setFiltroStatus(e.target.value)} className={styles.select}>
          <option value="">Todos os status</option>
          {Object.entries(STATUS_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      <div className={styles.tableWrap}>
        {loading ? (
          <div className={styles.empty}><i className="ti ti-loader-2" style={{ fontSize: 24 }} /></div>
        ) : mensagens.length === 0 ? (
          <div className={styles.empty}>
            <i className="ti ti-message-off" style={{ fontSize: 32, opacity: 0.3 }} />
            <p>Nenhuma mensagem encontrada.</p>
          </div>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Destinatário</th>
                <th>Mensagem</th>
                <th>Tipo</th>
                <th>Status</th>
                <th>Enviado em</th>
              </tr>
            </thead>
            <tbody>
              {mensagens.map(m => (
                <tr key={m.id}>
                  <td>
                    {m.cliente_nome
                      ? <><strong>{m.cliente_nome}</strong><br /><span className={styles.fone}>{m.telefone}</span></>
                      : <span>{m.telefone}</span>
                    }
                  </td>
                  <td className={styles.msgCell}>{m.mensagem}</td>
                  <td><span className={styles.tipoBadge}>{TIPO_LABEL[m.tipo] ?? m.tipo}</span></td>
                  <td>
                    <span className={styles.statusBadge} style={{ color: STATUS_COR[m.status] }}>
                      <i className={`ti ti-${m.status === 'enviado' ? 'check' : m.status === 'falha' ? 'x' : 'clock'}`} />
                      {STATUS_LABEL[m.status] ?? m.status}
                    </span>
                    {m.erro && <p className={styles.erroMsg}>{m.erro}</p>}
                  </td>
                  <td className={styles.data}>{dataFmt(m.enviado_em)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {modalAberto && (
        <div className={styles.backdrop} onClick={fecharModal}>
          <div className={styles.modal} onClick={e => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h2 className="serif">Nova mensagem</h2>
              <button className={styles.btnClose} onClick={fecharModal}><i className="ti ti-x" /></button>
            </div>

            <form onSubmit={handleEnviar} className={styles.form}>
              <label className={styles.label}>Destinatário</label>
              <div className={styles.autocompleteWrap}>
                <input
                  className={styles.input}
                  placeholder="Buscar cliente pelo nome…"
                  value={buscaCliente}
                  onChange={e => { setBuscaCliente(e.target.value); buscarClientes(e.target.value) }}
                  autoComplete="off"
                />
                {clientes.length > 0 && (
                  <ul className={styles.dropdown}>
                    {clientes.map(c => (
                      <li key={c.id} onClick={() => selecionarCliente(c)}>
                        <strong>{c.nome}</strong>
                        <span>{c.telefone_principal}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <label className={styles.label}>Ou informe o número diretamente</label>
              <input
                className={styles.input}
                placeholder="Ex: 86999999999"
                value={telefone}
                onChange={e => { setTelefone(e.target.value); if (clienteSel) { setClienteSel(null); setBuscaCliente('') } }}
              />

              <label className={styles.label}>Mensagem</label>
              <textarea
                className={styles.textarea}
                rows={4}
                placeholder="Digite a mensagem…"
                value={mensagem}
                onChange={e => setMensagem(e.target.value)}
                required
              />

              {erro    && <p className={styles.erroForm}>{erro}</p>}
              {sucesso && <p className={styles.sucessoForm}>{sucesso}</p>}

              <div className={styles.modalFooter}>
                <button type="button" className={styles.btnSecondary} onClick={fecharModal}>Cancelar</button>
                <button type="submit" className={styles.btnPrimary} disabled={enviando || !mensagem.trim()}>
                  {enviando ? <><i className="ti ti-loader-2" /> Enviando…</> : <><i className="ti ti-send" /> Enviar</>}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
