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
      <div className={styles.bg} />
      <form className={styles.box} onSubmit={handleSubmit} noValidate>
        {/* Logo */}
        <div className={styles.logo}>
          <svg width="56" height="34" viewBox="0 0 56 34" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M6 30 Q28 4 50 30" fill="rgba(200,134,10,0.12)" stroke="#C8860A" strokeWidth="1.2"/>
            <circle cx="18" cy="19" r="3.5" fill="none" stroke="#C8860A" strokeWidth="1"/>
            <path d="M16.5 19.5 L18 17.5 L18 19" fill="none" stroke="#C8860A" strokeWidth="0.9"/>
            <circle cx="28" cy="13" r="3.5" fill="none" stroke="#C8860A" strokeWidth="1"/>
            <path d="M26.5 13.5 L28 11.5 L28 13" fill="none" stroke="#C8860A" strokeWidth="0.9"/>
            <circle cx="38" cy="19" r="3.5" fill="none" stroke="#C8860A" strokeWidth="1"/>
            <path d="M36.5 19.5 L38 17.5 L38 19" fill="none" stroke="#C8860A" strokeWidth="0.9"/>
            <line x1="4" y1="31" x2="52" y2="31" stroke="rgba(200,134,10,0.3)" strokeWidth="0.5"/>
          </svg>
          <h1 className="serif">
            Arretado <span style={{ color: 'var(--caramelo)' }}>Doces</span>
          </h1>
          <p className={styles.logoSub}>Sistema de Gestão de Clientes</p>
        </div>

        <p className={styles.subtitle}>Entre com suas credenciais</p>

        <div className={styles.field}>
          <label>E-mail</label>
          <input
            type="email" autoComplete="email"
            placeholder="seu@arretado.com.br"
            value={email} onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div className={styles.field}>
          <label>Senha</label>
          <input
            type="password" autoComplete="current-password"
            placeholder="••••••••"
            value={password} onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        {error && <p className={styles.error}><i className="ti ti-alert-circle" />{error}</p>}

        <button type="submit" className={styles.btnLogin} disabled={loading}>
          {loading ? <i className="ti ti-loader spin" /> : null}
          {loading ? 'Entrando...' : 'Entrar no sistema'}
        </button>

        <p className={styles.hint}>
          Use qualquer e-mail + senha para acessar o demo.
        </p>
      </form>
    </div>
  )
}
