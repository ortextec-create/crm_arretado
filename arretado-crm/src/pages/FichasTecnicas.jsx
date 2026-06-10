import { useState, useEffect, useCallback } from 'react'
import { fichasApi } from '../api/services'
import { Btn, Modal, Spinner, Toast } from '../components/ui'
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
  const [fichas,    setFichas]    = useState([])
  const [search,    setSearch]    = useState('')
  const [selId,     setSelId]     = useState(null)
  const [detalhe,   setDetalhe]   = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [loadDet,   setLoadDet]   = useState(false)
  const [toast,     setToast]     = useState(null)
  const [materias,  setMaterias]  = useState([])
  const [produtos,  setProdutos]  = useState([])

  // Modal nova ficha
  const [showNovaFicha, setShowNovaFicha] = useState(false)

  // Adicionar ingrediente
  const [addMode, setAddMode] = useState(false)
  const [selMat,  setSelMat]  = useState('')
  const [qty,     setQty]     = useState('')
  const [adding,  setAdding]  = useState(false)

  // Editar cabeçalho da ficha (rendimento, embalagem, produto)
  const [editHeader, setEditHeader] = useState(false)
  const [headerForm, setHeaderForm] = useState({})
  const [savingHeader, setSavingHeader] = useState(false)

  useEffect(() => {
    fichasApi.listarMaterias({ page_size: 300 }).then(r => setMaterias(r.data.results ?? r.data)).catch(() => {})
    fichasApi.listarProdutos({ page_size: 300, ativo: 'true' }).then(r => setProdutos(r.data.results ?? r.data)).catch(() => {})
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
    setEditHeader(false)
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
      setSelMat(''); setQty(''); setAddMode(false)
      loadLista()
    } catch (e) {
      showToast(e?.response?.data?.detail || 'Erro ao adicionar.', 'error')
    } finally { setAdding(false) }
  }

  function abrirEditHeader() {
    setHeaderForm({
      nome:           detalhe.nome,
      produto_pdv_id: detalhe.produto_pdv_id ? String(detalhe.produto_pdv_id) : '',
      rendimento:     String(detalhe.rendimento),
      embalagem_custo: String(detalhe.embalagem_custo),
    })
    setEditHeader(true)
  }

  async function handleSalvarHeader() {
    setSavingHeader(true)
    try {
      const res = await fichasApi.atualizarFicha(detalhe.id, {
        nome:            headerForm.nome,
        produto_pdv_id:  headerForm.produto_pdv_id ? Number(headerForm.produto_pdv_id) : null,
        rendimento:      Number(headerForm.rendimento) || 1,
        embalagem_custo: headerForm.embalagem_custo,
      })
      // Recarrega o detalhe completo para atualizar todos os cálculos
      const det = await fichasApi.detalharFicha(detalhe.id)
      setDetalhe(det.data)
      setEditHeader(false)
      loadLista()
      showToast('Ficha atualizada.')
    } catch { showToast('Erro ao salvar.', 'error') }
    finally { setSavingHeader(false) }
  }

  function handleFichaCriada(ficha) {
    setShowNovaFicha(false)
    showToast(`Ficha "${ficha.nome}" criada!`)
    loadLista()
    selectFicha(ficha.id)
  }

  function showToast(msg, tipo = 'success') { setToast({ msg, tipo }) }

  const margem = detalhe?.margem_bruta_pct
  const markup = detalhe && detalhe.custo_total_unitario && detalhe.produto_preco
    ? (Number(detalhe.produto_preco) / Number(detalhe.custo_total_unitario)).toFixed(2)
    : null

  // mapa id → custo_unitario para exibir na coluna
  const materiaById = Object.fromEntries(materias.map(m => [m.id, m]))

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={`serif ${styles.title}`}>Fichas Técnicas</h1>
          <p className={styles.subtitle}>Composição de ingredientes e custo por produto</p>
        </div>
      </div>

      <div className={styles.layout}>
        {/* ── Lista ── */}
        <div className={styles.lista}>
          <div className={styles.listaHeader}>
            <div className={styles.listaSearch}>
              <i className="ti ti-search" />
              <input
                placeholder="Buscar ficha…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
            <button className={styles.btnNovaFicha} onClick={() => setShowNovaFicha(true)} title="Nova ficha técnica">
              <i className="ti ti-plus" />
            </button>
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

        {/* ── Detalhe ── */}
        <div className={styles.detalhe}>
          {!selId ? (
            <div className={styles.detalheVazio}>
              <i className="ti ti-flask" />
              <p>Selecione uma ficha ou crie uma nova</p>
              <button className={styles.btnCriarVazio} onClick={() => setShowNovaFicha(true)}>
                <i className="ti ti-plus" /> Nova ficha técnica
              </button>
            </div>
          ) : loadDet ? (
            <div className={styles.center}><Spinner /></div>
          ) : detalhe ? (
            <div className={styles.detalheInner}>

              {/* ── Cabeçalho ── */}
              {editHeader ? (
                <div className={styles.editHeaderBox}>
                  <div className={styles.editHeaderGrid}>
                    <div className={styles.editField} style={{ gridColumn: '1 / -1' }}>
                      <label>Nome da ficha</label>
                      <input value={headerForm.nome} onChange={e => setHeaderForm(f => ({ ...f, nome: e.target.value }))} />
                    </div>
                    <div className={styles.editField}>
                      <label>Produto PDV vinculado</label>
                      <select value={headerForm.produto_pdv_id} onChange={e => setHeaderForm(f => ({ ...f, produto_pdv_id: e.target.value }))}>
                        <option value="">— Sem vínculo —</option>
                        {produtos.map(p => <option key={p.id} value={p.id}>{p.nome} ({fmt(p.preco)})</option>)}
                      </select>
                    </div>
                    <div className={styles.editField}>
                      <label>Rendimento (unidades)</label>
                      <input type="number" min="1" value={headerForm.rendimento} onChange={e => setHeaderForm(f => ({ ...f, rendimento: e.target.value }))} />
                    </div>
                    <div className={styles.editField}>
                      <label>Custo de embalagem / un (R$)</label>
                      <input type="number" min="0" step="0.01" value={headerForm.embalagem_custo} onChange={e => setHeaderForm(f => ({ ...f, embalagem_custo: e.target.value }))} />
                    </div>
                  </div>
                  <div className={styles.editHeaderActions}>
                    <Btn variant="ghost" onClick={() => setEditHeader(false)}>Cancelar</Btn>
                    <Btn onClick={handleSalvarHeader} loading={savingHeader}>Salvar</Btn>
                  </div>
                </div>
              ) : (
                <div className={styles.detHeaderRow}>
                  <div>
                    <h2 className={`serif ${styles.detNome}`}>{detalhe.nome}</h2>
                    {detalhe.produto_nome
                      ? <p className={styles.detProduto}>Produto: <strong>{detalhe.produto_nome}</strong> · {fmt(detalhe.produto_preco)}</p>
                      : <p className={styles.detProdutoAusente}><i className="ti ti-unlink" /> Sem produto PDV vinculado</p>
                    }
                  </div>
                  <div className={styles.detHeaderRight}>
                    {margem != null && (
                      <span className={`${styles.margemBadge} ${semaforoClass(margem)}`}>
                        {fmtPct(margem)} margem
                      </span>
                    )}
                    <button className={styles.btnEditHeader} onClick={abrirEditHeader} title="Editar dados da ficha">
                      <i className="ti ti-pencil" />
                    </button>
                  </div>
                </div>
              )}

              {/* ── Meta ── */}
              {!editHeader && (
                <div className={styles.detMeta}>
                  <span><i className="ti ti-refresh" /> Rendimento: <strong>{detalhe.rendimento} un.</strong></span>
                  <span><i className="ti ti-package" /> Embalagem: <strong>{fmt(detalhe.embalagem_custo)}/un</strong></span>
                  <span><i className="ti ti-calculator" /> Custo/un: <strong>{fmt(detalhe.custo_total_unitario)}</strong></span>
                </div>
              )}

              {/* ── Tabela de ingredientes ── */}
              {detalhe.itens.length > 0 ? (
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
                    {detalhe.itens.map((item, i) => {
                      const mp = materiaById[item.materia_prima]
                      return (
                        <tr key={item.id}>
                          <td className={styles.tdIdx}>{i + 1}</td>
                          <td>{item.materia_prima_nome}</td>
                          <td className={styles.thRight}>
                            {Number(item.quantidade).toLocaleString('pt-BR')} {item.materia_prima_unidade}
                          </td>
                          <td className={styles.thRight}>
                            {mp ? `${fmt(mp.custo_unitario)}/${mp.unidade_medida}` : '—'}
                          </td>
                          <td className={`${styles.thRight} ${styles.tdCusto}`}>{fmt(item.custo_proporcional)}</td>
                          <td>
                            <button className={styles.btnRemove} onClick={() => handleRemoverItem(item.id)}>
                              <i className="ti ti-trash" />
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              ) : (
                <p className={styles.semIngredientes}>Nenhum ingrediente adicionado ainda.</p>
              )}

              {/* ── Totais ── */}
              <div className={styles.totaisBox}>
                <div className={styles.totaisRow}>
                  <span>Custo ingredientes:</span>
                  <span>{fmt(detalhe.custo_ingredientes)}</span>
                </div>
                <div className={styles.totaisRow}>
                  <span>+ Embalagem ({detalhe.rendimento} un.):</span>
                  <span>{fmt(detalhe.embalagem_custo)}</span>
                </div>
                <div className={`${styles.totaisRow} ${styles.totaisSep}`}>
                  <span>= Custo total / un:</span>
                  <strong>{fmt(detalhe.custo_total_unitario)}</strong>
                </div>
                {detalhe.produto_preco != null && (
                  <div className={styles.totaisRow}>
                    <span>Preço de venda atual:</span>
                    <span>{fmt(detalhe.produto_preco)}</span>
                  </div>
                )}
                <div className={`${styles.totaisRow} ${styles.totaisIdeal}`}>
                  <span>Preço ideal {markup ? `(${markup}x markup)` : ''}:</span>
                  <strong className={styles.precoIdeal}>{fmt(detalhe.preco_ideal)}</strong>
                </div>
                {margem != null && (
                  <div className={`${styles.totaisRow} ${semaforoClass(margem)}`}>
                    <span>Margem atual:</span>
                    <strong>
                      {fmtPct(margem)}&nbsp;
                      {Number(margem) * 100 >= 30 ? '🟢' : Number(margem) * 100 >= 15 ? '🟡' : '🔴'}
                    </strong>
                  </div>
                )}
              </div>

              {/* ── Adicionar ingrediente ── */}
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
                    {materias.map(m => (
                      <option key={m.id} value={m.id}>
                        {m.nome} — {fmt(m.custo_unitario)}/{m.unidade_medida}
                      </option>
                    ))}
                  </select>
                  <div className={styles.addRow}>
                    <input
                      type="number"
                      placeholder={`Quantidade (${materias.find(m => String(m.id) === selMat)?.unidade_medida || 'g/ml/un'})`}
                      step="0.001"
                      min="0"
                      value={qty}
                      onChange={e => setQty(e.target.value)}
                      className={styles.addQtyInput}
                    />
                    <Btn onClick={handleAdicionarItem} loading={adding} disabled={!selMat || !qty}>
                      <i className="ti ti-plus" /> Adicionar
                    </Btn>
                    <Btn variant="ghost" onClick={() => { setAddMode(false); setSelMat(''); setQty('') }}>
                      Cancelar
                    </Btn>
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>

      {/* Modal nova ficha */}
      {showNovaFicha && (
        <ModalNovaFicha
          produtos={produtos}
          onClose={() => setShowNovaFicha(false)}
          onCriada={handleFichaCriada}
        />
      )}

      {toast && <Toast message={toast.msg} type={toast.tipo} onClose={() => setToast(null)} />}
    </div>
  )
}

// ─── Modal nova ficha técnica ─────────────────────────────────────────────────

function ModalNovaFicha({ produtos, onClose, onCriada }) {
  const [form, setForm] = useState({
    nome:            '',
    produto_pdv_id:  '',
    rendimento:      '1',
    embalagem_custo: '0.08',
  })
  const [saving, setSaving] = useState(false)
  const [erro,   setErro]   = useState('')

  function set(f, v) { setForm(prev => ({ ...prev, [f]: v })) }

  // Quando seleciona um produto, pré-preenche o nome com o nome do produto
  function handleProduto(e) {
    const id = e.target.value
    set('produto_pdv_id', id)
    if (id && !form.nome) {
      const p = produtos.find(p => String(p.id) === id)
      if (p) set('nome', p.nome)
    }
  }

  async function handleSalvar() {
    if (!form.nome.trim()) { setErro('Nome é obrigatório.'); return }
    setSaving(true); setErro('')
    try {
      const res = await fichasApi.criarFicha({
        nome:            form.nome.trim(),
        produto_pdv_id:  form.produto_pdv_id ? Number(form.produto_pdv_id) : null,
        rendimento:      Number(form.rendimento) || 1,
        embalagem_custo: form.embalagem_custo || '0.08',
      })
      onCriada(res.data)
    } catch (e) {
      const errs = e?.response?.data
      setErro(errs?.nome?.[0] || typeof errs === 'string' ? errs : JSON.stringify(errs) || 'Erro ao criar.')
    } finally { setSaving(false) }
  }

  return (
    <Modal open title="Nova Ficha Técnica" onClose={onClose}>
      <p className={styles.modalDesc}>
        Crie a ficha e adicione os ingredientes a seguir.
      </p>

      <div className={styles.novaFichaGrid}>
        {/* Nome */}
        <div className={styles.nfField} style={{ gridColumn: '1 / -1' }}>
          <label>Nome da ficha *</label>
          <input
            value={form.nome}
            onChange={e => set('nome', e.target.value)}
            placeholder="Ex: Brigadeiro Tradicional"
            autoFocus
          />
        </div>

        {/* Produto PDV */}
        <div className={styles.nfField} style={{ gridColumn: '1 / -1' }}>
          <label>Vincular a produto do catálogo</label>
          <select value={form.produto_pdv_id} onChange={handleProduto}>
            <option value="">— Sem vínculo —</option>
            {produtos.map(p => (
              <option key={p.id} value={p.id}>{p.nome} — {Number(p.preco).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</option>
            ))}
          </select>
          <span className={styles.nfHint}>Permite calcular margem e comparar com o preço de venda</span>
        </div>

        {/* Rendimento */}
        <div className={styles.nfField}>
          <label>Rendimento</label>
          <div className={styles.nfInputUnit}>
            <input
              type="number"
              min="1"
              step="1"
              value={form.rendimento}
              onChange={e => set('rendimento', e.target.value)}
            />
            <span className={styles.nfUnit}>unidades</span>
          </div>
          <span className={styles.nfHint}>Quantas unidades a receita produz</span>
        </div>

        {/* Embalagem */}
        <div className={styles.nfField}>
          <label>Custo da embalagem / un (R$)</label>
          <input
            type="number"
            min="0"
            step="0.01"
            value={form.embalagem_custo}
            onChange={e => set('embalagem_custo', e.target.value)}
            placeholder="0,08"
          />
          <span className={styles.nfHint}>Saquinho, caixinha, etiqueta, etc.</span>
        </div>
      </div>

      {erro && <p className={styles.nfErro}>{erro}</p>}

      <div className={styles.nfActions}>
        <Btn variant="ghost" onClick={onClose}>Cancelar</Btn>
        <Btn onClick={handleSalvar} loading={saving}>
          <i className="ti ti-flask" /> Criar ficha
        </Btn>
      </div>
    </Modal>
  )
}
