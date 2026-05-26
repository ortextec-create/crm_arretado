"""
Cliente para a Merchant API do iFood.
Documentação: https://developer.ifood.com.br/
Base URL:     https://merchant-api.ifood.com.br
"""
import logging
from datetime import timedelta

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

IFOOD_BASE      = 'https://merchant-api.ifood.com.br'
AUTH_URL        = f'{IFOOD_BASE}/authentication/v1.0/oauth/token'
POLLING_URL     = f'{IFOOD_BASE}/order/v1.0/events:polling'
#ACK_URL        = f'{IFOOD_BASE}/order/v1.0/events:acknowledgment'
ACK_URL         = f'{IFOOD_BASE}/order/v1.0/orders:acknowledgment'
ORDER_URL       = f'{IFOOD_BASE}/order/v1.0/orders/{{order_id}}'
CONFIRM_URL     = f'{IFOOD_BASE}/order/v1.0/orders/{{order_id}}/confirm'
CANCEL_URL      = f'{IFOOD_BASE}/order/v1.0/orders/{{order_id}}/requestCancellation'
DISPATCH_URL    = f'{IFOOD_BASE}/order/v1.0/orders/{{order_id}}/dispatch'
PICKUP_URL      = f'{IFOOD_BASE}/order/v1.0/orders/{{order_id}}/readyToPickup'
CANCEL_REASONS  = f'{IFOOD_BASE}/order/v1.0/orders/{{order_id}}/cancellationReasons'


class IFoodAPIError(Exception):
    def __init__(self, message, status_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response    = response


class IFoodClient:
    """
    Wrapper completo da Merchant API do iFood.
    Gerencia token OAuth automaticamente a partir do model ConfiguracaoIFood.
    """

    def __init__(self, config):
        """
        config: instância de ConfiguracaoIFood
        """
        self.config = config
        self._session = requests.Session()
        self._session.headers.update({'Content-Type': 'application/json'})

    # ─── AUTENTICAÇÃO ────────────────────────────────────────────────────────

    def autenticar(self):
        """
        Obtém access_token via client_credentials.
        Atualiza o model config automaticamente.
        """
        payload = {
            'grantType':    'client_credentials',
            'clientId':     self.config.client_id,
            'clientSecret': self.config.client_secret,
        }
        resp = requests.post(
            AUTH_URL,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data=payload,
            timeout=15,
        )
        if resp.status_code != 200:
            raise IFoodAPIError(
                f'Falha na autenticação iFood: {resp.text}',
                status_code=resp.status_code,
            )
        data = resp.json()
        expires_in = data.get('expiresIn', 21600)  # default 6h

        self.config.access_token    = data['accessToken']
        self.config.refresh_token   = data.get('refreshToken', '')
        self.config.token_expira_em = timezone.now() + timedelta(seconds=expires_in)
        self.config.save(update_fields=['access_token', 'refresh_token', 'token_expira_em'])

        logger.info('Token iFood obtido, expira em %s', self.config.token_expira_em)
        return data['accessToken']

    def _get_token(self):
        """Retorna token válido, renovando se necessário."""
        if not self.config.token_valido:
            self.autenticar()
        return self.config.access_token

    def _headers(self):
        return {'Authorization': f'Bearer {self._get_token()}'}

    def _request(self, method, url, **kwargs):
        """Executa request com tratamento de erro e retry de auth."""
        kwargs.setdefault('timeout', 20)
        resp = self._session.request(method, url, headers=self._headers(), **kwargs)

        # Token expirado em produção → renova e repete uma vez
        if resp.status_code == 401:
            self.autenticar()
            resp = self._session.request(method, url, headers=self._headers(), **kwargs)

        if not resp.ok:
            raise IFoodAPIError(
                f'{method} {url} → {resp.status_code}: {resp.text[:300]}',
                status_code=resp.status_code,
                response=resp,
            )
        return resp

    # ─── POLLING DE EVENTOS ──────────────────────────────────────────────────

    def polling(self):
        """
        GET /order/v1.0/orders:polling
        Retorna lista de eventos. Deve ser chamado a cada 30 segundos.
        """
        headers = {
            **self._headers(),
            'x-polling-merchants': self.config.merchant_id,
        }
        resp = self._session.get(POLLING_URL, headers=headers, timeout=20)
        if resp.status_code == 401:
            self.autenticar()
            headers['Authorization'] = f'Bearer {self.config.access_token}'
            resp = self._session.get(POLLING_URL, headers=headers, timeout=20)

        if resp.status_code == 204:
            return []  # sem eventos

        if not resp.ok:
            raise IFoodAPIError(f'Polling falhou: {resp.status_code} {resp.text[:200]}', resp.status_code)

        # Atualiza timestamp de último polling
        self.config.ultimo_polling = timezone.now()
        self.config.save(update_fields=['ultimo_polling'])

        return resp.json() if resp.text else []

    def acknowledgment(self, event_ids: list):
        """
        POST /order/v1.0/orders:acknowledgment
        Confirma recebimento dos eventos para o iFood não reenviar.
        """
        if not event_ids:
            return
        # API aceita até 2000 IDs por request
        for chunk in _chunks(event_ids, 2000):
            self._request(
                'POST', ACK_URL,
                json={'acknowledgedEventIds': chunk},
            )
        logger.info('ACK enviado para %d eventos', len(event_ids))

    # ─── PEDIDOS ─────────────────────────────────────────────────────────────

    def get_order(self, order_id: str) -> dict:
        """GET /order/v1.0/orders/{id}"""
        resp = self._request('GET', ORDER_URL.format(order_id=order_id))
        return resp.json()

    def confirm_order(self, order_id: str):
        """POST /order/v1.0/orders/{id}/confirm"""
        self._request('POST', CONFIRM_URL.format(order_id=order_id))
        logger.info('Pedido %s confirmado', order_id)

    def dispatch_order(self, order_id: str):
        """POST /order/v1.0/orders/{id}/dispatch — saiu para entrega"""
        self._request('POST', DISPATCH_URL.format(order_id=order_id))

    def ready_to_pickup(self, order_id: str):
        """POST /order/v1.0/orders/{id}/readyToPickup — pronto para retirada"""
        self._request('POST', PICKUP_URL.format(order_id=order_id))

    def get_cancellation_reasons(self, order_id: str) -> list:
        """GET /order/v1.0/orders/{id}/cancellationReasons"""
        resp = self._request('GET', CANCEL_REASONS.format(order_id=order_id))
        return resp.json().get('reasons', resp.json()) if resp.text else []

    def cancel_order(self, order_id: str, reason_code: str, reason_description: str = ''):
        """POST /order/v1.0/orders/{id}/requestCancellation"""
        self._request(
            'POST',
            CANCEL_URL.format(order_id=order_id),
            json={'cancellationCode': reason_code, 'reason': reason_description},
        )
        logger.info('Cancelamento solicitado para pedido %s (código %s)', order_id, reason_code)

    # ─── TESTE DE CONEXÃO ────────────────────────────────────────────────────

    def testar_conexao(self) -> dict:
        """Autentica e verifica se o token é válido."""
        try:
            token = self.autenticar()
            return {'ok': True, 'token_preview': token[:20] + '...', 'expira_em': str(self.config.token_expira_em)}
        except IFoodAPIError as e:
            return {'ok': False, 'erro': str(e), 'status_code': e.status_code}


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]
