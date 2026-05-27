import { useState, useEffect, useCallback } from 'react'
import { eventosApi, locaisEventoApi, clientesApi } from '../api/services'
import { pdvApi } from '../api/services'
import { Btn, Modal, Spinner, Toast } from '../components/ui'
import styles from './Eventos.module.css'

// ─── Helpers ─────────────────────────────────────────────────────────────────

const TIPO_EVENTO_LABELS = {
  casamento:   'Casamento',
  formatura:   'Formatura',
  aniversario: 'Aniversário',
  corporativo: 'Corporativo',
  batizado:    'Batizado',
  cha:         'Chá de bebê / revelação',
  outro:       'Outro',
}

const TIPO_EVENTO_ICONS = {
  casamento:   'ti-heart',
  formatura:   'ti-school',
  aniversario: 'ti-cake',
  corporativo: 'ti-briefcase',
  batizado:    'ti-star',
  cha:         'ti-baby-carriage',
  outro:       'ti-calendar-event',
}

const STATUS_CONFIG = {
  orcamento:   { label: 'Orçamento',    color: '#6B7280' },
  confirmado:  { label: 'Confirmado',   color: '#2563EB' },
  em_producao: { label: 'Em produção',  color: '#D97706' },
  pronto:      { label: 'Pronto',       color: '#059669' },
  entregue:    { label: 'Entregue',     color: '#7C3AED' },
  cancelado:   { label: 'Cancelado',    color: '#DC2626' },
}

const STATUS_TABS = [
  { key: '',           label: 'Todos' },
  { key: 'orcamento',  label: 'Orçamento' },
  { key: 'confirmado', label: 'Confirmado' },
  { key: 'em_producao',label: 'Em produção' },
  { key: 'pronto',     label: 'Pronto' },
  { key: 'entregue',   label: 'Entregue' },
]

