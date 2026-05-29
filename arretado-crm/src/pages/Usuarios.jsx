import { useState, useEffect, useCallback } from 'react'
import Topbar from '../components/layout/Topbar'
import { Btn, Avatar, Toast, Modal, Field, Input, Select } from '../components/ui'
import { usuariosApi } from '../api/services'
import styles from './Usuarios.module.css'

const ROLES = { admin: 'Administrador', gerente: 'Gerente', atendente: 'Atendente' }
const ROLE_COLORS = { admin: 'var(--caramelo)', gerente: 'var(--verde)', atendente: 'var(--muted)' }

const PERMS_DEFS = [
  { section: 'Clientes', items: [
    { key: 'ver_clientes',      label: 'Visualizar clientes',  desc: 'Acessar lista e dados dos clientes' },
    { key: 'criar_clientes',    label: 'Criar clientes',       desc: 'Cadastrar novos clientes' },
    { key: 'editar_clientes',   label: 'Editar clientes',      desc: 'Alterar dados de clientes' },
    { key: 'excluir_clientes',  label: 'Excluir clientes',     desc: 'Remover clientes do sistema' },
    { key: 'bloquear_clientes', label: 'Bloquear / Ativar',    desc: 'Alterar status de clientes' },
  ]},
  { section: 'Integrações', items: [
    { key: 'ver_integracoes',    label: 'Ver integrações',          desc: 'Visualizar dados de iFood e Anota AI' },
    { key: 'config_integracoes', label: 'Configurar integrações',   desc: 'Gerenciar credenciais externas' },
  ]},
  { section: 'Administração', items: [
    { key: 'ver_dashboard',      label: 'Dashboard e relatórios', desc: 'Acessar estatísticas' },
    { key: 'gerenciar_tags',     label: 'Gerenciar tags',         desc: 'Criar, editar e remover tags' },
    { key: 'gerenciar_usuarios', label: 'Gerenciar usuários',     desc: 'Criar e editar usuários do sistema' },
  ]},
]

const DEFAULT_PERMS = {
  admin: {
    ver_clientes: true, criar_clientes: true, editar_clientes: true,
    excluir_clientes: true, bloquear_clientes: true, ver_integracoes: true,
    config_integracoes: true, ver_dashboard: true, gerenciar_tags: true,
    gerenciar_usuarios: true,
  },
  gerente: {
    ver_clientes: true, criar_clientes: true, editar_clientes: true,
    excluir_clientes: false, bloquear_clientes: true, ver_integracoes: true,
    config_integracoes: false, ver_dashboard: true, gerenciar_tags: true,
    gerenciar_usuarios: false,
  },
  atendente: {
    ver_clientes: true, criar_clientes: false, editar_clientes: false,
    excluir_clientes: false, bloquear_clientes: false, ver_integracoes: false,
    config_integracoes: false, ver_dashboard: false, gerenciar_tags: false,
    gerenciar_usuarios: false,
  },
}

const FORM_EMPTY = { name: '', email: '', role: 'atendente', password: '' }

