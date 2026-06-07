"""
Cliente Twilio para envio de mensagens WhatsApp.

Configuração via .env:
  TWILIO_ACCOUNT_SID      → Account SID (AC...)
  TWILIO_AUTH_TOKEN       → Auth Token
  TWILIO_WHATSAPP_FROM    → número Twilio com prefixo whatsapp: (ex: whatsapp:+14155238886)
  TWILIO_CONTENT_SID      → SID do Content Template {{1}} (HX...)
"""
import json
import logging
from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

_SID         = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
_TOKEN       = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
_FROM        = getattr(settings, 'TWILIO_WHATSAPP_FROM', '')
_CONTENT_SID = getattr(settings, 'TWILIO_CONTENT_SID', '')


class TwilioError(Exception):
    pass


def _fone(numero: str) -> str:
    """Normaliza para formato E.164 com prefixo whatsapp:."""
    digitos = ''.join(c for c in numero if c.isdigit())
    if not digitos.startswith('55'):
        digitos = '55' + digitos
    return f'whatsapp:+{digitos}'


def enviar_texto(numero: str, texto: str) -> dict:
    if not _SID or not _TOKEN or not _FROM:
        raise TwilioError('Twilio não configurado (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_FROM ausentes)')

    try:
        client = Client(_SID, _TOKEN)

        kwargs = dict(from_=_FROM, to=_fone(numero))

        if _CONTENT_SID:
            kwargs['content_sid'] = _CONTENT_SID
            kwargs['content_variables'] = json.dumps({'1': texto})
        else:
            kwargs['body'] = texto

        msg = client.messages.create(**kwargs)
        return {'sid': msg.sid, 'status': msg.status}
    except TwilioRestException as e:
        logger.error('Twilio error: %s', e)
        raise TwilioError(str(e)) from e


def status_conexao() -> dict:
    """Verifica se as credenciais Twilio são válidas."""
    if not _SID or not _TOKEN:
        return {'state': 'not_configured'}

    try:
        client = Client(_SID, _TOKEN)
        account = client.api.accounts(_SID).fetch()
        return {'state': 'open', 'status': account.status}
    except TwilioRestException as e:
        logger.warning('Twilio status check failed: %s', e)
        raise TwilioError(str(e)) from e
