import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { Avatar } from '../ui'
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
      { to: '/notificacoes', icon: 'brand-whatsapp',    label: 'WhatsApp' },
    ],
  },
  {
    section: 'Catálogo & Preços',
    items: [
      { to: '/catalogo',       icon: 'book-2',           label: 'Catálogo' },
      { to: '/fichas-tecnicas',icon: 'flask',            label: 'Fichas Técnicas', sub: true },
      { to: '/central-precos', icon: 'currency-dollar',  label: 'Central de Preços' },
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
    section: 'Administração',
    items: [
      { to: '/usuarios',      icon: 'shield-lock', label: 'Usuários' },
      { to: '/configuracoes', icon: 'settings',    label: 'Configurações' },
    ],
  },
]

const ROLE_LABEL = { admin: 'Administrador', gerente: 'Gerente', atendente: 'Atendente' }

export default function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <h2 className="serif">
          Arretado <span style={{ color: 'var(--caramelo)' }}>Doces</span>
        </h2>
        <p className={styles.brandSub}>CRM v1.0</p>
      </div>

      <nav className={styles.nav}>
        {NAV.map(({ section, items }) => (
          <div key={section} className={styles.navSection}>
            <span className={styles.sectionLabel}>{section}</span>
            {items.map(({ to, icon, label, dot, sub }) => (
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
        ))}
      </nav>

      <div className={styles.footer}>
        <button className={styles.userPill} onClick={handleLogout} title="Sair do sistema">
          <Avatar name={user?.name || 'U S'} size="sm" />
          <div className={styles.userInfo}>
            <p>{user?.name || 'Usuário'}</p>
            <span>{ROLE_LABEL[user?.role] || 'Usuário'}</span>
          </div>
          <i className="ti ti-logout" style={{ fontSize: 14, color: 'var(--muted)', marginLeft: 'auto' }} />
        </button>
      </div>
    </aside>
  )
}