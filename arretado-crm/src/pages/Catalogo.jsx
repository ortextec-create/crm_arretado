import { useState, useEffect, useCallback } from 'react'
import { fichasApi } from '../api/services'
import { Btn, Modal, Spinner, Toast } from '../components/ui'
import styles from './Catalogo.module.css'

const fmt = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const fmtPct = (v) => v != null ? `${(Number(v) * 100).toFixed(1)}%` : null

const SEGMENTO_LABELS = {
  unidade_pequena: 'Unidade Pequena',
  unidade_media:   'Unidade Média',
  bem_casado:      'Bem Casado',
  bolo_encomenda:  'Bolo / Encomenda',
  outro:           'Outro',
}

const SEGMENTO_TABS = [
  { key: '',               label: 'Todos' },
  { key: 'unidade_pequena', label: 'Un. Pequena' },
  { key: 'unidade_media',   label: 'Un. Média' },
  { key: 'bem_casado',      label: 'Bem Casado' },
  { key: 'bolo_encomenda',  label: 'Bolos' },
  { key: 'outro',           label: 'Outros' },
]

function semaforoClass(margem) {
  if (margem == null) return styles.bordaNeutro
  const pct = Number(margem) * 100
  if (pct >= 30) return styles.bordaVerde
  if (pct >= 15) return styles.bordaAmarelo
  return styles.bordaVermelho
}

