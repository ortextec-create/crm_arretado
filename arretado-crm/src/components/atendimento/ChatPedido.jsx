import { useCallback, useEffect, useState } from 'react'
import { atendimentoApi } from '../../api/services'
import { Btn } from '../ui'
import { STATUS_MSG, fmtHora } from './atendimento'
import styles from './ChatPedido.module.css'

// Seção "Chat" do detalhe do pedido iFood: mensagens do pedido + envio manual.
export default function ChatPedido({ pedido, onToast }) {
  const [msgs, setMsgs] = useState([])
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)

  const load = useCallback(() => {
    atendimentoApi.mensagens.list({ pedido: pedido.id, page_size: 100 })
      .then((r) => setMsgs([...(r.data.results ?? r.data)].reverse()))
      .catch(() => setMsgs([]))
  }, [pedido.id])

  useEffect(() => {
    load()
    const t = setInterval(load, 10_000)
    return () => clearInterval(t)
  }, [load])

  const enviar = async () => {
    const t = texto.trim()
    if (!t) return
    const nome = pedido.cliente_nome_crm || pedido.cliente_nome || 'o cliente'
    if (!window.confirm(`Enviar esta mensagem no chat do pedido #${pedido.display_id} (${nome})?\n\n${t}`)) return
    setEnviando(true)
    try {
      await atendimentoApi.mensagens.manual({ pedido: pedido.id, texto: t })
      setTexto('')
      onToast?.('Mensagem na fila — a extensão envia em instantes.')
      load()
    } catch (e) {
      onToast?.(e.response?.data?.detail || 'Não foi possível enfileirar a mensagem.', 'error')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.titulo}><i className="ti ti-messages" /> Chat</div>
      <div className={styles.lista}>
        {msgs.length === 0 && <span className={styles.vazio}>Nenhuma mensagem para este pedido.</span>}
        {msgs.map((m) => {
          const st = STATUS_MSG[m.status] || { label: m.status, cls: 'st_neutro' }
          return (
            <div key={m.id} className={`${styles.bolha} ${m.direcao === 'entrada' ? styles.entrada : ''}`}>
              {m.texto}
              <div className={styles.meta}>
                <span className={styles[st.cls]}>{st.label}</span>
                <span>{m.gatilho_display || m.origem}</span>
                <span>{fmtHora(m.enviado_em || m.criado_em)}</span>
              </div>
            </div>
          )
        })}
      </div>
      <div className={styles.form}>
        <textarea rows={2} value={texto} onChange={(e) => setTexto(e.target.value)}
          placeholder="Escrever mensagem para o cliente…" />
        <Btn size="sm" icon="send" loading={enviando} onClick={enviar} disabled={!texto.trim()}>Enviar</Btn>
      </div>
    </div>
  )
}
