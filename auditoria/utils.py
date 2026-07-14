import logging

from .models import LogAuditoria

logger = logging.getLogger(__name__)


def _extrair_ip(request):
    if not request:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def ator_ou_none(request):
    """
    Devolve o usuário autenticado da request, ou None se ninguém estiver
    logado — usado por actions oportunistas (não exigem login, mas captam
    o ator quando o token vier) e pelos mixins de auditoria genéricos.
    """
    usuario = getattr(request, 'user', None)
    return usuario if getattr(usuario, 'is_authenticated', False) else None


def registrar(usuario, acao, detalhes=None, request=None):
    """
    Grava um evento em LogAuditoria. Nunca lança exceção pra fora —
    falha de auditoria não pode derrubar login/CRUD de usuário
    (mesmo espírito de 'signals dentro de try/except' do projeto).
    """
    try:
        nome_snapshot = usuario.name if usuario else (detalhes or {}).get('email', '—')
        LogAuditoria.objects.create(
            usuario=usuario,
            usuario_nome_snapshot=nome_snapshot,
            acao=acao,
            detalhes=detalhes or {},
            ip=_extrair_ip(request),
        )
    except Exception:
        logger.exception('Falha ao gravar log de auditoria (acao=%s)', acao)


ACOES_MODIFICACAO_REGISTRO = [
    LogAuditoria.ACAO_REGISTRO_CRIADO,
    LogAuditoria.ACAO_REGISTRO_ATUALIZADO,
    LogAuditoria.ACAO_STATUS_ALTERADO,
]


def ultima_modificacao_por_id(model_name, ids):
    """
    Devolve {id: {'usuario': str|None, 'acao': str, 'data': datetime}} com o
    log mais recente de criação/edição/mudança de status de cada objeto —
    usado pra mostrar "última modificação" em listagens (Orçamento/Evento).
    Não considera item_adicionado/pagamento (esses ficam só na aba
    Histórico do próprio registro, ver historico/ em OrcamentoViewSet/
    EventoViewSet) — aqui é só quem criou/editou/mudou status por último.

    Agrupamento feito em Python (não via distinct('detalhes__id'), que só
    funciona em Postgres) pra continuar rodando também em `manage.py test`
    (settings_test.py usa SQLite).
    """
    ids = list(ids)
    if not ids:
        return {}
    logs = (
        LogAuditoria.objects
        .filter(detalhes__model=model_name, detalhes__id__in=ids, acao__in=ACOES_MODIFICACAO_REGISTRO)
        .order_by('-criado_em')
    )
    por_id = {}
    for log in logs:
        lid = log.detalhes.get('id')
        if lid not in por_id:
            por_id[lid] = {
                'usuario': log.usuario_nome_snapshot or None,
                'acao': log.acao,
                'data': log.criado_em,
            }
    return por_id
