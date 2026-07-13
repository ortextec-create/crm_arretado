// Compartilhado entre Auditoria.jsx (log geral, restrito a admin) e a seção/aba
// de "Histórico" dentro do modal de detalhe de Orçamento/Evento — mesmo shape
// de log (LogAuditoriaSerializer), mesma lógica de rótulo/cor/resumo.

export const ACAO_LABEL = {
  login_sucesso: 'Login',
  login_falha: 'Login falhou',
  logout: 'Logout',
  usuario_criado: 'Usuário criado',
  usuario_editado: 'Usuário editado',
  usuario_removido: 'Usuário removido',
  permissao_alterada: 'Permissão alterada',
  senha_redefinida: 'Senha redefinida',
  pagamento_registrado: 'Pagamento registrado',
  pagamento_removido: 'Pagamento removido',
  contrato_emitido: 'Contrato emitido',
  contrato_enviado: 'Contrato enviado',
  ajuste_linear_aplicado: 'Ajuste linear aplicado',
  ajuste_linear_desfeito: 'Ajuste linear desfeito',
  preco_materia_atualizado: 'Preço de matéria-prima atualizado',
  parametros_negocio_alterados: 'Parâmetros de negócio alterados',
  config_contrato_alterada: 'Configuração de contrato alterada',
  config_entrega_alterada: 'Configuração de entrega alterada',
  config_whatsapp_alterada: 'Configuração de WhatsApp alterada',
  registro_excluido: 'Registro excluído',
  registro_criado: 'Registro criado',
  registro_atualizado: 'Registro atualizado',
  status_alterado: 'Status alterado',
  item_adicionado: 'Item adicionado',
  orcamento_convertido_em_evento: 'Convertido em evento',
}

export const ACAO_COR = {
  login_sucesso: 'var(--verde)',
  login_falha: '#ef4444',
  logout: 'var(--muted)',
  usuario_criado: 'var(--verde)',
  usuario_editado: 'var(--caramelo)',
  usuario_removido: '#ef4444',
  permissao_alterada: 'var(--caramelo)',
  senha_redefinida: 'var(--caramelo)',
  pagamento_registrado: 'var(--verde)',
  pagamento_removido: '#ef4444',
  contrato_emitido: 'var(--verde)',
  contrato_enviado: 'var(--caramelo)',
  ajuste_linear_aplicado: 'var(--caramelo)',
  ajuste_linear_desfeito: '#ef4444',
  preco_materia_atualizado: 'var(--caramelo)',
  parametros_negocio_alterados: 'var(--caramelo)',
  config_contrato_alterada: 'var(--caramelo)',
  config_entrega_alterada: 'var(--caramelo)',
  config_whatsapp_alterada: 'var(--caramelo)',
  registro_excluido: '#ef4444',
  registro_criado: 'var(--verde)',
  registro_atualizado: 'var(--caramelo)',
  status_alterado: 'var(--caramelo)',
  item_adicionado: 'var(--verde)',
  orcamento_convertido_em_evento: 'var(--verde)',
}

export function dataFmt(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

export function resumo(log) {
  const d = log.detalhes || {}
  switch (log.acao) {
    case 'login_falha':
      return `Tentativa com ${d.email ?? '—'} (${d.motivo ?? '—'})`
    case 'usuario_criado':
      return `${d.criado_nome ?? '—'} (${d.role_inicial ?? '—'})`
    case 'usuario_removido':
      return `${d.removido_nome ?? '—'}`
    case 'permissao_alterada':
      return d.role_antes ? `role: ${d.role_antes} → ${d.role_depois}` : 'permissões alteradas'
    case 'senha_redefinida':
      return `${d.usuario_nome ?? '—'}`
    case 'pagamento_registrado':
    case 'pagamento_removido':
      return `Evento ${d.evento_numero ?? d.evento_id ?? '—'} · R$ ${d.valor ?? '—'} (${d.forma_pagamento ?? '—'})`
    case 'contrato_emitido':
      return `${d.contrato_numero ?? '—'} · ${d.cliente ?? '—'} · R$ ${d.valor_total ?? '—'}`
    case 'contrato_enviado':
      return `${d.contrato_numero ?? '—'} · ${d.cliente ?? '—'} · ${d.telefone ?? '—'}`
    case 'ajuste_linear_aplicado':
      return `${d.descricao ?? '—'} (snapshot #${d.snapshot_id ?? '—'})`
    case 'ajuste_linear_desfeito':
      return `${d.descricao ?? '—'} · ${d.produtos_restaurados ?? 0} produto(s) restaurado(s)`
    case 'preco_materia_atualizado':
      return `${d.materia_nome ?? '—'}: R$ ${d.valor_antigo ?? '—'} → R$ ${d.valor_novo ?? '—'}`
    case 'parametros_negocio_alterados':
    case 'config_contrato_alterada':
    case 'config_entrega_alterada':
    case 'config_whatsapp_alterada':
      return Object.keys(d.depois ?? {}).join(', ') || '—'
    case 'registro_excluido':
      return `${d.model ?? '—'} #${d.id ?? '—'} — ${d.descricao ?? ''}`
    case 'registro_criado':
      return `${d.model ?? '—'} #${d.id ?? '—'} criado — ${d.descricao ?? ''}`
    case 'registro_atualizado':
      return `${d.model ?? '—'} #${d.id ?? '—'}: ${Object.keys(d.campos ?? {}).join(', ') || '—'}`
    case 'status_alterado':
      return `${d.model ?? '—'} ${d.numero ?? d.id ?? '—'}: ${d.de ?? '—'} → ${d.para ?? '—'}`
    case 'item_adicionado':
      return `${d.model ?? '—'} — ${d.nome ?? '—'} (R$ ${d.preco_total ?? '—'})`
    case 'orcamento_convertido_em_evento':
      return `${d.orcamento_numero ?? '—'} → ${d.evento_numero ?? '—'}`
    default:
      return '—'
  }
}
