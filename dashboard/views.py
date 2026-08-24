from datetime import timedelta

from django.db.models import F, Sum, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import views
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from empresas.models import Empresa
from pedidos.models import PedidoUnificado
from eventos.models import Evento, PagamentoEvento, ConfiguracaoAlertaEvento
from fichas.models import MateriaPrima
from pdv.models import Produto
from usuarios.authentication import TokenAuthentication


class CsrfExemptMixin:
    authentication_classes = []


def _resolver_empresa(request):
    """
    Fase 5 do multi-empresa: ?empresa=<id> explícito > empresa_ativa do usuário
    autenticado > Empresa.get_padrao() — nunca .objects.first() (mesmo padrão de
    financeiro/views.py::_resolver_empresa e ifood/views.py::_resolver_config_por_empresa,
    duplicado aqui a propósito, ver CLAUDE.md). ?empresa=todas devolve None (consolidado).
    """
    param = request.query_params.get('empresa')
    if param == 'todas':
        return None
    if param:
        return get_object_or_404(Empresa, pk=param)
    user = request.user
    if getattr(user, 'is_authenticated', False) and getattr(user, 'empresa_ativa_id', None):
        return user.empresa_ativa
    return Empresa.get_padrao()


class DashboardResumoView(CsrfExemptMixin, views.APIView):
    """
    Agrega vendas do dia e histórico recente dos canais de venda
    (iFood, PDV Próprio, Eventos) a partir do PedidoUnificado e dos
    models de eventos/. Não cria nenhum model — view somente leitura.

    Fase 5 do multi-empresa: aceita ?empresa=<id>/?empresa=todas (default:
    empresa_ativa do usuário autenticado, senão Empresa.get_padrao()).
    PDV/iFood filtram por PedidoUnificado.empresa normalmente; Eventos/Estoque
    são mono-empresa (sem FK própria) e só aparecem quando a empresa resolvida é
    a matriz ou 'todas' — visão de uma empresa não-matriz (ex: MANGAIO) zera
    esses blocos e ganha o card `repasse_ifood_a_receber`.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        empresa = _resolver_empresa(request)
        eventos_habilitado = empresa is None or empresa.padrao

        hoje  = timezone.localtime(timezone.now()).date()
        ontem = hoje - timedelta(days=1)

        ifood_total_hoje,   ifood_pedidos_hoje   = self._canal_dia('ifood', hoje, empresa)
        pdv_total_hoje,     pdv_pedidos_hoje     = self._canal_dia('pdv', hoje, empresa)
        eventos_recebido_hoje  = self._eventos_recebido_dia(hoje) if eventos_habilitado else 0.0
        eventos_criados_hoje   = Evento.objects.filter(criado_em__date=hoje).count() if eventos_habilitado else 0
        eventos_entregues_hoje = (
            Evento.objects.filter(status='entregue', atualizado_em__date=hoje).count()
            if eventos_habilitado else 0
        )

        total_recebido_hoje  = ifood_total_hoje + pdv_total_hoje + eventos_recebido_hoje
        total_recebido_ontem = self._total_recebido_dia(ontem, empresa, eventos_habilitado)
        comparativo_ontem_pct = (
            round((total_recebido_hoje - total_recebido_ontem) / total_recebido_ontem * 100, 1)
            if total_recebido_ontem else None
        )

        grafico_7dias = []
        for i in range(6, -1, -1):
            dia = hoje - timedelta(days=i)
            ifood_dia, _ = self._canal_dia('ifood', dia, empresa)
            pdv_dia, _   = self._canal_dia('pdv', dia, empresa)
            grafico_7dias.append({
                'data':    str(dia),
                'ifood':   ifood_dia,
                'pdv':     pdv_dia,
                'eventos': self._eventos_recebido_dia(dia) if eventos_habilitado else 0.0,
            })

        return Response({
            'empresa': {'id': empresa.id, 'nome': empresa.nome, 'padrao': empresa.padrao} if empresa else None,
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
            'estoque':                  self._estoque() if eventos_habilitado else self._estoque_vazio(),
            'total_recebido_hoje':      total_recebido_hoje,
            'comparativo_ontem_pct':    comparativo_ontem_pct,
            'grafico_7dias':            grafico_7dias,
            'a_receber':                self._a_receber() if eventos_habilitado else {'total': 0.0, 'eventos': []},
            'repasse_ifood_a_receber':  self._repasse_ifood_a_receber(empresa),
            'fila_operacional':         self._fila_operacional(empresa),
            'proximos_eventos':        self._proximos_eventos(hoje) if eventos_habilitado else [],
            'ticket_medio':            self._ticket_medio(hoje, empresa, eventos_habilitado),
            'alertas':                 self._alertas(hoje) if eventos_habilitado else [],
        })

    # ── Canais (PedidoUnificado) ───────────────────────────────────────────

    @staticmethod
    def _canal_dia(canal, dia, empresa=None):
        qs = PedidoUnificado.objects.filter(canal=canal, pedido_em__date=dia)
        if empresa is not None:
            qs = qs.filter(empresa=empresa)
        total = qs.filter(status='concluido').aggregate(t=Sum('total'))['t'] or 0
        pedidos = qs.count()
        return float(total), pedidos

    @staticmethod
    def _eventos_recebido_dia(dia):
        total = PagamentoEvento.objects.filter(
            status='pago', data_pagamento=dia,
        ).aggregate(t=Sum('valor'))['t'] or 0
        return float(total)

    def _total_recebido_dia(self, dia, empresa=None, eventos_habilitado=True):
        ifood_total, _ = self._canal_dia('ifood', dia, empresa)
        pdv_total, _   = self._canal_dia('pdv', dia, empresa)
        eventos_total = self._eventos_recebido_dia(dia) if eventos_habilitado else 0.0
        return ifood_total + pdv_total + eventos_total

    # ── Repasse iFood a receber (empresas não-matriz, ex: MANGAIO) ─────────

    @staticmethod
    def _repasse_ifood_a_receber(empresa=None):
        from financeiro.models import ContaReceber

        qs = ContaReceber.objects.filter(canal='ifood', status__in=['pendente', 'parcial'])
        if empresa is not None:
            qs = qs.filter(empresa=empresa)
        total = qs.aggregate(t=Sum(F('valor') - F('valor_recebido')))['t'] or 0
        return float(total)

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
    def _fila_operacional(empresa=None):
        qs = PedidoUnificado.objects.all()
        if empresa is not None:
            qs = qs.filter(empresa=empresa)
        return {
            'pendente':   qs.filter(status__in=['pendente', 'confirmado']).count(),
            'em_preparo': qs.filter(status='em_preparo').count(),
            'pronto':     qs.filter(status='pronto').count(),
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

    @staticmethod
    def _estoque_vazio():
        # Estoque é mono-empresa (sem FK própria, ver MULTIEMPRESA.md) — visão de
        # uma empresa não-matriz não tem estoque próprio pra mostrar.
        return {'itens_abaixo_minimo': 0, 'insumos': [], 'produtos': []}

    # ── Ticket médio (últimos 30 dias) ─────────────────────────────────────

    @staticmethod
    def _ticket_medio(hoje, empresa=None, eventos_habilitado=True):
        desde = hoje - timedelta(days=30)

        def media_canal(canal):
            qs = PedidoUnificado.objects.filter(
                canal=canal, status='concluido', pedido_em__date__gte=desde,
            )
            if empresa is not None:
                qs = qs.filter(empresa=empresa)
            agg = qs.aggregate(t=Sum('total'), c=Count('id'))
            return float(agg['t'] / agg['c']) if agg['c'] else 0.0

        eventos_media = 0.0
        if eventos_habilitado:
            agg_eventos = Evento.objects.filter(
                status='entregue', atualizado_em__date__gte=desde,
            ).aggregate(t=Sum('valor_total'), c=Count('id'))
            eventos_media = float(agg_eventos['t'] / agg_eventos['c']) if agg_eventos['c'] else 0.0

        return {
            'ifood':   media_canal('ifood'),
            'pdv':     media_canal('pdv'),
            'eventos': eventos_media,
        }
