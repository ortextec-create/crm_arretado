import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { fichasApi, pdvApi } from '../api/services'
import { Btn, Modal, Spinner, Toast } from '../components/ui'
import styles from './Catalogo.module.css'

const fmt    = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const fmtPct = (v) => v != null ? `${(Number(v) * 100).toFixed(1)}%` : '—'

const TIPO_INFO = {
  fabricado: { label: 'Fabricado', icon: 'ti-cake',           cls: 'tipoFabricado' },
  revenda:   { label: 'Revenda',   icon: 'ti-truck-delivery', cls: 'tipoRevenda' },
  kit:       { label: 'Kit',       icon: 'ti-package',        cls: 'tipoKit' },
}

const TIPO_CHIPS = [
  { key: '',          label: 'Todos' },
  { key: 'fabricado', label: 'Fabricados', icon: 'ti-cake' },
  { key: 'revenda',   label: 'Revenda',    icon: 'ti-truck-delivery' },
  { key: 'kit',        label: 'Kits',       icon: 'ti-package' },
]

const CUSTO_LABEL = { ficha: 'ficha', compra: 'compra', soma: 'soma' }
const CUSTO_ICON  = { ficha: 'ti-flask', compra: 'ti-shopping-cart', soma: 'ti-sum' }

function margemClass(margem) {
  if (margem == null) return ''
  const pct = Number(margem) * 100
  if (pct >= 30) return styles.margemVerde
  if (pct >= 15) return styles.margemAmarela
  return styles.margemVermelha
}

function faixasResumo(faixas) {
  if (!faixas || faixas.length === 0) return null
  const CANAL_LABEL = { pdv: 'PDV', ifood: 'iFood', eventos: 'eventos' }
  if (faixas.length === 1) {
    const f = faixas[0]
    const canal = f.canal ? `${CANAL_LABEL[f.canal]}, ` : ''
    return `+1 faixa (${canal}${f.quantidade_minima}un ${fmt(f.preco_unitario)})`
  }
  const partes = faixas.slice(0, 2).map(f => `${f.quantidade_minima}un ${fmt(f.preco_unitario)}`)
  return `+${faixas.length} faixas (${partes.join(' · ')})`
}

