from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission

from .models import TokenExtensao, hash_token


class TokenExtensaoAuthentication(BaseAuthentication):
    """Lê `X-Extensao-Token`. Usada SÓ nos endpoints /extensao/. `request.auth` = TokenExtensao."""

    def authenticate(self, request):
        valor = request.META.get('HTTP_X_EXTENSAO_TOKEN')
        if not valor:
            return None
        token = TokenExtensao.objects.filter(token_hash=hash_token(valor), ativo=True).first()
        if token is None:
            raise AuthenticationFailed('Token da extensão inválido ou revogado.')
        return (None, token)

    def authenticate_header(self, request):
        return 'X-Extensao-Token'


class TokenExtensaoValido(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.auth, TokenExtensao)
