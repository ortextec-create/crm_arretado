import { useState, useEffect, useCallback, useRef } from 'react'
import { fichasApi } from '../api/services'
import { Btn, Modal, Spinner, Toast } from '../components/ui'
import styles from './CentralPrecos.module.css'

const fmt = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const fmtPct = (v) => v != null ? `${(Number(v) * 100).toFixed(1)}%` : '—'

const SEGMENTO_LABELS = {
  unidade_pequena: 'Un. Pequena',
  unidade_media:   'Un. Média',
  bem_casado:      'Bem Casado',
  bolo_encomenda:  'Bolo / Enc.',
  outro:           'Outro',
}

function semaforoClass(margem) {
  if (margem == null) return styles.semaforoNeutro
  const pct = Number(margem) * 100
  if (pct >= 30) return styles.semaforoVerde
  if (pct >= 15) return styles.semaforoAmarelo
  return styles.semaforoVermelho
}

const ABAS = ['Matérias-Primas', 'Ajuste em Lote', 'Semáforo de Margens', 'Parâmetros']

export default function CentralPrecos() {
  const [aba, setAba] = useState(0)
  const [toast, setToast] = useState(null)
  const showToast = (msg, tipo = 'success') => setToast({ msg, tipo })

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={`serif ${styles.title}`}>Central de Preços</h1>
          <p className={styles.subtitle}>Controle de custos, margens e precificação</p>
        </div>
      </div>

      <div className={styles.tabBar}>
        {ABAS.map((label, i) => (
          <button
            key={i}
            className={`${styles.tab} ${aba === i ? styles.tabActive : ''}`}
            onClick={() => setAba(i)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className={styles.abaContent}>
        {aba === 0 && <AbaMateriaPrima onToast={showToast} />}
        {aba === 1 && <AbaAjusteLote onToast={showToast} />}
        {aba === 2 && <AbaSemaforo onToast={showToast} />}
        {aba === 3 && <AbaParametros onToast={showToast} />}
      </div>

      {toast && <Toast message={toast.msg} type={toast.tipo} onClose={() => setToast(null)} />}
    </div>
  )
}

// ─── Aba 1: Matérias-Primas ───────────────────────────────────────────────────

function AbaMateriaPrima({ onToast }) {
  const [materias,   setMaterias]   = useState([])
  const [loading,    setLoading]    = useState(true)
  const [search,     setSearch]     = useState('')
  const [editados,   setEditados]   = useState({})   // { id: novoValor }
  const [saving,     setSaving]     = useState(false)
  const [modalItem,  setModalItem]  = useState(null)  // null | {} (novo) | materia (editar)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fichasApi.listarMaterias({ search, page_size: 200 })
      setMaterias(res.data.results ?? res.data)
    } finally { setLoading(false) }
  }, [search])

  useEffect(() => { load() }, [load])

  function handleChange(id, val) {
    setEditados(e => ({ ...e, [id]: val }))
  }

  async function handleSalvarPrecos() {
    const ids = Object.keys(editados).filter(id => editados[id] !== '')
    if (!ids.length) return
    setSaving(true)
    try {
      await Promise.all(
        ids.map(id => fichasApi.atualizarPrecoMateria(Number(id), { valor_compra: editados[id] }))
      )
      onToast(`${ids.length} ingrediente(s) atualizado(s).`)
      setEditados({})
      load()
    } catch {
      onToast('Erro ao salvar.', 'error')
    } finally { setSaving(false) }
  }

  function handleSalvoModal(item, criado) {
    setModalItem(null)
    onToast(criado ? `Ingrediente "${item.nome}" cadastrado!` : `"${item.nome}" atualizado.`)
    load()
  }

  const temEdicoes = Object.values(editados).some(v => v !== '')

  return (
    <div className={styles.abaInner}>
      <div className={styles.toolbarRow}>
        <div className={styles.searchBox}>
          <i className="ti ti-search" />
          <input
            placeholder="Buscar ingrediente…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <Btn variant="secondary" onClick={() => setModalItem({})}>
          <i className="ti ti-plus" /> Novo ingrediente
        </Btn>
        <Btn onClick={handleSalvarPrecos} loading={saving} disabled={!temEdicoes}>
          <i className="ti ti-device-floppy" /> Salvar preços
        </Btn>
      </div>

      {loading ? <div className={styles.center}><Spinner /></div> : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Ingrediente</th>
                <th>Embalagem</th>
                <th className={styles.thRight}>Qtd emb.</th>
                <th className={styles.thRight}>Preço atual</th>
                <th className={styles.thRight}>Custo/un</th>
                <th className={styles.thRight}>Atualizar preço</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {materias.map(m => {
                const editado = editados[m.id] !== undefined && editados[m.id] !== ''
                return (
                  <tr key={m.id} className={editado ? styles.rowEditado : ''}>
                    <td className={styles.tdNome}>{m.nome}</td>
                    <td className={styles.tdMuted}>{m.unidade_compra}</td>
                    <td className={styles.tdRight}>
                      {Number(m.quantidade_compra).toLocaleString('pt-BR')} {m.unidade_medida}
                    </td>
                    <td className={styles.tdRight}>{fmt(m.valor_compra)}</td>
                    <td className={styles.tdRight}>
                      <span className={styles.custoUn}>
                        {fmt(m.custo_unitario)}/{m.unidade_medida}
                      </span>
                    </td>
                    <td className={styles.tdRight}>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        className={styles.inputPreco}
                        placeholder="—"
                        value={editados[m.id] ?? ''}
                        onChange={e => handleChange(m.id, e.target.value)}
                      />
                    </td>
                    <td>
                      <button
                        className={styles.btnEdit}
                        onClick={() => setModalItem(m)}
                        title="Editar ingrediente"
                      >
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

      {modalItem !== null && (
        <ModalIngrediente
          item={Object.keys(modalItem).length === 0 ? null : modalItem}
          onClose={() => setModalItem(null)}
          onSalvo={handleSalvoModal}
        />
      )}
    </div>
  )
}

// ─── Modal de ingrediente ─────────────────────────────────────────────────────

const UNIDADE_OPTS = [
  { value: 'g',  label: 'Gramas (g)' },
  { value: 'ml', label: 'Mililitros (ml)' },
  { value: 'un', label: 'Unidade (un)' },
  { value: 'kg', label: 'Quilograma (kg)' },
  { value: 'l',  label: 'Litro (l)' },
]

function ModalIngrediente({ item, onClose, onSalvo }) {
  const criando = !item
  const [form,   setForm]   = useState({
    nome:              item?.nome              ?? '',
    unidade_compra:    item?.unidade_compra    ?? '',
    quantidade_compra: item?.quantidade_compra ? String(item.quantidade_compra) : '',
    unidade_medida:    item?.unidade_medida    ?? 'g',
    valor_compra:      item?.valor_compra      ? String(item.valor_compra) : '',
    ativo:             item?.ativo             ?? true,
  })
  const [saving, setSaving] = useState(false)
  const [erro,   setErro]   = useState('')

  function set(f, v) { setForm(prev => ({ ...prev, [f]: v })) }

  // Calcula custo unitário preview em tempo real
  const custoPreview = form.quantidade_compra && form.valor_compra
    ? Number(form.valor_compra) / Number(form.quantidade_compra)
    : null

  async function handleSalvar() {
    if (!form.nome.trim())              { setErro('Nome é obrigatório.'); return }
    if (!form.unidade_compra.trim())    { setErro('Embalagem é obrigatória.'); return }
    if (!form.quantidade_compra || isNaN(Number(form.quantidade_compra)) || Number(form.quantidade_compra) <= 0) {
      setErro('Quantidade inválida.')
      return
    }
    if (!form.valor_compra || isNaN(Number(form.valor_compra)) || Number(form.valor_compra) <= 0) {
      setErro('Valor de compra inválido.')
      return
    }

    setSaving(true); setErro('')
    const payload = {
      nome:              form.nome.trim(),
      unidade_compra:    form.unidade_compra.trim(),
      quantidade_compra: form.quantidade_compra,
      unidade_medida:    form.unidade_medida,
      valor_compra:      form.valor_compra,
      ativo:             form.ativo,
    }
    try {
      const res = criando
        ? await fichasApi.criarMateria(payload)
        : await fichasApi.atualizarMateria(item.id, payload)
      onSalvo(res.data, criando)
    } catch (e) {
      const errs = e?.response?.data
      if (errs?.nome) setErro(`Nome: ${errs.nome.join(' ')}`)
      else setErro(typeof errs === 'string' ? errs : JSON.stringify(errs) || 'Erro ao salvar.')
    } finally { setSaving(false) }
  }

  return (
    <Modal open title={criando ? 'Novo Ingrediente' : `Editar: ${item.nome}`} onClose={onClose}>
      <div className={styles.ingGrid}>

        {/* Nome */}
        <div className={styles.ingField} style={{ gridColumn: '1 / -1' }}>
          <label>Nome do ingrediente *</label>
          <input
            value={form.nome}
            onChange={e => set('nome', e.target.value)}
            placeholder="Ex: Leite Condensado"
            autoFocus
          />
        </div>

        {/* Embalagem + Qtd */}
        <div className={styles.ingField}>
          <label>Embalagem de compra *</label>
          <input
            value={form.unidade_compra}
            onChange={e => set('unidade_compra', e.target.value)}
            placeholder="Ex: 395g, 1kg, 30 unidades"
          />
          <span className={styles.ingHint}>Como aparece na etiqueta do produto</span>
        </div>
        <div className={styles.ingField}>
          <label>Unidade de medida *</label>
          <select value={form.unidade_medida} onChange={e => set('unidade_medida', e.target.value)}>
            {UNIDADE_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        {/* Qtd numérica */}
        <div className={styles.ingField}>
          <label>Quantidade na embalagem *</label>
          <div className={styles.ingInputUnit}>
            <input
              type="number"
              step="0.001"
              min="0"
              value={form.quantidade_compra}
              onChange={e => set('quantidade_compra', e.target.value)}
              placeholder="Ex: 395"
            />
            <span className={styles.ingUnit}>{form.unidade_medida}</span>
          </div>
          <span className={styles.ingHint}>
            {form.unidade_medida === 'g'  && 'Ex: 1kg = 1000g'}
            {form.unidade_medida === 'ml' && 'Ex: 1 litro = 1000ml'}
            {form.unidade_medida === 'kg' && 'Ex: 1 pacote = 1kg'}
            {form.unidade_medida === 'l'  && 'Ex: 1 garrafa = 1l'}
            {form.unidade_medida === 'un' && 'Ex: cartela de ovos = 30un'}
          </span>
        </div>

        {/* Valor compra */}
        <div className={styles.ingField}>
          <label>Valor de compra (R$) *</label>
          <input
            type="number"
            step="0.01"
            min="0"
            value={form.valor_compra}
            onChange={e => set('valor_compra', e.target.value)}
            placeholder="Ex: 6,50"
          />
          {custoPreview != null && (
            <span className={styles.ingPreview}>
              Custo: <strong>{custoPreview.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</strong>
              /{form.unidade_medida}
            </span>
          )}
        </div>

        {/* Ativo */}
        <div className={styles.ingField} style={{ gridColumn: '1 / -1' }}>
          <label className={styles.ingCheckLabel}>
            <input type="checkbox" checked={form.ativo} onChange={e => set('ativo', e.target.checked)} />
            Ingrediente ativo
          </label>
        </div>
      </div>

      {erro && <p className={styles.ingErro}>{erro}</p>}

      <div className={styles.ingActions}>
        <Btn variant="ghost" onClick={onClose}>Cancelar</Btn>
        <Btn onClick={handleSalvar} loading={saving}>
          {criando ? 'Cadastrar ingrediente' : 'Salvar alterações'}
        </Btn>
      </div>
    </Modal>
  )
}

// ─── Aba 2: Ajuste em Lote ────────────────────────────────────────────────────

const SEGMENTOS_AJUSTE = [
  { key: 'todos',           label: 'Todos' },
  { key: 'unidade_pequena', label: 'Un. Pequena' },
  { key: 'unidade_media',   label: 'Un. Média' },
  { key: 'bem_casado',      label: 'Bem Casado' },
  { key: 'bolo_encomenda',  label: 'Bolos / Enc.' },
]

function AbaAjusteLote({ onToast }) {
  const [segmento,  setSegmento]  = useState('todos')
  const [operacao,  setOperacao]  = useState('aumento')
  const [tipo,      setTipo]      = useState('percentual')
  const [valor,     setValor]     = useState('')
  const [preview,   setPreview]   = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [confirming,setConfirming]= useState(false)
  const [ultimoSnap,setUltimoSnap]= useState(null)
  const [snapshots, setSnapshots] = useState([])

  useEffect(() => {
    fichasApi.listarSnapshots({ page_size: 10 }).then(r => setSnapshots(r.data.results ?? r.data)).catch(() => {})
  }, [ultimoSnap])

  async function handlePreview() {
    if (!valor) return
    setLoading(true)
    try {
      const res = await fichasApi.previewAjuste({ segmento, operacao, tipo, valor: Number(valor) })
      setPreview(res.data)
    } catch { onToast('Erro ao gerar preview.', 'error') }
    finally { setLoading(false) }
  }

  async function handleConfirmar() {
    setConfirming(true)
    try {
      const res = await fichasApi.aplicarAjuste({ segmento, operacao, tipo, valor: Number(valor) })
      onToast(`Ajuste aplicado em ${res.data.total_produtos} produtos.`)
      setUltimoSnap(res.data.snapshot_id)
      setPreview(null)
      setValor('')
    } catch { onToast('Erro ao aplicar ajuste.', 'error') }
    finally { setConfirming(false) }
  }

  async function handleDesfazer(id) {
    try {
      const res = await fichasApi.desfazerAjuste(id)
      onToast(`${res.data.produtos_restaurados} produto(s) restaurado(s).`)
      setSnapshots(s => s.map(x => x.id === id ? { ...x, revertido: true } : x))
    } catch (e) {
      onToast(e?.response?.data?.detail || 'Erro ao desfazer.', 'error')
    }
  }

  return (
    <div className={styles.abaInner}>
      <div className={styles.ajusteCard}>
        <h3 className={styles.cardTitle}>Ajuste de Preços em Lote</h3>

        <div className={styles.ajusteGrid}>
          {/* Segmento */}
          <div className={styles.ajusteField}>
            <label>Aplicar em</label>
            <div className={styles.chipGroup}>
              {SEGMENTOS_AJUSTE.map(s => (
                <button
                  key={s.key}
                  className={`${styles.chip} ${segmento === s.key ? styles.chipActive : ''}`}
                  onClick={() => setSegmento(s.key)}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Operação */}
          <div className={styles.ajusteField}>
            <label>Operação</label>
            <div className={styles.chipGroup}>
              <button className={`${styles.chip} ${operacao === 'aumento' ? styles.chipActive : ''}`} onClick={() => setOperacao('aumento')}>
                <i className="ti ti-arrow-up" /> Aumento
              </button>
              <button className={`${styles.chip} ${styles.chipDanger} ${operacao === 'desconto' ? styles.chipDangerActive : ''}`} onClick={() => setOperacao('desconto')}>
                <i className="ti ti-arrow-down" /> Desconto
              </button>
            </div>
          </div>

          {/* Tipo + Valor */}
          <div className={styles.ajusteField}>
            <label>Tipo e valor</label>
            <div className={styles.valorRow}>
              <div className={styles.chipGroup}>
                <button className={`${styles.chip} ${tipo === 'percentual' ? styles.chipActive : ''}`} onClick={() => setTipo('percentual')}>Percentual (%)</button>
                <button className={`${styles.chip} ${tipo === 'valor_fixo' ? styles.chipActive : ''}`} onClick={() => setTipo('valor_fixo')}>Valor fixo (R$)</button>
              </div>
              <div className={styles.valorInputWrap}>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className={styles.valorInput}
                  value={valor}
                  onChange={e => { setValor(e.target.value); setPreview(null) }}
                  placeholder={tipo === 'percentual' ? '10' : '0,50'}
                />
                <span className={styles.valorSufixo}>{tipo === 'percentual' ? '%' : 'R$'}</span>
              </div>
            </div>
          </div>
        </div>

        <div className={styles.ajusteActions}>
          <Btn variant="secondary" onClick={handlePreview} loading={loading} disabled={!valor}>
            <i className="ti ti-eye" /> Visualizar preview
          </Btn>
        </div>
      </div>

      {/* Preview */}
      {preview && (
        <div className={styles.previewCard}>
          <div className={styles.previewHeader}>
            <div>
              <strong>{preview.total_produtos} produtos</strong> serão atualizados
              <span className={styles.previewDesc}> — {SEGMENTOS_AJUSTE.find(s => s.key === segmento)?.label} | {operacao === 'aumento' ? '+' : '-'}{valor}{tipo === 'percentual' ? '%' : ' R$'}</span>
            </div>
            <Btn onClick={handleConfirmar} loading={confirming}>
              <i className="ti ti-check" /> Confirmar ajuste
            </Btn>
          </div>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Produto</th>
                  <th>Segmento</th>
                  <th className={styles.thRight}>Preço atual</th>
                  <th className={styles.thRight}>Preço novo</th>
                  <th className={styles.thRight}>Variação</th>
                </tr>
              </thead>
              <tbody>
                {preview.preview.map(p => (
                  <tr key={p.id}>
                    <td>{p.nome}</td>
                    <td className={styles.tdMuted}>{SEGMENTO_LABELS[p.segmento] || p.segmento}</td>
                    <td className={styles.tdRight}>{fmt(p.preco_atual)}</td>
                    <td className={`${styles.tdRight} ${styles.tdDestaque}`}>{fmt(p.preco_novo)}</td>
                    <td className={`${styles.tdRight} ${p.variacao >= 0 ? styles.tdVerde : styles.tdVermelho}`}>
                      {p.variacao >= 0 ? '+' : ''}{fmt(p.variacao)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Histórico */}
      {snapshots.length > 0 && (
        <div className={styles.historicoCard}>
          <h4 className={styles.historicoTitulo}>Ajustes recentes</h4>
          {snapshots.map(s => {
            const d = new Date(s.criado_em)
            const age = (Date.now() - d.getTime()) / 3600000
            return (
              <div key={s.id} className={`${styles.historicoItem} ${s.revertido ? styles.historicoRevertido : ''}`}>
                <i className="ti ti-history" />
                <span>{d.toLocaleString('pt-BR')} — {s.descricao}</span>
                {!s.revertido ? (
                  <button
                    className={styles.btnDesfazer}
                    onClick={() => handleDesfazer(s.id)}
                    title="Desfazer este ajuste"
                  >
                    <i className="ti ti-rotate-left" /> Desfazer
                  </button>
                ) : (
                  <span className={styles.tagRevertido}>Desfeito</span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ─── Aba 3: Semáforo de Margens ───────────────────────────────────────────────

function AbaSemaforo({ onToast }) {
  const [produtos,  setProdutos]  = useState([])
  const [fichas,    setFichas]    = useState([])
  const [loading,   setLoading]   = useState(true)
  const [search,    setSearch]    = useState('')
  const [segFiltro, setSegFiltro] = useState('')
  const [sel,       setSel]       = useState(null)   // produto selecionado no painel lateral
  const [novoPreco, setNovoPreco] = useState('')
  const [saving,    setSaving]    = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [rp, rf] = await Promise.all([
        fichasApi.listarProdutos({ page_size: 300, ativo: 'true' }),
        fichasApi.listarFichas({ page_size: 300, ativo: 'true' }),
      ])
      setProdutos(rp.data.results ?? rp.data)
      setFichas(rf.data.results ?? rf.data)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const fichaByProduto = Object.fromEntries(fichas.map(f => [f.produto_pdv_id, f]))

  const produtosFiltrados = produtos.filter(p => {
    const ficha = fichaByProduto[p.id]
    const okSearch  = !search || p.nome.toLowerCase().includes(search.toLowerCase())
    const okSegmento= !segFiltro || p.segmento === segFiltro
    return okSearch && okSegmento
  })

  function openPainel(prod) {
    setSel(prod)
    setNovoPreco(String(prod.preco))
  }

  async function handleSalvarPreco() {
    if (!sel) return
    setSaving(true)
    try {
      await fichasApi.atualizarProduto(sel.id, { preco: novoPreco })
      onToast('Preço atualizado.')
      await load()
      setSel(s => ({ ...s, preco: Number(novoPreco) }))
    } catch { onToast('Erro ao salvar.', 'error') }
    finally { setSaving(false) }
  }

  const ficha = sel ? fichaByProduto[sel.id] : null

  return (
    <div className={styles.semaforoLayout}>
      <div className={styles.semaforoMain}>
        <div className={styles.toolbarRow}>
          <div className={styles.searchBox}>
            <i className="ti ti-search" />
            <input placeholder="Buscar produto…" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select
            className={styles.segSelect}
            value={segFiltro}
            onChange={e => setSegFiltro(e.target.value)}
          >
            <option value="">Todos os segmentos</option>
            {Object.entries(SEGMENTO_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>

        {loading ? <div className={styles.center}><Spinner /></div> : (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th></th>
                  <th>Produto</th>
                  <th>Segmento</th>
                  <th className={styles.thRight}>Custo/un</th>
                  <th className={styles.thRight}>Preço venda</th>
                  <th className={styles.thRight}>Margem</th>
                  <th className={styles.thRight}>Status</th>
                </tr>
              </thead>
              <tbody>
                {produtosFiltrados.map(prod => {
                  const ficha   = fichaByProduto[prod.id]
                  const margem  = ficha?.margem_bruta_pct
                  const custo   = ficha?.custo_total_unitario
                  const sc      = semaforoClass(margem)
                  const isActive= sel?.id === prod.id
                  const statusLabel = margem == null ? '—'
                    : Number(margem) * 100 >= 30 ? 'Saudável'
                    : Number(margem) * 100 >= 15 ? 'Atenção'
                    : 'Risco'
                  return (
                    <tr
                      key={prod.id}
                      className={`${styles.row} ${isActive ? styles.rowActive : ''}`}
                      onClick={() => openPainel(prod)}
                    >
                      <td><div className={`${styles.semaforo} ${sc}`} /></td>
                      <td className={styles.tdNome}>{prod.nome}</td>
                      <td className={styles.tdMuted}>{SEGMENTO_LABELS[prod.segmento] || prod.segmento}</td>
                      <td className={styles.tdRight}>{custo != null ? fmt(custo) : '—'}</td>
                      <td className={`${styles.tdRight} ${styles.tdDestaque}`}>{fmt(prod.preco)}</td>
                      <td className={styles.tdRight}>{fmtPct(margem)}</td>
                      <td className={styles.tdRight}>
                        <span className={`${styles.badge} ${sc}`}>{statusLabel}</span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Painel lateral */}
      {sel && (
        <div className={styles.painel}>
          <div className={styles.painelHeader}>
            <strong>{sel.nome}</strong>
            <button className={styles.painelClose} onClick={() => setSel(null)}><i className="ti ti-x" /></button>
          </div>

          {ficha ? (
            <>
              <div className={styles.painelRow}><span>Custo ingredientes:</span><strong>{fmt(ficha.custo_ingredientes)}</strong></div>
              <div className={styles.painelRow}><span>+ Embalagem:</span><strong>{fmt(ficha.embalagem_custo)}</strong></div>
              <div className={`${styles.painelRow} ${styles.painelSep}`}><span>= Custo total/un:</span><strong>{fmt(ficha.custo_total_unitario)}</strong></div>
              <div className={styles.painelRow}>
                <span>Preço ideal ({Number(ficha.preco_ideal / ficha.custo_total_unitario || 0).toFixed(2)}x):</span>
                <strong className={styles.painelIdeal}>{fmt(ficha.preco_ideal)}</strong>
              </div>
            </>
          ) : (
            <p className={styles.semFicha}>Sem ficha técnica cadastrada</p>
          )}

          <div className={styles.painelPrecoField}>
            <label>Preço de venda atual</label>
            <input
              type="number"
              step="0.01"
              min="0"
              className={styles.inputDestaque}
              value={novoPreco}
              onChange={e => setNovoPreco(e.target.value)}
            />
          </div>

          {ficha && (
            <button
              className={styles.btnIdeal}
              onClick={() => setNovoPreco(String(ficha.preco_ideal.toFixed(2)))}
            >
              <i className="ti ti-wand" /> Usar preço ideal: {fmt(ficha.preco_ideal)}
            </button>
          )}

          <Btn onClick={handleSalvarPreco} loading={saving} style={{ width: '100%', marginTop: 8 }}>
            <i className="ti ti-device-floppy" /> Salvar preço
          </Btn>
        </div>
      )}
    </div>
  )
}

// ─── Aba 4: Parâmetros ────────────────────────────────────────────────────────

function AbaParametros({ onToast }) {
  const [params,  setParams]  = useState(null)
  const [form,    setForm]    = useState({})
  const [loading, setLoading] = useState(true)
  const [saving,  setSaving]  = useState(false)

  useEffect(() => {
    fichasApi.getParametros()
      .then(r => { setParams(r.data); setForm(r.data) })
      .catch(() => onToast('Erro ao carregar parâmetros.', 'error'))
      .finally(() => setLoading(false))
  }, [])

  function set(field, val) { setForm(f => ({ ...f, [field]: val })) }

  async function handleSalvar() {
    setSaving(true)
    try {
      const res = await fichasApi.salvarParametros({
        faturamento_meta:          form.faturamento_meta,
        despesa_fixa_mensal:       form.despesa_fixa_mensal,
        despesa_variavel_pct:      Number(form.despesa_variavel_pct_pct || 0) / 100,
        margem_lucro_esperada_pct: Number(form.margem_lucro_esperada_pct_pct || 0) / 100,
      })
      setParams(res.data.parametros)
      onToast('Parâmetros salvos. Preços ideais recalculados.')
    } catch { onToast('Erro ao salvar.', 'error') }
    finally { setSaving(false) }
  }

  if (loading) return <div className={styles.center}><Spinner /></div>

  const desp_pct = Number(form.despesa_variavel_pct || params?.despesa_variavel_pct || 0)
  const marg_pct = Number(form.margem_lucro_esperada_pct || params?.margem_lucro_esperada_pct || 0)
  const markup   = params ? Number(params.markup).toFixed(2) : '—'

  return (
    <div className={styles.abaInner}>
      <div className={styles.parametrosCard}>
        <h3 className={styles.cardTitle}>Parâmetros do Negócio</h3>

        <div className={styles.paramGrid}>
          <div className={styles.paramField}>
            <label>Faturamento meta mensal (R$)</label>
            <input type="number" min="0" step="100" value={form.faturamento_meta || ''} onChange={e => set('faturamento_meta', e.target.value)} />
            <span className={styles.paramHelp}>Meta de receita bruta mensal</span>
          </div>
          <div className={styles.paramField}>
            <label>Despesas fixas mensais (R$)</label>
            <input type="number" min="0" step="100" value={form.despesa_fixa_mensal || ''} onChange={e => set('despesa_fixa_mensal', e.target.value)} />
            <span className={styles.paramHelp}>Folha + gás/gasolina + Simples Nacional</span>
          </div>
          <div className={styles.paramField}>
            <label>Despesas variáveis (% da venda)</label>
            <div className={styles.pctRow}>
              <input
                type="number" min="0" max="100" step="0.5"
                value={form.despesa_variavel_pct_pct ?? (desp_pct * 100).toFixed(1)}
                onChange={e => set('despesa_variavel_pct_pct', e.target.value)}
              />
              <span>%</span>
            </div>
            <span className={styles.paramHelp}>iFood, embalagens, outros variáveis</span>
          </div>
          <div className={styles.paramField}>
            <label>Margem de lucro esperada</label>
            <div className={styles.pctRow}>
              <input
                type="number" min="0" max="100" step="0.5"
                value={form.margem_lucro_esperada_pct_pct ?? (marg_pct * 100).toFixed(1)}
                onChange={e => set('margem_lucro_esperada_pct_pct', e.target.value)}
              />
              <span>%</span>
            </div>
            <span className={styles.paramHelp}>Margem desejada sobre cada venda</span>
          </div>
        </div>

        <div className={styles.markupDisplay}>
          <div className={styles.markupBox}>
            <span>Markup calculado</span>
            <strong>{markup}x</strong>
          </div>
          <p className={styles.markupNote}>
            <i className="ti ti-alert-triangle" />
            Alterar esses valores recalcula os preços ideais de todos os produtos automaticamente.
          </p>
        </div>

        <div className={styles.paramActions}>
          <Btn onClick={handleSalvar} loading={saving}>
            <i className="ti ti-device-floppy" /> Salvar parâmetros
          </Btn>
        </div>
      </div>
    </div>
  )
}
