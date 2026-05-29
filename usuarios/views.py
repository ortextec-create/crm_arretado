from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Usuario
from .serializers import UsuarioSerializer, RedefinirSenhaSerializer


class CsrfExemptMixin:
    """Remove SessionAuthentication — evita 403 em POSTs sem CSRF token."""
    authentication_classes = []


class UsuarioViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = Usuario.objects.all()
    serializer_class   = UsuarioSerializer
    permission_classes = [AllowAny]
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ['name', 'email', 'role', 'criado_em']
    ordering           = ['name']
    # IMPORTANTE: NÃO definir http_method_names aqui — deixar o DRF gerenciar
    # livremente para que as @action(methods=['post']) funcionem corretamente.

    def get_queryset(self):
        qs     = super().get_queryset()
        params = self.request.query_params

        role = params.get('role')
        if role:
            qs = qs.filter(role=role)

        ativo = params.get('ativo')
        if ativo == 'true':
            qs = qs.filter(ativo=True)
        elif ativo == 'false':
            qs = qs.filter(ativo=False)

        return qs

    # ── Login ─────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='login', url_name='login')
    def login(self, request):
        """
        POST /api/v1/usuarios/login/
        Body: { "email": "...", "password": "..." }
        """
        email    = (request.data.get('email') or '').strip().lower()
        password = request.data.get('password') or ''

        if not email or not password:
            return Response(
                {'detail': 'Informe e-mail e senha.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            usuario = Usuario.objects.get(email__iexact=email)
        except Usuario.DoesNotExist:
            return Response(
                {'detail': 'E-mail ou senha incorretos.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not usuario.ativo:
            return Response(
                {'detail': 'Usuário inativo. Fale com o administrador.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not usuario.check_password(password):
            return Response(
                {'detail': 'E-mail ou senha incorretos.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        usuario.last_login = timezone.now()
        usuario.save(update_fields=['last_login'])

        return Response(UsuarioSerializer(usuario).data, status=status.HTTP_200_OK)

    # ── Destroy com proteção ──────────────────────────────────────────────────

    def destroy(self, request, *args, **kwargs):
        usuario = self.get_object()
        if usuario.role == 'admin':
            restantes = Usuario.objects.filter(role='admin').exclude(pk=usuario.pk).count()
            if restantes == 0:
                return Response(
                    {'detail': 'Não é possível remover o único administrador.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        usuario.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Redefinir senha ───────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='redefinir-senha')
    def redefinir_senha(self, request, pk=None):
        usuario = self.get_object()
        serializer = RedefinirSenhaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        usuario.set_password(serializer.validated_data['password'])
        usuario.save(update_fields=['password', 'atualizado_em'])
        return Response({'detail': 'Senha redefinida com sucesso.'})