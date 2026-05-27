/**
 * ARQUIVO NOVO: arretado-crm/src/pages/Vinculacoes.jsx — Fase 4
 *
 * Página de associação manual de clientes a pedidos sem vínculo.
 * Segue o design system do projeto: variáveis CSS, Playfair Display, Tabler Icons.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { pedidosApi, clientesApi } from '../api/services'
import styles from './Vinculacoes.module.css'

// ─── Helpers ────────────────────────────────────────────────────────────────

const CANAL_LABEL = { ifood: 'iFood', pdv: 'PDV', anotaai: 'Anota AI' }
const CANAL_COR   = { ifood: '#EA580C', pdv: '#0EA5E9', anotaai: '#7C3AED' }

const STATUS_LABEL = {
  pendente: 'Pendente', confirmado: 'Confirmado', em_preparo: 'Em preparo',
  pronto: 'Pronto', em_entrega: 'Em entrega', concluido: 'Concluído', cancelado: 'Cancelado',
}

function moeda(v) {
  return Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function dataFmt(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

// ─── Componente principal ────────────────────────────────────────────────────

export default function Vinculacoes() {
  const navigate = useNavigate()

  // Estado da listagem
  const [pedidos, setPedidos]     = useState([])
  const [loading, setLoading]     = useState(true)
  const [search, setSearch]       = useState('')
  const [canalFiltro, setCanalFiltro] = useState('')
  const [contagens, setContagens] = useState({ total: 0, por_canal: {} })

  // Estado do modal de vinculação
  const [modalAberto, setModalAberto]         = useState(false)
  const [pedidoSelecionado, setPedidoSelecionado] = useState(null)
  const [buscaCliente, setBuscaCliente]       = useState('')
  const [clientes, setClientes]               = useState([])
  const [clienteSelecionado, setClienteSelecionado] = useState(null)
  const [buscandoClientes, setBuscandoClientes] = useState(false)
  const [salvando, setSalvando]               = useState(false)
  const [erro, setErro]                       = useState('')
  const [sucesso, setSucesso]                 = useState('')

  const debounceRef = useRef(null)

  // ── Carrega pedidos sem vínculo ──────────────────────────────────────────

  const carregar = useCallback(async () => {
    setLoading(true)
    try {
      const params = { sem_cliente: 'true' }
      if (canalFiltro) params.canal = canalFiltro
      if (search)      params.search = search

      const [resPedidos, resContagens] = await Promise.all([
        pedidosApi.listar(params),
        pedidosApi.semCliente(),
      ])

      setPedidos(resPedidos.data.results ?? resPedidos.data)
      setContagens(resContagens.data)
    } catch {
      setErro('Erro ao carregar pedidos.')
    } finally {
      setLoading(false)
    }
  }, [canalFiltro, search])

  useEffect(() => { carregar() }, [carregar])

  // ── Busca de clientes (debounce 350ms) ───────────────────────────────────

  useEffect(() => {
    if (!buscaCliente.trim()) {
      setClientes([])
      return
    }
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      setBuscandoClientes(true)
      try {

        const res = await clientesApi.list({ search: buscaCliente, status: 'ativo' })

        setClientes(res.data.results ?? res.data)
      } catch {
        setClientes([])
      } finally {
        setBuscandoClientes(false)
      }
    }, 350)
  }, [buscaCliente])

  // ── Abrir modal ──────────────────────────────────────────────────────────

  function abrirModal(pedido) {
    setPedidoSelecionado(pedido)
    setBuscaCliente('')
    setClientes([])
    setClienteSelecionado(null)
    setErro('')
    setSucesso('')
    setModalAberto(true)
  }

  function fecharModal() {
    setModalAberto(false)
    setPedidoSelecionado(null)
    setClienteSelecionado(null)
    setBuscaCliente('')
    setClientes([])
  }

  // ── Confirmar vínculo ────────────────────────────────────────────────────

  async function confirmarVinculo() {
    if (!clienteSelecionado || !pedidoSelecionado) return
    setSalvando(true)
    setErro('')
    try {
      await pedidosApi.vincularCliente(pedidoSelecionado.id, clienteSelecionado.id)
      setSucesso(`Pedido vinculado a ${clienteSelecionado.nome} com sucesso!`)
      setTimeout(() => {
        fecharModal()
        carregar()
      }, 1200)
    } catch {
      setErro('Erro ao vincular cliente. Tente novamente.')
    } finally {
      setSalvando(false)
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className={styles.page}>

      {/* Cabeçalho */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.titulo}>
            <i className="ti ti-link" />
            Associação de Clientes
          </h1>
          <p className={styles.subtitulo}>
            Pedidos sem cliente vinculado no CRM — associe manualmente para enriquecer o histórico.
          </p>
        </div>
      </div>

      {/* Cards de contagem por canal */}
      <div className={styles.cards}>
        <div
          className={`${styles.card} ${canalFiltro === '' ? styles.cardAtivo : ''}`}
          onClick={() => setCanalFiltro('')}
        >
          <span className={styles.cardNumero}>{contagens.total}</span>
          <span className={styles.cardLabel}>Todos</span>
        </div>
        {Object.entries(contagens.por_canal || {}).map(([canal, total]) => (
          <div
            key={canal}
            className={`${styles.card} ${canalFiltro === canal ? styles.cardAtivo : ''}`}
            onClick={() => setCanalFiltro(canal === canalFiltro ? '' : canal)}
            style={{ '--canal-cor': CANAL_COR[canal] ?? '#9CA3AF' }}
          >
            <span className={styles.cardNumero} style={{ color: CANAL_COR[canal] }}>{total}</span>
            <span className={styles.cardLabel}>{CANAL_LABEL[canal] ?? canal}</span>
          </div>
        ))}
      </div>

      {/* Barra de busca */}
      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <i className="ti ti-search" />
          <input
            className={styles.searchInput}
            placeholder="Buscar por número, nome ou telefone…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <button className={styles.clearBtn} onClick={() => setSearch('')}>
              <i className="ti ti-x" />
            </button>
          )}
        </div>
      </div>

      {/* Tabela */}
      <div className={styles.tableWrap}>
        {loading ? (
          <div className={styles.empty}>
            <i className="ti ti-loader-2 ti-spin" />
            <span>Carregando pedidos…</span>
          </div>
        ) : pedidos.length === 0 ? (
          <div className={styles.empty}>
            <i className="ti ti-circle-check" style={{ color: 'var(--verde)', fontSize: 32 }} />
            <span>Nenhum pedido sem vínculo encontrado.</span>
          </div>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Canal</th>
                <th>Nº Pedido</th>
                <th>Data</th>
                <th>Cliente (pedido)</th>
                <th>Telefone</th>
                <th>Total</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {pedidos.map(p => (
                <tr key={p.id}>
                  <td>
                    <span
                      className={styles.canalBadge}
                      style={{ background: CANAL_COR[p.canal] ?? '#9CA3AF' }}
                    >
                      {CANAL_LABEL[p.canal] ?? p.canal}
                    </span>
                  </td>
                  <td className={styles.mono}>{p.numero || `#${p.id}`}</td>
                  <td className={styles.muted}>{dataFmt(p.pedido_em)}</td>
                  <td>{p.cliente_nome || <span className={styles.muted}>—</span>}</td>
                  <td className={styles.muted}>{p.cliente_telefone || '—'}</td>
                  <td className={styles.valor}>{moeda(p.total)}</td>
                  <td>
                    <span className={styles.statusBadge}>
                      {STATUS_LABEL[p.status] ?? p.status}
                    </span>
                  </td>
                  <td>
                    <button
                      className={styles.btnVincular}
                      onClick={() => abrirModal(p)}
                      title="Vincular cliente do CRM"
                    >
                      <i className="ti ti-user-plus" />
                      Vincular
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal de vinculação */}
      {modalAberto && pedidoSelecionado && (
        <div className={styles.overlay} onClick={fecharModal}>
          <div className={styles.modal} onClick={e => e.stopPropagation()}>

            {/* Cabeçalho do modal */}
            <div className={styles.modalHeader}>
              <div>
                <h2 className={styles.modalTitulo}>Vincular Cliente</h2>
                <p className={styles.modalSubtitulo}>
                  <span
                    className={styles.canalBadge}
                    style={{ background: CANAL_COR[pedidoSelecionado.canal] }}
                  >
                    {CANAL_LABEL[pedidoSelecionado.canal]}
                  </span>
                  &nbsp; Pedido {pedidoSelecionado.numero || `#${pedidoSelecionado.id}`}
                  &nbsp;·&nbsp; {moeda(pedidoSelecionado.total)}
                </p>
              </div>
              <button className={styles.closeBtn} onClick={fecharModal}>
                <i className="ti ti-x" />
              </button>
            </div>

            {/* Resumo do pedido */}
            <div className={styles.pedidoResumo}>
              <div className={styles.resumoItem}>
                <span className={styles.resumoLabel}>Nome no pedido</span>
                <span>{pedidoSelecionado.cliente_nome || '—'}</span>
              </div>
              <div className={styles.resumoItem}>
                <span className={styles.resumoLabel}>Telefone</span>
                <span>{pedidoSelecionado.cliente_telefone || '—'}</span>
              </div>
              <div className={styles.resumoItem}>
                <span className={styles.resumoLabel}>Data</span>
                <span>{dataFmt(pedidoSelecionado.pedido_em)}</span>
              </div>
              <div className={styles.resumoItem}>
                <span className={styles.resumoLabel}>Status</span>
                <span>{STATUS_LABEL[pedidoSelecionado.status] ?? pedidoSelecionado.status}</span>
              </div>
            </div>

            {/* Busca de cliente */}
            <div className={styles.buscaSection}>
              <label className={styles.buscaLabel}>
                <i className="ti ti-search" /> Buscar cliente no CRM
              </label>
              <div className={styles.searchWrap}>
                <i className="ti ti-search" />
                <input
                  className={styles.searchInput}
                  placeholder="Nome, CPF, e-mail ou telefone…"
                  value={buscaCliente}
                  onChange={e => {
                    setBuscaCliente(e.target.value)
                    setClienteSelecionado(null)
                  }}
                  autoFocus
                />
                {buscandoClientes && <i className="ti ti-loader-2 ti-spin" style={{ marginRight: 8 }} />}
              </div>

              {/* Resultados */}
              {clientes.length > 0 && !clienteSelecionado && (
                <ul className={styles.resultados}>
                  {clientes.map(c => (
                    <li
                      key={c.id}
                      className={styles.resultadoItem}
                      onClick={() => {
                        setClienteSelecionado(c)
                        setBuscaCliente(c.nome)
                        setClientes([])
                      }}
                    >
                      <div className={styles.clienteAvatar}>
                        {c.iniciais || c.nome.slice(0, 2).toUpperCase()}
                      </div>
                      <div className={styles.clienteInfo}>
                        <strong>{c.nome}</strong>
                        <span>{c.telefone_principal || c.email || '—'}</span>
                      </div>
                      <i className="ti ti-chevron-right" style={{ color: 'var(--muted)' }} />
                    </li>
                  ))}
                </ul>
              )}

              {buscaCliente.trim() && clientes.length === 0 && !buscandoClientes && !clienteSelecionado && (
                <div className={styles.semResultado}>
                  Nenhum cliente encontrado.&nbsp;
                  <button
                    className={styles.linkBtn}
                    onClick={() => navigate('/clientes/novo')}
                  >
                    Cadastrar novo cliente
                  </button>
                </div>
              )}
            </div>

            {/* Cliente selecionado */}
            {clienteSelecionado && (
              <div className={styles.clienteSelecionado}>
                <div className={styles.clienteAvatar} style={{ background: 'var(--caramelo)' }}>
                  {clienteSelecionado.iniciais || clienteSelecionado.nome.slice(0, 2).toUpperCase()}
                </div>
                <div className={styles.clienteInfo}>
                  <strong>{clienteSelecionado.nome}</strong>
                  <span>{clienteSelecionado.telefone_principal || clienteSelecionado.email || '—'}</span>
                </div>
                <button
                  className={styles.clearBtn}
                  onClick={() => { setClienteSelecionado(null); setBuscaCliente('') }}
                >
                  <i className="ti ti-x" />
                </button>
              </div>
            )}

            {/* Feedback */}
            {erro    && <div className={styles.alerta}><i className="ti ti-alert-circle" /> {erro}</div>}
            {sucesso && <div className={styles.alertaSucesso}><i className="ti ti-circle-check" /> {sucesso}</div>}

            {/* Ações */}
            <div className={styles.modalFooter}>
              <button className={styles.btnCancelar} onClick={fecharModal} disabled={salvando}>
                Cancelar
              </button>
              <button
                className={styles.btnConfirmar}
                onClick={confirmarVinculo}
                disabled={!clienteSelecionado || salvando}
              >
                {salvando
                  ? <><i className="ti ti-loader-2 ti-spin" /> Salvando…</>
                  : <><i className="ti ti-link" /> Confirmar vínculo</>
                }
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  )
}
