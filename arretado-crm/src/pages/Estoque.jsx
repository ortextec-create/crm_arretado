import { useState, useEffect, useCallback, useRef } from 'react'
import { estoqueApi, fichasApi } from '../api/services'
import { Btn, Modal, Spinner, Toast, Field, Input, Select, Empty } from '../components/ui'
import styles from './Estoque.module.css'

const fmt = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const fmtQtd = (v) => Number(v || 0).toLocaleString('pt-BR', { maximumFractionDigits: 3 })

const ABAS = ['Insumos', 'Produtos', 'Produção', 'Movimentações']

function statusInsumo(m) {
  if (Number(m.quantidade_estoque) < 0) return 'neg'
  if (Number(m.estoque_minimo) > 0 && Number(m.quantidade_estoque) < Number(m.estoque_minimo)) return 'baixo'
  return 'ok'
}

const STATUS_LABEL = { ok: 'Ok', baixo: 'Baixo', neg: 'Negativo' }

function StatusBadge({ status }) {
  return <span className={`${styles.badge} ${styles['badge_' + status]}`}>{STATUS_LABEL[status] || status}</span>
}

export default function Estoque() {
  const [aba, setAba] = useState(0)
  const [toast, setToast] = useState(null)
  const [modalConfig, setModalConfig] = useState(false)
  const showToast = (msg, tipo = 'success') => setToast({ msg, tipo })

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={`serif ${styles.title}`}><i className="ti ti-boxes" /> Estoque</h1>
          <p className={styles.subtitle}>Controle de insumos, produtos fabricados e produtos de revenda</p>
        </div>
        <Btn variant="ghost" icon="settings" onClick={() => setModalConfig(true)}>Configurações</Btn>
      </div>

      <div className={styles.tabBar}>
        {ABAS.map((label, i) => (
          <button key={i} className={`${styles.tab} ${aba === i ? styles.tabActive : ''}`} onClick={() => setAba(i)}>
            {label}
          </button>
        ))}
      </div>

      <div className={styles.abaContent}>
        {aba === 0 && <AbaInsumos onToast={showToast} />}
        {aba === 1 && <AbaProdutos onToast={showToast} />}
        {aba === 2 && <AbaProducao onToast={showToast} />}
        {aba === 3 && <AbaMovimentacoes onToast={showToast} />}
      </div>

      {modalConfig && <ModalConfiguracao onClose={() => setModalConfig(false)} onToast={showToast} />}
      {toast && <Toast message={toast.msg} type={toast.tipo} onClose={() => setToast(null)} />}
    </div>
  )
}

// ─── Aba 1: Insumos ───────────────────────────────────────────────────────────

