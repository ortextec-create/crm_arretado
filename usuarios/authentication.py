from rest_framework import authentication, exceptions

from .models import Usuario


class TokenAuthentication(authentication.BaseAuthentication):
    """
    Lê 'Authorization: Token <valor>', busca o Usuario pelo auth_token.
    Popula request.user (Usuario) e request.auth (string do token).
    """
    keyword = 'Token'

    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).decode('utf-8')
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != self.keyword.lower():
            return None

        token = parts[1]
        try:
            usuario = Usuario.objects.get(auth_token=token)
        except Usuario.DoesNotExist:
            raise exceptions.AuthenticationFailed('Token inválido ou expirado.')

        if not usuario.ativo:
            raise exceptions.AuthenticationFailed('Usuário inativo.')

        return (usuario, token)

    def authenticate_header(self, request):
        return self.keyword
