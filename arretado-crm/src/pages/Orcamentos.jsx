import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { orcamentosApi, clientesApi, pdvApi } from '../api/services'
import { Btn, Modal, Spinner, Toast } from '../components/ui'
import styles from './Orcamentos.module.css'

// ─── Helpers ─────────────────────────────────────────────────────────────────

const TIPO_EVENTO_LABELS = {
  casamento:   'Casamento',
  formatura:   'Formatura',
  aniversario: 'Aniversário',
  corporativo: 'Corporativo',
  batizado:    'Batizado',
  cha:         'Chá de bebê / revelação',
  outro:       'Outro',
}

const STATUS_CONFIG = {
  rascunho:   { label: 'Rascunho',   color: '#6B7280' },
  enviado:    { label: 'Enviado',    color: '#2563EB' },
  aprovado:   { label: 'Aprovado',   color: '#059669' },
  recusado:   { label: 'Recusado',   color: '#DC2626' },
  expirado:   { label: 'Expirado',   color: '#9CA3AF' },
  convertido: { label: 'Convertido', color: '#7C3AED' },
}

const STATUS_TABS = [
  { key: '',           label: 'Todos' },
  { key: 'rascunho',   label: 'Rascunho' },
  { key: 'enviado',    label: 'Enviado' },
  { key: 'aprovado',   label: 'Aprovado' },
  { key: 'recusado',   label: 'Recusado' },
  { key: 'expirado',   label: 'Expirado' },
  { key: 'convertido', label: 'Convertido' },
]

const fmt = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const fmtData = (d) => {
  if (!d) return '—'
  const [y, m, day] = d.split('-')
  return `${day}/${m}/${y}`
}

// ─── Componente principal ─────────────────────────────────────────────────────

