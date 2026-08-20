import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { sistemaApi } from '../../api/services'
import { Avatar } from '../ui'
import EmpresaSwitcher from './EmpresaSwitcher'
import SeletorTema from './SeletorTema'
import styles from './Sidebar.module.css'

const NAV = [
  {
    section: 'Principal',
    items: [
      { to: '/',            icon: 'layout-dashboard', label: 'Dashboard' },
      { to: '/clientes',    icon: 'users',             label: 'Clientes' },
      { to: '/tags',        icon: 'tag',               label: 'Tags' },
      { to: '/vinculacoes', icon: 'link',              label: 'Associações' },
      { to: '/eventos',       icon: 'calendar-event',    label: 'Eventos' },
      { to: '/orcamentos',    icon: 'file-description',  label: 'Orçamentos', sub: true },
      { to: '/locais-evento', icon: 'map-pin',           label: 'Locais de Evento', sub: true },
      { to: '/notificacoes', icon: 'brand-whatsapp',    label: 'WhatsApp' },
    ],
  },
  {
    section: 'Catálogo & Preços',
    items: [
      { to: '/catalogo',       icon: 'book-2',           label: 'Catálogo' },
      { to: '/fichas-tecnicas',icon: 'flask',            label: 'Fichas Técnicas', sub: true },
      { to: '/central-precos', icon: 'currency-dollar',  label: 'Central de Preços' },
      { to: '/estoque',        icon: 'boxes',            label: 'Estoque' },
    ],
  },
  {
    section: 'Integrações',
    items: [
      { to: '/integracoes/ifood',    icon: 'brand-firebase', label: 'iFood',       dot: true },
      { to: '/integracoes/anotaai',  icon: 'device-mobile',  label: 'Anota AI',    dot: true },
      { to: '/integracoes/pdv',      icon: 'building-store', label: 'PDV Próprio' },
      { to: '/integracoes/pdv/catalogo', icon: 'package',    label: 'Catálogo PDV', sub: true },
    ],
  },
  {
    section: 'Financeiro',
    items: [
      { to: '/financeiro', icon: 'cash', label: 'Financeiro' },
    ],
  },
  {
    section: 'Relatórios',
    items: [
      { to: '/relatorios/ifood', icon: 'chart-bar', label: 'iFood' },
    ],
  },
  {
    section: 'Administração',
    items: [
      { to: '/usuarios',        icon: 'shield-lock', label: 'Usuários' },
      { to: '/taxas-entrega',   icon: 'map-pin',     label: 'Taxas de Entrega' },
      { to: '/configuracoes',   icon: 'settings',    label: 'Configurações' },
      { to: '/empresas',        icon: 'building-store', label: 'Empresas', adminOnly: true },
      { to: '/auditoria',       icon: 'history',     label: 'Log de Auditoria', adminOnly: true },
    ],
  },
]

const ROLE_LABEL = { admin: 'Administrador', gerente: 'Gerente', atendente: 'Atendente' }

export default function Sidebar() {
  const { user, logout, empresaAtiva } = useAuth()
  const navigate = useNavigate()
  const [versao, setVersao] = useState(null)

  useEffect(() => {
    sistemaApi.versao().then((r) => setVersao(r.data)).catch(() => {})
  }, [])

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        {empresaAtiva?.logo_horizontal || empresaAtiva?.logo_negativo ? (
          <img
            src={(empresaAtiva.cor_sidebar && empresaAtiva.logo_negativo) || empresaAtiva.logo_horizontal || empresaAtiva.logo_negativo}
            alt={empresaAtiva.nome}
            className={styles.brandLogo}
          />
        ) : (
          <h2 className="serif">
            Arretado <span style={{ color: 'var(--caramelo)' }}>Doces</span>
          </h2>
        )}
        {empresaAtiva?.subtitulo && <p className={styles.brandSubtitulo}>{empresaAtiva.subtitulo}</p>}
        <p
          className={styles.brandSub}
          title={versao ? `Commit ${versao.commit} · ${versao.commit_data?.slice(0, 10) || ''}` : ''}
        >
          CRM {versao?.versao || '···'}
        </p>
      </div>

      <nav className={styles.nav}>
        {NAV.map(({ section, items }) => {
          const visiveis = items.filter((item) => !item.adminOnly || user?.role === 'admin')
          if (visiveis.length === 0) return null
          return (
            <div key={section} className={styles.navSection}>
              <span className={styles.sectionLabel}>{section}</span>
              {visiveis.map(({ to, icon, label, dot, sub }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `${styles.navItem} ${isActive ? styles.active : ''} ${sub ? styles.navItemSub : ''}`
                  }
                >
                  <i className={`ti ti-${icon}`} aria-hidden="true" />
                  {label}
                  {dot && <span className={styles.dot} />}
                </NavLink>
              ))}
            </div>
          )
        })}
      </nav>

      <div className={styles.footer}>
        <SeletorTema />
        <EmpresaSwitcher />
        <button className={styles.userPill} onClick={handleLogout} title="Sair do sistema">
          <Avatar name={user?.name || 'U S'} size="sm" />
          <div className={styles.userInfo}>
            <p>{user?.name || 'Usuário'}</p>
            <span>{ROLE_LABEL[user?.role] || 'Usuário'}</span>
          </div>
          <i className="ti ti-logout" style={{ fontSize: 14, color: 'var(--texto-muted)', marginLeft: 'auto' }} />
        </button>
      </div>
    </aside>
  )
}