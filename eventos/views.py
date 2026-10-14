import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status, filters, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import (
    LocalEvento, Evento, ItemEvento, PagamentoEvento, Orcamento, ItemOrcamento,
    ImagemInspiracao, Contrato, AditivoContrato, ConfiguracaoContrato,
    ConfiguracaoAlertaEvento, TelefoneAlertaEvento, AdiamentoEvento, RemarcacaoEvento,
)
from . import adiamento as regras_adiamento
from notificacoes.servico import notificar, _fone_pedido
from usuarios.authentication import TokenAuthentication
from auditoria.models import LogAuditoria
from auditoria.utils import registrar, ator_ou_none, ultima_modificacao_por_id
from auditoria.mixins import (
    AuditoriaCreateMixin, AuditoriaDestroyMixin, AuditoriaStatusMixin, AuditoriaUpdateMixin,
)
from auditoria.serializers import LogAuditoriaSerializer


def _notificar_evento(evento, mensagem):
    notificar(_fone_pedido(evento), mensagem, cliente=evento.cliente, tipo='pedido')


MSG_EVENTO_REMARCADO = '📅 Sua encomenda #{numero} foi remarcada para {data}{hora}. Qualquer dúvida, estamos por aqui!'
MSG_EVENTO_ADIADO = '⏸️ Sua encomenda #{numero} foi adiada. Assim que tiver a nova data, é só nos avisar.'
MSG_EVENTO_CANCELADO = '❌ Sua encomenda #{numero} foi cancelada. Entre em contato se precisar de ajuda.'


def _msg_remarcado(evento):
    hora = f' às {evento.hora_evento.strftime("%H:%M")}' if evento.hora_evento else ''
    return MSG_EVENTO_REMARCADO.format(
        numero=evento.numero, data=evento.data_evento.strftime('%d/%m/%Y'), hora=hora,
    )


def _erro(detail, mensagem):
    return Response({'detail': detail, 'mensagem': mensagem}, status=status.HTTP_400_BAD_REQUEST)


def _parse_data(valor):
    try:
        return datetime.date.fromisoformat(str(valor))
    except (ValueError, TypeError):
        return None


def _parse_hora(valor):
    if not valor:
        return None
    try:
        return datetime.time.fromisoformat(str(valor))
    except (ValueError, TypeError):
        return False


def _nome_ator(user):
    return getattr(user, 'name', '') or ''


def _campos_entrada_contrato(request):
    """Snapshot opcional da entrada paga no ato da assinatura do Contrato —
    ver PAGAMENTOS_CONTRATO.md. Só usado pelo PDF quando Contrato.evento é
    None (contrato emitido antes da conversão em Evento); com Evento já
    vinculado, esses campos ficam gravados só como histórico informativo."""
    valor_str = request.data.get('valor_entrada_pago')
    try:
        valor_entrada_pago = Decimal(str(valor_str)) if valor_str not in (None, '') else Decimal('0')
    except (InvalidOperation, ValueError):
        valor_entrada_pago = Decimal('0')

    data_pagamento_entrada = None
    data_str = (request.data.get('data_pagamento_entrada') or '').strip()
    if data_str:
        try:
            data_pagamento_entrada = datetime.date.fromisoformat(data_str)
        except ValueError:
            data_pagamento_entrada = None

    return dict(
        valor_entrada_pago=valor_entrada_pago,
        forma_pagamento_entrada=request.data.get('forma_pagamento_entrada') or '',
        data_pagamento_entrada=data_pagamento_entrada,
        observacao_entrada=(request.data.get('observacao_entrada') or '').strip(),
    )
from .serializers import (
    LocalEventoSerializer,
    EventoListSerializer,
    EventoDetailSerializer,
    EventoCreateSerializer,
    EventoAgendaSerializer,
    ItemEventoCreateSerializer,
    ItemEventoSerializer,
    PagamentoEventoSerializer,
    OrcamentoListSerializer,
    OrcamentoDetailSerializer,
    OrcamentoCreateSerializer,
    ItemOrcamentoCreateSerializer,
    ContratoSerializer,
    AditivoContratoSerializer,
    _valor_referencia_contrato,
    ConfiguracaoContratoSerializer,
    ConfiguracaoAlertaEventoSerializer,
    TelefoneAlertaEventoSerializer,
)


class CsrfExemptMixin:
    authentication_classes = []


# ─── Local de Evento ──────────────────────────────────────────────────────────

class LocalEventoViewSet(AuditoriaDestroyMixin, CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = LocalEvento.objects.all()
    serializer_class   = LocalEventoSerializer
    authentication_classes = [TokenAuthentication]
    campos_log_exclusao = ['nome']

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        qs    = super().get_queryset()
        ativo = self.request.query_params.get('ativo')
        if ativo == 'true':
            qs = qs.filter(ativo=True)
        elif ativo == 'false':
            qs = qs.filter(ativo=False)
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(nome__icontains=search) | Q(bairro__icontains=search))
        return qs


# ─── Eventos ──────────────────────────────────────────────────────────────────

