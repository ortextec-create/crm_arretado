from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .authentication import TokenAuthentication
from .models import Usuario, gerar_token
from .serializers import UsuarioSerializer, RedefinirSenhaSerializer

from auditoria.models import LogAuditoria
from auditoria.utils import registrar


class CsrfExemptMixin:
    """Remove SessionAuthentication — evita 403 em POSTs sem CSRF token."""
    authentication_classes = []


class UsuarioViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = Usuario.objects.all()
    serializer_class   = UsuarioSerializer
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ['name', 'email', 'role', 'criado_em']
    ordering           = ['name']
    # Sobrescreve o [] do CsrfExemptMixin — este ViewSet exige token real (exceto login/)
    authentication_classes = [TokenAuthentication]
    # IMPORTANTE: NÃO definir http_method_names aqui — deixar o DRF gerenciar
    # livremente para que as @action(methods=['post']) funcionem corretamente.

    def get_permissions(self):
        if self.action == 'login':
            return [AllowAny()]
        return [IsAuthenticated()]

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
            registrar(
                None, LogAuditoria.ACAO_LOGIN_FALHA,
                detalhes={'email': email, 'motivo': 'usuario_nao_encontrado'}, request=request,
            )
            return Response(
                {'detail': 'E-mail ou senha incorretos.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not usuario.ativo:
            registrar(
                usuario, LogAuditoria.ACAO_LOGIN_FALHA,
                detalhes={'email': email, 'motivo': 'usuario_inativo'}, request=request,
            )
            return Response(
                {'detail': 'Usuário inativo. Fale com o administrador.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not usuario.check_password(password):
            registrar(
                usuario, LogAuditoria.ACAO_LOGIN_FALHA,
                detalhes={'email': email, 'motivo': 'senha_incorreta'}, request=request,
            )
            return Response(
                {'detail': 'E-mail ou senha incorretos.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        usuario.auth_token = gerar_token()
        usuario.last_login = timezone.now()
        usuario.save(update_fields=['auth_token', 'last_login'])

        registrar(usuario, LogAuditoria.ACAO_LOGIN_SUCESSO, request=request)

        data = UsuarioSerializer(usuario).data
        data['token'] = usuario.auth_token
        return Response(data, status=status.HTTP_200_OK)

    # ── Logout ────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='logout', url_name='logout')
    def logout(self, request):
        usuario = request.user
        registrar(usuario, LogAuditoria.ACAO_LOGOUT, request=request)
        usuario.auth_token = None
        usuario.save(update_fields=['auth_token'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Create/Update instrumentados ─────────────────────────────────────────

    def perform_create(self, serializer):
        usuario = serializer.save()
        registrar(
            self.request.user, LogAuditoria.ACAO_USUARIO_CRIADO,
            detalhes={
                'criado_id': usuario.id, 'criado_nome': usuario.name,
                'criado_email': usuario.email, 'role_inicial': usuario.role,
            },
            request=self.request,
        )

    def perform_update(self, serializer):
        usuario     = serializer.instance
        role_antes  = usuario.role
        perms_antes = dict(usuario.perms or {})

        usuario = serializer.save()

        mudou_role  = role_antes != usuario.role
        mudou_perms = perms_antes != (usuario.perms or {})

        detalhes = {'editado_id': usuario.id, 'editado_nome': usuario.name}
        if mudou_role:
            detalhes.update(role_antes=role_antes, role_depois=usuario.role)
        if mudou_perms:
            detalhes.update(perms_antes=perms_antes, perms_depois=usuario.perms)

        acao = (
            LogAuditoria.ACAO_PERMISSAO_ALTERADA if (mudou_role or mudou_perms)
            else LogAuditoria.ACAO_USUARIO_EDITADO
        )
        registrar(self.request.user, acao, detalhes=detalhes, request=self.request)

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

        registrar(
            request.user, LogAuditoria.ACAO_USUARIO_REMOVIDO,
            detalhes={'removido_id': usuario.id, 'removido_nome': usuario.name, 'removido_email': usuario.email},
            request=request,
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

        registrar(
            request.user, LogAuditoria.ACAO_SENHA_REDEFINIDA,
            detalhes={'usuario_id': usuario.id, 'usuario_nome': usuario.name},
            request=request,
        )
        return Response({'detail': 'Senha redefinida com sucesso.'})
