import { useEffect, useRef } from 'react'
import styles from './ui.module.css'

// ─── BUTTON ─────────────────────────────────────────────────────────────────
export function Btn({ variant = 'primary', size = 'md', children, icon, loading, ...props }) {
  return (
    <button className={`${styles.btn} ${styles[variant]} ${styles[size]}`} disabled={loading} {...props}>
      {loading ? <i className="ti ti-loader spin" /> : icon ? <i className={`ti ti-${icon}`} /> : null}
      {children}
    </button>
  )
}

// ─── BADGE ──────────────────────────────────────────────────────────────────
const STATUS_MAP = {
  ativo: { label: 'Ativo', cls: 'ativo' },
  inativo: { label: 'Inativo', cls: 'inativo' },
  bloqueado: { label: 'Bloqueado', cls: 'bloqueado' },
}

export function StatusBadge({ status }) {
  const s = STATUS_MAP[status] || { label: status, cls: 'inativo' }
  return <span className={`${styles.badge} ${styles[s.cls]}`}>{s.label}</span>
}

export function IntBadge({ type }) {
  return <span className={`${styles.badge} ${styles[type]}`}>{type === 'ifood' ? 'iFood' : 'Anota AI'}</span>
}

// ─── AVATAR ─────────────────────────────────────────────────────────────────
const COLORS = ['caramelo', 'verde', 'marrom', 'roxo']
function colorFor(name = '') {
  const i = (name.charCodeAt(0) + (name.charCodeAt(1) || 0)) % COLORS.length
  return COLORS[i]
}

export function Avatar({ name = '??', size = 'md' }) {
  const parts = name.trim().split(' ')
  const initials = parts.length >= 2
    ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    : name.slice(0, 2).toUpperCase()
  return (
    <div className={`${styles.avatar} ${styles['av-' + size]} ${styles['av-' + colorFor(name)]}`}>
      {initials}
    </div>
  )
}

// ─── INPUT ──────────────────────────────────────────────────────────────────
export function Field({ label, error, children }) {
  return (
    <div className={styles.field}>
      {label && <label className={styles.fieldLabel}>{label}</label>}
      {children}
      {error && <span className={styles.fieldError}>{error}</span>}
    </div>
  )
}

export function Input({ ...props }) {
  return <input className={styles.input} {...props} />
}

export function Select({ children, ...props }) {
  return <select className={styles.select} {...props}>{children}</select>
}

export function Textarea({ ...props }) {
  return <textarea className={styles.textarea} rows={3} {...props} />
}

// ─── MODAL ──────────────────────────────────────────────────────────────────
export function Modal({ open, onClose, title, children, footer, width = 520 }) {
  const overlayRef = useRef()

  useEffect(() => {
    const handleKey = (e) => { if (e.key === 'Escape') onClose() }
    if (open) document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className={styles.overlay}
      ref={overlayRef}
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div className={styles.modal} style={{ width }} role="dialog" aria-modal="true">
        <div className={styles.modalHeader}>
          <h3 className="serif">{title}</h3>
          <button className={styles.modalClose} onClick={onClose} aria-label="Fechar">
            <i className="ti ti-x" />
          </button>
        </div>
        <div className={styles.modalBody}>{children}</div>
        {footer && <div className={styles.modalFooter}>{footer}</div>}
      </div>
    </div>
  )
}

// ─── SPINNER ────────────────────────────────────────────────────────────────
export function Spinner({ size = 20 }) {
  return <i className="ti ti-loader spin" style={{ fontSize: size, color: 'var(--caramelo)' }} />
}

// ─── EMPTY STATE ─────────────────────────────────────────────────────────────
export function Empty({ icon = 'inbox', message = 'Nenhum resultado encontrado.' }) {
  return (
    <div className={styles.empty}>
      <i className={`ti ti-${icon}`} />
      <p>{message}</p>
    </div>
  )
}

// ─── TOAST ──────────────────────────────────────────────────────────────────
export function Toast({ message, type = 'success', onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 3500)
    return () => clearTimeout(t)
  }, [onClose])

  return (
    <div className={`${styles.toast} ${styles['toast-' + type]} fade-in`}>
      <i className={`ti ti-${type === 'success' ? 'circle-check' : 'alert-circle'}`} />
      <span>{message}</span>
      <button onClick={onClose}><i className="ti ti-x" /></button>
    </div>
  )
}
