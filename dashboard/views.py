from datetime import timedelta

from django.db.models import F, Sum, Count
from django.utils import timezone
from rest_framework import views
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from pedidos.models import PedidoUnificado
from eventos.models import Evento, PagamentoEvento, ConfiguracaoAlertaEvento
from fichas.models import MateriaPrima
from pdv.models import Produto


class CsrfExemptMixin:
    authentication_classes = []


class DashboardResumoView(CsrfExemptMixin, views.APIView):
    """
    Agrega vendas do dia e histórico recente dos canais de venda
    (iFood, PDV Próprio, Eventos) a partir do PedidoUnificado e dos
    models de eventos/. Não cria nenhum model — view somente leitura.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        hoje  = timezone.localtime(timezone.now()).date()
        ontem = hoje - timedelta(days=1)

        ifood_total_hoje,   ifood_pedidos_hoje   = self._canal_dia('ifood', hoje)
        pdv_total_hoje,     pdv_pedidos_hoje     = self._canal_dia('pdv', hoje)
        eventos_recebido_hoje  = self._eventos_recebido_dia(hoje)
        eventos_criados_hoje   = Evento.objects.filter(criado_em__date=hoje).count()
        eventos_entregues_hoje = Evento.objects.filter(status='entregue', atualizado_em__date=hoje).count()

        total_recebido_hoje  = ifood_total_hoje + pdv_total_hoje + eventos_recebido_hoje
        total_recebido_ontem = self._total_recebido_dia(ontem)
        comparativo_ontem_pct = (
            round((total_recebido_hoje - total_recebido_ontem) / total_recebido_ontem * 100, 1)
            if total_recebido_ontem else None
        )

        grafico_7dias = []
        for i in range(6, -1, -1):
            dia = hoje - timedelta(days=i)
            ifood_dia, _ = self._canal_dia('ifood', dia)
            pdv_dia, _   = self._canal_dia('pdv', dia)
            grafico_7dias.append({
                'data':    str(dia),
                'ifood':   ifood_dia,
                'pdv':     pdv_dia,
                'eventos': self._eventos_recebido_dia(dia),
            })

        return Response({
            'canais': {
                'ifood':   {'total_hoje': ifood_total_hoje, 'pedidos_hoje': ifood_pedidos_hoje},
                'pdv':     {'total_hoje': pdv_total_hoje, 'pedidos_hoje': pdv_pedidos_hoje},
                'eventos': {
                    'recebido_hoje':  eventos_recebido_hoje,
                    'criados_hoje':   eventos_criados_hoje,
                    'entregues_hoje': eventos_entregues_hoje,
                },
                'anotaai': None,
            },
            'estoque':               self._estoque(),
            'total_recebido_hoje':   total_recebido_hoje,
            'comparativo_ontem_pct': comparativo_ontem_pct,
            'grafico_7dias':         grafico_7dias,
            'a_receber':             self._a_receber(),
            'fila_operacional':      self._fila_operacional(),
            'proximos_eventos':      self._proximos_eventos(hoje),
            'ticket_medio':          self._ticket_medio(hoje),
            'alertas':               self._alertas(hoje),
        })

    # ── Canais (PedidoUnificado) ───────────────────────────────────────────

    @staticmethod
    def _canal_dia(canal, dia):
        total = PedidoUnificado.objects.filter(
            canal=canal, status='concluido', pedido_em__date=dia,
        ).aggregate(t=Sum('total'))['t'] or 0
        pedidos = PedidoUnificado.objects.filter(canal=canal, pedido_em__date=dia).count()
        return float(total), pedidos

    @staticmethod
    def _eventos_recebido_dia(dia):
        total = PagamentoEvento.objects.filter(
            status='pago', data_pagamento=dia,
        ).aggregate(t=Sum('valor'))['t'] or 0
        return float(total)

    def _total_recebido_dia(self, dia):
        ifood_total, _ = self._canal_dia('ifood', dia)
        pdv_total, _   = self._canal_dia('pdv', dia)
        return ifood_total + pdv_total + self._eventos_recebido_dia(dia)

    # ── A receber (saldo pendente de eventos) ──────────────────────────────

    @staticmethod
    def _a_receber():
        qs = (
            Evento.objects.exclude(status='cancelado')
            .annotate(saldo=F('valor_total') - F('sinal_pago'))
            .filter(saldo__gt=0)
        )
        total = qs.aggregate(t=Sum('saldo'))['t'] or 0
        return {
            'total': float(total),
            'eventos': [
                {
                    'id':             e.id,
                    'numero':         e.numero,
                    'cliente':        e.nome_cliente_display,
                    'saldo_restante': float(e.saldo),
                    'data_evento':    str(e.data_evento),
                }
                for e in qs.order_by('data_evento')[:5]
            ],
        }

    # ── Alertas (eventos com pagamento pendente / entrega próxima) ─────────
    # Mesmas janelas usadas por eventos/management/commands/alertar_eventos.py
    # (não olha AlertaEventoEnviado — aqui é "o que está na janela agora",
    # independente de já ter mandado WhatsApp ou não)

    @staticmethod
    def _alertas(hoje):
        cfg = ConfiguracaoAlertaEvento.get()
        alertas = []

        if cfg.ativo_pagamento:
            limite = hoje + timedelta(days=cfg.dias_antes_pagamento)
            qs = (
                Evento.objects.exclude(status__in=['cancelado', 'entregue'])
                .annotate(saldo=F('valor_total') - F('sinal_pago'))
                .filter(saldo__gt=0, data_evento__gte=hoje, data_evento__lte=limite)
            )
            for e in qs:
                alertas.append({
                    'tipo':            'pagamento_pendente',
                    'evento_id':       e.id,
                    'numero':          e.numero,
                    'cliente':         e.nome_cliente_display,
                    'data_evento':     str(e.data_evento),
                    'dias_restantes':  (e.data_evento - hoje).days,
                    'saldo_restante':  float(e.saldo),
                })

        if cfg.ativo_entrega:
            limite = hoje + timedelta(days=cfg.dias_antes_entrega)
            qs = (
                Evento.objects.exclude(status__in=['cancelado', 'entregue'])
                .filter(tipo_entrega='entrega_local', data_evento__gte=hoje, data_evento__lte=limite)
            )
            for e in qs:
                alertas.append({
                    'tipo':           'aviso_entrega',
                    'evento_id':      e.id,
                    'numero':         e.numero,
                    'cliente':        e.nome_cliente_display,
                    'data_evento':    str(e.data_evento),
                    'dias_restantes': (e.data_evento - hoje).days,
                    'local':          e.local.nome if e.local else e.endereco_avulso,
                    'bairro':         e.bairro_entrega,
                })

        return sorted(alertas, key=lambda a: a['dias_restantes'])

    # ── Fila operacional (cruza os 3 canais via PedidoUnificado) ───────────

    @staticmethod
    def _fila_operacional():
        return {
            'pendente':   PedidoUnificado.objects.filter(status__in=['pendente', 'confirmado']).count(),
            'em_preparo': PedidoUnificado.objects.filter(status='em_preparo').count(),
            'pronto':     PedidoUnificado.objects.filter(status='pronto').count(),
        }

    # ── Próximos eventos ────────────────────────────────────────────────────

    @staticmethod
    def _proximos_eventos(hoje):
        qs = Evento.objects.filter(
            status__in=['confirmado', 'em_producao', 'pronto'],
            data_evento__gte=hoje,
        ).order_by('data_evento', 'hora_evento')[:5]
        return [
            {
                'id':           e.id,
                'numero':       e.numero,
                'cliente':      e.nome_cliente_display,
                'titulo':       e.get_tipo_evento_display(),
                'data_evento':  str(e.data_evento),
                'hora_evento':  e.hora_evento.strftime('%H:%M') if e.hora_evento else None,
                'valor_total':  float(e.valor_total),
            }
            for e in qs
        ]

    # ── Estoque (itens abaixo do mínimo) ───────────────────────────────────

    @staticmethod
    def _estoque():
        materias_baixas = MateriaPrima.objects.filter(
            estoque_minimo__gt=0, quantidade_estoque__lt=F('estoque_minimo'), ativo=True,
        )
        produtos_baixos = Produto.objects.filter(
            estoque_minimo__gt=0, quantidade_estoque__lt=F('estoque_minimo'), ativo=True,
        ).exclude(tipo='kit')
        return {
            'itens_abaixo_minimo': materias_baixas.count() + produtos_baixos.count(),
            'insumos': list(materias_baixas.values_list('nome', flat=True)[:5]),
            'produtos': list(produtos_baixos.values_list('nome', flat=True)[:5]),
        }

    # ── Ticket médio (últimos 30 dias) ─────────────────────────────────────

    @staticmethod
    def _ticket_medio(hoje):
        desde = hoje - timedelta(days=30)

        def media_canal(canal):
            agg = PedidoUnificado.objects.filter(
                canal=canal, status='concluido', pedido_em__date__gte=desde,
            ).aggregate(t=Sum('total'), c=Count('id'))
            return float(agg['t'] / agg['c']) if agg['c'] else 0.0

        agg_eventos = Evento.objects.filter(
            status='entregue', atualizado_em__date__gte=desde,
        ).aggregate(t=Sum('valor_total'), c=Count('id'))
        eventos_media = float(agg_eventos['t'] / agg_eventos['c']) if agg_eventos['c'] else 0.0

        return {
            'ifood':   media_canal('ifood'),
            'pdv':     media_canal('pdv'),
            'eventos': eventos_media,
        }
