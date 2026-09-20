import io
import unicodedata
from datetime import date, timedelta

from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import views
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from empresas.models import Empresa
from ifood.models import PedidoIFood, ItemPedidoIFood
from pdv.models import ItemPedidoPDV, Produto
from eventos.models import Evento, ItemEvento
from usuarios.authentication import TokenAuthentication


class CsrfExemptMixin:
    authentication_classes = []


def _resolver_empresa(request):
    """
    Fase 5 do multi-empresa: mesmo contrato de dashboard/views.py::_resolver_empresa
    (duplicado a propósito — ver CLAUDE.md, "não importa função privada de outro app").
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


def _normalizar_nome(nome):
    """Chave de agrupamento sem acento/caixa — nenhum canal garante FK pra
    pdv.Produto (ItemPedidoIFood nunca tem), então o agrupamento entre canais
    é sempre por texto do nome do item, nunca por catálogo."""
    n = unicodedata.normalize('NFKD', nome or '').encode('ascii', 'ignore').decode('ascii')
    return ' '.join(n.strip().lower().split())


class RelatorioIFoodView(CsrfExemptMixin, views.APIView):
    """
    Fase 5 do multi-empresa: aceita ?empresa=<id>/?empresa=todas (default:
    empresa_ativa do usuário autenticado, senão Empresa.get_padrao()) — mesmo
    padrão de dashboard/resumo/.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        params = request.query_params
        formato = params.get('formato', 'json')
        agrupamento = params.get('agrupamento', 'dia')
        empresa = _resolver_empresa(request)

        hoje = timezone.localtime(timezone.now()).date()
        try:
            data_inicio = date.fromisoformat(params['data_inicio']) if params.get('data_inicio') else hoje - timedelta(days=29)
        except ValueError:
            data_inicio = hoje - timedelta(days=29)
        try:
            data_fim = date.fromisoformat(params['data_fim']) if params.get('data_fim') else hoje
        except ValueError:
            data_fim = hoje

        if data_inicio > data_fim:
            data_inicio, data_fim = data_fim, data_inicio

        qs = PedidoIFood.objects.filter(
            ifood_criado_em__date__gte=data_inicio,
            ifood_criado_em__date__lte=data_fim,
        )
        if empresa is not None:
            qs = qs.filter(empresa=empresa)

        resumo = self._calc_resumo(qs)
        agrupado = self._calc_agrupado(qs, agrupamento)

        dados = {
            'periodo': {'inicio': str(data_inicio), 'fim': str(data_fim)},
            'agrupamento': agrupamento,
            'resumo': resumo,
            'agrupado': agrupado,
        }

        if formato == 'excel':
            return self._export_excel(dados)
        if formato == 'pdf':
            return self._export_pdf(dados)

        return Response(dados)

    # ──────────────────────────────────────────────────────────────────────────

    def _calc_resumo(self, qs):
        agg = qs.aggregate(
            total=Count('id'),
            receita=Sum('total_valor'),
            cancelados=Count('id', filter=Q(status='CANCELLED')),
            delivery=Count('id', filter=Q(order_type='DELIVERY')),
            takeout=Count('id', filter=Q(order_type='TAKEOUT')),
            indoor=Count('id', filter=Q(order_type='INDOOR')),
        )
        total = agg['total'] or 0
        receita = float(agg['receita'] or 0)
        cancelados = agg['cancelados'] or 0
        nao_cancelados = total - cancelados
        ticket = receita / nao_cancelados if nao_cancelados else 0
        return {
            'total_pedidos': total,
            'receita_total': round(receita, 2),
            'ticket_medio': round(ticket, 2),
            'cancelados': cancelados,
            'taxa_cancelamento': round(cancelados / total * 100, 1) if total else 0,
            'delivery': agg['delivery'] or 0,
            'takeout': agg['takeout'] or 0,
            'indoor': agg['indoor'] or 0,
        }

    def _calc_agrupado(self, qs, agrupamento):
        trunc_fn = TruncMonth('ifood_criado_em') if agrupamento == 'mes' else TruncDate('ifood_criado_em')

        rows = (
            qs
            .annotate(periodo=trunc_fn)
            .values('periodo')
            .annotate(
                pedidos=Count('id'),
                receita=Sum('total_valor'),
                cancelados=Count('id', filter=Q(status='CANCELLED')),
            )
            .order_by('periodo')
        )

        result = []
        for row in rows:
            total = row['pedidos'] or 0
            receita = float(row['receita'] or 0)
            cancelados = row['cancelados'] or 0
            nao_cancelados = total - cancelados
            ticket = receita / nao_cancelados if nao_cancelados else 0

            p = row['periodo']
            if hasattr(p, 'date'):
                p = p.date()

            label = p.strftime('%b/%Y') if agrupamento == 'mes' else p.strftime('%d/%m/%Y')

            result.append({
                'periodo': str(p),
                'label': label,
                'pedidos': total,
                'receita': round(receita, 2),
                'cancelados': cancelados,
                'ticket_medio': round(ticket, 2),
            })

        return result

    # ──────────────────────────────────────────────────────────────────────────

    def _export_excel(self, dados):
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment

        CARAMELO = 'C97A3A'
        CINZA    = 'F5F5F5'

        def hfont(): return Font(bold=True, color='FFFFFF', size=11)
        def hfill(): return PatternFill('solid', fgColor=CARAMELO)
        def center(): return Alignment(horizontal='center', vertical='center')
        def tfont(): return Font(bold=True, color='FFFFFF')

        wb = openpyxl.Workbook()

        # ── Sheet 1: Resumo ────────────────────────────────────────────────────
        ws1 = wb.active
        ws1.title = 'Resumo'

        ws1.merge_cells('A1:B1')
        t = ws1['A1']
        t.value = (
            f'Relatório iFood  —  '
            f'{dados["periodo"]["inicio"]} a {dados["periodo"]["fim"]}'
        )
        t.font = Font(bold=True, size=13, color=CARAMELO)
        t.alignment = center()
        ws1.row_dimensions[1].height = 28
        ws1.append([])

        r = dados['resumo']
        summary = [
            ('Total de Pedidos',    r['total_pedidos']),
            ('Receita Total (R$)',  r['receita_total']),
            ('Ticket Médio (R$)',   r['ticket_medio']),
            ('Cancelados',         r['cancelados']),
            ('Taxa de Cancelamento', f'{r["taxa_cancelamento"]}%'),
            ('Delivery',           r['delivery']),
            ('Retirada (Takeout)', r['takeout']),
        ]

        ws1.append(['Indicador', 'Valor'])
        hr = ws1.max_row
        for col in range(1, 3):
            c = ws1.cell(hr, col)
            c.font, c.fill, c.alignment = hfont(), hfill(), center()

        for i, (label, val) in enumerate(summary, 1):
            ws1.append([label, val])
            rn = ws1.max_row
            ws1.cell(rn, 1).alignment = Alignment(horizontal='left', vertical='center')
            ws1.cell(rn, 2).alignment = Alignment(horizontal='right', vertical='center')
            if i % 2 == 0:
                for col in range(1, 3):
                    ws1.cell(rn, col).fill = PatternFill('solid', fgColor=CINZA)

        ws1.column_dimensions['A'].width = 28
        ws1.column_dimensions['B'].width = 20

        # ── Sheet 2: Por Período ───────────────────────────────────────────────
        ws2 = wb.create_sheet('Por Período')
        agrup = 'Mês' if dados['agrupamento'] == 'mes' else 'Data'
        headers = [agrup, 'Pedidos', 'Receita (R$)', 'Cancelados', 'Ticket Médio (R$)']
        ws2.append(headers)
        hr2 = ws2.max_row
        for col in range(1, len(headers) + 1):
            c = ws2.cell(hr2, col)
            c.font, c.fill, c.alignment = hfont(), hfill(), center()

        for i, row in enumerate(dados['agrupado'], 1):
            ws2.append([row['label'], row['pedidos'], row['receita'], row['cancelados'], row['ticket_medio']])
            rn = ws2.max_row
            ws2.cell(rn, 3).number_format = '#,##0.00'
            ws2.cell(rn, 5).number_format = '#,##0.00'
            if i % 2 == 0:
                for col in range(1, len(headers) + 1):
                    ws2.cell(rn, col).fill = PatternFill('solid', fgColor=CINZA)

        if dados['agrupado']:
            tp = sum(x['pedidos']    for x in dados['agrupado'])
            tr = sum(x['receita']    for x in dados['agrupado'])
            tc = sum(x['cancelados'] for x in dados['agrupado'])
            nc = tp - tc
            tkt = tr / nc if nc else 0
            ws2.append(['TOTAL', tp, round(tr, 2), tc, round(tkt, 2)])
            rn = ws2.max_row
            for col in range(1, len(headers) + 1):
                c = ws2.cell(rn, col)
                c.font, c.fill, c.alignment = tfont(), hfill(), center()
            ws2.cell(rn, 3).number_format = '#,##0.00'
            ws2.cell(rn, 5).number_format = '#,##0.00'

        for w, col in zip([18, 12, 18, 14, 20], 'ABCDE'):
            ws2.column_dimensions[col].width = w
        ws2.auto_filter.ref = f'A1:E{ws2.max_row}'

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        fname = f'relatorio_ifood_{dados["periodo"]["inicio"]}_{dados["periodo"]["fim"]}.xlsx'
        response = HttpResponse(buf, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{fname}"'
        return response

    # ──────────────────────────────────────────────────────────────────────────

    def _export_pdf(self, dados):
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle,
                Paragraph, Spacer, HRFlowable,
            )
        except ImportError:
            return HttpResponse(
                'Dependência reportlab não instalada. Execute: pip install reportlab',
                status=500,
            )

        CARAMELO = colors.HexColor('#C97A3A')
        CINZA    = colors.HexColor('#F5F5F5')
        CINZA_BD = colors.HexColor('#E7E5E4')

        title_s  = ParagraphStyle('t',  fontName='Helvetica-Bold', fontSize=15, textColor=CARAMELO, alignment=TA_CENTER, spaceAfter=4)
        sub_s    = ParagraphStyle('s',  fontName='Helvetica',      fontSize=9,  textColor=colors.grey, alignment=TA_CENTER, spaceAfter=10)
        sec_s    = ParagraphStyle('sc', fontName='Helvetica-Bold', fontSize=11, textColor=CARAMELO, spaceBefore=14, spaceAfter=6)
        footer_s = ParagraphStyle('f',  fontName='Helvetica',      fontSize=7,  textColor=colors.grey, alignment=TA_RIGHT)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)

        story = []
        story.append(Paragraph('Arretado Doces — Relatório Consolidado iFood', title_s))
        agrup_txt = 'Mensal' if dados['agrupamento'] == 'mes' else 'Diário'
        story.append(Paragraph(
            f'Período: {dados["periodo"]["inicio"]} a {dados["periodo"]["fim"]} &nbsp;|&nbsp; Agrupamento: {agrup_txt}',
            sub_s,
        ))
        story.append(HRFlowable(width='100%', thickness=2, color=CARAMELO, spaceAfter=8))

        # Resumo
        story.append(Paragraph('Resumo do Período', sec_s))
        r = dados['resumo']
        resumo_rows = [
            ['Indicador', 'Valor'],
            ['Total de Pedidos',         str(r['total_pedidos'])],
            ['Receita Total',            f'R$ {r["receita_total"]:.2f}'],
            ['Ticket Médio',             f'R$ {r["ticket_medio"]:.2f}'],
            ['Pedidos Cancelados',       f'{r["cancelados"]} ({r["taxa_cancelamento"]}%)'],
            ['Delivery',                 str(r['delivery'])],
            ['Retirada (Takeout)',       str(r['takeout'])],
        ]
        t_resumo = Table(resumo_rows, colWidths=[9*cm, 6*cm])
        t_resumo.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), CARAMELO),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
            ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0), (-1, 0), 10),
            ('FONTSIZE',     (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, CINZA]),
            ('GRID',         (0, 0), (-1, -1), 0.5, CINZA_BD),
            ('LEFTPADDING',  (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING',   (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
            ('ALIGN',        (1, 0), (1, -1), 'RIGHT'),
        ]))
        story.append(t_resumo)

        # Detalhamento
        story.append(Paragraph('Detalhamento por Período', sec_s))
        agrup_col = 'Mês' if dados['agrupamento'] == 'mes' else 'Data'
        det_rows = [[agrup_col, 'Pedidos', 'Receita (R$)', 'Cancelados', 'Ticket Médio']]
        for row in dados['agrupado']:
            det_rows.append([
                row['label'],
                str(row['pedidos']),
                f'R$ {row["receita"]:.2f}',
                str(row['cancelados']),
                f'R$ {row["ticket_medio"]:.2f}',
            ])

        if dados['agrupado']:
            tp = sum(x['pedidos']    for x in dados['agrupado'])
            tr = sum(x['receita']    for x in dados['agrupado'])
            tc = sum(x['cancelados'] for x in dados['agrupado'])
            nc = tp - tc
            tkt = tr / nc if nc else 0
            det_rows.append(['TOTAL', str(tp), f'R$ {tr:.2f}', str(tc), f'R$ {tkt:.2f}'])

        last = len(det_rows) - 1
        t_det = Table(det_rows, colWidths=[3.5*cm, 2.5*cm, 4*cm, 2.5*cm, 4*cm])
        ts = [
            ('BACKGROUND',   (0, 0),    (-1, 0),    CARAMELO),
            ('TEXTCOLOR',    (0, 0),    (-1, 0),    colors.white),
            ('FONTNAME',     (0, 0),    (-1, 0),    'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0),    (-1, 0),    9),
            ('FONTSIZE',     (0, 1),    (-1, -1),   8),
            ('ALIGN',        (0, 0),    (-1, -1),   'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, last - 1), [colors.white, CINZA]),
            ('GRID',         (0, 0),    (-1, -1),   0.5, CINZA_BD),
            ('TOPPADDING',   (0, 0),    (-1, -1),   4),
            ('BOTTOMPADDING',(0, 0),    (-1, -1),   4),
        ]
        if len(det_rows) > 1:
            ts += [
                ('BACKGROUND', (0, last), (-1, last), CARAMELO),
                ('TEXTCOLOR',  (0, last), (-1, last), colors.white),
                ('FONTNAME',   (0, last), (-1, last), 'Helvetica-Bold'),
            ]
        t_det.setStyle(TableStyle(ts))
        story.append(t_det)

        story.append(Spacer(1, 0.5*cm))
        story.append(HRFlowable(width='100%', thickness=1, color=CINZA_BD))
        story.append(Paragraph(
            f'Gerado em {timezone.now().strftime("%d/%m/%Y às %H:%M")} — Arretado Doces CRM',
            footer_s,
        ))

        doc.build(story)
        buf.seek(0)

        fname = f'relatorio_ifood_{dados["periodo"]["inicio"]}_{dados["periodo"]["fim"]}.pdf'
        response = HttpResponse(buf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{fname}"'
        return response


class RelatorioEventosView(CsrfExemptMixin, views.APIView):
    """
    Lista de Eventos num período + resumo (ver CLAUDE.md — pendência de
    expandir relatório de canal pra Eventos/Orçamentos, parte de Eventos).
    Eventos é mono-empresa (sem FK própria) — só retorna dado quando a
    empresa resolvida é a matriz ou 'todas' (mesma regra de
    ProdutosMaisVendidosView/dashboard). Filtra por Evento.data_evento (não
    criado_em). "Valor recebido" é sempre Evento.sinal_pago (campo já
    derivado via recalcular_sinal_pago(), nunca Evento.valor_total nem soma
    ao vivo de PagamentoEvento aqui).
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        params = request.query_params
        formato = params.get('formato', 'json')
        agrupamento = params.get('agrupamento', 'dia')
        empresa = _resolver_empresa(request)

        hoje = timezone.localtime(timezone.now()).date()
        try:
            data_inicio = date.fromisoformat(params['data_inicio']) if params.get('data_inicio') else hoje - timedelta(days=29)
        except ValueError:
            data_inicio = hoje - timedelta(days=29)
        try:
            data_fim = date.fromisoformat(params['data_fim']) if params.get('data_fim') else hoje
        except ValueError:
            data_fim = hoje

        if data_inicio > data_fim:
            data_inicio, data_fim = data_fim, data_inicio

        mono_empresa_habilitado = empresa is None or empresa.padrao
        if mono_empresa_habilitado:
            qs = Evento.objects.select_related('cliente').filter(
                data_evento__gte=data_inicio,
                data_evento__lte=data_fim,
            ).order_by('data_evento', 'numero')
        else:
            qs = Evento.objects.none()

        resumo = self._calc_resumo(qs)
        agrupado = self._calc_agrupado(qs, agrupamento)
        eventos = self._listar_eventos(qs)

        dados = {
            'periodo': {'inicio': str(data_inicio), 'fim': str(data_fim)},
            'agrupamento': agrupamento,
            'resumo': resumo,
            'agrupado': agrupado,
            'eventos': eventos,
        }

        if formato == 'excel':
            return self._export_excel(dados)
        if formato == 'pdf':
            return self._export_pdf(dados)

        return Response(dados)

    # ──────────────────────────────────────────────────────────────────────────

    def _listar_eventos(self, qs):
        result = []
        for e in qs:
            valor_total = float(e.valor_total or 0)
            recebido = float(e.sinal_pago or 0)
            result.append({
                'id': e.id,
                'numero': e.numero,
                'cliente': e.nome_cliente_display,
                'data_evento': str(e.data_evento),
                'data_evento_label': e.data_evento.strftime('%d/%m/%Y') if e.data_evento else '',
                'status': e.status,
                'status_label': e.get_status_display(),
                'valor_total': round(valor_total, 2),
                'valor_recebido': round(recebido, 2),
                'saldo': round(max(valor_total - recebido, 0), 2),
            })
        return result

    def _calc_resumo(self, qs):
        agg = qs.aggregate(
            total=Count('id'),
            valor_total=Sum('valor_total'),
            valor_recebido=Sum('sinal_pago'),
            cancelados=Count('id', filter=Q(status='cancelado')),
        )
        total = agg['total'] or 0
        valor_total = float(agg['valor_total'] or 0)
        valor_recebido = float(agg['valor_recebido'] or 0)
        return {
            'total_eventos': total,
            'valor_total': round(valor_total, 2),
            'valor_recebido': round(valor_recebido, 2),
            'saldo_a_receber': round(max(valor_total - valor_recebido, 0), 2),
            'ticket_medio': round(valor_total / total, 2) if total else 0,
            'cancelados': agg['cancelados'] or 0,
        }

    def _calc_agrupado(self, qs, agrupamento):
        trunc_fn = TruncMonth('data_evento') if agrupamento == 'mes' else TruncDate('data_evento')

        rows = (
            qs
            .annotate(periodo=trunc_fn)
            .values('periodo')
            .annotate(
                eventos=Count('id'),
                valor_total=Sum('valor_total'),
                valor_recebido=Sum('sinal_pago'),
            )
            .order_by('periodo')
        )

        result = []
        for row in rows:
            p = row['periodo']
            if hasattr(p, 'date'):
                p = p.date()
            label = p.strftime('%b/%Y') if agrupamento == 'mes' else p.strftime('%d/%m/%Y')

            valor_total = float(row['valor_total'] or 0)
            valor_recebido = float(row['valor_recebido'] or 0)
            result.append({
                'periodo': str(p),
                'label': label,
                'eventos': row['eventos'] or 0,
                'valor_total': round(valor_total, 2),
                'valor_recebido': round(valor_recebido, 2),
                'saldo': round(max(valor_total - valor_recebido, 0), 2),
            })

        return result

    # ──────────────────────────────────────────────────────────────────────────

    def _export_excel(self, dados):
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment

        CARAMELO = 'C97A3A'
        CINZA    = 'F5F5F5'

        def hfont(): return Font(bold=True, color='FFFFFF', size=11)
        def hfill(): return PatternFill('solid', fgColor=CARAMELO)
        def center(): return Alignment(horizontal='center', vertical='center')
        def tfont(): return Font(bold=True, color='FFFFFF')

        wb = openpyxl.Workbook()

        # ── Sheet 1: Resumo ────────────────────────────────────────────────────
        ws1 = wb.active
        ws1.title = 'Resumo'

        ws1.merge_cells('A1:B1')
        t = ws1['A1']
        t.value = (
            f'Relatório de Eventos  —  '
            f'{dados["periodo"]["inicio"]} a {dados["periodo"]["fim"]}'
        )
        t.font = Font(bold=True, size=13, color=CARAMELO)
        t.alignment = center()
        ws1.row_dimensions[1].height = 28
        ws1.append([])

        r = dados['resumo']
        summary = [
            ('Total de Eventos',      r['total_eventos']),
            ('Valor Total (R$)',      r['valor_total']),
            ('Valor Recebido (R$)',   r['valor_recebido']),
            ('Saldo a Receber (R$)',  r['saldo_a_receber']),
            ('Ticket Médio (R$)',     r['ticket_medio']),
            ('Cancelados',            r['cancelados']),
        ]

        ws1.append(['Indicador', 'Valor'])
        hr = ws1.max_row
        for col in range(1, 3):
            c = ws1.cell(hr, col)
            c.font, c.fill, c.alignment = hfont(), hfill(), center()

        for i, (label, val) in enumerate(summary, 1):
            ws1.append([label, val])
            rn = ws1.max_row
            ws1.cell(rn, 1).alignment = Alignment(horizontal='left', vertical='center')
            ws1.cell(rn, 2).alignment = Alignment(horizontal='right', vertical='center')
            if i % 2 == 0:
                for col in range(1, 3):
                    ws1.cell(rn, col).fill = PatternFill('solid', fgColor=CINZA)

        ws1.column_dimensions['A'].width = 28
        ws1.column_dimensions['B'].width = 20

        # ── Sheet 2: Por Período ───────────────────────────────────────────────
        ws2 = wb.create_sheet('Por Período')
        agrup = 'Mês' if dados['agrupamento'] == 'mes' else 'Data'
        headers2 = [agrup, 'Eventos', 'Valor Total (R$)', 'Valor Recebido (R$)', 'Saldo (R$)']
        ws2.append(headers2)
        hr2 = ws2.max_row
        for col in range(1, len(headers2) + 1):
            c = ws2.cell(hr2, col)
            c.font, c.fill, c.alignment = hfont(), hfill(), center()

        for i, row in enumerate(dados['agrupado'], 1):
            ws2.append([row['label'], row['eventos'], row['valor_total'], row['valor_recebido'], row['saldo']])
            rn = ws2.max_row
            for col in (3, 4, 5):
                ws2.cell(rn, col).number_format = '#,##0.00'
            if i % 2 == 0:
                for col in range(1, len(headers2) + 1):
                    ws2.cell(rn, col).fill = PatternFill('solid', fgColor=CINZA)

        if dados['agrupado']:
            te = sum(x['eventos']         for x in dados['agrupado'])
            tt = sum(x['valor_total']     for x in dados['agrupado'])
            tr = sum(x['valor_recebido']  for x in dados['agrupado'])
            ts = sum(x['saldo']           for x in dados['agrupado'])
            ws2.append(['TOTAL', te, round(tt, 2), round(tr, 2), round(ts, 2)])
            rn = ws2.max_row
            for col in range(1, len(headers2) + 1):
                c = ws2.cell(rn, col)
                c.font, c.fill, c.alignment = tfont(), hfill(), center()
            for col in (3, 4, 5):
                ws2.cell(rn, col).number_format = '#,##0.00'

        for w, col in zip([18, 12, 18, 20, 16], 'ABCDE'):
            ws2.column_dimensions[col].width = w
        ws2.auto_filter.ref = f'A1:E{ws2.max_row}'

        # ── Sheet 3: Eventos ────────────────────────────────────────────────────
        ws3 = wb.create_sheet('Eventos')
        headers3 = ['Evento', 'Cliente', 'Data', 'Status', 'Valor Total (R$)', 'Valor Recebido (R$)', 'Saldo (R$)']
        ws3.append(headers3)
        hr3 = ws3.max_row
        for col in range(1, len(headers3) + 1):
            c = ws3.cell(hr3, col)
            c.font, c.fill, c.alignment = hfont(), hfill(), center()

        for i, e in enumerate(dados['eventos'], 1):
            ws3.append([
                e['numero'], e['cliente'], e['data_evento_label'], e['status_label'],
                e['valor_total'], e['valor_recebido'], e['saldo'],
            ])
            rn = ws3.max_row
            for col in (5, 6, 7):
                ws3.cell(rn, col).number_format = '#,##0.00'
            if i % 2 == 0:
                for col in range(1, len(headers3) + 1):
                    ws3.cell(rn, col).fill = PatternFill('solid', fgColor=CINZA)

        for w, col in zip([14, 26, 12, 14, 18, 20, 16], 'ABCDEFG'):
            ws3.column_dimensions[col].width = w
        ws3.auto_filter.ref = f'A1:G{ws3.max_row}'

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        fname = f'relatorio_eventos_{dados["periodo"]["inicio"]}_{dados["periodo"]["fim"]}.xlsx'
        response = HttpResponse(buf, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{fname}"'
        return response

    # ──────────────────────────────────────────────────────────────────────────

    def _export_pdf(self, dados):
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle,
                Paragraph, Spacer, HRFlowable,
            )
        except ImportError:
            return HttpResponse(
                'Dependência reportlab não instalada. Execute: pip install reportlab',
                status=500,
            )

        CARAMELO = colors.HexColor('#C97A3A')
        CINZA    = colors.HexColor('#F5F5F5')
        CINZA_BD = colors.HexColor('#E7E5E4')

        title_s  = ParagraphStyle('t',  fontName='Helvetica-Bold', fontSize=15, textColor=CARAMELO, alignment=TA_CENTER, spaceAfter=4)
        sub_s    = ParagraphStyle('s',  fontName='Helvetica',      fontSize=9,  textColor=colors.grey, alignment=TA_CENTER, spaceAfter=10)
        sec_s    = ParagraphStyle('sc', fontName='Helvetica-Bold', fontSize=11, textColor=CARAMELO, spaceBefore=14, spaceAfter=6)
        footer_s = ParagraphStyle('f',  fontName='Helvetica',      fontSize=7,  textColor=colors.grey, alignment=TA_RIGHT)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)

        story = []
        story.append(Paragraph('Arretado Doces — Relatório de Eventos', title_s))
        agrup_txt = 'Mensal' if dados['agrupamento'] == 'mes' else 'Diário'
        story.append(Paragraph(
            f'Período: {dados["periodo"]["inicio"]} a {dados["periodo"]["fim"]} &nbsp;|&nbsp; Agrupamento: {agrup_txt}',
            sub_s,
        ))
        story.append(HRFlowable(width='100%', thickness=2, color=CARAMELO, spaceAfter=8))

        # Resumo
        story.append(Paragraph('Resumo do Período', sec_s))
        r = dados['resumo']
        resumo_rows = [
            ['Indicador', 'Valor'],
            ['Total de Eventos',    str(r['total_eventos'])],
            ['Valor Total',         f'R$ {r["valor_total"]:.2f}'],
            ['Valor Recebido',      f'R$ {r["valor_recebido"]:.2f}'],
            ['Saldo a Receber',     f'R$ {r["saldo_a_receber"]:.2f}'],
            ['Ticket Médio',        f'R$ {r["ticket_medio"]:.2f}'],
            ['Cancelados',          str(r['cancelados'])],
        ]
        t_resumo = Table(resumo_rows, colWidths=[9*cm, 6*cm])
        t_resumo.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), CARAMELO),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
            ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0), (-1, 0), 10),
            ('FONTSIZE',     (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, CINZA]),
            ('GRID',         (0, 0), (-1, -1), 0.5, CINZA_BD),
            ('LEFTPADDING',  (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING',   (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
            ('ALIGN',        (1, 0), (1, -1), 'RIGHT'),
        ]))
        story.append(t_resumo)

        # Por Período
        story.append(Paragraph('Por Período', sec_s))
        agrup_col = 'Mês' if dados['agrupamento'] == 'mes' else 'Data'
        per_rows = [[agrup_col, 'Eventos', 'Valor Total (R$)', 'Valor Recebido (R$)', 'Saldo (R$)']]
        for row in dados['agrupado']:
            per_rows.append([
                row['label'], str(row['eventos']),
                f'{row["valor_total"]:.2f}', f'{row["valor_recebido"]:.2f}', f'{row["saldo"]:.2f}',
            ])
        if dados['agrupado']:
            te = sum(x['eventos']        for x in dados['agrupado'])
            tt = sum(x['valor_total']    for x in dados['agrupado'])
            tr = sum(x['valor_recebido'] for x in dados['agrupado'])
            tsl = sum(x['saldo']         for x in dados['agrupado'])
            per_rows.append(['TOTAL', str(te), f'{tt:.2f}', f'{tr:.2f}', f'{tsl:.2f}'])

        last_per = len(per_rows) - 1
        t_per = Table(per_rows, colWidths=[3.5*cm, 2.5*cm, 3.5*cm, 3.5*cm, 3*cm])
        ts_per = [
            ('BACKGROUND',   (0, 0),  (-1, 0),  CARAMELO),
            ('TEXTCOLOR',    (0, 0),  (-1, 0),  colors.white),
            ('FONTNAME',     (0, 0),  (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0),  (-1, 0),  9),
            ('FONTSIZE',     (0, 1),  (-1, -1), 8),
            ('ALIGN',        (0, 0),  (-1, -1), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, last_per - 1), [colors.white, CINZA]),
            ('GRID',         (0, 0),  (-1, -1), 0.5, CINZA_BD),
            ('TOPPADDING',   (0, 0),  (-1, -1), 4),
            ('BOTTOMPADDING',(0, 0),  (-1, -1), 4),
        ]
        if len(per_rows) > 1:
            ts_per += [
                ('BACKGROUND', (0, last_per), (-1, last_per), CARAMELO),
                ('TEXTCOLOR',  (0, last_per), (-1, last_per), colors.white),
                ('FONTNAME',   (0, last_per), (-1, last_per), 'Helvetica-Bold'),
            ]
        t_per.setStyle(TableStyle(ts_per))
        story.append(t_per)

        # Lista de Eventos
        story.append(Paragraph('Lista de Eventos', sec_s))
        ev_rows = [['Evento', 'Cliente', 'Data', 'Status', 'Valor Total', 'Recebido', 'Saldo']]
        for e in dados['eventos']:
            ev_rows.append([
                e['numero'], e['cliente'], e['data_evento_label'], e['status_label'],
                f'{e["valor_total"]:.2f}', f'{e["valor_recebido"]:.2f}', f'{e["saldo"]:.2f}',
            ])

        t_ev = Table(ev_rows, colWidths=[2.2*cm, 4.3*cm, 2.2*cm, 2.3*cm, 2.6*cm, 2.4*cm, 2*cm], repeatRows=1)
        t_ev.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), CARAMELO),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
            ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0), (-1, 0), 8),
            ('FONTSIZE',     (0, 1), (-1, -1), 7.5),
            ('ALIGN',        (2, 0), (-1, -1), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, CINZA]),
            ('GRID',         (0, 0), (-1, -1), 0.5, CINZA_BD),
            ('TOPPADDING',   (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
        ]))
        story.append(t_ev)

        story.append(Spacer(1, 0.5*cm))
        story.append(HRFlowable(width='100%', thickness=1, color=CINZA_BD))
        story.append(Paragraph(
            f'Gerado em {timezone.now().strftime("%d/%m/%Y às %H:%M")} — Arretado Doces CRM',
            footer_s,
        ))

        doc.build(story)
        buf.seek(0)

        fname = f'relatorio_eventos_{dados["periodo"]["inicio"]}_{dados["periodo"]["fim"]}.pdf'
        response = HttpResponse(buf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{fname}"'
        return response


CANAIS_VALIDOS = ('ifood', 'pdv', 'eventos')


class ProdutosMaisVendidosView(CsrfExemptMixin, views.APIView):
    """
    Ranking de produtos mais vendidos, consolidando iFood + PDV + Eventos.

    Só considera pedido/evento que representa venda de fato concretizada:
    iFood status=CONCLUDED, PDV status confirmado/em_preparo/pronto/concluido
    (exclui aberto/cancelado), Evento status=entregue. Orçamentos ficam de
    fora de propósito — são cotação, não venda fechada. Itens de PDV/Eventos
    com natureza='brinde'/'permuta' (ver BRINDES_PERMUTAS.md, Fase 2) também
    ficam de fora — não são venda; iFood não tem esse conceito (campo não
    existe em ItemPedidoIFood), então não há o que filtrar ali.

    Fase 5 do multi-empresa: aceita ?empresa=<id>/?empresa=todas (mesmo default
    dos demais endpoints Fase 5). iFood filtra por `pedido__empresa`; PDV/Eventos
    são mono-empresa (sem FK própria) e só entram na soma quando a empresa
    resolvida é a matriz ou 'todas'.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        params = request.query_params
        hoje = timezone.localtime(timezone.now()).date()
        try:
            data_inicio = date.fromisoformat(params['data_inicio']) if params.get('data_inicio') else hoje - timedelta(days=29)
        except ValueError:
            data_inicio = hoje - timedelta(days=29)
        try:
            data_fim = date.fromisoformat(params['data_fim']) if params.get('data_fim') else hoje
        except ValueError:
            data_fim = hoje
        if data_inicio > data_fim:
            data_inicio, data_fim = data_fim, data_inicio

        canais = [c for c in params.getlist('canal') if c in CANAIS_VALIDOS] or list(CANAIS_VALIDOS)

        ordenar = params.get('ordenar', 'quantidade')
        if ordenar not in ('quantidade', 'valor'):
            ordenar = 'quantidade'

        try:
            limit = int(params.get('limit', 30))
        except (TypeError, ValueError):
            limit = 30
        limit = max(1, min(limit, 200))

        empresa = _resolver_empresa(request)
        mono_empresa_habilitado = empresa is None or empresa.padrao

        agregados = {}
        if 'ifood' in canais:
            self._somar(agregados, 'ifood', self._qs_ifood(data_inicio, data_fim, empresa))
        if 'pdv' in canais and mono_empresa_habilitado:
            self._somar(agregados, 'pdv', self._qs_pdv(data_inicio, data_fim))
        if 'eventos' in canais and mono_empresa_habilitado:
            self._somar(agregados, 'eventos', self._qs_eventos(data_inicio, data_fim))

        produtos = []
        for item in agregados.values():
            quantidade_total = sum(c['quantidade'] for c in item['canais'].values())
            valor_total = sum(c['valor'] for c in item['canais'].values())
            produtos.append({
                'nome': item['nome'],
                'quantidade_total': quantidade_total,
                'valor_total': round(valor_total, 2),
                'canais': {
                    canal: {'quantidade': v['quantidade'], 'valor': round(v['valor'], 2)}
                    for canal, v in item['canais'].items()
                },
            })

        produtos.sort(
            key=lambda p: p['quantidade_total'] if ordenar == 'quantidade' else p['valor_total'],
            reverse=True,
        )

        resumo = {
            'produtos_distintos': len(produtos),
            'quantidade_total': sum(p['quantidade_total'] for p in produtos),
            'valor_total': round(sum(p['valor_total'] for p in produtos), 2),
        }

        return Response({
            'periodo': {'inicio': str(data_inicio), 'fim': str(data_fim)},
            'canais': canais,
            'ordenar': ordenar,
            'resumo': resumo,
            'produtos': produtos[:limit],
        })

    # ── Querysets por canal ──────────────────────────────────────────────

    def _qs_ifood(self, data_inicio, data_fim, empresa=None):
        qs = ItemPedidoIFood.objects.filter(
            pedido__status='CONCLUDED',
            pedido__ifood_criado_em__date__gte=data_inicio,
            pedido__ifood_criado_em__date__lte=data_fim,
        )
        if empresa is not None:
            qs = qs.filter(pedido__empresa=empresa)
        return qs.values('nome').annotate(quantidade=Sum('quantidade'), valor=Sum('preco_total'))

    def _qs_pdv(self, data_inicio, data_fim):
        return (
            ItemPedidoPDV.objects
            .filter(
                pedido__status__in=['confirmado', 'em_preparo', 'pronto', 'concluido'],
                pedido__criado_em__date__gte=data_inicio,
                pedido__criado_em__date__lte=data_fim,
                natureza='venda',
            )
            .values('nome')
            .annotate(quantidade=Sum('quantidade'), valor=Sum('preco_total'))
        )

    def _qs_eventos(self, data_inicio, data_fim):
        return (
            ItemEvento.objects
            .filter(
                evento__status='entregue',
                evento__data_evento__gte=data_inicio,
                evento__data_evento__lte=data_fim,
                natureza='venda',
            )
            .values('nome')
            .annotate(quantidade=Sum('quantidade'), valor=Sum('preco_total'))
        )

    # ── Merge cross-canal por nome normalizado ────────────────────────────

    def _somar(self, agregados, canal, qs):
        for row in qs:
            nome = row['nome'] or '(sem nome)'
            chave = _normalizar_nome(nome)
            if chave not in agregados:
                agregados[chave] = {'nome': nome, 'canais': {}}
            bucket = agregados[chave]['canais'].setdefault(canal, {'quantidade': 0, 'valor': 0.0})
            bucket['quantidade'] += row['quantidade'] or 0
            bucket['valor'] += float(row['valor'] or 0)


def _fmt_estoque(valor):
    """Remove zeros à direita do DecimalField(3 casas) sem cair em notação científica."""
    texto = f'{valor:.3f}'.rstrip('0').rstrip('.')
    return texto or '0'


class RelatorioCatalogoView(CsrfExemptMixin, views.APIView):
    """
    Catálogo de produtos (pdv.Produto) com preço e saldo de estoque atual —
    vive no menu Catálogo (Catalogo.jsx), não em Relatorios.jsx.
    `quantidade_estoque` é campo denormalizado do próprio Produto (mantido só
    via estoque.MovimentoEstoque.registrar(), ver CLAUDE.md) — lido direto,
    nunca somado do ledger aqui. Mesmos filtros de ProdutoViewSet.get_queryset
    (duplicado a propósito — ver _resolver_empresa acima) pra o export bater
    com o que está em tela.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        params = request.query_params
        formato = params.get('formato', 'json')

        qs = Produto.objects.select_related('categoria').all()

        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(nome__icontains=search) | Q(descricao__icontains=search))

        categoria = params.get('categoria')
        if categoria:
            qs = qs.filter(categoria_id=categoria)

        ativo = params.get('ativo')
        if ativo == 'true':
            qs = qs.filter(ativo=True)
        elif ativo == 'false':
            qs = qs.filter(ativo=False)

        tipo = params.get('tipo')
        if tipo:
            qs = qs.filter(tipo=tipo)

        qs = qs.order_by('categoria__ordem', 'nome')

        produtos = [
            {
                'nome': p.nome,
                'categoria': p.categoria.nome if p.categoria_id else '— sem categoria —',
                'tipo': p.get_tipo_display(),
                'preco': float(p.preco),
                'quantidade_estoque': float(p.quantidade_estoque),
                'ativo': p.ativo,
            }
            for p in qs
        ]

        dados = {
            'gerado_em': timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M'),
            'total_produtos': len(produtos),
            'produtos': produtos,
        }

        if formato == 'excel':
            return self._export_excel(dados)
        if formato == 'pdf':
            return self._export_pdf(dados)

        return Response(dados)

    # ──────────────────────────────────────────────────────────────────────────

    def _export_excel(self, dados):
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment

        CARAMELO = 'C97A3A'
        CINZA    = 'F5F5F5'

        def hfont(): return Font(bold=True, color='FFFFFF', size=11)
        def hfill(): return PatternFill('solid', fgColor=CARAMELO)
        def center(): return Alignment(horizontal='center', vertical='center')

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Catálogo'

        headers = ['Produto', 'Categoria', 'Tipo', 'Preço (R$)', 'Estoque']

        ws.merge_cells(f'A1:{chr(64 + len(headers))}1')
        t = ws['A1']
        t.value = f'Catálogo de Produtos — Arretado Doces  ({dados["total_produtos"]} produtos)'
        t.font = Font(bold=True, size=13, color=CARAMELO)
        t.alignment = center()
        ws.row_dimensions[1].height = 28
        ws.append([])

        ws.append(headers)
        hr = ws.max_row
        for col in range(1, len(headers) + 1):
            c = ws.cell(hr, col)
            c.font, c.fill, c.alignment = hfont(), hfill(), center()

        for i, p in enumerate(dados['produtos'], 1):
            ws.append([p['nome'], p['categoria'], p['tipo'], p['preco'], p['quantidade_estoque']])
            rn = ws.max_row
            ws.cell(rn, 4).number_format = '#,##0.00'
            ws.cell(rn, 5).number_format = '#,##0.###'
            if i % 2 == 0:
                for col in range(1, len(headers) + 1):
                    ws.cell(rn, col).fill = PatternFill('solid', fgColor=CINZA)

        for w, col in zip([32, 20, 14, 14, 12], 'ABCDE'):
            ws.column_dimensions[col].width = w
        ws.auto_filter.ref = f'A{hr}:E{ws.max_row}'

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        fname = f'catalogo_produtos_{timezone.localtime(timezone.now()).strftime("%Y%m%d")}.xlsx'
        response = HttpResponse(buf, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{fname}"'
        return response

    # ──────────────────────────────────────────────────────────────────────────

    def _export_pdf(self, dados):
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle,
                Paragraph, Spacer, HRFlowable,
            )
        except ImportError:
            return HttpResponse(
                'Dependência reportlab não instalada. Execute: pip install reportlab',
                status=500,
            )

        CARAMELO = colors.HexColor('#C97A3A')
        CINZA    = colors.HexColor('#F5F5F5')
        CINZA_BD = colors.HexColor('#E7E5E4')

        title_s  = ParagraphStyle('t',  fontName='Helvetica-Bold', fontSize=15, textColor=CARAMELO, alignment=TA_CENTER, spaceAfter=4)
        sub_s    = ParagraphStyle('s',  fontName='Helvetica',      fontSize=9,  textColor=colors.grey, alignment=TA_CENTER, spaceAfter=10)
        footer_s = ParagraphStyle('f',  fontName='Helvetica',      fontSize=7,  textColor=colors.grey, alignment=TA_RIGHT)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)

        story = []
        story.append(Paragraph('Arretado Doces — Catálogo de Produtos', title_s))
        story.append(Paragraph(f'{dados["total_produtos"]} produtos', sub_s))
        story.append(HRFlowable(width='100%', thickness=2, color=CARAMELO, spaceAfter=8))

        rows = [['Produto', 'Categoria', 'Tipo', 'Preço', 'Estoque']]
        for p in dados['produtos']:
            rows.append([
                p['nome'], p['categoria'], p['tipo'],
                f'R$ {p["preco"]:.2f}', _fmt_estoque(p['quantidade_estoque']),
            ])

        t = Table(rows, colWidths=[6.5*cm, 4*cm, 2.5*cm, 2.7*cm, 2.3*cm], repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), CARAMELO),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
            ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0), (-1, 0), 9),
            ('FONTSIZE',     (0, 1), (-1, -1), 8),
            ('ALIGN',        (3, 0), (-1, -1), 'RIGHT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, CINZA]),
            ('GRID',         (0, 0), (-1, -1), 0.5, CINZA_BD),
            ('TOPPADDING',   (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 4),
        ]))
        story.append(t)

        story.append(Spacer(1, 0.5*cm))
        story.append(HRFlowable(width='100%', thickness=1, color=CINZA_BD))
        story.append(Paragraph(
            f'Gerado em {timezone.now().strftime("%d/%m/%Y às %H:%M")} — Arretado Doces CRM',
            footer_s,
        ))

        doc.build(story)
        buf.seek(0)

        fname = f'catalogo_produtos_{timezone.localtime(timezone.now()).strftime("%Y%m%d")}.pdf'
        response = HttpResponse(buf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{fname}"'
        return response
