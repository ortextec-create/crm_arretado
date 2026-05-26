import { useState, useEffect } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { Avatar } from '../ui'
import { pedidosApi } from '../../api/services'
import styles from './Sidebar.module.css'

const NAV = [
  {
    section: 'Principal',
    items: [
      { to: '/',             icon: 'layout-dashboard', label: 'Dashboard' },
      { to: '/clientes',     icon: 'users',            label: 'Clientes' },
      { to: '/tags',         icon: 'tag',              label: 'Tags' },
      { to: '/vinculacoes',  icon: 'link',             label: 'Associações', badge: true },
    ],
  },
  {
    section: 'Integrações',
    items: [
      { to: '/integracoes/ifood',       icon: 'brand-firebase',  label: 'iFood',       dot: true },
      { to: '/integracoes/anotaai',     icon: 'device-mobile',   label: 'Anota AI',    dot: true },
      { to: '/integracoes/pdv',         icon: 'building-store',  label: 'PDV Próprio' },
      { to: '/integracoes/pdv/catalogo',icon: 'package',         label: 'Catálogo',    sub: true },
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

  // ── Badge: pedidos sem cliente vinculado (Fase 4) ──────────────────────
  const [semVinculo, setSemVinculo] = useState(0)

  useEffect(() => {
    function atualizar() {
      pedidosApi.semCliente()
        .then(res => setSemVinculo(res.data.total ?? 0))
        .catch(() => {})
    }

    atualizar()
    const interval = setInterval(atualizar, 60_000)
    return () => clearInterval(interval)
  }, [])

  // ── Handlers ────────────────────────────────────────────────────────────
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
            {items.map(({ to, icon, label, dot, sub, badge }) => (
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
                {badge && semVinculo > 0 && (
                  <span className={styles.badge}>{semVinculo > 99 ? '99+' : semVinculo}</span>
                )}
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

/*
  ─────────────────────────────────────────────────────────────────────────────
  PATCH necessário em Sidebar.module.css — adicione a regra abaixo:

  .badge {
    margin-left: auto;
    background: var(--caramelo);
    color: #fff;
    font-size: 10px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 10px;
    min-width: 18px;
    text-align: center;
    line-height: 1.6;
  }
  ─────────────────────────────────────────────────────────────────────────────
*/
