"""
Geração do PDF do orçamento com papel timbrado (marca d'água Arretado Doces).
"""
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

# ── Paleta de cores ────────────────────────────────────────────────────────────

CARAMELO  = colors.HexColor('#C07C1A')
MARROM    = colors.HexColor('#2B1A0A')
CINZA_ESC = colors.HexColor('#3D3D3D')
CINZA_MED = colors.HexColor('#6B6B6B')
CINZA_LIG = colors.HexColor('#D5D5D5')
LISTRA    = colors.HexColor('#F9F6F1')

W, H = A4
ML   = 48.0   # margem esquerda
MR   = W - 48.0
MW   = MR - ML


def gerar_pdf_orcamento(orc) -> bytes:
    content_bytes = _gerar_conteudo(orc)
    return _mesclar_timbre(content_bytes)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _brl(value) -> str:
    v = float(value or 0)
    s = f"{v:,.2f}"
    s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"R$ {s}"


def _data(d) -> str:
    if not d:
        return '—'
    if hasattr(d, 'strftime'):
        return d.strftime('%d/%m/%Y')
    try:
        y, m, day = str(d).split('-')
        return f"{day}/{m}/{y}"
    except Exception:
        return str(d)


def _draw_separator(c, y, color=None, width=0.5):
    c.setStrokeColor(color or CINZA_LIG)
    c.setLineWidth(width)
    c.line(ML, y, MR, y)


# ── Geração do conteúdo ────────────────────────────────────────────────────────

