from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Autenticado + role == 'admin'. Reusado por auditoria (e futuros apps críticos)."""
    message = 'Apenas administradores podem acessar este recurso.'

    def has_permission(self, request, view):
        usuario = request.user
        return bool(usuario and getattr(usuario, 'is_authenticated', False) and usuario.role == 'admin')