class EventoViewSet(
    AuditoriaStatusMixin, AuditoriaUpdateMixin, AuditoriaCreateMixin, AuditoriaDestroyMixin,
    CsrfExemptMixin, viewsets.ModelViewSet,
):
    queryset           = Evento.objects.prefetch_related(
        'itens', 'pagamentos', 'orcamento_origem__imagens_inspiracao',
        'imagens_inspiracao_diretas', 'contratos__aditivos', 'aditivos',
        'adiamentos', 'remarcacoes',
    ).select_related('cliente', 'local', 'orcamento_origem').all()
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ['data_evento', 'criado_em', 'valor_total']
    ordering           = ['data_evento', 'hora_evento']
    # Sobrescreve o [] do CsrfExemptMixin — só assim dá pra saber quem registrou/removeu
    # um pagamento (ver get_permissions). Demais actions continuam AllowAny, sem mudança
    # de comportamento — a autenticação só passa a ser exigida nas actions de pagamento,
    # exclusão, criação/edição e mudança de status (ver get_permissions).
    authentication_classes = [TokenAuthentication]
    campos_log_exclusao = ['numero', 'cliente_nome', 'valor_total']
    campos_log_criacao = ['numero', 'cliente_nome', 'valor_total']
    campos_log_atualizacao = [
        'cliente', 'cliente_nome', 'cliente_telefone', 'tipo_evento', 'data_evento', 'hora_evento',
        'tipo_entrega', 'local', 'endereco_avulso', 'bairro_entrega', 'taxa_entrega',
        'desconto', 'observacoes', 'observacoes_cozinha',
    ]

    def get_permissions(self):
        if self.action in (
            'adicionar_pagamento', 'remover_pagamento', 'destroy', 'remover_item',
            'create', 'update', 'partial_update',
            'confirmar', 'iniciar_producao', 'marcar_pronto', 'entregar', 'cancelar',
            'adicionar_item', 'historico', 'gerar_contrato', 'gerar_aditivo', 'remover_imagem',
            'remarcar', 'adiar', 'retomar', 'prorrogar_adiamento', 'contato_adiamento',
            'encerrar_adiamento',
        ):
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.action == 'list':
            return EventoListSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return EventoCreateSerializer
        return EventoDetailSerializer

    def get_queryset(self):
        qs     = super().get_queryset()
        params = self.request.query_params

        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(numero__icontains=search) |
                Q(cliente_nome__icontains=search) |
                Q(cliente__nome__icontains=search) |
                Q(cliente_telefone__icontains=search) |
                Q(cliente__telefone_principal__icontains=search)
            )

        status_param = params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        tipo_evento = params.get('tipo_evento')
        if tipo_evento:
            qs = qs.filter(tipo_evento=tipo_evento)

        # Filtro por mês: ?mes=2025-06
        mes = params.get('mes')
        if mes:
            try:
                ano, m = mes.split('-')
                qs = qs.filter(data_evento__year=int(ano), data_evento__month=int(m))
            except (ValueError, AttributeError):
                pass

        # Filtro por data exata: ?data=2025-06-15
        data = params.get('data')
        if data:
            qs = qs.filter(data_evento=data)

        # Filtro: apenas futuros
        if params.get('futuros') == 'true':
            qs = qs.filter(data_evento__gte=timezone.localtime(timezone.now()).date())

        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        alvo = page if page is not None else queryset
        contexto = self.get_serializer_context()
        contexto['ultima_modificacao'] = ultima_modificacao_por_id('Evento', [obj.id for obj in alvo])
        serializer = self.get_serializer(alvo, many=True, context=contexto)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    # ── Ações de status ───────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='confirmar')
    def confirmar(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_confirmar:
            return Response({'detail': 'Evento não pode ser confirmado neste status.'},
                            status=status.HTTP_400_BAD_REQUEST)
        de = evento.status
        evento.status = 'confirmado'
        evento.save(update_fields=['status', 'atualizado_em'])
        self.log_mudanca_status(evento, de=de, para=evento.status)
        _notificar_evento(evento, f'✅ Sua encomenda #{evento.numero} está confirmada para {evento.data_evento.strftime("%d/%m/%Y")}! Qualquer dúvida, é só chamar. 🍬')
        return Response(EventoDetailSerializer(evento).data)

    @action(detail=True, methods=['post'], url_path='iniciar-producao')
    def iniciar_producao(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_iniciar_producao:
            return Response({'detail': 'Evento não pode iniciar produção neste status.'},
                            status=status.HTTP_400_BAD_REQUEST)
        de = evento.status
        evento.status = 'em_producao'
        evento.save(update_fields=['status', 'atualizado_em'])
        self.log_mudanca_status(evento, de=de, para=evento.status)
        _notificar_evento(evento, f'👨‍🍳 Sua encomenda #{evento.numero} entrou em produção! Estamos caprichando em cada detalhe.')
        return Response(EventoDetailSerializer(evento).data)

    @action(detail=True, methods=['post'], url_path='marcar-pronto')
    def marcar_pronto(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_marcar_pronto:
            return Response({'detail': 'Evento não pode ser marcado como pronto neste status.'},
                            status=status.HTTP_400_BAD_REQUEST)
        de = evento.status
        evento.status = 'pronto'
        evento.save(update_fields=['status', 'atualizado_em'])
        self.log_mudanca_status(evento, de=de, para=evento.status)
        _notificar_evento(evento, f'🎉 Sua encomenda #{evento.numero} está pronta! Entraremos em contato para combinar a entrega.')
        return Response(EventoDetailSerializer(evento).data)

    @action(detail=True, methods=['post'], url_path='entregar')
    def entregar(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_entregar:
            return Response({'detail': 'Evento não pode ser marcado como entregue neste status.'},
                            status=status.HTTP_400_BAD_REQUEST)
        de = evento.status
        evento.status = 'entregue'
        evento.save(update_fields=['status', 'atualizado_em'])
        self.log_mudanca_status(evento, de=de, para=evento.status)
        _notificar_evento(evento, f'💚 Encomenda #{evento.numero} entregue! Obrigado pela confiança na Arretado Doces. Até a próxima! 🍬')
        return Response(EventoDetailSerializer(evento).data)

    @action(detail=True, methods=['post'], url_path='cancelar')
    def cancelar(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_cancelar:
            return Response({'detail': 'Evento já foi entregue ou cancelado.'},
                            status=status.HTTP_400_BAD_REQUEST)
        de = evento.status
        evento.status = 'cancelado'
        evento.save(update_fields=['status', 'atualizado_em'])
        self.log_mudanca_status(evento, de=de, para=evento.status)
        _notificar_evento(evento, f'❌ Sua encomenda #{evento.numero} foi cancelada. Entre em contato se precisar de ajuda.')
        return Response(EventoDetailSerializer(evento).data)

    # ── Remarcação e Adiamento (ver ADIAMENTO.md) ─────────────────────────

    def _resposta_detalhe(self, evento, **extra):
        evento = self.get_queryset().get(pk=evento.pk)
        return Response({**EventoDetailSerializer(evento).data, **extra})

    @action(detail=True, methods=['post'], url_path='remarcar')
    def remarcar(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_remarcar:
            return _erro('status_invalido', 'Evento não pode ser remarcado neste status.')
        data_nova = _parse_data(request.data.get('data_evento'))
        hora_nova = _parse_hora(request.data['hora_evento']) if 'hora_evento' in request.data else evento.hora_evento
        motivo = (request.data.get('motivo') or '').strip()
        solicitado_por = request.data.get('solicitado_por')
        if not data_nova:
            return _erro('data_invalida', 'Informe a nova data do evento.')
        if hora_nova is False:
            return _erro('hora_invalida', 'Hora inválida.')
        if not motivo:
            return _erro('motivo_obrigatorio', 'Informe o motivo da remarcação.')
        if solicitado_por not in ('cliente', 'empresa'):
            return _erro('solicitado_por_invalido', 'Informe quem solicitou (cliente ou empresa).')
        if data_nova < timezone.localdate():
            return _erro('data_no_passado', 'A nova data não pode estar no passado.')
        if data_nova == evento.data_evento and hora_nova == evento.hora_evento:
            return _erro('sem_alteracao', 'A nova data e hora são iguais às atuais.')
        em_producao = evento.status in ('em_producao', 'pronto')
        if em_producao and request.data.get('confirmar_producao') not in (True, 'true', 'True', '1', 1):
            return _erro(
                'producao_iniciada',
                'A produção deste evento já começou — confirme a remarcação (itens perecíveis).',
            )
        voltar = em_producao and request.data.get('voltar_para_confirmado') in (True, 'true', 'True', '1', 1)

        with transaction.atomic():
            de = evento.status
            RemarcacaoEvento.objects.create(
                evento=evento, origem='remarcacao',
                data_anterior=evento.data_evento, hora_anterior=evento.hora_evento,
                data_nova=data_nova, hora_nova=hora_nova,
                status_anterior=de, status_novo='confirmado' if voltar else de,
                motivo=motivo[:300], solicitado_por=solicitado_por,
                criado_por=request.user, criado_por_nome=_nome_ator(request.user),
            )
            data_anterior = evento.data_evento
            evento.data_evento = data_nova
            evento.hora_evento = hora_nova
            campos = ['data_evento', 'hora_evento', 'atualizado_em']
            if voltar:
                evento.status = 'confirmado'
                campos.append('status')
            evento.save(update_fields=campos)
            registrar(
                request.user, LogAuditoria.ACAO_EVENTO_REMARCADO,
                detalhes={
                    'evento_id': evento.id, 'evento_numero': evento.numero,
                    'data_anterior': str(data_anterior), 'data_nova': str(data_nova),
                    'motivo': motivo, 'solicitado_por': solicitado_por,
                },
                request=request,
            )
            if voltar:
                self.log_mudanca_status(evento, de=de, para='confirmado')

        _notificar_evento(evento, _msg_remarcado(evento))
        evento = self.get_queryset().get(pk=evento.pk)
        aditivo_sugerido = bool(evento.contratos.all()) and evento.status != 'orcamento'
        return self._resposta_detalhe(evento, aditivo_sugerido=aditivo_sugerido)

    @action(detail=True, methods=['post'], url_path='adiar')
    def adiar(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_adiar:
            return _erro('status_invalido', 'Evento não pode ser adiado neste status.')
        if evento.adiamentos.filter(encerrado_em__isnull=True).exists():
            return _erro('adiamento_vigente', 'Este evento já tem um adiamento em andamento.')
        motivo = (request.data.get('motivo') or '').strip()
        solicitado_por = request.data.get('solicitado_por')
        if not motivo:
            return _erro('motivo_obrigatorio', 'Informe o motivo do adiamento.')
        if solicitado_por not in ('cliente', 'empresa'):
            return _erro('solicitado_por_invalido', 'Informe quem solicitou (cliente ou empresa).')

        cfg = ConfiguracaoContrato.get()
        hoje = timezone.localdate()
        contato = request.data.get('retomar_contato_em')
        contato = _parse_data(contato) if contato else hoje + datetime.timedelta(days=cfg.dias_followup_adiamento)
        if not contato or contato < hoje:
            return _erro('contato_invalido', 'A data de follow-up não pode estar no passado.')

        antecedencia = (evento.data_evento - hoje).days
        producao = evento.status in ('em_producao', 'pronto')
        contrato = next(iter(evento.contratos.all()), None)
        multa_pct = None
        if contrato and contrato.possui_clausula_adiamento:
            multa_pct = regras_adiamento.faixa_multa_pct(antecedencia, producao, cfg)

        with transaction.atomic():
            de = evento.status
            adiamento = AdiamentoEvento.objects.create(
                evento=evento, adiado_em=hoje, data_original=evento.data_evento, status_antes=de,
                motivo=motivo[:300], solicitado_por=solicitado_por,
                limite=evento.data_evento + datetime.timedelta(days=cfg.prazo_maximo_adiamento_dias),
                retomar_contato_em=contato, antecedencia_dias=antecedencia,
                producao_iniciada=producao, multa_pct=multa_pct,
                criado_por=request.user, criado_por_nome=_nome_ator(request.user),
            )
            evento.status = 'adiado'
            evento.save(update_fields=['status', 'atualizado_em'])
            registrar(
                request.user, LogAuditoria.ACAO_EVENTO_ADIADO,
                detalhes={
                    'evento_id': evento.id, 'evento_numero': evento.numero,
                    'adiamento_id': adiamento.id, 'data_original': str(adiamento.data_original),
                    'limite': str(adiamento.limite), 'motivo': motivo, 'solicitado_por': solicitado_por,
                    'multa_pct': str(multa_pct) if multa_pct is not None else None,
                },
                request=request,
            )
            self.log_mudanca_status(evento, de=de, para='adiado')

        _notificar_evento(evento, MSG_EVENTO_ADIADO.format(numero=evento.numero))
        return self._resposta_detalhe(evento)

    @action(detail=True, methods=['post'], url_path='retomar')
    def retomar(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_retomar:
            return _erro('status_invalido', 'Só é possível retomar um evento adiado.')
        adiamento = evento.adiamento_vigente
        if not adiamento:
            return _erro('sem_adiamento', 'Evento adiado sem adiamento vigente.')
        data_nova = _parse_data(request.data.get('data_evento'))
        hora_nova = _parse_hora(request.data['hora_evento']) if 'hora_evento' in request.data else evento.hora_evento
        if not data_nova:
            return _erro('data_invalida', 'Informe a nova data do evento.')
        if hora_nova is False:
            return _erro('hora_invalida', 'Hora inválida.')
        if data_nova < timezone.localdate():
            return _erro('data_no_passado', 'A nova data não pode estar no passado.')
        if data_nova > adiamento.limite:
            return _erro(
                'fora_do_prazo',
                f'A nova data passa do limite do adiamento ({adiamento.limite.strftime("%d/%m/%Y")}) '
                '— prorrogue o prazo antes de retomar.',
            )
        motivo = (request.data.get('motivo') or '').strip() or 'Retomada de evento adiado'

        with transaction.atomic():
            RemarcacaoEvento.objects.create(
                evento=evento, origem='retomada', adiamento=adiamento,
                data_anterior=evento.data_evento, hora_anterior=evento.hora_evento,
                data_nova=data_nova, hora_nova=hora_nova,
                status_anterior='adiado', status_novo='confirmado',
                motivo=motivo[:300], solicitado_por='cliente',
                criado_por=request.user, criado_por_nome=_nome_ator(request.user),
            )
            data_anterior = evento.data_evento
            evento.data_evento = data_nova
            evento.hora_evento = hora_nova
            evento.status = 'confirmado'
            evento.save(update_fields=['data_evento', 'hora_evento', 'status', 'atualizado_em'])
            adiamento.encerrado_em = timezone.now()
            adiamento.desfecho = 'retomado'
            adiamento.encerrado_por = request.user
            adiamento.encerrado_por_nome = _nome_ator(request.user)
            adiamento.save(update_fields=['encerrado_em', 'desfecho', 'encerrado_por', 'encerrado_por_nome'])
            registrar(
                request.user, LogAuditoria.ACAO_EVENTO_RETOMADO,
                detalhes={
                    'evento_id': evento.id, 'evento_numero': evento.numero,
                    'adiamento_id': adiamento.id,
                    'data_anterior': str(data_anterior), 'data_nova': str(data_nova),
                },
                request=request,
            )
            self.log_mudanca_status(evento, de='adiado', para='confirmado')

        _notificar_evento(evento, _msg_remarcado(evento))
        evento = self.get_queryset().get(pk=evento.pk)
        return self._resposta_detalhe(evento, aditivo_sugerido=bool(evento.contratos.all()))

    @action(detail=True, methods=['post'], url_path='adiamento/prorrogar')
    def prorrogar_adiamento(self, request, pk=None):
        evento = self.get_object()
        adiamento = evento.adiamento_vigente
        if not adiamento:
            return _erro('sem_adiamento', 'Este evento não tem adiamento em andamento.')
        cfg = ConfiguracaoContrato.get()
        if adiamento.prorrogacoes >= cfg.prorrogacoes_adiamento_max:
            return _erro('limite_prorrogacoes', 'O número máximo de prorrogações já foi atingido.')
        motivo = (request.data.get('motivo') or '').strip()
        if not motivo:
            return _erro('motivo_obrigatorio', 'Informe o motivo da prorrogação.')
        limite_anterior = adiamento.limite
        adiamento.limite = limite_anterior + datetime.timedelta(days=cfg.prazo_maximo_adiamento_dias)
        adiamento.prorrogacoes += 1
        adiamento.save(update_fields=['limite', 'prorrogacoes'])
        registrar(
            request.user, LogAuditoria.ACAO_ADIAMENTO_PRORROGADO,
            detalhes={
                'evento_id': evento.id, 'evento_numero': evento.numero, 'adiamento_id': adiamento.id,
                'limite_anterior': str(limite_anterior), 'limite': str(adiamento.limite), 'motivo': motivo,
            },
            request=request,
        )
        return self._resposta_detalhe(evento)

    @action(detail=True, methods=['post'], url_path='adiamento/contato')
    def contato_adiamento(self, request, pk=None):
        evento = self.get_object()
        adiamento = evento.adiamento_vigente
        if not adiamento:
            return _erro('sem_adiamento', 'Este evento não tem adiamento em andamento.')
        data = _parse_data(request.data.get('retomar_contato_em'))
        if not data or data < timezone.localdate():
            return _erro('contato_invalido', 'Informe uma data de follow-up de hoje em diante.')
        anterior = adiamento.retomar_contato_em
        adiamento.retomar_contato_em = data
        adiamento.save(update_fields=['retomar_contato_em'])
        registrar(
            request.user, LogAuditoria.ACAO_REGISTRO_ATUALIZADO,
            detalhes={
                'model': 'AdiamentoEvento', 'id': adiamento.id, 'evento_id': evento.id,
                'evento_numero': evento.numero,
                'campos': {'retomar_contato_em': [str(anterior), str(data)]},
                'observacao': (request.data.get('observacao') or '').strip(),
            },
            request=request,
        )
        return self._resposta_detalhe(evento)

    @action(detail=True, methods=['get'], url_path='adiamento/simular-encerramento')
    def simular_encerramento(self, request, pk=None):
        evento = self.get_object()
        adiamento = evento.adiamento_vigente
        if not adiamento:
            return _erro('sem_adiamento', 'Este evento não tem adiamento em andamento.')
        desfecho = request.query_params.get('desfecho', 'rescisao')
        if desfecho not in ('rescisao', 'forca_maior', 'acordo_manual'):
            return _erro('desfecho_invalido', 'Desfecho inválido.')
        try:
            retido = Decimal(request.query_params.get('retido') or '0')
        except InvalidOperation:
            return _erro('valor_invalido', 'Valor retido inválido.')
        return Response(self._simular(evento, adiamento, desfecho, retido))

    def _simular(self, evento, adiamento, desfecho, retido):
        cfg = ConfiguracaoContrato.get()
        contrato = next(iter(evento.contratos.all()), None)
        valor_pago = evento.sinal_pago
        valor_contrato = _valor_referencia_contrato(contrato) if contrato else evento.valor_total
        sem_clausula = desfecho == 'rescisao' and adiamento.multa_pct is None
        if desfecho == 'acordo_manual' or sem_clausula:
            acerto = {'multa': None, 'retido': retido, 'devolucao': None}
        else:
            acerto = regras_adiamento.calcular_acerto(
                valor_pago, valor_contrato, adiamento.multa_pct, retido, desfecho,
            )
        vencimento = regras_adiamento.somar_dias_uteis(timezone.localdate(), cfg.prazo_devolucao_dias)
        return {
            'desfecho': desfecho,
            'valor_pago': valor_pago,
            'valor_contrato': valor_contrato,
            'multa_pct': adiamento.multa_pct,
            'sem_clausula': sem_clausula,
            'multa_sugerida': acerto['multa'],
            'valor_retido_producao': acerto['retido'],
            'devolucao_sugerida': acerto['devolucao'],
            'vencimento_devolucao': vencimento,
        }

    @action(detail=True, methods=['post'], url_path='adiamento/encerrar')
    def encerrar_adiamento(self, request, pk=None):
        evento = self.get_object()
        adiamento = evento.adiamento_vigente
        if not adiamento:
            return _erro('sem_adiamento', 'Este evento não tem adiamento em andamento.')
        desfecho = request.data.get('desfecho')
        if desfecho not in ('rescisao', 'forca_maior', 'acordo_manual'):
            return _erro('desfecho_invalido', 'Desfecho inválido.')
        observacao = (request.data.get('observacao') or '').strip()
        if not observacao:
            return _erro('observacao_obrigatoria', 'Informe a observação do encerramento.')
        if desfecho == 'rescisao' and adiamento.multa_pct is None:
            return _erro(
                'sem_clausula',
                'Este contrato não tem a cláusula de adiamento — encerre como acordo manual.',
            )

        def _dec(campo):
            bruto = request.data.get(campo)
            if bruto in (None, ''):
                return None
            valor = Decimal(str(bruto))  # InvalidOperation tratada abaixo
            if valor < 0:
                raise InvalidOperation
            return valor

        try:
            multa_in, retido_in, devolucao_in = _dec('valor_multa'), _dec('valor_retido_producao'), _dec('valor_devolucao')
        except InvalidOperation:
            return _erro('valor_invalido', 'Valores devem ser números não negativos.')

        cfg = ConfiguracaoContrato.get()
        contrato = next(iter(evento.contratos.all()), None)
        valor_pago = evento.sinal_pago
        valor_contrato = _valor_referencia_contrato(contrato) if contrato else evento.valor_total
        retido = retido_in or Decimal('0')

        if desfecho == 'acordo_manual':
            if multa_in is None or devolucao_in is None:
                return _erro('valores_obrigatorios', 'No acordo manual, informe multa e devolução.')
            sugerido = None
            final = regras_adiamento.calcular_acerto(
                valor_pago, valor_contrato, None, retido, desfecho,
                valor_multa=multa_in, valor_devolucao=devolucao_in,
            )
        else:
            sugerido = regras_adiamento.calcular_acerto(
                valor_pago, valor_contrato, adiamento.multa_pct, retido, desfecho,
            )
            final = {
                'multa': multa_in if multa_in is not None else sugerido['multa'],
                'retido': retido,
                'devolucao': devolucao_in if devolucao_in is not None else sugerido['devolucao'],
            }
        if final['multa'] + final['retido'] + final['devolucao'] != valor_pago:
            return _erro(
                'soma_invalida',
                f'Multa + retido + devolução ({final["multa"] + final["retido"] + final["devolucao"]}) '
                f'precisa fechar com o total pago ({valor_pago}).',
            )

        hoje = timezone.localdate()
        with transaction.atomic():
            conta = None
            if final['devolucao'] > 0:
                from financeiro.models import ContaPagar
                from empresas.models import Empresa
                conta = ContaPagar.objects.create(
                    numero=ContaPagar.proximo_numero(), empresa=Empresa.get_padrao(), categoria=None,
                    origem='devolucao_evento',
                    descricao=f'Devolução — {evento.numero} ({evento.nome_cliente_display})'[:160],
                    valor=final['devolucao'], data_emissao=hoje,
                    data_vencimento=regras_adiamento.somar_dias_uteis(hoje, cfg.prazo_devolucao_dias),
                )
            adiamento.encerrado_em = timezone.now()
            adiamento.desfecho = desfecho
            adiamento.valor_pago_no_encerramento = valor_pago
            adiamento.valor_multa = final['multa']
            adiamento.valor_multa_sugerido = sugerido['multa'] if sugerido else None
            adiamento.valor_retido_producao = final['retido']
            adiamento.valor_devolucao = final['devolucao']
            adiamento.conta_pagar = conta
            adiamento.observacao_encerramento = observacao
            adiamento.encerrado_por = request.user
            adiamento.encerrado_por_nome = _nome_ator(request.user)
            adiamento.save()
            evento.status = 'cancelado'
            evento.save(update_fields=['status', 'atualizado_em'])
            registrar(
                request.user, LogAuditoria.ACAO_ADIAMENTO_ENCERRADO,
                detalhes={
                    'evento_id': evento.id, 'evento_numero': evento.numero, 'adiamento_id': adiamento.id,
                    'desfecho': desfecho, 'valor_pago': str(valor_pago),
                    'sugerido': {k: str(v) for k, v in sugerido.items()} if sugerido else None,
                    'final': {k: str(v) for k, v in final.items()},
                    'conta_pagar': conta.numero if conta else None, 'observacao': observacao,
                },
                request=request,
            )
            self.log_mudanca_status(evento, de='adiado', para='cancelado')

        _notificar_evento(evento, MSG_EVENTO_CANCELADO.format(numero=evento.numero))
        return self._resposta_detalhe(evento)

    # ── Itens ─────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='itens')
    def adicionar_item(self, request, pk=None):
        evento = self.get_object()
        if evento.status not in ('orcamento', 'confirmado'):
            return Response(
                {'detail': 'Só é possível adicionar itens em eventos com status Orçamento ou Confirmado.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = ItemEventoCreateSerializer(data=request.data)
        if serializer.is_valid():
            data  = serializer.validated_data
            qty   = data.get('quantidade', 1)
            price = data['preco_unit']
            item = ItemEvento.objects.create(
                evento=evento,
                preco_total=price * qty,
                **data,
            )
            evento.refresh_from_db()  # evita cache stale do prefetch_related('itens') — ver CLAUDE.md
            evento.recalcular_totais()
            registrar(
                ator_ou_none(request), LogAuditoria.ACAO_ITEM_ADICIONADO,
                detalhes={
                    'model': 'ItemEvento', 'id': item.id, 'nome': item.nome,
                    'preco_total': str(item.preco_total),
                    'evento_id': evento.id, 'evento_numero': evento.numero,
                },
                request=request,
            )
            return Response(EventoDetailSerializer(evento).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path=r'itens/(?P<item_id>[^/.]+)/remover')
    def remover_item(self, request, pk=None, item_id=None):
        evento = self.get_object()
        if evento.status not in ('orcamento', 'confirmado'):
            return Response(
                {'detail': 'Não é possível remover itens neste status.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            item = evento.itens.get(pk=item_id)
        except ItemEvento.DoesNotExist:
            return Response({'detail': 'Item não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        registrar(
            request.user, LogAuditoria.ACAO_REGISTRO_EXCLUIDO,
            detalhes={
                'model': 'ItemEvento', 'id': item.id, 'descricao': str(item),
                'evento_id': evento.id, 'evento_numero': evento.numero,
            },
            request=request,
        )
        item.delete()
        evento.refresh_from_db()  # evita cache stale do prefetch_related('itens') — ver CLAUDE.md
        evento.recalcular_totais()
        return Response(EventoDetailSerializer(evento).data)

    # ── Imagens de Inspiração ────────────────────────────────────────────
    # Podem ser adicionadas/removidas a qualquer momento, em qualquer status
    # (sem a restrição de status que vale para itens) — mesma filosofia de
    # adicionar_imagens/remover_imagem em OrcamentoViewSet. Quando o evento
    # veio de um orçamento, a imagem é anexada ao ORÇAMENTO de origem (mesma
    # galeria compartilhada, sem duplicar — ver CLAUDE.md); sem orçamento de
    # origem, a imagem é anexada direto ao Evento.

    @action(detail=True, methods=['post'], url_path='imagens')
    def adicionar_imagens(self, request, pk=None):
        evento = self.get_object()
        arquivos = request.FILES.getlist('imagens')
        if not arquivos:
            return Response(
                {'detail': 'Nenhuma imagem enviada.'}, status=status.HTTP_400_BAD_REQUEST
            )
        origem = getattr(evento, 'orcamento_origem', None)
        for arquivo in arquivos:
            if origem:
                ImagemInspiracao.objects.create(orcamento=origem, imagem=arquivo)
            else:
                ImagemInspiracao.objects.create(evento=evento, imagem=arquivo)
        evento.refresh_from_db()  # evita cache stale do prefetch — ver CLAUDE.md
        return Response(EventoDetailSerializer(evento).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path=r'imagens/(?P<imagem_id>[^/.]+)/remover')
    def remover_imagem(self, request, pk=None, imagem_id=None):
        evento = self.get_object()
        origem = getattr(evento, 'orcamento_origem', None)
        galeria = origem.imagens_inspiracao if origem else evento.imagens_inspiracao_diretas
        try:
            img = galeria.get(pk=imagem_id)
        except ImagemInspiracao.DoesNotExist:
            return Response({'detail': 'Imagem não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        registrar(
            request.user, LogAuditoria.ACAO_REGISTRO_EXCLUIDO,
            detalhes={
                'model': 'ImagemInspiracao', 'id': img.id,
                'evento_id': evento.id, 'evento_numero': evento.numero,
            },
            request=request,
        )
        img.imagem.delete(save=False)
        img.delete()
        evento.refresh_from_db()  # evita cache stale do prefetch — ver CLAUDE.md
        return Response(EventoDetailSerializer(evento).data)

    # ── Contrato ──────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='gerar-contrato')
    def gerar_contrato(self, request, pk=None):
        """
        Gera um novo Contrato usando os dados ATUAIS do Evento (não o
        Orçamento congelado) — útil quando o evento foi alterado depois da
        conversão (itens/valor divergentes do orçamento original). Exige que
        o evento tenha vindo de um orçamento (Contrato.orcamento é FK
        obrigatória) — ver CLAUDE.md.
        """
        evento = self.get_object()

        if not getattr(evento, 'orcamento_origem', None):
            return Response(
                {
                    'detail': 'sem_orcamento_origem',
                    'mensagem': (
                        'Este evento não foi criado a partir de um orçamento — não é possível '
                        'emitir contrato.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if evento.status == 'cancelado':
            return Response(
                {
                    'detail': 'evento_cancelado',
                    'mensagem': 'Não é possível emitir contrato de um evento cancelado.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        cliente = evento.cliente
        if not cliente:
            return Response(
                {
                    'detail': 'sem_cliente',
                    'mensagem': (
                        'Este evento não está vinculado a um cliente do CRM. '
                        'Vincule um cliente antes de emitir o contrato.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not evento.data_evento:
            return Response(
                {
                    'detail': 'sem_data_evento',
                    'mensagem': 'Este evento não tem a data definida. Preencha-a antes de emitir o contrato.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Campos do CONTRATANTE — opcionais no cadastro, exigidos aqui (ver Contrato.md)
        campos_atualizaveis = ['cpf', 'rg', 'rg_orgao_emissor', 'nacionalidade', 'profissao', 'estado_civil']
        campos_obrigatorios = ['cpf', 'rg', 'nacionalidade', 'profissao', 'estado_civil']

        dados_cliente = {c: request.data[c] for c in campos_atualizaveis if request.data.get(c)}
        if dados_cliente:
            from clientes.serializers import ClienteDetailSerializer
            serializer = ClienteDetailSerializer(cliente, data=dados_cliente, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

        faltando = [c for c in campos_obrigatorios if not getattr(cliente, c)]
        if faltando:
            return Response(
                {
                    'detail': 'dados_incompletos',
                    'campos_faltando': faltando,
                    'mensagem': (
                        'Complete os dados do CONTRATANTE (CPF, RG, nacionalidade, profissão e estado '
                        'civil) para emitir o contrato.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        endereco_avulso    = (request.data.get('endereco_avulso') or '').strip()
        endereco_principal = cliente.enderecos.filter(principal=True).first()
        if endereco_principal:
            contratante_endereco = endereco_principal.endereco_completo
        elif endereco_avulso:
            contratante_endereco = endereco_avulso
        else:
            return Response(
                {
                    'detail': 'sem_endereco',
                    'mensagem': (
                        'O cliente não tem endereço principal cadastrado. Informe um endereço avulso '
                        'para o contrato.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        local_evento = evento.local.endereco_completo if evento.local else evento.endereco_avulso

        cfg              = ConfiguracaoContrato.get()
        percentual_sinal = cfg.percentual_sinal
        valor_sinal      = (evento.valor_total * percentual_sinal / Decimal('100')).quantize(Decimal('0.01'))
        data_quitacao    = evento.data_evento - datetime.timedelta(days=cfg.prazo_quitacao_dias)

        contrato = Contrato.objects.create(
            numero=Contrato.proximo_numero(),
            orcamento=evento.orcamento_origem,
            evento=evento,
            cliente=cliente,
            contratante_nome=cliente.nome,
            contratante_nacionalidade=cliente.nacionalidade,
            contratante_profissao=cliente.profissao,
            contratante_rg=cliente.rg,
            contratante_rg_orgao_emissor=cliente.rg_orgao_emissor,
            contratante_cpf=cliente.cpf,
            contratante_estado_civil=cliente.estado_civil,
            contratante_endereco=contratante_endereco,
            data_evento=evento.data_evento,
            hora_evento=evento.hora_evento,
            local_evento=local_evento,
            valor_total=evento.valor_total,
            percentual_sinal=percentual_sinal,
            valor_sinal=valor_sinal,
            data_quitacao=data_quitacao,
            possui_clausula_adiamento=True,
            **_campos_entrada_contrato(request),
        )

        registrar(
            request.user, LogAuditoria.ACAO_CONTRATO_EMITIDO,
            detalhes={
                'contrato_numero': contrato.numero,
                'orcamento_id': evento.orcamento_origem.id, 'orcamento_numero': evento.orcamento_origem.numero,
                'evento_id': evento.id, 'evento_numero': evento.numero,
                'cliente': cliente.nome, 'valor_total': str(contrato.valor_total),
            },
            request=request,
        )

        return Response(ContratoSerializer(contrato).data, status=status.HTTP_201_CREATED)

    # ── Aditivo de Contrato (alteração de valores após contrato emitido) ────

    @action(detail=True, methods=['post'], url_path='gerar-aditivo')
    def gerar_aditivo(self, request, pk=None):
        """
        Emite um Termo Aditivo documentando alteração de valor/itens do
        Evento depois que o Contrato já foi emitido (cliente pediu mudança
        no pedido antes do evento acontecer) — ver Contrato.md. Snapshot
        imutável (itens + totais), mesma filosofia do Contrato: nunca
        recalculado depois, mesmo que o Evento mude de novo.
        """
        evento = self.get_object()

        contrato = next(iter(evento.contratos.all()), None)
        if not contrato:
            return Response(
                {
                    'detail': 'sem_contrato',
                    'mensagem': 'Este evento ainda não tem contrato emitido — não há o que aditivar.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if evento.status in ('cancelado', 'entregue', 'adiado'):
            return Response(
                {
                    'detail': f'evento_{evento.status}',
                    'mensagem': 'Não é possível emitir aditivo de um evento cancelado, entregue ou adiado.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        valor_referencia = _valor_referencia_contrato(contrato)
        data_ref, hora_ref = regras_adiamento.data_referencia_contrato(evento)
        mudou_valor = evento.valor_total != valor_referencia
        mudou_data = evento.data_evento != data_ref or evento.hora_evento != hora_ref
        if not mudou_valor and not mudou_data:
            return Response(
                {
                    'detail': 'sem_alteracao',
                    'mensagem': (
                        'Nem o valor nem a data do evento mudaram desde o contrato/último aditivo '
                        '— nada para documentar.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        campos_data = {}
        if mudou_data:
            cfg = ConfiguracaoContrato.get()
            campos_data = dict(
                data_evento_anterior=data_ref, hora_evento_anterior=hora_ref,
                data_evento_nova=evento.data_evento, hora_evento_nova=evento.hora_evento,
                data_quitacao_nova=evento.data_evento - datetime.timedelta(days=cfg.prazo_quitacao_dias),
            )

        itens_snapshot = [
            {
                'nome': item.nome,
                'quantidade': item.quantidade,
                'preco_unit': str(item.preco_unit),
                'preco_total': str(item.preco_total),
                'natureza': item.natureza,
                'observacao': item.observacao,
            }
            for item in evento.itens.all()
        ]

        aditivo = AditivoContrato.objects.create(
            contrato=contrato,
            evento=evento,
            cliente=evento.cliente,
            numero=AditivoContrato.proximo_numero(),
            valor_total_anterior=valor_referencia,
            subtotal_novo=evento.subtotal,
            desconto_novo=evento.desconto,
            taxa_entrega_novo=evento.taxa_entrega,
            valor_total_novo=evento.valor_total,
            itens_snapshot=itens_snapshot,
            **campos_data,
        )

        registrar(
            request.user, LogAuditoria.ACAO_ADITIVO_EMITIDO,
            detalhes={
                'aditivo_numero': aditivo.numero, 'contrato_numero': contrato.numero,
                'evento_id': evento.id, 'evento_numero': evento.numero,
                'valor_total_anterior': str(aditivo.valor_total_anterior),
                'valor_total_novo': str(aditivo.valor_total_novo),
            },
            request=request,
        )

        return Response(AditivoContratoSerializer(aditivo).data, status=status.HTTP_201_CREATED)

    # ── Pagamentos ────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='pagamentos')
    def adicionar_pagamento(self, request, pk=None):
        evento = self.get_object()
        serializer = PagamentoEventoSerializer(data=request.data)
        if serializer.is_valid():
            pagamento = PagamentoEvento.objects.create(evento=evento, **serializer.validated_data)
            evento.refresh_from_db()  # evita cache stale do prefetch — ver CLAUDE.md
            evento.recalcular_sinal_pago()
            registrar(
                request.user, LogAuditoria.ACAO_PAGAMENTO_REGISTRADO,
                detalhes={
                    'evento_id': evento.id, 'evento_numero': evento.numero,
                    'pagamento_id': pagamento.id, 'valor': str(pagamento.valor),
                    'forma_pagamento': pagamento.forma_pagamento, 'origem': 'action_pagamentos',
                },
                request=request,
            )
            return Response(EventoDetailSerializer(evento).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path=r'pagamentos/(?P<pagamento_id>[^/.]+)/remover')
    def remover_pagamento(self, request, pk=None, pagamento_id=None):
        evento = self.get_object()
        try:
            pagamento = evento.pagamentos.get(pk=pagamento_id)
        except PagamentoEvento.DoesNotExist:
            return Response({'detail': 'Pagamento não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        registrar(
            request.user, LogAuditoria.ACAO_PAGAMENTO_REMOVIDO,
            detalhes={
                'evento_id': evento.id, 'evento_numero': evento.numero,
                'pagamento_id': pagamento.id, 'valor': str(pagamento.valor),
                'forma_pagamento': pagamento.forma_pagamento,
            },
            request=request,
        )
        pagamento.delete()
        evento.recalcular_sinal_pago()
        return Response(EventoDetailSerializer(evento).data)

    # ── Histórico ─────────────────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='historico')
    def historico(self, request, pk=None):
        """
        GET /api/v1/eventos/{id}/historico/
        Trilha de auditoria deste evento (criação, edição, mudança de
        status, itens, pagamentos) — não confundir com
        clientes/{id}/historico/, que é histórico de PEDIDOS do cliente
        entre canais, um conceito totalmente diferente.
        """
        evento = self.get_object()
        logs = LogAuditoria.objects.filter(
            Q(detalhes__model='Evento', detalhes__id=evento.id) |
            Q(detalhes__model='ItemEvento', detalhes__evento_id=evento.id) |
            Q(
                acao__in=[LogAuditoria.ACAO_PAGAMENTO_REGISTRADO, LogAuditoria.ACAO_PAGAMENTO_REMOVIDO],
                detalhes__evento_id=evento.id,
            ) |
            Q(
                acao__in=[LogAuditoria.ACAO_CONTRATO_EMITIDO, LogAuditoria.ACAO_CONTRATO_ENVIADO],
                detalhes__evento_id=evento.id,
            ) |
            Q(
                acao__in=[LogAuditoria.ACAO_ADITIVO_EMITIDO, LogAuditoria.ACAO_ADITIVO_ENVIADO],
                detalhes__evento_id=evento.id,
            )
        ).select_related('usuario').order_by('-criado_em')
        return Response(LogAuditoriaSerializer(logs, many=True).data)

    # ── Resumo de cozinha (PDF operacional, uso interno) ────────────────────

    @action(detail=True, methods=['get'], url_path='resumo-cozinha')
    def resumo_cozinha(self, request, pk=None):
        if Evento.objects.filter(pk=pk, status='adiado').exists():
            return _erro('evento_adiado', 'Evento adiado fora da produção — sem resumo de cozinha.')
        evento = (
            Evento.objects
            .prefetch_related(
                'itens__produto__categoria',
                'orcamento_origem__imagens_inspiracao', 'imagens_inspiracao_diretas',
            )
            .select_related('cliente', 'local', 'orcamento_origem')
            .get(pk=pk)
        )
        # ?imagens=1 — opção do usuário de incluir (ou não) as imagens de
        # inspiração numa folha separada do PDF (ver "Resumo de Cozinha" no CLAUDE.md)
        incluir_imagens = request.query_params.get('imagens') in ('1', 'true', 'True')
        imagens = list(evento.galeria_imagens_inspiracao()) if incluir_imagens else []
        from .pdf_resumo_cozinha import gerar_pdf_resumo_cozinha
        pdf_bytes = gerar_pdf_resumo_cozinha(evento, imagens=imagens)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="resumo-cozinha-{evento.numero}.pdf"'
        return response

    # ── View de agenda (calendário) ────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='agenda')
    def agenda(self, request):
        """
        Retorna eventos agrupados por dia para uma visão de calendário.
        Parâmetro: ?mes=2025-06 (obrigatório)
        """
        mes = request.query_params.get('mes')
        if not mes:
            hoje = timezone.localtime(timezone.now()).date()
            mes  = hoje.strftime('%Y-%m')

        try:
            ano, m = mes.split('-')
            ano, m = int(ano), int(m)
        except (ValueError, AttributeError):
            return Response({'detail': 'Parâmetro mes inválido. Use YYYY-MM.'},
                            status=status.HTTP_400_BAD_REQUEST)

        eventos = (
            Evento.objects
            .filter(data_evento__year=ano, data_evento__month=m)
            .exclude(status__in=['cancelado', 'adiado'])
            .select_related('cliente', 'local')
            .order_by('data_evento', 'hora_evento')
        )

        # Agrupar por dia
        agenda = {}
        for ev in eventos:
            dia = str(ev.data_evento)
            if dia not in agenda:
                agenda[dia] = []
            agenda[dia].append(EventoAgendaSerializer(ev).data)

        return Response({
            'mes':    mes,
            'agenda': agenda,
            'total':  eventos.count(),
        })

    # ── Estatísticas ──────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='estatisticas')
    def estatisticas(self, request):
        hoje  = timezone.localtime(timezone.now()).date()
        mes   = hoje.replace(day=1)

        # Total de eventos do mês
        eventos_mes = Evento.objects.filter(
            data_evento__year=hoje.year,
            data_evento__month=hoje.month,
        ).exclude(status__in=['cancelado', 'adiado'])

        # Próximos 7 dias
        prox7 = Evento.objects.filter(
            data_evento__range=(hoje, hoje + datetime.timedelta(days=7)),
            status__in=('confirmado', 'em_producao', 'pronto'),
        ).order_by('data_evento', 'hora_evento')

        # Faturamento do mês (entregues)
        fat_mes = Evento.objects.filter(
            data_evento__year=hoje.year,
            data_evento__month=hoje.month,
            status='entregue',
        ).aggregate(total=Sum('valor_total'))['total'] or 0

        # Por status
        por_status = dict(
            Evento.objects
            .filter(data_evento__gte=hoje)
            .exclude(status__in=['cancelado', 'adiado'])
            .values('status')
            .annotate(total=Count('id'))
            .values_list('status', 'total')
        )
        # Adiados não filtram por data_evento (a data é só a última prevista) — KPI "Adiados"
        por_status['adiado'] = Evento.objects.filter(status='adiado').count()

        return Response({
            'eventos_mes':        eventos_mes.count(),
            'faturamento_mes':    float(fat_mes),
            'proximos_7_dias':    EventoAgendaSerializer(prox7, many=True).data,
            'por_status':         por_status,
        })


# ─── Orçamentos ───────────────────────────────────────────────────────────────

class OrcamentoViewSet(
    AuditoriaStatusMixin, AuditoriaUpdateMixin, AuditoriaCreateMixin, AuditoriaDestroyMixin,
    CsrfExemptMixin, viewsets.ModelViewSet,
):
    queryset           = Orcamento.objects.prefetch_related('itens', 'imagens_inspiracao', 'contratos').select_related('cliente', 'evento').all()
    # authentication_classes real (ver abaixo) — algumas actions continuam AllowAny
    # (permission depende de get_permissions), só permitindo capturar o ator de forma
    # oportunista quando o token vier, para auditar o sinal inicial em converter_em_evento.
    authentication_classes = [TokenAuthentication]
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ['criado_em', 'valor_total', 'data_evento']
    ordering           = ['-criado_em']
    campos_log_exclusao = ['numero', 'cliente_nome', 'valor_total']
    campos_log_criacao = ['numero', 'cliente_nome', 'valor_total']
    campos_log_atualizacao = [
        'cliente', 'cliente_nome', 'cliente_telefone', 'tipo_evento', 'data_evento', 'validade',
        'tipo_entrega', 'local', 'endereco_avulso', 'bairro_entrega', 'taxa_entrega',
        'desconto', 'observacoes',
    ]

    def get_permissions(self):
        if self.action in (
            'gerar_contrato', 'destroy', 'remover_item', 'remover_imagem',
            'create', 'update', 'partial_update',
            'enviar', 'aprovar', 'recusar', 'restaurar',
            'adicionar_item', 'editar_item', 'historico',
        ):
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.action == 'list':
            return OrcamentoListSerializer
        if self.action in ('update', 'partial_update'):
            return OrcamentoCreateSerializer
        return OrcamentoDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = OrcamentoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            OrcamentoDetailSerializer(serializer.instance).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        orc = self.get_object()
        if orc.status not in ('rascunho', 'enviado'):
            return Response(
                {'detail': 'Só é possível editar orçamentos com status Rascunho ou Enviado.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        partial = kwargs.pop('partial', False)
        serializer = OrcamentoCreateSerializer(orc, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(OrcamentoDetailSerializer(serializer.instance).data)

    def get_queryset(self):
        qs     = super().get_queryset()
        params = self.request.query_params

        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(numero__icontains=search) |
                Q(cliente_nome__icontains=search) |
                Q(cliente__nome__icontains=search) |
                Q(cliente_telefone__icontains=search)
            )

        status_param = params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        tipo_evento = params.get('tipo_evento')
        if tipo_evento:
            qs = qs.filter(tipo_evento=tipo_evento)

        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        alvo = page if page is not None else queryset
        contexto = self.get_serializer_context()
        contexto['ultima_modificacao'] = ultima_modificacao_por_id('Orcamento', [obj.id for obj in alvo])
        serializer = self.get_serializer(alvo, many=True, context=contexto)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    # ── Ações de status ───────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='enviar')
    def enviar(self, request, pk=None):
        orc = self.get_object()
        if not orc.pode_enviar:
            return Response({'detail': 'Orçamento não pode ser marcado como enviado neste status.'},
                            status=status.HTTP_400_BAD_REQUEST)
        de = orc.status
        orc.status = 'enviado'
        orc.save(update_fields=['status', 'atualizado_em'])
        self.log_mudanca_status(orc, de=de, para=orc.status)
        return Response(OrcamentoDetailSerializer(orc).data)

    @action(detail=True, methods=['post'], url_path='aprovar')
    def aprovar(self, request, pk=None):
        orc = self.get_object()
        if not orc.pode_aprovar:
            return Response({'detail': 'Orçamento não pode ser aprovado neste status.'},
                            status=status.HTTP_400_BAD_REQUEST)
        de = orc.status
        orc.status = 'aprovado'
        orc.save(update_fields=['status', 'atualizado_em'])
        self.log_mudanca_status(orc, de=de, para=orc.status)
        return Response(OrcamentoDetailSerializer(orc).data)

    @action(detail=True, methods=['post'], url_path='recusar')
    def recusar(self, request, pk=None):
        orc = self.get_object()
        if not orc.pode_recusar:
            return Response({'detail': 'Orçamento não pode ser recusado neste status.'},
                            status=status.HTTP_400_BAD_REQUEST)
        de = orc.status
        orc.status = 'recusado'
        orc.save(update_fields=['status', 'atualizado_em'])
        self.log_mudanca_status(orc, de=de, para=orc.status)
        return Response(OrcamentoDetailSerializer(orc).data)

    @action(detail=True, methods=['post'], url_path='converter-em-evento')
    def converter_em_evento(self, request, pk=None):
        orc = self.get_object()
        if not orc.pode_converter:
            return Response({'detail': 'Orçamento precisa estar aprovado para ser convertido.'},
                            status=status.HTTP_400_BAD_REQUEST)

        data_evento = request.data.get('data_evento') or (
            str(orc.data_evento) if orc.data_evento else None
        )
        if not data_evento:
            return Response({'detail': 'Informe a data do evento para converter.'},
                            status=status.HTTP_400_BAD_REQUEST)

        tipo_entrega    = request.data.get('tipo_entrega', orc.tipo_entrega)
        hora_evento     = request.data.get('hora_evento') or None
        local_id        = request.data.get('local', orc.local_id)
        endereco_avulso = request.data.get('endereco_avulso', orc.endereco_avulso)
        bairro_entrega  = request.data.get('bairro_entrega', orc.bairro_entrega)
        taxa_entrega    = request.data.get('taxa_entrega', orc.taxa_entrega)
        sinal_pago      = Decimal(str(request.data.get('sinal_pago', 0) or 0))

        evento = Evento.objects.create(
            numero=Evento.proximo_numero(),
            cliente=orc.cliente,
            cliente_nome=orc.cliente_nome,
            cliente_telefone=orc.cliente_telefone,
            tipo_evento=orc.tipo_evento or 'outro',
            data_evento=data_evento,
            hora_evento=hora_evento,
            tipo_entrega=tipo_entrega,
            local_id=local_id,
            endereco_avulso=endereco_avulso,
            bairro_entrega=bairro_entrega,
            taxa_entrega=taxa_entrega,
            status='orcamento',
            subtotal=orc.subtotal,
            desconto=orc.desconto,
            valor_total=orc.valor_total,
            observacoes=orc.observacoes,
        )

        # Sinal informado na conversão vira o primeiro PagamentoEvento — sinal_pago é
        # sempre derivado da soma dos pagamentos (ver recalcular_sinal_pago), nunca gravado direto.
        if sinal_pago:
            pagamento = PagamentoEvento.objects.create(
                evento=evento,
                valor=sinal_pago,
                forma_pagamento='outro',
                status='pago',
                data_pagamento=timezone.localtime(timezone.now()).date(),
                observacao='Sinal informado na conversão do orçamento em evento.',
            )
            evento.recalcular_sinal_pago()
            registrar(
                ator_ou_none(request), LogAuditoria.ACAO_PAGAMENTO_REGISTRADO,
                detalhes={
                    'evento_id': evento.id, 'evento_numero': evento.numero,
                    'pagamento_id': pagamento.id, 'valor': str(pagamento.valor),
                    'forma_pagamento': pagamento.forma_pagamento, 'origem': 'conversao_orcamento',
                },
                request=request,
            )

        for item in orc.itens.all():
            ItemEvento.objects.create(
                evento=evento,
                produto=item.produto,
                nome=item.nome,
                preco_unit=item.preco_unit,
                quantidade=item.quantidade,
                preco_total=item.preco_total,
                observacao=item.observacao,
                natureza=item.natureza,
            )

        orc.evento = evento
        orc.status = 'convertido'
        orc.save(update_fields=['evento', 'status', 'atualizado_em'])

        registrar(
            ator_ou_none(request), LogAuditoria.ACAO_ORCAMENTO_CONVERTIDO,
            detalhes={
                'orcamento_id': orc.id, 'orcamento_numero': orc.numero,
                'evento_id': evento.id, 'evento_numero': evento.numero,
                'cliente': orc.nome_cliente_display,
            },
            request=request,
        )

        return Response({
            'evento':    EventoDetailSerializer(evento).data,
            'orcamento': OrcamentoDetailSerializer(orc).data,
        }, status=status.HTTP_201_CREATED)

    # ── Itens ─────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='itens')
    def adicionar_item(self, request, pk=None):
        orc = self.get_object()
        if orc.status not in ('rascunho', 'enviado'):
            return Response(
                {'detail': 'Só é possível adicionar itens em orçamentos com status Rascunho ou Enviado.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = ItemOrcamentoCreateSerializer(data=request.data)
        if serializer.is_valid():
            data  = serializer.validated_data
            qty   = data.get('quantidade', 1)
            price = data['preco_unit']
            item = ItemOrcamento.objects.create(
                orcamento=orc,
                preco_total=price * qty,
                **data,
            )
            orc.refresh_from_db()  # evita cache stale do prefetch_related('itens') — ver CLAUDE.md
            orc.recalcular_totais()
            registrar(
                ator_ou_none(request), LogAuditoria.ACAO_ITEM_ADICIONADO,
                detalhes={
                    'model': 'ItemOrcamento', 'id': item.id, 'nome': item.nome,
                    'preco_total': str(item.preco_total),
                    'orcamento_id': orc.id, 'orcamento_numero': orc.numero,
                },
                request=request,
            )
            return Response(OrcamentoDetailSerializer(orc).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path=r'itens/(?P<item_id>[^/.]+)/remover')
    def remover_item(self, request, pk=None, item_id=None):
        orc = self.get_object()
        if orc.status not in ('rascunho', 'enviado'):
            return Response(
                {'detail': 'Não é possível remover itens neste status.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            item = orc.itens.get(pk=item_id)
        except ItemOrcamento.DoesNotExist:
            return Response({'detail': 'Item não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        registrar(
            request.user, LogAuditoria.ACAO_REGISTRO_EXCLUIDO,
            detalhes={
                'model': 'ItemOrcamento', 'id': item.id, 'descricao': str(item),
                'orcamento_id': orc.id, 'orcamento_numero': orc.numero,
            },
            request=request,
        )
        item.delete()
        orc.refresh_from_db()  # evita cache stale do prefetch_related('itens') — ver CLAUDE.md
        orc.recalcular_totais()
        return Response(OrcamentoDetailSerializer(orc).data)

    @action(detail=True, methods=['patch'], url_path=r'itens/(?P<item_id>[^/.]+)/editar')
    def editar_item(self, request, pk=None, item_id=None):
        orc = self.get_object()
        if orc.status not in ('rascunho', 'enviado'):
            return Response(
                {'detail': 'Não é possível editar itens neste status.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            item = orc.itens.get(pk=item_id)
        except ItemOrcamento.DoesNotExist:
            return Response({'detail': 'Item não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ItemOrcamentoCreateSerializer(item, data=request.data)
        if serializer.is_valid():
            campos_auditados = ('nome', 'preco_unit', 'quantidade', 'observacao', 'natureza')
            antes = {c: str(getattr(item, c, None)) for c in campos_auditados}

            data  = serializer.validated_data
            qty   = data.get('quantidade', item.quantidade)
            price = data.get('preco_unit', item.preco_unit)
            for attr, value in data.items():
                setattr(item, attr, value)
            item.preco_total = price * qty
            item.save()
            orc.refresh_from_db()  # evita cache stale do prefetch_related('itens') — ver CLAUDE.md
            orc.recalcular_totais()

            depois = {c: str(getattr(item, c, None)) for c in campos_auditados}
            mudou = {c: {'de': antes[c], 'para': depois[c]} for c in campos_auditados if antes[c] != depois[c]}
            if mudou:
                registrar(
                    ator_ou_none(request), LogAuditoria.ACAO_REGISTRO_ATUALIZADO,
                    detalhes={
                        'model': 'ItemOrcamento', 'id': item.id, 'campos': mudou,
                        'orcamento_id': orc.id, 'orcamento_numero': orc.numero,
                    },
                    request=request,
                )
            return Response(OrcamentoDetailSerializer(orc).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # ── Imagens de Inspiração ────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='imagens')
    def adicionar_imagens(self, request, pk=None):
        orc = self.get_object()
        arquivos = request.FILES.getlist('imagens')
        if not arquivos:
            return Response(
                {'detail': 'Nenhuma imagem enviada.'}, status=status.HTTP_400_BAD_REQUEST
            )
        for arquivo in arquivos:
            ImagemInspiracao.objects.create(orcamento=orc, imagem=arquivo)
        orc.refresh_from_db()
        return Response(OrcamentoDetailSerializer(orc).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path=r'imagens/(?P<imagem_id>[^/.]+)/remover')
    def remover_imagem(self, request, pk=None, imagem_id=None):
        orc = self.get_object()
        try:
            img = orc.imagens_inspiracao.get(pk=imagem_id)
        except ImagemInspiracao.DoesNotExist:
            return Response({'detail': 'Imagem não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        registrar(
            request.user, LogAuditoria.ACAO_REGISTRO_EXCLUIDO,
            detalhes={
                'model': 'ImagemInspiracao', 'id': img.id,
                'orcamento_id': orc.id, 'orcamento_numero': orc.numero,
            },
            request=request,
        )
        img.imagem.delete(save=False)
        img.delete()
        orc.refresh_from_db()
        return Response(OrcamentoDetailSerializer(orc).data)

    @action(detail=True, methods=['post'], url_path='restaurar')
    def restaurar(self, request, pk=None):
        orc = self.get_object()
        if not orc.pode_restaurar:
            return Response({'detail': 'Apenas orçamentos expirados podem ser restaurados.'},
                            status=status.HTTP_400_BAD_REQUEST)
        from notificacoes.models import ConfiguracaoWhatsApp
        dias = ConfiguracaoWhatsApp.get().validade_orcamento_dias
        de = orc.status
        orc.status   = 'rascunho'
        orc.validade = timezone.localtime(timezone.now()).date() + datetime.timedelta(days=dias)
        orc.save(update_fields=['status', 'validade', 'atualizado_em'])
        self.log_mudanca_status(orc, de=de, para=orc.status)
        return Response(OrcamentoDetailSerializer(orc).data)

    @action(detail=True, methods=['post'], url_path='enviar-whatsapp')
    def enviar_whatsapp(self, request, pk=None):
        orc = self.get_object()

        telefone = orc.telefone_display
        if not telefone:
            if orc.cliente:
                return Response(
                    {
                        'detail': 'sem_telefone',
                        'mensagem': (
                            f'O cliente {orc.nome_cliente_display} não tem telefone cadastrado. '
                            'Atualize o cadastro com um número de WhatsApp antes de enviar.'
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {
                    'detail': 'sem_cliente',
                    'mensagem': (
                        'Este orçamento não tem telefone de contato. '
                        'Vincule um cliente do CRM ou adicione um telefone avulso ao orçamento.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        caption = request.data.get('mensagem', '').strip()

        from .pdf_orcamento import gerar_pdf_orcamento
        from notificacoes.servico import notificar_documento

        pdf_bytes    = gerar_pdf_orcamento(orc)
        nome_arquivo = f'{orc.numero}.pdf'

        ok = notificar_documento(
            telefone=telefone,
            pdf_bytes=pdf_bytes,
            nome_arquivo=nome_arquivo,
            caption=caption,
            cliente=orc.cliente,
        )

        if not ok:
            return Response(
                {'detail': 'Falha ao enviar via WhatsApp. Verifique as credenciais Z-API em Configurações.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if orc.status == 'rascunho':
            orc.status = 'enviado'
            orc.save(update_fields=['status', 'atualizado_em'])
            self.log_mudanca_status(orc, de='rascunho', para='enviado')

        return Response(OrcamentoDetailSerializer(orc).data)

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        orc = (
            Orcamento.objects
            .prefetch_related('itens__produto')
            .select_related('cliente', 'evento')
            .get(pk=pk)
        )
        from .pdf_orcamento import gerar_pdf_orcamento
        pdf_bytes = gerar_pdf_orcamento(orc)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{orc.numero}.pdf"'
        return response

    @action(detail=True, methods=['get'], url_path='historico')
    def historico(self, request, pk=None):
        """
        GET /api/v1/eventos/orcamentos/{id}/historico/
        Trilha de auditoria deste orçamento (criação, edição, mudança de
        status, itens, imagens, conversão, contrato) — não confundir com
        clientes/{id}/historico/, que é histórico de PEDIDOS do cliente
        entre canais, um conceito totalmente diferente.
        """
        orc = self.get_object()
        logs = LogAuditoria.objects.filter(
            Q(detalhes__model='Orcamento', detalhes__id=orc.id) |
            Q(detalhes__model='ItemOrcamento', detalhes__orcamento_id=orc.id) |
            Q(detalhes__model='ImagemInspiracao', detalhes__orcamento_id=orc.id) |
            Q(acao=LogAuditoria.ACAO_ORCAMENTO_CONVERTIDO, detalhes__orcamento_id=orc.id) |
            Q(
                acao__in=[LogAuditoria.ACAO_CONTRATO_EMITIDO, LogAuditoria.ACAO_CONTRATO_ENVIADO],
                detalhes__orcamento_id=orc.id,
            )
        ).select_related('usuario').order_by('-criado_em')
        return Response(LogAuditoriaSerializer(logs, many=True).data)

    @action(detail=True, methods=['post'], url_path='gerar-contrato')
    def gerar_contrato(self, request, pk=None):
        orc = self.get_object()

        if orc.status not in ('aprovado', 'convertido'):
            return Response(
                {'detail': 'Só é possível emitir contrato de um orçamento aprovado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cliente = orc.cliente
        if not cliente:
            return Response(
                {
                    'detail': 'sem_cliente',
                    'mensagem': (
                        'Este orçamento não está vinculado a um cliente do CRM. '
                        'Vincule um cliente antes de emitir o contrato.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not orc.data_evento:
            return Response(
                {
                    'detail': 'sem_data_evento',
                    'mensagem': 'Este orçamento não tem a data do evento definida. Preencha-a antes de emitir o contrato.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Campos do CONTRATANTE — opcionais no cadastro, exigidos aqui (ver Contrato.md)
        campos_atualizaveis = ['cpf', 'rg', 'rg_orgao_emissor', 'nacionalidade', 'profissao', 'estado_civil']
        campos_obrigatorios = ['cpf', 'rg', 'nacionalidade', 'profissao', 'estado_civil']

        dados_cliente = {c: request.data[c] for c in campos_atualizaveis if request.data.get(c)}
        if dados_cliente:
            from clientes.serializers import ClienteDetailSerializer
            serializer = ClienteDetailSerializer(cliente, data=dados_cliente, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

        faltando = [c for c in campos_obrigatorios if not getattr(cliente, c)]
        if faltando:
            return Response(
                {
                    'detail': 'dados_incompletos',
                    'campos_faltando': faltando,
                    'mensagem': (
                        'Complete os dados do CONTRATANTE (CPF, RG, nacionalidade, profissão e estado '
                        'civil) para emitir o contrato.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        endereco_avulso    = (request.data.get('endereco_avulso') or '').strip()
        endereco_principal = cliente.enderecos.filter(principal=True).first()
        if endereco_principal:
            contratante_endereco = endereco_principal.endereco_completo
        elif endereco_avulso:
            contratante_endereco = endereco_avulso
        else:
            return Response(
                {
                    'detail': 'sem_endereco',
                    'mensagem': (
                        'O cliente não tem endereço principal cadastrado. Informe um endereço avulso '
                        'para o contrato.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        local_evento = orc.local.endereco_completo if orc.local else orc.endereco_avulso

        cfg              = ConfiguracaoContrato.get()
        percentual_sinal = cfg.percentual_sinal
        valor_sinal      = (orc.valor_total * percentual_sinal / Decimal('100')).quantize(Decimal('0.01'))
        data_quitacao    = orc.data_evento - datetime.timedelta(days=cfg.prazo_quitacao_dias)

        contrato = Contrato.objects.create(
            numero=Contrato.proximo_numero(),
            orcamento=orc,
            evento=orc.evento,
            cliente=cliente,
            contratante_nome=cliente.nome,
            contratante_nacionalidade=cliente.nacionalidade,
            contratante_profissao=cliente.profissao,
            contratante_rg=cliente.rg,
            contratante_rg_orgao_emissor=cliente.rg_orgao_emissor,
            contratante_cpf=cliente.cpf,
            contratante_estado_civil=cliente.estado_civil,
            contratante_endereco=contratante_endereco,
            data_evento=orc.data_evento,
            hora_evento=None,
            local_evento=local_evento,
            valor_total=orc.valor_total,
            percentual_sinal=percentual_sinal,
            valor_sinal=valor_sinal,
            data_quitacao=data_quitacao,
            possui_clausula_adiamento=True,
            **_campos_entrada_contrato(request),
        )

        registrar(
            request.user, LogAuditoria.ACAO_CONTRATO_EMITIDO,
            detalhes={
                'contrato_numero': contrato.numero, 'orcamento_id': orc.id, 'orcamento_numero': orc.numero,
                'cliente': cliente.nome, 'valor_total': str(contrato.valor_total),
            },
            request=request,
        )

        return Response(ContratoSerializer(contrato).data, status=status.HTTP_201_CREATED)


# ─── Contrato ──────────────────────────────────────────────────────────────────

class ContratoViewSet(CsrfExemptMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Somente leitura via API — Contrato só é criado através de
    OrcamentoViewSet.gerar_contrato (nunca via POST direto neste ViewSet)."""
    queryset           = Contrato.objects.select_related('orcamento', 'cliente', 'evento').all()
    serializer_class   = ContratoSerializer
    filter_backends    = [filters.OrderingFilter]
    ordering           = ['-criado_em']
    # Sobrescreve o [] do CsrfExemptMixin — só assim dá pra saber quem enviou o contrato
    # (ver get_permissions). list/retrieve/pdf continuam AllowAny, sem mudança de comportamento.
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action == 'enviar_whatsapp':
            return [IsAuthenticated()]
        return [AllowAny()]

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        contrato = self.get_object()
        from .pdf_contrato import gerar_pdf_contrato
        pdf_bytes = gerar_pdf_contrato(contrato)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{contrato.numero}.pdf"'
        return response

    @action(detail=True, methods=['post'], url_path='enviar-whatsapp')
    def enviar_whatsapp(self, request, pk=None):
        contrato = self.get_object()

        telefone = contrato.cliente.telefone_principal if contrato.cliente else ''
        if not telefone:
            return Response(
                {
                    'detail': 'sem_telefone',
                    'mensagem': 'Este contrato não tem telefone de contato vinculado.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        caption = request.data.get('mensagem', '').strip()

        from .pdf_contrato import gerar_pdf_contrato
        from notificacoes.servico import notificar_documento

        pdf_bytes    = gerar_pdf_contrato(contrato)
        nome_arquivo = f'{contrato.numero}.pdf'

        ok = notificar_documento(
            telefone=telefone,
            pdf_bytes=pdf_bytes,
            nome_arquivo=nome_arquivo,
            caption=caption,
            cliente=contrato.cliente,
            tipo='contrato',
        )

        if not ok:
            return Response(
                {'detail': 'Falha ao enviar via WhatsApp. Verifique as credenciais Z-API em Configurações.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        contrato.status = 'enviado'
        contrato.save(update_fields=['status', 'atualizado_em'])

        registrar(
            request.user, LogAuditoria.ACAO_CONTRATO_ENVIADO,
            detalhes={
                'contrato_numero': contrato.numero, 'orcamento_id': contrato.orcamento_id,
                'evento_id': contrato.evento_id,
                'cliente': contrato.cliente.nome if contrato.cliente else None,
                'telefone': telefone,
            },
            request=request,
        )

        return Response(ContratoSerializer(contrato).data)


# ─── Aditivo de Contrato ───────────────────────────────────────────────────────

class AditivoContratoViewSet(CsrfExemptMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Somente leitura via API — AditivoContrato só é criado através de
    EventoViewSet.gerar_aditivo (nunca via POST direto neste ViewSet)."""
    queryset           = AditivoContrato.objects.select_related('contrato', 'evento', 'cliente').all()
    serializer_class   = AditivoContratoSerializer
    filter_backends    = [filters.OrderingFilter]
    ordering           = ['-criado_em']
    # Mesmo padrão de ContratoViewSet — list/retrieve/pdf continuam AllowAny,
    # só enviar-whatsapp exige login (pra sempre ter um ator no log).
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action == 'enviar_whatsapp':
            return [IsAuthenticated()]
        return [AllowAny()]

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        aditivo = self.get_object()
        from .pdf_aditivo import gerar_pdf_aditivo
        pdf_bytes = gerar_pdf_aditivo(aditivo)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{aditivo.numero}.pdf"'
        return response

    @action(detail=True, methods=['post'], url_path='enviar-whatsapp')
    def enviar_whatsapp(self, request, pk=None):
        aditivo = self.get_object()

        telefone = aditivo.cliente.telefone_principal if aditivo.cliente else ''
        if not telefone:
            return Response(
                {
                    'detail': 'sem_telefone',
                    'mensagem': 'Este aditivo não tem telefone de contato vinculado.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        caption = request.data.get('mensagem', '').strip()

        from .pdf_aditivo import gerar_pdf_aditivo
        from notificacoes.servico import notificar_documento

        pdf_bytes    = gerar_pdf_aditivo(aditivo)
        nome_arquivo = f'{aditivo.numero}.pdf'

        ok = notificar_documento(
            telefone=telefone,
            pdf_bytes=pdf_bytes,
            nome_arquivo=nome_arquivo,
            caption=caption,
            cliente=aditivo.cliente,
            tipo='aditivo_contrato',
        )

        if not ok:
            return Response(
                {'detail': 'Falha ao enviar via WhatsApp. Verifique as credenciais Z-API em Configurações.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        registrar(
            request.user, LogAuditoria.ACAO_ADITIVO_ENVIADO,
            detalhes={
                'aditivo_numero': aditivo.numero, 'contrato_numero': aditivo.contrato.numero,
                'evento_id': aditivo.evento_id,
                'cliente': aditivo.cliente.nome if aditivo.cliente else None,
                'telefone': telefone,
            },
            request=request,
        )

        return Response(AditivoContratoSerializer(aditivo).data)


# ─── Configuração de Contrato (singleton) ─────────────────────────────────────

class ConfiguracaoContratoViewSet(CsrfExemptMixin, viewsets.GenericViewSet):
    serializer_class   = ConfiguracaoContratoSerializer
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action == 'partial_update':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_object(self):
        return ConfiguracaoContrato.get()

    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(self.get_object()).data)

    def partial_update(self, request, pk=None):
        config  = self.get_object()
        campos  = list(request.data.keys())
        antes   = {c: str(getattr(config, c)) for c in campos if hasattr(config, c)}
        serializer = ConfiguracaoContratoSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        depois = {c: str(getattr(config, c)) for c in campos if hasattr(config, c)}
        registrar(
            request.user, LogAuditoria.ACAO_CONFIG_CONTRATO_ALTERADA,
            detalhes={'antes': antes, 'depois': depois},
            request=request,
        )
        return Response(serializer.data)


# ─── Alertas de Evento (pagamento pendente / aviso de entrega) ────────────────

class ConfiguracaoAlertaEventoViewSet(CsrfExemptMixin, viewsets.GenericViewSet):
    serializer_class   = ConfiguracaoAlertaEventoSerializer
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action == 'partial_update':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_object(self):
        return ConfiguracaoAlertaEvento.get()

    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(self.get_object()).data)

    def partial_update(self, request, pk=None):
        config  = self.get_object()
        campos  = list(request.data.keys())
        antes   = {c: str(getattr(config, c)) for c in campos if hasattr(config, c)}
        serializer = ConfiguracaoAlertaEventoSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        depois = {c: str(getattr(config, c)) for c in campos if hasattr(config, c)}
        registrar(
            request.user, LogAuditoria.ACAO_CONFIG_ALERTA_EVENTO_ALTERADA,
            detalhes={'antes': antes, 'depois': depois},
            request=request,
        )
        return Response(serializer.data)


class TelefoneAlertaEventoViewSet(AuditoriaDestroyMixin, CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = TelefoneAlertaEvento.objects.all()
    serializer_class   = TelefoneAlertaEventoSerializer
    authentication_classes = [TokenAuthentication]
    campos_log_exclusao = ['numero', 'nome']

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated()]
        return [AllowAny()]
