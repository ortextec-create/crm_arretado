import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import styles from './EscolherEmpresa.module.css'

export default function EscolherEmpresa() {
  const { user, empresas, trocarEmpresa } = useAuth()
  const navigate = useNavigate()
  const [loadingId, setLoadingId] = useState(null)
  const [error, setError] = useState('')

  // Sem 2+ empresas não há o que escolher — nunca deveria chegar aqui
  // (Login.jsx só navega pra cá com empresas.length >= 2), mas cobre o
  // acesso direto à rota.
  if (!user || (empresas?.length || 0) < 2) {
    navigate('/', { replace: true })
    return null
  }

  const escolher = async (empresaId) => {
    setLoadingId(empresaId)
    setError('')
    try {
      await trocarEmpresa(empresaId)
      navigate('/')
    } catch {
      setError('Não foi possível selecionar esta empresa. Tente novamente.')
      setLoadingId(null)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.box}>
        <h1 className={`serif ${styles.title}`}>Qual empresa você quer acessar?</h1>
        <p className={styles.subtitle}>Você tem acesso a mais de uma empresa neste sistema.</p>

        <div className={styles.grid}>
          {empresas.map((empresa) => (
            <button
              key={empresa.id}
              className={styles.card}
              style={{ '--cor-empresa': empresa.cor_primaria || 'var(--caramelo)' }}
              onClick={() => escolher(empresa.id)}
              disabled={loadingId !== null}
            >
              {empresa.logo_simbolo || empresa.logo_horizontal ? (
                <img
                  className={styles.logo}
                  src={empresa.logo_simbolo || empresa.logo_horizontal}
                  alt={empresa.nome}
                />
              ) : (
                <div className={styles.logoFallback}>
                  <i className="ti ti-building-store" />
                </div>
              )}
              <span className={styles.nome}>{empresa.nome}</span>
              {empresa.subtitulo && <span className={styles.subtitulo}>{empresa.subtitulo}</span>}
              {loadingId === empresa.id && <i className={`ti ti-loader spin ${styles.loading}`} />}
            </button>
          ))}
        </div>

        {error && (
          <p className={styles.error}>
            <i className="ti ti-alert-circle" /> {error}
          </p>
        )}
      </div>
    </div>
  )
}