def _gerar_conteudo(orc) -> bytes:
    buf = BytesIO()
    c   = canvas.Canvas(buf, pagesize=A4)

    y = H - 38.0

    # ── Linha decorativa superior ──────────────────────────────────────────
    c.setStrokeColor(CARAMELO)
    c.setLineWidth(2.5)
    c.line(ML, y, MR, y)
    y -= 16

    # ── Cabeçalho: empresa (esquerda) + contato (direita) ─────────────────
    c.setFillColor(MARROM)
    c.setFont('Times-Bold', 19)
    c.drawString(ML, y, 'Arretado Doces')

    c.setFont('Helvetica', 8)
    c.setFillColor(CINZA_MED)
    c.drawRightString(MR, y, 'Teresina — PI')
    y -= 13

    c.setFont('Helvetica-Oblique', 8.5)
    c.setFillColor(CARAMELO)
    c.drawString(ML, y, 'Confeitaria Artesanal')

    c.setFont('Helvetica', 8)
    c.setFillColor(CINZA_MED)
    c.drawRightString(MR, y, '@arretado.doces  ·  arretado.ortex.solutions')
    y -= 16

    # ── Linha decorativa ──────────────────────────────────────────────────
    _draw_separator(c, y, CARAMELO, 1.2)
    y -= 22

    # ── Título ────────────────────────────────────────────────────────────
    c.setFillColor(MARROM)
    c.setFont('Times-Bold', 17)
    c.drawCentredString(W / 2, y, 'PROPOSTA COMERCIAL')
    y -= 14

    emitido_em  = _data(orc.criado_em.date() if hasattr(orc.criado_em, 'date') else orc.criado_em)
    valido_ate  = _data(orc.validade)
    c.setFont('Helvetica', 8.5)
    c.setFillColor(CINZA_MED)
    c.drawCentredString(W / 2, y, f'Nº {orc.numero}   ·   Emitido em: {emitido_em}   ·   Válido até: {valido_ate}')
    y -= 20

    _draw_separator(c, y)
    y -= 16

    # ── Dados cliente / evento ─────────────────────────────────────────────
    col2_x = ML + MW * 0.53

    c.setFillColor(CARAMELO)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML, y, 'SOLICITANTE')
    c.drawString(col2_x, y, 'DADOS DO EVENTO')
    y -= 13

    c.setFont('Helvetica', 9)
    c.setFillColor(CINZA_ESC)

    # Lado esquerdo — cliente
    y_left = y
    c.drawString(ML, y_left, f'Nome:      {orc.nome_cliente_display}')
    y_left -= 12
    tel = orc.telefone_display
    if tel:
        c.drawString(ML, y_left, f'Telefone:  {tel}')
        y_left -= 12

    # Lado direito — evento
    y_right = y
    if orc.tipo_evento:
        tipo_label = dict(orc.TIPO_EVENTO_CHOICES).get(orc.tipo_evento, orc.tipo_evento)
        c.drawString(col2_x, y_right, f'Tipo:            {tipo_label}')
        y_right -= 12
    if orc.data_evento:
        c.drawString(col2_x, y_right, f'Data prevista:   {_data(orc.data_evento)}')
        y_right -= 12

    y = min(y_left, y_right) - 18

    _draw_separator(c, y)
    y -= 16

    # ── Itens ─────────────────────────────────────────────────────────────
    c.setFillColor(CARAMELO)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML, y, 'ITENS DA PROPOSTA')
    y -= 12

    itens = list(orc.itens.all())
    n     = len(itens)

    # Monta dados da tabela
    table_data = [['Descrição', 'Qtd', 'Preço Unit.', 'Total']]
    for item in itens:
        nome = item.nome
        if item.observacao:
            nome += f'  ({item.observacao})'
        table_data.append([nome, str(item.quantidade), _brl(item.preco_unit), _brl(item.preco_total)])

    # Linhas de totais
    table_data.append(['', '', 'Subtotal', _brl(orc.subtotal)])
    n_sub = len(table_data) - 1  # índice da linha subtotal
    if float(orc.desconto) > 0:
        table_data.append(['', '', 'Desconto', f'− {_brl(orc.desconto)}'])
    if float(orc.taxa_entrega) > 0:
        table_data.append(['', '', 'Taxa de entrega', _brl(orc.taxa_entrega)])
    table_data.append(['', '', 'TOTAL', _brl(orc.valor_total)])
    n_total = len(table_data) - 1  # índice da linha TOTAL

    col_w = [MW * 0.50, MW * 0.10, MW * 0.20, MW * 0.20]

    # Estilos base
    cmds = [
        # Cabeçalho
        ('BACKGROUND',    (0, 0),  (-1, 0),       MARROM),
        ('TEXTCOLOR',     (0, 0),  (-1, 0),       colors.white),
        ('FONTNAME',      (0, 0),  (-1, 0),       'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0),  (-1, 0),       8),
        ('TOPPADDING',    (0, 0),  (-1, 0),       7),
        ('BOTTOMPADDING', (0, 0),  (-1, 0),       7),
        # Dados
        ('FONTNAME',      (0, 1),  (-1, n),       'Helvetica'),
        ('FONTSIZE',      (0, 1),  (-1, n),       8.5),
        ('TOPPADDING',    (0, 1),  (-1, n),       5),
        ('BOTTOMPADDING', (0, 1),  (-1, n),       5),
        # Linhas separadoras
        ('LINEBELOW',     (0, 0),  (-1, 0),       0.5, CINZA_LIG),
        ('LINEBELOW',     (0, n),  (-1, n),       0.8, CINZA_LIG),
        # Totais
        ('FONTNAME',      (2, n_sub), (-1, n_sub-1), 'Helvetica'),
        ('FONTSIZE',      (2, n_sub), (-1, -1),   8.5),
        ('TOPPADDING',    (0, n_sub), (-1, -1),   5),
        ('BOTTOMPADDING', (0, n_sub), (-1, -1),   5),
        ('FONTNAME',      (2, n_total), (-1, n_total), 'Helvetica-Bold'),
        ('FONTSIZE',      (2, n_total), (-1, n_total), 9.5),
        ('TEXTCOLOR',     (2, n_total), (-1, n_total), CARAMELO),
        # Alinhamento
        ('ALIGN',         (1, 0),  (1, -1),       'CENTER'),
        ('ALIGN',         (2, 0),  (-1, -1),      'RIGHT'),
        # Sem borda externa
        ('BOX',           (0, 0),  (-1, n),       0.3, CINZA_LIG),
    ]

    # Listras alternadas nos itens
    for i in range(1, n + 1):
        if i % 2 == 0:
            cmds.append(('BACKGROUND', (0, i), (-1, i), LISTRA))

    # Linha horizontal entre linhas de item
    for i in range(1, n):
        cmds.append(('LINEBELOW', (0, i), (-1, i), 0.3, CINZA_LIG))

    table = Table(table_data, colWidths=col_w, repeatRows=1)
    table.setStyle(TableStyle(cmds))

    tw, th = table.wrap(MW, y - 150)
    table.drawOn(c, ML, y - th)
    y -= th + 20

    # ── Observações ───────────────────────────────────────────────────────
    if orc.observacoes:
        _draw_separator(c, y)
        y -= 14

        c.setFillColor(CARAMELO)
        c.setFont('Helvetica-Bold', 7.5)
        c.drawString(ML, y, 'OBSERVAÇÕES')
        y -= 12

        c.setFont('Helvetica', 8.5)
        c.setFillColor(CINZA_ESC)
        for linha in _quebrar_texto(c, orc.observacoes, MW, 'Helvetica', 8.5):
            c.drawString(ML, y, linha)
            y -= 12
        y -= 6

    # ── Condições comerciais ──────────────────────────────────────────────
    cond_y = max(y - 10, 162)

    _draw_separator(c, cond_y + 14)

    c.setFillColor(CARAMELO)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML, cond_y, 'CONDIÇÕES COMERCIAIS')
    cond_y -= 11

    condicoes = [
        f'• Esta proposta é válida até {valido_ate}. Após esse prazo os preços poderão ser reajustados.',
        '• A confirmação do pedido está condicionada ao pagamento de um sinal de 50% do valor total.',
        '• Todo pedido é artesanal — o prazo de produção será combinado no momento da confirmação.',
        '• Cancelamentos comunicados com menos de 7 dias de antecedência não terão devolução do sinal.',
        '• Dúvidas ou ajustes: WhatsApp / Instagram @arretado.doces.',
    ]
    c.setFont('Helvetica', 7.5)
    c.setFillColor(CINZA_ESC)
    for linha in condicoes:
        c.drawString(ML, cond_y, linha)
        cond_y -= 11

    # ── Área de assinatura ────────────────────────────────────────────────
    sig_y = 98
    _draw_separator(c, sig_y + 14)

    c.setFont('Helvetica', 8)
    c.setFillColor(CINZA_MED)
    c.drawString(ML, sig_y, 'Teresina,  ____/____/________')

    mid_x   = ML + MW * 0.50 + 10
    linha_x = MR
    c.setStrokeColor(CINZA_LIG)
    c.setLineWidth(0.5)
    c.line(mid_x, sig_y, linha_x, sig_y)
    c.setFont('Helvetica', 7.5)
    c.drawCentredString((mid_x + linha_x) / 2, sig_y - 11, 'Assinatura do cliente')

    # ── Rodapé ────────────────────────────────────────────────────────────
    c.setStrokeColor(CARAMELO)
    c.setLineWidth(1.5)
    c.line(ML, 46, MR, 46)

    c.setFont('Helvetica', 7.5)
    c.setFillColor(CINZA_MED)
    c.drawCentredString(W / 2, 34,
        'Arretado Doces — Confeitaria Artesanal  ·  Teresina, PI  ·  @arretado.doces  ·  arretado.ortex.solutions')

    c.save()
    return buf.getvalue()


