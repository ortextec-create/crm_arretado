from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import ValidationError

from .models import LogAuditoria
from .utils import registrar


class AuditoriaDestroyMixin:
    """
    Audita o destroy() padrão de um ModelViewSet (usar junto com
    authentication_classes = [TokenAuthentication] e get_permissions()
    exigindo IsAuthenticated na action 'destroy' na própria view).

    Também traduz ProtectedError (FK on_delete=PROTECT) numa resposta 400
    amigável em vez do 500 cru do Django — nesse caso nada é auditado,
    já que a exclusão não chegou a acontecer.

    campos_log_exclusao: lista de campos do model a incluir em detalhes,
    além de model/id/descricao (sempre presentes).
    """
    campos_log_exclusao = []

    def perform_destroy(self, instance):
        detalhes = {
            'model': instance.__class__.__name__,
            'id': instance.pk,
            'descricao': str(instance),
        }
        for campo in self.campos_log_exclusao:
            detalhes[campo] = str(getattr(instance, campo, None))

        try:
            super().perform_destroy(instance)
        except ProtectedError as e:
            nomes = sorted({obj.__class__.__name__ for obj in e.protected_objects})
            raise ValidationError(f'Não é possível excluir: está em uso em {", ".join(nomes)}.')

        registrar(self.request.user, LogAuditoria.ACAO_REGISTRO_EXCLUIDO, detalhes=detalhes, request=self.request)
