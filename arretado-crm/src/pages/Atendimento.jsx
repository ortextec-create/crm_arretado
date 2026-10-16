import { useState, useEffect, useCallback, useRef } from 'react'
import { atendimentoApi } from '../api/services'
import { useAuth } from '../hooks/useAuth'
import { Btn, Modal, Spinner, Toast, Field, Input, Empty } from '../components/ui'
import { STATUS_MSG, VARIAVEIS, fmtHora } from '../components/atendimento/atendimento'
import styles from './Atendimento.module.css'

const msgErro = (e, padrao) => {
  const d = e.response?.data
  if (!d) return padrao
  if (typeof d === 'string') return padrao
  return d.detail || Object.values(d).flat().join(' ') || padrao
}

// ─── Aba 1: Fila ────────────────────────────────────────────────────────────

function AbaFila({ onToast }) {
  const [msgs, setMsgs] = useState([])
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState('')
  const [direcao, setDirecao] = useState('')

  const load = useCallback(() => {
    const params = { page_size: 100 }
    if (status) params.status = status
    if (direcao) params.direcao = direcao
    atendimentoApi.mensagens.list(params)
      .then((r) => setMsgs(r.data.results ?? r.data))
      .catch(() => setMsgs([]))
      .finally(() => setLoading(false))
  }, [status, direcao])

  useEffect(() => {
    load()
    const t = setInterval(load, 10_000)
    return () => clearInterval(t)
  }, [load])

  const cancelar = async (m) => {
    try {
      await atendimentoApi.mensagens.cancelar(m.id)
      onToast('Mensagem cancelada.')
      load()
    } catch (e) { onToast(msgErro(e, 'Não foi possível cancelar.'), 'error'); load() }
  }
  const reenviar = async (m) => {
    if (!window.confirm(`Reenviar a mensagem do pedido #${m.display_id}?\n\n${m.texto}`)) return
    try {
      await atendimentoApi.mensagens.reenviar(m.id)
      onToast('Nova mensagem enfileirada.')
      load()
    } catch (e) { onToast(msgErro(e, 'Não foi possível reenviar.'), 'error') }
  }

  return (
    <div className={styles.abaInner}>
      <div className={styles.filtros}>
        <select className={styles.sel} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Todos os status</option>
          {Object.entries(STATUS_MSG).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select className={styles.sel} value={direcao} onChange={(e) => setDirecao(e.target.value)}>
          <option value="">Saída e entrada</option>
          <option value="saida">Saída</option>
          <option value="entrada">Entrada</option>
        </select>
        <span className={styles.spacer} />
        <span className={styles.muted}>Atualiza a cada 10 s</span>
      </div>
      {loading ? <div className={styles.center}><Spinner size={26} /></div>
        : msgs.length === 0 ? <Empty icon="messages" message="Nenhuma mensagem na fila." />
        : (
          <div className={styles.tblWrap}>
            <table className={styles.tbl}>
              <thead><tr>
                <th>Pedido</th><th>Gatilho</th><th>Texto</th><th>Status</th><th>Quando</th><th />
              </tr></thead>
              <tbody>
                {msgs.map((m) => {
                  const st = STATUS_MSG[m.status] || { label: m.status, cls: 'st_neutro' }
                  return (
                    <tr key={m.id}>
                      <td><b>#{m.display_id}</b></td>
                      <td>{m.gatilho_display || (m.direcao === 'entrada' ? 'Cliente' : m.origem)}
                        {m.autor_nome && <div className={styles.muted}>{m.autor_nome}</div>}</td>
                      <td className={styles.texto}>{m.texto}
                        {m.erro && <div className={styles.erroTxt}>{m.erro}</div>}</td>
                      <td><span className={`${styles.pill} ${styles[st.cls]}`}>{st.label}</span>
                        {m.tentativas > 1 && <div className={styles.muted}>{m.tentativas} tentativas</div>}</td>
                      <td className={styles.muted}>{fmtHora(m.enviado_em || m.criado_em)}</td>
                      <td><div className={styles.acoes}>
                        {['pendente', 'sugerida'].includes(m.status) && (
                          <Btn variant="ghost" size="sm" icon="x" onClick={() => cancelar(m)}>Cancelar</Btn>)}
                        {['falha', 'incerta', 'expirada'].includes(m.status) && m.direcao === 'saida' && (
                          <Btn variant="ghost" size="sm" icon="refresh" onClick={() => reenviar(m)}>Reenviar</Btn>)}
                      </div></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
    </div>
  )
}

// ─── Aba 2: Mensagens (modelos) ─────────────────────────────────────────────

function CardModelo({ modelo, onSalvo, onToast }) {
  const [texto, setTexto] = useState(modelo.texto)
  const [ativo, setAtivo] = useState(modelo.ativo)
  const [preview, setPreview] = useState('')
  const [salvando, setSalvando] = useState(false)
  const ref = useRef(null)
  const sujo = texto !== modelo.texto || ativo !== modelo.ativo

  useEffect(() => {
    const t = setTimeout(() => {
      atendimentoApi.modelos.preview({ texto })
        .then((r) => setPreview(r.data.renderizado))
        .catch(() => setPreview(''))
    }, 400)
    return () => clearTimeout(t)
  }, [texto])

  const inserir = (v) => {
    const el = ref.current
    const ins = `{${v}}`
    if (!el) return setTexto((t) => t + ins)
    const ini = el.selectionStart ?? texto.length
    const fim = el.selectionEnd ?? texto.length
    setTexto(texto.slice(0, ini) + ins + texto.slice(fim))
    setTimeout(() => { el.focus(); el.setSelectionRange(ini + ins.length, ini + ins.length) }, 0)
  }

  const salvar = async () => {
    setSalvando(true)
    try {
      await atendimentoApi.modelos.update(modelo.id, { texto, ativo })
      onToast('Modelo salvo.')
      onSalvo()
    } catch (e) { onToast(msgErro(e, 'Erro ao salvar o modelo.'), 'error') }
    finally { setSalvando(false) }
  }

  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>
        <b>{modelo.gatilho_display}</b>
        <label className={styles.toggle}>
          <input type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} /> Ativo
        </label>
      </div>
      <div className={styles.cols}>
        <div>
          <div className={styles.lbl}>Texto</div>
          <textarea ref={ref} className={styles.ta} value={texto} onChange={(e) => setTexto(e.target.value)} />
          <div className={styles.chips} style={{ marginTop: 6 }}>
            {VARIAVEIS.map(([v, l]) => (
              <button key={v} type="button" className={styles.chip} onClick={() => inserir(v)} title={`{${v}}`}>{l}</button>
            ))}
          </div>
        </div>
        <div>
          <div className={styles.lbl}>Prévia (dados fictícios)</div>
          <div className={styles.preview}>{preview}</div>
        </div>
      </div>
      {sujo && <div className={styles.acoes}>
        <Btn variant="ghost" size="sm" onClick={() => { setTexto(modelo.texto); setAtivo(modelo.ativo) }}>Descartar</Btn>
        <Btn size="sm" icon="device-floppy" loading={salvando} onClick={salvar}>Salvar</Btn>
      </div>}
    </div>
  )
}

function AbaMensagens({ onToast }) {
  const [modelos, setModelos] = useState(null)
  const load = useCallback(() => {
    atendimentoApi.modelos.list().then((r) => setModelos(r.data.results ?? r.data)).catch(() => setModelos([]))
  }, [])
  useEffect(() => { load() }, [load])
  if (!modelos) return <div className={styles.center}><Spinner size={26} /></div>
  return (
    <div className={styles.abaInner}>
      <div className={styles.aviso}><i className="ti ti-info-circle" />
        Alterar um modelo vale para os próximos pedidos — mensagens já na fila mantêm o texto de quando foram criadas.</div>
      <div className={styles.cards}>
        {modelos.map((m) => <CardModelo key={`${m.id}-${m.atualizado_em}`} modelo={m} onSalvo={load} onToast={onToast} />)}
      </div>
    </div>
  )
}

// ─── Aba 3: Configuração ────────────────────────────────────────────────────

const CAMPOS_NUM = [
  ['janela_maxima_horas', 'Janela máxima (horas)', 'Pedidos mais antigos que isso não recebem mensagem automática.'],
  ['expiracao_minutos', 'Expiração (minutos)', 'Mensagem automática não enviada nesse prazo é descartada.'],
  ['atraso_tolerancia_min', 'Tolerância de atraso (min)', 'Minutos além da previsão antes de avisar o cliente.'],
]

function AbaConfiguracao({ onToast }) {
  const [cfg, setCfg] = useState(null)
  const [form, setForm] = useState({})
  const [salvando, setSalvando] = useState(false)

  const load = useCallback(() => {
    atendimentoApi.configuracao.get().then((r) => { setCfg(r.data); setForm(r.data) }).catch(() => {})
  }, [])
  useEffect(() => { load() }, [load])

  if (!cfg) return <div className={styles.center}><Spinner size={26} /></div>

  const patch = async (dados, okMsg = 'Configuração salva.') => {
    setSalvando(true)
    try {
      const r = await atendimentoApi.configuracao.update(dados)
      setCfg(r.data); setForm(r.data); onToast(okMsg)
    } catch (e) { onToast(msgErro(e, 'Erro ao salvar.'), 'error') }
    finally { setSalvando(false) }
  }

  const alternarChat = () => {
    const ligar = !cfg.chat_ativo
    if (ligar && !window.confirm('Ligar o chat automático?\n\nA partir de agora, mensagens reais serão enviadas aos clientes dos pedidos iFood desta empresa.')) return
    patch({ chat_ativo: ligar }, ligar ? 'Chat automático ligado.' : 'Chat automático desligado.')
  }

  const sujo = CAMPOS_NUM.some(([k]) => Number(form[k]) !== cfg[k])

  return (
    <div className={styles.abaInner}>
      <div className={`${styles.card} ${styles.destaque}`}>
        <div className={styles.cardHead}>
          <div>
            <b>Chat automático</b>
            <div className={styles.muted}>{cfg.chat_ativo ? 'Ligado — mensagens reais estão sendo enfileiradas.' : 'Desligado — nada é enfileirado nem enviado.'}</div>
          </div>
          <Btn variant={cfg.chat_ativo ? 'ghost' : 'primary'} icon={cfg.chat_ativo ? 'player-pause' : 'player-play'}
            loading={salvando} onClick={alternarChat}>
            {cfg.chat_ativo ? 'Desligar' : 'Ligar'}
          </Btn>
        </div>
        <div className={styles.aviso}><i className="ti ti-alert-triangle" />
          Ligar esta chave faz o CRM enviar mensagens reais no chat dos clientes (via extensão). Teste antes com o modo seguro da extensão.</div>
      </div>

      <div className={styles.card}>
        <b>Parâmetros</b>
        <div className={styles.grid3}>
          {CAMPOS_NUM.map(([k, l, h]) => (
            <Field key={k} label={l}>
              <Input type="number" min="1" value={form[k] ?? ''} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
              <span className={styles.muted}>{h}</span>
            </Field>
          ))}
        </div>
        {sujo && <div className={styles.acoes}>
          <Btn variant="ghost" size="sm" onClick={() => setForm(cfg)}>Descartar</Btn>
          <Btn size="sm" icon="device-floppy" loading={salvando}
            onClick={() => patch(Object.fromEntries(CAMPOS_NUM.map(([k]) => [k, Number(form[k])])))}>Salvar</Btn>
        </div>}
      </div>

      <div className={`${styles.card} ${styles.desabilitado}`}>
        <b>Respostas com IA <span className={styles.muted}>(disponível em breve — Fase 5)</span></b>
        <div className={styles.muted}>Modo: {cfg.modo_ia} · Modelo: {cfg.ia_modelo}</div>
      </div>
    </div>
  )
}

// ─── Aba 4: Extensão ────────────────────────────────────────────────────────

function AbaExtensao({ onToast }) {
  const { user, empresas, empresaAtiva } = useAuth()
  const admin = user?.role === 'admin'
  const [st, setSt] = useState(null)
  const [tokens, setTokens] = useState([])
  const [cfgExt, setCfgExt] = useState(null)
  const [json, setJson] = useState('')
  const [jsonErro, setJsonErro] = useState('')
  const [novo, setNovo] = useState(false)
  const [nome, setNome] = useState('')
  const [empIds, setEmpIds] = useState([])
  const [tokenPuro, setTokenPuro] = useState(null)
  const [salvando, setSalvando] = useState(false)

  const loadStatus = useCallback(() => {
    atendimentoApi.statusExtensao().then((r) => setSt(r.data)).catch(() => {})
  }, [])
  const loadTokens = useCallback(() => {
    if (!admin) return
    atendimentoApi.tokens.list().then((r) => setTokens(r.data.results ?? r.data)).catch(() => {})
  }, [admin])
  const loadCfgExt = useCallback(() => {
    if (!admin) return
    atendimentoApi.extensao.getConfig().then((r) => {
      setCfgExt(r.data)
      setJson(JSON.stringify({ seletores: r.data.seletores, tempos_ms: r.data.tempos_ms }, null, 2))
    }).catch(() => {})
  }, [admin])

  useEffect(() => {
    loadStatus()
    const t = setInterval(loadStatus, 15_000)
    return () => clearInterval(t)
  }, [loadStatus])
  useEffect(() => { loadTokens(); loadCfgExt() }, [loadTokens, loadCfgExt])

  const abrirNovo = () => {
    setNome(''); setTokenPuro(null)
    setEmpIds(empresaAtiva ? [empresaAtiva.id] : [])
    setNovo(true)
  }
  const criar = async () => {
    setSalvando(true)
    try {
      const r = await atendimentoApi.tokens.create({ nome: nome.trim(), empresas_ids: empIds })
      setTokenPuro(r.data.token); loadTokens()
    } catch (e) { onToast(msgErro(e, 'Erro ao criar o token.'), 'error') }
    finally { setSalvando(false) }
  }
  const copiar = () => navigator.clipboard?.writeText(tokenPuro).then(() => onToast('Token copiado.'))
  const revogar = async (t) => {
    if (!window.confirm(`Revogar o token "${t.nome}"? A extensão que o usa para de funcionar.`)) return
    try { await atendimentoApi.tokens.revogar(t.id); onToast('Token revogado.'); loadTokens() }
    catch (e) { onToast(msgErro(e, 'Erro ao revogar.'), 'error') }
  }
  const salvarJson = async () => {
    let dados
    try { dados = JSON.parse(json) } catch { return setJsonErro('JSON inválido.') }
    setJsonErro('')
    try {
      await atendimentoApi.extensao.updateConfig({ seletores: dados.seletores ?? {}, tempos_ms: dados.tempos_ms ?? {} })
      onToast('Configuração da extensão salva (vale em até 5 min).'); loadCfgExt()
    } catch (e) { setJsonErro(msgErro(e, 'Erro ao salvar.')) }
  }

  const seletores = Object.entries(st?.seletores_ok || {})

  return (
    <div className={styles.abaInner}>
      <div className={styles.card}>
        <div className={styles.cardHead}>
          <b>Status da extensão</b>
          <span className={styles.statusPill}>
            <span className={`${styles.dot} ${!st?.online ? styles.dotOff : ''}`} />
            {st?.online ? 'Online' : 'Offline'}
          </span>
        </div>
        <div className={styles.muted}>
          {st?.ultimo_heartbeat ? `Último sinal: ${fmtHora(st.ultimo_heartbeat)} · versão ${st.versao || '—'}` : 'Nenhum sinal recebido ainda.'}
        </div>
        {seletores.length > 0 && (
          <div className={styles.seletores}>
            {seletores.map(([k, ok]) => (
              <span key={k} className={`${styles.pill} ${ok ? styles.st_ok : styles.st_critico}`}>
                {ok ? '✓' : '✗'} {k}
              </span>
            ))}
          </div>
        )}
        <div className={styles.aviso}><i className="ti ti-info-circle" />
          A extensão só envia com o Chrome aberto no Gestor de Pedidos do iFood, logado. Instalação: ver extensao-ifood-chat/README.md.</div>
      </div>

      {admin ? (
        <>
          <div className={styles.card}>
            <div className={styles.cardHead}>
              <b>Tokens de acesso</b>
              <Btn size="sm" icon="plus" onClick={abrirNovo}>Novo token</Btn>
            </div>
            {tokens.length === 0 ? <div className={styles.muted}>Nenhum token criado.</div> : (
              <div className={styles.tblWrap}>
                <table className={styles.tbl} style={{ minWidth: 600 }}>
                  <thead><tr><th>Nome</th><th>Prefixo</th><th>Empresas</th><th>Último sinal</th><th>Status</th><th /></tr></thead>
                  <tbody>{tokens.map((t) => (
                    <tr key={t.id}>
                      <td>{t.nome}</td>
                      <td><code>{t.prefixo}…</code></td>
                      <td>{t.empresas.map((e) => e.nome).join(', ')}</td>
                      <td className={styles.muted}>{t.ultimo_heartbeat ? fmtHora(t.ultimo_heartbeat) : '—'}</td>
                      <td><span className={`${styles.pill} ${t.ativo ? styles.st_ok : styles.st_neutro}`}>{t.ativo ? 'Ativo' : 'Revogado'}</span></td>
                      <td><div className={styles.acoes}>
                        {t.ativo && <Btn variant="ghost" size="sm" icon="ban" onClick={() => revogar(t)}>Revogar</Btn>}
                      </div></td>
                    </tr>))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {cfgExt && (
            <div className={styles.card}>
              <b>Configuração técnica da extensão (seletores e tempos)</b>
              <div className={styles.muted}>Quando o iFood mudar o HTML do Gestor, o conserto é aqui — sem reinstalar a extensão. Vale para todas as empresas.</div>
              <textarea className={styles.json} value={json} onChange={(e) => setJson(e.target.value)} spellCheck={false} />
              {jsonErro && <div className={styles.erro}>{jsonErro}</div>}
              <div className={styles.acoes}><Btn size="sm" icon="device-floppy" onClick={salvarJson}>Salvar</Btn></div>
            </div>
          )}
        </>
      ) : (
        <div className={styles.aviso}><i className="ti ti-lock" />Tokens e configuração técnica da extensão são restritos a administradores.</div>
      )}

      <Modal open={novo} onClose={() => { setNovo(false); setTokenPuro(null) }} title="Novo token da extensão" width={480}
        footer={tokenPuro
          ? <Btn onClick={() => { setNovo(false); setTokenPuro(null) }}>Fechar</Btn>
          : <Btn icon="key" loading={salvando} disabled={!nome.trim() || empIds.length === 0} onClick={criar}>Criar token</Btn>}>
        {tokenPuro ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div className={styles.aviso}><i className="ti ti-alert-triangle" />Copie agora: este token não será exibido de novo.</div>
            <div className={styles.tokenBox}>{tokenPuro}</div>
            <Btn variant="ghost" icon="copy" onClick={copiar}>Copiar</Btn>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <Field label="Nome"><Input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex.: Computador do caixa" /></Field>
            <Field label="Empresas atendidas por este Gestor">
              {(empresas || []).map((e) => (
                <label key={e.id} className={styles.toggle}>
                  <input type="checkbox" checked={empIds.includes(e.id)}
                    onChange={(ev) => setEmpIds(ev.target.checked ? [...empIds, e.id] : empIds.filter((i) => i !== e.id))} /> {e.nome}
                </label>
              ))}
            </Field>
          </div>
        )}
      </Modal>
    </div>
  )
}

// ─── Página ─────────────────────────────────────────────────────────────────

const ABAS = [
  ['Fila', 'list'],
  ['Mensagens', 'message-2'],
  ['Configuração', 'settings'],
  ['Extensão', 'plug-connected'],
]

export default function Atendimento() {
  const { empresaAtiva } = useAuth()
  const [aba, setAba] = useState(0)
  const [toast, setToast] = useState(null)
  const showToast = (msg, tipo = 'success') => setToast({ msg, tipo })
  const [cfg, setCfg] = useState(null)

  // Recarrega tudo ao trocar de empresa (o backend resolve pela empresa ativa do usuário).
  useEffect(() => {
    setCfg(null)
    atendimentoApi.configuracao.get().then((r) => setCfg(r.data)).catch(() => {})
  }, [empresaAtiva?.id, aba])

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={`serif ${styles.title}`}><i className="ti ti-messages" /> Atendimento iFood</h1>
          <p className={styles.subtitle}>Mensagens automáticas no chat dos pedidos iFood, enviadas pela extensão de Chrome.</p>
        </div>
        {cfg && (
          <span className={styles.statusPill}>
            <span className={`${styles.dot} ${!cfg.chat_ativo ? styles.dotOff : ''}`} />
            {cfg.chat_ativo ? 'Chat automático ligado' : 'Chat automático desligado · nada é enviado'}
          </span>
        )}
      </div>
      <div className={styles.tabBar}>
        {ABAS.map(([l, ic], i) => (
          <button key={l} className={`${styles.tab} ${aba === i ? styles.tabActive : ''}`} onClick={() => setAba(i)}>
            <i className={`ti ti-${ic}`} /> {l}
          </button>
        ))}
      </div>
      <div key={`${empresaAtiva?.id}-${aba}`} style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {aba === 0 && <AbaFila onToast={showToast} />}
        {aba === 1 && <AbaMensagens onToast={showToast} />}
        {aba === 2 && <AbaConfiguracao onToast={showToast} />}
        {aba === 3 && <AbaExtensao onToast={showToast} />}
      </div>
      {toast && <Toast message={toast.msg} type={toast.tipo} onClose={() => setToast(null)} />}
    </div>
  )
}