export default function Orcamentos() {
  const navigate = useNavigate()

  const [orcamentos,  setOrcamentos]  = useState([])
  const [loading,     setLoading]     = useState(true)
  const [statusTab,   setStatusTab]   = useState('')
  const [search,      setSearch]      = useState('')
  const [toast,       setToast]       = useState(null)

  const [showNovo,      setShowNovo]      = useState(false)
  const [showDetalhe,   setShowDetalhe]   = useState(false)
  const [showConverter, setShowConverter] = useState(false)
  const [showWpp,       setShowWpp]       = useState(false)
  const [orcAtivo,      setOrcAtivo]      = useState(null)

  // ── Carregamento ──────────────────────────────────────────────────────────

  const loadOrcamentos = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (statusTab) params.status = statusTab
      if (search)    params.search = search
      const res = await orcamentosApi.list(params)
      setOrcamentos(res.data.results ?? res.data)
    } catch {
      showToast('Erro ao carregar orçamentos.', 'error')
    } finally {
      setLoading(false)
    }
  }, [statusTab, search])

  useEffect(() => { loadOrcamentos() }, [loadOrcamentos])

  function showToast(msg, tipo = 'success') {
    setToast({ msg, tipo })
  }

  async function openDetalhe(orc) {
    try {
      const res = await orcamentosApi.detail(orc.id)
      setOrcAtivo(res.data)
      setShowDetalhe(true)
    } catch {
      showToast('Erro ao carregar orçamento.', 'error')
    }
  }

  // ── Ações de status ───────────────────────────────────────────────────────

  async function handleAcao(acao, orc) {
    try {
      let res
      if (acao === 'enviar')    res = await orcamentosApi.enviar(orc.id)
      if (acao === 'aprovar')   res = await orcamentosApi.aprovar(orc.id)
      if (acao === 'recusar')   res = await orcamentosApi.recusar(orc.id)
      if (acao === 'restaurar') res = await orcamentosApi.restaurar(orc.id)
      if (acao === 'excluir') {
        await orcamentosApi.delete(orc.id)
        setShowDetalhe(false)
        setOrcAtivo(null)
        showToast('Orçamento excluído.')
        loadOrcamentos()
        return
      }
      if (res) {
        setOrcAtivo(res.data)
        loadOrcamentos()
        const msgs = { enviar: 'marcado como enviado', aprovar: 'aprovado', recusar: 'recusado', restaurar: 'restaurado' }
        showToast(`Orçamento ${msgs[acao] || acao}.`)
      }
    } catch (e) {
      showToast(e?.response?.data?.detail || 'Erro ao executar ação.', 'error')
    }
  }

  async function handlePdf(orc) {
    try {
      const res = await orcamentosApi.pdf(orc.id)
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      window.open(url, '_blank')
    } catch {
      showToast('Erro ao gerar PDF.', 'error')
    }
  }

  function handleAbrirWpp(orc) {
    if (!orc.telefone_display) {
      if (orc.cliente) {
        showToast(
          `O cliente ${orc.nome_cliente_display} não tem telefone cadastrado. Atualize o cadastro antes de enviar por WhatsApp.`,
          'error'
        )
      } else {
        showToast(
          'Orçamento sem telefone de contato. Vincule um cliente do CRM ou adicione um telefone avulso ao orçamento.',
          'error'
        )
      }
      return
    }
    setShowWpp(true)
  }

  function handleWppEnviado(updatedOrc) {
    setShowWpp(false)
    setOrcAtivo(updatedOrc)
    loadOrcamentos()
    showToast(`PDF ${updatedOrc.numero} enviado por WhatsApp com sucesso!`)
  }

  async function handleRemoverItem(itemId) {
    if (!orcAtivo) return
    try {
      const res = await orcamentosApi.removerItem(orcAtivo.id, itemId)
      setOrcAtivo(res.data)
      loadOrcamentos()
    } catch (e) {
      showToast(e?.response?.data?.detail || 'Erro ao remover item.', 'error')
    }
  }

  function handleNovoSalvo(orc) {
    setShowNovo(false)
    setOrcAtivo(orc)
    setShowDetalhe(true)
    loadOrcamentos()
    showToast(`Orçamento ${orc.numero} criado!`)
  }

  function handleConverterSalvo(evento) {
    setShowConverter(false)
    setShowDetalhe(false)
    setOrcAtivo(null)
    loadOrcamentos()
    showToast(`Evento ${evento.numero} criado com sucesso!`)
  }

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div className={styles.page}>
      {/* Cabeçalho */}
      <div className={styles.header}>
        <div>
          <h1 className={`serif ${styles.title}`}>Orçamentos</h1>
          <p className={styles.subtitle}>Propostas comerciais antes da confirmação do evento</p>
        </div>
        <Btn onClick={() => setShowNovo(true)}>
          <i className="ti ti-plus" /> Novo orçamento
        </Btn>
      </div>

      {/* Filtros */}
      <div className={styles.filters}>
        <div className={styles.tabs}>
          {STATUS_TABS.map(t => (
            <button
              key={t.key}
              className={`${styles.tab} ${statusTab === t.key ? styles.tabActive : ''}`}
              onClick={() => setStatusTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <input
          className={styles.search}
          placeholder="Buscar por número, cliente..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {/* Lista */}
      {loading ? (
        <div className={styles.spinnerWrap}><Spinner /></div>
      ) : orcamentos.length === 0 ? (
        <div className={styles.empty}>
          <i className="ti ti-file-description" />
          <p>Nenhum orçamento encontrado.</p>
        </div>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Número</th>
                <th>Cliente</th>
                <th>Tipo de evento</th>
                <th>Data prevista</th>
                <th>Validade</th>
                <th>Total</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {orcamentos.map(orc => {
                const sc = STATUS_CONFIG[orc.status] || {}
                return (
                  <tr key={orc.id} className={styles.row} onClick={() => openDetalhe(orc)}>
                    <td className={styles.numero}>{orc.numero}</td>
                    <td>{orc.nome_cliente_display}</td>
                    <td>{TIPO_EVENTO_LABELS[orc.tipo_evento] || '—'}</td>
                    <td>{fmtData(orc.data_evento)}</td>
                    <td>{fmtData(orc.validade)}</td>
                    <td className={styles.valor}>{fmt(orc.valor_total)}</td>
                    <td>
                      <span className={styles.badge} style={{ background: sc.color + '22', color: sc.color }}>
                        {sc.label || orc.status}
                      </span>
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      {orc.status === 'convertido' && orc.evento_numero && (
                        <button
                          className={styles.linkEvento}
                          onClick={() => navigate('/eventos')}
                          title={`Ver evento ${orc.evento_numero}`}
                        >
                          <i className="ti ti-calendar-event" /> {orc.evento_numero}
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal: novo orçamento */}
      {showNovo && (
        <ModalNovoOrcamento
          onClose={() => setShowNovo(false)}
          onSalvo={handleNovoSalvo}
        />
      )}

      {/* Modal: detalhe / edição de itens */}
      {showDetalhe && orcAtivo && (
        <ModalDetalheOrcamento
          orc={orcAtivo}
          onClose={() => { setShowDetalhe(false); setOrcAtivo(null) }}
          onAcao={handleAcao}
          onPdf={handlePdf}
          onEnviarWpp={handleAbrirWpp}
          onRemoverItem={handleRemoverItem}
          onItemAdicionado={(updated) => { setOrcAtivo(updated); loadOrcamentos() }}
          onConverter={() => setShowConverter(true)}
        />
      )}

      {/* Modal: converter em evento */}
      {showConverter && orcAtivo && (
        <ModalConverterEvento
          orc={orcAtivo}
          onClose={() => setShowConverter(false)}
          onConvertido={handleConverterSalvo}
        />
      )}

      {/* Modal: enviar por WhatsApp */}
      {showWpp && orcAtivo && (
        <ModalEnviarWhatsApp
          orc={orcAtivo}
          onClose={() => setShowWpp(false)}
          onEnviado={handleWppEnviado}
        />
      )}

      {toast && <Toast message={toast.msg} type={toast.tipo} onClose={() => setToast(null)} />}
    </div>
  )
}

// ─── Modal: Novo Orçamento ────────────────────────────────────────────────────

function ModalNovoOrcamento({ onClose, onSalvo }) {
  const EMPTY = {
    cliente: '', cliente_nome: '', cliente_telefone: '',
    tipo_evento: '', data_evento: '', validade: '',
    desconto: '0', observacoes: '', itens: [],
  }
  const [form,     setForm]     = useState(EMPTY)
  const [produtos, setProdutos] = useState([])
  const [saving,   setSaving]   = useState(false)
  const [erro,     setErro]     = useState('')

  // Busca de cliente CRM
  const [buscaCliente,    setBuscaCliente]    = useState('')
  const [clienteOptions,  setClienteOptions]  = useState([])
  const [clienteSel,      setClienteSel]      = useState(null)
  const [buscandoCliente, setBuscandoCliente] = useState(false)

  // Item em edição
  const EMPTY_ITEM = { produto: '', nome: '', preco_unit: '', quantidade: '1', observacao: '' }
  const [novoItem, setNovoItem] = useState(EMPTY_ITEM)

  useEffect(() => {
    pdvApi.listProdutos({ ativo: 'true', page_size: 500 }).then(r => setProdutos(r.data.results ?? r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    if (!buscaCliente || buscaCliente.length < 2) { setClienteOptions([]); return }
    setBuscandoCliente(true)
    const t = setTimeout(async () => {
      try {
        const r = await clientesApi.list({ search: buscaCliente, status: 'ativo' })
        setClienteOptions(r.data.results ?? r.data)
      } finally { setBuscandoCliente(false) }
    }, 350)
    return () => clearTimeout(t)
  }, [buscaCliente])

  function set(field, value) { setForm(f => ({ ...f, [field]: value })) }

  function handleClienteSel(c) {
    setClienteSel(c)
    set('cliente', String(c.id))
    set('cliente_nome', '')
    set('cliente_telefone', '')
    setClienteOptions([])
    setBuscaCliente('')
  }

  function handleClienteClear() {
    setClienteSel(null)
    set('cliente', '')
    set('cliente_nome', '')
    set('cliente_telefone', '')
  }

  function handleProdutoItem(e) {
    const id = e.target.value
    if (!id) { setNovoItem(i => ({ ...i, produto: '', nome: '', preco_unit: '' })); return }
    const p = produtos.find(p => String(p.id) === id)
    if (p) setNovoItem(i => ({ ...i, produto: id, nome: p.nome, preco_unit: String(p.preco) }))
  }

  function addItem() {
    if (!novoItem.nome || !novoItem.preco_unit) return
    const qty   = parseInt(novoItem.quantidade) || 1
    const price = parseFloat(novoItem.preco_unit) || 0
    setForm(f => ({
      ...f,
      itens: [...f.itens, { ...novoItem, quantidade: qty, preco_unit: price, preco_total: price * qty }],
    }))
    setNovoItem(EMPTY_ITEM)
  }

  function removeItem(idx) {
    setForm(f => ({ ...f, itens: f.itens.filter((_, i) => i !== idx) }))
  }

  const subtotal   = form.itens.reduce((s, i) => s + i.preco_total, 0)
  const desconto   = parseFloat(form.desconto) || 0
  const valorTotal = Math.max(subtotal - desconto, 0)

  async function handleSalvar() {
    if (!form.cliente && !form.cliente_nome) { setErro('Informe o cliente ou nome do cliente.'); return }
    setSaving(true); setErro('')
    try {
      const payload = {
        cliente:          form.cliente || null,
        cliente_nome:     form.cliente_nome,
        cliente_telefone: form.cliente_telefone,
        tipo_evento:      form.tipo_evento || '',
        data_evento:      form.data_evento || null,
        validade:         form.validade || null,
        desconto:         desconto,
        observacoes:      form.observacoes,
        itens: form.itens.map(i => ({
          produto:    i.produto || null,
          nome:       i.nome,
          preco_unit: i.preco_unit,
          quantidade: i.quantidade,
          observacao: i.observacao,
        })),
      }
      const res = await orcamentosApi.create(payload)
      onSalvo(res.data)
    } catch (e) {
      const errs = e?.response?.data
      setErro(typeof errs === 'string' ? errs : JSON.stringify(errs))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open title="Novo Orçamento" onClose={onClose} wide>
      <div className={styles.formGrid}>
        {/* Cliente */}
        <div className={styles.formGroup} style={{ gridColumn: '1 / -1' }}>
          <label>Cliente do CRM</label>
          {clienteSel ? (
            <div className={styles.clienteSelecionado}>
              <i className="ti ti-user" />
              <span>{clienteSel.nome}</span>
              {clienteSel.telefone_principal && (
                <span className={styles.clienteTel}>{clienteSel.telefone_principal}</span>
              )}
              <button onClick={handleClienteClear}><i className="ti ti-x" /></button>
            </div>
          ) : (
            <div className={styles.clienteBusca}>
              <i className="ti ti-search" />
              <input
                placeholder="Digite o nome ou telefone para buscar…"
                value={buscaCliente}
                onChange={e => setBuscaCliente(e.target.value)}
              />
              {buscandoCliente && <Spinner size={14} />}
              {clienteOptions.length > 0 && (
                <div className={styles.clienteDropdown}>
                  {clienteOptions.map(c => (
                    <button key={c.id} onClick={() => handleClienteSel(c)}>
                      <strong>{c.nome}</strong>
                      {c.telefone_principal && <span>{c.telefone_principal}</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
        {!clienteSel && (
          <>
            <div className={styles.formGroup}>
              <label>Nome do cliente *</label>
              <input value={form.cliente_nome} onChange={e => set('cliente_nome', e.target.value)} placeholder="Nome completo" />
            </div>
            <div className={styles.formGroup}>
              <label>Telefone</label>
              <input value={form.cliente_telefone} onChange={e => set('cliente_telefone', e.target.value)} placeholder="(86) 9 0000-0000" />
            </div>
          </>
        )}

        {/* Tipo evento */}
        <div className={styles.formGroup}>
          <label>Tipo de evento</label>
          <select value={form.tipo_evento} onChange={e => set('tipo_evento', e.target.value)}>
            <option value="">— Não definido —</option>
            {Object.entries(TIPO_EVENTO_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>

        {/* Datas */}
        <div className={styles.formGroup}>
          <label>Data prevista do evento</label>
          <input type="date" value={form.data_evento} onChange={e => set('data_evento', e.target.value)} />
        </div>
        <div className={styles.formGroup}>
          <label>Validade do orçamento</label>
          <input type="date" value={form.validade} onChange={e => set('validade', e.target.value)} />
        </div>
        <div className={styles.formGroup}>
          <label>Desconto (R$)</label>
          <input type="number" min="0" step="0.01" value={form.desconto} onChange={e => set('desconto', e.target.value)} />
        </div>

        {/* Observações */}
        <div className={styles.formGroup} style={{ gridColumn: '1 / -1' }}>
          <label>Observações</label>
          <textarea rows={2} value={form.observacoes} onChange={e => set('observacoes', e.target.value)} />
        </div>
      </div>

      {/* Itens */}
      <div className={styles.itensSection}>
        <h3 className={styles.itensTitulo}>Itens do orçamento</h3>

        <div className={styles.addItemCard}>
          <div className={styles.addItemRow1}>
            <select value={novoItem.produto} onChange={handleProdutoItem} className={styles.selProduto}>
              <option value="">— Selecionar do catálogo —</option>
              {produtos.map(p => <option key={p.id} value={p.id}>{p.nome} — {fmt(p.preco)}</option>)}
            </select>
          </div>
          <div className={styles.addItemRow2}>
            <input
              placeholder="Nome do item *"
              value={novoItem.nome}
              onChange={e => setNovoItem(i => ({ ...i, nome: e.target.value }))}
              className={styles.inputNome}
            />
            <input
              type="number" placeholder="Preço unit."
              min="0" step="0.01"
              value={novoItem.preco_unit}
              onChange={e => setNovoItem(i => ({ ...i, preco_unit: e.target.value }))}
              className={styles.inputPreco}
            />
            <input
              type="number" placeholder="Qtd"
              min="1"
              value={novoItem.quantidade}
              onChange={e => setNovoItem(i => ({ ...i, quantidade: e.target.value }))}
              className={styles.inputQtd}
            />
            <Btn variant="secondary" onClick={addItem}>
              <i className="ti ti-plus" /> Adicionar
            </Btn>
          </div>
        </div>

        {form.itens.length > 0 && (
          <table className={styles.itensTable}>
            <thead>
              <tr>
                <th>Item</th>
                <th className={styles.thCenter}>Qtd</th>
                <th className={styles.thRight}>Unit.</th>
                <th className={styles.thRight}>Total</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {form.itens.map((item, idx) => (
                <tr key={idx}>
                  <td>{item.nome}</td>
                  <td className={styles.tdCenter}>{item.quantidade}</td>
                  <td className={styles.tdRight}>{fmt(item.preco_unit)}</td>
                  <td className={`${styles.tdRight} ${styles.tdTotal}`}>{fmt(item.preco_total)}</td>
                  <td><button className={styles.btnRemove} onClick={() => removeItem(idx)}><i className="ti ti-trash" /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className={styles.totais}>
          <span>Subtotal: <strong>{fmt(subtotal)}</strong></span>
          {desconto > 0 && <span className={styles.desconto}>— Desconto: <strong>{fmt(desconto)}</strong></span>}
          <span className={styles.totalFinal}>Total: <strong>{fmt(valorTotal)}</strong></span>
        </div>
      </div>

      {erro && <p className={styles.erro}>{erro}</p>}

      <div className={styles.modalActions}>
        <Btn variant="ghost" onClick={onClose}>Cancelar</Btn>
        <Btn onClick={handleSalvar} loading={saving}>Criar orçamento</Btn>
      </div>
    </Modal>
  )
}

// ─── Modal: Detalhe do Orçamento ──────────────────────────────────────────────

function ModalDetalheOrcamento({ orc, onClose, onAcao, onPdf, onEnviarWpp, onRemoverItem, onItemAdicionado, onConverter }) {
  const sc = STATUS_CONFIG[orc.status] || {}
  const [produtos,  setProdutos]  = useState([])
  const [novoItem,  setNovoItem]  = useState({ produto: '', nome: '', preco_unit: '', quantidade: '1', observacao: '' })
  const [addingItem, setAddingItem] = useState(false)

  useEffect(() => {
    pdvApi.listProdutos({ ativo: 'true', page_size: 500 }).then(r => setProdutos(r.data.results ?? r.data)).catch(() => {})
  }, [])

  function handleProdutoItem(e) {
    const id = e.target.value
    if (!id) { setNovoItem(i => ({ ...i, produto: '', nome: '', preco_unit: '' })); return }
    const p = produtos.find(p => String(p.id) === id)
    if (p) setNovoItem(i => ({ ...i, produto: id, nome: p.nome, preco_unit: String(p.preco) }))
  }

  async function handleAddItem() {
    if (!novoItem.nome || !novoItem.preco_unit) return
    setAddingItem(true)
    try {
      const res = await orcamentosApi.adicionarItem(orc.id, {
        produto:    novoItem.produto || null,
        nome:       novoItem.nome,
        preco_unit: parseFloat(novoItem.preco_unit),
        quantidade: parseInt(novoItem.quantidade) || 1,
        observacao: novoItem.observacao,
      })
      onItemAdicionado(res.data)
      setNovoItem({ produto: '', nome: '', preco_unit: '', quantidade: '1', observacao: '' })
    } catch { /* silencioso */ } finally { setAddingItem(false) }
  }

  const podeEditar = orc.status === 'rascunho' || orc.status === 'enviado'

  return (
    <Modal open title={`Orçamento ${orc.numero}`} onClose={onClose} wide>
      {/* Cabeçalho do orçamento */}
      <div className={styles.detHeader}>
        <div className={styles.detInfo}>
          <div className={styles.detRow}><i className="ti ti-user" /> <strong>{orc.nome_cliente_display}</strong></div>
          {orc.telefone_display && <div className={styles.detRow}><i className="ti ti-phone" /> {orc.telefone_display}</div>}
          {orc.tipo_evento && <div className={styles.detRow}><i className="ti ti-calendar-event" /> {TIPO_EVENTO_LABELS[orc.tipo_evento] || orc.tipo_evento}</div>}
          {orc.data_evento && <div className={styles.detRow}><i className="ti ti-calendar" /> Data prevista: {fmtData(orc.data_evento)}</div>}
          {orc.validade && <div className={styles.detRow}><i className="ti ti-clock" /> Válido até: {fmtData(orc.validade)}</div>}
          {orc.observacoes && <div className={styles.detRow}><i className="ti ti-notes" /> {orc.observacoes}</div>}
        </div>
        <div className={styles.detStatus}>
          <span className={styles.badgeLg} style={{ background: sc.color + '22', color: sc.color }}>{sc.label}</span>
          {orc.evento_numero && (
            <div className={styles.eventoLink}><i className="ti ti-calendar-event" /> Evento: <strong>{orc.evento_numero}</strong></div>
          )}
        </div>
      </div>

      {/* Itens */}
      <div className={styles.itensSection}>
        <h3 className={styles.itensTitulo}>Itens</h3>
        {orc.itens && orc.itens.length > 0 ? (
          <table className={styles.itensTable}>
            <thead>
              <tr>
                <th>Item</th>
                <th className={styles.thCenter}>Qtd</th>
                <th className={styles.thRight}>Unit.</th>
                <th className={styles.thRight}>Total</th>
                {podeEditar && <th></th>}
              </tr>
            </thead>
            <tbody>
              {orc.itens.map(item => (
                <tr key={item.id}>
                  <td>{item.nome}</td>
                  <td className={styles.tdCenter}>{item.quantidade}</td>
                  <td className={styles.tdRight}>{fmt(item.preco_unit)}</td>
                  <td className={`${styles.tdRight} ${styles.tdTotal}`}>{fmt(item.preco_total)}</td>
                  {podeEditar && (
                    <td><button className={styles.btnRemove} onClick={() => onRemoverItem(item.id)}><i className="ti ti-trash" /></button></td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className={styles.semItens}>Nenhum item adicionado.</p>
        )}

        {podeEditar && (
          <div className={styles.addItemCard} style={{ marginTop: 8 }}>
            <div className={styles.addItemRow1}>
              <select value={novoItem.produto} onChange={handleProdutoItem} className={styles.selProduto}>
                <option value="">— Selecionar do catálogo —</option>
                {produtos.map(p => <option key={p.id} value={p.id}>{p.nome} — {fmt(p.preco)}</option>)}
              </select>
            </div>
            <div className={styles.addItemRow2}>
              <input
                placeholder="Nome do item *"
                value={novoItem.nome}
                onChange={e => setNovoItem(i => ({ ...i, nome: e.target.value }))}
                className={styles.inputNome}
              />
              <input
                type="number" placeholder="Preço unit."
                min="0" step="0.01"
                value={novoItem.preco_unit}
                onChange={e => setNovoItem(i => ({ ...i, preco_unit: e.target.value }))}
                className={styles.inputPreco}
              />
              <input
                type="number" placeholder="Qtd"
                min="1"
                value={novoItem.quantidade}
                onChange={e => setNovoItem(i => ({ ...i, quantidade: e.target.value }))}
                className={styles.inputQtd}
              />
              <Btn variant="secondary" onClick={handleAddItem} loading={addingItem}>
                <i className="ti ti-plus" /> Adicionar
              </Btn>
            </div>
          </div>
        )}

        <div className={styles.totais}>
          {parseFloat(orc.desconto) > 0 && <span>Desconto: <strong>-{fmt(orc.desconto)}</strong></span>}
          <span className={styles.totalFinal}>Total: <strong>{fmt(orc.valor_total)}</strong></span>
        </div>
      </div>

      {/* Ações */}
      <div className={styles.modalActions} style={{ flexWrap: 'wrap' }}>
        <Btn variant="ghost" onClick={onClose}>Fechar</Btn>
        <Btn variant="secondary" onClick={() => onPdf(orc)} title="Exportar PDF com papel timbrado">
          <i className="ti ti-file-type-pdf" /> Exportar PDF
        </Btn>
        <Btn
          variant="secondary"
          onClick={() => onEnviarWpp(orc)}
          className={styles.btnWpp}
          title={orc.telefone_display ? `Enviar PDF para ${orc.telefone_display}` : 'Sem telefone de contato'}
        >
          <i className="ti ti-brand-whatsapp" /> Enviar por WhatsApp
        </Btn>
        <div style={{ flex: 1 }} />
        {orc.pode_restaurar && (
          <Btn variant="secondary" onClick={() => onAcao('restaurar', orc)}>
            <i className="ti ti-refresh" /> Restaurar
          </Btn>
        )}
        {orc.pode_recusar && (
          <Btn variant="danger" onClick={() => onAcao('recusar', orc)}>
            <i className="ti ti-x" /> Recusar
          </Btn>
        )}
        {orc.pode_cancelar && orc.status === 'rascunho' && (
          <Btn variant="danger" onClick={() => onAcao('excluir', orc)}>
            <i className="ti ti-trash" /> Excluir
          </Btn>
        )}
        {orc.pode_enviar && (
          <Btn variant="secondary" onClick={() => onAcao('enviar', orc)}>
            <i className="ti ti-send" /> Marcar como enviado
          </Btn>
        )}
        {orc.pode_aprovar && (
          <Btn onClick={() => onAcao('aprovar', orc)}>
            <i className="ti ti-check" /> Aprovar
          </Btn>
        )}
        {orc.pode_converter && (
          <Btn onClick={onConverter} style={{ background: 'var(--caramelo)' }}>
            <i className="ti ti-calendar-plus" /> Converter em evento
          </Btn>
        )}
      </div>
    </Modal>
  )
}

// ─── Modal: Enviar por WhatsApp ───────────────────────────────────────────────

function ModalEnviarWhatsApp({ orc, onClose, onEnviado }) {
  const [mensagem, setMensagem] = useState('')
  const [sending,  setSending]  = useState(false)
  const [erro,     setErro]     = useState('')

  async function handleEnviar() {
    setSending(true)
    setErro('')
    try {
      const res = await orcamentosApi.enviarWhatsApp(orc.id, { mensagem })
      onEnviado(res.data)
    } catch (e) {
      const data = e?.response?.data
      setErro(data?.mensagem || data?.detail || 'Erro ao enviar via WhatsApp. Verifique as credenciais Z-API em Configurações.')
    } finally {
      setSending(false)
    }
  }

  return (
    <Modal open title="Enviar por WhatsApp" onClose={onClose}>
      <div className={styles.wppDestinatarioCard}>
        <i className="ti ti-brand-whatsapp" style={{ color: '#25D366', fontSize: 22 }} />
        <div>
          <div className={styles.wppLabel}>Destinatário</div>
          <div className={styles.wppNome}>{orc.nome_cliente_display}</div>
          <div className={styles.wppFone}>{orc.telefone_display}</div>
        </div>
      </div>

      <div className={styles.wppDocCard}>
        <i className="ti ti-file-type-pdf" style={{ color: '#DC2626', fontSize: 18 }} />
        <span>{orc.numero}.pdf — Proposta Comercial Arretado Doces</span>
      </div>

      <div className={styles.formGroup} style={{ marginTop: 14 }}>
        <label>Mensagem que acompanha o PDF (opcional)</label>
        <textarea
          rows={3}
          value={mensagem}
          onChange={e => setMensagem(e.target.value)}
          placeholder={`Olá, ${orc.nome_cliente_display.split(' ')[0]}! Segue a proposta comercial conforme conversamos. Qualquer dúvida, é só chamar! 🍬`}
        />
      </div>

      {erro && <p className={styles.erro}>{erro}</p>}

      <div className={styles.modalActions}>
        <Btn variant="ghost" onClick={onClose} disabled={sending}>Cancelar</Btn>
        <Btn onClick={handleEnviar} loading={sending} className={styles.btnWppSend}>
          <i className="ti ti-brand-whatsapp" /> Enviar PDF
        </Btn>
      </div>
    </Modal>
  )
}

// ─── Modal: Converter em Evento ───────────────────────────────────────────────

function ModalConverterEvento({ orc, onClose, onConvertido }) {
  const [form,    setForm]    = useState({
    data_evento:     orc.data_evento || '',
    hora_evento:     '',
    tipo_entrega:    'retirada_loja',
    endereco_avulso: '',
    sinal_pago:      '0',
  })
  const [saving, setSaving] = useState(false)
  const [erro,   setErro]   = useState('')

  function set(field, value) { setForm(f => ({ ...f, [field]: value })) }

  async function handleConverter() {
    if (!form.data_evento) { setErro('Informe a data do evento.'); return }
    setSaving(true); setErro('')
    try {
      const payload = {
        data_evento:     form.data_evento,
        hora_evento:     form.hora_evento || null,
        tipo_entrega:    form.tipo_entrega,
        endereco_avulso: form.endereco_avulso,
        sinal_pago:      parseFloat(form.sinal_pago) || 0,
      }
      const res = await orcamentosApi.converterEmEvento(orc.id, payload)
      onConvertido(res.data.evento)
    } catch (e) {
      setErro(e?.response?.data?.detail || 'Erro ao converter.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open title="Converter em Evento" onClose={onClose}>
      <p className={styles.converterDesc}>
        Um novo evento será criado com os itens e dados do orçamento <strong>{orc.numero}</strong>.
        O orçamento ficará como <em>Convertido</em> e terá um link para o evento gerado.
      </p>
      <div className={styles.formGrid}>
        <div className={styles.formGroup}>
          <label>Data do evento *</label>
          <input type="date" value={form.data_evento} onChange={e => set('data_evento', e.target.value)} />
        </div>
        <div className={styles.formGroup}>
          <label>Horário do evento</label>
          <input type="time" value={form.hora_evento} onChange={e => set('hora_evento', e.target.value)} />
        </div>
        <div className={styles.formGroup}>
          <label>Tipo de entrega</label>
          <select value={form.tipo_entrega} onChange={e => set('tipo_entrega', e.target.value)}>
            <option value="retirada_loja">Retirada na loja</option>
            <option value="entrega_local">Entrega no local da festa</option>
          </select>
        </div>
        <div className={styles.formGroup}>
          <label>Sinal / entrada (R$)</label>
          <input type="number" min="0" step="0.01" value={form.sinal_pago} onChange={e => set('sinal_pago', e.target.value)} />
        </div>
        {form.tipo_entrega === 'entrega_local' && (
          <div className={styles.formGroup} style={{ gridColumn: '1 / -1' }}>
            <label>Endereço de entrega</label>
            <input value={form.endereco_avulso} onChange={e => set('endereco_avulso', e.target.value)} placeholder="Endereço completo" />
          </div>
        )}
      </div>
      {erro && <p className={styles.erro}>{erro}</p>}
      <div className={styles.modalActions}>
        <Btn variant="ghost" onClick={onClose}>Cancelar</Btn>
        <Btn onClick={handleConverter} loading={saving}>
          <i className="ti ti-calendar-plus" /> Criar evento
        </Btn>
      </div>
    </Modal>
  )
}
