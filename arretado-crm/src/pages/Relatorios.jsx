import { useState, useCallback } from 'react'
import { relatoriosApi } from '../api/services'
import styles from './Relatorios.module.css'

const hoje = () => new Date().toISOString().slice(0, 10)
const mesPasado = () => {
  const d = new Date()
  d.setDate(d.getDate() - 29)
  return d.toISOString().slice(0, 10)
}

const BRL = (v) =>
  Number(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

export default function Relatorios() {
  const [dataInicio, setDataInicio]   = useState(mesPasado)
  const [dataFim, setDataFim]         = useState(hoje)
  const [agrupamento, setAgrupamento] = useState('dia')
  const [dados, setDados]             = useState(null)
  const [loading, setLoading]         = useState(false)
  const [erro, setErro]               = useState(null)

  const buscar = useCallback(async () => {
    setLoading(true)
    setErro(null)
    try {
      const res = await relatoriosApi.ifood({ data_inicio: dataInicio, data_fim: dataFim, agrupamento })
      setDados(res.data)
    } catch (e) {
      setErro('Falha ao carregar relatório.')
    } finally {
      setLoading(false)
    }
  }, [dataInicio, dataFim, agrupamento])

  const exportar = (formato) => {
    const p = new URLSearchParams({ formato, data_inicio: dataInicio, data_fim: dataFim, agrupamento })
    window.open(`/api/v1/relatorios/ifood/?${p}`, '_blank')
  }

  const r = dados?.resumo
  const agrupado = dados?.agrupado || []

  const totalPedidos   = agrupado.reduce((s, x) => s + x.pedidos, 0)
  const totalReceita   = agrupado.reduce((s, x) => s + x.receita, 0)
  const totalCancelados = agrupado.reduce((s, x) => s + x.cancelados, 0)
  const naoCancel       = totalPedidos - totalCancelados
  const ticketGeral     = naoCancel ? totalReceita / naoCancel : 0

  return (
    <div className={styles.page}>
      {/* ── Cabeçalho ── */}
      <div className={styles.header}>
        <div>
          <h1 className={`${styles.titulo} serif`}>Relatórios</h1>
          <p className={styles.subtitulo}>Análise consolidada de pedidos</p>
        </div>
        {dados && (
          <div className={styles.exportBtns}>
            <button className={styles.btnExcel} onClick={() => exportar('excel')}>
              <i className="ti ti-table-export" /> Excel
            </button>
            <button className={styles.btnPdf} onClick={() => exportar('pdf')}>
              <i className="ti ti-file-type-pdf" /> PDF
            </button>
          </div>
        )}
      </div>

      {/* ── Filtros ── */}
      <div className={styles.filtros}>
        <div className={styles.filtroGrupo}>
          <label>Canal</label>
          <div className={styles.canalChip}>
            <i className="ti ti-brand-firebase" /> iFood
          </div>
        </div>

        <div className={styles.filtroGrupo}>
          <label>Período</label>
          <div className={styles.dateRange}>
            <input
              type="date"
              value={dataInicio}
              max={dataFim}
              onChange={e => setDataInicio(e.target.value)}
              className={styles.dateInput}
            />
            <span className={styles.dateSep}>até</span>
            <input
              type="date"
              value={dataFim}
              min={dataInicio}
              max={hoje()}
              onChange={e => setDataFim(e.target.value)}
              className={styles.dateInput}
            />
          </div>
        </div>

        <div className={styles.filtroGrupo}>
          <label>Agrupamento</label>
          <div className={styles.segControl}>
            {[['dia', 'Por dia'], ['mes', 'Por mês']].map(([v, l]) => (
              <button
                key={v}
                className={`${styles.segBtn} ${agrupamento === v ? styles.segBtnActive : ''}`}
                onClick={() => setAgrupamento(v)}
              >
                {l}
              </button>
            ))}
          </div>
        </div>

        <button
          className={styles.btnBuscar}
          onClick={buscar}
          disabled={loading}
        >
          {loading ? <i className="ti ti-loader-2 spin" /> : <i className="ti ti-search" />}
          {loading ? 'Buscando…' : 'Buscar'}
        </button>
      </div>

      {/* ── Erro ── */}
      {erro && <div className={styles.erro}><i className="ti ti-alert-circle" /> {erro}</div>}

      {/* ── Estado vazio ── */}
      {!dados && !loading && (
        <div className={styles.vazio}>
          <i className="ti ti-chart-bar" />
          <p>Configure o período e clique em <strong>Buscar</strong> para gerar o relatório.</p>
        </div>
      )}

      {/* ── Loading skeleton ── */}
      {loading && (
        <div className={styles.vazio}>
          <i className="ti ti-loader-2 spin" style={{ fontSize: 32 }} />
          <p>Carregando dados…</p>
        </div>
      )}

      {/* ── Resultado ── */}
      {dados && !loading && (
        <>
          {/* Cards de resumo */}
          <div className={styles.cards}>
            <div className={styles.card}>
              <div className={styles.cardIcon} style={{ background: 'rgba(201,122,58,.12)', color: 'var(--caramelo)' }}>
                <i className="ti ti-shopping-bag" />
              </div>
              <div>
                <p className={styles.cardLabel}>Total de Pedidos</p>
                <p className={styles.cardVal}>{r.total_pedidos}</p>
              </div>
            </div>

            <div className={styles.card}>
              <div className={styles.cardIcon} style={{ background: 'rgba(34,197,94,.12)', color: '#16a34a' }}>
                <i className="ti ti-currency-dollar" />
              </div>
              <div>
                <p className={styles.cardLabel}>Receita Total</p>
                <p className={styles.cardVal}>{BRL(r.receita_total)}</p>
              </div>
            </div>

            <div className={styles.card}>
              <div className={styles.cardIcon} style={{ background: 'rgba(59,130,246,.12)', color: '#2563eb' }}>
                <i className="ti ti-receipt" />
              </div>
              <div>
                <p className={styles.cardLabel}>Ticket Médio</p>
                <p className={styles.cardVal}>{BRL(r.ticket_medio)}</p>
              </div>
            </div>

            <div className={styles.card}>
              <div className={styles.cardIcon} style={{ background: 'rgba(239,68,68,.12)', color: '#dc2626' }}>
                <i className="ti ti-x" />
              </div>
              <div>
                <p className={styles.cardLabel}>Cancelados</p>
                <p className={styles.cardVal}>
                  {r.cancelados}
                  {r.taxa_cancelamento > 0 && (
                    <span className={styles.pct}> ({r.taxa_cancelamento}%)</span>
                  )}
                </p>
              </div>
            </div>
          </div>

          {/* Cards secundários (tipos) */}
          <div className={styles.tipoRow}>
            <span className={styles.tipoChip}>
              <i className="ti ti-moped" /> Delivery: <strong>{r.delivery}</strong>
            </span>
            <span className={styles.tipoChip}>
              <i className="ti ti-walk" /> Retirada: <strong>{r.takeout}</strong>
            </span>
            {r.indoor > 0 && (
              <span className={styles.tipoChip}>
                <i className="ti ti-armchair" /> Mesa: <strong>{r.indoor}</strong>
              </span>
            )}
          </div>

          {/* Tabela */}
          {agrupado.length === 0 ? (
            <div className={styles.vazio}>
              <i className="ti ti-inbox" />
              <p>Nenhum pedido encontrado no período selecionado.</p>
            </div>
          ) : (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>{agrupamento === 'mes' ? 'Mês' : 'Data'}</th>
                    <th className={styles.num}>Pedidos</th>
                    <th className={styles.num}>Receita</th>
                    <th className={styles.num}>Cancelados</th>
                    <th className={styles.num}>Ticket Médio</th>
                  </tr>
                </thead>
                <tbody>
                  {agrupado.map((row) => (
                    <tr key={row.periodo}>
                      <td className={styles.label}>{row.label}</td>
                      <td className={styles.num}>{row.pedidos}</td>
                      <td className={styles.num}>{BRL(row.receita)}</td>
                      <td className={`${styles.num} ${row.cancelados > 0 ? styles.cancel : ''}`}>
                        {row.cancelados}
                      </td>
                      <td className={styles.num}>{BRL(row.ticket_medio)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className={styles.totalRow}>
                    <td>TOTAL</td>
                    <td className={styles.num}>{totalPedidos}</td>
                    <td className={styles.num}>{BRL(totalReceita)}</td>
                    <td className={styles.num}>{totalCancelados}</td>
                    <td className={styles.num}>{BRL(ticketGeral)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
