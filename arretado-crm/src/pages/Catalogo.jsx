import { useState, useEffect, useCallback } from 'react'
import { fichasApi, pdvApi } from '../api/services'
import { Btn, Modal, Spinner, Toast } from '../components/ui'
import styles from './Catalogo.module.css'

const fmt    = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const fmtPct = (v) => v != null ? `${(Number(v) * 100).toFixed(1)}%` : '—'

const SEGMENTO_LABELS = {
  unidade_pequena: 'Un. Pequena',
  unidade_media:   'Un. Média',
  bem_casado:      'Bem Casado',
  bolo_encomenda:  'Bolo/Enc.',
  outro:           'Outro',
}

const SEGMENTO_TABS = [
  { key: '',                label: 'Todos' },
  { key: 'unidade_pequena', label: 'Un. Pequena' },
  { key: 'unidade_media',   label: 'Un. Média' },
  { key: 'bem_casado',      label: 'Bem Casado' },
  { key: 'bolo_encomenda',  label: 'Bolos' },
  { key: 'outro',           label: 'Outros' },
]

const SEGMENTO_CORES = {
  unidade_pequena: '#B8730A',
  unidade_media:   '#7C5CBF',
  bem_casado:      '#D4890F',
  bolo_encomenda:  '#4A7C59',
  outro:           '#9CA3AF',
}

function margemClass(margem) {
  if (margem == null) return ''
  const pct = Number(margem) * 100
  if (pct >= 30) return styles.margemVerde
  if (pct >= 15) return styles.margemAmarelo
  return styles.margemVermelho
}

