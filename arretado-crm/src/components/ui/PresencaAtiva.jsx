import { useEffect, useState, useRef } from 'react'
import { presencaApi } from '../../api/services'
import { useAuth } from '../../hooks/useAuth'
import { Avatar } from './index'
import styles from './PresencaAtiva.module.css'

const INTERVALO_MS = 15000

// Heartbeat via polling REST (não WebSocket — ver CLAUDE.md). Mostra quem mais
// está com este registro aberto agora — informativo, não é uma trava de edição.
export default function PresencaAtiva({ model, objetoId }) {
  const { user } = useAuth()
  const [outros, setOutros] = useState([])
  const intervalRef = useRef(null)

  useEffect(() => {
    if (!objetoId) return

    let ativo = true
    const bater = () => {
      presencaApi.heartbeat({ model, objeto_id: objetoId })
        .then((r) => {
          if (!ativo) return
          setOutros((r.data.usuarios ?? []).filter((u) => u.id !== user?.id))
        })
        .catch(() => {})
    }

    bater()
    intervalRef.current = setInterval(bater, INTERVALO_MS)

    return () => {
      ativo = false
      clearInterval(intervalRef.current)
    }
  }, [model, objetoId, user?.id])

  if (outros.length === 0) return null

  const nomes = outros.map((u) => u.name).join(', ')
  return (
    <div className={styles.presenca} title={`${nomes} também está vendo isso agora`}>
      <div className={styles.avatares}>
        {outros.slice(0, 3).map((u) => <Avatar key={u.id} name={u.name} size="sm" />)}
      </div>
      <span className={styles.texto}>
        {outros.length === 1 ? `${outros[0].name} também está vendo` : `${outros.length} pessoas também estão vendo`}
      </span>
    </div>
  )
}
