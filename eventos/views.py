import datetime

from django.conf import settings
from django.db.models import Q, Sum, Count
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import LocalEvento, Evento, ItemEvento, Orcamento, ItemOrcamento
from notificacoes.servico import notificar, _fone_pedido


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
    OrcamentoListSerializer,
    OrcamentoDetailSerializer,
    OrcamentoCreateSerializer,
    ItemOrcamentoCreateSerializer,
)


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
        _notificar_evento(evento, f'✅ Sua encomenda #{evento.numero} está confirmada para {evento.data_evento.strftime("%d/%m/%Y")}! Qualquer dúvida, é só chamar. 🍬')
        return Response(EventoDetailSerializer(evento).data)

    @action(detail=True, methods=['post'], url_path='iniciar-producao')
    def iniciar_producao(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_iniciar_producao:
            return Response({'detail': 'Evento não pode iniciar produção neste status.'},
                            status=status.HTTP_400_BAD_REQUEST)
        evento.status = 'em_producao'
        evento.save(update_fields=['status', 'atualizado_em'])
        _notificar_evento(evento, f'👨‍🍳 Sua encomenda #{evento.numero} entrou em produção! Estamos caprichando em cada detalhe.')
        return Response(EventoDetailSerializer(evento).data)

    @action(detail=True, methods=['post'], url_path='marcar-pronto')
    def marcar_pronto(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_marcar_pronto:
            return Response({'detail': 'Evento não pode ser marcado como pronto neste status.'},
                            status=status.HTTP_400_BAD_REQUEST)
        evento.status = 'pronto'
        evento.save(update_fields=['status', 'atualizado_em'])
        _notificar_evento(evento, f'🎉 Sua encomenda #{evento.numero} está pronta! Entraremos em contato para combinar a entrega.')
        return Response(EventoDetailSerializer(evento).data)

    @action(detail=True, methods=['post'], url_path='entregar')
    def entregar(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_entregar:
            return Response({'detail': 'Evento não pode ser marcado como entregue neste status.'},
                            status=status.HTTP_400_BAD_REQUEST)
        evento.status = 'entregue'
        evento.save(update_fields=['status', 'atualizado_em'])
        _notificar_evento(evento, f'💚 Encomenda #{evento.numero} entregue! Obrigado pela confiança na Arretado Doces. Até a próxima! 🍬')
        return Response(EventoDetailSerializer(evento).data)

    @action(detail=True, methods=['post'], url_path='cancelar')
    def cancelar(self, request, pk=None):
        evento = self.get_object()
        if not evento.pode_cancelar:
            return Response({'detail': 'Evento já foi entregue ou cancelado.'},
                            status=status.HTTP_400_BAD_REQUEST)
        evento.status = 'cancelado'
        evento.save(update_fields=['status', 'atualizado_em'])
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


# ─── Orçamentos ───────────────────────────────────────────────────────────────

class OrcamentoViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    queryset           = Orcamento.objects.prefetch_related('itens').select_related('cliente', 'evento').all()
    permission_classes = [AllowAny]
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ['criado_em', 'valor_total', 'data_evento']
    ordering           = ['-criado_em']

    def get_serializer_class(self):
        if self.action == 'list':
            return OrcamentoListSerializer
        if self.action in ('update', 'partial_update'):
            return OrcamentoCreateSerializer
        return OrcamentoDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = OrcamentoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        orcamento = serializer.save()
        return Response(
            OrcamentoDetailSerializer(orcamento).data,
            status=status.HTTP_201_CREATED,
        )

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
        orc.status = 'enviado'
        orc.save(update_fields=['status', 'atualizado_em'])
        return Response(OrcamentoDetailSerializer(orc).data)

    @action(detail=True, methods=['post'], url_path='aprovar')
    def aprovar(self, request, pk=None):
        orc = self.get_object()
        if not orc.pode_aprovar:
            return Response({'detail': 'Orçamento não pode ser aprovado neste status.'},
                            status=status.HTTP_400_BAD_REQUEST)
        orc.status = 'aprovado'
        orc.save(update_fields=['status', 'atualizado_em'])
        return Response(OrcamentoDetailSerializer(orc).data)

    @action(detail=True, methods=['post'], url_path='recusar')
    def recusar(self, request, pk=None):
        orc = self.get_object()
        if not orc.pode_recusar:
            return Response({'detail': 'Orçamento não pode ser recusado neste status.'},
                            status=status.HTTP_400_BAD_REQUEST)
        orc.status = 'recusado'
        orc.save(update_fields=['status', 'atualizado_em'])
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

        tipo_entrega    = request.data.get('tipo_entrega', 'retirada_loja')
        hora_evento     = request.data.get('hora_evento') or None
        local_id        = request.data.get('local') or None
        endereco_avulso = request.data.get('endereco_avulso', '')
        sinal_pago      = request.data.get('sinal_pago', 0)

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
            status='orcamento',
            subtotal=orc.subtotal,
            desconto=orc.desconto,
            valor_total=orc.valor_total,
            sinal_pago=sinal_pago,
            observacoes=orc.observacoes,
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
            ItemOrcamento.objects.create(
                orcamento=orc,
                preco_total=price * qty,
                **data,
            )
            orc.recalcular_totais()
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
        item.delete()
        orc.recalcular_totais()
        return Response(OrcamentoDetailSerializer(orc).data)

    @action(detail=True, methods=['post'], url_path='restaurar')
    def restaurar(self, request, pk=None):
        orc = self.get_object()
        if not orc.pode_restaurar:
            return Response({'detail': 'Apenas orçamentos expirados podem ser restaurados.'},
                            status=status.HTTP_400_BAD_REQUEST)
        from notificacoes.models import ConfiguracaoWhatsApp
        dias = ConfiguracaoWhatsApp.get().validade_orcamento_dias
        orc.status   = 'rascunho'
        orc.validade = timezone.now().date() + datetime.timedelta(days=dias)
        orc.save(update_fields=['status', 'validade', 'atualizado_em'])
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
