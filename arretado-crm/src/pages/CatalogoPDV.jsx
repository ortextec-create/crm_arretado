import { useState, useEffect, useCallback } from 'react'
import styles from './CatalogoPDV.module.css'
import { pdvApi } from '../api/services'

// ─── Helpers ─────────────────────────────────────────────────────────────────

const fmtMoeda = v => `R$ ${Number(v || 0).toFixed(2)}`

function Toast({ toast, onClose }) {
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(onClose, 3500)
    return () => clearTimeout(t)
  }, [toast, onClose])
  if (!toast) return null
  return (
    <div className={`${styles.toast} ${toast.type === 'error' ? styles.toastError : styles.toastSuccess}`}>
      <i className={`ti ti-${toast.type === 'error' ? 'alert-circle' : 'check'}`} />
      {toast.message}
    </div>
  )
}

// ─── Modal genérico de confirmação ───────────────────────────────────────────

function ModalConfirm({ msg, onConfirm, onCancel }) {
  return (
    <div className={styles.overlay} onClick={e => e.target === e.currentTarget && onCancel()}>
      <div className={styles.modalConfirm}>
        <i className="ti ti-alert-triangle" style={{ fontSize: 32, color: '#F59E0B' }} />
        <p>{msg}</p>
        <div className={styles.confirmBtns}>
          <button className={styles.btnGhost} onClick={onCancel}>Cancelar</button>
          <button className={styles.btnDanger} onClick={onConfirm}>Confirmar</button>
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// ABA CATEGORIAS
// ─────────────────────────────────────────────────────────────────────────────

function AbaCategorias({ showToast }) {
  const [categorias, setCategorias] = useState([])
  const [loading,    setLoading]    = useState(true)
  const [form,       setForm]       = useState({ nome: '', ordem: 0 })
  const [editando,   setEditando]   = useState(null)   // id em edição
  const [saving,     setSaving]     = useState(false)
  const [confirm,    setConfirm]    = useState(null)   // { id, nome }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await pdvApi.listCategorias()
      setCategorias(r.data.results ?? r.data)
    } catch { showToast('Erro ao carregar categorias.', 'error') }
    finally { setLoading(false) }
  }, [showToast])

  useEffect(() => { load() }, [load])

  const abrirNovo = () => {
    setEditando('novo')
    setForm({ nome: '', ordem: categorias.length })
  }

  const abrirEditar = (cat) => {
    setEditando(cat.id)
    setForm({ nome: cat.nome, ordem: cat.ordem })
  }

  const cancelar = () => { setEditando(null); setForm({ nome: '', ordem: 0 }) }

  const salvar = async () => {
    if (!form.nome.trim()) { showToast('Informe o nome da categoria.', 'error'); return }
    setSaving(true)
    try {
      if (editando === 'novo') {
        await pdvApi.criarCategoria(form)
        showToast('Categoria criada!', 'success')
      } else {
        await pdvApi.editarCategoria(editando, form)
        showToast('Categoria atualizada!', 'success')
      }
      cancelar()
      load()
    } catch { showToast('Erro ao salvar categoria.', 'error') }
    finally { setSaving(false) }
  }

  const deletar = async (id) => {
    try {
      await pdvApi.deletarCategoria(id)
      showToast('Categoria removida.', 'success')
      setConfirm(null)
      load()
    } catch { showToast('Erro ao remover. Verifique se há produtos vinculados.', 'error'); setConfirm(null) }
  }

  return (
    <div className={styles.abaContent}>
      {confirm && (
        <ModalConfirm
          msg={`Remover a categoria "${confirm.nome}"? Produtos vinculados ficarão sem categoria.`}
          onConfirm={() => deletar(confirm.id)}
          onCancel={() => setConfirm(null)}
        />
      )}

      {/* Cabeçalho */}
      <div className={styles.abaHeader}>
        <div>
          <h2 className={styles.abaTitle}>Categorias</h2>
          <p className={styles.abaSub}>Organize os produtos por tipo. A ordem define como aparecem no catálogo do PDV.</p>
        </div>
        <button className={styles.btnPrimary} onClick={abrirNovo}>
          <i className="ti ti-plus" /> Nova Categoria
        </button>
      </div>

      {/* Form inline de criação/edição */}
      {editando && (
        <div className={styles.formInline}>
          <div className={styles.formInlineTitle}>
            {editando === 'novo' ? 'Nova categoria' : 'Editar categoria'}
          </div>
          <div className={styles.formInlineRow}>
            <div className={styles.fieldGroup}>
              <label>Nome *</label>
              <input
                autoFocus
                placeholder="Ex: Bolos, Brigadeiros, Bebidas…"
                value={form.nome}
                onChange={e => setForm(f => ({ ...f, nome: e.target.value }))}
                onKeyDown={e => e.key === 'Enter' && salvar()}
              />
            </div>
            <div className={styles.fieldGroup} style={{ maxWidth: 100 }}>
              <label>Ordem</label>
              <input
                type="number" min={0}
                value={form.ordem}
                onChange={e => setForm(f => ({ ...f, ordem: Number(e.target.value) }))}
              />
            </div>
            <div className={styles.formInlineAcoes}>
              <button className={styles.btnPrimary} onClick={salvar} disabled={saving}>
                {saving ? <i className="ti ti-loader-2 spin" /> : <i className="ti ti-check" />}
                {saving ? 'Salvando…' : 'Salvar'}
              </button>
              <button className={styles.btnGhost} onClick={cancelar}>Cancelar</button>
            </div>
          </div>
        </div>
      )}

      {/* Lista */}
      {loading ? (
        <div className={styles.center}><i className="ti ti-loader-2 spin" style={{ fontSize: 24, color: 'var(--caramelo)' }} /></div>
      ) : categorias.length === 0 ? (
        <div className={styles.empty}>
          <i className="ti ti-folder-off" />
          <p>Nenhuma categoria cadastrada.</p>
          <button className={styles.btnPrimary} onClick={abrirNovo}><i className="ti ti-plus" /> Criar primeira</button>
        </div>
      ) : (
        <div className={styles.catList}>
          <div className={styles.catListHeader}>
            <span>Ordem</span>
            <span>Nome</span>
            <span style={{ textAlign: 'right' }}>Ações</span>
          </div>
          {categorias.map(cat => (
            <div key={cat.id} className={`${styles.catRow} ${editando === cat.id ? styles.catRowEditing : ''}`}>
              <span className={styles.catOrdem}>{cat.ordem}</span>
              <span className={styles.catNome}>{cat.nome}</span>
              <div className={styles.catAcoes}>
                <button className={styles.actBtn} title="Editar" onClick={() => abrirEditar(cat)}>
                  <i className="ti ti-pencil" />
                </button>
                <button className={styles.actBtnDanger} title="Remover" onClick={() => setConfirm({ id: cat.id, nome: cat.nome })}>
                  <i className="ti ti-trash" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// MODAL PRODUTO (criação e edição)
// ─────────────────────────────────────────────────────────────────────────────

function ModalProduto({ produto, categorias, onClose, onSaved, showToast }) {
  const isNovo = !produto
  const [form, setForm] = useState({
    nome:      produto?.nome      ?? '',
    descricao: produto?.descricao ?? '',
    preco:     produto?.preco     ?? '',
    categoria: produto?.categoria ?? '',
    ativo:     produto?.ativo     ?? true,
  })
  const [saving, setSaving] = useState(false)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const salvar = async () => {
    if (!form.nome.trim())  { showToast('Informe o nome do produto.', 'error'); return }
    if (!form.preco || isNaN(Number(form.preco)) || Number(form.preco) <= 0) {
      showToast('Informe um preço válido.', 'error'); return
    }
    setSaving(true)
    try {
      const payload = {
        ...form,
        preco:     Number(form.preco),
        categoria: form.categoria || null,
      }
      if (isNovo) {
        await pdvApi.criarProduto(payload)
        showToast('Produto criado!', 'success')
      } else {
        await pdvApi.editarProduto(produto.id, payload)
        showToast('Produto atualizado!', 'success')
      }
      onSaved()
      onClose()
    } catch { showToast('Erro ao salvar produto.', 'error') }
    finally { setSaving(false) }
  }

  return (
    <div className={styles.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className={styles.modalProduto}>
        <div className={styles.modalHeader}>
          <span className={styles.modalTitle}>
            <i className={`ti ti-${isNovo ? 'package' : 'pencil'}`} />
            {isNovo ? 'Novo Produto' : `Editar: ${produto.nome}`}
          </span>
          <button className={styles.closeBtn} onClick={onClose}><i className="ti ti-x" /></button>
        </div>

        <div className={styles.modalBody}>
          <div className={styles.fieldGroup}>
            <label>Nome *</label>
            <input
              autoFocus
              placeholder="Ex: Bolo de Cenoura com Brigadeiro"
              value={form.nome}
              onChange={e => set('nome', e.target.value)}
            />
          </div>

          <div className={styles.fieldRow}>
            <div className={styles.fieldGroup}>
              <label>Preço (R$) *</label>
              <input
                type="number" min="0" step="0.01"
                placeholder="0,00"
                value={form.preco}
                onChange={e => set('preco', e.target.value)}
              />
            </div>
            <div className={styles.fieldGroup}>
              <label>Categoria</label>
              <select value={form.categoria} onChange={e => set('categoria', e.target.value)}>
                <option value="">Sem categoria</option>
                {categorias.map(c => (
                  <option key={c.id} value={c.id}>{c.nome}</option>
                ))}
              </select>
            </div>
          </div>

          <div className={styles.fieldGroup}>
            <label>Descrição</label>
            <textarea
              rows={3}
              placeholder="Ingredientes, tamanho, sabores disponíveis…"
              value={form.descricao}
              onChange={e => set('descricao', e.target.value)}
            />
          </div>

          <div className={styles.fieldGroupInline}>
            <label>Produto ativo</label>
            <button
              className={`${styles.toggle} ${form.ativo ? styles.toggleOn : ''}`}
              onClick={() => set('ativo', !form.ativo)}
            >
              <span className={styles.toggleThumb} />
            </button>
            <span className={styles.toggleLabel}>{form.ativo ? 'Visível no PDV' : 'Oculto no PDV'}</span>
          </div>
        </div>

        <div className={styles.modalFooter}>
          <button className={styles.btnGhost} onClick={onClose}>Cancelar</button>
          <button className={styles.btnPrimary} onClick={salvar} disabled={saving}>
            {saving ? <i className="ti ti-loader-2 spin" /> : <i className="ti ti-device-floppy" />}
            {saving ? 'Salvando…' : 'Salvar Produto'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// ABA PRODUTOS
// ─────────────────────────────────────────────────────────────────────────────

function AbaProdutos({ showToast }) {
  const [produtos,   setProdutos]   = useState([])
  const [categorias, setCategorias] = useState([])
  const [loading,    setLoading]    = useState(true)
  const [search,     setSearch]     = useState('')
  const [catFilter,  setCatFilter]  = useState('')
  const [ativoFilter,setAtivoFilter]= useState('todos')
  const [modalProd,  setModalProd]  = useState(null)   // null | 'novo' | produto object
  const [confirm,    setConfirm]    = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [prods, cats] = await Promise.all([
        pdvApi.listProdutos({ page_size: 300 }),
        pdvApi.listCategorias(),
      ])
      setProdutos(prods.data.results ?? prods.data)
      setCategorias(cats.data.results ?? cats.data)
    } catch { showToast('Erro ao carregar produtos.', 'error') }
    finally { setLoading(false) }
  }, [showToast])

  useEffect(() => { load() }, [load])

  const toggleAtivo = async (prod) => {
    try {
      if (prod.ativo) {
        await pdvApi.desativarProduto(prod.id)
        showToast(`"${prod.nome}" desativado.`, 'success')
      } else {
        await pdvApi.ativarProduto(prod.id)
        showToast(`"${prod.nome}" ativado.`, 'success')
      }
      load()
    } catch { showToast('Erro ao alterar status.', 'error') }
  }

  const deletar = async (id) => {
    try {
      await pdvApi.deletarProduto(id)
      showToast('Produto removido.', 'success')
      setConfirm(null)
      load()
    } catch { showToast('Erro ao remover produto.', 'error'); setConfirm(null) }
  }

  // Filtros client-side
  const prodsFiltrados = produtos.filter(p => {
    const matchSearch = !search || p.nome.toLowerCase().includes(search.toLowerCase()) || p.descricao?.toLowerCase().includes(search.toLowerCase())
    const matchCat    = !catFilter || String(p.categoria) === String(catFilter)
    const matchAtivo  = ativoFilter === 'todos' || (ativoFilter === 'ativo' ? p.ativo : !p.ativo)
    return matchSearch && matchCat && matchAtivo
  })

  const catNome = (id) => categorias.find(c => c.id === id)?.nome ?? '—'

  return (
    <div className={styles.abaContent}>
      {confirm && (
        <ModalConfirm
          msg={`Remover o produto "${confirm.nome}"? Esta ação não pode ser desfeita.`}
          onConfirm={() => deletar(confirm.id)}
          onCancel={() => setConfirm(null)}
        />
      )}

      {(modalProd === 'novo' || (modalProd && typeof modalProd === 'object')) && (
        <ModalProduto
          produto={modalProd === 'novo' ? null : modalProd}
          categorias={categorias}
          onClose={() => setModalProd(null)}
          onSaved={load}
          showToast={showToast}
        />
      )}

      {/* Cabeçalho */}
      <div className={styles.abaHeader}>
        <div>
          <h2 className={styles.abaTitle}>Produtos</h2>
          <p className={styles.abaSub}>{produtos.length} produto{produtos.length !== 1 ? 's' : ''} cadastrado{produtos.length !== 1 ? 's' : ''} · {produtos.filter(p => p.ativo).length} ativo{produtos.filter(p => p.ativo).length !== 1 ? 's' : ''}</p>
        </div>
        <button className={styles.btnPrimary} onClick={() => setModalProd('novo')}>
          <i className="ti ti-plus" /> Novo Produto
        </button>
      </div>

      {/* Filtros */}
      <div className={styles.filtrosRow}>
        <div className={styles.searchBox}>
          <i className="ti ti-search" />
          <input
            placeholder="Buscar produto…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <button className={styles.clearSearch} onClick={() => setSearch('')}>
              <i className="ti ti-x" />
            </button>
          )}
        </div>

        <select
          className={styles.filterSelect}
          value={catFilter}
          onChange={e => setCatFilter(e.target.value)}
        >
          <option value="">Todas as categorias</option>
          {categorias.map(c => <option key={c.id} value={c.id}>{c.nome}</option>)}
        </select>

        <div className={styles.ativoTabs}>
          {['todos', 'ativo', 'inativo'].map(v => (
            <button
              key={v}
              className={`${styles.ativoTab} ${ativoFilter === v ? styles.ativoTabActive : ''}`}
              onClick={() => setAtivoFilter(v)}
            >
              {v === 'todos' ? 'Todos' : v === 'ativo' ? 'Ativos' : 'Inativos'}
            </button>
          ))}
        </div>
      </div>

      {/* Grid de produtos */}
      {loading ? (
        <div className={styles.center}><i className="ti ti-loader-2 spin" style={{ fontSize: 24, color: 'var(--caramelo)' }} /></div>
      ) : prodsFiltrados.length === 0 ? (
        <div className={styles.empty}>
          <i className="ti ti-package-off" />
          <p>{search || catFilter ? 'Nenhum produto encontrado com esses filtros.' : 'Nenhum produto cadastrado.'}</p>
          {!search && !catFilter && (
            <button className={styles.btnPrimary} onClick={() => setModalProd('novo')}>
              <i className="ti ti-plus" /> Criar primeiro produto
            </button>
          )}
        </div>
      ) : (
        <div className={styles.prodGrid}>
          {prodsFiltrados.map(prod => (
            <div key={prod.id} className={`${styles.prodCard} ${!prod.ativo ? styles.prodCardInativo : ''}`}>
              {/* Badge ativo/inativo */}
              <div className={styles.prodBadgeRow}>
                <span className={`${styles.prodBadge} ${prod.ativo ? styles.prodBadgeAtivo : styles.prodBadgeInativo}`}>
                  <i className={`ti ti-${prod.ativo ? 'check' : 'eye-off'}`} />
                  {prod.ativo ? 'Ativo' : 'Inativo'}
                </span>
                {prod.categoria_nome && (
                  <span className={styles.prodCategoria}>{prod.categoria_nome}</span>
                )}
              </div>

              {/* Info */}
              <p className={styles.prodNome}>{prod.nome}</p>
              {prod.descricao && (
                <p className={styles.prodDesc}>{prod.descricao}</p>
              )}
              <p className={styles.prodPreco}>{fmtMoeda(prod.preco)}</p>

              {/* Ações */}
              <div className={styles.prodAcoes}>
                <button
                  className={`${styles.prodBtn} ${prod.ativo ? styles.prodBtnDesativar : styles.prodBtnAtivar}`}
                  onClick={() => toggleAtivo(prod)}
                  title={prod.ativo ? 'Desativar' : 'Ativar'}
                >
                  <i className={`ti ti-${prod.ativo ? 'eye-off' : 'eye'}`} />
                  {prod.ativo ? 'Desativar' : 'Ativar'}
                </button>
                <button
                  className={`${styles.prodBtn} ${styles.prodBtnEditar}`}
                  onClick={() => setModalProd(prod)}
                  title="Editar"
                >
                  <i className="ti ti-pencil" /> Editar
                </button>
                <button
                  className={`${styles.prodBtn} ${styles.prodBtnDel}`}
                  onClick={() => setConfirm({ id: prod.id, nome: prod.nome })}
                  title="Remover"
                >
                  <i className="ti ti-trash" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// PÁGINA PRINCIPAL
// ─────────────────────────────────────────────────────────────────────────────

export default function CatalogoPDV() {
  const [aba,   setAba]   = useState('produtos')
  const [toast, setToast] = useState(null)

  const showToast = (message, type = 'success') => setToast({ message, type })

  return (
    <div className={styles.page}>
      <Toast toast={toast} onClose={() => setToast(null)} />

      {/* Topbar */}
      <div className={styles.topbar}>
        <div className={styles.topbarLeft}>
          <h1 className={styles.topbarTitle}>
            <i className="ti ti-building-store" />
            PDV Próprio
            <span className={styles.breadSep}>/</span>
            <span className={styles.breadAtual}>Catálogo</span>
          </h1>
        </div>
      </div>

      {/* Abas */}
      <div className={styles.tabsBar}>
        <button
          className={`${styles.tab} ${aba === 'produtos' ? styles.tabActive : ''}`}
          onClick={() => setAba('produtos')}
        >
          <i className="ti ti-package" /> Produtos
        </button>
        <button
          className={`${styles.tab} ${aba === 'categorias' ? styles.tabActive : ''}`}
          onClick={() => setAba('categorias')}
        >
          <i className="ti ti-folder" /> Categorias
        </button>
      </div>

      {/* Conteúdo da aba */}
      <div className={styles.abaWrapper}>
        {aba === 'produtos'   && <AbaProdutos   showToast={showToast} />}
        {aba === 'categorias' && <AbaCategorias showToast={showToast} />}
      </div>
    </div>
  )
}
