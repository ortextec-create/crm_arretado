import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { clientesApi, dashboardApi } from '../api/services'
import Topbar from '../components/layout/Topbar'
import { Btn, Avatar, StatusBadge, IntBadge, Spinner } from '../components/ui'
import styles from './Dashboard.module.css'

const brl = (v) =>
  (v ?? 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

const dataCurta = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })

const CANAL_COR = {
  ifood:   '#D85A30',
  pdv:     '#1D9E75',
  eventos: '#7F77DD',
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [resumo, setResumo] = useState(null)
  const [recentes, setRecentes] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      dashboardApi.resumo(),
      clientesApi.list({ ordering: '-criado_em', page: 1 }),
    ])
      .then(([r, c]) => {
        setResumo(r.data)
        setRecentes(c.data.results ?? c.data)
      })
      .catch(() => {
        setResumo(null)
        setRecentes([])
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className={styles.page}>
        <Topbar
          title="Dashboard"
          actions={<Btn icon="plus" onClick={() => navigate('/clientes?novo=1')}>Novo Cliente</Btn>}
        />
        <div className={styles.content}><div className={styles.center}><Spinner size={28} /></div></div>
      </div>
    )
  }

  const canais = resumo?.canais ?? { ifood: null, pdv: null, eventos: null, anotaai: null }
  const grafico = resumo?.grafico_7dias ?? []
  const maxTotalDia = Math.max(1, ...grafico.map((d) => d.ifood + d.pdv + d.eventos))
  const aReceber = resumo?.a_receber ?? { total: 0, eventos: [] }
  const fila = resumo?.fila_operacional ?? { pendente: 0, em_preparo: 0, pronto: 0 }
  const proximosEventos = resumo?.proximos_eventos ?? []
  const ticketMedio = resumo?.ticket_medio ?? { ifood: 0, pdv: 0, eventos: 0 }
  const maxTicket = Math.max(1, ticketMedio.ifood, ticketMedio.pdv, ticketMedio.eventos)
  const comparativo = resumo?.comparativo_ontem_pct

  return (
    <div className={styles.page}>
      <Topbar
        title="Dashboard"
        actions={<Btn icon="plus" onClick={() => navigate('/clientes?novo=1')}>Novo Cliente</Btn>}
      />

      <div className={styles.content}>
        {/* LINHA 1 — CARDS DE CANAL */}
        <div className={styles.canaisGrid}>
          <div className={`${styles.canalCard} ${styles.canalIfood}`}>
            <i className="ti ti-shopping-bag" aria-hidden="true" />
            <div className={styles.canalLabel}>iFood</div>
            <div className={styles.canalValue}>{brl(canais.ifood?.total_hoje)}</div>
            <div className={styles.canalSub}>{canais.ifood?.pedidos_hoje ?? 0} pedidos hoje</div>
          </div>

          <div className={`${styles.canalCard} ${styles.canalPdv}`}>
            <i className="ti ti-building-store" aria-hidden="true" />
            <div className={styles.canalLabel}>PDV Próprio</div>
            <div className={styles.canalValue}>{brl(canais.pdv?.total_hoje)}</div>
            <div className={styles.canalSub}>{canais.pdv?.pedidos_hoje ?? 0} pedidos hoje</div>
          </div>

          <div className={`${styles.canalCard} ${styles.canalEventos}`}>
            <i className="ti ti-calendar-event" aria-hidden="true" />
            <div className={styles.canalLabel}>Eventos</div>
            <div className={styles.canalValue}>{brl(canais.eventos?.recebido_hoje)}</div>
            <div className={styles.canalSub}>
              {canais.eventos?.criados_hoje ?? 0} criados · {canais.eventos?.entregues_hoje ?? 0} entregues hoje
            </div>
          </div>

          <div className={`${styles.canalCard} ${styles.canalEmBreve}`}>
            <i className="ti ti-device-mobile" aria-hidden="true" />
            <div className={styles.canalLabel}>Anota AI</div>
            <div className={styles.canalValue}>—</div>
            <div className={styles.canalSub}>Em breve</div>
          </div>
        </div>

        {/* LINHA 2 */}
        <div className={styles.row2}>
          <div className={styles.panel}>
            <div className={styles.totalHeader}>
              <div>
                <div className={styles.sectionLabel}>Total recebido hoje</div>
                <div className={styles.totalValue}>{brl(resumo?.total_recebido_hoje)}</div>
              </div>
              {comparativo !== null && comparativo !== undefined && (
                <div className={`${styles.trend} ${comparativo >= 0 ? styles.trendUp : styles.trendDown}`}>
                  <i className={`ti ti-trending-${comparativo >= 0 ? 'up' : 'down'}`} />
                  {Math.abs(comparativo).toFixed(1)}% vs ontem
                </div>
              )}
            </div>

            <div className={styles.stackedChart}>
              {grafico.map((d) => {
                const total = d.ifood + d.pdv + d.eventos
                const scale = 110 / maxTotalDia
                return (
                  <div key={d.data} className={styles.stackedCol} title={`${dataCurta(d.data)} — ${brl(total)}`}>
                    <div className={styles.stackedBar}>
                      <div style={{ height: d.ifood * scale, background: CANAL_COR.ifood }} />
                      <div style={{ height: d.pdv * scale, background: CANAL_COR.pdv }} />
                      <div style={{ height: d.eventos * scale, background: CANAL_COR.eventos }} />
                    </div>
                    <span className={styles.stackedLabel}>{dataCurta(d.data)}</span>
                  </div>
                )
              })}
            </div>
            <div className={styles.legend}>
              <span><i style={{ background: CANAL_COR.ifood }} />iFood</span>
              <span><i style={{ background: CANAL_COR.pdv }} />PDV</span>
              <span><i style={{ background: CANAL_COR.eventos }} />Eventos</span>
            </div>
          </div>

          <div className={styles.stackedPanels}>
            <div className={styles.panel}>
              <div className={styles.sectionLabel}>A receber (eventos)</div>
              <div className={styles.aReceberTotal}>{brl(aReceber.total)}</div>
              {aReceber.eventos.length === 0 && <div className={styles.emptySmall}>Nenhum saldo pendente.</div>}
              {aReceber.eventos.map((e) => (
                <div key={e.id} className={styles.aReceberRow} onClick={() => navigate('/eventos')}>
                  <div>
                    <div className={styles.aReceberCliente}>{e.cliente}</div>
                    <div className={styles.clientSub}>{e.numero} · {dataCurta(e.data_evento)}</div>
                  </div>
                  <div className={styles.aReceberValor}>{brl(e.saldo_restante)}</div>
                </div>
              ))}
            </div>

            <div className={styles.panel}>
              <div className={styles.sectionLabel}>Fila operacional</div>
              <div className={styles.filaGrid}>
                <div className={`${styles.filaBadge} ${styles.filaWarning}`}>
                  <span className={styles.filaValue}>{fila.pendente}</span>
                  <span className={styles.filaLabel}>Pendentes</span>
                </div>
                <div className={`${styles.filaBadge} ${styles.filaWarning}`}>
                  <span className={styles.filaValue}>{fila.em_preparo}</span>
                  <span className={styles.filaLabel}>Em preparo</span>
                </div>
                <div className={`${styles.filaBadge} ${styles.filaSuccess}`}>
                  <span className={styles.filaValue}>{fila.pronto}</span>
                  <span className={styles.filaLabel}>Prontos</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* LINHA 3 */}
        <div className={styles.row3}>
          <div>
            <div className={styles.sectionHeader}>
              <h3 className="serif">Próximos Eventos</h3>
              <Btn variant="ghost" size="sm" icon="arrow-right" onClick={() => navigate('/eventos')}>Ver todos</Btn>
            </div>
            <div className={styles.panel}>
              {proximosEventos.length === 0 && (
                <div className={styles.emptyMsg}>
                  <i className="ti ti-calendar-event" />
                  <p>Nenhum evento confirmado nos próximos dias.</p>
                </div>
              )}
              {proximosEventos.map((e) => (
                <div key={e.id} className={styles.tableRow} style={{ gridTemplateColumns: '1fr 90px 90px' }} onClick={() => navigate('/eventos')}>
                  <div>
                    <div className={styles.clientName}>{e.cliente}</div>
                    <div className={styles.clientSub}>{e.numero} · {e.titulo}</div>
                  </div>
                  <div className={styles.clientSub}>
                    {dataCurta(e.data_evento)}{e.hora_evento ? ` ${e.hora_evento}` : ''}
                  </div>
                  <div className={styles.aReceberValor}>{brl(e.valor_total)}</div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className={styles.sectionHeader}>
              <h3 className="serif">Ticket Médio por Canal</h3>
            </div>
            <div className={styles.panel} style={{ padding: '14px 18px' }}>
              {[
                { label: 'iFood', value: ticketMedio.ifood, color: CANAL_COR.ifood },
                { label: 'PDV', value: ticketMedio.pdv, color: CANAL_COR.pdv },
                { label: 'Eventos', value: ticketMedio.eventos, color: CANAL_COR.eventos },
              ].map(({ label, value, color }) => (
                <div key={label} className={styles.statusRow} style={{ padding: '10px 0' }}>
                  <div className={styles.statusDot} style={{ background: color }} />
                  <span className={styles.statusLabel}>{label}</span>
                  <div className={styles.statusBar}>
                    <div style={{ width: `${(value / maxTicket) * 100}%`, background: color, height: '100%', borderRadius: 2, opacity: 0.7 }} />
                  </div>
                  <span className={styles.statusValue} style={{ width: 'auto' }}>{brl(value)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* CLIENTES RECENTES */}
        <div className={styles.sectionHeader}>
          <h3 className="serif">Clientes Recentes</h3>
          <Btn variant="ghost" size="sm" icon="arrow-right" onClick={() => navigate('/clientes')}>Ver todos</Btn>
        </div>
        <div className={styles.panel}>
          <div className={styles.tableHead}>
            <span />
            <span>Cliente</span>
            <span>Cidade</span>
            <span>Integrações</span>
            <span>Status</span>
          </div>
          {recentes.length === 0 && (
            <div className={styles.emptyMsg}>
              <i className="ti ti-users" />
              <p>Nenhum cliente cadastrado ainda.</p>
            </div>
          )}
          {recentes.slice(0, 6).map((c) => (
            <div key={c.id} className={styles.tableRow} onClick={() => navigate(`/clientes/${c.id}`)}>
              <Avatar name={c.nome} size="sm" />
              <div>
                <div className={styles.clientName}>{c.nome}</div>
                <div className={styles.clientSub}>{c.telefone_principal}</div>
              </div>
              <div className={styles.clientSub}>
                {c.endereco_principal ? `${c.endereco_principal.cidade}/${c.endereco_principal.estado}` : '—'}
              </div>
              <div className={styles.intBadges}>
                {c.tem_integracao_ifood && <IntBadge type="ifood" />}
                {c.tem_integracao_anotaai && <IntBadge type="anotaai" />}
                {!c.tem_integracao_ifood && !c.tem_integracao_anotaai && <span className={styles.clientSub}>—</span>}
              </div>
              <StatusBadge status={c.status} />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
