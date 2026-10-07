import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { cobrancaApi, usuariosApi } from '../api/services'
import { useAuth } from '../hooks/useAuth'
import { Btn, Modal, Spinner, Toast, Field, Input, Select, Textarea, Empty } from '../components/ui'
import styles from './Cobranca.module.css'

// ─── Helpers ────────────────────────────────────────────────────────────────

const brl = (v) => Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const hojeISO = () => new Date().toISOString().slice(0, 10)

function fmtDataCurta(iso) {
  if (!iso) return ''
  const [, m, d] = iso.split('-')
  return `${d}/${m}`
}
function fmtDataLonga(iso) {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}
function diffDias(iso) {
  const hoje = new Date(hojeISO() + 'T00:00:00')
  const data = new Date(iso + 'T00:00:00')
  return Math.round((data - hoje) / 86400000)
}
function fmtQuando(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const hora = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
  const dias = diffDias(d.toISOString().slice(0, 10))
  if (dias === 0) return `hoje, ${hora}`
  if (dias === -1) return `ontem, ${hora}`
  return `${d.toLocaleDateString('pt-BR')} · ${dias < 0 ? `há ${-dias} dias` : hora}`
}

const FILTROS = [
  ['todos', 'Todos'],
  ['lembrete', 'Lembrete'],
  ['cobranca', 'Cobrança'],
  ['pausado', 'Pausados'],
  ['prazo_hoje', 'Prazo vence hoje'],
  ['pos_evento', 'Pós-evento'],
  ['sem_ligacao', 'Sem ligação'],
]

function bateFiltro(item, id) {
  const codigo = item.fase.codigo
  switch (id) {
    case 'lembrete': return codigo === 'lembrete' || codigo === 'aguardando'
    case 'cobranca': return codigo === 'cobranca' || codigo === 'concluida'
    case 'pausado': return !!item.pausa_vigente
    case 'prazo_hoje': return !!item.pausa_vigente && item.pausa_vigente.pausado_ate === hojeISO()
    case 'pos_evento': return item.dias_para_evento < 0
    case 'sem_ligacao': return item.total_ligacoes === 0 && codigo !== 'aguardando'
    default: return true
  }
}

const VARS = [
  'primeiro_nome', 'nome', 'numero_evento', 'tipo_evento', 'data_evento',
  'valor_total', 'valor_pago', 'saldo', 'data_limite', 'dias_para_limite',
  'dias_em_atraso', 'dias_para_evento', 'chave_pix', 'favorecido_pix',
  'telefone_empresa', 'empresa',
]
const VARS_PRAZO = [...VARS, 'prazo_combinado']

const DIAS_SEMANA_LABEL = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

