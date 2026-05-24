import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import styles from './Login.module.css'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!email || !password) { setError('Preencha e-mail e senha.'); return }
    setLoading(true); setError('')
    try {
      await login(email, password)
      navigate('/')
    } catch {
      setError('Credenciais inválidas. Tente novamente.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <form className={styles.box} onSubmit={handleSubmit} noValidate>
        <div className={styles.logo}>
          <svg width="56" height="36" viewBox="0 0 56 36" fill="none">
            <path d="M7 32 Q28 5 51 32" fill="rgba(184,115,10,0.08)" stroke="#B8730A" strokeWidth="1.5"/>
            <circle cx="19" cy="20" r="3.5" fill="none" stroke="#B8730A" strokeWidth="1.2"/>
            <path d="M17.5 20.5L19 18.5L19 20" fill="none" stroke="#B8730A" strokeWidth="1"/>
            <circle cx="28" cy="14" r="3.5" fill="none" stroke="#B8730A" strokeWidth="1.2"/>
            <path d="M26.5 14.5L28 12.5L28 14" fill="none" stroke="#B8730A" strokeWidth="1"/>
            <circle cx="37" cy="20" r="3.5" fill="none" stroke="#B8730A" strokeWidth="1.2"/>
            <path d="M35.5 20.5L37 18.5L37 20" fill="none" stroke="#B8730A" strokeWidth="1"/>
            <line x1="5" y1="33" x2="53" y2="33" stroke="rgba(184,115,10,0.2)" strokeWidth="0.8"/>
          </svg>
          <h1 className="serif">Arretado <span style={{ color: 'var(--caramelo)' }}>Doces</span></h1>
          <p className={styles.logoSub}>Sistema de Gestão de Clientes</p>
        </div>

        <p className={styles.subtitle}>Entre com suas credenciais para acessar</p>

        <div className={styles.field}>
          <label>E-mail</label>
          <input type="email" autoComplete="email" placeholder="seu@arretado.com.br"
            value={email} onChange={e => setEmail(e.target.value)} />
        </div>
        <div className={styles.field}>
          <label>Senha</label>
          <input type="password" autoComplete="current-password" placeholder="••••••••"
            value={password} onChange={e => setPassword(e.target.value)} />
        </div>

        {error && (
          <p className={styles.error}>
            <i className="ti ti-alert-circle" />{error}
          </p>
        )}

        <button type="submit" className={styles.btnLogin} disabled={loading}>
          {loading && <i className="ti ti-loader spin" />}
          {loading ? 'Entrando...' : 'Entrar no sistema'}
        </button>

        <p className={styles.hint}>Use qualquer e-mail + senha para o demo.</p>
      </form>
    </div>
  )
}
