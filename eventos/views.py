import datetime
from decimal import Decimal

from django.conf import settings
from django.db.models import Q, Sum, Count
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status, filters, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import (
    LocalEvento, Evento, ItemEvento, PagamentoEvento, Orcamento, ItemOrcamento,
    ImagemInspiracao, Contrato, ConfiguracaoContrato,
)
from notificacoes.servico import notificar, _fone_pedido
from usuarios.authentication import TokenAuthentication
from auditoria.models import LogAuditoria
from auditoria.utils import registrar, ator_ou_none
from auditoria.mixins import (
    AuditoriaCreateMixin, AuditoriaDestroyMixin, AuditoriaStatusMixin, AuditoriaUpdateMixin,
)
from auditoria.serializers import LogAuditoriaSerializer


def _notificar_evento(evento, mensagem):
    notificar(_fone_pedido(evento), mensagem, cliente=evento.cliente, tipo='pedido')
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
    ConfiguracaoContratoSerializer,
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
        'desconto', 'observacoes',
    ]

    def get_permissions(self):
        if self.action in (
            'adicionar_pagamento', 'remover_pagamento', 'destroy', 'remover_item',
            'create', 'update', 'partial_update',
            'confirmar', 'iniciar_producao', 'marcar_pronto', 'entregar', 'cancelar',
            'adicionar_item', 'historico',
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
            )
        ).select_related('usuario').order_by('-criado_em')
        return Response(LogAuditoriaSerializer(logs, many=True).data)

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
            .exclude(status='cancelado')
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
        ).exclude(status='cancelado')

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
            .exclude(status='cancelado')
            .values('status')
            .annotate(total=Count('id'))
            .values_list('status', 'total')
        )

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
    queryset           = Orcamento.objects.prefetch_related('itens', 'imagens_inspiracao').select_related('cliente', 'evento').all()
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
            campos_auditados = ('nome', 'preco_unit', 'quantidade', 'observacao')
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

        if orc.status != 'aprovado':
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
                'cliente': contrato.cliente.nome if contrato.cliente else None,
                'telefone': telefone,
            },
            request=request,
        )

        return Response(ContratoSerializer(contrato).data)


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