function AbaInsumos({ onToast }) {
  const [materias, setMaterias] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [modalCompra, setModalCompra] = useState(false)
  const [modalAjuste, setModalAjuste] = useState(null) // null | { tipo_item, item }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await fichasApi.listarMaterias({ search, page_size: 200 })
      setMaterias(r.data.results ?? r.data)
    } finally { setLoading(false) }
  }, [search])

  useEffect(() => { load() }, [load])

  return (
    <div className={styles.abaInner}>
      <div className={styles.toolbarRow}>
        <div className={styles.searchBox}>
          <i className="ti ti-search" />
          <input placeholder="Buscar insumo…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className={styles.spacer} />
        <Btn variant="secondary" icon="adjustments" onClick={() => setModalAjuste({ tipo_item: 'materia_prima', item: null })}>
          Ajuste de inventário
        </Btn>
        <Btn icon="plus" onClick={() => setModalCompra(true)}>Registrar Compra</Btn>
      </div>

      {loading ? <div className={styles.center}><Spinner /></div> : materias.length === 0 ? (
        <Empty icon="wheat" message="Nenhum insumo cadastrado ainda." />
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Insumo</th><th>Unidade</th>
                <th className={styles.thRight}>Saldo</th>
                <th className={styles.thRight}>Mínimo</th>
                <th className={styles.thRight}>Custo/un</th>
                <th className={styles.thRight}>Valor em estoque</th>
                <th>Status</th><th></th>
              </tr>
            </thead>
            <tbody>
              {materias.map((m) => {
                const st = statusInsumo(m)
                const valorEstoque = Number(m.quantidade_estoque) * Number(m.custo_unitario)
                return (
                  <tr key={m.id}>
                    <td className={styles.tdNome}>{m.nome}</td>
                    <td className={styles.tdMuted}>{m.unidade_medida}</td>
                    <td className={`${styles.tdRight} ${st === 'neg' ? styles.tdVermelho : ''}`}>{fmtQtd(m.quantidade_estoque)}</td>
                    <td className={`${styles.tdRight} ${styles.tdMuted}`}>{fmtQtd(m.estoque_minimo)}</td>
                    <td className={styles.tdRight}>{fmt(m.custo_unitario)}</td>
                    <td className={`${styles.tdRight} ${valorEstoque < 0 ? styles.tdVermelho : ''}`}>{fmt(valorEstoque)}</td>
                    <td><StatusBadge status={st} /></td>
                    <td>
                      <button
                        className={styles.btnEdit}
                        title="Ajustar saldo"
                        onClick={() => setModalAjuste({ tipo_item: 'materia_prima', item: m })}
                      >
                        <i className="ti ti-edit" />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {modalCompra && (
        <ModalRegistrarCompra
          onClose={() => setModalCompra(false)}
          onSaved={() => { setModalCompra(false); load(); onToast('Entrada registrada!') }}
        />
      )}
      {modalAjuste && (
        <ModalAjusteInventario
          tipoItemInicial={modalAjuste.tipo_item}
          itemInicial={modalAjuste.item}
          onClose={() => setModalAjuste(null)}
          onSaved={() => { setModalAjuste(null); load(); onToast('Ajuste registrado!') }}
        />
      )}
    </div>
  )
}

// ─── Aba 2: Produtos ──────────────────────────────────────────────────────────

function tipoTag(p) {
  if (p.tipo === 'kit') return 'Kit · estoque virtual'
  if (p.tipo === 'revenda') return 'Revenda'
  if (p.modo_estoque === 'sob_encomenda') return 'Fabricado · sob encomenda'
  return 'Fabricado · mantém estoque'
}

function statusProduto(p) {
  if (p.tipo === 'kit') return 'virtual'
  if (p.tipo === 'fabricado' && p.modo_estoque === 'sob_encomenda') return 'gray'
  if (Number(p.quantidade_estoque) < 0) return 'neg'
  if (Number(p.estoque_minimo) > 0 && Number(p.quantidade_estoque) < Number(p.estoque_minimo)) return 'baixo'
  return 'ok'
}

function AbaProdutos({ onToast }) {
  const [produtos, setProdutos] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [modalAjuste, setModalAjuste] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await fichasApi.listarProdutos({ search, ativo: 'true', page_size: 300 })
      setProdutos(r.data.results ?? r.data)
    } finally { setLoading(false) }
  }, [search])

  useEffect(() => { load() }, [load])

  return (
    <div className={styles.abaInner}>
      <div className={styles.toolbarRow}>
        <div className={styles.searchBox}>
          <i className="ti ti-search" />
          <input placeholder="Buscar produto…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      </div>

      {loading ? <div className={styles.center}><Spinner /></div> : produtos.length === 0 ? (
        <Empty icon="package" message="Nenhum produto cadastrado ainda." />
      ) : (
        <div className={styles.prodGrid}>
          {produtos.map((p) => {
            const st = statusProduto(p)
            const semSaldo = p.tipo === 'kit' || (p.tipo === 'fabricado' && p.modo_estoque === 'sob_encomenda')
            return (
              <div key={p.id} className={`${styles.prodCard} ${styles['prodBorder_' + st]}`}>
                <div className={styles.prodTop}>
                  <div>
                    <div className={styles.prodNome}>{p.nome}</div>
                    <div className={styles.prodTipoTag}>{tipoTag(p)}</div>
                  </div>
                  <StatusBadge status={st === 'virtual' ? 'neutro' : st === 'gray' ? 'gray' : st} />
                </div>
                {semSaldo ? (
                  <div className={styles.prodSemSaldo}>
                    {p.tipo === 'kit' ? 'Depende dos componentes' : 'Consumo de insumo direto na confirmação do pedido'}
                  </div>
                ) : (
                  <>
                    <div className={styles.prodSaldoWrap}>
                      <span className={st === 'neg' ? styles.tdVermelho : ''}>{fmtQtd(p.quantidade_estoque)}</span>
                      <span className={styles.prodSaldoUn}>un.</span>
                    </div>
                    <div className={styles.prodMin}>Mínimo configurado: {fmtQtd(p.estoque_minimo)} un.</div>
                  </>
                )}
                <div className={styles.prodFoot}>
                  {!semSaldo && (
                    <button className={styles.iconBtn} title="Ajustar saldo" onClick={() => setModalAjuste({ tipo_item: 'produto', item: p })}>
                      <i className="ti ti-edit" />
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {modalAjuste && (
        <ModalAjusteInventario
          tipoItemInicial={modalAjuste.tipo_item}
          itemInicial={modalAjuste.item}
          onClose={() => setModalAjuste(null)}
          onSaved={() => { setModalAjuste(null); load(); onToast('Ajuste registrado!') }}
        />
      )}
    </div>
  )
}

// ─── Aba 3: Produção ──────────────────────────────────────────────────────────

function AbaProducao({ onToast }) {
  const [fichas, setFichas] = useState([])
  const [fichaId, setFichaId] = useState('')
  const [quantidade, setQuantidade] = useState('')
  const [preview, setPreview] = useState(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [saving, setSaving] = useState(false)
  const [producoes, setProducoes] = useState([])
  const debounceRef = useRef(null)

  const loadProducoes = useCallback(() => {
    estoqueApi.producoes.list({ page_size: 15 }).then((r) => setProducoes(r.data.results ?? r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    fichasApi.listarFichas({ ativo: 'true', page_size: 200 }).then((r) => {
      const lista = r.data.results ?? r.data
      setFichas(lista)
      if (lista.length && !fichaId) setFichaId(String(lista[0].id))
    }).catch(() => {})
    loadProducoes()
  }, [loadProducoes]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (!fichaId || !quantidade || Number(quantidade) <= 0) { setPreview(null); return }
    debounceRef.current = setTimeout(async () => {
      setLoadingPreview(true)
      try {
        const r = await estoqueApi.producoes.preview({ ficha_tecnica: fichaId, quantidade })
        setPreview(r.data.itens)
      } catch { setPreview(null) }
      finally { setLoadingPreview(false) }
    }, 300)
    return () => clearTimeout(debounceRef.current)
  }, [fichaId, quantidade])

  const handleConfirmar = async () => {
    if (!fichaId || !quantidade) return
    setSaving(true)
    try {
      await estoqueApi.producoes.create({ ficha_tecnica: fichaId, quantidade_produzida: quantidade })
      onToast('Produção registrada!')
      setQuantidade('')
      setPreview(null)
      loadProducoes()
    } catch (e) {
      onToast(e?.response?.data?.detail || 'Erro ao registrar produção.', 'error')
    } finally { setSaving(false) }
  }

  return (
    <div className={styles.abaInner}>
      <div className={styles.producaoLayout}>
        <div className={styles.panel}>
          <h3 className={styles.cardTitle}><i className="ti ti-chef-hat" /> Registrar Produção</h3>
          <Field label="Ficha técnica">
            <Select value={fichaId} onChange={(e) => setFichaId(e.target.value)}>
              {fichas.map((f) => <option key={f.id} value={f.id}>{f.nome} (rende {f.rendimento} un.)</option>)}
            </Select>
          </Field>
          <Field label="Quantidade produzida (un.)">
            <Input type="number" min="0" step="0.001" value={quantidade} onChange={(e) => setQuantidade(e.target.value)} />
          </Field>
          <p className={styles.hintSmall}>Consumo de insumo é calculado proporcionalmente ao rendimento da ficha.</p>

          {loadingPreview ? <div className={styles.center}><Spinner size={18} /></div> : preview && (
            <>
              <h4 className={styles.previewTitle}><i className="ti ti-list-check" /> Consumo previsto de insumos</h4>
              <div className={styles.previewBox}>
                {preview.map((it) => (
                  <div key={it.materia_prima_id} className={`${styles.previewRow} ${!it.suficiente ? styles.previewInsuf : ''}`}>
                    <span>{it.materia_prima_nome}</span>
                    <span>{fmtQtd(it.quantidade)} {it.unidade_medida}{!it.suficiente && ' — saldo insuficiente'}</span>
                  </div>
                ))}
              </div>
              <p className={styles.hintSmall}>Saldo negativo não bloqueia a produção — apenas gera alerta para a equipe.</p>
            </>
          )}

          <Btn onClick={handleConfirmar} loading={saving} disabled={!fichaId || !quantidade} style={{ width: '100%', justifyContent: 'center', marginTop: 8 }}>
            Confirmar Produção
          </Btn>
        </div>

        <div className={styles.panel}>
          <h3 className={styles.cardTitle}><i className="ti ti-clock-history" /> Produções recentes</h3>
          {producoes.length === 0 ? <Empty icon="chef-hat" message="Nenhuma produção registrada ainda." /> : (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead><tr><th>Data</th><th>Ficha técnica</th><th className={styles.thRight}>Quantidade</th><th>Produto gerado</th><th>Responsável</th></tr></thead>
                <tbody>
                  {producoes.map((p) => (
                    <tr key={p.id}>
                      <td className={styles.tdMuted}>{new Date(p.criado_em).toLocaleString('pt-BR')}</td>
                      <td>{p.ficha_tecnica_nome}</td>
                      <td className={styles.tdRight}>{fmtQtd(p.quantidade_produzida)} un.</td>
                      <td>{p.produto_gerado || '—'}</td>
                      <td className={styles.tdMuted}>{p.criado_por_nome || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Aba 4: Movimentações ─────────────────────────────────────────────────────

const TIPO_MOVIMENTO_LABEL = {
  entrada_compra: 'Entrada — compra',
  entrada_producao: 'Entrada — produção',
  saida_producao: 'Saída — produção',
  saida_venda: 'Saída — venda',
  ajuste_inventario: 'Ajuste — inventário',
}

function AbaMovimentacoes() {
  const [movimentos, setMovimentos] = useState([])
  const [loading, setLoading] = useState(true)
  const [tipoFiltro, setTipoFiltro] = useState('')
  const [origemFiltro, setOrigemFiltro] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    const params = { page_size: 100 }
    if (tipoFiltro) params.tipo_movimento = tipoFiltro
    if (origemFiltro) params.origem_tipo = origemFiltro
    estoqueApi.movimentos.list(params)
      .then((r) => setMovimentos(r.data.results ?? r.data))
      .catch(() => setMovimentos([]))
      .finally(() => setLoading(false))
  }, [tipoFiltro, origemFiltro])

  useEffect(() => { load() }, [load])

  return (
    <div className={styles.abaInner}>
      <div className={styles.toolbarRow}>
        <Select value={tipoFiltro} onChange={(e) => setTipoFiltro(e.target.value)} style={{ width: 220 }}>
          <option value="">Todos os tipos</option>
          {Object.entries(TIPO_MOVIMENTO_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
        <Select value={origemFiltro} onChange={(e) => setOrigemFiltro(e.target.value)} style={{ width: 180 }}>
          <option value="">Todas as origens</option>
          <option value="manual">Manual</option>
          <option value="producao">Produção</option>
          <option value="pedido_pdv">Pedido PDV</option>
          <option value="pedido_ifood">Pedido iFood</option>
          <option value="evento">Evento</option>
        </Select>
      </div>

      {loading ? <div className={styles.center}><Spinner /></div> : movimentos.length === 0 ? (
        <Empty icon="history" message="Nenhuma movimentação encontrada." />
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Data</th><th>Item</th><th>Movimento</th>
                <th className={styles.thRight}>Quantidade</th>
                <th className={styles.thRight}>Saldo anterior</th>
                <th className={styles.thRight}>Saldo posterior</th>
                <th>Origem</th>
              </tr>
            </thead>
            <tbody>
              {movimentos.map((m) => {
                const isSaida = m.tipo_movimento.startsWith('saida')
                const isAjuste = m.tipo_movimento === 'ajuste_inventario'
                return (
                  <tr key={m.id}>
                    <td className={styles.tdMuted}>{new Date(m.criado_em).toLocaleString('pt-BR')}</td>
                    <td className={styles.tdNome}>{m.materia_prima_nome || m.produto_nome}</td>
                    <td>
                      <span className={`${styles.movTipo} ${isAjuste ? styles.movAjuste : isSaida ? styles.movSaida : styles.movEntrada}`}>
                        <i className={`ti ti-${isAjuste ? 'adjustments' : isSaida ? 'arrow-down-right' : 'arrow-up-right'}`} />
                        {TIPO_MOVIMENTO_LABEL[m.tipo_movimento] || m.tipo_movimento}
                      </span>
                    </td>
                    <td className={styles.tdRight}>{isSaida ? '-' : isAjuste ? '' : '+'}{fmtQtd(m.quantidade)}</td>
                    <td className={`${styles.tdRight} ${styles.tdMuted}`}>{fmtQtd(m.saldo_anterior)}</td>
                    <td className={styles.tdRight}>{fmtQtd(m.saldo_posterior)}</td>
                    <td className={styles.tdMuted}>{m.origem_tipo || '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ─── Modal: Registrar Compra (manual) ─────────────────────────────────────────

function ModalRegistrarCompra({ onClose, onSaved }) {
  const [tipoItem, setTipoItem] = useState('materia_prima')
  const [materias, setMaterias] = useState([])
  const [produtos, setProdutos] = useState([])
  const [itemId, setItemId] = useState('')
  const [quantidade, setQuantidade] = useState('')
  const [valorTotal, setValorTotal] = useState('')
  const [numeroNota, setNumeroNota] = useState('')
  const [saving, setSaving] = useState(false)
  const [erro, setErro] = useState('')

  useEffect(() => {
    fichasApi.listarMaterias({ ativo: 'true', page_size: 300 }).then((r) => setMaterias(r.data.results ?? r.data)).catch(() => {})
    fichasApi.listarProdutos({ tipo: 'revenda', ativo: 'true', page_size: 300 }).then((r) => setProdutos(r.data.results ?? r.data)).catch(() => {})
  }, [])

  useEffect(() => { setItemId('') }, [tipoItem])

  const opcoes = tipoItem === 'materia_prima' ? materias : produtos

  const handleSalvar = async () => {
    if (!itemId || !quantidade) { setErro('Selecione o item e informe a quantidade.'); return }
    setSaving(true); setErro('')
    try {
      await estoqueApi.registrarCompra({
        tipo_item: tipoItem, item_id: Number(itemId), quantidade,
        valor_total: valorTotal || undefined, numero_nota: numeroNota,
      })
      onSaved()
    } catch (e) {
      const d = e?.response?.data
      setErro(typeof d === 'string' ? d : d?.detail || JSON.stringify(d) || 'Erro ao registrar entrada.')
    } finally { setSaving(false) }
  }

  return (
    <Modal
      open title="Registrar Compra" onClose={onClose} width={440}
      footer={<>
        <Btn variant="ghost" onClick={onClose}>Cancelar</Btn>
        <Btn onClick={handleSalvar} loading={saving}>Registrar Entrada</Btn>
      </>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className={styles.radioRow}>
          <button className={`${styles.radioChip} ${tipoItem === 'materia_prima' ? styles.radioChipSel : ''}`} onClick={() => setTipoItem('materia_prima')}>
            <i className="ti ti-wheat" /> Insumo
          </button>
          <button className={`${styles.radioChip} ${tipoItem === 'produto' ? styles.radioChipSel : ''}`} onClick={() => setTipoItem('produto')}>
            <i className="ti ti-package" /> Produto (revenda)
          </button>
        </div>
        <Field label="Item">
          <Select value={itemId} onChange={(e) => setItemId(e.target.value)}>
            <option value="">— selecionar —</option>
            {opcoes.map((o) => <option key={o.id} value={o.id}>{o.nome}</option>)}
          </Select>
        </Field>
        <Field label="Quantidade comprada">
          <Input type="number" min="0" step="0.001" placeholder="Ex: 5" value={quantidade} onChange={(e) => setQuantidade(e.target.value)} />
        </Field>
        <Field label="Valor total da nota (opcional — atualiza custo)">
          <Input type="number" min="0" step="0.01" placeholder="R$" value={valorTotal} onChange={(e) => setValorTotal(e.target.value)} />
        </Field>
        <Field label="Nº da nota fiscal (opcional)">
          <Input type="text" placeholder="Ex: 8821" value={numeroNota} onChange={(e) => setNumeroNota(e.target.value)} />
        </Field>
        {erro && <p className={styles.erro}>{erro}</p>}
      </div>
    </Modal>
  )
}

// ─── Modal: Ajuste de Inventário ──────────────────────────────────────────────

const MOTIVOS = ['Contagem periódica', 'Perda / quebra', 'Vencimento', 'Correção de erro']

function ModalAjusteInventario({ tipoItemInicial, itemInicial, onClose, onSaved }) {
  const [tipoItem, setTipoItem] = useState(tipoItemInicial || 'materia_prima')
  const [materias, setMaterias] = useState([])
  const [produtos, setProdutos] = useState([])
  const [itemId, setItemId] = useState(itemInicial ? String(itemInicial.id) : '')
  const [saldoContado, setSaldoContado] = useState('')
  const [motivo, setMotivo] = useState(MOTIVOS[0])
  const [observacao, setObservacao] = useState('')
  const [saving, setSaving] = useState(false)
  const [erro, setErro] = useState('')

  useEffect(() => {
    if (!itemInicial) {
      fichasApi.listarMaterias({ ativo: 'true', page_size: 300 }).then((r) => setMaterias(r.data.results ?? r.data)).catch(() => {})
      fichasApi.listarProdutos({ ativo: 'true', page_size: 300 }).then((r) => setProdutos(r.data.results ?? r.data)).catch(() => {})
    }
  }, [itemInicial])

  const opcoes = tipoItem === 'materia_prima' ? materias : produtos
  const itemSelecionado = itemInicial || opcoes.find((o) => String(o.id) === itemId)

  const handleSalvar = async () => {
    if (!itemId || saldoContado === '') { setErro('Selecione o item e informe o saldo contado.'); return }
    setSaving(true); setErro('')
    try {
      await estoqueApi.ajusteInventario({
        tipo_item: tipoItem, item_id: Number(itemId), saldo_contado: saldoContado, motivo, observacao,
      })
      onSaved()
    } catch (e) {
      const d = e?.response?.data
      setErro(typeof d === 'string' ? d : d?.detail || JSON.stringify(d) || 'Erro ao registrar ajuste.')
    } finally { setSaving(false) }
  }

  return (
    <Modal
      open title="Ajuste de Inventário" onClose={onClose} width={420}
      footer={<>
        <Btn variant="ghost" onClick={onClose}>Cancelar</Btn>
        <Btn onClick={handleSalvar} loading={saving}>Salvar Ajuste</Btn>
      </>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {!itemInicial && (
          <div className={styles.radioRow}>
            <button className={`${styles.radioChip} ${tipoItem === 'materia_prima' ? styles.radioChipSel : ''}`} onClick={() => setTipoItem('materia_prima')}>Insumo</button>
            <button className={`${styles.radioChip} ${tipoItem === 'produto' ? styles.radioChipSel : ''}`} onClick={() => setTipoItem('produto')}>Produto</button>
          </div>
        )}
        <Field label="Item">
          {itemInicial ? (
            <Input disabled value={`${itemInicial.nome} — saldo atual: ${fmtQtd(itemInicial.quantidade_estoque)}`} />
          ) : (
            <Select value={itemId} onChange={(e) => setItemId(e.target.value)}>
              <option value="">— selecionar —</option>
              {opcoes.map((o) => <option key={o.id} value={o.id}>{o.nome} — saldo atual: {fmtQtd(o.quantidade_estoque)}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Saldo real contado">
          <Input type="number" step="0.001" placeholder="Ex: 1,00" value={saldoContado} onChange={(e) => setSaldoContado(e.target.value)} />
        </Field>
        <Field label="Motivo">
          <Select value={motivo} onChange={(e) => setMotivo(e.target.value)}>
            {MOTIVOS.map((m) => <option key={m} value={m}>{m}</option>)}
          </Select>
        </Field>
        <Field label="Observação (opcional)">
          <Input type="text" placeholder="Ex: embalagem estufada" value={observacao} onChange={(e) => setObservacao(e.target.value)} />
        </Field>
        {erro && <p className={styles.erro}>{erro}</p>}
      </div>
    </Modal>
  )
}

// ─── Modal: Configurações de Estoque ──────────────────────────────────────────

function ModalConfiguracao({ onClose, onToast }) {
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [telefones, setTelefones] = useState([])
  const [novoNumero, setNovoNumero] = useState('')
  const [novoNome, setNovoNome] = useState('')
  const [addingTel, setAddingTel] = useState(false)

  useEffect(() => {
    estoqueApi.configuracao.get().then((r) => setForm(r.data)).catch(() => {})
    estoqueApi.telefonesAlerta.list().then((r) => setTelefones(r.data.results ?? r.data)).catch(() => {})
  }, [])

  const salvar = async () => {
    setSaving(true)
    try {
      const { data } = await estoqueApi.configuracao.update({
        estoque_minimo_padrao: form.estoque_minimo_padrao,
        alerta_whatsapp_ativo: form.alerta_whatsapp_ativo,
        alerta_repetir_diariamente: form.alerta_repetir_diariamente,
      })
      setForm(data)
      onToast('Configurações de estoque salvas!')
      onClose()
    } catch {
      onToast('Erro ao salvar configurações.', 'error')
    } finally { setSaving(false) }
  }

  const adicionarTelefone = async () => {
    if (!novoNumero.trim()) return
    setAddingTel(true)
    try {
      const { data } = await estoqueApi.telefonesAlerta.create({ numero: novoNumero.trim(), nome: novoNome.trim() })
      setTelefones((t) => [...t, data])
      setNovoNumero(''); setNovoNome('')
    } catch {
      onToast('Erro ao adicionar telefone.', 'error')
    } finally { setAddingTel(false) }
  }

  const removerTelefone = async (id) => {
    try {
      await estoqueApi.telefonesAlerta.remove(id)
      setTelefones((t) => t.filter((x) => x.id !== id))
    } catch {
      onToast('Erro ao remover telefone.', 'error')
    }
  }

  if (!form) {
    return (
      <Modal open title="Configurações de Estoque" onClose={onClose}>
        <div className={styles.center}><Spinner /></div>
      </Modal>
    )
  }

  return (
    <Modal
      open title="Configurações de Estoque" onClose={onClose} width={460}
      footer={<>
        <Btn variant="ghost" onClick={onClose}>Cancelar</Btn>
        <Btn onClick={salvar} loading={saving}>Salvar Configurações</Btn>
      </>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Field label="Estoque mínimo padrão (novos itens)">
          <Input
            type="number" min="0" step="0.001" placeholder="Ex: 10"
            value={form.estoque_minimo_padrao}
            onChange={(e) => setForm((f) => ({ ...f, estoque_minimo_padrao: e.target.value }))}
          />
        </Field>

        <label className={styles.toggleRow}>
          <div>
            <div className={styles.toggleLbl}>Alertar equipe por WhatsApp</div>
            <div className={styles.toggleDesc}>Reaproveita o Z-API já usado nos alertas de Evento</div>
          </div>
          <input
            type="checkbox" checked={form.alerta_whatsapp_ativo}
            onChange={(e) => setForm((f) => ({ ...f, alerta_whatsapp_ativo: e.target.checked }))}
          />
        </label>

        <label className={styles.toggleRow}>
          <div>
            <div className={styles.toggleLbl}>Repetir alerta diariamente</div>
            <div className={styles.toggleDesc}>Enquanto o item continuar abaixo do mínimo</div>
          </div>
          <input
            type="checkbox" checked={form.alerta_repetir_diariamente}
            onChange={(e) => setForm((f) => ({ ...f, alerta_repetir_diariamente: e.target.checked }))}
          />
        </label>

        <Field label="Telefones que recebem o alerta">
          <div style={{ display: 'flex', gap: 8 }}>
            <Input placeholder="(86) 99xxx-xxxx" value={novoNumero} onChange={(e) => setNovoNumero(e.target.value)} />
            <Input placeholder="Label (opcional)" value={novoNome} onChange={(e) => setNovoNome(e.target.value)} style={{ maxWidth: 140 }} />
            <Btn variant="secondary" icon="plus" loading={addingTel} onClick={adicionarTelefone} disabled={!novoNumero.trim()}>Add</Btn>
          </div>
        </Field>
        {telefones.length === 0 ? (
          <p className={styles.hintSmall}>Nenhum telefone cadastrado ainda — os alertas não serão enviados.</p>
        ) : (
          <ul className={styles.telList}>
            {telefones.map((t) => (
              <li key={t.id} className={styles.telItem}>
                <span>{t.nome ? `${t.nome} — ${t.numero}` : t.numero}</span>
                <button onClick={() => removerTelefone(t.id)} aria-label="Remover telefone"><i className="ti ti-x" /></button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Modal>
  )
}
