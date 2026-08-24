import { useState, useEffect, useCallback } from 'react'
import { financeiroApi } from '../api/services'
import { useAuth } from '../hooks/useAuth'
import { Btn, Modal, Spinner, Toast, Field, Input, Select, Empty } from '../components/ui'
import styles from './Financeiro.module.css'

const fmt = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const fmtData = (iso) => {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}
const fmtDataCurta = (iso) => {
  if (!iso) return ''
  const [, m, d] = iso.split('-')
  return `${d}/${m}`
}
const hojeISO = () => new Date().toISOString().slice(0, 10)

const ABAS = ['Contas a Pagar', 'Contas a Receber', 'Fluxo de Caixa', 'Categorias', 'Configurações']

const STATUS_PAGAR_LABEL = { pendente: 'Pendente', parcial: 'Parcial', paga: 'Paga', cancelada: 'Cancelada' }
const STATUS_RECEBER_LABEL = { pendente: 'Pendente', parcial: 'Parcial', recebida: 'Recebida', cancelada: 'Cancelada' }
const ORIGEM_PAGAR_LABEL = { manual: 'Manual', nota_fiscal: 'Nota Fiscal', recorrente: 'Recorrente' }
const CANAL_RECEBER_LABEL = { ifood: 'iFood', manual: 'Manual' }
const FORMA_PAGAMENTO_LABEL = { pix: 'Pix', boleto: 'Boleto', cartao: 'Cartão', dinheiro: 'Dinheiro', outro: 'Outro' }

function StatusBadge({ status, labels, vencida }) {
  if (vencida) return <span className={`${styles.badge} ${styles.badge_atraso}`}>Em atraso</span>
  return <span className={`${styles.badge} ${styles['badge_' + status]}`}>{labels[status] || status}</span>
}

export default function Financeiro() {
  const { empresaAtiva, empresas } = useAuth()
  const empresaId = empresaAtiva?.id
  const multiEmpresa = (empresas?.length || 0) > 1

  const [aba, setAba] = useState(0)
  const [toast, setToast] = useState(null)
  const showToast = (msg, tipo = 'success') => setToast({ msg, tipo })

  const [contasBancarias, setContasBancarias] = useState([])
  const [categorias, setCategorias] = useState([])
  const [fornecedores, setFornecedores] = useState([])

  const loadListasBase = useCallback(() => {
    if (!empresaId) return
    financeiroApi.contasBancarias.list({ page_size: 100, empresa: empresaId }).then((r) => setContasBancarias(r.data.results ?? r.data)).catch(() => {})
    financeiroApi.categorias.list({ page_size: 200 }).then((r) => setCategorias(r.data.results ?? r.data)).catch(() => {})
    financeiroApi.fornecedores.list({ page_size: 300 }).then((r) => setFornecedores(r.data.results ?? r.data)).catch(() => {})
  }, [empresaId])

  useEffect(() => { loadListasBase() }, [loadListasBase])

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={`serif ${styles.title}`}><i className="ti ti-cash" /> Financeiro</h1>
          <p className={styles.subtitle}>
            Contas a pagar/receber, fluxo de caixa e configurações financeiras
            {multiEmpresa && empresaAtiva && <span className={styles.empresaBadge}> · {empresaAtiva.nome}</span>}
          </p>
        </div>
      </div>

      <div className={styles.tabBar}>
        {ABAS.map((label, i) => (
          <button key={i} className={`${styles.tab} ${aba === i ? styles.tabActive : ''}`} onClick={() => setAba(i)}>
            {label}
          </button>
        ))}
      </div>

      <div className={styles.abaContent}>
        {aba === 0 && <AbaContasPagar categorias={categorias} fornecedores={fornecedores} contasBancarias={contasBancarias} empresaId={empresaId} multiEmpresa={multiEmpresa} onToast={showToast} />}
        {aba === 1 && <AbaContasReceber categorias={categorias} contasBancarias={contasBancarias} empresaId={empresaId} multiEmpresa={multiEmpresa} onToast={showToast} />}
        {aba === 2 && <AbaFluxoCaixa contasBancarias={contasBancarias} categorias={categorias} empresaId={empresaId} multiEmpresa={multiEmpresa} onReloadContas={loadListasBase} onToast={showToast} />}
        {aba === 3 && <AbaCategorias categorias={categorias} onReload={loadListasBase} onToast={showToast} />}
        {aba === 4 && <AbaConfiguracoes contasBancarias={contasBancarias} fornecedores={fornecedores} empresaId={empresaId} empresaNome={empresaAtiva?.nome} onReload={loadListasBase} onToast={showToast} />}
      </div>

      {toast && <Toast message={toast.msg} type={toast.tipo} onClose={() => setToast(null)} />}
    </div>
  )
}

// ─── Aba 1: Contas a Pagar ─────────────────────────────────────────────────────