export default function Catalogo() {
  const navigate = useNavigate()

  const [produtos,       setProdutos]       = useState([])
  const [fichas,         setFichas]         = useState([])
  const [materiasPrimas, setMateriasPrimas] = useState([])
  const [categorias,     setCategorias]     = useState([])
  const [loading,        setLoading]        = useState(true)
  const [search,         setSearch]         = useState('')
  const [tipoFiltro,     setTipoFiltro]     = useState('')
  const [categoriaFiltro,setCategoriaFiltro]= useState('')
  const [showInativos,   setShowInativos]   = useState(false)
  const [toast,          setToast]          = useState(null)
  const [editProd,       setEditProd]       = useState(null)   // null | produto | 'novo'

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [rp, rf, rm, rc] = await Promise.all([
        pdvApi.listProdutos({ page_size: 300 }),
        fichasApi.listarFichas({ page_size: 300 }),
        fichasApi.listarMaterias({ page_size: 300, ativo: 'true' }),
        pdvApi.listCategorias(),
      ])
      setProdutos(rp.data.results ?? rp.data)
      setFichas(rf.data.results ?? rf.data)
      setMateriasPrimas(rm.data.results ?? rm.data)
      setCategorias(rc.data.results ?? rc.data)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const produtosFiltrados = produtos.filter(p => {
    const okSearch = !search || p.nome.toLowerCase().includes(search.toLowerCase())
    const okTipo   = !tipoFiltro || p.tipo === tipoFiltro
    const okCat    = !categoriaFiltro || String(p.categoria) === String(categoriaFiltro)
    const okAtivo  = showInativos ? true : p.ativo
    return okSearch && okTipo && okCat && okAtivo
  })

  function showToast(msg, tipo = 'success') { setToast({ msg, tipo }) }

  function upsertProdutoLocal(prod) {
    setProdutos(ps => ps.some(p => p.id === prod.id) ? ps.map(p => p.id === prod.id ? prod : p) : [...ps, prod])
  }

  function handleSalvo(prod, criado) {
    upsertProdutoLocal(prod)
    if (criado) showToast(`Produto "${prod.nome}" criado!`)
  }

  function handleFichaAtualizada(ficha) {
    // resposta do PATCH usa FichaTecnicaCreateSerializer (sem custo_total_unitario/preco_ideal) —
    // faz merge parcial pra não perder os campos calculados que só existem no serializer de listagem
    setFichas(fs => fs.map(f => f.id === ficha.id ? { ...f, ...ficha } : f))
  }

  const totalAtivos = produtos.filter(p => p.ativo).length

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h1 className={`serif ${styles.title}`}>Catálogo</h1>
          <p className={styles.subtitle}>{totalAtivos} produto{totalAtivos !== 1 ? 's' : ''} ativos · fabricados, revenda e kits</p>
        </div>
        <Btn onClick={() => setEditProd('novo')}>
          <i className="ti ti-plus" /> Novo produto
        </Btn>
      </div>

      {/* Filtros */}
      <div className={styles.filters}>
        <div className={styles.search}>
          <i className="ti ti-search" />
          <input placeholder="Buscar produto…" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <div className={styles.chips}>
          {TIPO_CHIPS.map(t => (
            <button
              key={t.key}
              className={`${styles.chip} ${tipoFiltro === t.key ? styles.chipActive : ''}`}
              onClick={() => setTipoFiltro(t.key)}
            >
              {t.icon && <i className={`ti ${t.icon}`} />} {t.label}
            </button>
          ))}
        </div>
        <select className={styles.selectCategoria} value={categoriaFiltro} onChange={e => setCategoriaFiltro(e.target.value)}>
          <option value="">Todas as categorias</option>
          {categorias.map(c => <option key={c.id} value={c.id}>{c.nome}</option>)}
        </select>
        <label className={styles.checkLabel}>
          <input type="checkbox" checked={showInativos} onChange={e => setShowInativos(e.target.checked)} />
          Ver inativos
        </label>
      </div>

      {/* Grid */}
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
            const tipoInfo = TIPO_INFO[prod.tipo] || TIPO_INFO.fabricado
            const custoLbl = CUSTO_LABEL[prod.custo_origem] || 'ficha'
            return (
              <div
                key={prod.id}
                className={`${styles.card} ${margemClass(prod.margem_pct)} ${!prod.ativo ? styles.cardInativo : ''}`}
              >
                <div className={styles.cardFoto}>
                  <span className={`${styles.tipoPill} ${styles[tipoInfo.cls]}`}>
                    <i className={`ti ${tipoInfo.icon}`} /> {tipoInfo.label}
                  </span>
                  <button className={styles.btnEditarCard} onClick={() => setEditProd(prod)}>
                    <i className="ti ti-pencil" />
                  </button>
                  {prod.foto ? <img className={styles.cardFotoImg} src={prod.foto} alt={prod.nome} /> : <i className="ti ti-photo" />}
                  {!prod.ativo && <span className={styles.badgeInativo}>Inativo</span>}
                </div>
                <div className={styles.cardBody}>
                  <div className={styles.cardNome}>{prod.nome}</div>
                  <div className={styles.cardCat}>{prod.categoria_nome || '— sem categoria —'}</div>

                  <div className={styles.cardPrecoRow}>
                    <span className={styles.cardPreco}>{fmt(prod.preco)}</span>
                    <span className={styles.cardPrecoLabel}>
                      {prod.tipo === 'kit' ? 'kit' : prod.faixas_preco?.length ? 'a partir de 1un' : 'unidade'}
                    </span>
                  </div>

                  {prod.tipo === 'kit' ? (
                    prod.itens_kit?.length > 0 && (
                      <div className={styles.faixasHint}>
                        <i className="ti ti-components" /> {prod.itens_kit.length} produto{prod.itens_kit.length !== 1 ? 's' : ''} no kit
                      </div>
                    )
                  ) : (
                    faixasResumo(prod.faixas_preco) && (
                      <div className={styles.faixasHint}>
                        <i className="ti ti-stack-2" /> {faixasResumo(prod.faixas_preco)}
                      </div>
                    )
                  )}

                  <div className={styles.cardCustoRow}>
                    <div className={styles.cardCustoInfo}>
                      <span className={styles.cardCustoLabel}>
                        <i className={`ti ${CUSTO_ICON[custoLbl]}`} /> custo ({custoLbl})
                      </span>
                      <span className={styles.cardCustoVal}>{prod.custo != null ? fmt(prod.custo) : '—'}</span>
                    </div>
                    <span className={styles.cardMargem}>{fmtPct(prod.margem_pct)}</span>
                  </div>

                  <div className={styles.cardCanais}>
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
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Modal criar/editar */}
      {editProd !== null && (
        <ModalProduto
          prod={editProd === 'novo' ? null : editProd}
          categorias={categorias}
          fichas={fichas}
          materiasPrimas={materiasPrimas}
          produtos={produtos}
          onClose={() => setEditProd(null)}
          onSalvo={handleSalvo}
          onFichaAtualizada={handleFichaAtualizada}
          onNavegarFicha={() => navigate('/fichas-tecnicas')}
        />
      )}

      {toast && <Toast message={toast.msg} type={toast.tipo} onClose={() => setToast(null)} />}
    </div>
  )
}

