from datetime import timedelta
from types import SimpleNamespace

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auditoria.models import LogAuditoria
from auditoria.utils import registrar
from empresas.models import Empresa
from ifood.models import PedidoIFood
from usuarios.authentication import TokenAuthentication
from usuarios.permissions import IsAdminRole

from .authentication import TokenExtensaoAuthentication, TokenExtensaoValido
from .models import (
    ConfiguracaoAtendimento, ConfiguracaoExtensao, MensagemChat, ModeloMensagemChat, TokenExtensao,
)
from .render import renderizar
from .serializers import (
    ConfiguracaoAtendimentoSerializer, ConfiguracaoExtensaoSerializer, MensagemChatSerializer,
    MensagemManualSerializer, ModeloMensagemChatSerializer, PreviewSerializer, TokenExtensaoSerializer,
)
from .servico import enfileirar

ONLINE_SEGUNDOS = 90  # folga pro heartbeat atrasado de aba oculta (throttling do Chrome)
FALHAS_ROTA_JANELA_MIN = 60


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de empresa (duplicados por app de propósito — ver CLAUDE.md)
# ─────────────────────────────────────────────────────────────────────────────

def _resolver_empresa(request):
    """`?empresa=<id>` > `empresa_ativa` do usuário > `Empresa.get_padrao()`. Nunca None aqui."""
    param = request.query_params.get('empresa')
    if param and param != 'todas':
        return get_object_or_404(Empresa, pk=param)
    user = request.user
    if getattr(user, 'empresa_ativa_id', None):
        return user.empresa_ativa
    return Empresa.get_padrao()


def _empresas_do_usuario(usuario):
    if usuario.role == 'admin':
        return list(Empresa.objects.filter(ativo=True))
    vinculadas = list(usuario.empresas.filter(ativo=True))
    return vinculadas or [Empresa.get_padrao()]


def _empresa_validada(request):
    empresa = _resolver_empresa(request)
    if empresa not in _empresas_do_usuario(request.user):
        raise ValidationError({'empresa': 'Empresa fora do vínculo do usuário.'})
    return empresa


class CrmAuthMixin:
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints da extensão (X-Extensao-Token)
# ─────────────────────────────────────────────────────────────────────────────

class ExtensaoBaseView(APIView):
    authentication_classes = [TokenExtensaoAuthentication]
    permission_classes = [TokenExtensaoValido]


class ExtensaoConfigView(ExtensaoBaseView):
    def get(self, request):
        cfg = ConfiguracaoExtensao.get()
        return Response({
            'intervalo_segundos': cfg.intervalo_segundos,
            'pausa_interacao_segundos': cfg.pausa_interacao_segundos,
            'seletores': cfg.seletores,
            'tempos_ms': cfg.tempos_ms,
        })