function AbaContasPagar({ categorias, fornecedores, contasBancarias, empresaId, multiEmpresa, onToast }) {
  const [resumo, setResumo] = useState(null)
  const [contas, setContas] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusFiltro, setStatusFiltro] = useState('')
  const [search, setSearch] = useState('')
  const [todas, setTodas] = useState(false)
  const [modalNova, setModalNova] = useState(false)
  const [modalBaixa, setModalBaixa] = useState(null)
  const [recorrentes, setRecorrentes] = useState([])
  const [modalRecorrente, setModalRecorrente] = useState(false)

  const empresaParam = todas ? 'todas' : empresaId

  const loadResumo = useCallback(() => {
    financeiroApi.contasPagar.resumo({ empresa: empresaParam }).then((r) => setResumo(r.data)).catch(() => {})
  }, [empresaParam])

  const load = useCallback(() => {
    setLoading(true)
    const params = { page_size: 100, empresa: empresaParam }
    if (statusFiltro) params.status = statusFiltro
    if (search) params.search = search
    financeiroApi.contasPagar.list(params)
      .then((r) => setContas(r.data.results ?? r.data))
      .catch(() => setContas([]))
      .finally(() => setLoading(false))
  }, [statusFiltro, search, empresaParam])

  const loadRecorrentes = useCallback(() => {
    financeiroApi.recorrentes.list({ page_size: 100, empresa: empresaParam }).then((r) => setRecorrentes(r.data.results ?? r.data)).catch(() => {})
  }, [empresaParam])

  useEffect(() => { loadResumo(); loadRecorrentes() }, [loadResumo, loadRecorrentes])
  useEffect(() => { load() }, [load])

  const handleCancelar = async (conta) => {
    if (!window.confirm(`Cancelar a conta ${conta.numero}? Só é possível se nada tiver sido pago ainda.`)) return
    try {
      await financeiroApi.contasPagar.cancelar(conta.id)
      onToast('Conta cancelada.')
      load(); loadResumo()
    } catch (e) {
      onToast(e?.response?.data?.detail || 'Erro ao cancelar.', 'error')
    }
  }

  const toggleRecorrente = async (r) => {
    try {
      await financeiroApi.recorrentes.update(r.id, { ativo: !r.ativo })
      loadRecorrentes()
      onToast(r.ativo ? 'Despesa recorrente pausada.' : 'Despesa recorrente reativada.')
    } catch { onToast('Erro ao atualizar despesa recorrente.', 'error') }
  }

  const hoje = hojeISO()

  return (
    <div className={styles.abaInner}>
      {resumo && (
        <div className={styles.statsRow}>
          <div className={`${styles.statCard} ${styles.statDanger}`}>
            <i className={`ti ti-alert-triangle ${styles.statIconDanger}`} />
            <div><div className={styles.statValue}>{resumo.em_atraso}</div><div className={styles.statLabel}>Em atraso</div></div>
          </div>
          <div className={styles.statCard}>
            <i className="ti ti-calendar-due" style={{ color: 'var(--caramelo)' }} />
            <div><div className={styles.statValue}>{resumo.vence_hoje}</div><div className={styles.statLabel}>Vence hoje</div></div>
          </div>
          <div className={styles.statCard}>
            <i className="ti ti-calendar-time" style={{ color: 'var(--caramelo)' }} />
            <div><div className={styles.statValue}>{resumo.proximos_7_dias}</div><div className={styles.statLabel}>Próx. 7 dias</div></div>
          </div>
          <div className={`${styles.statCard} ${styles.statAccent}`}>
            <i className="ti ti-report-money" />
            <div><div className={styles.statValue}>{fmt(resumo.total_mes.pago)}</div><div className={styles.statLabel}>Pago no mês (pendente {fmt(resumo.total_mes.pendente)})</div></div>
          </div>
        </div>
      )}

      <div className={styles.toolbarRow}>
        <div className={styles.searchBox}>
          <i className="ti ti-search" />
          <input placeholder="Buscar por número, descrição, fornecedor…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className={styles.chipRow}>
          {['', 'pendente', 'parcial', 'paga', 'cancelada'].map((s) => (
            <button key={s || 'todas'} className={`${styles.chip} ${statusFiltro === s ? styles.chipActive : ''}`} onClick={() => setStatusFiltro(s)}>
              {s ? STATUS_PAGAR_LABEL[s] : 'Todas'}
            </button>
          ))}
        </div>
        {multiEmpresa && (
          <button className={`${styles.chip} ${todas ? styles.chipActive : ''}`} onClick={() => setTodas((v) => !v)}>
            Todas as empresas
          </button>
        )}
        <div className={styles.spacer} />
        <Btn icon="plus" onClick={() => setModalNova(true)}>Nova Conta a Pagar</Btn>
      </div>

      {loading ? <div className={styles.center}><Spinner /></div> : contas.length === 0 ? (
        <Empty icon="receipt-off" message="Nenhuma conta a pagar encontrada." />
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Número</th><th>Descrição / Fornecedor</th><th>Categoria</th><th>Vencimento</th>
                <th className={styles.thRight}>Valor</th><th className={styles.thRight}>Saldo</th>
                <th>Origem</th><th>Status</th><th></th>
              </tr>
            </thead>
            <tbody>
              {contas.map((c) => {
                const vencida = c.data_vencimento < hoje && ['pendente', 'parcial'].includes(c.status)
                return (
                  <tr key={c.id} className={c.status === 'cancelada' ? styles.rowCancelada : ''}>
                    <td className={styles.tdMuted}>{c.numero}</td>
                    <td>
                      <div className={styles.tdNome}>{c.descricao || c.fornecedor_nome || '—'}</div>
                      {c.descricao && c.fornecedor_nome && <div className={styles.tdMuted}>{c.fornecedor_nome}</div>}
                    </td>
                    <td className={styles.tdMuted}>{c.categoria_nome || '— sem categoria —'}</td>
                    <td className={vencida ? styles.tdVermelho : ''}>{fmtData(c.data_vencimento)}</td>
                    <td className={styles.tdRight}>{fmt(c.valor)}</td>
                    <td className={styles.tdRight}>{fmt(c.saldo_restante)}</td>
                    <td><span className={styles.origemTag}>{ORIGEM_PAGAR_LABEL[c.origem]}</span></td>
                    <td><StatusBadge status={c.status} labels={STATUS_PAGAR_LABEL} vencida={vencida} /></td>
                    <td>
                      {['pendente', 'parcial'].includes(c.status) && (
                        <>
                          <button className={styles.iconBtn} title="Registrar baixa" onClick={() => setModalBaixa(c)}><i className="ti ti-cash-banknote" /></button>
                          {Number(c.valor_pago) === 0 && (
                            <button className={styles.iconBtn} title="Cancelar" onClick={() => handleCancelar(c)}><i className="ti ti-ban" /></button>
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className={styles.subSection}>
        <div className={styles.subSectionHeader}>
          <h3 className={styles.subSectionTitle}><i className="ti ti-repeat" /> Despesas Recorrentes</h3>
          <Btn variant="ghost" size="sm" icon="plus" onClick={() => setModalRecorrente(true)}>Nova Despesa Recorrente</Btn>
        </div>
        {recorrentes.length === 0 ? (
          <Empty icon="repeat-off" message="Nenhuma despesa recorrente cadastrada — aluguel, energia, assinaturas etc." />
        ) : (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr><th>Descrição</th><th>Fornecedor</th><th>Categoria</th><th className={styles.thRight}>Valor</th><th>Dias de vencimento</th><th></th></tr>
              </thead>
              <tbody>
                {recorrentes.map((r) => (
                  <tr key={r.id}>
                    <td className={styles.tdNome}>{r.descricao}</td>
                    <td className={styles.tdMuted}>{r.fornecedor_nome || '—'}</td>
                    <td className={styles.tdMuted}>{r.categoria_nome}</td>
                    <td className={styles.tdRight}>{fmt(r.valor)}{r.valor_tipo === 'estimado' && <span className={styles.tdMuted}> (estimado)</span>}</td>
                    <td className={styles.tdMuted}>{r.dias_vencimento.join(', ')}</td>
                    <td>
                      <button className={styles.chip} onClick={() => toggleRecorrente(r)}>{r.ativo ? 'Ativa' : 'Pausada'}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {modalNova && (
        <ModalNovaContaPagar
          categorias={categorias} fornecedores={fornecedores} empresaId={empresaId}
          onClose={() => setModalNova(false)}
          onSaved={() => { setModalNova(false); load(); loadResumo(); onToast('Conta a pagar criada!') }}
        />
      )}
      {modalBaixa && (
        <ModalBaixaConta
          conta={modalBaixa} tipo="pagar" contasBancarias={contasBancarias}
          onClose={() => setModalBaixa(null)}
          onSaved={() => { setModalBaixa(null); load(); loadResumo(); onToast('Baixa registrada!') }}
        />
      )}
      {modalRecorrente && (
        <ModalNovaDespesaRecorrente
          categorias={categorias} fornecedores={fornecedores} empresaId={empresaId}
          onClose={() => setModalRecorrente(false)}
          onSaved={() => { setModalRecorrente(false); loadRecorrentes(); onToast('Despesa recorrente criada!') }}
        />
      )}
    </div>
  )
}

// ─── Aba 2: Contas a Receber ───────────────────────────────────────────────────

function AbaContasReceber({ categorias, contasBancarias, empresaId, multiEmpresa, onToast }) {
  const [resumo, setResumo] = useState(null)
  const [contas, setContas] = useState([])
  const [loading, setLoading] = useState(true)
  const [canalFiltro, setCanalFiltro] = useState('')
  const [statusFiltro, setStatusFiltro] = useState('')
  const [search, setSearch] = useState('')
  const [todas, setTodas] = useState(false)
  const [modalNova, setModalNova] = useState(false)
  const [modalBaixa, setModalBaixa] = useState(null)

  const empresaParam = todas ? 'todas' : empresaId

  const loadResumo = useCallback(() => {
    financeiroApi.contasReceber.resumo({ empresa: empresaParam }).then((r) => setResumo(r.data)).catch(() => {})
  }, [empresaParam])

  const load = useCallback(() => {
    setLoading(true)
    const params = { page_size: 100, empresa: empresaParam }
    if (canalFiltro) params.canal = canalFiltro
    if (statusFiltro) params.status = statusFiltro
    if (search) params.search = search
    financeiroApi.contasReceber.list(params)
      .then((r) => setContas(r.data.results ?? r.data))
      .catch(() => setContas([]))
      .finally(() => setLoading(false))
  }, [canalFiltro, statusFiltro, search, empresaParam])

  useEffect(() => { loadResumo() }, [loadResumo])
  useEffect(() => { load() }, [load])

  const hoje = hojeISO()

  return (
    <div className={styles.abaInner}>
      {resumo && (
        <div className={styles.statsRow} style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
          <div className={`${styles.statCard} ${styles.statAccent}`}>
            <i className="ti ti-cash" />
            <div><div className={styles.statValue}>{fmt(resumo.recebido_hoje)}</div><div className={styles.statLabel}>Recebido hoje</div></div>
          </div>
          <div className={styles.statCard}>
            <i className="ti ti-clock-dollar" style={{ color: 'var(--caramelo)' }} />
            <div><div className={styles.statValue}>{fmt(resumo.a_receber)}</div><div className={styles.statLabel}>A receber (contas + eventos)</div></div>
          </div>
          <div className={styles.statCard}>
            <i className="ti ti-calendar-time" style={{ color: 'var(--caramelo)' }} />
            <div><div className={styles.statValue}>{fmt(resumo.proximos_30_dias)}</div><div className={styles.statLabel}>Próx. 30 dias</div></div>
          </div>
        </div>
      )}

      <div className={styles.toolbarRow}>
        <div className={styles.searchBox}>
          <i className="ti ti-search" />
          <input placeholder="Buscar por número, cliente, referência…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className={styles.chipRow}>
          {['', 'ifood', 'manual'].map((c) => (
            <button key={c || 'todos'} className={`${styles.chip} ${canalFiltro === c ? styles.chipActive : ''}`} onClick={() => setCanalFiltro(c)}>
              {c ? CANAL_RECEBER_LABEL[c] : 'Todos os canais'}
            </button>
          ))}
        </div>
        <Select value={statusFiltro} onChange={(e) => setStatusFiltro(e.target.value)} style={{ width: 160 }}>
          <option value="">Todos os status</option>
          {Object.entries(STATUS_RECEBER_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
        {multiEmpresa && (
          <button className={`${styles.chip} ${todas ? styles.chipActive : ''}`} onClick={() => setTodas((v) => !v)}>
            Todas as empresas
          </button>
        )}
        <div className={styles.spacer} />
        <Btn icon="plus" onClick={() => setModalNova(true)}>Novo Lançamento Manual</Btn>
      </div>

      <p className={styles.hintSmall}>
        O saldo de Eventos em aberto entra automaticamente no resumo acima — nunca aparece como linha na
        tabela (evita duplicar o mesmo valor). iFood no modo <strong>repasse</strong> gera contas aqui
        automaticamente; no modo <strong>no ato</strong> o valor já entra direto no caixa. Configure isso na aba Configurações.
      </p>

      {loading ? <div className={styles.center}><Spinner /></div> : contas.length === 0 ? (
        <Empty icon="receipt-off" message="Nenhuma conta a receber encontrada." />
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Número</th><th>Cliente / Referência</th><th>Categoria</th><th>Vencimento</th>
                <th className={styles.thRight}>Valor</th><th className={styles.thRight}>Saldo</th>
                <th>Canal</th><th>Status</th><th></th>
              </tr>
            </thead>
            <tbody>
              {contas.map((c) => {
                const vencida = c.data_vencimento < hoje && ['pendente', 'parcial'].includes(c.status)
                return (
                  <tr key={c.id} className={c.status === 'cancelada' ? styles.rowCancelada : ''}>
                    <td className={styles.tdMuted}>{c.numero}</td>
                    <td>
                      <div className={styles.tdNome}>{c.cliente_nome_crm || c.cliente_nome || '—'}</div>
                      {c.referencia && <div className={styles.tdMuted}>{c.referencia}</div>}
                    </td>
                    <td className={styles.tdMuted}>{c.categoria_nome || '—'}</td>
                    <td className={vencida ? styles.tdVermelho : ''}>{fmtData(c.data_vencimento)}</td>
                    <td className={styles.tdRight}>{fmt(c.valor)}</td>
                    <td className={styles.tdRight}>{fmt(c.saldo_restante)}</td>
                    <td><span className={styles.origemTag}>{CANAL_RECEBER_LABEL[c.canal]}</span></td>
                    <td><StatusBadge status={c.status} labels={STATUS_RECEBER_LABEL} vencida={vencida} /></td>
                    <td>
                      {['pendente', 'parcial'].includes(c.status) && (
                        <button className={styles.iconBtn} title="Registrar recebimento" onClick={() => setModalBaixa(c)}><i className="ti ti-cash-banknote" /></button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {modalNova && (
        <ModalNovaContaReceber
          categorias={categorias} empresaId={empresaId}
          onClose={() => setModalNova(false)}
          onSaved={() => { setModalNova(false); load(); loadResumo(); onToast('Lançamento manual criado!') }}
        />
      )}
      {modalBaixa && (
        <ModalBaixaConta
          conta={modalBaixa} tipo="receber" contasBancarias={contasBancarias}
          onClose={() => setModalBaixa(null)}
          onSaved={() => { setModalBaixa(null); load(); loadResumo(); onToast('Recebimento registrado!') }}
        />
      )}
    </div>
  )
}

// ─── Aba 3: Fluxo de Caixa ─────────────────────────────────────────────────────

function AbaFluxoCaixa({ contasBancarias, categorias, empresaId, multiEmpresa, onReloadContas, onToast }) {
  const [dias, setDias] = useState(14)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [modalConferir, setModalConferir] = useState(null)
  const [modalManual, setModalManual] = useState(false)
  const [todas, setTodas] = useState(false)

  const empresaParam = todas ? 'todas' : empresaId

  const load = useCallback(() => {
    setLoading(true)
    financeiroApi.fluxoCaixa(dias, empresaParam).then((r) => setData(r.data)).catch(() => setData(null)).finally(() => setLoading(false))
  }, [dias, empresaParam])

  useEffect(() => { load() }, [load])

  const diasArr = data?.dias ?? []
  const maxValor = Math.max(1, ...diasArr.flatMap((d) => [
    Number(d.entrada_realizada) + Number(d.entrada_projetada),
    Number(d.saida_realizada) + Number(d.saida_projetada),
  ]))
  const scale = 86 / maxValor

  return (
    <div className={styles.abaInner}>
      <div className={styles.toolbarRow}>
        <div className={styles.chipRow}>
          {[7, 14, 30].map((d) => (
            <button key={d} className={`${styles.chip} ${dias === d ? styles.chipActive : ''}`} onClick={() => setDias(d)}>{d} dias</button>
          ))}
        </div>
        {multiEmpresa && (
          <button className={`${styles.chip} ${todas ? styles.chipActive : ''}`} onClick={() => setTodas((v) => !v)}>
            Todas as empresas
          </button>
        )}
        <div className={styles.spacer} />
        <Btn variant="ghost" icon="cash-banknote" onClick={() => setModalManual(true)}>Lançamento Manual</Btn>
      </div>

      {loading ? <div className={styles.center}><Spinner /></div> : (
        <>
          <div className={styles.fluxoPanel}>
            <h3 className={styles.cardTitle}><i className="ti ti-chart-bar" /> Realizado × Projetado</h3>
            {diasArr.length === 0 ? <Empty icon="chart-bar" message="Sem movimentos ou contas no período." /> : (
              <>
                <div className={styles.fluxoChart}>
                  {diasArr.map((d) => {
                    const title = `${fmtData(d.data)} — Entradas: ${fmt(d.entrada_realizada)} realizado + ${fmt(d.entrada_projetada)} projetado · Saídas: ${fmt(d.saida_realizada)} realizado + ${fmt(d.saida_projetada)} projetado`
                    return (
                      <div key={d.data} className={styles.fluxoCol} title={title}>
                        <div className={styles.fluxoUpWrap}>
                          <div className={styles.fluxoBarUp}>
                            <div className={styles.barEntradaProjetada} style={{ height: Number(d.entrada_projetada) * scale }} />
                            <div className={styles.barEntradaRealizada} style={{ height: Number(d.entrada_realizada) * scale }} />
                          </div>
                        </div>
                        <div className={styles.fluxoBaseline} />
                        <div className={styles.fluxoDownWrap}>
                          <div className={styles.fluxoBarDown}>
                            <div className={styles.barSaidaRealizada} style={{ height: Number(d.saida_realizada) * scale }} />
                            <div className={styles.barSaidaProjetada} style={{ height: Number(d.saida_projetada) * scale }} />
                          </div>
                        </div>
                        <span className={styles.fluxoLabel}>{fmtDataCurta(d.data)}</span>
                      </div>
                    )
                  })}
                </div>
                <div className={styles.legend}>
                  <span><i style={{ background: '#059669' }} />Entrada realizada</span>
                  <span><i style={{ background: 'rgba(5,150,105,.35)' }} />Entrada projetada</span>
                  <span><i style={{ background: '#dc2626' }} />Saída realizada</span>
                  <span><i style={{ background: 'rgba(220,38,38,.35)' }} />Saída projetada</span>
                </div>
              </>
            )}
          </div>

          <div>
            <h3 className={styles.cardTitle} style={{ marginTop: 4 }}><i className="ti ti-building-bank" /> Contas Bancárias</h3>
            {(data?.contas ?? []).length === 0 ? (
              <Empty icon="building-bank" message="Nenhuma conta bancária cadastrada — cadastre em Configurações." />
            ) : (
              <div className={styles.contasGrid}>
                {data.contas.map((c) => (
                  <div key={c.id} className={styles.contaCard}>
                    <div className={styles.contaNome}>{c.nome}</div>
                    <div className={styles.contaSaldo}>{fmt(c.saldo_atual)}</div>
                    {c.ultima_conferencia ? (
                      <div className={styles.contaConferencia}>
                        <span>Conferido em {fmtData(c.ultima_conferencia.data)}: {fmt(c.ultima_conferencia.saldo_informado)}</span>
                        <span className={styles.contaConferenciaDif} style={{ color: Number(c.ultima_conferencia.diferenca) === 0 ? '#059669' : '#dc2626' }}>
                          Diferença: {fmt(c.ultima_conferencia.diferenca)}
                        </span>
                      </div>
                    ) : <div className={styles.contaConferencia}>Ainda não conferido.</div>}
                    <div className={styles.contaFoot}>
                      <Btn variant="ghost" size="sm" icon="checkbox" onClick={() => setModalConferir(c)}>Conferir saldo</Btn>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {modalConferir && (
        <ModalConferirSaldo
          conta={modalConferir}
          onClose={() => setModalConferir(null)}
          onSaved={() => { setModalConferir(null); load(); onToast('Conferência de saldo registrada!') }}
        />
      )}
      {modalManual && (
        <ModalLancamentoManual
          contasBancarias={contasBancarias} categorias={categorias}
          onClose={() => setModalManual(false)}
          onSaved={() => { setModalManual(false); load(); onReloadContas(); onToast('Lançamento manual registrado!') }}
        />
      )}
    </div>
  )
}

// ─── Aba 4: Categorias ─────────────────────────────────────────────────────────

function AbaCategorias({ categorias, onReload, onToast }) {
  const [modalCat, setModalCat] = useState(null)
  const [tipoFiltro, setTipoFiltro] = useState('')

  const listaFiltrada = tipoFiltro ? categorias.filter((c) => c.tipo === tipoFiltro) : categorias

  const handleRemover = async (cat) => {
    if (!window.confirm(`Excluir a categoria "${cat.nome}"?`)) return
    try {
      await financeiroApi.categorias.remove(cat.id)
      onReload()
      onToast('Categoria removida.')
    } catch (e) {
      onToast(e?.response?.data?.detail || 'Não foi possível excluir — categoria em uso.', 'error')
    }
  }

  return (
    <div className={styles.abaInner}>
      <div className={styles.toolbarRow}>
        <div className={styles.chipRow}>
          {['', 'entrada', 'saida'].map((t) => (
            <button key={t || 'todas'} className={`${styles.chip} ${tipoFiltro === t ? styles.chipActive : ''}`} onClick={() => setTipoFiltro(t)}>
              {t === '' ? 'Todas' : t === 'entrada' ? 'Entrada' : 'Saída'}
            </button>
          ))}
        </div>
        <div className={styles.spacer} />
        <Btn icon="plus" onClick={() => setModalCat({})}>Nova Categoria</Btn>
      </div>

      {categorias.length === 0 ? (
        <Empty icon="category" message='Nenhuma categoria cadastrada ainda. Cadastre as categorias financeiras da sua empresa (ex: Fornecedores, Aluguel, Vendas) para organizar contas e movimentos.' />
      ) : listaFiltrada.length === 0 ? (
        <Empty icon="category" message="Nenhuma categoria desse tipo." />
      ) : (
        <div className={styles.catGrid}>
          {listaFiltrada.map((c) => (
            <div key={c.id} className={styles.catRow}>
              <span className={styles.catNome}>{c.nome}</span>
              <span className={`${styles.catTipoTag} ${styles['catTipoTag_' + c.tipo]}`}>{c.tipo === 'entrada' ? 'Entrada' : 'Saída'}</span>
              <button className={styles.iconBtn} title="Editar" onClick={() => setModalCat(c)}><i className="ti ti-edit" /></button>
              <button className={styles.iconBtn} title="Excluir" onClick={() => handleRemover(c)}><i className="ti ti-trash" /></button>
            </div>
          ))}
        </div>
      )}

      {modalCat && (
        <ModalCategoria
          categoria={modalCat.id ? modalCat : null}
          onClose={() => setModalCat(null)}
          onSaved={() => { setModalCat(null); onReload(); onToast('Categoria salva!') }}
        />
      )}
    </div>
  )
}

// ─── Aba 5: Configurações ──────────────────────────────────────────────────────

function AbaConfiguracoes({ contasBancarias, fornecedores, empresaId, empresaNome, onReload, onToast }) {
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [telefones, setTelefones] = useState([])
  const [novoNumero, setNovoNumero] = useState('')
  const [novoNome, setNovoNome] = useState('')
  const [addingTel, setAddingTel] = useState(false)
  const [modalConta, setModalConta] = useState(null)
  const [modalFornecedor, setModalFornecedor] = useState(null)
  const [searchFornecedor, setSearchFornecedor] = useState('')

  useEffect(() => {
    if (!empresaId) return
    setForm(null)
    financeiroApi.configuracao.get(empresaId).then((r) => setForm(r.data)).catch(() => {})
    financeiroApi.telefonesAlerta.list().then((r) => setTelefones(r.data.results ?? r.data)).catch(() => {})
  }, [empresaId])

  const salvar = async () => {
    setSaving(true)
    try {
      const { data } = await financeiroApi.configuracao.update({
        recebimento_ifood: form.recebimento_ifood,
        dias_repasse_ifood: form.dias_repasse_ifood,
        nota_gera_conta_pagar: form.nota_gera_conta_pagar,
        alerta_antecedencia_dias: form.alerta_antecedencia_dias,
        alerta_repeticao_dias: form.alerta_repeticao_dias,
        horizonte_recorrencia_dias: form.horizonte_recorrencia_dias,
        conta_padrao_vendas: form.conta_padrao_vendas || null,
      }, empresaId)
      setForm(data)
      onToast('Configurações financeiras salvas!')
    } catch {
      onToast('Erro ao salvar configurações.', 'error')
    } finally { setSaving(false) }
  }

  const adicionarTelefone = async () => {
    if (!novoNumero.trim()) return
    setAddingTel(true)
    try {
      const { data } = await financeiroApi.telefonesAlerta.create({ numero: novoNumero.trim(), nome: novoNome.trim() })
      setTelefones((t) => [...t, data])
      setNovoNumero(''); setNovoNome('')
    } catch {
      onToast('Erro ao adicionar telefone.', 'error')
    } finally { setAddingTel(false) }
  }

  const removerTelefone = async (id) => {
    try {
      await financeiroApi.telefonesAlerta.remove(id)
      setTelefones((t) => t.filter((x) => x.id !== id))
    } catch {
      onToast('Erro ao remover telefone.', 'error')
    }
  }

  const handleRemoverFornecedor = async (f) => {
    if (!window.confirm(`Excluir o fornecedor "${f.nome}"?`)) return
    try {
      await financeiroApi.fornecedores.remove(f.id)
      onReload()
      onToast('Fornecedor removido.')
    } catch (e) {
      onToast(e?.response?.data?.detail || 'Não foi possível excluir.', 'error')
    }
  }

  const fornecedoresFiltrados = searchFornecedor
    ? fornecedores.filter((f) => f.nome.toLowerCase().includes(searchFornecedor.toLowerCase()) || (f.cnpj || '').includes(searchFornecedor))
    : fornecedores

  if (!form) {
    return <div className={styles.abaInner}><div className={styles.center}><Spinner /></div></div>
  }

  return (
    <div className={styles.abaInner}>
      <div className={styles.confLayout}>
        <div className={styles.panel}>
          <h3 className={styles.cardTitle}><i className="ti ti-settings" /> Configurações Gerais</h3>

          <Field label="Recebimento iFood">
            <Select value={form.recebimento_ifood} onChange={(e) => setForm((f) => ({ ...f, recebimento_ifood: e.target.value }))}>
              <option value="no_ato">No ato (pago direto no caixa)</option>
              <option value="repasse">Repasse (recebido depois)</option>
            </Select>
          </Field>
          {form.recebimento_ifood === 'repasse' && (
            <Field label="Dias até o repasse">
              <Input type="number" min="0" value={form.dias_repasse_ifood} onChange={(e) => setForm((f) => ({ ...f, dias_repasse_ifood: e.target.value }))} />
            </Field>
          )}

          <Field label="Conta padrão de vendas">
            <Select value={form.conta_padrao_vendas ?? ''} onChange={(e) => setForm((f) => ({ ...f, conta_padrao_vendas: e.target.value || null }))}>
              <option value="">— nenhuma (movimentos automáticos não serão gravados) —</option>
              {contasBancarias.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </Select>
          </Field>

          <label className={styles.toggleRow}>
            <div>
              <div className={styles.toggleLbl}>Nota fiscal gera Conta a Pagar</div>
              <div className={styles.toggleDesc}>Ao confirmar a entrada de estoque de uma nota fiscal</div>
            </div>
            <input type="checkbox" checked={form.nota_gera_conta_pagar} onChange={(e) => setForm((f) => ({ ...f, nota_gera_conta_pagar: e.target.checked }))} />
          </label>

          <Field label="Alertar vencimento com quantos dias de antecedência">
            <Input type="number" min="0" value={form.alerta_antecedencia_dias} onChange={(e) => setForm((f) => ({ ...f, alerta_antecedencia_dias: e.target.value }))} />
          </Field>
          <Field label="Repetir alerta a cada quantos dias">
            <Input type="number" min="1" value={form.alerta_repeticao_dias} onChange={(e) => setForm((f) => ({ ...f, alerta_repeticao_dias: e.target.value }))} />
          </Field>
          <Field label="Horizonte de geração de recorrentes (dias)">
            <Input type="number" min="1" value={form.horizonte_recorrencia_dias} onChange={(e) => setForm((f) => ({ ...f, horizonte_recorrencia_dias: e.target.value }))} />
          </Field>

          <Btn onClick={salvar} loading={saving} style={{ width: '100%', justifyContent: 'center', marginTop: 8 }}>Salvar Configurações</Btn>

          <Field label="Telefones que recebem alerta de vencimento">
            <div style={{ display: 'flex', gap: 8 }}>
              <Input placeholder="(86) 99xxx-xxxx" value={novoNumero} onChange={(e) => setNovoNumero(e.target.value)} />
              <Input placeholder="Label (opcional)" value={novoNome} onChange={(e) => setNovoNome(e.target.value)} style={{ maxWidth: 140 }} />
              <Btn variant="ghost" icon="plus" loading={addingTel} onClick={adicionarTelefone} disabled={!novoNumero.trim()}>Add</Btn>
            </div>
          </Field>
          {telefones.length === 0 ? (
            <p className={styles.hintSmall}>Nenhum telefone cadastrado ainda — os alertas não serão enviados.</p>
          ) : (
            <ul className={styles.telList}>
              {telefones.map((t) => (
                <li key={t.id} className={styles.telItem}>
                  <span>{t.nome ? `${t.nome} — ${t.numero}` : t.numero}</span>
                  <button onClick={() => removerTelefone(t.id)} aria-label="Remover telefone"><i className="ti ti-x" /></button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div className={styles.panel}>
            <div className={styles.subSectionHeader}>
              <h3 className={styles.cardTitle} style={{ margin: 0 }}><i className="ti ti-building-bank" /> Contas Bancárias</h3>
              <Btn variant="ghost" size="sm" icon="plus" onClick={() => setModalConta({})}>Nova</Btn>
            </div>
            {contasBancarias.length === 0 ? (
              <Empty icon="building-bank" message="Nenhuma conta bancária cadastrada." />
            ) : (
              <ul className={styles.telList}>
                {contasBancarias.map((c) => (
                  <li key={c.id} className={styles.telItem}>
                    <span>{c.nome} · {c.tipo === 'banco' ? 'Banco' : 'Caixa'} · {fmt(c.saldo_atual)}{!c.ativo && ' (inativa)'}</span>
                    <button onClick={() => setModalConta(c)} aria-label="Editar conta"><i className="ti ti-edit" /></button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className={styles.panel}>
            <div className={styles.subSectionHeader}>
              <h3 className={styles.cardTitle} style={{ margin: 0 }}><i className="ti ti-truck-delivery" /> Fornecedores</h3>
              <Btn variant="ghost" size="sm" icon="plus" onClick={() => setModalFornecedor({})}>Novo</Btn>
            </div>
            <div className={styles.searchBox} style={{ maxWidth: 'none', marginBottom: 10 }}>
              <i className="ti ti-search" />
              <input placeholder="Buscar fornecedor…" value={searchFornecedor} onChange={(e) => setSearchFornecedor(e.target.value)} />
            </div>
            {fornecedoresFiltrados.length === 0 ? (
              <Empty icon="truck-off" message="Nenhum fornecedor cadastrado." />
            ) : (
              <ul className={styles.telList}>
                {fornecedoresFiltrados.map((f) => (
                  <li key={f.id} className={styles.telItem}>
                    <span>{f.nome}{f.cnpj && ` — ${f.cnpj}`}</span>
                    <span>
                      <button onClick={() => setModalFornecedor(f)} aria-label="Editar"><i className="ti ti-edit" /></button>
                      <button onClick={() => handleRemoverFornecedor(f)} aria-label="Excluir"><i className="ti ti-trash" /></button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {modalConta && (
        <ModalContaBancaria
          conta={modalConta.id ? modalConta : null} empresaId={empresaId} empresaNome={empresaNome}
          onClose={() => setModalConta(null)}
          onSaved={() => { setModalConta(null); onReload(); onToast('Conta bancária salva!') }}
        />
      )}
      {modalFornecedor && (
        <ModalFornecedor
          fornecedor={modalFornecedor.id ? modalFornecedor : null}
          onClose={() => setModalFornecedor(null)}
          onSaved={() => { setModalFornecedor(null); onReload(); onToast('Fornecedor salvo!') }}
        />
      )}
    </div>
  )
}

// ─── Modal: Nova Conta a Pagar ─────────────────────────────────────────────────

function ModalNovaContaPagar({ categorias, fornecedores, empresaId, onClose, onSaved }) {
  const [fornecedor, setFornecedor] = useState('')
  const [descricao, setDescricao] = useState('')
  const [categoria, setCategoria] = useState('')
  const [valor, setValor] = useState('')
  const [dataEmissao, setDataEmissao] = useState(hojeISO())
  const [dataVencimento, setDataVencimento] = useState('')
  const [observacao, setObservacao] = useState('')
  const [saving, setSaving] = useState(false)
  const [erro, setErro] = useState('')

  const categoriasSaida = categorias.filter((c) => c.tipo === 'saida')

  const handleSalvar = async () => {
    if (!valor || !dataVencimento) { setErro('Informe ao menos o valor e o vencimento.'); return }
    setSaving(true); setErro('')
    try {
      await financeiroApi.contasPagar.create({
        fornecedor: fornecedor || null, descricao, categoria: categoria || null,
        valor, data_emissao: dataEmissao, data_vencimento: dataVencimento, observacao,
      }, empresaId)
      onSaved()
    } catch (e) {
      const d = e?.response?.data
      setErro(typeof d === 'string' ? d : d?.detail || JSON.stringify(d) || 'Erro ao criar conta a pagar.')
    } finally { setSaving(false) }
  }

  return (
    <Modal
      open title="Nova Conta a Pagar" onClose={onClose} width={460}
      footer={<><Btn variant="ghost" onClick={onClose}>Cancelar</Btn><Btn onClick={handleSalvar} loading={saving}>Criar Conta</Btn></>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Field label="Fornecedor (opcional)">
          <Select value={fornecedor} onChange={(e) => setFornecedor(e.target.value)}>
            <option value="">— nenhum —</option>
            {fornecedores.map((f) => <option key={f.id} value={f.id}>{f.nome}</option>)}
          </Select>
        </Field>
        <Field label="Descrição">
          <Input type="text" placeholder="Ex: Aluguel julho" value={descricao} onChange={(e) => setDescricao(e.target.value)} />
        </Field>
        <Field label="Categoria (opcional)">
          <Select value={categoria} onChange={(e) => setCategoria(e.target.value)}>
            <option value="">— sem categoria —</option>
            {categoriasSaida.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
          </Select>
        </Field>
        <Field label="Valor">
          <Input type="number" min="0.01" step="0.01" placeholder="R$" value={valor} onChange={(e) => setValor(e.target.value)} />
        </Field>
        <Field label="Data de emissão">
          <Input type="date" value={dataEmissao} onChange={(e) => setDataEmissao(e.target.value)} />
        </Field>
        <Field label="Data de vencimento">
          <Input type="date" value={dataVencimento} onChange={(e) => setDataVencimento(e.target.value)} />
        </Field>
        <Field label="Observação (opcional)">
          <Input type="text" value={observacao} onChange={(e) => setObservacao(e.target.value)} />
        </Field>
        {erro && <p className={styles.erro}>{erro}</p>}
      </div>
    </Modal>
  )
}

// ─── Modal: Nova Despesa Recorrente ────────────────────────────────────────────

function ModalNovaDespesaRecorrente({ categorias, fornecedores, empresaId, onClose, onSaved }) {
  const [descricao, setDescricao] = useState('')
  const [fornecedor, setFornecedor] = useState('')
  const [categoria, setCategoria] = useState('')
  const [valor, setValor] = useState('')
  const [valorTipo, setValorTipo] = useState('fixo')
  const [diasTexto, setDiasTexto] = useState('')
  const [saving, setSaving] = useState(false)
  const [erro, setErro] = useState('')

  const categoriasSaida = categorias.filter((c) => c.tipo === 'saida')

  const handleSalvar = async () => {
    const dias = diasTexto.split(',').map((s) => parseInt(s.trim(), 10)).filter((n) => !isNaN(n) && n >= 1 && n <= 31)
    if (!descricao || !categoria || !valor || dias.length === 0) {
      setErro('Preencha descrição, categoria, valor e ao menos um dia de vencimento válido (1-31).')
      return
    }
    setSaving(true); setErro('')
    try {
      await financeiroApi.recorrentes.create({
        descricao, fornecedor: fornecedor || null, categoria, valor, valor_tipo: valorTipo, dias_vencimento: dias,
      }, empresaId)
      onSaved()
    } catch (e) {
      const d = e?.response?.data
      setErro(typeof d === 'string' ? d : d?.detail || JSON.stringify(d) || 'Erro ao criar despesa recorrente.')
    } finally { setSaving(false) }
  }

  return (
    <Modal
      open title="Nova Despesa Recorrente" onClose={onClose} width={460}
      footer={<><Btn variant="ghost" onClick={onClose}>Cancelar</Btn><Btn onClick={handleSalvar} loading={saving}>Criar Despesa Recorrente</Btn></>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Field label="Descrição">
          <Input type="text" placeholder="Ex: Aluguel, Energia, Assinatura" value={descricao} onChange={(e) => setDescricao(e.target.value)} />
        </Field>
        <Field label="Fornecedor (opcional)">
          <Select value={fornecedor} onChange={(e) => setFornecedor(e.target.value)}>
            <option value="">— nenhum —</option>
            {fornecedores.map((f) => <option key={f.id} value={f.id}>{f.nome}</option>)}
          </Select>
        </Field>
        <Field label="Categoria">
          <Select value={categoria} onChange={(e) => setCategoria(e.target.value)}>
            <option value="">— selecionar —</option>
            {categoriasSaida.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
          </Select>
        </Field>
        <Field label="Valor">
          <Input type="number" min="0.01" step="0.01" placeholder="R$" value={valor} onChange={(e) => setValor(e.target.value)} />
        </Field>
        <div className={styles.radioRow}>
          <button className={`${styles.radioChip} ${valorTipo === 'fixo' ? styles.radioChipSel : ''}`} onClick={() => setValorTipo('fixo')}>Valor fixo</button>
          <button className={`${styles.radioChip} ${valorTipo === 'estimado' ? styles.radioChipSel : ''}`} onClick={() => setValorTipo('estimado')}>Valor estimado</button>
        </div>
        <Field label="Dias do mês do vencimento (separados por vírgula)">
          <Input type="text" placeholder="Ex: 1, 15" value={diasTexto} onChange={(e) => setDiasTexto(e.target.value)} />
        </Field>
        <p className={styles.hintSmall}>Dia inexistente no mês (ex: 31 em fevereiro) cai automaticamente no último dia daquele mês.</p>
        {erro && <p className={styles.erro}>{erro}</p>}
      </div>
    </Modal>
  )
}

// ─── Modal: Nova Conta a Receber (manual) ──────────────────────────────────────

function ModalNovaContaReceber({ categorias, empresaId, onClose, onSaved }) {
  const [clienteNome, setClienteNome] = useState('')
  const [referencia, setReferencia] = useState('')
  const [categoria, setCategoria] = useState('')
  const [valor, setValor] = useState('')
  const [dataVencimento, setDataVencimento] = useState('')
  const [saving, setSaving] = useState(false)
  const [erro, setErro] = useState('')

  const categoriasEntrada = categorias.filter((c) => c.tipo === 'entrada')

  const handleSalvar = async () => {
    if (!valor || !dataVencimento) { setErro('Informe ao menos o valor e o vencimento.'); return }
    setSaving(true); setErro('')
    try {
      await financeiroApi.contasReceber.create({
        cliente_nome: clienteNome, referencia, categoria: categoria || null, valor, data_vencimento: dataVencimento,
      }, empresaId)
      onSaved()
    } catch (e) {
      const d = e?.response?.data
      setErro(typeof d === 'string' ? d : d?.detail || JSON.stringify(d) || 'Erro ao criar lançamento.')
    } finally { setSaving(false) }
  }

  return (
    <Modal
      open title="Novo Lançamento Manual (a Receber)" onClose={onClose} width={460}
      footer={<><Btn variant="ghost" onClick={onClose}>Cancelar</Btn><Btn onClick={handleSalvar} loading={saving}>Criar Lançamento</Btn></>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Field label="Cliente (nome livre, opcional)">
          <Input type="text" value={clienteNome} onChange={(e) => setClienteNome(e.target.value)} />
        </Field>
        <Field label="Referência (opcional)">
          <Input type="text" placeholder="Ex: contrato, pedido…" value={referencia} onChange={(e) => setReferencia(e.target.value)} />
        </Field>
        <Field label="Categoria (opcional)">
          <Select value={categoria} onChange={(e) => setCategoria(e.target.value)}>
            <option value="">— sem categoria —</option>
            {categoriasEntrada.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
          </Select>
        </Field>
        <Field label="Valor">
          <Input type="number" min="0.01" step="0.01" placeholder="R$" value={valor} onChange={(e) => setValor(e.target.value)} />
        </Field>
        <Field label="Data de vencimento">
          <Input type="date" value={dataVencimento} onChange={(e) => setDataVencimento(e.target.value)} />
        </Field>
        {erro && <p className={styles.erro}>{erro}</p>}
      </div>
    </Modal>
  )
}

// ─── Modal: Baixa de Conta (pagar/receber) ─────────────────────────────────────

function ModalBaixaConta({ conta, tipo, contasBancarias, onClose, onSaved }) {
  const [dataBaixa, setDataBaixa] = useState(hojeISO())
  const [valor, setValor] = useState(String(conta.saldo_restante))
  const [contaBancaria, setContaBancaria] = useState('')
  const [forma, setForma] = useState('pix')
  const [comprovante, setComprovante] = useState(null)
  const [saving, setSaving] = useState(false)
  const [erro, setErro] = useState('')

  const handleSalvar = async () => {
    if (!valor || !contaBancaria) { setErro('Informe o valor e a conta bancária.'); return }
    setSaving(true); setErro('')
    try {
      let payload, config
      if (comprovante) {
        const formData = new FormData()
        formData.append('data', dataBaixa)
        formData.append('valor', valor)
        formData.append('conta', contaBancaria)
        formData.append('forma', forma)
        formData.append('comprovante', comprovante)
        payload = formData
        config = { headers: { 'Content-Type': undefined } }
      } else {
        payload = { data: dataBaixa, valor, conta: contaBancaria, forma }
        config = {}
      }
      if (tipo === 'pagar') await financeiroApi.contasPagar.baixa(conta.id, payload, config)
      else await financeiroApi.contasReceber.baixa(conta.id, payload, config)
      onSaved()
    } catch (e) {
      const d = e?.response?.data
      setErro(typeof d === 'string' ? d : d?.detail || JSON.stringify(d) || 'Erro ao registrar baixa.')
    } finally { setSaving(false) }
  }

  return (
    <Modal
      open title={tipo === 'pagar' ? `Baixa — ${conta.numero}` : `Recebimento — ${conta.numero}`} onClose={onClose} width={420}
      footer={<><Btn variant="ghost" onClick={onClose}>Cancelar</Btn><Btn onClick={handleSalvar} loading={saving}>{tipo === 'pagar' ? 'Registrar Baixa' : 'Registrar Recebimento'}</Btn></>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <p className={styles.hintSmall}>Saldo restante: {fmt(conta.saldo_restante)}</p>
        <Field label="Data">
          <Input type="date" value={dataBaixa} onChange={(e) => setDataBaixa(e.target.value)} />
        </Field>
        <Field label="Valor">
          <Input type="number" min="0.01" step="0.01" value={valor} onChange={(e) => setValor(e.target.value)} />
        </Field>
        <Field label="Conta bancária">
          <Select value={contaBancaria} onChange={(e) => setContaBancaria(e.target.value)}>
            <option value="">— selecionar —</option>
            {contasBancarias.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
          </Select>
        </Field>
        <Field label="Forma de pagamento">
          <Select value={forma} onChange={(e) => setForma(e.target.value)}>
            {Object.entries(FORMA_PAGAMENTO_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        </Field>
        <Field label="Comprovante (opcional)">
          <input type="file" accept="application/pdf,image/*" onChange={(e) => setComprovante(e.target.files?.[0] ?? null)} />
        </Field>
        {erro && <p className={styles.erro}>{erro}</p>}
      </div>
    </Modal>
  )
}

// ─── Modal: Conferir Saldo ──────────────────────────────────────────────────────

function ModalConferirSaldo({ conta, onClose, onSaved }) {
  const [data, setData] = useState(hojeISO())
  const [saldoInformado, setSaldoInformado] = useState('')
  const [saving, setSaving] = useState(false)
  const [erro, setErro] = useState('')

  const handleSalvar = async () => {
    if (saldoInformado === '') { setErro('Informe o saldo do app do banco.'); return }
    setSaving(true); setErro('')
    try {
      await financeiroApi.conferencias.create({ conta: conta.id, data, saldo_informado: saldoInformado })
      onSaved()
    } catch (e) {
      const d = e?.response?.data
      setErro(typeof d === 'string' ? d : d?.detail || JSON.stringify(d) || 'Erro ao registrar conferência.')
    } finally { setSaving(false) }
  }

  return (
    <Modal
      open title={`Conferir Saldo — ${conta.nome}`} onClose={onClose} width={400}
      footer={<><Btn variant="ghost" onClick={onClose}>Cancelar</Btn><Btn onClick={handleSalvar} loading={saving}>Registrar Conferência</Btn></>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <p className={styles.hintSmall}>Saldo calculado pelo sistema: {fmt(conta.saldo_atual)}</p>
        <Field label="Data">
          <Input type="date" value={data} onChange={(e) => setData(e.target.value)} />
        </Field>
        <Field label="Saldo informado (do app do banco)">
          <Input type="number" step="0.01" placeholder="R$" value={saldoInformado} onChange={(e) => setSaldoInformado(e.target.value)} />
        </Field>
        <p className={styles.hintSmall}>A conferência não altera nenhum valor — só registra a comparação para acompanhamento.</p>
        {erro && <p className={styles.erro}>{erro}</p>}
      </div>
    </Modal>
  )
}

// ─── Modal: Lançamento Manual ───────────────────────────────────────────────────

function ModalLancamentoManual({ contasBancarias, categorias, onClose, onSaved }) {
  const [conta, setConta] = useState('')
  const [tipo, setTipo] = useState('entrada')
  const [valor, setValor] = useState('')
  const [dataMovimento, setDataMovimento] = useState(hojeISO())
  const [categoria, setCategoria] = useState('')
  const [descricao, setDescricao] = useState('')
  const [forma, setForma] = useState('')
  const [comprovante, setComprovante] = useState(null)
  const [saving, setSaving] = useState(false)
  const [erro, setErro] = useState('')

  useEffect(() => { setCategoria('') }, [tipo])

  const categoriasFiltradas = categorias.filter((c) => c.tipo === tipo)

  const handleSalvar = async () => {
    if (!conta || !valor) { setErro('Informe a conta e o valor.'); return }
    setSaving(true); setErro('')
    try {
      let payload, config
      if (comprovante) {
        const formData = new FormData()
        formData.append('conta', conta)
        formData.append('tipo', tipo)
        formData.append('valor', valor)
        formData.append('data_movimento', dataMovimento)
        if (categoria) formData.append('categoria', categoria)
        formData.append('descricao', descricao)
        if (forma) formData.append('forma_pagamento', forma)
        formData.append('comprovante', comprovante)
        payload = formData
        config = { headers: { 'Content-Type': undefined } }
      } else {
        payload = {
          conta, tipo, valor, data_movimento: dataMovimento,
          categoria: categoria || undefined, descricao, forma_pagamento: forma || undefined,
        }
        config = {}
      }
      await financeiroApi.movimentos.manual(payload, config)
      onSaved()
    } catch (e) {
      const d = e?.response?.data
      setErro(typeof d === 'string' ? d : d?.detail || JSON.stringify(d) || 'Erro ao registrar lançamento.')
    } finally { setSaving(false) }
  }

  return (
    <Modal
      open title="Lançamento Manual" onClose={onClose} width={440}
      footer={<><Btn variant="ghost" onClick={onClose}>Cancelar</Btn><Btn onClick={handleSalvar} loading={saving}>Registrar Lançamento</Btn></>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className={styles.radioRow}>
          <button className={`${styles.radioChip} ${tipo === 'entrada' ? styles.radioChipSel : ''}`} onClick={() => setTipo('entrada')}>
            <i className="ti ti-arrow-up-right" /> Entrada
          </button>
          <button className={`${styles.radioChip} ${tipo === 'saida' ? styles.radioChipSel : ''}`} onClick={() => setTipo('saida')}>
            <i className="ti ti-arrow-down-right" /> Saída
          </button>
        </div>
        <Field label="Conta bancária">
          <Select value={conta} onChange={(e) => setConta(e.target.value)}>
            <option value="">— selecionar —</option>
            {contasBancarias.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
          </Select>
        </Field>
        <Field label="Valor">
          <Input type="number" min="0.01" step="0.01" placeholder="R$" value={valor} onChange={(e) => setValor(e.target.value)} />
        </Field>
        <Field label="Data">
          <Input type="date" value={dataMovimento} onChange={(e) => setDataMovimento(e.target.value)} />
        </Field>
        <Field label="Categoria (opcional)">
          <Select value={categoria} onChange={(e) => setCategoria(e.target.value)}>
            <option value="">— sem categoria —</option>
            {categoriasFiltradas.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
          </Select>
        </Field>
        <Field label="Descrição">
          <Input type="text" placeholder="Ex: Saldo inicial" value={descricao} onChange={(e) => setDescricao(e.target.value)} />
        </Field>
        <Field label="Forma de pagamento (opcional)">
          <Select value={forma} onChange={(e) => setForma(e.target.value)}>
            <option value="">— não informar —</option>
            {Object.entries(FORMA_PAGAMENTO_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        </Field>
        <Field label="Comprovante (opcional)">
          <input type="file" accept="application/pdf,image/*" onChange={(e) => setComprovante(e.target.files?.[0] ?? null)} />
        </Field>
        {erro && <p className={styles.erro}>{erro}</p>}
      </div>
    </Modal>
  )
}

// ─── Modal: Categoria ───────────────────────────────────────────────────────────

function ModalCategoria({ categoria, onClose, onSaved }) {
  const [nome, setNome] = useState(categoria?.nome ?? '')
  const [tipo, setTipo] = useState(categoria?.tipo ?? 'saida')
  const [ativo, setAtivo] = useState(categoria?.ativo ?? true)
  const [saving, setSaving] = useState(false)
  const [erro, setErro] = useState('')

  const handleSalvar = async () => {
    if (!nome.trim()) { setErro('Informe o nome da categoria.'); return }
    setSaving(true); setErro('')
    try {
      if (categoria) await financeiroApi.categorias.update(categoria.id, { nome, tipo, ativo })
      else await financeiroApi.categorias.create({ nome, tipo })
      onSaved()
    } catch (e) {
      const d = e?.response?.data
      setErro(typeof d === 'string' ? d : d?.detail || JSON.stringify(d) || 'Erro ao salvar categoria.')
    } finally { setSaving(false) }
  }

  return (
    <Modal
      open title={categoria ? 'Editar Categoria' : 'Nova Categoria'} onClose={onClose} width={380}
      footer={<><Btn variant="ghost" onClick={onClose}>Cancelar</Btn><Btn onClick={handleSalvar} loading={saving}>Salvar</Btn></>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Field label="Nome">
          <Input type="text" placeholder="Ex: Fornecedores, Aluguel, Vendas" value={nome} onChange={(e) => setNome(e.target.value)} />
        </Field>
        <div className={styles.radioRow}>
          <button className={`${styles.radioChip} ${tipo === 'entrada' ? styles.radioChipSel : ''}`} onClick={() => setTipo('entrada')}>Entrada</button>
          <button className={`${styles.radioChip} ${tipo === 'saida' ? styles.radioChipSel : ''}`} onClick={() => setTipo('saida')}>Saída</button>
        </div>
        {categoria && (
          <label className={styles.toggleRow} style={{ borderTop: 'none' }}>
            <div className={styles.toggleLbl}>Ativa</div>
            <input type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} />
          </label>
        )}
        {erro && <p className={styles.erro}>{erro}</p>}
      </div>
    </Modal>
  )
}

// ─── Modal: Conta Bancária ──────────────────────────────────────────────────────

function ModalContaBancaria({ conta, empresaId, empresaNome, onClose, onSaved }) {
  const [nome, setNome] = useState(conta?.nome ?? '')
  const [tipo, setTipo] = useState(conta?.tipo ?? 'banco')
  const [ativo, setAtivo] = useState(conta?.ativo ?? true)
  const [saving, setSaving] = useState(false)
  const [erro, setErro] = useState('')

  const handleSalvar = async () => {
    if (!nome.trim()) { setErro('Informe o nome da conta.'); return }
    setSaving(true); setErro('')
    try {
      if (conta) await financeiroApi.contasBancarias.update(conta.id, { nome, tipo, ativo })
      else await financeiroApi.contasBancarias.create({ nome, tipo }, empresaId)
      onSaved()
    } catch (e) {
      const d = e?.response?.data
      setErro(typeof d === 'string' ? d : d?.detail || JSON.stringify(d) || 'Erro ao salvar conta bancária.')
    } finally { setSaving(false) }
  }

  return (
    <Modal
      open title={conta ? 'Editar Conta Bancária' : 'Nova Conta Bancária'} onClose={onClose} width={380}
      footer={<><Btn variant="ghost" onClick={onClose}>Cancelar</Btn><Btn onClick={handleSalvar} loading={saving}>Salvar</Btn></>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Field label="Nome">
          <Input type="text" placeholder="Ex: Nubank, Caixa da loja" value={nome} onChange={(e) => setNome(e.target.value)} />
        </Field>
        <div className={styles.radioRow}>
          <button className={`${styles.radioChip} ${tipo === 'banco' ? styles.radioChipSel : ''}`} onClick={() => setTipo('banco')}>Banco</button>
          <button className={`${styles.radioChip} ${tipo === 'caixa' ? styles.radioChipSel : ''}`} onClick={() => setTipo('caixa')}>Caixa</button>
        </div>
        {conta ? (
          <>
            <p className={styles.hintSmall}>Saldo atual: {fmt(conta.saldo_atual)} (só muda via movimentos do ledger)</p>
            <label className={styles.toggleRow} style={{ borderTop: 'none' }}>
              <div className={styles.toggleLbl}>Ativa</div>
              <input type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} />
            </label>
          </>
        ) : empresaNome && (
          <p className={styles.hintSmall}>Será criada para a empresa <strong>{empresaNome}</strong>.</p>
        )}
        {erro && <p className={styles.erro}>{erro}</p>}
      </div>
    </Modal>
  )
}

// ─── Modal: Fornecedor ──────────────────────────────────────────────────────────

function ModalFornecedor({ fornecedor, onClose, onSaved }) {
  const [nome, setNome] = useState(fornecedor?.nome ?? '')
  const [cnpj, setCnpj] = useState(fornecedor?.cnpj ?? '')
  const [telefone, setTelefone] = useState(fornecedor?.telefone ?? '')
  const [email, setEmail] = useState(fornecedor?.email ?? '')
  const [saving, setSaving] = useState(false)
  const [erro, setErro] = useState('')

  const handleSalvar = async () => {
    if (!nome.trim()) { setErro('Informe o nome do fornecedor.'); return }
    setSaving(true); setErro('')
    try {
      if (fornecedor) await financeiroApi.fornecedores.update(fornecedor.id, { nome, cnpj, telefone, email })
      else await financeiroApi.fornecedores.create({ nome, cnpj, telefone, email })
      onSaved()
    } catch (e) {
      const d = e?.response?.data
      setErro(typeof d === 'string' ? d : d?.detail || JSON.stringify(d) || 'Erro ao salvar fornecedor.')
    } finally { setSaving(false) }
  }

  return (
    <Modal
      open title={fornecedor ? 'Editar Fornecedor' : 'Novo Fornecedor'} onClose={onClose} width={400}
      footer={<><Btn variant="ghost" onClick={onClose}>Cancelar</Btn><Btn onClick={handleSalvar} loading={saving}>Salvar</Btn></>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Field label="Nome">
          <Input type="text" value={nome} onChange={(e) => setNome(e.target.value)} />
        </Field>
        <Field label="CNPJ (opcional)">
          <Input type="text" placeholder="00.000.000/0000-00" value={cnpj} onChange={(e) => setCnpj(e.target.value)} />
        </Field>
        <Field label="Telefone (opcional)">
          <Input type="text" value={telefone} onChange={(e) => setTelefone(e.target.value)} />
        </Field>
        <Field label="E-mail (opcional)">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        {erro && <p className={styles.erro}>{erro}</p>}
      </div>
    </Modal>
  )
}
