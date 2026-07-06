import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { orcamentosApi, contratosApi, clientesApi, pdvApi, locaisEventoApi, taxasEntregaApi, configEntregaApi } from '../api/services'
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
  const [showContrato,  setShowContrato]  = useState(false)
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
          onEmitirContrato={() => setShowContrato(true)}
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

      {/* Modal: emitir contrato */}
      {showContrato && orcAtivo && (
        <ModalEmitirContrato
          orc={orcAtivo}
          onClose={() => setShowContrato(false)}
          onGerado={() => loadOrcamentos()}
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
    tipo_entrega: 'retirada_loja', local: '', endereco_avulso: '',
    bairro_entrega: '', taxa_entrega: '0',
    desconto: '0', observacoes: '', itens: [],
  }
  const [form,        setForm]        = useState(EMPTY)
  const [produtos,    setProdutos]    = useState([])
  const [locais,      setLocais]      = useState([])
  const [taxasBairro, setTaxasBairro] = useState([])
  const [fretePadrao, setFretePadrao] = useState('0')
  const [saving,      setSaving]      = useState(false)
  const [erro,        setErro]        = useState('')

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
    locaisEventoApi.list({ ativo: 'true' }).then(r => setLocais(r.data.results ?? r.data)).catch(() => {})
    taxasEntregaApi.list({ ativo: true }).then(r => setTaxasBairro(r.data.results ?? r.data)).catch(() => {})
    configEntregaApi.get().then(r => setFretePadrao(String(r.data.frete_padrao))).catch(() => {})
  }, [])

  // Preenche a taxa automaticamente a partir do bairro do local cadastrado
  useEffect(() => {
    if (form.tipo_entrega !== 'entrega_local' || !form.local) return
    const local = locais.find(l => String(l.id) === String(form.local))
    if (!local?.bairro) return
    const t = taxasBairro.find(x => x.bairro.toLowerCase() === local.bairro.toLowerCase())
    setForm(f => ({ ...f, bairro_entrega: local.bairro, taxa_entrega: t ? String(t.taxa) : f.taxa_entrega }))
  }, [form.local, form.tipo_entrega, locais, taxasBairro])

  // Ao entrar em modo entrega: tenta o bairro do endereço do cliente selecionado;
  // sem bairro cadastrado, cai no frete padrão configurado
  useEffect(() => {
    if (form.tipo_entrega !== 'entrega_local' || form.local || form.bairro_entrega) return
    const bairroCliente = clienteSel?.endereco_principal?.bairro
    if (bairroCliente) {
      const t = taxasBairro.find(x => x.bairro.toLowerCase() === bairroCliente.toLowerCase())
      if (t) { setForm(f => ({ ...f, bairro_entrega: t.bairro, taxa_entrega: String(t.taxa) })); return }
    }
    setForm(f => (f.taxa_entrega && f.taxa_entrega !== '0' ? f : { ...f, taxa_entrega: fretePadrao }))
  }, [form.tipo_entrega, form.local, form.bairro_entrega, clienteSel, taxasBairro, fretePadrao])

  function selecionarBairroAvulso(bairro) {
    const t = taxasBairro.find(x => x.bairro === bairro)
    setForm(f => ({ ...f, bairro_entrega: bairro, taxa_entrega: t ? String(t.taxa) : f.taxa_entrega }))
  }

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

  const subtotal     = form.itens.reduce((s, i) => s + i.preco_total, 0)
  const desconto     = parseFloat(form.desconto) || 0
  const taxaEntrega  = form.tipo_entrega === 'entrega_local' ? (parseFloat(form.taxa_entrega) || 0) : 0
  const valorTotal   = Math.max(subtotal - desconto, 0) + taxaEntrega

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
        tipo_entrega:     form.tipo_entrega,
        local:            form.tipo_entrega === 'entrega_local' && form.local ? Number(form.local) : null,
        endereco_avulso:  form.tipo_entrega === 'entrega_local' && !form.local ? form.endereco_avulso : '',
        bairro_entrega:   form.tipo_entrega === 'entrega_local' ? form.bairro_entrega : '',
        taxa_entrega:     taxaEntrega,
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

        {/* Entrega */}
        <div className={styles.formGroup} style={{ gridColumn: '1 / -1' }}>
          <label>Tipo de entrega</label>
          <div className={styles.radioGroup}>
            <label className={`${styles.radioCard} ${form.tipo_entrega === 'retirada_loja' ? styles.radioCardActive : ''}`}>
              <input type="radio" value="retirada_loja" checked={form.tipo_entrega === 'retirada_loja'} onChange={e => set('tipo_entrega', e.target.value)} />
              <i className="ti ti-building-store" /> Retirada na loja
            </label>
            <label className={`${styles.radioCard} ${form.tipo_entrega === 'entrega_local' ? styles.radioCardActive : ''}`}>
              <input type="radio" value="entrega_local" checked={form.tipo_entrega === 'entrega_local'} onChange={e => set('tipo_entrega', e.target.value)} />
              <i className="ti ti-truck-delivery" /> Entrega no local
            </label>
          </div>
        </div>

        {form.tipo_entrega === 'entrega_local' && (
          <>
            <div className={styles.formGroup} style={{ gridColumn: '1 / -1' }}>
              <label>Local cadastrado</label>
              <select value={form.local} onChange={e => set('local', e.target.value)}>
                <option value="">— Endereço avulso —</option>
                {locais.map(l => <option key={l.id} value={l.id}>{l.nome} — {l.bairro}</option>)}
              </select>
            </div>
            {!form.local && (
              <>
                <div className={styles.formGroup} style={{ gridColumn: '1 / -1' }}>
                  <label>Endereço do local</label>
                  <input value={form.endereco_avulso} onChange={e => set('endereco_avulso', e.target.value)} placeholder="Rua, número, bairro…" />
                </div>
                <div className={styles.formGroup}>
                  <label>Bairro (para calcular a taxa)</label>
                  <select value={form.bairro_entrega} onChange={e => selecionarBairroAvulso(e.target.value)}>
                    <option value="">Selecione o bairro…</option>
                    {taxasBairro.map(t => (
                      <option key={t.id} value={t.bairro}>{t.bairro} — R$ {Number(t.taxa).toFixed(2)}</option>
                    ))}
                  </select>
                </div>
              </>
            )}
            <div className={styles.formGroup}>
              <label>Taxa de entrega (R$)</label>
              <input type="number" min="0" step="0.01" value={form.taxa_entrega} onChange={e => set('taxa_entrega', e.target.value)} />
            </div>
          </>
        )}

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
          {taxaEntrega > 0 && <span>+ Taxa de entrega: <strong>{fmt(taxaEntrega)}</strong></span>}
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

