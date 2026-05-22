import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { clientesApi } from '../api/services'
import Topbar from '../components/layout/Topbar'
import { Btn, Avatar, StatusBadge, IntBadge, Spinner, Empty, Toast } from '../components/ui'
import ClienteForm from './ClienteForm'
import styles from './Clientes.module.css'

const FILTERS = [
  { key: '', label: 'Todos' },
  { key: 'ativo', label: 'Ativos' },
  { key: 'inativo', label: 'Inativos' },
  { key: 'bloqueado', label: 'Bloqueados' },
]

export default function Clientes() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState(searchParams.get('search') || '')
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || '')
  const [page, setPage] = useState(1)
  const [data, setData] = useState({ results: [], count: 0, next: null, previous: null })
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(searchParams.get('novo') === '1')
  const [editCliente, setEditCliente] = useState(null)
  const [toast, setToast] = useState(null)
  const [actionLoading, setActionLoading] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    const params = { page, ordering: '-criado_em' }
    if (search) params.search = search
    if (statusFilter) params.status = statusFilter
    clientesApi
      .list(params)
      .then((r) => {
        const d = r.data
        setData({ results: d.results ?? d, count: d.count ?? (d.results ?? d).length, next: d.next, previous: d.previous })
      })
      .catch(() => setData({ results: [], count: 0, next: null, previous: null }))
      .finally(() => setLoading(false))
  }, [search, statusFilter, page])

  useEffect(() => { load() }, [load])

  // debounce search
  useEffect(() => {
    const t = setTimeout(() => { setPage(1) }, 350)
    return () => clearTimeout(t)
  }, [search])

  const handleSave = async (form) => {
    if (editCliente) {
      await clientesApi.update(editCliente.id, form)
      setToast({ message: 'Cliente atualizado com sucesso!', type: 'success' })
    } else {
      await clientesApi.create(form)
      setToast({ message: 'Cliente cadastrado com sucesso!', type: 'success' })
    }
    setEditCliente(null)
    load()
  }

  const handleDelete = async (id) => {
    if (!confirm('Confirma a exclusão deste cliente?')) return
    try {
      await clientesApi.delete(id)
      setToast({ message: 'Cliente removido.', type: 'success' })
      load()
    } catch {
      setToast({ message: 'Erro ao remover cliente.', type: 'error' })
    }
  }

  const handleStatusToggle = async (c) => {
    setActionLoading(c.id)
    try {
      if (c.status === 'bloqueado') {
        await clientesApi.ativar(c.id)
        setToast({ message: `${c.nome} foi ativado.`, type: 'success' })
      } else {
        await clientesApi.bloquear(c.id)
        setToast({ message: `${c.nome} foi bloqueado.`, type: 'success' })
      }
      load()
    } catch {
      setToast({ message: 'Erro ao alterar status.', type: 'error' })
    } finally {
      setActionLoading(null)
    }
  }

  const totalPages = Math.ceil(data.count / 20) || 1

  return (
    <div className={styles.page}>
      <Topbar
        title="Clientes"
        search={search}
        onSearch={(v) => { setSearch(v); setPage(1) }}
        actions={
          <>
            <Btn variant="ghost" icon="filter" size="sm">Filtros</Btn>
            <Btn icon="plus" onClick={() => { setEditCliente(null); setShowForm(true) }}>
              Novo Cliente
            </Btn>
          </>
        }
      />

      <div className={styles.content}>
        {/* Status filter pills */}
        <div className={styles.filtersBar}>
          {FILTERS.map((f) => (
            <button
              key={f.key}
              className={`${styles.filterPill} ${statusFilter === f.key ? styles.active : ''}`}
              onClick={() => { setStatusFilter(f.key); setPage(1) }}
            >
              {f.label}
              {f.key === '' && data.count > 0 && ` (${data.count})`}
            </button>
          ))}
          <label className={styles.filterToggle}>
            <input
              type="checkbox"
              onChange={(e) => {
                setSearchParams(e.target.checked ? { com_ifood: 'true' } : {})
              }}
            />
            Apenas iFood
          </label>
        </div>

        {loading ? (
          <div className={styles.center}><Spinner size={26} /></div>
        ) : data.results.length === 0 ? (
          <Empty icon="users" message="Nenhum cliente encontrado." />
        ) : (
          <>
            <div className={styles.table}>
              <div className={styles.thead}>
                <span />
                <span>Cliente</span>
                <span>Telefone</span>
                <span>Cidade</span>
                <span>Tags</span>
                <span>Integrações</span>
                <span>Status</span>
                <span>Ações</span>
              </div>

              {data.results.map((c) => (
                <div key={c.id} className={styles.trow} onClick={() => navigate(`/clientes/${c.id}`)}>
                  <Avatar name={c.nome} size="sm" />
                  <div>
                    <div className={styles.name}>{c.nome}</div>
                    <div className={styles.sub}>{c.email || '—'}</div>
                  </div>
                  <div className={styles.sub}>{c.telefone_principal}</div>
                  <div className={styles.sub}>
                    {c.endereco_principal ? `${c.endereco_principal.cidade}/${c.endereco_principal.estado}` : '—'}
                  </div>
                  <div className={styles.tagsCell}>
                    {(c.tags || []).slice(0, 2).map((t) => (
                      <span key={t.id} className={styles.tagPill} style={{ borderColor: t.cor + '50', color: t.cor }}>
                        {t.nome}
                      </span>
                    ))}
                  </div>
                  <div className={styles.intCell}>
                    {c.tem_integracao_ifood && <IntBadge type="ifood" />}
                    {c.tem_integracao_anotaai && <IntBadge type="anotaai" />}
                    {!c.tem_integracao_ifood && !c.tem_integracao_anotaai && <span className={styles.sub}>—</span>}
                  </div>
                  <StatusBadge status={c.status} />
                  <div className={styles.actions} onClick={(e) => e.stopPropagation()}>
                    <button
                      className={styles.iconBtn}
                      title="Editar"
                      onClick={() => { setEditCliente(c); setShowForm(true) }}
                    >
                      <i className="ti ti-edit" />
                    </button>
                    <button
                      className={styles.iconBtn}
                      title={c.status === 'bloqueado' ? 'Ativar' : 'Bloquear'}
                      onClick={() => handleStatusToggle(c)}
                      disabled={actionLoading === c.id}
                    >
                      {actionLoading === c.id
                        ? <i className="ti ti-loader spin" />
                        : <i className={`ti ti-${c.status === 'bloqueado' ? 'lock-open' : 'lock'}`} />
                      }
                    </button>
                    <button
                      className={`${styles.iconBtn} ${styles.iconBtnDanger}`}
                      title="Excluir"
                      onClick={() => handleDelete(c.id)}
                    >
                      <i className="ti ti-trash" />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* Pagination */}
            <div className={styles.pagination}>
              <span>{data.count} clientes no total</span>
              <div className={styles.pages}>
                <Btn variant="ghost" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>
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
                <Btn variant="ghost" size="sm" disabled={!data.next} onClick={() => setPage(p => p + 1)}>
                  Próximo <i className="ti ti-chevron-right" />
                </Btn>
              </div>
            </div>
          </>
        )}
      </div>

      <ClienteForm
        open={showForm}
        onClose={() => { setShowForm(false); setEditCliente(null) }}
        onSave={handleSave}
        initial={editCliente}
      />

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
