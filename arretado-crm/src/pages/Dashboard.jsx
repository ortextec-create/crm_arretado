import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { clientesApi } from '../api/services'
import Topbar from '../components/layout/Topbar'
import { Btn, Avatar, StatusBadge, IntBadge, Spinner } from '../components/ui'
import styles from './Dashboard.module.css'

const MONTHS = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [recentes, setRecentes] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      clientesApi.estatisticas(),
      clientesApi.list({ ordering: '-criado_em', page: 1 }),
    ])
      .then(([s, c]) => {
        setStats(s.data)
        setRecentes(c.data.results ?? c.data)
      })
      .catch(() => {
        // Fallback demo data when backend is offline
        setStats({ total: 0, ativos: 0, inativos: 0, bloqueados: 0, com_ifood: 0, com_anotaai: 0 })
        setRecentes([])
      })
      .finally(() => setLoading(false))
  }, [])

  const now = new Date()
  const bars = Array.from({ length: 6 }, (_, i) => {
    const m = (now.getMonth() - 5 + i + 12) % 12
    return { label: MONTHS[m], h: 30 + Math.round(Math.random() * 80) }
  })

  const statCards = stats
    ? [
        { label: 'Total de Clientes', value: stats.total, sub: `${stats.inativos} inativos`, icon: 'users', trend: null },
        { label: 'Ativos', value: stats.ativos, sub: stats.total ? `${Math.round(stats.ativos / stats.total * 100)}% do total` : '—', icon: 'circle-check', trend: 'up' },
        { label: 'Com iFood', value: stats.com_ifood, sub: 'Clientes integrados', icon: 'brand-firebase', trend: 'up' },
        { label: 'Com Anota AI', value: stats.com_anotaai, sub: 'Clientes integrados', icon: 'device-mobile', trend: null },
      ]
    : []

  return (
    <div className={styles.page}>
      <Topbar
        title="Dashboard"
        actions={
          <Btn icon="plus" onClick={() => navigate('/clientes?novo=1')}>Novo Cliente</Btn>
        }
      />

      <div className={styles.content}>
        {loading ? (
          <div className={styles.center}><Spinner size={28} /></div>
        ) : (
          <>
            {/* STAT CARDS */}
            <div className={styles.statsGrid}>
              {statCards.map((c) => (
                <div key={c.label} className={styles.statCard}>
                  <i className={`ti ti-${c.icon} ${styles.statIcon}`} aria-hidden="true" />
                  <div className={styles.statLabel}>{c.label}</div>
                  <div className={styles.statValue}>{c.value}</div>
                  <div className={`${styles.statSub} ${c.trend === 'up' ? styles.up : ''}`}>
                    {c.trend === 'up' && <i className="ti ti-trending-up" />}
                    {c.sub}
                  </div>
                </div>
              ))}
            </div>

            {/* MAIN GRID */}
            <div className={styles.grid}>
              {/* Recent clients */}
              <div>
                <div className={styles.sectionHeader}>
                  <h3 className="serif">Clientes Recentes</h3>
                  <Btn variant="ghost" size="sm" icon="arrow-right" onClick={() => navigate('/clientes')}>
                    Ver todos
                  </Btn>
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
                    <div
                      key={c.id}
                      className={styles.tableRow}
                      onClick={() => navigate(`/clientes/${c.id}`)}
                    >
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

              {/* Right column */}
              <div>
                <div className={styles.sectionHeader}>
                  <h3 className="serif">Cadastros por Mês</h3>
                </div>
                <div className={styles.panel} style={{ marginBottom: 20 }}>
                  <div className={styles.chartWrap}>
                    {bars.map((b, i) => (
                      <div key={i} className={styles.barCol}>
                        <div className={`${styles.bar} ${i === bars.length - 1 ? styles.barActive : ''}`} style={{ height: b.h }} />
                        <span className={styles.barLabel}>{b.label}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className={styles.sectionHeader}>
                  <h3 className="serif">Status dos Clientes</h3>
                </div>
                <div className={styles.panel}>
                  {[
                    { label: 'Ativos', value: stats?.ativos ?? 0, color: 'var(--verde)' },
                    { label: 'Inativos', value: stats?.inativos ?? 0, color: 'var(--muted)' },
                    { label: 'Bloqueados', value: stats?.bloqueados ?? 0, color: 'var(--danger)' },
                  ].map(({ label, value, color }) => {
                    const pct = stats?.total ? Math.round(value / stats.total * 100) : 0
                    return (
                      <div key={label} className={styles.statusRow}>
                        <div className={styles.statusDot} style={{ background: color }} />
                        <span className={styles.statusLabel}>{label}</span>
                        <div className={styles.statusBar}>
                          <div style={{ width: `${pct}%`, background: color, height: '100%', borderRadius: 2, opacity: 0.6 }} />
                        </div>
                        <span className={styles.statusValue}>{value}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