function ModalDetalheOrcamento({ orc, onClose, onAcao, onPdf, onEnviarWpp, onRemoverItem, onItemAdicionado, onConverter, onEmitirContrato }) {
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
          {orc.tipo_entrega === 'entrega_local' && (
            <div className={styles.detRow}>
              <i className="ti ti-truck-delivery" />
              {orc.local_nome || orc.endereco_avulso || 'Entrega no local'}
              {orc.bairro_entrega ? ` — ${orc.bairro_entrega}` : ''}
            </div>
          )}
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
          {parseFloat(orc.taxa_entrega) > 0 && <span>Taxa de entrega: <strong>{fmt(orc.taxa_entrega)}</strong></span>}
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
        {orc.status === 'aprovado' && (
          <Btn onClick={onEmitirContrato} style={{ background: 'var(--caramelo)' }}>
            <i className="ti ti-file-signature" /> Emitir Contrato
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
    tipo_entrega:    orc.tipo_entrega || 'retirada_loja',
    local:           orc.local || '',
    endereco_avulso: orc.endereco_avulso || '',
    bairro_entrega:  orc.bairro_entrega || '',
    taxa_entrega:    String(orc.taxa_entrega || '0'),
    sinal_pago:      '0',
  })
  const [locais,      setLocais]      = useState([])
  const [taxasBairro, setTaxasBairro] = useState([])
  const [saving, setSaving] = useState(false)
  const [erro,   setErro]   = useState('')

  useEffect(() => {
    locaisEventoApi.list({ ativo: 'true' }).then(r => setLocais(r.data.results ?? r.data)).catch(() => {})
    taxasEntregaApi.list({ ativo: true }).then(r => setTaxasBairro(r.data.results ?? r.data)).catch(() => {})
  }, [])

  function set(field, value) { setForm(f => ({ ...f, [field]: value })) }

  function selecionarBairroAvulso(bairro) {
    const t = taxasBairro.find(x => x.bairro === bairro)
    setForm(f => ({ ...f, bairro_entrega: bairro, taxa_entrega: t ? String(t.taxa) : f.taxa_entrega }))
  }

  async function handleConverter() {
    if (!form.data_evento) { setErro('Informe a data do evento.'); return }
    setSaving(true); setErro('')
    try {
      const payload = {
        data_evento:     form.data_evento,
        hora_evento:     form.hora_evento || null,
        tipo_entrega:    form.tipo_entrega,
        local:           form.tipo_entrega === 'entrega_local' && form.local ? Number(form.local) : null,
        endereco_avulso: form.tipo_entrega === 'entrega_local' && !form.local ? form.endereco_avulso : '',
        bairro_entrega:  form.tipo_entrega === 'entrega_local' ? form.bairro_entrega : '',
        taxa_entrega:    form.tipo_entrega === 'entrega_local' ? (parseFloat(form.taxa_entrega) || 0) : 0,
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
          <>
            <div className={styles.formGroup} style={{ gridColumn: '1 / -1' }}>
              <label>Local cadastrado</label>
              <select value={form.local} onChange={e => set('local', e.target.value)}>
                <option value="">— Endereço avulso —</option>
                {locais.map(l => <option key={l.id} value={l.id}>{l.nome} — {l.bairro}</option>)}
              </select>
            </div>
            {!form.local && (
              <>
                <div className={styles.formGroup} style={{ gridColumn: '1 / -1' }}>
                  <label>Endereço de entrega</label>
                  <input value={form.endereco_avulso} onChange={e => set('endereco_avulso', e.target.value)} placeholder="Endereço completo" />
                </div>
                <div className={styles.formGroup}>
                  <label>Bairro (para calcular a taxa)</label>
                  <select value={form.bairro_entrega} onChange={e => selecionarBairroAvulso(e.target.value)}>
                    <option value="">Selecione o bairro…</option>
                    {taxasBairro.map(t => (
                      <option key={t.id} value={t.bairro}>{t.bairro} — R$ {Number(t.taxa).toFixed(2)}</option>
                    ))}
                  </select>
                </div>
              </>
            )}
            <div className={styles.formGroup}>
              <label>Taxa de entrega (R$)</label>
              <input type="number" min="0" step="0.01" value={form.taxa_entrega} onChange={e => set('taxa_entrega', e.target.value)} />
            </div>
          </>
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

// ─── Modal: Emitir Contrato ───────────────────────────────────────────────────

const ESTADO_CIVIL_OPTS = [
  ['solteiro',      'Solteiro(a)'],
  ['casado',        'Casado(a)'],
  ['divorciado',    'Divorciado(a)'],
  ['viuvo',         'Viúvo(a)'],
  ['uniao_estavel', 'União Estável'],
]

function ModalEmitirContrato({ orc, onClose, onGerado }) {
  const [loadingCliente,       setLoadingCliente]       = useState(true)
  const [temEnderecoPrincipal, setTemEnderecoPrincipal] = useState(false)
  const [form, setForm] = useState({
    cpf: '', rg: '', rg_orgao_emissor: '', nacionalidade: 'brasileira',
    profissao: '', estado_civil: '', endereco_avulso: '',
  })
  const [saving, setSaving] = useState(false)
  const [erro,   setErro]   = useState('')
  const [contrato, setContrato] = useState(null)

  const [mensagem,   setMensagem]   = useState('')
  const [sendingWpp, setSendingWpp] = useState(false)
  const [erroWpp,    setErroWpp]    = useState('')

  useEffect(() => {
    if (!orc.cliente) { setLoadingCliente(false); return }
    clientesApi.get(orc.cliente)
      .then(r => {
        const c = r.data
        setForm(f => ({
          ...f,
          cpf:              c.cpf || '',
          rg:               c.rg || '',
          rg_orgao_emissor: c.rg_orgao_emissor || '',
          nacionalidade:    c.nacionalidade || 'brasileira',
          profissao:        c.profissao || '',
          estado_civil:     c.estado_civil || '',
        }))
        setTemEnderecoPrincipal((c.enderecos || []).some(e => e.principal))
      })
      .finally(() => setLoadingCliente(false))
  }, [orc.cliente])

  function set(field, value) { setForm(f => ({ ...f, [field]: value })) }

  async function handleGerar() {
    if (!form.cpf || !form.rg || !form.nacionalidade || !form.profissao || !form.estado_civil) {
      setErro('Preencha CPF, RG, nacionalidade, profissão e estado civil do CONTRATANTE.')
      return
    }
    if (!temEnderecoPrincipal && !form.endereco_avulso) {
      setErro('O cliente não tem endereço principal cadastrado — informe um endereço para o contrato.')
      return
    }
    setSaving(true); setErro('')
    try {
      const res = await orcamentosApi.gerarContrato(orc.id, form)
      setContrato(res.data)
      onGerado?.(res.data)
    } catch (e) {
      const data = e?.response?.data
      const msg = data?.mensagem || (data?.campos_faltando ? `Faltam: ${data.campos_faltando.join(', ')}` : data?.detail)
      setErro(msg || 'Erro ao emitir contrato.')
    } finally {
      setSaving(false)
    }
  }

  async function handleVerPdf() {
    try {
      const res = await contratosApi.pdf(contrato.id)
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      window.open(url, '_blank')
    } catch {
      setErro('Erro ao gerar PDF do contrato.')
    }
  }

  async function handleEnviarWpp() {
    setSendingWpp(true); setErroWpp('')
    try {
      const res = await contratosApi.enviarWhatsApp(contrato.id, { mensagem })
      setContrato(res.data)
    } catch (e) {
      const data = e?.response?.data
      setErroWpp(data?.mensagem || data?.detail || 'Erro ao enviar via WhatsApp.')
    } finally {
      setSendingWpp(false)
    }
  }

  if (loadingCliente) {
    return (
      <Modal open title="Emitir Contrato" onClose={onClose}>
        <div className={styles.spinnerWrap}><Spinner /></div>
      </Modal>
    )
  }

  if (contrato) {
    return (
      <Modal open title={`Contrato ${contrato.numero}`} onClose={onClose}>
        <p className={styles.converterDesc}>
          Contrato gerado com sucesso para <strong>{contrato.contratante_nome}</strong>.
        </p>
        <div className={styles.wppDocCard}>
          <i className="ti ti-file-type-pdf" style={{ color: '#DC2626', fontSize: 18 }} />
          <span>{contrato.numero}.pdf — Contrato de Aquisição de Produtos</span>
        </div>
        <div className={styles.formGroup} style={{ marginTop: 14 }}>
          <label>Mensagem que acompanha o PDF (opcional)</label>
          <textarea
            rows={3}
            value={mensagem}
            onChange={e => setMensagem(e.target.value)}
            placeholder="Segue o contrato para assinatura. Qualquer dúvida, é só chamar!"
          />
        </div>
        {erroWpp && <p className={styles.erro}>{erroWpp}</p>}
        <div className={styles.modalActions}>
          <Btn variant="ghost" onClick={onClose}>Fechar</Btn>
          <Btn variant="secondary" onClick={handleVerPdf}>
            <i className="ti ti-file-type-pdf" /> Ver PDF
          </Btn>
          {contrato.status === 'enviado' ? (
            <span className={styles.badgeLg} style={{ background: '#05966922', color: '#059669' }}>Enviado</span>
          ) : (
            <Btn onClick={handleEnviarWpp} loading={sendingWpp} className={styles.btnWppSend}>
              <i className="ti ti-brand-whatsapp" /> Enviar por WhatsApp
            </Btn>
          )}
        </div>
      </Modal>
    )
  }

  return (
    <Modal open title="Emitir Contrato" onClose={onClose}>
      <p className={styles.converterDesc}>
        Complete os dados do CONTRATANTE para gerar o contrato do orçamento <strong>{orc.numero}</strong>.
      </p>
      <div className={styles.formGrid}>
        <div className={styles.formGroup}>
          <label>CPF *</label>
          <input value={form.cpf} onChange={e => set('cpf', e.target.value)} placeholder="000.000.000-00" />
        </div>
        <div className={styles.formGroup}>
          <label>RG *</label>
          <input value={form.rg} onChange={e => set('rg', e.target.value)} />
        </div>
        <div className={styles.formGroup}>
          <label>Órgão emissor</label>
          <input value={form.rg_orgao_emissor} onChange={e => set('rg_orgao_emissor', e.target.value)} placeholder="SSP-PI" />
        </div>
        <div className={styles.formGroup}>
          <label>Nacionalidade *</label>
          <input value={form.nacionalidade} onChange={e => set('nacionalidade', e.target.value)} />
        </div>
        <div className={styles.formGroup}>
          <label>Profissão *</label>
          <input value={form.profissao} onChange={e => set('profissao', e.target.value)} />
        </div>
        <div className={styles.formGroup}>
          <label>Estado civil *</label>
          <select value={form.estado_civil} onChange={e => set('estado_civil', e.target.value)}>
            <option value="">— Selecione —</option>
            {ESTADO_CIVIL_OPTS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        {!temEnderecoPrincipal && (
          <div className={styles.formGroup} style={{ gridColumn: '1 / -1' }}>
            <label>Endereço do CONTRATANTE * (cliente sem endereço principal cadastrado)</label>
            <input
              value={form.endereco_avulso}
              onChange={e => set('endereco_avulso', e.target.value)}
              placeholder="Rua, número, bairro, cidade/estado"
            />
          </div>
        )}
      </div>
      {erro && <p className={styles.erro}>{erro}</p>}
      <div className={styles.modalActions}>
        <Btn variant="ghost" onClick={onClose}>Cancelar</Btn>
        <Btn onClick={handleGerar} loading={saving}>
          <i className="ti ti-file-signature" /> Gerar contrato
        </Btn>
      </div>
    </Modal>
  )
}