const fmt = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const fmtData = (d) => {
  if (!d) return '—'
  const [y, m, day] = d.split('-')
  return `${day}/${m}/${y}`
}
const mesAtual = () => {
  const n = new Date()
  return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}`
}

// ─── Componente principal ─────────────────────────────────────────────────────

export default function Eventos() {
  const [view,       setView]       = useState('lista')   // 'lista' | 'agenda'
  const [eventos,    setEventos]    = useState([])
  const [stats,      setStats]      = useState(null)
  const [agenda,     setAgenda]     = useState({})
  const [loading,    setLoading]    = useState(true)
  const [statusTab,  setStatusTab]  = useState('')
  const [search,     setSearch]     = useState('')
  const [mes,        setMes]        = useState(mesAtual())
  const [toast,      setToast]      = useState(null)

  // Modais
  const [showNovo,    setShowNovo]    = useState(false)
  const [showDetalhe, setShowDetalhe] = useState(false)
  const [eventoAtivo, setEventoAtivo] = useState(null)

  // ── Carregamento ──────────────────────────────────────────────────────────

  const loadEventos = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (statusTab)  params.status = statusTab
      if (search)     params.search = search
      if (view === 'agenda') params.mes = mes
      const res = await eventosApi.list(params)
      setEventos(res.data.results ?? res.data)
    } catch { /* silencioso */ }
    finally { setLoading(false) }
  }, [statusTab, search, view, mes])

  const loadStats = useCallback(async () => {
    try {
      const res = await eventosApi.estatisticas()
      setStats(res.data)
    } catch { /* silencioso */ }
  }, [])

  const loadAgenda = useCallback(async () => {
    try {
      const res = await eventosApi.agenda(mes)
      setAgenda(res.data.agenda ?? {})
    } catch { /* silencioso */ }
  }, [mes])

  useEffect(() => { loadEventos(); loadStats() }, [loadEventos, loadStats])
  useEffect(() => { if (view === 'agenda') loadAgenda() }, [view, loadAgenda])

  // ── Ação de status ────────────────────────────────────────────────────────

  const handleAcao = async (acao, eventoId) => {
    try {
      const fn = {
        confirmar:       () => eventosApi.confirmar(eventoId),
        iniciar_producao:() => eventosApi.iniciarProducao(eventoId),
        marcar_pronto:   () => eventosApi.marcarPronto(eventoId),
        entregar:        () => eventosApi.entregar(eventoId),
        cancelar:        () => eventosApi.cancelar(eventoId),
      }[acao]
      if (!fn) return
      const res = await fn()
      setEventoAtivo(res.data)
      loadEventos(); loadStats()
      setToast({ message: 'Status atualizado com sucesso.', type: 'success' })
    } catch {
      setToast({ message: 'Erro ao atualizar status.', type: 'error' })
    }
  }

  const abrirDetalhe = async (id) => {
    try {
      const res = await eventosApi.detail(id)
      setEventoAtivo(res.data)
      setShowDetalhe(true)
    } catch {
      setToast({ message: 'Erro ao carregar evento.', type: 'error' })
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className={styles.page}>
      {/* ── Topbar ──────────────────────────────────────────────────── */}
      <div className={styles.topbar}>
        <div className={styles.topbarLeft}>
          <h1 className={`serif ${styles.title}`}>Eventos</h1>
          <p className={styles.subtitle}>Agendamento de bolos, doces finos e salgados para festas</p>
        </div>
        <div className={styles.topbarRight}>
          <div className={styles.viewToggle}>
            <button
              className={`${styles.toggleBtn} ${view === 'lista'  ? styles.toggleActive : ''}`}
              onClick={() => setView('lista')}
            >
              <i className="ti ti-list" /> Lista
            </button>
            <button
              className={`${styles.toggleBtn} ${view === 'agenda' ? styles.toggleActive : ''}`}
              onClick={() => setView('agenda')}
            >
              <i className="ti ti-calendar-month" /> Agenda
            </button>
          </div>
          <Btn icon="plus" onClick={() => setShowNovo(true)}>Novo Evento</Btn>
        </div>
      </div>

      {/* ── Stats ───────────────────────────────────────────────────── */}
      {stats && (
        <div className={styles.statsRow}>
          <StatCard icon="ti-calendar-event" label="Eventos este mês"    value={stats.eventos_mes} />
          <StatCard icon="ti-currency-dollar" label="Faturamento (entregues)" value={fmt(stats.faturamento_mes)} />
          <StatCard icon="ti-clock"           label="Próximos 7 dias"    value={stats.proximos_7_dias?.length ?? 0} />
          <StatCard
            icon="ti-alert-circle"
            label="Em produção"
            value={stats.por_status?.em_producao ?? 0}
            accent
          />
        </div>
      )}

      {/* ── Próximos eventos (mini-lista no topo) ───────────────────── */}
      {stats?.proximos_7_dias?.length > 0 && (
        <div className={styles.proximosCard}>
          <span className={styles.proximosTitle}>
            <i className="ti ti-bell-ringing" /> Próximos 7 dias
          </span>
          <div className={styles.proximosList}>
            {stats.proximos_7_dias.map(ev => (
              <button
                key={ev.id}
                className={styles.proximoItem}
                onClick={() => abrirDetalhe(ev.id)}
              >
                <i className={`ti ${TIPO_EVENTO_ICONS[ev.tipo_evento] || 'ti-calendar'}`} />
                <span className={styles.proximoData}>{fmtData(ev.data_evento)}</span>
                <span className={styles.proximoNome}>{ev.nome_cliente_display}</span>
                <span className={styles.proximoTipo}>{ev.tipo_evento_display}</span>
                <StatusBadge status={ev.status} />
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Vista Lista ─────────────────────────────────────────────── */}
      {view === 'lista' && (
        <>
          <div className={styles.toolbar}>
            <div className={styles.tabs}>
              {STATUS_TABS.map(t => (
                <button
                  key={t.key}
                  className={`${styles.tab} ${statusTab === t.key ? styles.tabActive : ''}`}
                  onClick={() => setStatusTab(t.key)}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <div className={styles.searchWrap}>
              <i className="ti ti-search" />
              <input
                className={styles.search}
                placeholder="Buscar por nome, número…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
              {search && (
                <button className={styles.clearSearch} onClick={() => setSearch('')}>
                  <i className="ti ti-x" />
                </button>
              )}
            </div>
          </div>

          {loading ? (
            <div className={styles.center}><Spinner size={28} /></div>
          ) : eventos.length === 0 ? (
            <div className={styles.empty}>
              <i className="ti ti-calendar-off" />
              <p>Nenhum evento encontrado.</p>
            </div>
          ) : (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Número</th>
                    <th>Tipo</th>
                    <th>Data do Evento</th>
                    <th>Cliente</th>
                    <th>Entrega</th>
                    <th>Valor Total</th>
                    <th>Saldo</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {eventos.map(ev => (
                    <tr key={ev.id} className={styles.row} onClick={() => abrirDetalhe(ev.id)}>
                      <td className={styles.numero}>{ev.numero}</td>
                      <td>
                        <span className={styles.tipoEvento}>
                          <i className={`ti ${TIPO_EVENTO_ICONS[ev.tipo_evento] || 'ti-calendar'}`} />
                          {ev.tipo_evento_display}
                        </span>
                      </td>
                      <td>
                        <span className={styles.dataEvento}>{fmtData(ev.data_evento)}</span>
                        {ev.hora_evento && (
                          <span className={styles.horaEvento}> {ev.hora_evento.slice(0, 5)}</span>
                        )}
                      </td>
                      <td>
                        <div className={styles.clienteCell}>
                          <span>{ev.nome_cliente_display}</span>
                          {ev.telefone_display && (
                            <span className={styles.tel}>{ev.telefone_display}</span>
                          )}
                        </div>
                      </td>
                      <td>
                        <span className={`${styles.tipoEntrega} ${ev.tipo_entrega === 'entrega_local' ? styles.entregaLocal : ''}`}>
                          <i className={`ti ${ev.tipo_entrega === 'retirada_loja' ? 'ti-building-store' : 'ti-truck-delivery'}`} />
                          {ev.tipo_entrega_display}
                        </span>
                      </td>
                      <td className={styles.valor}>{fmt(ev.valor_total)}</td>
                      <td className={`${styles.valor} ${Number(ev.saldo_restante) > 0 ? styles.saldoPendente : styles.saldoQuitado}`}>
                        {Number(ev.saldo_restante) > 0 ? fmt(ev.saldo_restante) : '✓ Quitado'}
                      </td>
                      <td><StatusBadge status={ev.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ── Vista Agenda ────────────────────────────────────────────── */}
      {view === 'agenda' && (
        <AgendaView
          mes={mes}
          setMes={setMes}
          agenda={agenda}
          onClickEvento={abrirDetalhe}
        />
      )}

      {/* ── Modais ──────────────────────────────────────────────────── */}
      {showNovo && (
        <ModalNovoEvento
          onClose={() => setShowNovo(false)}
          onSaved={() => { setShowNovo(false); loadEventos(); loadStats(); setToast({ message: 'Evento criado com sucesso!', type: 'success' }) }}
        />
      )}

      {showDetalhe && eventoAtivo && (
        <ModalDetalheEvento
          evento={eventoAtivo}
          onClose={() => { setShowDetalhe(false); setEventoAtivo(null) }}
          onAcao={handleAcao}
          onItemAdded={async () => { const r = await eventosApi.detail(eventoAtivo.id); setEventoAtivo(r.data); loadEventos() }}
          onToast={setToast}
        />
      )}

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}

// ─── Sub-componentes ──────────────────────────────────────────────────────────

function StatCard({ icon, label, value, accent }) {
  return (
    <div className={`${styles.statCard} ${accent ? styles.statAccent : ''}`}>
      <i className={`ti ${icon} ${styles.statIcon}`} />
      <div>
        <p className={styles.statValue}>{value}</p>
        <p className={styles.statLabel}>{label}</p>
      </div>
    </div>
  )
}

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || { label: status, color: '#6B7280' }
  return (
    <span className={styles.badge} style={{ '--badge-color': cfg.color }}>
      {cfg.label}
    </span>
  )
}

// ─── Vista Agenda (calendário mensal) ─────────────────────────────────────────

function AgendaView({ mes, setMes, agenda, onClickEvento }) {
  const [ano, m] = mes.split('-').map(Number)

  const navMes = (delta) => {
    const d = new Date(ano, m - 1 + delta, 1)
    setMes(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
  }

  const diasNoMes = new Date(ano, m, 0).getDate()
  const primeiroDia = new Date(ano, m - 1, 1).getDay() // 0=Dom

  const MESES_PT = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
                    'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']

  const celulas = []
  // Células vazias do início
  for (let i = 0; i < primeiroDia; i++) celulas.push(null)
  // Dias do mês
  for (let d = 1; d <= diasNoMes; d++) celulas.push(d)

  return (
    <div className={styles.agendaWrap}>
      <div className={styles.agendaHeader}>
        <button className={styles.agendaNav} onClick={() => navMes(-1)}>
          <i className="ti ti-chevron-left" />
        </button>
        <h2 className={`serif ${styles.agendaMes}`}>
          {MESES_PT[m - 1]} {ano}
        </h2>
        <button className={styles.agendaNav} onClick={() => navMes(1)}>
          <i className="ti ti-chevron-right" />
        </button>
      </div>

      <div className={styles.agendaGrid}>
        {['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'].map(d => (
          <div key={d} className={styles.agendaDiaSemana}>{d}</div>
        ))}
        {celulas.map((dia, idx) => {
          if (!dia) return <div key={`empty-${idx}`} className={styles.agendaCelula} />
          const key = `${ano}-${String(m).padStart(2,'0')}-${String(dia).padStart(2,'0')}`
          const evsDia = agenda[key] || []
          const hoje = new Date()
          const isHoje = hoje.getDate() === dia && hoje.getMonth() === m - 1 && hoje.getFullYear() === ano
          return (
            <div key={key} className={`${styles.agendaCelula} ${evsDia.length > 0 ? styles.agendaCelulaCom : ''} ${isHoje ? styles.agendaHoje : ''}`}>
              <span className={styles.agendaDiaNum}>{dia}</span>
              <div className={styles.agendaEventosDia}>
                {evsDia.map(ev => (
                  <button
                    key={ev.id}
                    className={styles.agendaEvento}
                    style={{ '--ev-color': STATUS_CONFIG[ev.status]?.color || '#6B7280' }}
                    onClick={() => onClickEvento(ev.id)}
                    title={`${ev.nome_cliente_display} — ${ev.tipo_evento_display}`}
                  >
                    <i className={`ti ${TIPO_EVENTO_ICONS[ev.tipo_evento] || 'ti-calendar'}`} />
                    <span>{ev.nome_cliente_display}</span>
                  </button>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Modal Novo Evento ────────────────────────────────────────────────────────

function ModalNovoEvento({ onClose, onSaved }) {
  const STEPS = ['dados', 'entrega', 'itens', 'financeiro']
  const [step, setStep] = useState(0)

  // Dados do evento
  const [tipoEvento,   setTipoEvento]   = useState('aniversario')
  const [dataEvento,   setDataEvento]   = useState('')
  const [horaEvento,   setHoraEvento]   = useState('')
  const [observacoes,  setObservacoes]  = useState('')

  // Cliente
  const [buscaCliente,    setBuscaCliente]    = useState('')
  const [clienteOptions,  setClienteOptions]  = useState([])
  const [clienteSel,      setClienteSel]      = useState(null)
  const [clienteNome,     setClienteNome]     = useState('')
  const [clienteTel,      setClienteTel]      = useState('')
  const [buscandoCliente, setBuscandoCliente] = useState(false)

  // Entrega
  const [tipoEntrega,    setTipoEntrega]    = useState('retirada_loja')
  const [locais,         setLocais]         = useState([])
  const [localSel,       setLocalSel]       = useState('')
  const [endAvulso,      setEndAvulso]      = useState('')

  // Itens
  const [categorias,     setCategorias]     = useState([])
  const [produtos,       setProdutos]       = useState([])
  const [buscaProd,      setBuscaProd]      = useState('')
  const [catSel,         setCatSel]         = useState('')
  const [carrinho,       setCarrinho]       = useState([])

  // Financeiro
  const [desconto,       setDesconto]       = useState('0')
  const [sinal,          setSinal]          = useState('0')

  const [saving,  setSaving]  = useState(false)
  const [error,   setError]   = useState('')

  // Carrega locais e catálogo
  useEffect(() => {
    locaisEventoApi.list({ ativo: 'true' }).then(r => setLocais(r.data.results ?? r.data)).catch(() => {})
    pdvApi.categorias.list().then(r => setCategorias(r.data.results ?? r.data)).catch(() => {})
    pdvApi.produtos.list({ ativo: 'true' }).then(r => setProdutos(r.data.results ?? r.data)).catch(() => {})
  }, [])

  // Busca de cliente
  useEffect(() => {
    if (!buscaCliente || buscaCliente.length < 2) { setClienteOptions([]); return }
    setBuscandoCliente(true)
    const t = setTimeout(async () => {
      try {
        const r = await clientesApi.list({ search: buscaCliente, status: 'ativo' })
        setClienteOptions(r.data.results ?? r.data)
      } finally { setBuscandoCliente(false) }
    }, 350)
    return () => clearTimeout(t)
  }, [buscaCliente])

  const produtosFiltrados = produtos.filter(p => {
    const okCat  = catSel ? p.categoria === Number(catSel) : true
    const okBusca = buscaProd ? p.nome.toLowerCase().includes(buscaProd.toLowerCase()) : true
    return okCat && okBusca
  })

  const addCarrinho = (prod) => {
    setCarrinho(c => {
      const idx = c.findIndex(i => i.produto === prod.id)
      if (idx >= 0) {
        const n = [...c]; n[idx] = { ...n[idx], quantidade: n[idx].quantidade + 1 }; return n
      }
      return [...c, { produto: prod.id, nome: prod.nome, preco_unit: prod.preco, quantidade: 1, observacao: '' }]
    })
  }
  const setQty = (prodId, qty) => {
    if (qty <= 0) { setCarrinho(c => c.filter(i => i.produto !== prodId)); return }
    setCarrinho(c => c.map(i => i.produto === prodId ? { ...i, quantidade: qty } : i))
  }
  const setObs = (prodId, obs) => {
    setCarrinho(c => c.map(i => i.produto === prodId ? { ...i, observacao: obs } : i))
  }

  const subtotal = carrinho.reduce((s, i) => s + Number(i.preco_unit) * i.quantidade, 0)
  const total    = Math.max(subtotal - Number(desconto || 0), 0)

  const handleSalvar = async () => {
    setError('')
    if (!dataEvento) { setError('Informe a data do evento.'); return }
    if (!clienteSel && !clienteNome) { setError('Informe o cliente.'); return }
    setSaving(true)
    try {
      await eventosApi.create({
        cliente:          clienteSel?.id || null,
        cliente_nome:     clienteSel ? clienteSel.nome : clienteNome,
        cliente_telefone: clienteSel ? (clienteSel.telefone_principal || '') : clienteTel,
        tipo_evento:      tipoEvento,
        data_evento:      dataEvento,
        hora_evento:      horaEvento || null,
        tipo_entrega:     tipoEntrega,
        local:            tipoEntrega === 'entrega_local' && localSel ? Number(localSel) : null,
        endereco_avulso:  tipoEntrega === 'entrega_local' && !localSel ? endAvulso : '',
        desconto:         Number(desconto || 0),
        sinal_pago:       Number(sinal || 0),
        observacoes,
        itens: carrinho.map(i => ({
          produto:    i.produto,
          nome:       i.nome,
          preco_unit: i.preco_unit,
          quantidade: i.quantidade,
          observacao: i.observacao,
        })),
      })
      onSaved()
    } catch (e) {
      setError('Erro ao salvar evento. Verifique os dados e tente novamente.')
    } finally {
      setSaving(false)
    }
  }

  const STEP_LABELS = ['Dados do Evento', 'Entrega', 'Itens', 'Financeiro']

  return (
    <Modal title="Novo Evento" onClose={onClose} wide>
      {/* Stepper */}
      <div className={styles.stepper}>
        {STEP_LABELS.map((l, i) => (
          <div
            key={l}
            className={`${styles.stepItem} ${i === step ? styles.stepAtivo : ''} ${i < step ? styles.stepConcluido : ''}`}
            onClick={() => i < step && setStep(i)}
          >
            <div className={styles.stepCircle}>{i < step ? <i className="ti ti-check" /> : i + 1}</div>
            <span>{l}</span>
          </div>
        ))}
      </div>

      <div className={styles.stepContent}>

        {/* ── Step 0: Dados ──────────────────────────────────────────── */}
        {step === 0 && (
          <div className={styles.formGrid}>
            <div className={styles.formGroup}>
              <label>Tipo do Evento</label>
              <select value={tipoEvento} onChange={e => setTipoEvento(e.target.value)}>
                {Object.entries(TIPO_EVENTO_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div className={styles.formGroup}>
              <label>Data do Evento *</label>
              <input type="date" value={dataEvento} onChange={e => setDataEvento(e.target.value)} />
            </div>
            <div className={styles.formGroup}>
              <label>Hora do Evento</label>
              <input type="time" value={horaEvento} onChange={e => setHoraEvento(e.target.value)} />
            </div>

            {/* Busca cliente */}
            <div className={`${styles.formGroup} ${styles.fullRow}`}>
              <label>Cliente (buscar no CRM)</label>
              {clienteSel ? (
                <div className={styles.clienteSelecionado}>
                  <i className="ti ti-user-check" />
                  <span>{clienteSel.nome}</span>
                  <span className={styles.tel}>{clienteSel.telefone_principal}</span>
                  <button onClick={() => { setClienteSel(null); setBuscaCliente('') }}>
                    <i className="ti ti-x" />
                  </button>
                </div>
              ) : (
                <div className={styles.buscaWrap}>
                  <input
                    placeholder="Digite nome, CPF ou telefone…"
                    value={buscaCliente}
                    onChange={e => setBuscaCliente(e.target.value)}
                  />
                  {buscandoCliente && <Spinner size={14} />}
                  {clienteOptions.length > 0 && (
                    <div className={styles.dropdown}>
                      {clienteOptions.map(c => (
                        <button key={c.id} onClick={() => { setClienteSel(c); setClienteOptions([]); setBuscaCliente('') }}>
                          <span>{c.nome}</span>
                          <span className={styles.tel}>{c.telefone_principal}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Cliente avulso (se não encontrou no CRM) */}
            {!clienteSel && (
              <>
                <div className={styles.formGroup}>
                  <label>Nome do cliente (avulso)</label>
                  <input placeholder="Nome" value={clienteNome} onChange={e => setClienteNome(e.target.value)} />
                </div>
                <div className={styles.formGroup}>
                  <label>Telefone</label>
                  <input placeholder="(86) 99999-0000" value={clienteTel} onChange={e => setClienteTel(e.target.value)} />
                </div>
              </>
            )}

            <div className={`${styles.formGroup} ${styles.fullRow}`}>
              <label>Observações</label>
              <textarea
                rows={2}
                placeholder="Informações adicionais sobre o evento…"
                value={observacoes}
                onChange={e => setObservacoes(e.target.value)}
              />
            </div>
          </div>
        )}

        {/* ── Step 1: Entrega ────────────────────────────────────────── */}
        {step === 1 && (
          <div className={styles.formGrid}>
            <div className={`${styles.formGroup} ${styles.fullRow}`}>
              <label>Tipo de Entrega</label>
              <div className={styles.radioGroup}>
                <label className={`${styles.radioCard} ${tipoEntrega === 'retirada_loja' ? styles.radioCardAtivo : ''}`}>
                  <input type="radio" value="retirada_loja" checked={tipoEntrega === 'retirada_loja'} onChange={e => setTipoEntrega(e.target.value)} />
                  <i className="ti ti-building-store" />
                  <div>
                    <strong>Retirada na loja</strong>
                    <span>O cliente retira no estabelecimento</span>
                  </div>
                </label>
                <label className={`${styles.radioCard} ${tipoEntrega === 'entrega_local' ? styles.radioCardAtivo : ''}`}>
                  <input type="radio" value="entrega_local" checked={tipoEntrega === 'entrega_local'} onChange={e => setTipoEntrega(e.target.value)} />
                  <i className="ti ti-truck-delivery" />
                  <div>
                    <strong>Entrega no local da festa</strong>
                    <span>Levamos até o endereço do evento</span>
                  </div>
                </label>
              </div>
            </div>

            {tipoEntrega === 'entrega_local' && (
              <>
                <div className={`${styles.formGroup} ${styles.fullRow}`}>
                  <label>Local cadastrado</label>
                  <select value={localSel} onChange={e => setLocalSel(e.target.value)}>
                    <option value="">— Selecione um local salvo (opcional) —</option>
                    {locais.map(l => (
                      <option key={l.id} value={l.id}>{l.nome} — {l.bairro}</option>
                    ))}
                  </select>
                </div>
                {!localSel && (
                  <div className={`${styles.formGroup} ${styles.fullRow}`}>
                    <label>Endereço avulso</label>
                    <input
                      placeholder="Rua, número, bairro, referência…"
                      value={endAvulso}
                      onChange={e => setEndAvulso(e.target.value)}
                    />
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* ── Step 2: Itens ──────────────────────────────────────────── */}
        {step === 2 && (
          <div className={styles.itensLayout}>
            <div className={styles.catalogo}>
              <div className={styles.catalogoToolbar}>
                <input
                  className={styles.catalogoBusca}
                  placeholder="Buscar produto…"
                  value={buscaProd}
                  onChange={e => setBuscaProd(e.target.value)}
                />
                <select value={catSel} onChange={e => setCatSel(e.target.value)}>
                  <option value="">Todas as categorias</option>
                  {categorias.map(c => <option key={c.id} value={c.id}>{c.nome}</option>)}
                </select>
              </div>
              <div className={styles.produtosList}>
                {produtosFiltrados.map(p => {
                  const noCarrinho = carrinho.find(i => i.produto === p.id)
                  return (
                    <div key={p.id} className={styles.produtoCard}>
                      <div className={styles.produtoInfo}>
                        <span className={styles.produtoNome}>{p.nome}</span>
                        <span className={styles.produtoPreco}>{fmt(p.preco)}</span>
                        {p.categoria_nome && <span className={styles.produtoCat}>{p.categoria_nome}</span>}
                      </div>
                      {noCarrinho ? (
                        <div className={styles.qtyControl}>
                          <button onClick={() => setQty(p.id, noCarrinho.quantidade - 1)}>−</button>
                          <span>{noCarrinho.quantidade}</span>
                          <button onClick={() => setQty(p.id, noCarrinho.quantidade + 1)}>+</button>
                        </div>
                      ) : (
                        <button className={styles.addBtn} onClick={() => addCarrinho(p)}>
                          <i className="ti ti-plus" />
                        </button>
                      )}
                    </div>
                  )
                })}
                {produtosFiltrados.length === 0 && (
                  <p className={styles.semProdutos}>Nenhum produto encontrado.</p>
                )}
              </div>
            </div>

            <div className={styles.carrinho}>
              <h3 className={styles.carrinhoTitle}>
                <i className="ti ti-shopping-cart" /> Pedido
                <span className={styles.carrinhoCount}>{carrinho.length} itens</span>
              </h3>
              {carrinho.length === 0 ? (
                <p className={styles.carrinhoVazio}>Adicione itens do catálogo.</p>
              ) : (
                <>
                  <div className={styles.carrinhoItens}>
                    {carrinho.map(item => (
                      <div key={item.produto} className={styles.carrinhoItem}>
                        <div className={styles.carrinhoItemTop}>
                          <span className={styles.carrinhoItemNome}>{item.nome}</span>
                          <span className={styles.carrinhoItemTotal}>
                            {fmt(Number(item.preco_unit) * item.quantidade)}
                          </span>
                        </div>
                        <div className={styles.carrinhoItemBottom}>
                          <div className={styles.qtyControl}>
                            <button onClick={() => setQty(item.produto, item.quantidade - 1)}>−</button>
                            <span>{item.quantidade}</span>
                            <button onClick={() => setQty(item.produto, item.quantidade + 1)}>+</button>
                          </div>
                          <input
                            className={styles.obsInput}
                            placeholder="Obs. deste item…"
                            value={item.observacao}
                            onChange={e => setObs(item.produto, e.target.value)}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className={styles.carrinhoTotal}>
                    <span>Subtotal</span>
                    <span>{fmt(subtotal)}</span>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* ── Step 3: Financeiro ─────────────────────────────────────── */}
        {step === 3 && (
          <div className={styles.formGrid}>
            <div className={styles.resumoFinanceiro}>
              <div className={styles.resumoLinha}>
                <span>Subtotal</span>
                <span>{fmt(subtotal)}</span>
              </div>
              <div className={styles.formGroup}>
                <label>Desconto (R$)</label>
                <input type="number" min="0" step="0.01" value={desconto} onChange={e => setDesconto(e.target.value)} />
              </div>
              <div className={styles.resumoLinha + ' ' + styles.resumoTotal}>
                <strong>Valor Total</strong>
                <strong>{fmt(total)}</strong>
              </div>
              <div className={styles.formGroup}>
                <label>Sinal / Entrada paga (R$)</label>
                <input type="number" min="0" step="0.01" value={sinal} onChange={e => setSinal(e.target.value)} />
              </div>
              <div className={styles.resumoLinha + ' ' + styles.resumoSaldo}>
                <span>Saldo restante</span>
                <span style={{ color: 'var(--caramelo)', fontWeight: 600 }}>
                  {fmt(Math.max(total - Number(sinal || 0), 0))}
                </span>
              </div>
            </div>

            {/* Resumo do evento */}
            <div className={styles.resumoEvento}>
              <h4 className="serif">Resumo do evento</h4>
              <p><i className={`ti ${TIPO_EVENTO_ICONS[tipoEvento]}`} /> {TIPO_EVENTO_LABELS[tipoEvento]}</p>
              <p><i className="ti ti-calendar" /> {fmtData(dataEvento)}{horaEvento && ` às ${horaEvento}`}</p>
              <p><i className="ti ti-user" /> {clienteSel?.nome || clienteNome || '—'}</p>
              <p>
                <i className={`ti ${tipoEntrega === 'retirada_loja' ? 'ti-building-store' : 'ti-truck-delivery'}`} />{' '}
                {tipoEntrega === 'retirada_loja' ? 'Retirada na loja' : 'Entrega no local'}
              </p>
              <p><i className="ti ti-shopping-cart" /> {carrinho.length} itens · {carrinho.reduce((s, i) => s + i.quantidade, 0)} unidades</p>
            </div>
          </div>
        )}
      </div>

      {error && <p className={styles.error}><i className="ti ti-alert-circle" /> {error}</p>}

      {/* Navegação dos steps */}
      <div className={styles.stepNav}>
        {step > 0 && (
          <Btn variant="ghost" onClick={() => setStep(s => s - 1)}>
            <i className="ti ti-arrow-left" /> Voltar
          </Btn>
        )}
        <Btn variant="ghost" onClick={onClose}>Cancelar</Btn>
        {step < STEPS.length - 1 ? (
          <Btn onClick={() => setStep(s => s + 1)}>
            Próximo <i className="ti ti-arrow-right" />
          </Btn>
        ) : (
          <Btn onClick={handleSalvar} disabled={saving}>
            {saving ? <Spinner size={14} /> : <i className="ti ti-check" />}
            {saving ? 'Salvando…' : 'Salvar Evento'}
          </Btn>
        )}
      </div>
    </Modal>
  )
}

// ─── Modal Detalhe do Evento ──────────────────────────────────────────────────

function ModalDetalheEvento({ evento, onClose, onAcao, onItemAdded, onToast }) {
  const [addingItem,   setAddingItem]   = useState(false)
  const [produtos,     setProdutos]     = useState([])
  const [catSel,       setCatSel]       = useState('')
  const [buscaProd,    setBuscaProd]    = useState('')
  const [categorias,   setCategorias]   = useState([])
  const [carrinho,     setCarrinho]     = useState([])
  const [savingItems,  setSavingItems]  = useState(false)

  useEffect(() => {
    if (addingItem) {
      pdvApi.produtos.list({ ativo: 'true' }).then(r => setProdutos(r.data.results ?? r.data)).catch(() => {})
      pdvApi.categorias.list().then(r => setCategorias(r.data.results ?? r.data)).catch(() => {})
    }
  }, [addingItem])

  const prodsFiltrados = produtos.filter(p => {
    const okCat   = catSel ? p.categoria === Number(catSel) : true
    const okBusca = buscaProd ? p.nome.toLowerCase().includes(buscaProd.toLowerCase()) : true
    return okCat && okBusca
  })

  const addCarrinho = (prod) => {
    setCarrinho(c => {
      const idx = c.findIndex(i => i.produto === prod.id)
      if (idx >= 0) { const n = [...c]; n[idx] = {...n[idx], quantidade: n[idx].quantidade+1}; return n }
      return [...c, { produto: prod.id, nome: prod.nome, preco_unit: prod.preco, quantidade: 1, observacao: '' }]
    })
  }
  const setQty = (id, qty) => {
    if (qty <= 0) { setCarrinho(c => c.filter(i => i.produto !== id)); return }
    setCarrinho(c => c.map(i => i.produto === id ? {...i, quantidade: qty} : i))
  }

  const salvarItens = async () => {
    setSavingItems(true)
    try {
      for (const item of carrinho) {
        await eventosApi.adicionarItem(evento.id, {
          produto:    item.produto,
          nome:       item.nome,
          preco_unit: item.preco_unit,
          quantidade: item.quantidade,
          observacao: item.observacao,
        })
      }
      setCarrinho([])
      setAddingItem(false)
      await onItemAdded()
      onToast({ message: 'Itens adicionados!', type: 'success' })
    } catch {
      onToast({ message: 'Erro ao adicionar itens.', type: 'error' })
    } finally {
      setSavingItems(false)
    }
  }

  const removerItem = async (itemId) => {
    try {
      await eventosApi.removerItem(evento.id, itemId)
      await onItemAdded()
      onToast({ message: 'Item removido.', type: 'success' })
    } catch {
      onToast({ message: 'Erro ao remover item.', type: 'error' })
    }
  }

  const ACOES = [
    { key: 'confirmar',        label: 'Confirmar',       icon: 'ti-check',          show: evento.pode_confirmar,        variant: 'primary' },
    { key: 'iniciar_producao', label: 'Iniciar produção',icon: 'ti-chef-hat',       show: evento.pode_iniciar_producao, variant: 'primary' },
    { key: 'marcar_pronto',    label: 'Marcar como pronto',icon:'ti-package',        show: evento.pode_marcar_pronto,    variant: 'primary' },
    { key: 'entregar',         label: 'Entregar',        icon: 'ti-truck-delivery', show: evento.pode_entregar,         variant: 'primary' },
    { key: 'cancelar',         label: 'Cancelar',        icon: 'ti-ban',            show: evento.pode_cancelar,         variant: 'danger'  },
  ]

  const cfg = STATUS_CONFIG[evento.status] || {}

  return (
    <Modal title={`Evento ${evento.numero}`} onClose={onClose} wide>
      <div className={styles.detalheLayout}>

        {/* Coluna esquerda: informações */}
        <div className={styles.detalheInfo}>
          <div className={styles.detalheHeader}>
            <span className={styles.badge} style={{ '--badge-color': cfg.color }}>{cfg.label}</span>
            <span className={styles.detalheTipo}>
              <i className={`ti ${TIPO_EVENTO_ICONS[evento.tipo_evento] || 'ti-calendar'}`} />
              {evento.tipo_evento_display}
            </span>
          </div>

          <div className={styles.infoGrid}>
            <InfoRow icon="ti-calendar"       label="Data" value={fmtData(evento.data_evento)} />
            {evento.hora_evento && <InfoRow icon="ti-clock" label="Hora" value={evento.hora_evento.slice(0,5)} />}
            <InfoRow icon="ti-user"           label="Cliente" value={evento.nome_cliente_display} />
            {evento.telefone_display && <InfoRow icon="ti-phone" label="Telefone" value={evento.telefone_display} />}
            <InfoRow
              icon={evento.tipo_entrega === 'retirada_loja' ? 'ti-building-store' : 'ti-truck-delivery'}
              label="Entrega"
              value={evento.tipo_entrega_display}
            />
            {evento.local_detalhe && (
              <InfoRow icon="ti-map-pin" label="Local" value={`${evento.local_detalhe.nome} — ${evento.local_detalhe.bairro}`} />
            )}
            {evento.endereco_avulso && (
              <InfoRow icon="ti-map-pin" label="Endereço" value={evento.endereco_avulso} />
            )}
            {evento.observacoes && (
              <InfoRow icon="ti-notes" label="Obs." value={evento.observacoes} />
            )}
          </div>

          {/* Financeiro */}
          <div className={styles.financeiroCard}>
            <div className={styles.financeiroLinha}>
              <span>Subtotal</span><span>{fmt(evento.subtotal)}</span>
            </div>
            {Number(evento.desconto) > 0 && (
              <div className={styles.financeiroLinha}>
                <span>Desconto</span><span>− {fmt(evento.desconto)}</span>
              </div>
            )}
            <div className={`${styles.financeiroLinha} ${styles.financeiroTotal}`}>
              <strong>Total</strong><strong>{fmt(evento.valor_total)}</strong>
            </div>
            <div className={styles.financeiroLinha}>
              <span>Sinal pago</span><span style={{color:'var(--verde)'}}>{fmt(evento.sinal_pago)}</span>
            </div>
            <div className={`${styles.financeiroLinha} ${Number(evento.saldo_restante) > 0 ? styles.saldoPendente : styles.saldoQuitado}`}>
              <span>Saldo restante</span>
              <span>{Number(evento.saldo_restante) > 0 ? fmt(evento.saldo_restante) : '✓ Quitado'}</span>
            </div>
          </div>

          {/* Ações */}
          <div className={styles.acoesWrap}>
            {ACOES.filter(a => a.show).map(a => (
              <Btn
                key={a.key}
                variant={a.variant === 'danger' ? 'ghost' : 'primary'}
                icon={a.icon.replace('ti-','')}
                onClick={() => onAcao(a.key, evento.id)}
                style={a.variant === 'danger' ? { color: '#DC2626', borderColor: '#DC2626' } : {}}
              >
                {a.label}
              </Btn>
            ))}
          </div>
        </div>

        {/* Coluna direita: itens */}
        <div className={styles.detalheItens}>
          <div className={styles.itensHeader}>
            <h3 className="serif">Itens do Pedido</h3>
            {evento.status in { orcamento: 1, confirmado: 1 } && (
              <Btn variant="ghost" size="sm" icon="plus" onClick={() => setAddingItem(v => !v)}>
                Adicionar
              </Btn>
            )}
          </div>

          {evento.itens?.length === 0 ? (
            <p className={styles.semItens}>Nenhum item adicionado.</p>
          ) : (
            <div className={styles.itensList}>
              {evento.itens?.map(item => (
                <div key={item.id} className={styles.itemRow}>
                  <div className={styles.itemInfo}>
                    <span className={styles.itemNome}>{item.nome}</span>
                    {item.observacao && <span className={styles.itemObs}>{item.observacao}</span>}
                  </div>
                  <div className={styles.itemNums}>
                    <span className={styles.itemQty}>{item.quantidade}×</span>
                    <span className={styles.itemPreco}>{fmt(item.preco_unit)}</span>
                    <span className={styles.itemTotal}>{fmt(item.preco_total)}</span>
                    {evento.status in { orcamento: 1, confirmado: 1 } && (
                      <button className={styles.removeItem} onClick={() => removerItem(item.id)}>
                        <i className="ti ti-trash" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Adicionar itens inline */}
          {addingItem && (
            <div className={styles.addItemsPanel}>
              <div className={styles.catalogoToolbar}>
                <input placeholder="Buscar…" value={buscaProd} onChange={e => setBuscaProd(e.target.value)} />
                <select value={catSel} onChange={e => setCatSel(e.target.value)}>
                  <option value="">Todas</option>
                  {categorias.map(c => <option key={c.id} value={c.id}>{c.nome}</option>)}
                </select>
              </div>
              <div className={styles.produtosListSmall}>
                {prodsFiltrados.map(p => {
                  const noCarrinho = carrinho.find(i => i.produto === p.id)
                  return (
                    <div key={p.id} className={styles.produtoCardSm}>
                      <span>{p.nome}</span>
                      <span className={styles.produtoPreco}>{fmt(p.preco)}</span>
                      {noCarrinho ? (
                        <div className={styles.qtyControl}>
                          <button onClick={() => setQty(p.id, noCarrinho.quantidade - 1)}>−</button>
                          <span>{noCarrinho.quantidade}</span>
                          <button onClick={() => setQty(p.id, noCarrinho.quantidade + 1)}>+</button>
                        </div>
                      ) : (
                        <button className={styles.addBtn} onClick={() => addCarrinho(p)}>+</button>
                      )}
                    </div>
                  )
                })}
              </div>
              {carrinho.length > 0 && (
                <Btn onClick={salvarItens} disabled={savingItems}>
                  {savingItems ? <Spinner size={14} /> : null}
                  Adicionar {carrinho.reduce((s,i) => s+i.quantidade, 0)} itens
                </Btn>
              )}
            </div>
          )}
        </div>
      </div>
    </Modal>
  )
}

function InfoRow({ icon, label, value }) {
  return (
    <div className={styles.infoRow}>
      <i className={`ti ${icon}`} />
      <span className={styles.infoLabel}>{label}</span>
      <span className={styles.infoValue}>{value}</span>
    </div>
  )
}
