// Constantes/helpers compartilhados do Atendimento iFood (ver ATENDIMENTO_IFOOD.md)
export const STATUS_MSG = {
  sugerida:  { label: 'Sugerida',  cls: 'st_neutro' },
  pendente:  { label: 'Pendente',  cls: 'st_alerta' },
  enviando:  { label: 'Enviando',  cls: 'st_alerta' },
  enviada:   { label: 'Enviada',   cls: 'st_ok' },
  falha:     { label: 'Falha',     cls: 'st_critico' },
  incerta:   { label: 'Incerta',   cls: 'st_critico' },
  expirada:  { label: 'Expirada',  cls: 'st_neutro' },
  cancelada: { label: 'Cancelada', cls: 'st_neutro' },
  recebida:  { label: 'Recebida',  cls: 'st_ok' },
}

export const VARIAVEIS = [
  ['primeiro_nome', 'Primeiro nome'],
  ['nome', 'Nome completo'],
  ['pedido', 'Nº do pedido'],
  ['loja', 'Loja'],
  ['itens_resumo', 'Itens'],
  ['previsao', 'Previsão'],
  ['minutos_atraso', 'Min. de atraso'],
]

export function fmtHora(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }) + ' ' +
    d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

// Minutos de atraso (>0) se o pedido passou da previsão + tolerância e ainda está em andamento.
export function minutosAtraso(pedido, toleranciaMin = 10, agora = Date.now()) {
  if (!pedido?.previsao_entrega) return 0
  if (['CONCLUDED', 'CANCELLED', 'PLACED'].includes(pedido.status)) return 0
  const diff = Math.floor((agora - new Date(pedido.previsao_entrega).getTime()) / 60000)
  return diff > toleranciaMin ? diff : 0
}

// Reenviar mensagem de gatilho de status quando o pedido já passou dele (ex.: "confirmado" em CONCLUDED).
const ORDEM_STATUS = ['PLACED', 'CONFIRMED', 'PREPARATION_STARTED', 'READY_TO_PICKUP', 'DISPATCHED', 'CONCLUDED']
const STATUS_DO_GATILHO = {
  confirmado: 'CONFIRMED', em_preparo: 'PREPARATION_STARTED', pronto_retirada: 'READY_TO_PICKUP',
  pronto_entrega: 'READY_TO_PICKUP', saiu_entrega: 'DISPATCHED', concluido: 'CONCLUDED',
}

export function mensagemDesatualizada(m) {
  const alvo = STATUS_DO_GATILHO[m.gatilho]
  if (!alvo || !m.pedido_status) return false
  if (m.pedido_status === 'CANCELLED') return true
  return ORDEM_STATUS.indexOf(m.pedido_status) > ORDEM_STATUS.indexOf(alvo)
}