export default function Usuarios() {
  const [users, setUsers]       = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading]   = useState(true)
  const [saving, setSaving]     = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm]         = useState(FORM_EMPTY)
  const [toast, setToast]       = useState(null)

  // ── Carrega lista da API ──────────────────────────────────────────────────
  const carregarUsuarios = useCallback(async () => {
    setLoading(true)
    try {
      const res = await usuariosApi.listar()
      const lista = res.data?.results ?? res.data ?? []
      setUsers(lista)
      if (lista.length > 0 && !selected) setSelected(lista[0])
    } catch {
      setToast({ message: 'Erro ao carregar usuários.', type: 'error' })
    } finally {
      setLoading(false)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { carregarUsuarios() }, [carregarUsuarios])

  // ── Toggle permissão e persiste ──────────────────────────────────────────
  const togglePerm = async (userId, key) => {
    const user = users.find((u) => u.id === userId)
    if (!user) return

    const novasPerms = { ...user.perms, [key]: !user.perms[key] }

    // Atualização otimista
    setUsers((prev) => prev.map((u) =>
      u.id === userId ? { ...u, perms: novasPerms } : u
    ))
    if (selected?.id === userId) {
      setSelected((u) => ({ ...u, perms: novasPerms }))
    }

    try {
      await usuariosApi.atualizarPermissoes(userId, novasPerms)
    } catch {
      // Reverte em caso de erro
      setUsers((prev) => prev.map((u) =>
        u.id === userId ? { ...u, perms: user.perms } : u
      ))
      if (selected?.id === userId) setSelected((u) => ({ ...u, perms: user.perms }))
      setToast({ message: 'Erro ao salvar permissão.', type: 'error' })
    }
  }

  // ── Salva permissões explicitamente ──────────────────────────────────────
  const salvarPermissoes = async () => {
    if (!selected) return
    setSaving(true)
    try {
      await usuariosApi.atualizarPermissoes(selected.id, selected.perms)
      setToast({ message: 'Permissões salvas.', type: 'success' })
    } catch {
      setToast({ message: 'Erro ao salvar permissões.', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  // ── Cria usuário via API ──────────────────────────────────────────────────
  const saveUser = async () => {
    if (!form.name.trim() || !form.email.trim()) {
      setToast({ message: 'Preencha nome e e-mail.', type: 'error' })
      return
    }
    if (!form.password) {
      setToast({ message: 'Informe uma senha temporária.', type: 'error' })
      return
    }
    setSaving(true)
    try {
      const res = await usuariosApi.criar({
        name:     form.name.trim(),
        email:    form.email.trim(),
        role:     form.role,
        password: form.password,
        perms:    { ...DEFAULT_PERMS[form.role] },
      })
      const novo = res.data
      setUsers((prev) => [...prev, novo])
      setSelected(novo)
      setForm(FORM_EMPTY)
      setShowForm(false)
      setToast({ message: 'Usuário criado com sucesso!', type: 'success' })
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.response?.data?.email?.[0]
      setToast({ message: detail || 'Erro ao criar usuário.', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  // ── Remove usuário via API ────────────────────────────────────────────────
  const deleteUser = async (id) => {
    if (!confirm('Remover este usuário?')) return
    try {
      await usuariosApi.remover(id)
      const restante = users.filter((u) => u.id !== id)
      setUsers(restante)
      setSelected(restante[0] ?? null)
      setToast({ message: 'Usuário removido.', type: 'success' })
    } catch {
      setToast({ message: 'Erro ao remover usuário.', type: 'error' })
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className={styles.page}>
      <Topbar
        title="Usuários do Sistema"
        actions={<Btn icon="plus" onClick={() => setShowForm(true)}>Novo Usuário</Btn>}
      />

      <div className={styles.content}>
        {loading ? (
          <div className={styles.center}>
            <i className="ti ti-loader-2 spin" style={{ fontSize: 28, color: 'var(--caramelo)' }} />
          </div>
        ) : (
          <div className={styles.grid}>
            {/* ── Lista de usuários ── */}
            <div>
              <div className={styles.sectionLabel}>
                Usuários Cadastrados ({users.length})
              </div>

              {users.length === 0 && (
                <div className={styles.empty}>
                  <i className="ti ti-users-off" />
                  <p>Nenhum usuário cadastrado.</p>
                  <Btn icon="plus" onClick={() => setShowForm(true)}>Criar primeiro</Btn>
                </div>
              )}

              {users.map((u) => (
                <div
                  key={u.id}
                  className={`${styles.userCard} ${selected?.id === u.id ? styles.userCardActive : ''}`}
                  onClick={() => setSelected(u)}
                >
                  <Avatar name={u.name} size="md" />
                  <div className={styles.userInfo}>
                    <span className={styles.userName}>{u.name}</span>
                    <span className={styles.userEmail}>{u.email}</span>
                    <span className={styles.userRole} style={{ color: ROLE_COLORS[u.role] }}>
                      {ROLES[u.role]}
                    </span>
                  </div>
                  <div className={styles.userMeta}>
                    <span className={styles.metaLabel}>Último acesso</span>
                    <span className={styles.metaValue}>{u.last_login ?? '—'}</span>
                  </div>
                  <button
                    className={styles.iconBtnDanger}
                    onClick={(e) => { e.stopPropagation(); deleteUser(u.id) }}
                    title="Remover usuário"
                  >
                    <i className="ti ti-trash" />
                  </button>
                </div>
              ))}
            </div>

            {/* ── Painel de permissões ── */}
            {selected && (
              <div>
                <div className={styles.permHeader}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <Avatar name={selected.name} size="md" />
                    <div>
                      <div className={styles.permTitle}>{selected.name}</div>
                      <div style={{ fontSize: 11, color: ROLE_COLORS[selected.role] }}>
                        {ROLES[selected.role]}
                      </div>
                    </div>
                  </div>
                  <Btn
                    variant="ghost"
                    size="sm"
                    icon={saving ? 'loader-2' : 'device-floppy'}
                    onClick={salvarPermissoes}
                    disabled={saving}
                  >
                    {saving ? 'Salvando…' : 'Salvar'}
                  </Btn>
                </div>

                <div className={styles.permsPanel}>
                  {PERMS_DEFS.map(({ section, items }) => (
                    <div key={section}>
                      <div className={styles.permSection}>{section}</div>
                      {items.map(({ key, label, desc }) => (
                        <div key={key} className={styles.permRow}>
                          <div>
                            <div className={styles.permLabel}>{label}</div>
                            <div className={styles.permDesc}>{desc}</div>
                          </div>
                          <button
                            className={`${styles.toggle} ${selected.perms?.[key] ? styles.toggleOn : ''}`}
                            onClick={() => togglePerm(selected.id, key)}
                            aria-pressed={!!selected.perms?.[key]}
                            aria-label={label}
                          />
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Modal: Novo usuário ── */}
      <Modal
        open={showForm}
        onClose={() => { setShowForm(false); setForm(FORM_EMPTY) }}
        title="Novo Usuário"
        width={440}
        footer={
          <>
            <Btn variant="ghost" onClick={() => { setShowForm(false); setForm(FORM_EMPTY) }}>
              Cancelar
            </Btn>
            <Btn icon={saving ? 'loader-2' : 'check'} onClick={saveUser} disabled={saving}>
              {saving ? 'Criando…' : 'Criar Usuário'}
            </Btn>
          </>
        }
      >
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={{ gridColumn: '1 / -1' }}>
            <Field label="Nome Completo *">
              <Input
                placeholder="Nome do usuário"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </Field>
          </div>
          <div style={{ gridColumn: '1 / -1' }}>
            <Field label="E-mail *">
              <Input
                type="email"
                placeholder="usuario@arretado.com.br"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              />
            </Field>
          </div>
          <Field label="Perfil de Acesso">
            <Select
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
            >
              <option value="admin">Administrador</option>
              <option value="gerente">Gerente</option>
              <option value="atendente">Atendente</option>
            </Select>
          </Field>
          <Field label="Senha Temporária *">
            <Input
              type="password"
              placeholder="••••••••"
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
            />
          </Field>
        </div>
      </Modal>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}