export default function Catalogo() {
  const [produtos,    setProdutos]    = useState([])
  const [fichas,      setFichas]      = useState([])
  const [categorias,  setCategorias]  = useState([])
  const [loading,     setLoading]     = useState(true)
  const [search,      setSearch]      = useState('')
  const [seg,         setSeg]         = useState('')
  const [toast,       setToast]       = useState(null)
  const [editProd,    setEditProd]    = useState(null)   // null | produto | 'novo'
  const [showInativos, setShowInativos] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [rp, rf, rc] = await Promise.all([
        fichasApi.listarProdutos({ page_size: 300 }),
        fichasApi.listarFichas({ page_size: 300 }),
        pdvApi.listCategorias(),
      ])
      setProdutos(rp.data.results ?? rp.data)
      setFichas(rf.data.results ?? rf.data)
      setCategorias(rc.data.results ?? rc.data)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const fichaByProduto = Object.fromEntries(fichas.map(f => [f.produto_pdv_id, f]))

  const produtosFiltrados = produtos.filter(p => {
    const okSearch   = !search || p.nome.toLowerCase().includes(search.toLowerCase())
    const okSeg      = !seg    || p.segmento === seg
    const okAtivo    = showInativos ? true : p.ativo
    return okSearch && okSeg && okAtivo
  })

  function showToast(msg, tipo = 'success') { setToast({ msg, tipo }) }

  function handleSalvo(prod, criado) {
    if (criado) {
      setProdutos(ps => [...ps, prod])
    } else {
      setProdutos(ps => ps.map(p => p.id === prod.id ? prod : p))
    }
    setEditProd(null)
    showToast(criado ? `Produto "${prod.nome}" criado!` : 'Produto atualizado.')
  }

  const totalAtivos = produtos.filter(p => p.ativo).length

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h1 className={`serif ${styles.title}`}>Catálogo</h1>
          <p className={styles.subtitle}>{totalAtivos} produto{totalAtivos !== 1 ? 's' : ''} ativos</p>
        </div>
        <Btn onClick={() => setEditProd('novo')}>
          <i className="ti ti-plus" /> Novo produto
        </Btn>
      </div>

      {/* Filtros */}
      <div className={styles.filters}>
        <div className={styles.tabs}>
          {SEGMENTO_TABS.map(t => (
            <button
              key={t.key}
              className={`${styles.tab} ${seg === t.key ? styles.tabActive : ''}`}
              onClick={() => setSeg(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className={styles.filtersRight}>
          <label className={styles.checkLabel}>
            <input
              type="checkbox"
              checked={showInativos}
              onChange={e => setShowInativos(e.target.checked)}
            />
            Ver inativos
          </label>
          <input
            className={styles.search}
            placeholder="Buscar produto…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Tabela */}
      {loading ? (
        <div className={styles.center}><Spinner /></div>
      ) : produtosFiltrados.length === 0 ? (
        <div className={styles.empty}>
          <i className="ti ti-package-off" />
          <p>Nenhum produto encontrado.</p>
        </div>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Produto</th>
                <th>Segmento</th>
                <th className={styles.thRight}>Preço</th>
                <th className={styles.thRight}>Custo/un</th>
                <th className={styles.thRight}>Margem</th>
                <th className={styles.thCenter}>Canais</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {produtosFiltrados.map(prod => {
                const ficha  = fichaByProduto[prod.id]
                const margem = ficha?.margem_bruta_pct
                const cor    = SEGMENTO_CORES[prod.segmento] || '#9CA3AF'
                return (
                  <tr key={prod.id} className={`${styles.row} ${!prod.ativo ? styles.rowInativo : ''}`}>
                    <td>
                      <div className={styles.prodNome}>
                        <span
                          className={styles.segDot}
                          style={{ background: cor }}
                          title={SEGMENTO_LABELS[prod.segmento]}
                        />
                        <span className={styles.nomeText}>{prod.nome}</span>
                        {!prod.ativo && <span className={styles.badgeInativo}>Inativo</span>}
                      </div>
                    </td>
                    <td>
                      <span className={styles.segBadge} style={{ color: cor, borderColor: cor + '44', background: cor + '14' }}>
                        {SEGMENTO_LABELS[prod.segmento] || '—'}
                      </span>
                    </td>
                    <td className={`${styles.tdRight} ${styles.tdPreco}`}>{fmt(prod.preco)}</td>
                    <td className={styles.tdRight}>
                      {ficha ? fmt(ficha.custo_total_unitario) : <span className={styles.semFicha}>—</span>}
                    </td>
                    <td className={styles.tdRight}>
                      {margem != null ? (
                        <span className={`${styles.margemVal} ${margemClass(margem)}`}>
                          {fmtPct(margem)}
                        </span>
                      ) : <span className={styles.semFicha}>—</span>}
                    </td>
                    <td className={styles.thCenter}>
                      <div className={styles.canaisRow}>
                        <span className={`${styles.canal} ${prod.disponivel_pdv ? styles.canalAtivo : ''}`} title="PDV">
                          <i className="ti ti-building-store" />
                        </span>
                        <span className={`${styles.canal} ${prod.disponivel_ifood ? styles.canalAtivo : ''}`} title="iFood">
                          <i className="ti ti-brand-firebase" />
                        </span>
                        <span className={`${styles.canal} ${prod.disponivel_eventos ? styles.canalAtivo : ''}`} title="Eventos">
                          <i className="ti ti-calendar-event" />
                        </span>
                      </div>
                    </td>
                    <td>
                      <button className={styles.btnEditar} onClick={() => setEditProd(prod)}>
                        <i className="ti ti-pencil" />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal criar/editar */}
      {editProd !== null && (
        <ModalProduto
          prod={editProd === 'novo' ? null : editProd}
          categorias={categorias}
          onClose={() => setEditProd(null)}
          onSalvo={handleSalvo}
        />
      )}

      {toast && <Toast message={toast.msg} type={toast.tipo} onClose={() => setToast(null)} />}
    </div>
  )
}

// ─── Modal criar / editar produto ────────────────────────────────────────────

const SEGMENTO_FULL = [
  ['unidade_pequena', 'Unidade Pequena'],
  ['unidade_media',   'Unidade Média'],
  ['bem_casado',      'Bem Casado'],
  ['bolo_encomenda',  'Bolo / Encomenda'],
  ['outro',           'Outro'],
]

function ModalProduto({ prod, categorias, onClose, onSalvo }) {
  const criando = !prod
  const [form,   setForm]   = useState({
    nome:               prod?.nome               ?? '',
    descricao:          prod?.descricao          ?? '',
    preco:              prod?.preco              ? String(prod.preco) : '',
    segmento:           prod?.segmento           ?? 'outro',
    categoria:          prod?.categoria          ? String(prod.categoria) : '',
    disponivel_pdv:     prod?.disponivel_pdv     ?? true,
    disponivel_ifood:   prod?.disponivel_ifood   ?? false,
    disponivel_eventos: prod?.disponivel_eventos ?? true,
    ativo:              prod?.ativo              ?? true,
  })
  const [saving, setSaving] = useState(false)
  const [erro,   setErro]   = useState('')

  function set(field, val) { setForm(f => ({ ...f, [field]: val })) }

  async function handleSalvar() {
    if (!form.nome.trim()) { setErro('Nome é obrigatório.'); return }
    if (!form.preco || isNaN(Number(form.preco))) { setErro('Preço inválido.'); return }
    setSaving(true); setErro('')
    const payload = {
      nome:               form.nome.trim(),
      descricao:          form.descricao,
      preco:              form.preco,
      segmento:           form.segmento,
      categoria:          form.categoria ? Number(form.categoria) : null,
      disponivel_pdv:     form.disponivel_pdv,
      disponivel_ifood:   form.disponivel_ifood,
      disponivel_eventos: form.disponivel_eventos,
      ativo:              form.ativo,
    }
    try {
      const res = criando
        ? await pdvApi.criarProduto(payload)
        : await fichasApi.atualizarProduto(prod.id, payload)
      onSalvo(res.data, criando)
    } catch (e) {
      const errs = e?.response?.data
      setErro(typeof errs === 'string' ? errs : JSON.stringify(errs) || 'Erro ao salvar.')
    } finally { setSaving(false) }
  }

  return (
    <Modal open title={criando ? 'Novo Produto' : `Editar: ${prod.nome}`} onClose={onClose}>
      <div className={styles.modalGrid}>

        {/* Nome */}
        <div className={styles.fg} style={{ gridColumn: '1 / -1' }}>
          <label>Nome do produto *</label>
          <input
            value={form.nome}
            onChange={e => set('nome', e.target.value)}
            placeholder="Ex: Brigadeiro Tradicional"
            autoFocus
          />
        </div>

        {/* Preço + Segmento */}
        <div className={styles.fg}>
          <label>Preço de venda (R$) *</label>
          <input
            type="number" step="0.01" min="0"
            value={form.preco}
            onChange={e => set('preco', e.target.value)}
            placeholder="0,00"
          />
        </div>
        <div className={styles.fg}>
          <label>Segmento</label>
          <select value={form.segmento} onChange={e => set('segmento', e.target.value)}>
            {SEGMENTO_FULL.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>

        {/* Categoria */}
        <div className={styles.fg}>
          <label>Categoria PDV</label>
          <select value={form.categoria} onChange={e => set('categoria', e.target.value)}>
            <option value="">— Sem categoria —</option>
            {categorias.map(c => <option key={c.id} value={c.id}>{c.nome}</option>)}
          </select>
        </div>

        {/* Ativo */}
        <div className={styles.fg} style={{ display: 'flex', alignItems: 'flex-end' }}>
          <label className={styles.checkLabel} style={{ marginBottom: 7 }}>
            <input type="checkbox" checked={form.ativo} onChange={e => set('ativo', e.target.checked)} />
            Produto ativo
          </label>
        </div>

        {/* Descrição */}
        <div className={styles.fg} style={{ gridColumn: '1 / -1' }}>
          <label>Descrição (opcional)</label>
          <textarea rows={2} value={form.descricao} onChange={e => set('descricao', e.target.value)} placeholder="Descrição ou observação do produto" />
        </div>

        {/* Canais */}
        <div className={styles.fg} style={{ gridColumn: '1 / -1' }}>
          <label>Disponível em</label>
          <div className={styles.toggleRow}>
            {[
              ['disponivel_pdv',     'ti-building-store', 'PDV'],
              ['disponivel_ifood',   'ti-brand-firebase', 'iFood'],
              ['disponivel_eventos', 'ti-calendar-event', 'Eventos'],
            ].map(([field, icon, label]) => (
              <label key={field} className={styles.toggle}>
                <input type="checkbox" checked={form[field]} onChange={e => set(field, e.target.checked)} />
                <i className={`ti ${icon}`} /> {label}
              </label>
            ))}
          </div>
        </div>
      </div>

      {erro && <p className={styles.erro}>{erro}</p>}

      <div className={styles.modalActions}>
        <Btn variant="ghost" onClick={onClose}>Cancelar</Btn>
        <Btn onClick={handleSalvar} loading={saving}>
          {criando ? 'Criar produto' : 'Salvar alterações'}
        </Btn>
      </div>
    </Modal>
  )
}