def _quebrar_texto(c, texto, largura_max, fonte, tamanho):
    """Quebra o texto em linhas que caibam na largura máxima."""
    palavras = texto.split()
    linhas   = []
    linha    = ''
    for palavra in palavras:
        teste = (linha + ' ' + palavra).strip()
        if c.stringWidth(teste, fonte, tamanho) <= largura_max:
            linha = teste
        else:
            if linha:
                linhas.append(linha)
            linha = palavra
    if linha:
        linhas.append(linha)
    return linhas


# ── Mesclagem com timbre ───────────────────────────────────────────────────────

def _mesclar_timbre(content_bytes: bytes) -> bytes:
    try:
        from pypdf import PdfWriter, PdfReader
    except ImportError:
        return content_bytes

    import os
    from django.conf import settings

    timbre_path = str(getattr(settings, 'TIMBRE_PDF_PATH', ''))
    if not timbre_path or not os.path.exists(timbre_path):
        return content_bytes

    watermark = PdfReader(timbre_path)
    content   = PdfReader(BytesIO(content_bytes))
    writer    = PdfWriter()

    for content_page in content.pages:
        # Adiciona página do timbre como base e mescla conteúdo por cima
        writer.add_page(watermark.pages[0])
        bg = writer.pages[-1]
        bg.merge_page(content_page)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()