function useDebounced(fn, delay, deps) {
  const ref = useRef()
  useEffect(() => {
    clearTimeout(ref.current)
    ref.current = setTimeout(fn, delay)
    return () => clearTimeout(ref.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}

// ─── Página ─────────────────────────────────────────────────────────────────

export default function Cobranca() {
  const [aba, setAba] = useState(0)
  const [toast, setToast] = useState(null)
  const showToast = (msg, tipo = 'success') => setToast({ msg, tipo })
  const [cfg, setCfg] = useState(null)

  const loadCfg = useCallback(() => {
    cobrancaApi.configuracao.get().then((r) => setCfg(r.data)).catch(() => {})
  }, [])
  useEffect(() => { loadCfg() }, [loadCfg])

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={`serif ${styles.title}`}><i className="ti ti-coin" /> Cobrança</h1>
          <p className={styles.subtitle}>Eventos com saldo em aberto, régua automática de WhatsApp e ligações da equipe.</p>
        </div>
        {cfg && (
          <span className={styles.statusAuto}>
            <span className={`${styles.dot} ${!cfg.ativo ? styles.dotOff : ''}`} />
            {cfg.ativo ? 'Régua automática ligada' : 'Régua automática desligada · nada é enviado'}
          </span>
        )}
      </div>

      <div className={styles.tabBar}>
        <button className={`${styles.tab} ${aba === 0 ? styles.tabActive : ''}`} onClick={() => setAba(0)}>
          <i className="ti ti-list" /> Fila de cobrança
        </button>
        <button className={`${styles.tab} ${aba === 1 ? styles.tabActive : ''}`} onClick={() => setAba(1)}>
          <i className="ti ti-settings" /> Régua e mensagens
        </button>
      </div>

      <div className={styles.abaContent}>
        {aba === 0 && <AbaFila onToast={showToast} />}
        {aba === 1 && <AbaRegua cfg={cfg} onCfgReload={loadCfg} onToast={showToast} />}
      </div>

      {toast && <Toast message={toast.msg} type={toast.tipo} onClose={() => setToast(null)} />}
    </div>
  )
}

// ═════════════════════════════ ABA: FILA ═══════════════════════════════════

function AbaFila({ onToast }) {
  const [itens, setItens] = useState([])
  const [loading, setLoading] = useState(true)
  const [filtro, setFiltro] = useState('todos')
  const [search, setSearch] = useState('')

  const [modalLigacao, setModalLigacao] = useState(null)
  const [modalPausa, setModalPausa] = useState(null)
  const [modalRetomar, setModalRetomar] = useState(null)
  const [drawerEventoId, setDrawerEventoId] = useState(null)

  // Deep-link: CobrancaBadge (Eventos.jsx/ClienteDetail.jsx) navega pra cá com
  // state.openEventoId — mesmo padrão do openPedidoId do iFood.
  const location = useLocation()
  const navigate = useNavigate()
  useEffect(() => {
    if (location.state?.openEventoId) {
      setDrawerEventoId(location.state.openEventoId)
      navigate(location.pathname, { replace: true, state: {} })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const load = useCallback(() => {
    setLoading(true)
    cobrancaApi.fila.list().then((r) => setItens(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])
  useEffect(() => { load() }, [load])

  const contagens = useMemo(() => {
    const out = {}
    FILTROS.forEach(([id]) => { out[id] = id === 'todos' ? itens.length : itens.filter((i) => bateFiltro(i, id)).length })
    return out
  }, [itens])

  const visiveis = useMemo(() => {
    let lista = filtro === 'todos' ? itens : itens.filter((i) => bateFiltro(i, filtro))
    const s = search.trim().toLowerCase()
    if (s) lista = lista.filter((i) => i.nome.toLowerCase().includes(s) || i.numero.toLowerCase().includes(s))
    return lista
  }, [itens, filtro, search])

  const resumo = useMemo(() => {
    const totalAberto = itens.reduce((s, i) => s + Number(i.saldo), 0)
    const emCobranca = itens.filter((i) => ['cobranca', 'concluida'].includes(i.fase.codigo))
    const valorCobranca = emCobranca.reduce((s, i) => s + Number(i.saldo), 0)
    const prazosHoje = itens.filter((i) => i.pausa_vigente && i.pausa_vigente.pausado_ate === hojeISO()).length
    const posEvento = itens.filter((i) => i.dias_para_evento < 0)
    return {
      totalAberto, emCobranca: emCobranca.length, valorCobranca, prazosHoje,
      posEvento: posEvento.length, valorPos: posEvento.reduce((s, i) => s + Number(i.saldo), 0),
    }
  }, [itens])

  const recarregarTudo = () => { load() }

  return (
    <div className={styles.abaInner}>
      <div className={styles.resumo}>
        <div className={styles.kpi}>
          <div className={styles.kpiLb}>Em aberto</div>
          <div className={styles.kpiVl}>R$ {brl(resumo.totalAberto)}</div>
          <div className={styles.kpiSub}>{itens.length} evento(s) na régua</div>
        </div>
        <div className={styles.kpi}>
          <div className={styles.kpiLb}>Já em cobrança</div>
          <div className={styles.kpiVl}>R$ {brl(resumo.valorCobranca)}</div>
          <div className={styles.kpiSub}>{resumo.emCobranca} evento(s) passaram da data limite</div>
        </div>
        <div className={`${styles.kpi} ${resumo.prazosHoje ? styles.kpiAlerta : ''}`}>
          <div className={styles.kpiLb}>Prazos combinados para hoje</div>
          <div className={styles.kpiVl}>{resumo.prazosHoje}</div>
          <div className={styles.kpiSub}>pausas que vencem hoje</div>
        </div>
        <div className={`${styles.kpi} ${resumo.posEvento ? styles.kpiAlerta : ''}`}>
          <div className={styles.kpiLb}>Evento já realizado</div>
          <div className={styles.kpiVl}>{resumo.posEvento}</div>
          <div className={styles.kpiSub}>R$ {brl(resumo.valorPos)} pós-evento</div>
        </div>
      </div>

      <div className={styles.filtros}>
        {FILTROS.map(([id, label]) => (
          <button
            key={id} className={styles.chip} aria-pressed={filtro === id}
            onClick={() => setFiltro(id)}
          >
            {label}<span className={styles.chipCount}>{contagens[id]}</span>
          </button>
        ))}
        <div className={styles.spacer} />
        <input
          className={styles.searchInput} placeholder="Buscar cliente ou evento…"
          value={search} onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className={styles.tblWrap}>
        {loading ? (
          <div className={styles.center}><Spinner /></div>
        ) : !visiveis.length ? (
          <Empty message="Nenhum evento neste filtro." />
        ) : (
          <table className={styles.tbl}>
            <thead>
              <tr>
                <th>Cliente / evento</th><th>Data do evento</th><th>Saldo</th>
                <th>Fase da régua</th><th>Último contato</th><th>Próxima ação</th><th />
              </tr>
            </thead>
            <tbody>
              {visiveis.map((item) => (
                <LinhaFila
                  key={item.evento_id} item={item}
                  onLigar={() => setModalLigacao(item)}
                  onPausar={() => setModalPausa(item)}
                  onRetomar={() => setModalRetomar(item)}
                  onLinha={() => setDrawerEventoId(item.evento_id)}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {modalLigacao && (
        <ModalLigacao
          item={modalLigacao} onClose={() => setModalLigacao(null)}
          onSalvo={(msg) => { setModalLigacao(null); recarregarTudo(); onToast(msg) }}
        />
      )}
      {modalPausa && (
        <ModalPausa
          item={modalPausa} onClose={() => setModalPausa(null)}
          onSalvo={(msg) => { setModalPausa(null); recarregarTudo(); onToast(msg) }}
        />
      )}
      {modalRetomar && (
        <ModalRetomar
          item={modalRetomar} onClose={() => setModalRetomar(null)}
          onSalvo={(msg) => { setModalRetomar(null); recarregarTudo(); onToast(msg) }}
        />
      )}
      {drawerEventoId && (
        <DrawerLinhaDoTempo
          eventoId={drawerEventoId} onClose={() => setDrawerEventoId(null)}
          onLigar={(item) => { setDrawerEventoId(null); setModalLigacao(item) }}
          onPausar={(item) => { setDrawerEventoId(null); setModalPausa(item) }}
          onRetomar={(item) => { setDrawerEventoId(null); setModalRetomar(item) }}
        />
      )}
    </div>
  )
}

function LinhaFila({ item, onLigar, onPausar, onRetomar, onLinha }) {
  const f = item.fase
  const c = item.ultimo_contato
  const p = item.proxima_acao
  const pausado = !!item.pausa_vigente

  return (
    <tr>
      <td className={styles.cli}>
        <b>{item.nome}</b>
        <span>{item.numero} · {item.tipo_evento}</span>
      </td>
      <td className={styles.data}>
        <b>{fmtDataLonga(item.data_evento)}</b>
        <span className={styles.dRel}>
          {item.dias_para_evento === 0 ? 'hoje'
            : item.dias_para_evento > 0 ? `em ${item.dias_para_evento} dias`
            : `há ${-item.dias_para_evento} dias`}
        </span>
      </td>
      <td className={styles.saldo}>
        R$ {brl(item.saldo)}
        <span>de R$ {brl(item.valor_total)}</span>
      </td>
      <td>
        <span className={`${styles.pill} ${styles['pill_' + f.codigo]}`}>{f.texto}</span>
        <div className={styles.etapas} aria-hidden="true">
          {item.etapas.map((e) => (
            <i
              key={e.id} title={`${e.rotulo} · D${e.dias > 0 ? '+' : ''}${e.dias}`}
              className={
                e.situacao === 'enviada' ? (e.rotulo?.startsWith('L') ? styles.etL : styles.etC)
                : e.situacao === 'pulada' ? styles.etP : ''
              }
            />
          ))}
        </div>
      </td>
      <td>
        {c ? (
          <div className={styles.contato}>
            <span className={`${styles.ic} ${c.canal === 'whatsapp' ? styles.icW : c.atendeu === false ? styles.icN : styles.icL}`}>
              <i className={`ti ${c.canal === 'whatsapp' ? 'ti-brand-whatsapp' : c.atendeu === false ? 'ti-phone-off' : 'ti-phone'}`} />
            </span>
            <div>
              {c.canal === 'whatsapp' ? 'WhatsApp' : (c.atendeu ? 'Ligação, atendeu' : 'Ligação, não atendeu')}
              <small>{fmtQuando(c.quando)}</small>
            </div>
          </div>
        ) : <span className={styles.textoMuted}>Nenhum contato</span>}
      </td>
      <td><span className={`${styles.prox} ${p.urgente ? styles.proxHoje : ''}`}>{p.texto}</span></td>
      <td>
        <div className={styles.acoes}>
          <button className={styles.ib} title="Registrar ligação" onClick={onLigar}><i className="ti ti-phone" /></button>
          {pausado
            ? <button className={styles.ib} title="Retomar régua" onClick={onRetomar}><i className="ti ti-player-play" /></button>
            : <button className={styles.ib} title="Pausar com prazo" onClick={onPausar}><i className="ti ti-player-pause" /></button>}
          <button className={styles.ib} title="Linha do tempo" onClick={onLinha}><i className="ti ti-list" /></button>
        </div>
      </td>
    </tr>
  )
}

// ─── Modal: Registrar Ligação ───────────────────────────────────────────────

function ModalLigacao({ item, onClose, onSalvo }) {
  const { user } = useAuth()
  const [usuarios, setUsuarios] = useState([])
  const [dataHora, setDataHora] = useState(() => new Date().toISOString().slice(0, 16))
  const [atendenteId, setAtendenteId] = useState(user?.id || '')
  const [telOutro, setTelOutro] = useState('')
  const [usarOutroTel, setUsarOutroTel] = useState(false)
  const [atendeu, setAtendeu] = useState(null)
  const [prazo, setPrazo] = useState('')
  const [pausar, setPausar] = useState(true)
  const [obs, setObs] = useState('')
  const [erro, setErro] = useState('')
  const [salvando, setSalvando] = useState(false)

  useEffect(() => {
    usuariosApi.listar({ page_size: 200 }).then((r) => {
      const lista = r.data.results ?? r.data
      setUsuarios(lista.filter((u) => u.ativo))
    }).catch(() => {})
  }, [])

  const salvar = async () => {
    if (atendeu === null) { setErro('Informe se o cliente atendeu.'); return }
    setErro('')
    setSalvando(true)
    const telefone = usarOutroTel ? telOutro : item.telefone
    const payload = {
      evento: item.evento_id,
      data_hora: new Date(dataHora).toISOString(),
      atendente: atendenteId || undefined,
      telefone_discado: telefone,
      atendeu,
      observacao: obs,
    }
    if (atendeu && prazo) {
      payload.prazo_pagamento = prazo
      payload.pausar = pausar
    }
    try {
      const r = await cobrancaApi.ligacoes.create(payload)
      onSalvo(atendeu && prazo && pausar ? 'Ligação registrada e régua pausada até o prazo' : 'Ligação registrada')
      void r
    } catch (e) {
      setErro(e?.response?.data?.telefone_discado?.[0] || e?.response?.data?.prazo_pagamento?.[0] || e?.response?.data?.data_hora?.[0] || 'Não foi possível registrar a ligação.')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Modal
      open onClose={onClose} title="Registrar ligação"
      footer={<>
        <Btn variant="ghost" onClick={onClose}>Cancelar</Btn>
        <Btn variant="primary" icon="check" loading={salvando} onClick={salvar}>Registrar ligação</Btn>
      </>}
    >
      <p className={styles.modalSub}>{item.numero} · {item.nome} · saldo R$ {brl(item.saldo)}</p>
      <div className={styles.grid2}>
        <Field label="Data e hora da ligação">
          <Input type="datetime-local" value={dataHora} max={new Date().toISOString().slice(0, 16)} onChange={(e) => setDataHora(e.target.value)} />
        </Field>
        <Field label="Atendente">
          <Select value={atendenteId} onChange={(e) => setAtendenteId(e.target.value)}>
            {!atendenteId && <option value="">Selecione…</option>}
            {usuarios.map((u) => <option key={u.id} value={u.id}>{u.name}{u.id === user?.id ? ' (você)' : ''}</option>)}
          </Select>
        </Field>
      </div>

      <div className={styles.radios}>
        <label><input type="radio" name="tel" checked={!usarOutroTel} onChange={() => setUsarOutroTel(false)} /> Telefone do evento · {item.telefone || 'sem telefone'}</label>
        <label><input type="radio" name="tel" checked={usarOutroTel} onChange={() => setUsarOutroTel(true)} /> Outro número</label>
        {usarOutroTel && <Input placeholder="(86) 99999-9999" value={telOutro} onChange={(e) => setTelOutro(e.target.value)} />}
      </div>

      <div>
        <div className={styles.hintStrong}>O cliente atendeu?</div>
        <div className={styles.seg}>
          <button type="button" className={atendeu === true ? styles.segSim : ''} onClick={() => setAtendeu(true)}>
            <i className="ti ti-phone" /> Atendeu
          </button>
          <button type="button" className={atendeu === false ? styles.segNao : ''} onClick={() => setAtendeu(false)}>
            <i className="ti ti-phone-off" /> Não atendeu
          </button>
        </div>
      </div>

      {atendeu === true && (
        <div className={styles.stackSm}>
          <Field label="Prazo combinado para pagamento (opcional)">
            <Input type="date" min={hojeISO()} value={prazo} onChange={(e) => setPrazo(e.target.value)} />
          </Field>
          {prazo && (
            <label className={styles.check}>
              <input type="checkbox" checked={pausar} onChange={(e) => setPausar(e.target.checked)} />
              <span>Pausar o WhatsApp até o prazo<br /><span className={styles.hint}>No dia do prazo sai o lembrete "vence hoje"; se não pagar, no dia seguinte sai "prazo venceu".</span></span>
            </label>
          )}
        </div>
      )}
      {atendeu === false && (
        <div className={styles.aviso}><i className="ti ti-info-circle" /><span>Se a mensagem "tentamos te ligar" estiver desligada na configuração, nada será enviado ao cliente.</span></div>
      )}

      <Field label="Observação"><Textarea value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Ex.: pediu para pagar em 2x" /></Field>
      <div className={styles.aviso}><i className="ti ti-info-circle" /><span>O registro não pode ser editado depois. Para corrigir, registre uma nova ligação.</span></div>
      {erro && <div className={styles.erro}>{erro}</div>}
    </Modal>
  )
}

// ─── Modal: Pausar ──────────────────────────────────────────────────────────

function ModalPausa({ item, onClose, onSalvo }) {
  const [pausadoAte, setPausadoAte] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() + 7)
    return d.toISOString().slice(0, 10)
  })
  const [motivo, setMotivo] = useState('')
  const [erro, setErro] = useState('')
  const [salvando, setSalvando] = useState(false)

  const salvar = async () => {
    if (!motivo.trim()) { setErro('Informe o motivo da pausa.'); return }
    setSalvando(true)
    try {
      await cobrancaApi.pausas.create({ evento: item.evento_id, pausado_ate: pausadoAte, motivo })
      onSalvo(`Régua pausada até ${fmtDataCurta(pausadoAte)}`)
    } catch (e) {
      setErro(e?.response?.data?.motivo?.[0] || e?.response?.data?.pausado_ate?.[0] || 'Não foi possível pausar a régua.')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Modal
      open onClose={onClose} title="Pausar com prazo de pagamento"
      footer={<>
        <Btn variant="ghost" onClick={onClose}>Cancelar</Btn>
        <Btn variant="primary" icon="player-pause" loading={salvando} onClick={salvar}>Pausar régua</Btn>
      </>}
    >
      <p className={styles.modalSub}>{item.numero} · {item.nome} · saldo R$ {brl(item.saldo)}</p>
      <Field label="Pausado até (prazo para pagar)">
        <Input type="date" min={hojeISO()} value={pausadoAte} onChange={(e) => setPausadoAte(e.target.value)} />
      </Field>
      <Field label="Motivo">
        <Input placeholder="Ex.: cliente pediu até sexta para pagar" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      </Field>
      <div className={styles.aviso}><i className="ti ti-info-circle" /><span>Mensagens da régua que vencerem durante a pausa não são enviadas. No dia do prazo sai o lembrete "vence hoje"; no dia seguinte, se não houver pagamento, sai "prazo venceu".</span></div>
      {erro && <div className={styles.erro}>{erro}</div>}
    </Modal>
  )
}

// ─── Modal: Retomar ─────────────────────────────────────────────────────────

function ModalRetomar({ item, onClose, onSalvo }) {
  const [motivo, setMotivo] = useState('')
  const [erro, setErro] = useState('')
  const [salvando, setSalvando] = useState(false)

  const salvar = async () => {
    if (!motivo.trim()) { setErro('Informe o motivo da retomada.'); return }
    setSalvando(true)
    try {
      await cobrancaApi.pausas.encerrar(item.pausa_vigente.id, { motivo })
      onSalvo('Régua retomada')
    } catch (e) {
      setErro(e?.response?.data?.detail || 'Não foi possível retomar a régua.')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Modal
      open onClose={onClose} title="Retomar régua agora"
      footer={<>
        <Btn variant="ghost" onClick={onClose}>Cancelar</Btn>
        <Btn variant="primary" icon="player-play" loading={salvando} onClick={salvar}>Retomar</Btn>
      </>}
    >
      <p className={styles.modalSub}>{item.numero} · pausado até {fmtDataCurta(item.pausa_vigente.pausado_ate)}</p>
      <Field label="Motivo da retomada">
        <Input placeholder="Ex.: cliente desistiu do acordo" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      </Field>
      <div className={styles.aviso}><i className="ti ti-info-circle" /><span>A régua volta a enviar a partir da próxima etapa. Etapas puladas durante a pausa não são reenviadas.</span></div>
      {erro && <div className={styles.erro}>{erro}</div>}
    </Modal>
  )
}

// ─── Gaveta: Linha do Tempo ─────────────────────────────────────────────────

const ICONE_ITEM = { envio: 'ti-message-circle', ligacao: 'ti-phone', pausa: 'ti-player-pause', pausa_encerrada: 'ti-player-play', pagamento: 'ti-cash' }

function DrawerLinhaDoTempo({ eventoId, onClose, onLigar, onPausar, onRetomar }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    cobrancaApi.linhaDoTempo(eventoId).then((r) => setData(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [eventoId])

  const itemParaAcao = () => data && ({
    evento_id: data.evento.id, numero: data.evento.numero, nome: data.evento.nome,
    saldo: data.evento.saldo, valor_total: data.evento.valor_total, telefone: data.evento.telefone,
    pausa_vigente: data.pausa_vigente,
  })

  return (
    <div className={styles.drawerOv} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <aside className={styles.drawer} role="dialog" aria-modal="true" aria-label="Linha do tempo de cobrança">
        <div className={styles.drawerHead}>
          <div>
            <h2 className="serif">{data?.evento?.nome || '···'}</h2>
            <p>{data ? `${data.evento.numero} · ${data.evento.tipo_evento} · ${fmtDataLonga(data.evento.data_evento)}` : ''}</p>
          </div>
          <button className={styles.ib} onClick={onClose} aria-label="Fechar"><i className="ti ti-x" /></button>
        </div>

        {loading || !data ? <div className={styles.center}><Spinner /></div> : (
          <div className={styles.drawerBody}>
            <div className={styles.drFin}>
              <div><small>Total</small><b>R$ {brl(data.evento.valor_total)}</b></div>
              <div><small>Pago</small><b>R$ {brl(data.evento.valor_pago)}</b></div>
              <div><small>Saldo</small><b>R$ {brl(data.evento.saldo)}</b></div>
            </div>

            {data.pausa_vigente && (
              <div className={styles.aviso}>
                <i className="ti ti-player-pause" />
                <span><b>Pausado até {fmtDataLonga(data.pausa_vigente.pausado_ate)}</b> · {data.pausa_vigente.motivo}</span>
              </div>
            )}

            <div className={styles.drAcoes}>
              <Btn icon="phone" onClick={() => onLigar(itemParaAcao())}>Registrar ligação</Btn>
              {data.pausa_vigente
                ? <Btn icon="player-play" onClick={() => onRetomar(itemParaAcao())}>Retomar</Btn>
                : <Btn icon="player-pause" onClick={() => onPausar(itemParaAcao())}>Pausar com prazo</Btn>}
            </div>

            <div>
              <p className={styles.secT}>Régua deste evento</p>
              <div className={styles.miniRegua}>
                {data.etapas.map((e) => (
                  <span
                    key={e.id}
                    className={`${e.situacao === 'enviada' ? styles.envOk : ''} ${e.rotulo?.startsWith('L') ? styles.envL : styles.envC} ${e.situacao === 'pulada' ? styles.pul : ''}`}
                  >
                    {e.situacao === 'enviada' && <i className="ti ti-check" />}
                    {e.rotulo} · {fmtDataCurta(e.data)}
                  </span>
                ))}
              </div>
            </div>

            <div>
              <p className={styles.secT}>Linha do tempo</p>
              <ul className={styles.tl}>
                {!data.linha_do_tempo.length && <li><div className={styles.t}>Sem contatos ainda</div></li>}
                {data.linha_do_tempo.map((it, i) => (
                  <li key={i}>
                    <span className={`${styles.tlIc} ${styles['tlIc_' + it.tipo]}`}><i className={`ti ${ICONE_ITEM[it.tipo] || 'ti-info-circle'}`} /></span>
                    <div>
                      <div className={styles.t}>{it.titulo}</div>
                      <div className={styles.w}>{new Date(it.data_hora).toLocaleString('pt-BR')}</div>
                      {it.detalhe && <div className={styles.d}>{it.detalhe}</div>}
                      {it.mensagem && <div className={styles.q}>{it.mensagem}</div>}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </aside>
    </div>
  )
}

// ═════════════════════════════ ABA: RÉGUA ══════════════════════════════════

function AbaRegua({ cfg, onCfgReload, onToast }) {
  const [etapas, setEtapas] = useState([])
  const [limite, setLimite] = useState(-7)
  const [sel, setSel] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadEtapas = useCallback(() => {
    cobrancaApi.etapas.list().then((r) => {
      const lista = r.data.results ?? r.data
      setEtapas(lista.sort((a, b) => a.dias - b.dias))
      setLimite(r.data.limite_lembrete ?? cfg?.limite_lembrete ?? -7)
      setSel((s) => s ?? (lista[0]?.id ?? null))
    }).catch(() => {}).finally(() => setLoading(false))
  }, [cfg])

  useEffect(() => { loadEtapas() }, [loadEtapas])
  useEffect(() => { if (cfg) setLimite(cfg.limite_lembrete) }, [cfg])

  if (loading || !cfg) return <div className={styles.center}><Spinner /></div>

  const etapaSel = etapas.find((e) => e.id === sel) || null

  return (
    <div className={styles.abaInner}>
      <div className={styles.cfgGrid}>
        <div className={styles.stack}>
          <div className={styles.card}>
            <h3 className="serif">Régua de mensagens</h3>
            <p className={styles.desc}>Cada ponto é uma mensagem de WhatsApp, contada a partir da data do evento. O tipo é definido pela posição em relação à data limite.</p>
            <EixoRegua etapas={etapas} limite={limite} sel={sel} onSel={setSel} />
          </div>

          {etapaSel && (
            <EditorEtapa
              key={etapaSel.id} etapa={etapaSel} limite={limite} etapas={etapas}
              onSalvo={(msg) => { loadEtapas(); onToast(msg) }}
            />
          )}

          <div className={styles.card}>
            <h3 className="serif">Mensagens do prazo combinado e da ligação</h3>
            <p className={styles.desc}>Disparadas fora da régua: quando há uma pausa com prazo de pagamento, ou quando uma ligação não é atendida.</p>
            <MensagensEspeciais cfg={cfg} onSalvo={(msg) => { onCfgReload(); onToast(msg) }} />
          </div>
        </div>

        <div className={styles.stack}>
          <CardGeral cfg={cfg} limite={limite} onSalvo={(msg) => { onCfgReload(); onToast(msg) }} />
          <div className={styles.card}>
            <h3 className="serif">Etapas</h3>
            <p className={styles.desc}>Etapas não são apagadas, só desativadas, para manter o histórico de envios.</p>
            <div className={styles.listaEtapas}>
              {etapas.map((e) => (
                <button key={e.id} className={`${styles.le} ${sel === e.id ? styles.leSel : ''}`} onClick={() => setSel(e.id)}>
                  <span className={styles.leDd}>D{e.dias > 0 ? '+' : ''}{e.dias}</span>
                  <span className={styles.leTx}>{e.mensagem.split('\n')[0]}</span>
                  <span className={`${styles.pill} ${e.ativo ? styles['pill_' + e.tipo] : styles.pill_aguardando}`}>{e.ativo ? e.rotulo : 'Off'}</span>
                </button>
              ))}
            </div>
            <Btn variant="ghost" icon="plus" style={{ marginTop: 12, width: '100%', justifyContent: 'center' }}
              onClick={async () => {
                const maior = etapas.length ? Math.max(...etapas.map((e) => e.dias)) : -12
                let dias = Math.min(maior + 4, 60)
                while (etapas.some((e) => e.dias === dias)) dias -= 1
                try {
                  const r = await cobrancaApi.etapas.create({ dias, mensagem: 'Olá, {primeiro_nome}. O saldo de *R$ {saldo}* do evento {numero_evento} segue em aberto.\nPix: {chave_pix}' })
                  setSel(r.data.id)
                  loadEtapas()
                  onToast('Etapa criada')
                } catch {
                  onToast('Não foi possível criar a etapa', 'error')
                }
              }}
            >
              Adicionar etapa
            </Btn>
          </div>
        </div>
      </div>
    </div>
  )
}

function EixoRegua({ etapas, limite, sel, onSel }) {
  const dias = etapas.map((e) => e.dias).concat([limite])
  const MIN = Math.min(-16, ...dias.map((d) => d - 2))
  const MAX = Math.max(8, ...dias.map((d) => d + 2))
  const pos = (d) => `${((d - MIN) / (MAX - MIN)) * 100}%`
  const corte = limite + 0.5

  const ticks = []
  for (let d = MIN; d <= MAX; d += 2) ticks.push(d)

  return (
    <div className={styles.axisWrap}>
      <div className={styles.axis}>
        <div className={styles.zoneL} style={{ left: 0, width: pos(corte) }} />
        <div className={styles.zoneC} style={{ left: pos(corte), right: 0 }} />
        <span className={styles.zoneLbL} style={{ left: 4 }}>Lembretes</span>
        <span className={styles.zoneLbC} style={{ left: `calc(${pos(corte)} + 6px)` }}>Cobranças</span>
        <div className={styles.base} />
        {ticks.map((d) => (
          <span key={d} className={styles.tickM} style={{ left: pos(d) }} />
        ))}
        <div className={styles.eventoMk} style={{ left: pos(0) }} />
        <span className={styles.eventoLb} style={{ left: pos(0) }}>Dia do evento</span>
        <div className={styles.limiteMk} style={{ left: pos(limite) }} />
        <span className={styles.limiteLb} style={{ left: pos(limite) }}>Data limite D{limite}</span>
        {etapas.map((e) => (
          <button
            key={e.id}
            className={`${styles.etapaPt} ${e.ativo ? (e.rotulo?.startsWith('L') ? styles.etapaL : styles.etapaC) : styles.etapaOff} ${sel === e.id ? styles.etapaSel : ''}`}
            style={{ left: pos(e.dias) }}
            title={`${e.rotulo} · D${e.dias > 0 ? '+' : ''}${e.dias}${e.ativo ? '' : ', desativada'}`}
            onClick={() => onSel(e.id)}
          >
            {e.rotulo}
          </button>
        ))}
      </div>
    </div>
  )
}

function EditorEtapa({ etapa, limite, etapas, onSalvo }) {
  const [dias, setDias] = useState(etapa.dias)
  const [mensagem, setMensagem] = useState(etapa.mensagem)
  const [ativo, setAtivo] = useState(etapa.ativo)
  const [preview, setPreview] = useState({ texto: '', variaveis_invalidas: [] })
  const [salvando, setSalvando] = useState(false)

  const tipo = dias <= limite ? 'lembrete' : 'cobranca'
  const duplicado = etapas.some((e) => e.id !== etapa.id && e.dias === dias)

  useDebounced(() => {
    cobrancaApi.etapas.preview({ mensagem }).then((r) => setPreview(r.data)).catch(() => {})
  }, 400, [mensagem])

  const inserirVar = (v) => setMensagem((m) => `${m}{${v}}`)

  const salvar = async () => {
    setSalvando(true)
    try {
      await cobrancaApi.etapas.update(etapa.id, { dias, mensagem, ativo })
      onSalvo('Etapa salva')
    } catch (e) {
      onSalvo(e?.response?.data?.mensagem?.[0] || e?.response?.data?.dias?.[0] || 'Não foi possível salvar a etapa')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div className={styles.card}>
      <div className={styles.etapaEdHead}>
        <div className={styles.row}>
          <h3 className="serif">Etapa {etapa.ativo ? etapa.rotulo : '—'}</h3>
          <span className={`${styles.pill} ${styles['pill_' + tipo]}`}>{tipo === 'lembrete' ? 'Lembrete' : 'Cobrança'}</span>
          <span className={styles.hint}>tipo definido pela data limite</span>
        </div>
        <label className={styles.switch}>
          <input type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} />
          <span className={styles.track} />Ativa
        </label>
      </div>

      <div className={styles.edGrid}>
        <div className={styles.stackSm}>
          <Field label="Enviar em (dias em relação ao evento)">
            <Input type="number" min={-60} max={60} value={dias} onChange={(e) => setDias(parseInt(e.target.value, 10) || 0)} />
          </Field>
          <span className={styles.hint}>{dias === 0 ? 'Dia do evento' : dias < 0 ? `${-dias} dia(s) antes` : `${dias} dia(s) depois`} · negativo = antes do evento</span>
          {duplicado && <div className={styles.erro}>Já existe outra etapa em D{dias > 0 ? '+' : ''}{dias}.</div>}

          <Field label="Texto da mensagem"><Textarea rows={9} value={mensagem} onChange={(e) => setMensagem(e.target.value)} /></Field>
          <div>
            <span className={styles.hint}>Clique para inserir. Use *texto* para negrito no WhatsApp.</span>
            <div className={styles.vars}>
              {VARS.map((v) => <button type="button" key={v} onClick={() => inserirVar(v)}>{`{${v}}`}</button>)}
            </div>
          </div>
          {!!preview.variaveis_invalidas?.length && (
            <div className={styles.erro}>Variável desconhecida: {preview.variaveis_invalidas.map((v) => `{${v}}`).join(', ')}. O sistema não salva com variáveis inválidas.</div>
          )}
        </div>

        <div className={styles.wa}>
          <div className={styles.waHdr}><span>Prévia{preview.contexto_ficticio ? ' (exemplo)' : ''}</span></div>
          <div className={styles.bolha}>{preview.texto}</div>
        </div>
      </div>

      <div className={styles.saveBar}>
        <Btn variant="primary" icon="check" loading={salvando} disabled={duplicado || !!preview.variaveis_invalidas?.length} onClick={salvar}>
          Salvar etapa
        </Btn>
      </div>
    </div>
  )
}

function MensagensEspeciais({ cfg, onSalvo }) {
  const BLOCOS = [
    { campo: 'msg_prazo_hoje', nome: 'Prazo combinado vence hoje', quando: 'No dia do prazo da pausa, se ainda houver saldo', permitirPrazo: false },
    { campo: 'msg_prazo_vencido', nome: 'Prazo combinado venceu', quando: 'No dia seguinte ao prazo da pausa, se ainda houver saldo', permitirPrazo: true },
    { campo: 'msg_ligacao_nao_atendida', nome: 'Ligação não atendida', quando: 'Logo após registrar uma ligação sem resposta', permitirPrazo: false },
  ]
  return (
    <div className={styles.esp}>
      {BLOCOS.map((b) => <BlocoEspecial key={b.campo} bloco={b} cfg={cfg} onSalvo={onSalvo} />)}
    </div>
  )
}

function BlocoEspecial({ bloco, cfg, onSalvo }) {
  const [aberto, setAberto] = useState(false)
  const [texto, setTexto] = useState(cfg[bloco.campo])
  const [ativoFlag, setAtivoFlag] = useState(cfg[bloco.campo + '_ativo'])
  const [preview, setPreview] = useState({ texto: '', variaveis_invalidas: [] })
  const [salvando, setSalvando] = useState(false)

  useDebounced(() => {
    cobrancaApi.etapas.preview({ mensagem: texto, tipo_especial: bloco.permitirPrazo ? 'prazo_vencido' : undefined })
      .then((r) => setPreview(r.data)).catch(() => {})
  }, 400, [texto])

  const salvar = async () => {
    setSalvando(true)
    try {
      await cobrancaApi.configuracao.update({ [bloco.campo]: texto, [bloco.campo + '_ativo']: ativoFlag })
      onSalvo('Mensagem salva')
    } catch (e) {
      onSalvo(e?.response?.data?.[bloco.campo]?.[0] || 'Não foi possível salvar', 'error')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <details open={aberto} onToggle={(e) => setAberto(e.target.open)}>
      <summary>
        <span>{bloco.nome}<small>{bloco.quando}</small></span>
        <span className={`${styles.pill} ${ativoFlag ? styles.pill_lembrete : styles.pill_aguardando}`}>{ativoFlag ? 'Ligada' : 'Desligada'}</span>
      </summary>
      <div className={styles.edGrid}>
        <div className={styles.stackSm}>
          <label className={styles.switch}>
            <input type="checkbox" checked={ativoFlag} onChange={(e) => setAtivoFlag(e.target.checked)} />
            <span className={styles.track} />Enviar esta mensagem
          </label>
          <Textarea rows={6} value={texto} onChange={(e) => setTexto(e.target.value)} />
          {!!preview.variaveis_invalidas?.length && (
            <div className={styles.erro}>Variável desconhecida: {preview.variaveis_invalidas.map((v) => `{${v}}`).join(', ')}</div>
          )}
          <div className={styles.saveBar}>
            <Btn variant="primary" icon="check" size="sm" loading={salvando} disabled={!!preview.variaveis_invalidas?.length} onClick={salvar}>Salvar</Btn>
          </div>
        </div>
        <div className={styles.wa}>
          <div className={styles.waHdr}><span>Prévia{preview.contexto_ficticio ? ' (exemplo)' : ''}</span></div>
          <div className={styles.bolha}>{preview.texto}</div>
        </div>
      </div>
    </details>
  )
}

function CardGeral({ cfg, limite, onSalvo }) {
  const [ativo, setAtivo] = useState(cfg.ativo)
  const [confirmando, setConfirmando] = useState(false)
  const [limiteLocal, setLimiteLocal] = useState(limite)
  const [diasSem, setDiasSem] = useState(cfg.dias_semana_envio)
  const [pix, setPix] = useState(cfg.chave_pix)
  const [fav, setFav] = useState(cfg.favorecido_pix)
  const [tel, setTel] = useState(cfg.telefone_contato)
  const [intervalo, setIntervalo] = useState(cfg.intervalo_envio_segundos)
  const [notificarEquipe, setNotificarEquipe] = useState(cfg.notificar_equipe_ultima_etapa)
  const [salvando, setSalvando] = useState(false)

  const toggleDia = (i) => setDiasSem((d) => d.includes(i) ? d.filter((x) => x !== i) : [...d, i].sort())

  const salvarGeral = async () => {
    setSalvando(true)
    try {
      await cobrancaApi.configuracao.update({
        limite_lembrete: limiteLocal, dias_semana_envio: diasSem, chave_pix: pix,
        favorecido_pix: fav, telefone_contato: tel, intervalo_envio_segundos: intervalo,
        notificar_equipe_ultima_etapa: notificarEquipe,
      })
      onSalvo('Configurações salvas')
    } catch {
      onSalvo('Não foi possível salvar as configurações', 'error')
    } finally {
      setSalvando(false)
    }
  }

  const confirmarAtivacao = async () => {
    setSalvando(true)
    try {
      await cobrancaApi.configuracao.update({ ativo: true })
      setConfirmando(false)
      onSalvo('Envio automático ligado')
    } catch {
      onSalvo('Não foi possível ligar o envio automático', 'error')
    } finally {
      setSalvando(false)
    }
  }

  const desligar = async () => {
    setSalvando(true)
    try {
      await cobrancaApi.configuracao.update({ ativo: false })
      setAtivo(false)
      onSalvo('Envio automático desligado')
    } catch {
      onSalvo('Não foi possível desligar', 'error')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div className={styles.card}>
      <h3 className="serif">Geral</h3>
      <div className={styles.stackSm} style={{ marginTop: 12 }}>
        <label className={styles.switch}>
          <input
            type="checkbox" checked={ativo}
            onChange={(e) => { if (e.target.checked) { setConfirmando(true) } else { setAtivo(false); desligar() } }}
          />
          <span className={styles.track} />Envio automático ligado
        </label>

        {confirmando && (
          <div className={styles.confirmBox}>
            <p>A partir de hoje, clientes com saldo em aberto passam a receber WhatsApp automático. Etapas com data anterior a hoje não serão enviadas.</p>
            <div className={styles.row}>
              <Btn variant="ghost" size="sm" onClick={() => setConfirmando(false)}>Cancelar</Btn>
              <Btn variant="primary" size="sm" loading={salvando} onClick={() => { setAtivo(true); confirmarAtivacao() }}>Confirmar ativação</Btn>
            </div>
          </div>
        )}

        {!cfg.ativo && (
          <div className={styles.aviso}><i className="ti ti-info-circle" /><span>No primeiro deploy esta opção nasce desligada. Nada é enviado até alguém ligar aqui.</span></div>
        )}

        <Field label="Data limite (fim dos lembretes)">
          <div className={styles.row}>
            <input type="range" min={-30} max={0} value={limiteLocal} onChange={(e) => setLimiteLocal(parseInt(e.target.value, 10))} style={{ flex: 1 }} />
            <output style={{ fontWeight: 700, minWidth: 90 }}>D{limiteLocal}</output>
          </div>
        </Field>

        <div>
          <div className={styles.hintStrong}>Dias com envio</div>
          <div className={styles.diasSem}>
            {DIAS_SEMANA_LABEL.map((lb, i) => (
              <button key={i} type="button" aria-pressed={diasSem.includes(i)} onClick={() => toggleDia(i)}>{lb}</button>
            ))}
          </div>
          <span className={styles.hint}>Mensagem que cair num dia sem envio sai no próximo dia liberado.</span>
        </div>

        <Field label="Chave Pix"><Input value={pix} onChange={(e) => setPix(e.target.value)} /></Field>
        <Field label="Favorecido"><Input value={fav} onChange={(e) => setFav(e.target.value)} /></Field>
        <Field label="Telefone de contato"><Input value={tel} onChange={(e) => setTel(e.target.value)} /></Field>
        <Field label="Intervalo entre envios (segundos)"><Input type="number" min={0} max={30} value={intervalo} onChange={(e) => setIntervalo(parseInt(e.target.value, 10) || 0)} /></Field>
        <label className={styles.check}>
          <input type="checkbox" checked={notificarEquipe} onChange={(e) => setNotificarEquipe(e.target.checked)} />
          <span>Avisar a equipe quando a última etapa é enviada sem pagamento</span>
        </label>

        <div className={styles.saveBar}>
          <Btn variant="primary" icon="check" loading={salvando} onClick={salvarGeral}>Salvar configurações</Btn>
        </div>
      </div>
    </div>
  )
}
