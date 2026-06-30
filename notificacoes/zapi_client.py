"""
Cliente Z-API para envio de mensagens WhatsApp.
Credenciais carregadas do banco (ConfiguracaoWhatsApp) com fallback para .env.
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_BASE = 'https://api.z-api.io/instances'

# Fallback para .env (usado quando o banco ainda não está disponível)
_INSTANCE_ENV     = getattr(settings, 'ZAPI_INSTANCE_ID', '')
_TOKEN_ENV        = getattr(settings, 'ZAPI_TOKEN', '')
_CLIENT_TOKEN_ENV = getattr(settings, 'ZAPI_CLIENT_TOKEN', '')


class ZAPIError(Exception):
    pass


def _credenciais():
    """Retorna (instance_id, token, client_token) do banco ou do .env."""
    try:
        from notificacoes.models import ConfiguracaoWhatsApp
        cfg = ConfiguracaoWhatsApp.objects.filter(pk=1).first()
        if cfg and cfg.zapi_instance_id:
            return cfg.zapi_instance_id, cfg.zapi_token, cfg.zapi_client_token
    except Exception:
        pass
    return _INSTANCE_ENV, _TOKEN_ENV, _CLIENT_TOKEN_ENV


def _headers(client_token: str) -> dict:
    return {'Client-Token': client_token, 'Content-Type': 'application/json'}


def _normalizar(numero: str) -> str:
    digitos = ''.join(c for c in numero if c.isdigit())
    if not digitos.startswith('55'):
        digitos = '55' + digitos
    return digitos


def _resolver_fone(numero: str, instance: str, token: str, client_token: str) -> str:
    """Consulta o Z-API para obter o número canônico registrado no WhatsApp."""
    fone = _normalizar(numero)
    try:
        url  = f'{_BASE}/{instance}/token/{token}/phone-exists/{fone}'
        resp = requests.get(url, headers=_headers(client_token), timeout=10)
        if resp.ok:
            data = resp.json()
            if data.get('exists') and data.get('phone'):
                return data['phone']
    except requests.RequestException:
        pass
    return fone


def enviar_texto(numero: str, texto: str) -> dict:
    instance, token, client_token = _credenciais()

    if not instance or not token or not client_token:
        raise ZAPIError('Z-API não configurada (verifique credenciais em Configurações → WhatsApp)')

    fone = _resolver_fone(numero, instance, token, client_token)
    url  = f'{_BASE}/{instance}/token/{token}/send-text'
    body = {'phone': fone, 'message': texto}

    try:
        resp = requests.post(url, json=body, headers=_headers(client_token), timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        msg = f'HTTP {resp.status_code}: {resp.text[:200]}'
        logger.error('Z-API error: %s', msg)
        raise ZAPIError(msg) from e
    except requests.RequestException as e:
        logger.error('Z-API connection error: %s', e)
        raise ZAPIError(str(e)) from e


def enviar_documento(numero: str, pdf_bytes: bytes, nome_arquivo: str, caption: str = '') -> dict:
    import base64
    instance, token, client_token = _credenciais()

    if not instance or not token or not client_token:
        raise ZAPIError('Z-API não configurada (verifique credenciais em Configurações → WhatsApp)')

    extensao = nome_arquivo.rsplit('.', 1)[-1].lower() if '.' in nome_arquivo else 'pdf'
    fone = _resolver_fone(numero, instance, token, client_token)
    url  = f'{_BASE}/{instance}/token/{token}/send-document/{extensao}'
    b64  = base64.b64encode(pdf_bytes).decode('utf-8')
    body: dict = {
        'phone':    fone,
        'document': f'data:application/{extensao};base64,{b64}',
        'fileName': nome_arquivo,
    }
    if caption:
        body['caption'] = caption

    try:
        resp = requests.post(url, json=body, headers=_headers(client_token), timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        msg = f'HTTP {resp.status_code}: {resp.text[:200]}'
        logger.error('Z-API error (documento): %s', msg)
        raise ZAPIError(msg) from e
    except requests.RequestException as e:
        logger.error('Z-API connection error (documento): %s', e)
        raise ZAPIError(str(e)) from e


def status_conexao() -> dict:
    instance, token, client_token = _credenciais()

    if not instance or not token:
        return {'state': 'not_configured'}

    url = f'{_BASE}/{instance}/token/{token}/status'
    try:
        resp = requests.get(url, headers=_headers(client_token), timeout=10)
        resp.raise_for_status()
        data  = resp.json()
        state = 'open' if data.get('connected') else 'close'
        return {'state': state, **data}
    except requests.RequestException as e:
        logger.warning('Z-API status check failed: %s', e)
        raise ZAPIError(str(e)) from e
