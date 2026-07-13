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