class ExtensaoHeartbeatView(ExtensaoBaseView):
    def post(self, request):
        token = request.auth
        d = request.data
        token.ultimo_heartbeat = timezone.now()
        token.versao_extensao = str(d.get('versao', ''))[:30]
        token.ultimo_diagnostico = {
            'aba_ok': bool(d.get('aba_ok')),
            'aba_visivel': bool(d.get('aba_visivel', True)),
            'seletores_ok': d.get('seletores_ok') if isinstance(d.get('seletores_ok'), dict) else {},
            'url': str(d.get('url', ''))[:300],
        }
        token.save(update_fields=['ultimo_heartbeat', 'versao_extensao', 'ultimo_diagnostico'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExtensaoReservarView(ExtensaoBaseView):
    def post(self, request):
        cfg = ConfiguracaoExtensao.get()
        agora = timezone.now()
        empresas_ids = list(request.auth.empresas.values_list('id', flat=True))
        with transaction.atomic():
            # Varredura: lease vencido vira `incerta` (nunca volta pra fila); pendente vencida expira.
            MensagemChat.objects.filter(
                status='enviando', reservado_em__lt=agora - timedelta(seconds=cfg.lease_segundos),
            ).update(status='incerta', erro='lease_vencido')
            MensagemChat.objects.filter(status='pendente', expira_em__lt=agora).update(status='expirada')

            msg = (
                MensagemChat.objects
                .select_for_update(skip_locked=True, of=('self',))
                .select_related('pedido', 'empresa')
                .filter(status='pendente', direcao='saida', empresa_id__in=empresas_ids)
                .order_by('criado_em', 'id')
                .first()
            )
            if msg is None:
                return Response(status=status.HTTP_204_NO_CONTENT)
            msg.status = 'enviando'
            msg.reservado_em = agora
            msg.tentativas += 1
            msg.save(update_fields=['status', 'reservado_em', 'tentativas'])
        return Response({
            'id': msg.id, 'display_id': msg.pedido.display_id,
            'texto': msg.texto, 'empresa_nome': msg.empresa.nome,
        })


class ExtensaoResultadoView(ExtensaoBaseView):
    def post(self, request, pk):
        empresas_ids = list(request.auth.empresas.values_list('id', flat=True))
        with transaction.atomic():
            msg = get_object_or_404(
                MensagemChat.objects.select_for_update(), pk=pk, empresa_id__in=empresas_ids,
            )
            if msg.status != 'enviando':
                return Response({'detail': f'Mensagem não está em envio (status: {msg.status}).'}, status=409)
            passos = request.data.get('passos')
            msg.passos = passos if isinstance(passos, list) else []
            if request.data.get('ok') is True:
                msg.status = 'enviada'
                msg.enviado_em = timezone.now()
                msg.erro = ''
            else:
                msg.status = 'falha'
                msg.erro = str(request.data.get('erro', ''))[:1000]
            msg.save(update_fields=['status', 'enviado_em', 'erro', 'passos'])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─────────────────────────────────────────────────────────────────────────────
# CRM — configuração, modelos, mensagens
# ─────────────────────────────────────────────────────────────────────────────

class ConfiguracaoAtendimentoView(CrmAuthMixin, APIView):
    def get(self, request):
        cfg = ConfiguracaoAtendimento.get(_empresa_validada(request))
        return Response(ConfiguracaoAtendimentoSerializer(cfg).data)

    def patch(self, request):
        cfg = ConfiguracaoAtendimento.get(_empresa_validada(request))
        campos = list(request.data.keys())
        antes = {c: str(getattr(cfg, c)) for c in campos if hasattr(cfg, c)}
        ser = ConfiguracaoAtendimentoSerializer(cfg, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        depois = {c: str(getattr(cfg, c)) for c in campos if hasattr(cfg, c)}
        registrar(request.user, LogAuditoria.ACAO_CONFIG_ATENDIMENTO_ALTERADA,
                  detalhes={'empresa': cfg.empresa_id, 'antes': antes, 'depois': depois}, request=request)
        return Response(ser.data)


class ModeloMensagemChatViewSet(
    CrmAuthMixin, mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet,
):
    """Sem DELETE/PUT/POST — desativar via `ativo=False`."""
    serializer_class = ModeloMensagemChatSerializer
    http_method_names = ['get', 'patch', 'post', 'head', 'options']
    pagination_class = None

    def get_queryset(self):
        empresa = _empresa_validada(self.request)
        ModeloMensagemChat.garantir_padroes(empresa)
        return ModeloMensagemChat.objects.filter(empresa=empresa)

    def perform_update(self, serializer):
        antes = {c: str(getattr(serializer.instance, c)) for c in serializer.validated_data}
        serializer.save()
        registrar(self.request.user, LogAuditoria.ACAO_MODELO_ATENDIMENTO_ALTERADO,
                  detalhes={'gatilho': serializer.instance.gatilho, 'antes': antes,
                            'depois': {c: str(v) for c, v in serializer.validated_data.items()}},
                  request=self.request)

    @action(detail=False, methods=['post'], url_path='preview')
    def preview(self, request):
        ser = PreviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        empresa = _empresa_validada(request)
        pedido_id = ser.validated_data.get('pedido_id')
        if pedido_id:
            pedido = get_object_or_404(PedidoIFood, pk=pedido_id, empresa=empresa)
        else:
            pedido = _pedido_ficticio(empresa)
        extra = {'minutos_atraso': 15}
        return Response({'renderizado': renderizar(ser.validated_data['texto'], pedido, extra)})


def _pedido_ficticio(empresa):
    itens = [SimpleNamespace(quantidade=2, nome='Bolo de pote'), SimpleNamespace(quantidade=1, nome='Brigadeiro')]
    return SimpleNamespace(
        empresa=empresa, cliente_nome='Maria da Silva', display_id='1234',
        previsao_entrega=timezone.now() + timedelta(minutes=30),
        itens=SimpleNamespace(all=lambda: itens),
    )


class MensagemChatViewSet(CrmAuthMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Sem DELETE — histórico de atendimento."""
    serializer_class = MensagemChatSerializer

    def get_queryset(self):
        empresa = _empresa_validada(self.request)
        qs = MensagemChat.objects.filter(empresa=empresa).select_related('pedido', 'autor')
        p = self.request.query_params
        if p.get('pedido'):
            qs = qs.filter(pedido_id=p['pedido'])
        if p.get('status'):
            qs = qs.filter(status=p['status'])
        if p.get('direcao'):
            qs = qs.filter(direcao=p['direcao'])
        if p.get('data_inicio'):
            qs = qs.filter(criado_em__date__gte=p['data_inicio'])
        if p.get('data_fim'):
            qs = qs.filter(criado_em__date__lte=p['data_fim'])
        return qs

    @action(detail=False, methods=['post'], url_path='manual')
    def manual(self, request):
        ser = MensagemManualSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        empresa = _empresa_validada(request)
        pedido = get_object_or_404(PedidoIFood.objects.select_related('empresa'),
                                   pk=ser.validated_data['pedido'], empresa=empresa)
        if pedido.status in ('CONCLUDED', 'CANCELLED') and pedido.atualizado_em < timezone.now() - timedelta(hours=24):
            return Response({'detail': 'O chat do iFood já está fechado para este pedido (mais de 24 h).'}, status=400)
        msg = enfileirar(pedido, 'manual', origem='manual', texto=ser.validated_data['texto'], autor=request.user)
        if msg is None:
            return Response({'detail': 'Não foi possível enfileirar a mensagem.'}, status=500)
        return Response(MensagemChatSerializer(msg).data, status=201)

    @action(detail=True, methods=['post'], url_path='cancelar')
    def cancelar(self, request, pk=None):
        msg = self.get_object()
        if msg.status not in ('pendente', 'sugerida'):
            return Response({'detail': f'Só mensagens pendentes/sugeridas podem ser canceladas (status: {msg.status}).'}, status=400)
        # update condicional: se a extensão reservou entre o get e aqui, não sobrescreve
        n = MensagemChat.objects.filter(pk=msg.pk, status__in=('pendente', 'sugerida')).update(status='cancelada')
        if not n:
            return Response({'detail': 'A mensagem já foi reservada para envio.'}, status=409)
        msg.refresh_from_db()
        return Response(MensagemChatSerializer(msg).data)

    @action(detail=True, methods=['post'], url_path='reenviar')
    def reenviar(self, request, pk=None):
        msg = self.get_object()
        if msg.direcao != 'saida' or msg.status not in ('falha', 'incerta', 'expirada'):
            return Response({'detail': 'Só mensagens com falha, incertas ou expiradas podem ser reenviadas.'}, status=400)
        nova = enfileirar(msg.pedido, 'manual', origem='manual', texto=msg.texto, autor=request.user)
        if nova is None:
            return Response({'detail': 'Não foi possível enfileirar a mensagem.'}, status=500)
        return Response(MensagemChatSerializer(nova).data, status=201)


class StatusExtensaoView(CrmAuthMixin, APIView):
    def get(self, request):
        empresa = _empresa_validada(request)
        tokens = TokenExtensao.objects.filter(ativo=True, empresas=empresa, ultimo_heartbeat__isnull=False) \
            .order_by('-ultimo_heartbeat')
        t = tokens.first()
        if t is None:
            return Response({'online': False, 'aba_visivel': True, 'ultimo_heartbeat': None, 'versao': '',
                             'seletores_ok': {}, 'falhas_rota_recentes': 0})
        online = t.ultimo_heartbeat >= timezone.now() - timedelta(seconds=ONLINE_SEGUNDOS)
        return Response({
            'online': online, 'ultimo_heartbeat': t.ultimo_heartbeat, 'versao': t.versao_extensao,
            'aba_visivel': (t.ultimo_diagnostico or {}).get('aba_visivel', True),
            'seletores_ok': (t.ultimo_diagnostico or {}).get('seletores_ok', {}),
            # sequência de rota_nao_abriu = sinal de que o iFood mudou a rota do Gestor
            'falhas_rota_recentes': MensagemChat.objects.filter(
                empresa=empresa, status='falha', erro='rota_nao_abriu',
                criado_em__gte=timezone.now() - timedelta(minutes=FALHAS_ROTA_JANELA_MIN),
            ).count(),
        })


# ─────────────────────────────────────────────────────────────────────────────
# CRM — administração da extensão (admin)
# ─────────────────────────────────────────────────────────────────────────────

class ConfiguracaoExtensaoView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdminRole]

    def get(self, request):
        return Response(ConfiguracaoExtensaoSerializer(ConfiguracaoExtensao.get()).data)

    def patch(self, request):
        cfg = ConfiguracaoExtensao.get()
        campos = list(request.data.keys())
        antes = {c: getattr(cfg, c) for c in campos if hasattr(cfg, c)}
        ser = ConfiguracaoExtensaoSerializer(cfg, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        registrar(request.user, LogAuditoria.ACAO_CONFIG_EXTENSAO_ALTERADA,
                  detalhes={'campos': campos, 'antes': antes}, request=request)
        return Response(ser.data)


class TokenExtensaoViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Sem DELETE — revogar é `ativo=False`."""
    queryset = TokenExtensao.objects.prefetch_related('empresas')
    serializer_class = TokenExtensaoSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdminRole]
    pagination_class = None

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        empresas = ser.validated_data['empresas']
        if not empresas:
            raise ValidationError({'empresas_ids': 'Informe ao menos uma empresa.'})
        obj, token = TokenExtensao.criar(ser.validated_data['nome'], empresas, criado_por=request.user)
        registrar(request.user, LogAuditoria.ACAO_TOKEN_EXTENSAO_CRIADO,
                  detalhes={'id': obj.id, 'nome': obj.nome, 'empresas': [e.id for e in empresas]}, request=request)
        data = TokenExtensaoSerializer(obj).data
        data['token'] = token  # única vez em que o token puro é devolvido
        return Response(data, status=201)

    @action(detail=True, methods=['post'], url_path='revogar')
    def revogar(self, request, pk=None):
        obj = self.get_object()
        obj.ativo = False
        obj.save(update_fields=['ativo'])
        registrar(request.user, LogAuditoria.ACAO_TOKEN_EXTENSAO_REVOGADO,
                  detalhes={'id': obj.id, 'nome': obj.nome}, request=request)
        return Response(TokenExtensaoSerializer(obj).data)
