import { useState, useEffect, useCallback } from 'react'
import { auditoriaApi, usuariosApi } from '../api/services'
import { Btn, Spinner, Empty } from '../components/ui'
import styles from './Auditoria.module.css'

const ACAO_LABEL = {
  login_sucesso: 'Login',
  login_falha: 'Login falhou',
  logout: 'Logout',
  usuario_criado: 'Usuário criado',
  usuario_editado: 'Usuário editado',
  usuario_removido: 'Usuário removido',
  permissao_alterada: 'Permissão alterada',
  senha_redefinida: 'Senha redefinida',
}

const ACAO_COR = {
  login_sucesso: 'var(--verde)',
  login_falha: '#ef4444',
  logout: 'var(--muted)',
  usuario_criado: 'var(--verde)',
  usuario_editado: 'var(--caramelo)',
  usuario_removido: '#ef4444',
  permissao_alterada: 'var(--caramelo)',
  senha_redefinida: 'var(--caramelo)',
}

function dataFmt(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

function resumo(log) {
  const d = log.detalhes || {}
  switch (log.acao) {
    case 'login_falha':
      return `Tentativa com ${d.email ?? '—'} (${d.motivo ?? '—'})`
    case 'usuario_criado':
      return `${d.criado_nome ?? '—'} (${d.role_inicial ?? '—'})`
    case 'usuario_removido':
      return `${d.removido_nome ?? '—'}`
    case 'permissao_alterada':
      return d.role_antes ? `role: ${d.role_antes} → ${d.role_depois}` : 'permissões alteradas'
    case 'senha_redefinida':
      return `${d.usuario_nome ?? '—'}`
    default:
      return '—'
  }
}

export default function Auditoria() {
  const [logs, setLogs] = useState([])
  const [count, setCount] = useState(0)
  const [next, setNext] = useState(null)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [usuarios, setUsuarios] = useState([])

  const [filtroUsuario, setFiltroUsuario] = useState('')
  const [filtroAcao, setFiltroAcao] = useState('')
  const [dataInicio, setDataInicio] = useState('')
  const [dataFim, setDataFim] = useState('')

  useEffect(() => {
    usuariosApi.listar({ page_size: 200 })
      .then((r) => setUsuarios(r.data.results ?? r.data))
      .catch(() => {})
  }, [])

  const carregar = useCallback(() => {
    setLoading(true)
    const params = { page }
    if (filtroUsuario) params.usuario = filtroUsuario
    if (filtroAcao) params.acao = filtroAcao
    if (dataInicio) params.data_inicio = dataInicio
    if (dataFim) params.data_fim = dataFim

    auditoriaApi.listar(params)
      .then((r) => {
        setLogs(r.data.results ?? r.data)
        setCount(r.data.count ?? (Array.isArray(r.data) ? r.data.length : 0))
        setNext(r.data.next ?? null)
      })
      .catch(() => { setLogs([]); setCount(0); setNext(null) })
      .finally(() => setLoading(false))
  }, [page, filtroUsuario, filtroAcao, dataInicio, dataFim])

  useEffect(() => { carregar() }, [carregar])

  const totalPages = Math.ceil(count / 20) || 1

  const filtrar = (setter) => (e) => { setter(e.target.value); setPage(1) }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={`${styles.title} serif`}>Log de Auditoria</h1>
          <p className={styles.sub}>Login, criação/edição/exclusão de usuário e mudanças de permissão</p>
        </div>
      </div>

      <div className={styles.filtros}>
        <select value={filtroUsuario} onChange={filtrar(setFiltroUsuario)} className={styles.select}>
          <option value="">Todos os usuários</option>
          {usuarios.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
        </select>
        <select value={filtroAcao} onChange={filtrar(setFiltroAcao)} className={styles.select}>
          <option value="">Todas as ações</option>
          {Object.entries(ACAO_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <input type="date" value={dataInicio} onChange={filtrar(setDataInicio)} className={styles.select} />
        <input type="date" value={dataFim} onChange={filtrar(setDataFim)} className={styles.select} />
      </div>

      <div className={styles.tableWrap}>
        {loading ? (
          <div className={styles.empty}><Spinner size={26} /></div>
        ) : logs.length === 0 ? (
          <Empty icon="history" message="Nenhum registro encontrado." />
        ) : (
          <>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Data/Hora</th>
                  <th>Usuário</th>
                  <th>Ação</th>
                  <th>Detalhes</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td className={styles.data}>{dataFmt(log.criado_em)}</td>
                    <td>{log.usuario_nome_snapshot}</td>
                    <td>
                      <span className={styles.acaoBadge} style={{ color: ACAO_COR[log.acao] }}>
                        {ACAO_LABEL[log.acao] ?? log.acao_display}
                      </span>
                    </td>
                    <td>{resumo(log)}</td>
                    <td className={styles.data}>{log.ip ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className={styles.pagination}>
              <span>{count} registros no total</span>
              <div className={styles.pages}>
                <Btn variant="ghost" size="sm" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
                  <i className="ti ti-chevron-left" /> Anterior
                </Btn>
                {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => i + 1).map((p) => (
                  <button
                    key={p}
                    className={`${styles.pageBtn} ${p === page ? styles.pageBtnActive : ''}`}
                    onClick={() => setPage(p)}
                  >
                    {p}
                  </button>
                ))}
                <Btn variant="ghost" size="sm" disabled={!next} onClick={() => setPage((p) => p + 1)}>
                  Próximo <i className="ti ti-chevron-right" />
                </Btn>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
