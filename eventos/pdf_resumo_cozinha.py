"""
Geração do PDF de Resumo de Cozinha (Evento) — documento operacional interno,
não client-facing. Sem timbre/marca d'água. Usa ReportLab Platypus (não canvas
cru como pdf_orcamento.py) porque a lista de itens tem tamanho variável e pode
quebrar página.
"""
from io import BytesIO
from functools import partial
from itertools import groupby
from xml.sax.saxutils import escape

from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)

# ── Paleta de cores (mesma de pdf_orcamento.py) ────────────────────────────────

CARAMELO  = colors.HexColor('#C07C1A')
MARROM    = colors.HexColor('#2B1A0A')
CINZA_ESC = colors.HexColor('#3D3D3D')
CINZA_MED = colors.HexColor('#6B6B6B')
CINZA_LIG = colors.HexColor('#D5D5D5')

W, H = A4
ML   = 48.0
MR   = W - 48.0
MW   = MR - ML


def gerar_pdf_resumo_cozinha(evento) -> bytes:
    return _gerar_conteudo(evento)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _data(d) -> str:
    if not d:
        return '—'
    if hasattr(d, 'strftime'):
        return d.strftime('%d/%m/%Y')
    return str(d)


def _data_hora_entrega(evento) -> str:
    data_txt = _data(evento.data_evento)
    if evento.hora_evento:
        hora_txt = (
            evento.hora_evento.strftime('%Hh%M')
            if hasattr(evento.hora_evento, 'strftime')
            else str(evento.hora_evento)
        )
        return f'{data_txt} às {hora_txt}'
    return data_txt


def _local_texto(evento) -> str:
    if evento.tipo_entrega == 'retirada_loja':
        return '<b>Entrega:</b> Retirada na loja'
    if evento.local:
        partes = [evento.local.nome, evento.local.endereco_completo]
        if evento.local.referencia:
            partes.append(evento.local.referencia)
        return '<b>Local:</b> ' + '<br/>'.join(escape(p) for p in partes if p)
    if evento.endereco_avulso:
        return f'<b>Local:</b> {escape(evento.endereco_avulso)}'
    return '<b>Local:</b> —'


def _categoria_nome(item) -> str:
    if item.produto and item.produto.categoria:
        return item.produto.categoria.nome
    return 'Outros'


# ── Estilos ────────────────────────────────────────────────────────────────────

def _estilos():
    return {
        'titulo': ParagraphStyle(
            'titulo', fontName='Times-Bold', fontSize=15, textColor=MARROM, spaceAfter=4,
        ),
        'destaque': ParagraphStyle(
            'destaque', fontName='Helvetica-Bold', fontSize=11, textColor=CARAMELO, spaceAfter=10,
        ),
        'secao': ParagraphStyle(
            'secao', fontName='Helvetica-Bold', fontSize=9, textColor=CARAMELO,
            spaceBefore=10, spaceAfter=6,
        ),
        'info': ParagraphStyle(
            'info', fontName='Helvetica', fontSize=9, textColor=CINZA_ESC, leading=13,
        ),
        'item': ParagraphStyle(
            'item', fontName='Helvetica', fontSize=8.8, textColor=CINZA_ESC, leading=11,
        ),
        'texto': ParagraphStyle(
            'texto', fontName='Helvetica', fontSize=8.8, textColor=CINZA_ESC, leading=12,
        ),
        'assinatura_label': ParagraphStyle(
            'assinatura_label', fontName='Helvetica', fontSize=8, textColor=CINZA_MED,
            alignment=TA_CENTER,
        ),
    }


# ── Cabeçalho / rodapé (repetido em toda página) ───────────────────────────────

def _header_footer(c, doc, evento):
    c.saveState()

    y = H - 38
    c.setStrokeColor(CARAMELO)
    c.setLineWidth(2.2)
    c.line(ML, y, MR, y)
    y -= 15

    c.setFillColor(MARROM)
    c.setFont('Times-Bold', 15)
    c.drawString(ML, y, 'Arretado Doces')

    c.setFont('Helvetica-Bold', 9)
    c.setFillColor(CARAMELO)
    c.drawRightString(MR, y, 'RESUMO DE COZINHA')
    y -= 12

    c.setFont('Helvetica', 8)
    c.setFillColor(CINZA_MED)
    c.drawRightString(MR, y, f'Evento {evento.numero}')
    y -= 8

    c.setStrokeColor(CARAMELO)
    c.setLineWidth(0.8)
    c.line(ML, y, MR, y)

    c.setStrokeColor(CARAMELO)
    c.setLineWidth(1.2)
    c.line(ML, 40, MR, 40)

    c.setFont('Helvetica', 7)
    c.setFillColor(CINZA_MED)
    gerado_em = timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')
    c.drawString(ML, 28, f'Gerado em {gerado_em} · Arretado Doces CRM')
    c.drawRightString(MR, 28, f'Página {doc.page}')

    c.restoreState()


