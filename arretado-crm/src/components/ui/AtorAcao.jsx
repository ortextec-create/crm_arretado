import { useAuth } from '../../hooks/useAuth'
import { Avatar } from './index'
import styles from './AtorAcao.module.css'

// Mostra quem está fazendo a ação (criando/editando) dentro do próprio modal —
// hoje o ator só ficava visível depois de salvo, na aba "Histórico".
export default function AtorAcao({ acao }) {
  const { user } = useAuth()
  if (!user) return null

  return (
    <div className={styles.ator} title={`${acao} como ${user.name}`}>
      <Avatar name={user.name} size="sm" />
      <span className={styles.texto}>{acao} como <strong>{user.name}</strong></span>
    </div>
  )
}
