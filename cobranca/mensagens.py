"""
Renderização de mensagens da régua de cobrança — variáveis `{var}`, nunca
str.format()/format_map() (ver COBRANCA.md: chave com '.'/'[' ou texto com
'{}' literal derruba o envio com str.format).
"""
import re
from datetime import timedelta

from rest_framework.exceptions import ValidationError

from empresas.models import Empresa

VARS_COMUNS = [
    'primeiro_nome', 'nome', 'numero_evento', 'tipo_evento', 'data_evento',
    'valor_total', 'valor_pago', 'saldo', 'data_limite', 'dias_para_limite',
    'dias_em_atraso', 'dias_para_evento', 'chave_pix', 'favorecido_pix',
    'telefone_empresa', 'empresa',
]
VAR_PRAZO = 'prazo_combinado'
VARS = VARS_COMUNS + [VAR_PRAZO]

_PADRAO_VAR = re.compile(r'\{(\w+)\}')


def _brl(valor) -> str:
    v = float(valor or 0)
    s = f'{v:,.2f}'
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')


def _data_br(d) -> str:
    if not d:
        return ''
    return d.strftime('%d/%m/%Y')


def render(texto: str, contexto: dict) -> str:
    """Substitui {var} pelo valor em contexto. Variável ausente → string vazia."""
    return _PADRAO_VAR.sub(lambda m: str(contexto.get(m.group(1), '')), texto or '')


def montar_contexto(evento, cfg, hoje, pausa=None) -> dict:
    data_evento = evento.data_evento
    data_limite = data_evento + timedelta(days=cfg.limite_lembrete)
    saldo = max(evento.valor_total - evento.sinal_pago, 0)
    nome = evento.nome_cliente_display

    contexto = {
        'primeiro_nome': (nome or '').split(' ')[0],
        'nome': nome,
        'numero_evento': evento.numero,
        'tipo_evento': evento.get_tipo_evento_display(),
        'data_evento': _data_br(data_evento),
        'valor_total': _brl(evento.valor_total),
        'valor_pago': _brl(evento.sinal_pago),
        'saldo': _brl(saldo),
        'data_limite': _data_br(data_limite),
        'dias_para_limite': str(max((data_limite - hoje).days, 0)),
        'dias_em_atraso': str(max((hoje - data_limite).days, 0)),
        'dias_para_evento': str(max((data_evento - hoje).days, 0)),
        'chave_pix': cfg.chave_pix,
        'favorecido_pix': cfg.favorecido_pix,
        'telefone_empresa': cfg.telefone_contato,
        'empresa': Empresa.get_padrao().nome,
    }
    if pausa is not None:
        contexto['prazo_combinado'] = _data_br(pausa.pausado_ate)
    return contexto


def contexto_ficticio(cfg, hoje, permitir_prazo=False) -> dict:
    """Contexto de exemplo pra prévia quando não há evento elegível na base."""
    data_evento = hoje + timedelta(days=15)
    data_limite = data_evento + timedelta(days=cfg.limite_lembrete)
    contexto = {
        'primeiro_nome': 'Maria', 'nome': 'Maria Silva', 'numero_evento': 'EV-0000',
        'tipo_evento': 'Aniversário', 'data_evento': _data_br(data_evento),
        'valor_total': _brl(1000), 'valor_pago': _brl(500), 'saldo': _brl(500),
        'data_limite': _data_br(data_limite),
        'dias_para_limite': str(max((data_limite - hoje).days, 0)),
        'dias_em_atraso': str(max((hoje - data_limite).days, 0)),
        'dias_para_evento': str(max((data_evento - hoje).days, 0)),
        'chave_pix': cfg.chave_pix or '(chave Pix não configurada)',
        'favorecido_pix': cfg.favorecido_pix,
        'telefone_empresa': cfg.telefone_contato,
        'empresa': Empresa.get_padrao().nome,
    }
    if permitir_prazo:
        contexto['prazo_combinado'] = _data_br(hoje + timedelta(days=5))
    return contexto


def variaveis_invalidas(texto: str, permitir_prazo: bool) -> list:
    """Lista (sem efeito colateral) das variáveis usadas no texto que não
    deveriam estar lá — desconhecidas, ou {prazo_combinado} fora de
    contexto que o permita. Usado pela prévia (etapas/preview/, AllowAny)."""
    usadas = set(_PADRAO_VAR.findall(texto or ''))
    permitidas = set(VARS) if permitir_prazo else set(VARS_COMUNS)
    invalidas = usadas - permitidas
    if not permitir_prazo and VAR_PRAZO in usadas:
        invalidas.add(VAR_PRAZO)
    return sorted(invalidas)


def validar_texto(texto: str, permitir_prazo: bool):
    """Levanta ValidationError (DRF) se o texto tiver variável desconhecida,
    usar {prazo_combinado} fora de contexto que o permita, ou estiver vazio."""
    texto = (texto or '').strip()
    if not texto:
        raise ValidationError({'mensagem': ['O texto não pode ficar vazio.']})

    invalidas = variaveis_invalidas(texto, permitir_prazo)
    if VAR_PRAZO in invalidas and not permitir_prazo:
        raise ValidationError({'mensagem': [f'Variável desconhecida: {{{VAR_PRAZO}}} — não existe pausa neste contexto.']})
    if invalidas:
        nomes = ', '.join(f'{{{v}}}' for v in invalidas)
        raise ValidationError({'mensagem': [f'Variável desconhecida: {nomes}']})
