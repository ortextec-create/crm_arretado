import { useState } from 'react'
import Topbar from '../components/layout/Topbar'
import { Btn, Avatar, Toast, Modal, Field, Input, Select } from '../components/ui'
import styles from './Usuarios.module.css'

const ROLES = { admin: 'Administrador', gerente: 'Gerente', atendente: 'Atendente' }
const ROLE_COLORS = { admin: 'var(--caramelo)', gerente: 'var(--verde)', atendente: 'var(--muted)' }

const PERMS_DEFS = [
  { section: 'Clientes', items: [
    { key: 'ver_clientes', label: 'Visualizar clientes', desc: 'Acessar lista e dados dos clientes' },
    { key: 'criar_clientes', label: 'Criar clientes', desc: 'Cadastrar novos clientes' },
    { key: 'editar_clientes', label: 'Editar clientes', desc: 'Alterar dados de clientes' },
    { key: 'excluir_clientes', label: 'Excluir clientes', desc: 'Remover clientes do sistema' },
    { key: 'bloquear_clientes', label: 'Bloquear / Ativar', desc: 'Alterar status de clientes' },
  ]},
  { section: 'Integrações', items: [
    { key: 'ver_integracoes', label: 'Ver integrações', desc: 'Visualizar dados de iFood e Anota AI' },
    { key: 'config_integracoes', label: 'Configurar integrações', desc: 'Gerenciar credenciais externas' },
  ]},
  { section: 'Administração', items: [
    { key: 'ver_dashboard', label: 'Dashboard e relatórios', desc: 'Acessar estatísticas' },
    { key: 'gerenciar_tags', label: 'Gerenciar tags', desc: 'Criar, editar e remover tags' },
    { key: 'gerenciar_usuarios', label: 'Gerenciar usuários', desc: 'Criar e editar usuários do sistema' },
  ]},
]

const DEFAULT_PERMS = {
  admin:      { ver_clientes:true, criar_clientes:true, editar_clientes:true, excluir_clientes:true, bloquear_clientes:true, ver_integracoes:true, config_integracoes:true, ver_dashboard:true, gerenciar_tags:true, gerenciar_usuarios:true },
  gerente:    { ver_clientes:true, criar_clientes:true, editar_clientes:true, excluir_clientes:false, bloquear_clientes:true, ver_integracoes:true, config_integracoes:false, ver_dashboard:true, gerenciar_tags:true, gerenciar_usuarios:false },
  atendente:  { ver_clientes:true, criar_clientes:false, editar_clientes:false, excluir_clientes:false, bloquear_clientes:false, ver_integracoes:false, config_integracoes:false, ver_dashboard:false, gerenciar_tags:false, gerenciar_usuarios:false },
}

const INITIAL_USERS = [
  { id: 1, name: 'Edvan Santos', email: 'edvan@arretado.com.br', role: 'admin', lastLogin: 'hoje', since: 'Jan 2024', perms: { ...DEFAULT_PERMS.admin } },
  { id: 2, name: 'Ana Nascimento', email: 'ana@arretado.com.br', role: 'gerente', lastLogin: 'ontem', since: 'Mar 2024', perms: { ...DEFAULT_PERMS.gerente } },
  { id: 3, name: 'Felipe Costa', email: 'felipe@arretado.com.br', role: 'atendente', lastLogin: '3 dias atrás', since: 'Mai 2024', perms: { ...DEFAULT_PERMS.atendente } },
]

export default function Usuarios() {
  const [users, setUsers] = useState(INITIAL_USERS)
  const [selected, setSelected] = useState(INITIAL_USERS[0])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', email: '', role: 'atendente', password: '' })
  const [toast, setToast] = useState(null)

  const togglePerm = (userId, key) => {
    setUsers((prev) => prev.map((u) =>
      u.id === userId ? { ...u, perms: { ...u.perms, [key]: !u.perms[key] } } : u
    ))
    if (selected?.id === userId) {
      setSelected((u) => ({ ...u, perms: { ...u.perms, [key]: !u.perms[key] } }))
    }
  }

  const saveUser = () => {
    if (!form.name || !form.email) return
    const newUser = {
      id: Date.now(), name: form.name, email: form.email,
      role: form.role, lastLogin: '—', since: new Date().toLocaleDateString('pt-BR', { month: 'short', year: 'numeric' }),
      perms: { ...DEFAULT_PERMS[form.role] },
    }
    setUsers((prev) => [...prev, newUser])
    setForm({ name: '', email: '', role: 'atendente', password: '' })
    setShowForm(false)
    setToast({ message: 'Usuário criado com sucesso!', type: 'success' })
  }

  const deleteUser = (id) => {
    if (!confirm('Remover este usuário?')) return
    setUsers((prev) => prev.filter((u) => u.id !== id))
    if (selected?.id === id) setSelected(users[0])
    setToast({ message: 'Usuário removido.', type: 'success' })
  }

  return (
    <div className={styles.page}>
      <Topbar
        title="Usuários do Sistema"
        actions={<Btn icon="plus" onClick={() => setShowForm(true)}>Novo Usuário</Btn>}
      />

      <div className={styles.content}>
        <div className={styles.grid}>
          {/* Left: user cards */}
          <div>
            <div className={styles.sectionLabel}>Usuários Cadastrados</div>
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
                  <span className={styles.metaValue}>{u.lastLogin}</span>
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

          {/* Right: permissions */}
          {selected && (
            <div>
              <div className={styles.permHeader}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <Avatar name={selected.name} size="md" />
                  <div>
                    <div className={styles.permTitle}>{selected.name}</div>
                    <div style={{ fontSize: 11, color: ROLE_COLORS[selected.role] }}>{ROLES[selected.role]}</div>
                  </div>
                </div>
                <Btn variant="ghost" size="sm" icon="device-floppy"
                  onClick={() => setToast({ message: 'Permissões salvas.', type: 'success' })}>
                  Salvar
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
                          className={`${styles.toggle} ${selected.perms[key] ? styles.toggleOn : ''}`}
                          onClick={() => togglePerm(selected.id, key)}
                          aria-pressed={selected.perms[key]}
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
      </div>

      <Modal
        open={showForm}
        onClose={() => setShowForm(false)}
        title="Novo Usuário"
        width={440}
        footer={
          <>
            <Btn variant="ghost" onClick={() => setShowForm(false)}>Cancelar</Btn>
            <Btn icon="check" onClick={saveUser}>Criar Usuário</Btn>
          </>
        }
      >
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={{ gridColumn: '1 / -1' }}>
            <Field label="Nome Completo *">
              <Input placeholder="Nome do usuário" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
            </Field>
          </div>
          <div style={{ gridColumn: '1 / -1' }}>
            <Field label="E-mail *">
              <Input type="email" placeholder="usuario@arretado.com.br" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
            </Field>
          </div>
          <Field label="Perfil de Acesso">
            <Select value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}>
              <option value="admin">Administrador</option>
              <option value="gerente">Gerente</option>
              <option value="atendente">Atendente</option>
            </Select>
          </Field>
          <Field label="Senha Temporária *">
            <Input type="password" placeholder="••••••••" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} />
          </Field>
        </div>
      </Modal>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
