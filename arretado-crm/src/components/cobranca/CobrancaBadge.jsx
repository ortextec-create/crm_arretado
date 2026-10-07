import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { cobrancaApi } from '../../api/services'

// Badge leve de status da régua de cobrança pra um Evento específico — lido
// de GET /cobranca/fila/?evento=<id> (fase/pausa/ligações já calculados pelo
// backend, ver COBRANCA.md). Sem lógica de régua aqui, só apresentação.
// Usado no modal do Evento (Eventos.jsx) e no histórico do cliente
// (ClienteDetail.jsx). Clicar leva pra tela /cobranca e abre a gaveta de
// linha do tempo daquele evento (via location.state, mesmo padrão do
// openPedidoId do iFood em ClienteDetail.jsx).
export default function CobrancaBadge({ eventoId }) {
  const [item, setItem] = useState(undefined) // undefined = carregando, null = não elegível
  const navigate = useNavigate()

  useEffect(() => {
    let ativo = true
    cobrancaApi.fila.list({ evento: eventoId })
      .then((r) => { if (ativo) setItem(r.data?.[0] || null) })
      .catch(() => { if (ativo) setItem(null) })
    return () => { ativo = false }
  }, [eventoId])

  if (!item) return null

  let texto
  if (item.pausa_vigente) {
    const [y, m, d] = item.pausa_vigente.pausado_ate.split('-')
    texto = `Pausado até ${d}/${m}`
  } else if (item.fase.codigo === 'aguardando') {
    texto = 'Cobrança: ainda não começou'
  } else if (item.fase.codigo === 'concluida') {
    texto = 'Cobrança: régua concluída sem pagamento'
  } else {
    texto = `Cobrança: ${item.fase.texto}${item.proxima_acao?.texto ? ` · ${item.proxima_acao.texto.replace(/^Sem mensagens.*$/, 'ligar')}` : ''}`
  }
  if (item.total_ligacoes > 0 && !item.pausa_vigente) {
    texto += ` · ${item.total_ligacoes} ligação(ões)`
  }

  return (
    <button
      type="button"
      onClick={() => navigate('/cobranca', { state: { openEventoId: item.evento_id } })}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11.5, fontWeight: 600,
        padding: '3px 9px', borderRadius: 99, border: '1px solid var(--border)',
        background: 'var(--caramelo-pale)', color: 'var(--caramelo)', cursor: 'pointer',
      }}
      title="Ver na régua de cobrança"
    >
      <i className="ti ti-coin" style={{ fontSize: 12 }} />
      {texto}
    </button>
  )
}
