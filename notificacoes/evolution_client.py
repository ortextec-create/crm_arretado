"""
Cliente HTTP para a Evolution API (WhatsApp self-hosted).

Configuração via settings.py / .env:
  EVOLUTION_API_URL      → ex: http://localhost:8080
  EVOLUTION_API_KEY      → API key da instância
  EVOLUTION_INSTANCE     → nome da instância (ex: arretado)
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_BASE     = getattr(settings, 'EVOLUTION_API_URL', '').rstrip('/')
_KEY      = getattr(settings, 'EVOLUTION_API_KEY', '')
_INSTANCE = getattr(settings, 'EVOLUTION_INSTANCE', 'arretado')


class EvolutionError(Exception):
    pass


def _headers():
    return {'apikey': _KEY, 'Content-Type': 'application/json'}


def _fone(numero: str) -> str:
    """Normaliza para formato internacional sem '+': 5586999999999."""
    digitos = ''.join(c for c in numero if c.isdigit())
    if len(digitos) <= 11 and not digitos.startswith('55'):
        digitos = '55' + digitos
    return digitos


def enviar_texto(numero: str, texto: str) -> dict:
    """
    POST /message/sendText/{instance}
    Retorna o payload de resposta da API ou lança EvolutionError.
    """
    if not _BASE or not _KEY:
        raise EvolutionError('Evolution API não configurada (EVOLUTION_API_URL / EVOLUTION_API_KEY ausentes)')

    url  = f'{_BASE}/message/sendText/{_INSTANCE}'
    body = {'number': _fone(numero), 'text': texto}

    try:
        resp = requests.post(url, json=body, headers=_headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        msg = f'HTTP {resp.status_code}: {resp.text[:200]}'
        logger.error('Evolution API error: %s', msg)
        raise EvolutionError(msg) from e
    except requests.RequestException as e:
        logger.error('Evolution API connection error: %s', e)
        raise EvolutionError(str(e)) from e


def status_conexao() -> dict:
    """
    GET /instance/connectionState/{instance}
    Retorna dict com 'state' (open | close | connecting) ou lança EvolutionError.
    """
    if not _BASE or not _KEY:
        return {'state': 'not_configured'}

    url = f'{_BASE}/instance/connectionState/{_INSTANCE}'
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.warning('Não foi possível checar status Evolution API: %s', e)
        raise EvolutionError(str(e)) from e
