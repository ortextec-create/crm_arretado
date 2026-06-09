import { useState, useEffect, useCallback } from 'react'
import { fichasApi } from '../api/services'
import { Btn, Spinner, Toast } from '../components/ui'
import styles from './FichasTecnicas.module.css'

const fmt    = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const fmtPct = (v) => v != null ? `${(Number(v) * 100).toFixed(1)}%` : '—'

function semaforoClass(margem) {
  if (margem == null) return ''
  const pct = Number(margem) * 100
  if (pct >= 30) return styles.statusVerde
  if (pct >= 15) return styles.statusAmarelo
  return styles.statusVermelho
}

export default function FichasTecnicas() {
  const [fichas,   setFichas]   = useState([])
  const [search,   setSearch]   = useState('')
  const [selId,    setSelId]    = useState(null)
  const [detalhe,  setDetalhe]  = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [loadDet,  setLoadDet]  = useState(false)
  const [toast,    setToast]    = useState(null)
  const [materias, setMaterias] = useState([])

  // Add item form
  const [addMode,  setAddMode]  = useState(false)
  const [selMat,   setSelMat]   = useState('')
  const [qty,      setQty]      = useState('')
  const [adding,   setAdding]   = useState(false)

  useEffect(() => {
    fichasApi.listarMaterias({ page_size: 300 }).then(r => setMaterias(r.data.results ?? r.data)).catch(() => {})
  }, [])

  const loadLista = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fichasApi.listarFichas({ search, page_size: 200 })
      setFichas(res.data.results ?? res.data)
    } finally { setLoading(false) }
  }, [search])

  useEffect(() => { loadLista() }, [loadLista])

  async function selectFicha(id) {
    setSelId(id)
    setLoadDet(true)
    setAddMode(false)
    try {
      const res = await fichasApi.detalharFicha(id)
      setDetalhe(res.data)
    } finally { setLoadDet(false) }
  }

  async function handleRemoverItem(itemId) {
    try {
      const res = await fichasApi.removerItemFicha(detalhe.id, itemId)
      setDetalhe(res.data)
      loadLista()
    } catch { showToast('Erro ao remover ingrediente.', 'error') }
  }

  async function handleAdicionarItem() {
    if (!selMat || !qty) return
    setAdding(true)
    try {
      const res = await fichasApi.adicionarItemFicha(detalhe.id, { materia_prima: selMat, quantidade: qty })
      setDetalhe(res.data)
      setSelMat('')
      setQty('')
      setAddMode(false)
      loadLista()
    } catch (e) {
      showToast(e?.response?.data?.detail || 'Erro ao adicionar.', 'error')
    } finally { setAdding(false) }
  }

  function showToast(msg, tipo = 'success') { setToast({ msg, tipo }) }

  const margem  = detalhe?.margem_bruta_pct
  const markup  = detalhe && detalhe.custo_total_unitario
    ? (detalhe.produto_preco / detalhe.custo_total_unitario).toFixed(2)
    : null

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={`serif ${styles.title}`}>Fichas Técnicas</h1>
          <p className={styles.subtitle}>Composição de ingredientes e custo por produto</p>
        </div>
      </div>

      <div className={styles.layout}>
        {/* Lista */}
        <div className={styles.lista}>
          <div className={styles.listaSearch}>
            <i className="ti ti-search" />
            <input
              placeholder="Buscar ficha…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          {loading ? <div className={styles.center}><Spinner /></div> : (
            <div className={styles.listaItens}>
              {fichas.map(f => (
                <button
                  key={f.id}
                  className={`${styles.listaItem} ${selId === f.id ? styles.listaItemActive : ''}`}
                  onClick={() => selectFicha(f.id)}
                >
                  <div className={styles.listaItemNome}>{f.nome}</div>
                  <div className={styles.listaItemInfo}>
                    {f.produto_nome && <span>{f.produto_preco != null ? fmt(f.produto_preco) : ''}</span>}
                    {f.margem_bruta_pct != null && (
                      <span className={semaforoClass(f.margem_bruta_pct)}>
                        {fmtPct(f.margem_bruta_pct)}
                      </span>
                    )}
                  </div>
                </button>
              ))}
              {fichas.length === 0 && <p className={styles.empty}>Nenhuma ficha encontrada.</p>}
            </div>
          )}
        </div>

        {/* Detalhe */}
        <div className={styles.detalhe}>
          {!selId ? (
            <div className={styles.detalheVazio}>
              <i className="ti ti-flask" />
              <p>Selecione uma ficha para ver os detalhes</p>
            </div>
          ) : loadDet ? (
            <div className={styles.center}><Spinner /></div>
          ) : detalhe ? (
            <div className={styles.detalheInner}>
              {/* Header da ficha */}
              <div className={styles.detHeaderRow}>
                <div>
                  <h2 className={`serif ${styles.detNome}`}>{detalhe.nome}</h2>
                  {detalhe.produto_nome && (
                    <p className={styles.detProduto}>Produto: <strong>{detalhe.produto_nome}</strong></p>
                  )}
                </div>
                {margem != null && (
                  <span className={`${styles.margemBadge} ${semaforoClass(margem)}`}>
                    {fmtPct(margem)} margem
                  </span>
                )}
              </div>

              <div className={styles.detMeta}>
                <span><i className="ti ti-refresh" /> Rendimento: <strong>{detalhe.rendimento} un.</strong></span>
                <span><i className="ti ti-package" /> Embalagem: <strong>{fmt(detalhe.embalagem_custo)}</strong></span>
              </div>

              {/* Tabela de ingredientes */}
              <table className={styles.iTable}>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Ingrediente</th>
                    <th className={styles.thRight}>Qtd</th>
                    <th className={styles.thRight}>Custo/un</th>
                    <th className={styles.thRight}>Custo</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {detalhe.itens.map((item, i) => (
                    <tr key={item.id}>
                      <td className={styles.tdIdx}>{i + 1}</td>
                      <td>{item.materia_prima_nome}</td>
                      <td className={styles.thRight}>
                        {Number(item.quantidade).toLocaleString('pt-BR')}{item.materia_prima_unidade}
                      </td>
                      <td className={styles.thRight}>
                        {fmt(fichasApi._custo && 0)} —
                      </td>
                      <td className={`${styles.thRight} ${styles.tdCusto}`}>{fmt(item.custo_proporcional)}</td>
                      <td>
                        <button className={styles.btnRemove} onClick={() => handleRemoverItem(item.id)}>
                          <i className="ti ti-trash" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Totais */}
              <div className={styles.totaisBox}>
                <div className={styles.totaisRow}>
                  <span>Custo ingredientes:</span>
                  <span>{fmt(detalhe.custo_ingredientes)}</span>
                </div>
                <div className={styles.totaisRow}>
                  <span>+ Embalagem:</span>
                  <span>{fmt(detalhe.embalagem_custo)}</span>
                </div>
                <div className={`${styles.totaisRow} ${styles.totaisSep}`}>
                  <span>= Custo total / un:</span>
                  <strong>{fmt(detalhe.custo_total_unitario)}</strong>
                </div>
                <div className={styles.totaisRow}>
                  <span>Preço de venda atual:</span>
                  <span>{detalhe.produto_preco != null ? fmt(detalhe.produto_preco) : '—'}</span>
                </div>
                <div className={`${styles.totaisRow} ${styles.totaisIdeal}`}>
                  <span>Preço ideal {markup ? `(${markup}x)` : ''}:</span>
                  <strong className={styles.precoIdeal}>{fmt(detalhe.preco_ideal)}</strong>
                </div>
                {margem != null && (
                  <div className={`${styles.totaisRow} ${semaforoClass(margem)}`}>
                    <span>Margem atual:</span>
                    <strong>{fmtPct(margem)} {Number(margem)*100 >= 30 ? '🟢' : Number(margem)*100 >= 15 ? '🟡' : '🔴'}</strong>
                  </div>
                )}
              </div>

              {/* Adicionar ingrediente */}
              {!addMode ? (
                <button className={styles.btnAdd} onClick={() => setAddMode(true)}>
                  <i className="ti ti-plus" /> Adicionar ingrediente
                </button>
              ) : (
                <div className={styles.addForm}>
                  <select
                    className={styles.addSelect}
                    value={selMat}
                    onChange={e => setSelMat(e.target.value)}
                  >
                    <option value="">— Selecionar matéria-prima —</option>
                    {materias.map(m => <option key={m.id} value={m.id}>{m.nome} ({fmt(m.custo_unitario)}/{m.unidade_medida})</option>)}
                  </select>
                  <div className={styles.addRow}>
                    <input
                      type="number"
                      placeholder="Quantidade (g / ml / un)"
                      step="0.001"
                      min="0"
                      value={qty}
                      onChange={e => setQty(e.target.value)}
                      className={styles.addQtyInput}
                    />
                    <Btn onClick={handleAdicionarItem} loading={adding} disabled={!selMat || !qty}>
                      <i className="ti ti-plus" /> Adicionar
                    </Btn>
                    <Btn variant="ghost" onClick={() => setAddMode(false)}>Cancelar</Btn>
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>

      {toast && <Toast message={toast.msg} type={toast.tipo} onClose={() => setToast(null)} />}
    </div>
  )
}
