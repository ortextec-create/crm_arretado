import { useEffect, useState } from 'react'
import { atendimentoApi } from '../../api/services'

// Indicador discreto online/offline da extensão de Chrome (poll 15 s).
export default function StatusExtensao({ className }) {
  const [st, setSt] = useState(null)
  useEffect(() => {
    const load = () => atendimentoApi.statusExtensao().then((r) => setSt(r.data)).catch(() => setSt(null))
    load()
    const t = setInterval(load, 15_000)
    return () => clearInterval(t)
  }, [])
  if (!st) return null
  return (
    <div className={className} title="Extensão de Chrome que envia as mensagens no chat do iFood">
      <i className="ti ti-messages" style={{ fontSize: 13, color: st.online ? 'var(--status-ok-fg)' : 'var(--texto-faint)' }} />{' '}
      Chat {st.online ? 'online' : 'offline'}
    </div>
  )
}