// ─── Modal criar / editar produto ────────────────────────────────────────────

const CANAL_OPCOES = [
  { value: '',        label: 'Todos' },
  { value: 'pdv',      label: 'PDV' },
  { value: 'ifood',    label: 'iFood' },
  { value: 'eventos',  label: 'Eventos' },
]

function ModalProduto({ prod, categorias, fichas, materiasPrimas, produtos, onClose, onSalvo, onFichaAtualizada, onNavegarFicha }) {
  const [produtoAtual, setProdutoAtual] = useState(prod)   // null enquanto o produto ainda não foi criado
  const criando = !produtoAtual

  const [form, setForm] = useState({
    nome:                 prod?.nome                 ?? '',
    descricao:            prod?.descricao            ?? '',
    preco:                prod?.preco                ? String(prod.preco) : '',
    categoria:            prod?.categoria             ? String(prod.categoria) : '',
    tipo:                 prod?.tipo                 ?? 'fabricado',
    materia_prima_origem: prod?.materia_prima_origem  ? String(prod.materia_prima_origem) : '',
    margem_desejada_pct:  prod?.margem_desejada_pct != null ? String(Number(prod.margem_desejada_pct) * 100) : '',
    disponivel_pdv:       prod?.disponivel_pdv       ?? true,
    disponivel_ifood:     prod?.disponivel_ifood     ?? false,
    disponivel_eventos:   prod?.disponivel_eventos   ?? true,
    ativo:                prod?.ativo                ?? true,
  })
  const [dadosFiscais, setDadosFiscais] = useState({
    unidade:       prod?.dados_fiscais?.unidade       ?? 'UN',
    codigo:        prod?.dados_fiscais?.codigo        ?? '',
    codigo_barras: prod?.dados_fiscais?.codigo_barras ?? '',
    ncm:           prod?.dados_fiscais?.ncm            ?? '',
  })
  const [fiscalAberto, setFiscalAberto] = useState(false)
  const [saving, setSaving] = useState(false)
  const [erro,   setErro]   = useState('')

  // ── Fabricado: ficha técnica vinculada ─────────────────────────────────
  const [fichaId, setFichaId] = useState(() => fichas.find(f => f.produto_pdv_id === prod?.id)?.id ?? '')
  const [vinculandoFicha, setVinculandoFicha] = useState(false)

  // ── Faixas de preço ─────────────────────────────────────────────────────
  const [novaFaixa,  setNovaFaixa]  = useState({ quantidade_minima: '', preco_unitario: '', canal: '' })
  const [addingFaixa, setAddingFaixa] = useState(false)

  // ── Kit: componentes ────────────────────────────────────────────────────
  const [novoComponente, setNovoComponente] = useState({ componente: '', quantidade: '1' })
  const [addingComponente, setAddingComponente] = useState(false)

  function set(field, val) { setForm(f => ({ ...f, [field]: val })) }

  function atualizarLocal(novo) {
    setProdutoAtual(novo)
    onSalvo(novo, false)
  }

  async function handleSalvar() {
    if (!form.nome.trim()) { setErro('Nome é obrigatório.'); return }
    if (!form.preco || isNaN(Number(form.preco))) { setErro('Preço inválido.'); return }
    if (form.tipo === 'revenda' && !form.materia_prima_origem) { setErro('Selecione a matéria-prima de origem.'); return }
    setSaving(true); setErro('')

    const temDadosFiscais = !!(dadosFiscais.codigo || dadosFiscais.codigo_barras || dadosFiscais.ncm || dadosFiscais.unidade !== 'UN')

    const payload = {
      nome:                 form.nome.trim(),
      descricao:            form.descricao,
      preco:                form.preco,
      categoria:            form.categoria ? Number(form.categoria) : null,
      tipo:                 form.tipo,
      materia_prima_origem: form.tipo === 'revenda' && form.materia_prima_origem ? Number(form.materia_prima_origem) : null,
      margem_desejada_pct:  form.tipo === 'revenda' && form.margem_desejada_pct  ? Number(form.margem_desejada_pct) / 100 : null,
      disponivel_pdv:       form.disponivel_pdv,
      disponivel_ifood:     form.disponivel_ifood,
      disponivel_eventos:   form.disponivel_eventos,
      ativo:                form.ativo,
    }
    if (temDadosFiscais) payload.dados_fiscais = dadosFiscais

    try {
      const res = criando
        ? await pdvApi.criarProduto(payload)
        : await pdvApi.updateProduto(produtoAtual.id, payload)
      if (criando) {
        setProdutoAtual(res.data)
        onSalvo(res.data, true)
      } else {
        atualizarLocal(res.data)
      }
    } catch (e) {
      const errs = e?.response?.data
      setErro(typeof errs === 'string' ? errs : JSON.stringify(errs) || 'Erro ao salvar.')
    } finally { setSaving(false) }
  }

  // ── Fabricado: vincular/desvincular ficha técnica ──────────────────────
  async function handleVincularFicha(novoFichaId) {
    if (!produtoAtual) return
    setVinculandoFicha(true); setErro('')
    try {
      const anterior = fichas.find(f => f.produto_pdv_id === produtoAtual.id)
      if (anterior && String(anterior.id) !== String(novoFichaId)) {
        const r = await fichasApi.atualizarFicha(anterior.id, { produto_pdv_id: null })
        onFichaAtualizada(r.data)
      }
      if (novoFichaId) {
        const r = await fichasApi.atualizarFicha(novoFichaId, { produto_pdv_id: produtoAtual.id })
        onFichaAtualizada(r.data)
      }
      setFichaId(novoFichaId)
    } catch {
      setErro('Erro ao vincular ficha técnica.')
    } finally { setVinculandoFicha(false) }
  }

  const fichaVinculada    = fichas.find(f => String(f.id) === String(fichaId))
  const fichasDisponiveis = fichas.filter(f => f.ativo && (!f.produto_pdv_id || f.produto_pdv_id === produtoAtual?.id))

  // ── Revenda: custo derivado da matéria-prima ────────────────────────────
  const materiaSelecionada = materiasPrimas.find(m => String(m.id) === String(form.materia_prima_origem))
  const custoRevenda = materiaSelecionada ? materiaSelecionada.custo_unitario : null
  const margemNum    = form.margem_desejada_pct ? Number(form.margem_desejada_pct) / 100 : null
  const precoSugerido = custoRevenda != null && margemNum && margemNum < 1
    ? custoRevenda / (1 - margemNum)
    : null

  // ── Kit: adicionar/remover componente ───────────────────────────────────
  async function handleAddComponente() {
    if (!produtoAtual || !novoComponente.componente) return
    setAddingComponente(true); setErro('')
    try {
      const res = await pdvApi.itensKit.adicionar(produtoAtual.id, {
        componente: Number(novoComponente.componente),
        quantidade: Number(novoComponente.quantidade) || 1,
      })
      atualizarLocal(res.data)
      setNovoComponente({ componente: '', quantidade: '1' })
    } catch (e) {
      setErro(e?.response?.data?.componente?.[0] || e?.response?.data?.non_field_errors?.[0] || 'Erro ao adicionar componente.')
    } finally { setAddingComponente(false) }
  }

  async function handleRemoverComponente(itemId) {
    const res = await pdvApi.itensKit.remover(produtoAtual.id, itemId)
    atualizarLocal(res.data)
  }

  const componentesDisponiveis = produtos.filter(p => p.tipo !== 'kit' && p.id !== produtoAtual?.id)

  // ── Faixas de preço: adicionar/remover ──────────────────────────────────
  async function handleAddFaixa() {
    if (!produtoAtual || !novaFaixa.quantidade_minima || !novaFaixa.preco_unitario) return
    setAddingFaixa(true); setErro('')
    try {
      const res = await pdvApi.faixasPreco.criar(produtoAtual.id, {
        quantidade_minima: Number(novaFaixa.quantidade_minima),
        preco_unitario:    novaFaixa.preco_unitario,
        canal:             novaFaixa.canal || null,
      })
      atualizarLocal(res.data)
      setNovaFaixa({ quantidade_minima: '', preco_unitario: '', canal: '' })
    } catch (e) {
      setErro(e?.response?.data?.quantidade_minima?.[0] || e?.response?.data?.non_field_errors?.[0] || 'Erro ao adicionar faixa.')
    } finally { setAddingFaixa(false) }
  }

  async function handleRemoverFaixa(faixaId) {
    const res = await pdvApi.faixasPreco.remover(produtoAtual.id, faixaId)
    atualizarLocal(res.data)
  }

  return (
    <Modal
      open
      title={criando ? 'Novo Produto' : `Editar: ${produtoAtual.nome}`}
      onClose={onClose}
      width={640}
      footer={
        <>
          <Btn variant="ghost" onClick={onClose}>{criando ? 'Cancelar' : 'Fechar'}</Btn>
          <Btn onClick={handleSalvar} loading={saving}>{criando ? 'Criar produto' : 'Salvar alterações'}</Btn>
        </>
      }
    >
      <div className={styles.modalGrid}>
        <div className={styles.fg} style={{ gridColumn: '1 / -1' }}>
          <label>Nome do produto *</label>
          <input value={form.nome} onChange={e => set('nome', e.target.value)} placeholder="Ex: Brigadeiro Tradicional" autoFocus />
        </div>

        <div className={styles.fg}>
          <label>Preço base (R$) *</label>
          <input type="number" step="0.01" min="0" value={form.preco} onChange={e => set('preco', e.target.value)} placeholder="0,00" />
        </div>
        <div className={styles.fg}>
          <label>Categoria</label>
          <select value={form.categoria} onChange={e => set('categoria', e.target.value)}>
            <option value="">— Sem categoria —</option>
            {categorias.map(c => <option key={c.id} value={c.id}>{c.nome}</option>)}
          </select>
        </div>

        <div className={styles.fg} style={{ display: 'flex', alignItems: 'flex-end' }}>
          <label className={styles.checkLabel} style={{ marginBottom: 7 }}>
            <input type="checkbox" checked={form.ativo} onChange={e => set('ativo', e.target.checked)} />
            Produto ativo
          </label>
        </div>

        <div className={styles.fg} style={{ gridColumn: '1 / -1' }}>
          <label>Descrição (opcional)</label>
          <textarea rows={2} value={form.descricao} onChange={e => set('descricao', e.target.value)} placeholder="Descrição ou observação do produto" />
        </div>

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

      {/* Tipo do produto */}
      <div className={styles.sectionTitle}>Tipo do produto</div>
      <div className={styles.tipoSwitch}>
        {Object.entries(TIPO_INFO).map(([key, info]) => (
          <button
            key={key}
            type="button"
            className={`${styles.tipoBtn} ${form.tipo === key ? styles.tipoBtnActive : ''} ${form.tipo === key ? styles[info.cls] : ''}`}
            onClick={() => set('tipo', key)}
          >
            <i className={`ti ${info.icon}`} /> {info.label}
          </button>
        ))}
      </div>

      {form.tipo === 'fabricado' && (
        <div className={styles.tipoPainel}>
          <div className={styles.fg}>
            <label>Ficha técnica vinculada</label>
            {criando ? (
              <p className={styles.hint}>Salve os dados básicos do produto para vincular uma ficha técnica.</p>
            ) : (
              <select value={fichaId} disabled={vinculandoFicha} onChange={e => handleVincularFicha(e.target.value)}>
                <option value="">— Nenhuma ficha vinculada —</option>
                {fichasDisponiveis.map(f => (
                  <option key={f.id} value={f.id}>{f.nome} — rendimento {f.rendimento}un</option>
                ))}
              </select>
            )}
          </div>
          {fichaVinculada && (
            <div className={styles.custoDerivado}>
              <span>Custo unitário: <b>{fmt(fichaVinculada.custo_total_unitario)}</b> · Preço ideal (markup): <b>{fmt(fichaVinculada.preco_ideal)}</b></span>
              <span className={styles.linkFicha} onClick={onNavegarFicha}>
                <i className="ti ti-external-link" /> Abrir ficha técnica
              </span>
            </div>
          )}
        </div>
      )}

      {form.tipo === 'revenda' && (
        <div className={styles.tipoPainel}>
          <div className={styles.fg}>
            <label>Matéria-prima de origem *</label>
            <select value={form.materia_prima_origem} onChange={e => set('materia_prima_origem', e.target.value)}>
              <option value="">— Selecione —</option>
              {materiasPrimas.map(m => <option key={m.id} value={m.id}>{m.nome}</option>)}
            </select>
          </div>
          <div className={styles.fg}>
            <label>Margem desejada (%) — opcional</label>
            <input type="number" step="0.1" min="0" max="99" value={form.margem_desejada_pct} onChange={e => set('margem_desejada_pct', e.target.value)} placeholder="Ex: 30" />
          </div>
          {materiaSelecionada && (
            <div className={styles.custoDerivado}>
              <span>
                Custo unitário (calculado automaticamente): <b>{fmt(custoRevenda)}</b>
                {precoSugerido != null && <> · Preço sugerido: <b>{fmt(precoSugerido)}</b></>}
              </span>
            </div>
          )}
        </div>
      )}

      {form.tipo === 'kit' && (
        <div className={styles.tipoPainel}>
          {criando ? (
            <p className={styles.hint}>Salve os dados básicos do produto para adicionar componentes ao kit.</p>
          ) : (
            <>
              <div className={styles.kitCompLista}>
                {(produtoAtual.itens_kit || []).length === 0 && <p className={styles.hint}>Nenhum componente adicionado ainda.</p>}
                {(produtoAtual.itens_kit || []).map(item => (
                  <div key={item.id} className={styles.kitComp}>
                    <span>{item.componente_nome}</span>
                    <span className={styles.qtd}>x{item.quantidade}</span>
                    <button className={styles.btnRemoverFaixa} onClick={() => handleRemoverComponente(item.id)}>
                      <i className="ti ti-trash" />
                    </button>
                  </div>
                ))}
              </div>
              <div className={styles.addComponenteRow}>
                <select value={novoComponente.componente} onChange={e => setNovoComponente(c => ({ ...c, componente: e.target.value }))}>
                  <option value="">— Produto —</option>
                  {componentesDisponiveis.map(p => <option key={p.id} value={p.id}>{p.nome}</option>)}
                </select>
                <input
                  type="number" min="1" style={{ width: 70 }}
                  value={novoComponente.quantidade}
                  onChange={e => setNovoComponente(c => ({ ...c, quantidade: e.target.value }))}
                />
                <button className={styles.btnAddComp} onClick={handleAddComponente} disabled={addingComponente || !novoComponente.componente}>
                  <i className="ti ti-plus" /> Adicionar
                </button>
              </div>
              {produtoAtual.custo != null && (
                <div className={styles.custoDerivado}>
                  <span>Custo total (soma dos componentes): <b>{fmt(produtoAtual.custo)}</b></span>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Faixas de preço */}
      <div className={styles.sectionTitle}>
        Faixas de preço por quantidade <span className={styles.hint}>preço base = quantidade 1, sem faixa aplicada</span>
      </div>
      {criando ? (
        <p className={styles.hint}>Salve os dados básicos do produto para cadastrar faixas de preço.</p>
      ) : (
        <>
          {(produtoAtual.faixas_preco || []).length > 0 && (
            <table className={styles.faixasTable}>
              <thead>
                <tr><th>Qtde. mínima</th><th>Preço unit.</th><th>Canal</th><th></th></tr>
              </thead>
              <tbody>
                {produtoAtual.faixas_preco.map(f => (
                  <tr key={f.id} className={styles.faixaRow}>
                    <td>{f.quantidade_minima}un</td>
                    <td>{fmt(f.preco_unitario)}</td>
                    <td>{CANAL_OPCOES.find(c => c.value === (f.canal || ''))?.label ?? 'Todos'}</td>
                    <td>
                      <button className={styles.btnRemoverFaixa} onClick={() => handleRemoverFaixa(f.id)}>
                        <i className="ti ti-trash" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className={styles.addFaixaRow}>
            <input
              placeholder="Qtde. mín." type="number" min="2"
              value={novaFaixa.quantidade_minima}
              onChange={e => setNovaFaixa(f => ({ ...f, quantidade_minima: e.target.value }))}
            />
            <input
              placeholder="Preço unit." type="number" step="0.01" min="0"
              value={novaFaixa.preco_unitario}
              onChange={e => setNovaFaixa(f => ({ ...f, preco_unitario: e.target.value }))}
            />
            <select value={novaFaixa.canal} onChange={e => setNovaFaixa(f => ({ ...f, canal: e.target.value }))}>
              {CANAL_OPCOES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
            <button
              className={styles.btnAddFaixa}
              onClick={handleAddFaixa}
              disabled={addingFaixa || !novaFaixa.quantidade_minima || !novaFaixa.preco_unitario}
            >
              <i className="ti ti-plus" /> Adicionar faixa
            </button>
          </div>
        </>
      )}

      {/* Dados fiscais */}
      <div className={styles.accordion}>
        <button type="button" className={`${styles.accordionHead} ${fiscalAberto ? styles.open : ''}`} onClick={() => setFiscalAberto(a => !a)}>
          <i className="ti ti-file-invoice" /> Dados fiscais (para NFC-e)
          <i className="ti ti-chevron-down" style={{ marginLeft: 'auto' }} />
        </button>
        {fiscalAberto && (
          <div className={styles.accordionBody}>
            <div className={styles.fg}>
              <label>Unidade</label>
              <select value={dadosFiscais.unidade} onChange={e => setDadosFiscais(d => ({ ...d, unidade: e.target.value }))}>
                <option value="UN">UN</option>
                <option value="KG">KG</option>
                <option value="CENTO">CENTO</option>
                <option value="DUZIA">DÚZIA</option>
                <option value="L">L</option>
              </select>
            </div>
            <div className={styles.fg}>
              <label>Código / SKU</label>
              <input placeholder="BRIG-001" value={dadosFiscais.codigo} onChange={e => setDadosFiscais(d => ({ ...d, codigo: e.target.value }))} />
            </div>
            <div className={styles.fg}>
              <label>Código de barras (EAN)</label>
              <input placeholder="Opcional" value={dadosFiscais.codigo_barras} onChange={e => setDadosFiscais(d => ({ ...d, codigo_barras: e.target.value }))} />
            </div>
            <div className={styles.fg}>
              <label>NCM</label>
              <input placeholder="Opcional" value={dadosFiscais.ncm} onChange={e => setDadosFiscais(d => ({ ...d, ncm: e.target.value }))} />
            </div>
            <p className={styles.fiscalHint}>
              <i className="ti ti-info-circle" /> Preenchimento opcional por enquanto — será obrigatório quando a emissão de NFC-e via Focus NFe entrar em produção.
            </p>
          </div>
        )}
      </div>

      {erro && <p className={styles.erro}>{erro}</p>}
    </Modal>
  )
}