# ── Tabela de itens (agrupada por categoria) ────────────────────────────────────

def _tabela_itens(evento, st):
    itens = list(
        evento.itens
        .select_related('produto__categoria')
        .order_by('produto__categoria__ordem', 'produto__categoria__nome', 'nome')
    )

    data = [['', 'Item', 'Qtd', 'Observação']]
    cmds = [
        ('BACKGROUND',    (0, 0), (-1, 0), CINZA_LIG),
        ('TEXTCOLOR',     (0, 0), (-1, 0), MARROM),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0), 8.5),
        ('TOPPADDING',    (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('ALIGN',         (2, 0), (2, 0), 'CENTER'),
        ('LINEBELOW',     (0, 0), (-1, 0), 0.6, CINZA_MED),
    ]

    row = 1
    box_rows = []
    for cat_nome, grupo in groupby(itens, key=_categoria_nome):
        data.append([cat_nome.upper(), '', '', ''])
        cmds += [
            ('SPAN',          (0, row), (-1, row)),
            ('BACKGROUND',    (0, row), (-1, row), MARROM),
            ('TEXTCOLOR',     (0, row), (-1, row), colors.white),
            ('FONTNAME',      (0, row), (-1, row), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, row), (-1, row), 8),
            ('TOPPADDING',    (0, row), (-1, row), 5),
            ('BOTTOMPADDING', (0, row), (-1, row), 5),
        ]
        row += 1

        for item in grupo:
            data.append([
                '',
                Paragraph(escape(item.nome), st['item']),
                str(item.quantidade),
                Paragraph(escape(item.observacao), st['item']) if item.observacao else '',
            ])
            box_rows.append(row)
            cmds += [
                ('ALIGN',         (2, row), (2, row), 'CENTER'),
                ('VALIGN',        (0, row), (-1, row), 'MIDDLE'),
                ('TOPPADDING',    (0, row), (-1, row), 5),
                ('BOTTOMPADDING', (0, row), (-1, row), 5),
                ('LINEBELOW',     (0, row), (-1, row), 0.3, CINZA_LIG),
            ]
            row += 1

    for r in box_rows:
        cmds.append(('BOX', (0, r), (0, r), 0.7, CINZA_MED))

    col_w = [26, MW * 0.56, 36, MW - 26 - MW * 0.56 - 36]
    table = Table(data, colWidths=col_w, repeatRows=1)
    table.setStyle(TableStyle(cmds))
    return table


def _tabela_assinatura():
    tbl = Table(
        [
            ['_' * 40, '_' * 26],
            ['Produção conferida por', 'Horário de conclusão'],
        ],
        colWidths=[MW * 0.6, MW * 0.35],
    )
    tbl.setStyle(TableStyle([
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica'),
        ('TEXTCOLOR',     (0, 0), (-1, 0), CINZA_LIG),
        ('FONTNAME',      (0, 1), (-1, 1), 'Helvetica'),
        ('FONTSIZE',      (0, 1), (-1, 1), 8),
        ('TEXTCOLOR',     (0, 1), (-1, 1), CINZA_MED),
        ('TOPPADDING',    (0, 1), (-1, 1), 4),
    ]))
    return tbl


# ── Geração do conteúdo ────────────────────────────────────────────────────────

def _gerar_conteudo(evento) -> bytes:
    st = _estilos()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=ML, rightMargin=W - MR,
        topMargin=78, bottomMargin=56,
    )

    story = []

    story.append(Paragraph(
        f'Nº {evento.numero} — {evento.get_tipo_evento_display()}', st['titulo'],
    ))
    story.append(Paragraph(_data_hora_entrega(evento), st['destaque']))

    cliente_linhas = [f'<b>Cliente:</b> {escape(evento.nome_cliente_display)}']
    telefone = evento.telefone_display
    if telefone:
        cliente_linhas.append(f'<b>Telefone:</b> {escape(telefone)}')

    info_table = Table(
        [[
            Paragraph('<br/>'.join(cliente_linhas), st['info']),
            Paragraph(_local_texto(evento), st['info']),
        ]],
        colWidths=[MW * 0.48, MW * 0.52],
    )
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph('ITENS', st['secao']))
    story.append(_tabela_itens(evento, st))

    if evento.observacoes:
        story.append(Spacer(1, 10))
        story.append(Paragraph('OBSERVAÇÕES GERAIS', st['secao']))
        obs_html = escape(evento.observacoes).replace('\n', '<br/>')
        story.append(Paragraph(obs_html, st['texto']))

    story.append(Spacer(1, 26))
    story.append(_tabela_assinatura())

    hf = partial(_header_footer, evento=evento)
    doc.build(story, onFirstPage=hf, onLaterPages=hf)

    return buf.getvalue()
