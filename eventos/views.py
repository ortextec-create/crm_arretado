from django.db.models import Q, Sum, Count
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import LocalEvento, Evento, ItemEvento
from .serializers import (
    LocalEventoSerializer,
    EventoListSerializer,
    EventoDetailSerializer,
    EventoCreateSerializer,
    EventoAgendaSerializer,
    ItemEventoCreateSerializer,
    ItemEventoSerializer,
)

import datetime


class CsrfExemptMixin:
    authentication_classes = []


# ─── Local de Evento ──────────────────────────────────────────────────────────

class LocalEventoViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = LocalEvento.objects.all()
    serializer_class   = LocalEventoSerializer
    permission_classes = [AllowAny]

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

class EventoViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = Evento.objects.prefetch_related('itens').select_related('cliente', 'local').all()
    permission_classes = [AllowAny]
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ['data_evento', 'criado_em', 'valor_total']
    ordering           = ['data_evento', 'hora_evento']

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
            qs = qs.filter(data_evento__gte=timezone.now().date())

        return qs

    # ── Ações de status ───────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='confirmar')
    def confirmar(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_confirmar:
            return Response({'detail': 'Evento não pode ser confirmado neste status.'},
                            status=status.HTTP_400_BAD_REQUEST)
        evento.status = 'confirmado'
        evento.save(update_fields=['status', 'atualizado_em'])
        return Response(EventoDetailSerializer(evento).data)

    @action(detail=True, methods=['post'], url_path='iniciar-producao')
    def iniciar_producao(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_iniciar_producao:
            return Response({'detail': 'Evento não pode iniciar produção neste status.'},
                            status=status.HTTP_400_BAD_REQUEST)
        evento.status = 'em_producao'
        evento.save(update_fields=['status', 'atualizado_em'])
        return Response(EventoDetailSerializer(evento).data)

    @action(detail=True, methods=['post'], url_path='marcar-pronto')
    def marcar_pronto(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_marcar_pronto:
            return Response({'detail': 'Evento não pode ser marcado como pronto neste status.'},
                            status=status.HTTP_400_BAD_REQUEST)
        evento.status = 'pronto'
        evento.save(update_fields=['status', 'atualizado_em'])
        return Response(EventoDetailSerializer(evento).data)

    @action(detail=True, methods=['post'], url_path='entregar')
    def entregar(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_entregar:
            return Response({'detail': 'Evento não pode ser marcado como entregue neste status.'},
                            status=status.HTTP_400_BAD_REQUEST)
        evento.status = 'entregue'
        evento.save(update_fields=['status', 'atualizado_em'])
        return Response(EventoDetailSerializer(evento).data)

    @action(detail=True, methods=['post'], url_path='cancelar')
    def cancelar(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_cancelar:
            return Response({'detail': 'Evento já foi entregue ou cancelado.'},
                            status=status.HTTP_400_BAD_REQUEST)
        evento.status = 'cancelado'
        evento.save(update_fields=['status', 'atualizado_em'])
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
            ItemEvento.objects.create(
                evento=evento,
                preco_total=price * qty,
                **data,
            )
            evento.recalcular_totais()
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
        item.delete()
        evento.recalcular_totais()
        return Response(EventoDetailSerializer(evento).data)

    # ── View de agenda (calendário) ────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='agenda')
    def agenda(self, request):
        """
        Retorna eventos agrupados por dia para uma visão de calendário.
        Parâmetro: ?mes=2025-06 (obrigatório)
        """
        mes = request.query_params.get('mes')
        if not mes:
            hoje = timezone.now().date()
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
        hoje  = timezone.now().date()
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
