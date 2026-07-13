import { useState, useEffect, useCallback, Fragment } from 'react'
import { eventosApi, locaisEventoApi, clientesApi } from '../api/services'
import { pdvApi, taxasEntregaApi } from '../api/services'
import { Btn, Modal, Spinner, Toast, Empty } from '../components/ui'
import PresencaAtiva from '../components/ui/PresencaAtiva'
import { ACAO_LABEL, ACAO_COR, dataFmt, resumo } from '../utils/auditoriaResumo'
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

// Sequência do stepper de status do modal de detalhe (exclui 'cancelado', tratado à parte)
const STATUS_STEPS = ['orcamento', 'confirmado', 'em_producao', 'pronto', 'entregue']

const FORMA_PAGAMENTO_LABELS = {
  pix:      'Pix',
  dinheiro: 'Dinheiro',
  cartao:   'Cartão',
  outro:    'Outro',
}

const PAGAMENTO_STATUS_LABELS = {
  pago:     'Pago',
  pendente: 'Pendente',
}

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
        confirmar:        () => eventosApi.confirmar(eventoId),
        iniciar_producao: () => eventosApi.iniciarProducao(eventoId),
        marcar_pronto:    () => eventosApi.marcarPronto(eventoId),
        entregar:         () => eventosApi.entregar(eventoId),
        cancelar:         () => eventosApi.cancelar(eventoId),
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
          <StatCard icon="ti-calendar-event"  label="Eventos este mês"       value={stats.eventos_mes} />
          <StatCard icon="ti-currency-dollar" label="Faturamento (entregues)" value={fmt(stats.faturamento_mes)} />
          <StatCard icon="ti-clock"           label="Próximos 7 dias"        value={stats.proximos_7_dias?.length ?? 0} />
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
            <div className={styles.center}>
              <i className="ti ti-calendar-off" style={{ fontSize: 40, opacity: 0.3 }} />
              <p style={{ opacity: 0.5 }}>Nenhum evento encontrado.</p>
            </div>
          ) : (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Número</th>
                    <th>Tipo</th>
                    <th>Data</th>
                    <th>Cliente</th>
                    <th>Entrega</th>
                    <th>Total</th>
                    <th>Saldo</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {eventos.map(ev => (
                    <tr key={ev.id} className={styles.tableRow} onClick={() => abrirDetalhe(ev.id)}>
                      <td className={styles.numero}>{ev.numero}</td>
                      <td>
                        <span className={styles.tipoEvento}>
                          <i className={`ti ${TIPO_EVENTO_ICONS[ev.tipo_evento] || 'ti-calendar'}`} />
                          {ev.tipo_evento_display}
                        </span>
                      </td>
                      <td>{fmtData(ev.data_evento)}</td>
                      <td>{ev.nome_cliente_display}</td>
                      <td>
                        <span className={`${styles.entregaBadge} ${ev.tipo_entrega === 'entrega_local' ? styles.entregaLocal : ''}`}>
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
          onSaved={() => {
            setShowNovo(false)
            loadEventos()
            loadStats()
            setToast({ message: 'Evento criado com sucesso!', type: 'success' })
          }}
        />
      )}

      {showDetalhe && eventoAtivo && (
        <ModalDetalheEvento
          evento={eventoAtivo}
          onClose={() => { setShowDetalhe(false); setEventoAtivo(null) }}
          onAcao={handleAcao}
          onItemAdded={async () => {
            const r = await eventosApi.detail(eventoAtivo.id)
            setEventoAtivo(r.data)
            loadEventos()
          }}
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
  const primeiroDia = new Date(ano, m - 1, 1).getDay()

  const MESES_PT = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
                    'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']

  const celulas = []
  for (let i = 0; i < primeiroDia; i++) celulas.push(null)
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
            <div
              key={key}
              className={`${styles.agendaCelula} ${evsDia.length > 0 ? styles.agendaCelulaCom : ''} ${isHoje ? styles.agendaHoje : ''}`}
            >
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
  const [tipoEvento,  setTipoEvento]  = useState('aniversario')
  const [dataEvento,  setDataEvento]  = useState('')
  const [horaEvento,  setHoraEvento]  = useState('')
  const [observacoes, setObservacoes] = useState('')

  // Cliente
  const [buscaCliente,    setBuscaCliente]    = useState('')
  const [clienteOptions,  setClienteOptions]  = useState([])
  const [clienteSel,      setClienteSel]      = useState(null)
  const [clienteNome,     setClienteNome]     = useState('')
  const [clienteTel,      setClienteTel]      = useState('')
  const [buscandoCliente, setBuscandoCliente] = useState(false)

  // Entrega
  const [tipoEntrega,   setTipoEntrega]   = useState('retirada_loja')
  const [locais,        setLocais]        = useState([])
  const [localSel,      setLocalSel]      = useState('')
  const [endAvulso,     setEndAvulso]     = useState('')
  const [taxasBairro,   setTaxasBairro]   = useState([])
  const [bairroEntrega, setBairroEntrega] = useState('')
  const [taxaEntrega,   setTaxaEntrega]   = useState('0')

  // Itens
  const [categorias, setCategorias] = useState([])
  const [produtos,   setProdutos]   = useState([])
  const [buscaProd,  setBuscaProd]  = useState('')
  const [catSel,     setCatSel]     = useState('')
  const [carrinho,   setCarrinho]   = useState([])

  // Financeiro
  const [desconto, setDesconto] = useState('0')
  const [sinal,    setSinal]    = useState('0')

  const [saving, setSaving] = useState(false)
  const [error,  setError]  = useState('')

  // ── Carrega locais e catálogo ─────────────────────────────────────────────
  // CORRIGIDO: usa pdvApi.listCategorias() e pdvApi.listProdutos()
  useEffect(() => {
    locaisEventoApi.list({ ativo: 'true' }).then(r => setLocais(r.data.results ?? r.data)).catch(() => {})
    pdvApi.listCategorias().then(r => setCategorias(r.data.results ?? r.data)).catch(() => {})
    pdvApi.listProdutos({ ativo: 'true' }).then(r => setProdutos(r.data.results ?? r.data)).catch(() => {})
    taxasEntregaApi.list({ ativo: true }).then(r => setTaxasBairro(r.data.results ?? r.data)).catch(() => {})
  }, [])

  // Preenche a taxa automaticamente a partir do bairro do local cadastrado
  useEffect(() => {
    if (tipoEntrega !== 'entrega_local' || !localSel) return
    const local = locais.find(l => String(l.id) === String(localSel))
    if (!local?.bairro) return
    setBairroEntrega(local.bairro)
    const t = taxasBairro.find(x => x.bairro.toLowerCase() === local.bairro.toLowerCase())
    if (t) setTaxaEntrega(t.taxa)
  }, [localSel, locais, taxasBairro, tipoEntrega])

  const selecionarBairroAvulso = (bairro) => {
    setBairroEntrega(bairro)
    const t = taxasBairro.find(x => x.bairro === bairro)
    if (t) setTaxaEntrega(t.taxa)
  }

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
    const okCat   = catSel ? p.categoria === Number(catSel) : true
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
  const total    = Math.max(subtotal - Number(desconto || 0), 0) +
                   (tipoEntrega === 'entrega_local' ? Number(taxaEntrega || 0) : 0)

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
        bairro_entrega:   tipoEntrega === 'entrega_local' ? bairroEntrega : '',
        taxa_entrega:     tipoEntrega === 'entrega_local' ? Number(taxaEntrega || 0) : 0,
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
    } catch {
      setError('Erro ao salvar evento. Verifique os dados e tente novamente.')
    } finally {
      setSaving(false)
    }
  }

  const STEP_LABELS = ['Dados do Evento', 'Entrega', 'Itens', 'Financeiro']

  return (
    <Modal open title="Novo Evento" onClose={onClose} wide>
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
                  <span>{clienteSel.nome}</span>
                  <button onClick={() => setClienteSel(null)}><i className="ti ti-x" /></button>
                </div>
              ) : (
                <div className={styles.clienteBusca}>
                  <input
                    placeholder="Digite o nome ou telefone…"
                    value={buscaCliente}
                    onChange={e => setBuscaCliente(e.target.value)}
                  />
                  {buscandoCliente && <Spinner size={14} />}
                  {clienteOptions.length > 0 && (
                    <div className={styles.clienteDropdown}>
                      {clienteOptions.map(c => (
                        <button key={c.id} onClick={() => { setClienteSel(c); setClienteOptions([]) }}>
                          <strong>{c.nome}</strong>
                          <span>{c.telefone_principal}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Cliente avulso (se não selecionou do CRM) */}
            {!clienteSel && (
              <>
                <div className={styles.formGroup}>
                  <label>Nome do cliente (avulso)</label>
                  <input value={clienteNome} onChange={e => setClienteNome(e.target.value)} placeholder="Nome completo" />
                </div>
                <div className={styles.formGroup}>
                  <label>Telefone</label>
                  <input value={clienteTel} onChange={e => setClienteTel(e.target.value)} placeholder="(86) 9 9999-9999" />
                </div>
              </>
            )}

            <div className={`${styles.formGroup} ${styles.fullRow}`}>
              <label>Observações</label>
              <textarea value={observacoes} onChange={e => setObservacoes(e.target.value)} rows={3} placeholder="Observações gerais do evento…" />
            </div>
          </div>
        )}

        {/* ── Step 1: Entrega ─────────────────────────────────────────── */}
        {step === 1 && (
          <div className={styles.formGrid}>
            <div className={`${styles.formGroup} ${styles.fullRow}`}>
              <label>Tipo de entrega</label>
              <div className={styles.radioGroup}>
                <label className={`${styles.radioCard} ${tipoEntrega === 'retirada_loja' ? styles.radioCardActive : ''}`}>
                  <input type="radio" value="retirada_loja" checked={tipoEntrega === 'retirada_loja'} onChange={e => setTipoEntrega(e.target.value)} />
                  <i className="ti ti-building-store" /> Retirada na loja
                </label>
                <label className={`${styles.radioCard} ${tipoEntrega === 'entrega_local' ? styles.radioCardActive : ''}`}>
                  <input type="radio" value="entrega_local" checked={tipoEntrega === 'entrega_local'} onChange={e => setTipoEntrega(e.target.value)} />
                  <i className="ti ti-truck-delivery" /> Entrega no local
                </label>
              </div>
            </div>

            {tipoEntrega === 'entrega_local' && (
              <>
                <div className={`${styles.formGroup} ${styles.fullRow}`}>
                  <label>Local cadastrado</label>
                  <select value={localSel} onChange={e => setLocalSel(e.target.value)}>
                    <option value="">— Endereço avulso —</option>
                    {locais.map(l => (
                      <option key={l.id} value={l.id}>{l.nome} — {l.bairro}</option>
                    ))}
                  </select>
                </div>
                {!localSel && (
                  <>
                    <div className={`${styles.formGroup} ${styles.fullRow}`}>
                      <label>Endereço do local</label>
                      <input value={endAvulso} onChange={e => setEndAvulso(e.target.value)} placeholder="Rua, número, bairro…" />
                    </div>
                    <div className={styles.formGroup}>
                      <label>Bairro (para calcular a taxa)</label>
                      <select value={bairroEntrega} onChange={e => selecionarBairroAvulso(e.target.value)}>
                        <option value="">Selecione o bairro…</option>
                        {taxasBairro.map(t => (
                          <option key={t.id} value={t.bairro}>{t.bairro} — R$ {Number(t.taxa).toFixed(2)}</option>
                        ))}
                      </select>
                    </div>
                  </>
                )}
                <div className={styles.formGroup}>
                  <label>Taxa de entrega (R$)</label>
                  <input
                    type="number" min="0" step="0.01"
                    value={taxaEntrega}
                    onChange={e => setTaxaEntrega(e.target.value)}
                  />
                </div>
              </>
            )}
          </div>
        )}

        {/* ── Step 2: Itens ───────────────────────────────────────────── */}
        {step === 2 && (
          <div className={styles.itensStep}>
            <div className={styles.catalogoToolbar}>
              <input
                placeholder="Buscar produto…"
                value={buscaProd}
                onChange={e => setBuscaProd(e.target.value)}
              />
              <select value={catSel} onChange={e => setCatSel(e.target.value)}>
                <option value="">Todas as categorias</option>
                {categorias.map(c => <option key={c.id} value={c.id}>{c.nome}</option>)}
              </select>
            </div>

            <div className={styles.itensLayout}>
              {/* Catálogo */}
              <div className={styles.catalogo}>
                {produtosFiltrados.length === 0 ? (
                  <p className={styles.semItens}>Nenhum produto encontrado.</p>
                ) : produtosFiltrados.map(p => {
                  const noCarrinho = carrinho.find(i => i.produto === p.id)
                  return (
                    <div key={p.id} className={styles.produtoCard}>
                      <div className={styles.produtoInfo}>
                        <span className={styles.produtoNome}>{p.nome}</span>
                        <span className={styles.produtoPreco}>{fmt(p.preco)}</span>
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
              </div>

              {/* Carrinho */}
              <div className={styles.carrinho}>
                <h4>Carrinho</h4>
                {carrinho.length === 0 ? (
                  <p className={styles.semItens}>Nenhum item adicionado.</p>
                ) : carrinho.map(item => (
                  <div key={item.produto} className={styles.carrinhoItem}>
                    <div className={styles.carrinhoItemTop}>
                      <span>{item.nome}</span>
                      <button onClick={() => setQty(item.produto, 0)}><i className="ti ti-x" /></button>
                    </div>
                    <div className={styles.carrinhoItemBot}>
                      <div className={styles.qtyControl}>
                        <button onClick={() => setQty(item.produto, item.quantidade - 1)}>−</button>
                        <span>{item.quantidade}</span>
                        <button onClick={() => setQty(item.produto, item.quantidade + 1)}>+</button>
                      </div>
                      <span>{fmt(Number(item.preco_unit) * item.quantidade)}</span>
                    </div>
                    <input
                      className={styles.obsInput}
                      placeholder="Obs. (ex: sem nozes)"
                      value={item.observacao}
                      onChange={e => setObs(item.produto, e.target.value)}
                    />
                  </div>
                ))}
                {carrinho.length > 0 && (
                  <div className={styles.carrinhoTotal}>
                    <strong>Subtotal:</strong> {fmt(subtotal)}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── Step 3: Financeiro ──────────────────────────────────────── */}
        {step === 3 && (
          <div className={styles.formGrid}>
            <div className={styles.formGroup}>
              <label>Desconto (R$)</label>
              <input type="number" min="0" step="0.01" value={desconto} onChange={e => setDesconto(e.target.value)} />
            </div>
            <div className={styles.formGroup}>
              <label>Sinal pago (R$)</label>
              <input type="number" min="0" step="0.01" value={sinal} onChange={e => setSinal(e.target.value)} />
            </div>

            <div className={`${styles.resumoFinanceiro} ${styles.fullRow}`}>
              <div className={styles.resumoLinha}>
                <span>Subtotal</span><span>{fmt(subtotal)}</span>
              </div>
              <div className={styles.resumoLinha}>
                <span>Desconto</span><span>− {fmt(Number(desconto || 0))}</span>
              </div>
              {tipoEntrega === 'entrega_local' && Number(taxaEntrega || 0) > 0 && (
                <div className={styles.resumoLinha}>
                  <span>Taxa de entrega</span><span>{fmt(Number(taxaEntrega || 0))}</span>
                </div>
              )}
              <div className={`${styles.resumoLinha} ${styles.resumoTotal}`}>
                <span>Total</span><span>{fmt(total)}</span>
              </div>
              <div className={styles.resumoLinha}>
                <span>Sinal pago</span><span>{fmt(Number(sinal || 0))}</span>
              </div>
              <div className={`${styles.resumoLinha} ${styles.resumoSaldo}`}>
                <span>Saldo restante</span>
                <span>{fmt(Math.max(total - Number(sinal || 0), 0))}</span>
              </div>
            </div>

            {/* Resumo do evento */}
            <div className={`${styles.resumoEvento} ${styles.fullRow}`}>
              <p>
                <i className={`ti ${TIPO_EVENTO_ICONS[tipoEvento] || 'ti-calendar'}`} />
                {TIPO_EVENTO_LABELS[tipoEvento]} · {fmtData(dataEvento)}
                {horaEvento && ` às ${horaEvento}`}
              </p>
              <p>
                <i className="ti ti-user" />
                {clienteSel ? clienteSel.nome : clienteNome || '—'}
              </p>
              <p>
                <i className={`ti ${tipoEntrega === 'retirada_loja' ? 'ti-building-store' : 'ti-truck-delivery'}`} />{' '}
                {tipoEntrega === 'retirada_loja' ? 'Retirada na loja' : 'Entrega no local'}
              </p>
              <p>
                <i className="ti ti-shopping-cart" /> {carrinho.length} itens ·{' '}
                {carrinho.reduce((s, i) => s + i.quantidade, 0)} unidades
              </p>
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
  const [abaAtiva,    setAbaAtiva]    = useState('itens')
  const [addingItem,  setAddingItem]  = useState(false)
  const [produtos,    setProdutos]    = useState([])
  const [catSel,      setCatSel]      = useState('')
  const [buscaProd,   setBuscaProd]   = useState('')
  const [categorias,  setCategorias]  = useState([])
  const [carrinho,    setCarrinho]    = useState([])
  const [savingItems, setSavingItems] = useState(false)
  const [lightboxImg, setLightboxImg] = useState(null)

  // Histórico (aba) — fetch lazy, só quando a aba é ativada pela 1ª vez
  const [historico,        setHistorico]        = useState(null)
  const [loadingHistorico, setLoadingHistorico]  = useState(false)

  useEffect(() => {
    if (abaAtiva === 'historico' && historico === null) {
      setLoadingHistorico(true)
      eventosApi.historico(evento.id)
        .then((r) => setHistorico(r.data))
        .catch(() => setHistorico([]))
        .finally(() => setLoadingHistorico(false))
    }
  }, [abaAtiva, historico, evento.id])

  // Pagamentos
  const [registrandoPagamento, setRegistrandoPagamento] = useState(false)
  const [savingPagamento,      setSavingPagamento]      = useState(false)
  const [pagamentoForm,        setPagamentoForm]        = useState({
    valor: '', forma_pagamento: 'pix', status: 'pago',
    data_pagamento: new Date().toISOString().slice(0, 10), observacao: '',
  })
  const [comprovanteFile, setComprovanteFile] = useState(null)

  // CORRIGIDO: usa pdvApi.listProdutos() e pdvApi.listCategorias()
  useEffect(() => {
    if (addingItem) {
      pdvApi.listProdutos({ ativo: 'true' }).then(r => setProdutos(r.data.results ?? r.data)).catch(() => {})
      pdvApi.listCategorias().then(r => setCategorias(r.data.results ?? r.data)).catch(() => {})
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
      if (idx >= 0) { const n = [...c]; n[idx] = { ...n[idx], quantidade: n[idx].quantidade + 1 }; return n }
      return [...c, { produto: prod.id, nome: prod.nome, preco_unit: prod.preco, quantidade: 1, observacao: '' }]
    })
  }
  const setQty = (id, qty) => {
    if (qty <= 0) { setCarrinho(c => c.filter(i => i.produto !== id)); return }
    setCarrinho(c => c.map(i => i.produto === id ? { ...i, quantidade: qty } : i))
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

  const salvarPagamento = async () => {
    const valor = parseFloat(pagamentoForm.valor)
    if (!valor || valor <= 0) {
      onToast({ message: 'Informe um valor válido para o pagamento.', type: 'error' })
      return
    }
    setSavingPagamento(true)
    try {
      if (comprovanteFile) {
        const formData = new FormData()
        formData.append('valor', valor)
        formData.append('forma_pagamento', pagamentoForm.forma_pagamento)
        formData.append('status', pagamentoForm.status)
        formData.append('data_pagamento', pagamentoForm.data_pagamento)
        formData.append('observacao', pagamentoForm.observacao)
        formData.append('comprovante', comprovanteFile)
        await eventosApi.adicionarPagamento(evento.id, formData, { headers: { 'Content-Type': undefined } })
      } else {
        await eventosApi.adicionarPagamento(evento.id, {
          valor,
          forma_pagamento: pagamentoForm.forma_pagamento,
          status:          pagamentoForm.status,
          data_pagamento:  pagamentoForm.data_pagamento,
          observacao:      pagamentoForm.observacao,
        })
      }
      setPagamentoForm({
        valor: '', forma_pagamento: 'pix', status: 'pago',
        data_pagamento: new Date().toISOString().slice(0, 10), observacao: '',
      })
      setComprovanteFile(null)
      setRegistrandoPagamento(false)
      await onItemAdded()
      onToast({ message: 'Pagamento registrado!', type: 'success' })
    } catch {
      onToast({ message: 'Erro ao registrar pagamento.', type: 'error' })
    } finally {
      setSavingPagamento(false)
    }
  }

  const removerPagamento = async (pagamentoId) => {
    if (!window.confirm('Remover este pagamento? O saldo do evento será recalculado.')) return
    try {
      await eventosApi.removerPagamento(evento.id, pagamentoId)
      await onItemAdded()
      onToast({ message: 'Pagamento removido.', type: 'success' })
    } catch {
      onToast({ message: 'Erro ao remover pagamento.', type: 'error' })
    }
  }

  const ACOES = [
    { key: 'confirmar',        label: 'Confirmar',         icon: 'ti-check',          show: evento.pode_confirmar,        variant: 'primary' },
    { key: 'iniciar_producao', label: 'Iniciar produção',  icon: 'ti-chef-hat',       show: evento.pode_iniciar_producao, variant: 'primary' },
    { key: 'marcar_pronto',    label: 'Marcar como pronto',icon: 'ti-package',         show: evento.pode_marcar_pronto,    variant: 'primary' },
    { key: 'entregar',         label: 'Entregar',          icon: 'ti-truck-delivery', show: evento.pode_entregar,         variant: 'primary' },
    { key: 'cancelar',         label: 'Cancelar',          icon: 'ti-ban',            show: evento.pode_cancelar,         variant: 'danger'  },
  ]

  const cfg = STATUS_CONFIG[evento.status] || {}
  const stepIdx = STATUS_STEPS.indexOf(evento.status)
  const podeEditarItens = evento.status === 'orcamento' || evento.status === 'confirmado'

  const nItens      = evento.itens?.length ?? 0
  const nPagamentos = evento.pagamentos?.length ?? 0
  const nImagens     = evento.imagens_inspiracao?.length ?? 0

  return (
    <Modal open title={`Evento ${evento.numero}`} onClose={onClose} width={920}>
      <PresencaAtiva model="Evento" objetoId={evento.id} />

      {/* Stepper de status (ou badge de cancelado) */}
      {evento.status === 'cancelado' ? (
        <div className={styles.statusCanceladoBadge}>
          <i className="ti ti-ban" /> Evento cancelado
        </div>
      ) : (
        <div className={styles.statusStepper}>
          {STATUS_STEPS.map((s, i) => (
            <Fragment key={s}>
              <div
                className={`${styles.statusStepItem}
                  ${i === stepIdx ? styles.stepAtivo : ''}
                  ${i < stepIdx ? styles.stepConcluido : ''}`}
              >
                <span className={styles.statusStepDot}>{i < stepIdx ? <i className="ti ti-check" /> : i + 1}</span>
                <span>{STATUS_CONFIG[s]?.label}</span>
              </div>
              {i < STATUS_STEPS.length - 1 && <div className={styles.statusStepSep} />}
            </Fragment>
          ))}
        </div>
      )}

      <div className={styles.detalheLayoutV2}>

        {/* Sidebar: dados + financeiro + ações */}
        <div className={styles.detalheSidebar}>
          <span className={styles.detalheTipo}>
            <i className={`ti ${TIPO_EVENTO_ICONS[evento.tipo_evento] || 'ti-calendar'}`} />
            {evento.tipo_evento_display}
          </span>

          <div className={styles.infoGrid}>
            <InfoRow icon="ti-calendar" label="Data"     value={fmtData(evento.data_evento)} />
            {evento.hora_evento && <InfoRow icon="ti-clock" label="Hora" value={evento.hora_evento.slice(0,5)} />}
            <InfoRow icon="ti-user"    label="Cliente"  value={evento.nome_cliente_display} />
            {evento.telefone_display && <InfoRow icon="ti-phone" label="Telefone" value={evento.telefone_display} />}
            <InfoRow
              icon={evento.tipo_entrega === 'retirada_loja' ? 'ti-building-store' : 'ti-truck-delivery'}
              label="Entrega"
              value={evento.tipo_entrega_display}
            />
            {evento.local_nome && <InfoRow icon="ti-map-pin" label="Local" value={evento.local_nome} />}
            {evento.endereco_avulso && <InfoRow icon="ti-map-pin" label="Endereço" value={evento.endereco_avulso} />}
            {evento.observacoes && <InfoRow icon="ti-notes" label="Obs." value={evento.observacoes} />}
          </div>

          {/* Financeiro */}
          <div className={styles.financeiroCard}>
            <div className={styles.financeiroLinha}><span>Subtotal</span><span>{fmt(evento.subtotal)}</span></div>
            {Number(evento.desconto) > 0 && (
              <div className={styles.financeiroLinha}><span>Desconto</span><span>− {fmt(evento.desconto)}</span></div>
            )}
            {Number(evento.taxa_entrega) > 0 && (
              <div className={styles.financeiroLinha}>
                <span>Taxa de entrega{evento.bairro_entrega ? ` (${evento.bairro_entrega})` : ''}</span>
                <span>{fmt(evento.taxa_entrega)}</span>
              </div>
            )}
            <div className={`${styles.financeiroLinha} ${styles.financeiroTotal}`}><span>Total</span><span>{fmt(evento.valor_total)}</span></div>
            <div className={styles.financeiroLinha}><span>Sinal pago</span><span>{fmt(evento.sinal_pago)}</span></div>
            <div className={`${styles.financeiroLinha} ${styles.financeiroTotal} ${Number(evento.saldo_restante) > 0 ? styles.saldoPendente : styles.saldoQuitado}`}>
              <span>Saldo restante</span>
              <span>{Number(evento.saldo_restante) > 0 ? fmt(evento.saldo_restante) : '✓ Quitado'}</span>
            </div>
          </div>

          {/* Ações de status */}
          <div className={styles.acoesWrap}>
            {ACOES.filter(a => a.show).map(a => (
              <Btn
                key={a.key}
                variant={a.variant === 'danger' ? 'ghost' : 'primary'}
                onClick={() => onAcao(a.key, evento.id)}
                style={a.variant === 'danger' ? { color: '#DC2626', borderColor: '#DC2626' } : {}}
              >
                <i className={`ti ${a.icon}`} /> {a.label}
              </Btn>
            ))}
          </div>
        </div>

        {/* Área principal: abas */}
        <div className={styles.detalheMain}>
          <div className={styles.tabsNav}>
            <button className={`${styles.tabBtn} ${abaAtiva === 'itens' ? styles.tabBtnAtivo : ''}`} onClick={() => setAbaAtiva('itens')}>
              Itens ({nItens})
            </button>
            <button className={`${styles.tabBtn} ${abaAtiva === 'pagamentos' ? styles.tabBtnAtivo : ''}`} onClick={() => setAbaAtiva('pagamentos')}>
              Pagamentos ({nPagamentos})
            </button>
            <button className={`${styles.tabBtn} ${abaAtiva === 'imagens' ? styles.tabBtnAtivo : ''}`} onClick={() => setAbaAtiva('imagens')}>
              Imagens ({nImagens})
            </button>
            <button className={`${styles.tabBtn} ${abaAtiva === 'historico' ? styles.tabBtnAtivo : ''}`} onClick={() => setAbaAtiva('historico')}>
              Histórico
            </button>
          </div>

          {/* ── Aba: Itens ──────────────────────────────────────────────── */}
          {abaAtiva === 'itens' && (
            <>
              <div className={styles.itensHeader}>
                <h4>Itens do evento</h4>
                {podeEditarItens && !addingItem && (
                  <Btn variant="ghost" onClick={() => setAddingItem(true)}>
                    <i className="ti ti-plus" /> Adicionar itens
                  </Btn>
                )}
              </div>

              {nItens === 0 ? (
                <p className={styles.semItens}>Nenhum item adicionado.</p>
              ) : (
                <div className={styles.itensList}>
                  {evento.itens.map(item => (
                    <div key={item.id} className={styles.itemRow}>
                      <div className={styles.itemInfo}>
                        <span className={styles.itemNome}>{item.nome}</span>
                        {item.observacao && <span className={styles.itemObs}>{item.observacao}</span>}
                      </div>
                      <div className={styles.itemNums}>
                        <span className={styles.itemQty}>{item.quantidade}×</span>
                        <span className={styles.itemPreco}>{fmt(item.preco_unit)}</span>
                        <span className={styles.itemTotal}>{fmt(item.preco_total)}</span>
                        {podeEditarItens && (
                          <button className={styles.removeItem} onClick={() => removerItem(item.id)}>
                            <i className="ti ti-trash" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Painel de adicionar itens inline */}
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
                      {savingItems ? <Spinner size={14} /> : <i className="ti ti-check" />}
                      {savingItems ? 'Salvando…' : `Salvar ${carrinho.length} item(s)`}
                    </Btn>
                  )}
                  <Btn variant="ghost" onClick={() => { setAddingItem(false); setCarrinho([]) }}>
                    Cancelar
                  </Btn>
                </div>
              )}
            </>
          )}

          {/* ── Aba: Pagamentos ─────────────────────────────────────────── */}
          {abaAtiva === 'pagamentos' && (
            <>
              <div className={styles.itensHeader}>
                <h4>Pagamentos</h4>
                {!registrandoPagamento && (
                  <Btn variant="ghost" onClick={() => setRegistrandoPagamento(true)}>
                    <i className="ti ti-plus" /> Registrar pagamento
                  </Btn>
                )}
              </div>

              {nPagamentos === 0 ? (
                <p className={styles.semItens}>Nenhum pagamento registrado.</p>
              ) : (
                <div className={styles.itensList}>
                  {evento.pagamentos.map(pg => (
                    <div key={pg.id} className={styles.pagamentoRow}>
                      <div className={styles.itemInfo}>
                        <span className={styles.itemNome}>
                          {pg.forma_pagamento_display} · {fmtData(pg.data_pagamento)}
                        </span>
                        {pg.observacao && <span className={styles.itemObs}>{pg.observacao}</span>}
                      </div>
                      <div className={styles.itemNums}>
                        {pg.comprovante && (
                          /\.pdf($|\?)/i.test(pg.comprovante) ? (
                            <a href={pg.comprovante} target="_blank" rel="noreferrer" className={styles.comprovanteLink} title="Ver comprovante (PDF)">
                              <i className="ti ti-file-type-pdf" />
                            </a>
                          ) : (
                            <button className={styles.comprovanteLink} onClick={() => setLightboxImg(pg.comprovante)} title="Ver comprovante">
                              <i className="ti ti-receipt" />
                            </button>
                          )
                        )}
                        <span
                          className={styles.badge}
                          style={{ '--badge-color': pg.status === 'pago' ? '#059669' : '#D97706' }}
                        >
                          {pg.status_display}
                        </span>
                        <span className={styles.itemTotal}>{fmt(pg.valor)}</span>
                        <button className={styles.removeItem} onClick={() => removerPagamento(pg.id)}>
                          <i className="ti ti-trash" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {registrandoPagamento && (
                <div className={styles.addItemsPanel}>
                  <div className={styles.formGridPagamento}>
                    <div className={styles.formGroup}>
                      <label>Valor (R$) *</label>
                      <input
                        type="number" min="0" step="0.01"
                        value={pagamentoForm.valor}
                        onChange={e => setPagamentoForm(f => ({ ...f, valor: e.target.value }))}
                      />
                    </div>
                    <div className={styles.formGroup}>
                      <label>Forma de pagamento</label>
                      <select
                        value={pagamentoForm.forma_pagamento}
                        onChange={e => setPagamentoForm(f => ({ ...f, forma_pagamento: e.target.value }))}
                      >
                        {Object.entries(FORMA_PAGAMENTO_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                      </select>
                    </div>
                    <div className={styles.formGroup}>
                      <label>Status</label>
                      <select
                        value={pagamentoForm.status}
                        onChange={e => setPagamentoForm(f => ({ ...f, status: e.target.value }))}
                      >
                        {Object.entries(PAGAMENTO_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                      </select>
                    </div>
                    <div className={styles.formGroup}>
                      <label>Data</label>
                      <input
                        type="date"
                        value={pagamentoForm.data_pagamento}
                        onChange={e => setPagamentoForm(f => ({ ...f, data_pagamento: e.target.value }))}
                      />
                    </div>
                    <div className={styles.formGroup} style={{ gridColumn: '1 / -1' }}>
                      <label>Observação</label>
                      <input
                        value={pagamentoForm.observacao}
                        onChange={e => setPagamentoForm(f => ({ ...f, observacao: e.target.value }))}
                        placeholder="Ex: Pix referente à 2ª parcela"
                      />
                    </div>
                    <div className={styles.formGroup} style={{ gridColumn: '1 / -1' }}>
                      <label>Comprovante (opcional)</label>
                      <input
                        type="file"
                        accept="image/*,application/pdf"
                        onChange={e => setComprovanteFile(e.target.files?.[0] ?? null)}
                      />
                      {comprovanteFile && (
                        <span className={styles.itemObs}>
                          <i className="ti ti-paperclip" /> {comprovanteFile.name}
                        </span>
                      )}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <Btn onClick={salvarPagamento} disabled={savingPagamento}>
                      {savingPagamento ? <Spinner size={14} /> : <i className="ti ti-check" />}
                      {savingPagamento ? 'Salvando…' : 'Salvar pagamento'}
                    </Btn>
                    <Btn variant="ghost" onClick={() => { setRegistrandoPagamento(false); setComprovanteFile(null) }}>
                      Cancelar
                    </Btn>
                  </div>
                </div>
              )}
            </>
          )}

          {/* ── Aba: Imagens de Inspiração ──────────────────────────────── */}
          {abaAtiva === 'imagens' && (
            <>
              <div className={styles.itensHeader}>
                <h4>Imagens de Inspiração</h4>
              </div>
              <p className={styles.imagensAviso}>
                <i className="ti ti-lock" /> Uso interno — nunca aparece em PDFs ou WhatsApp.
              </p>
              {nImagens === 0 ? (
                <p className={styles.semItens}>
                  {evento.tem_orcamento_origem
                    ? 'Nenhuma imagem anexada ao orçamento de origem.'
                    : 'Este evento não tem imagens de inspiração porque não veio de um orçamento.'}
                </p>
              ) : (
                <div className={styles.imagensInspiracaoGrid}>
                  {evento.imagens_inspiracao.map(img => (
                    <div key={img.id} className={styles.imagemInspiracaoThumb}>
                      <img src={img.imagem} alt="Inspiração" onClick={() => setLightboxImg(img.imagem)} />
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* ── Aba: Histórico ──────────────────────────────────────────── */}
          {abaAtiva === 'historico' && (
            <>
              <div className={styles.itensHeader}>
                <h4>Histórico de Alterações</h4>
              </div>
              {loadingHistorico ? (
                <div style={{ padding: 24, textAlign: 'center' }}><Spinner size={22} /></div>
              ) : !historico || historico.length === 0 ? (
                <Empty icon="history" message="Nenhuma alteração registrada ainda." />
              ) : (
                <div className={styles.historicoLista}>
                  {historico.map((log) => (
                    <div key={log.id} className={styles.historicoItem}>
                      <span className={styles.historicoBadge} style={{ color: ACAO_COR[log.acao] }}>
                        {ACAO_LABEL[log.acao] ?? log.acao_display}
                      </span>
                      <span className={styles.historicoResumo}>{resumo(log)}</span>
                      <span className={styles.historicoMeta}>
                        {log.usuario_nome_snapshot || 'Sistema'} · {dataFmt(log.criado_em)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {lightboxImg && (
        <div className={styles.lightboxOverlay} onClick={() => setLightboxImg(null)}>
          <button className={styles.lightboxClose} onClick={() => setLightboxImg(null)} aria-label="Fechar">
            <i className="ti ti-x" />
          </button>
          <img className={styles.lightboxImg} src={lightboxImg} alt="Imagem ampliada" onClick={e => e.stopPropagation()} />
        </div>
      )}
    </Modal>
  )
}

// ─── InfoRow helper ───────────────────────────────────────────────────────────

function InfoRow({ icon, label, value }) {
  return (
    <div className={styles.infoRow}>
      <i className={`ti ${icon} ${styles.infoIcon}`} />
      <span className={styles.infoLabel}>{label}</span>
      <span className={styles.infoValue}>{value}</span>
    </div>
  )
}