export default function Catalogo() {
  const [produtos, setProdutos] = useState([])
  const [fichas,   setFichas]   = useState([])
  const [loading,  setLoading]  = useState(true)
  const [search,   setSearch]   = useState('')
  const [seg,      setSeg]      = useState('')
  const [toast,    setToast]    = useState(null)
  const [editProd, setEditProd] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [rp, rf] = await Promise.all([
        fichasApi.listarProdutos({ page_size: 300 }),
        fichasApi.listarFichas({ page_size: 300 }),
      ])
      setProdutos(rp.data.results ?? rp.data)
      setFichas(rf.data.results ?? rf.data)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const fichaByProduto = Object.fromEntries(fichas.map(f => [f.produto_pdv_id, f]))

  const produtosFiltrados = produtos.filter(p => {
    const okSearch = !search || p.nome.toLowerCase().includes(search.toLowerCase())
    const okSeg    = !seg    || p.segmento === seg
    return okSearch && okSeg
  })

  function showToast(msg, tipo = 'success') { setToast({ msg, tipo }) }

  function handleSalvo(prod) {
    setProdutos(ps => ps.map(p => p.id === prod.id ? prod : p))
    setEditProd(null)
    showToast('Produto atualizado.')
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={`serif ${styles.title}`}>Catálogo</h1>
          <p className={styles.subtitle}>Produtos disponíveis para venda</p>
        </div>
      </div>

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
        <input
          className={styles.search}
          placeholder="Buscar produto…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {loading ? (
        <div className={styles.center}><Spinner /></div>
      ) : produtosFiltrados.length === 0 ? (
        <div className={styles.empty}>
          <i className="ti ti-package-off" />
          <p>Nenhum produto encontrado.</p>
        </div>
      ) : (
        <div className={styles.grid}>
          {produtosFiltrados.map(prod => {
            const ficha  = fichaByProduto[prod.id]
            const margem = ficha?.margem_bruta_pct
            const custo  = ficha?.custo_total_unitario
            return (
              <div key={prod.id} className={`${styles.card} ${semaforoClass(margem)}`}>
                {prod.foto ? (
                  <img src={prod.foto} alt={prod.nome} className={styles.cardFoto} />
                ) : (
                  <div className={styles.cardFotoPlaceholder}>
                    <i className="ti ti-photo" />
                  </div>
                )}
                <div className={styles.cardBody}>
                  <p className={styles.cardSegmento}>{SEGMENTO_LABELS[prod.segmento] || prod.segmento}</p>
                  <h3 className={styles.cardNome}>{prod.nome}</h3>
                  <p className={styles.cardPreco}>{fmt(prod.preco)}</p>

                  {custo != null && (
                    <div className={styles.cardCusto}>
                      <span>Custo: {fmt(custo)}</span>
                      {margem != null && (
                        <span className={`${styles.cardMargem} ${
                          Number(margem) * 100 >= 30 ? styles.margemVerde :
                          Number(margem) * 100 >= 15 ? styles.margemAmarelo :
                          styles.margemVermelho
                        }`}>
                          Margem: {fmtPct(margem)}
                        </span>
                      )}
                    </div>
                  )}

                  <div className={styles.cardCanais}>
                    <span className={`${styles.canal} ${prod.disponivel_pdv ? styles.canalAtivo : ''}`}>
                      <i className="ti ti-building-store" /> PDV
                    </span>
                    <span className={`${styles.canal} ${prod.disponivel_ifood ? styles.canalAtivo : ''}`}>
                      <i className="ti ti-brand-firebase" /> iFood
                    </span>
                    <span className={`${styles.canal} ${prod.disponivel_eventos ? styles.canalAtivo : ''}`}>
                      <i className="ti ti-calendar-event" /> Eventos
                    </span>
                  </div>

                  <div className={styles.cardActions}>
                    <button className={styles.btnCard} onClick={() => setEditProd(prod)}>
                      <i className="ti ti-pencil" /> Editar
                    </button>
                    {ficha && (
                      <button className={`${styles.btnCard} ${styles.btnCardSecondary}`}
                        onClick={() => window.open('/fichas-tecnicas', '_self')}>
                        <i className="ti ti-flask" /> Ficha
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {editProd && (
        <ModalEditarProduto
          prod={editProd}
          onClose={() => setEditProd(null)}
          onSalvo={handleSalvo}
        />
      )}

      {toast && <Toast message={toast.msg} type={toast.tipo} onClose={() => setToast(null)} />}
    </div>
  )
}

// ─── Modal de edição ──────────────────────────────────────────────────────────

function ModalEditarProduto({ prod, onClose, onSalvo }) {
  const [form,   setForm]   = useState({
    nome:               prod.nome,
    descricao:          prod.descricao || '',
    preco:              String(prod.preco),
    segmento:           prod.segmento || 'outro',
    disponivel_pdv:     prod.disponivel_pdv ?? true,
    disponivel_ifood:   prod.disponivel_ifood ?? false,
    disponivel_eventos: prod.disponivel_eventos ?? false,
  })
  const [saving, setSaving] = useState(false)
  const [erro,   setErro]   = useState('')

  function set(field, val) { setForm(f => ({ ...f, [field]: val })) }

  async function handleSalvar() {
    if (!form.nome) { setErro('Nome é obrigatório.'); return }
    setSaving(true); setErro('')
    try {
      const res = await fichasApi.atualizarProduto(prod.id, {
        nome:               form.nome,
        descricao:          form.descricao,
        preco:              form.preco,
        segmento:           form.segmento,
        disponivel_pdv:     form.disponivel_pdv,
        disponivel_ifood:   form.disponivel_ifood,
        disponivel_eventos: form.disponivel_eventos,
      })
      onSalvo(res.data)
    } catch (e) {
      setErro(e?.response?.data?.detail || JSON.stringify(e?.response?.data) || 'Erro ao salvar.')
    } finally { setSaving(false) }
  }

  return (
    <Modal open title={`Editar: ${prod.nome}`} onClose={onClose}>
      <div className={styles.modalGrid}>
        <div className={styles.formGroup} style={{ gridColumn: '1 / -1' }}>
          <label>Nome</label>
          <input value={form.nome} onChange={e => set('nome', e.target.value)} />
        </div>
        <div className={styles.formGroup}>
          <label>Preço de venda (R$)</label>
          <input type="number" step="0.01" min="0" value={form.preco} onChange={e => set('preco', e.target.value)} />
        </div>
        <div className={styles.formGroup}>
          <label>Segmento</label>
          <select value={form.segmento} onChange={e => set('segmento', e.target.value)}>
            {Object.entries(SEGMENTO_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <div className={styles.formGroup} style={{ gridColumn: '1 / -1' }}>
          <label>Descrição</label>
          <textarea rows={2} value={form.descricao} onChange={e => set('descricao', e.target.value)} />
        </div>
        <div className={styles.formGroup} style={{ gridColumn: '1 / -1' }}>
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
        <Btn onClick={handleSalvar} loading={saving}>Salvar</Btn>
      </div>
    </Modal>
  )
}
