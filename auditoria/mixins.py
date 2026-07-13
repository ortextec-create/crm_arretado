from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import ValidationError

from .models import LogAuditoria
from .utils import ator_ou_none, registrar


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


class AuditoriaCreateMixin:
    """
    Audita o perform_create() padrão de um ModelViewSet, gravando
    ACAO_REGISTRO_CRIADO.

    campos_log_criacao: lista de campos do model a incluir em detalhes,
    além de model/id/descricao (sempre presentes) — mesma convenção de
    campos_log_exclusao no AuditoriaDestroyMixin.
    """
    campos_log_criacao = []

    def perform_create(self, serializer):
        super().perform_create(serializer)
        instance = serializer.instance
        detalhes = {
            'model': instance.__class__.__name__,
            'id': instance.pk,
            'descricao': str(instance),
        }
        for campo in self.campos_log_criacao:
            detalhes[campo] = str(getattr(instance, campo, None))
        registrar(ator_ou_none(self.request), LogAuditoria.ACAO_REGISTRO_CRIADO, detalhes=detalhes, request=self.request)


class AuditoriaUpdateMixin:
    """
    Audita o perform_update() padrão de um ModelViewSet, gravando
    ACAO_REGISTRO_ATUALIZADO só com os campos que vieram no payload da
    requisição (self.request.data) E que de fato mudaram de valor —
    mesmo espírito do antes/depois já usado pelas configs singleton
    (ConfiguracaoContrato/Entrega/WhatsApp).

    campos_log_atualizacao: whitelist de campos elegíveis a entrar no log
    (evita logar campos relacionais/nested, ex: 'itens').
    """
    campos_log_atualizacao = []

    def perform_update(self, serializer):
        instance = serializer.instance
        campos = [c for c in self.campos_log_atualizacao if c in self.request.data]
        antes = {c: str(getattr(instance, c, None)) for c in campos}

        super().perform_update(serializer)

        instance.refresh_from_db()
        depois = {c: str(getattr(instance, c, None)) for c in campos}
        mudou = {c: {'de': antes[c], 'para': depois[c]} for c in campos if antes[c] != depois[c]}

        if mudou:
            registrar(
                ator_ou_none(self.request), LogAuditoria.ACAO_REGISTRO_ATUALIZADO,
                detalhes={'model': instance.__class__.__name__, 'id': instance.pk, 'campos': mudou},
                request=self.request,
            )


class AuditoriaStatusMixin:
    """
    Helper genérico pra logar mudança de status de qualquer objeto com
    atributo .numero (Orcamento, Evento, PedidoPDV...) — chamar
    explicitamente dentro de cada action de status (enviar/aprovar/
    confirmar/etc.), depois do .save().
    """
    def log_mudanca_status(self, obj, de, para):
        registrar(
            ator_ou_none(self.request), LogAuditoria.ACAO_STATUS_ALTERADO,
            detalhes={
                'model': obj.__class__.__name__, 'id': obj.id,
                'numero': getattr(obj, 'numero', None), 'de': de, 'para': para,
            },
            request=self.request,
        )
