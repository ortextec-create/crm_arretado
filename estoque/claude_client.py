"""
Cliente da API Claude (Anthropic) para o fallback de IA multimodal na
importação de nota fiscal (fase 7). Chamada HTTP pura via `requests`
(sem SDK), mesmo espírito leve de `notificacoes/zapi_client.py`.

API key nunca fica em model/banco — sempre ANTHROPIC_API_KEY (.env/settings).
Custo é da Ortex, não do cliente (decisão de negócio — ver CLAUDE.md).
"""
import base64
import json
import logging

import requests
from django.conf import settings

from .models import ConfiguracaoIA

logger = logging.getLogger(__name__)

_URL = 'https://api.anthropic.com/v1/messages'
_ANTHROPIC_VERSION = '2023-06-01'

PROMPT_EXTRACAO = (
    'Você é um assistente de extração de dados de notas fiscais brasileiras (NF-e/DANFE). '
    'Extraia os dados da nota fiscal na imagem/documento anexado e responda APENAS com um '
    'JSON puro, sem markdown, sem crases, sem texto antes ou depois, no seguinte formato exato:\n'
    '{"numero_nota": "8821", "fornecedor_nome": "Distribuidora Center Doces", '
    '"itens": [{"descricao": "Choc. Fracionado 70% 1kg", "quantidade": 3, "valor_unitario": 42.50}]}\n'
    'Use ponto como separador decimal. Se não conseguir identificar algum campo, use string vazia '
    'ou lista vazia — nunca invente dados.'
)


class ClaudeAPIError(Exception):
    pass


def extrair_nota_fiscal(conteudo_bytes: bytes, media_type: str) -> dict:
    """
    Envia o arquivo (imagem ou PDF) em base64 pra API Claude e espera de
    volta um JSON com numero_nota/fornecedor_nome/itens. Lança
    ClaudeAPIError em qualquer falha (sem chave, erro HTTP, resposta que
    não é JSON válido) — o chamador decide o que fazer (cascata cai pra
    metodo_extracao='falhou', nunca trava o fluxo).
    """
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
    if not api_key:
        raise ClaudeAPIError('ANTHROPIC_API_KEY não configurada')

    cfg = ConfiguracaoIA.get()
    if not cfg.extracao_ia_ativa:
        raise ClaudeAPIError('Extração via IA desativada na configuração')

    tipo_bloco = 'document' if media_type == 'application/pdf' else 'image'
    b64 = base64.b64encode(conteudo_bytes).decode('utf-8')

    body = {
        'model': cfg.modelo,
        'max_tokens': 2048,
        'messages': [{
            'role': 'user',
            'content': [
                {'type': tipo_bloco, 'source': {'type': 'base64', 'media_type': media_type, 'data': b64}},
                {'type': 'text', 'text': PROMPT_EXTRACAO},
            ],
        }],
    }
    headers = {
        'x-api-key': api_key,
        'anthropic-version': _ANTHROPIC_VERSION,
        'content-type': 'application/json',
    }

    try:
        resp = requests.post(_URL, json=body, headers=headers, timeout=cfg.timeout_segundos)
        resp.raise_for_status()
    except requests.HTTPError as e:
        msg = f'HTTP {resp.status_code}: {resp.text[:200]}'
        logger.error('Claude API error: %s', msg)
        raise ClaudeAPIError(msg) from e
    except requests.RequestException as e:
        logger.error('Claude API connection error: %s', e)
        raise ClaudeAPIError(str(e)) from e

    try:
        texto = resp.json()['content'][0]['text']
        dados = json.loads(texto.strip())
    except (KeyError, IndexError, ValueError, json.JSONDecodeError) as e:
        logger.error('Falha ao interpretar resposta da Claude API: %s', e)
        raise ClaudeAPIError(f'Resposta da IA não é um JSON válido: {e}') from e

    return dados
