import io
from datetime import date, timedelta

from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import views
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from ifood.models import PedidoIFood


class CsrfExemptMixin:
    authentication_classes = []


class RelatorioIFoodView(CsrfExemptMixin, views.APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        params = request.query_params
        formato = params.get('formato', 'json')
        agrupamento = params.get('agrupamento', 'dia')

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
