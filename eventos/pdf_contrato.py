"""
Geração do PDF do Contrato de Aquisição de Produtos, com papel timbrado
(mesmo padrão de pdf_orcamento.py). Nenhum número/prazo/percentual é
hardcoded aqui — tudo vem de ConfiguracaoContrato.get() ou do snapshot
gravado no próprio Contrato (ver Contrato.md).
"""
from io import BytesIO
from functools import partial

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
)

# ── Paleta de cores (mesma de pdf_orcamento.py) ────────────────────────────────

CARAMELO  = colors.HexColor('#C07C1A')
MARROM    = colors.HexColor('#2B1A0A')
CINZA_ESC = colors.HexColor('#3D3D3D')
CINZA_MED = colors.HexColor('#6B6B6B')
CINZA_LIG = colors.HexColor('#D5D5D5')
LISTRA    = colors.HexColor('#F9F6F1')

W, H = A4
ML   = 48.0
MR   = W - 48.0
MW   = MR - ML

MESES = [
    '', 'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
]


def gerar_pdf_contrato(contrato) -> bytes:
    content_bytes = _gerar_conteudo(contrato)
    return _mesclar_timbre(content_bytes)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _brl(value) -> str:
    v = float(value or 0)
    s = f"{v:,.2f}"
    s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"R$ {s}"


def _data(d) -> str:
    if not d:
        return '____/____/________'
    if hasattr(d, 'strftime'):
        return d.strftime('%d/%m/%Y')
    try:
        y, m, day = str(d).split('-')
        return f"{day}/{m}/{y}"
    except Exception:
        return str(d)


def _data_extenso(d) -> str:
    if not d:
        return '_____ de _______________ de 20____'
    return f'{d.day:02d} de {MESES[d.month]} de {d.year}'


def _pct(value) -> str:
    v = float(value or 0)
    s = f'{v:.2f}'.rstrip('0').rstrip('.')
    return s


def _hora(h) -> str:
    if not h:
        return 'horário a combinar'
    if hasattr(h, 'strftime'):
        return h.strftime('%Hh%M')
    return str(h)


# ── Estilos ────────────────────────────────────────────────────────────────────

def _estilos():
    return {
        'titulo': ParagraphStyle(
            'titulo', fontName='Times-Bold', fontSize=14, textColor=MARROM,
            alignment=TA_CENTER, spaceAfter=14,
        ),
        'secao': ParagraphStyle(
            'secao', fontName='Helvetica-Bold', fontSize=9.5, textColor=CARAMELO,
            spaceBefore=12, spaceAfter=5,
        ),
        'clausula': ParagraphStyle(
            'clausula', fontName='Helvetica', fontSize=8.8, textColor=CINZA_ESC,
            alignment=TA_JUSTIFY, leading=12.5, spaceAfter=5,
        ),
        'assinatura_label': ParagraphStyle(
            'assinatura_label', fontName='Helvetica', fontSize=8, textColor=CINZA_MED,
            alignment=TA_CENTER,
        ),
    }


# ── Cabeçalho / rodapé (repetido em toda página) ───────────────────────────────

def _header_footer(c, doc, cfg):
    c.saveState()

    y = H - 38
    c.setStrokeColor(CARAMELO)
    c.setLineWidth(2.2)
    c.line(ML, y, MR, y)
    y -= 15

    c.setFillColor(MARROM)
    c.setFont('Times-Bold', 13)
    c.drawString(ML, y, cfg.razao_social_contratada or 'Arretado Doces')

    c.setFont('Helvetica', 7.5)
    c.setFillColor(CINZA_MED)
    c.drawRightString(MR, y, f'{cfg.foro_comarca} — {cfg.foro_estado}')
    y -= 10

    c.setStrokeColor(CARAMELO)
    c.setLineWidth(0.8)
    c.line(ML, y, MR, y)

    c.setStrokeColor(CARAMELO)
    c.setLineWidth(1.2)
    c.line(ML, 46, MR, 46)
    c.setFont('Helvetica', 7)
    c.setFillColor(CINZA_MED)
    c.drawString(ML, 34, f'{cfg.razao_social_contratada} — CNPJ {cfg.cnpj_contratada}')
    c.drawRightString(MR, 34, f'Página {doc.page}')

    contato = ' — '.join(filter(None, [cfg.instagram_contratada, cfg.telefone_contratada]))
    if contato:
        c.drawString(ML, 24, contato)

    c.restoreState()


# ── Geração do conteúdo ────────────────────────────────────────────────────────

def _gerar_conteudo(contrato) -> bytes:
    from .models import ConfiguracaoContrato

    cfg = ConfiguracaoContrato.get()
    st  = _estilos()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=ML, rightMargin=W - MR,
        topMargin=68, bottomMargin=64,
    )

    story = []

    story.append(Paragraph(
        f'CONTRATO DE AQUISIÇÃO DE PRODUTOS – {(cfg.razao_social_contratada or "Arretado Doces").upper()}',
        st['titulo'],
    ))

    # ── 1. Identificação das partes ────────────────────────────────────────
    story.append(Paragraph('1. IDENTIFICAÇÃO DAS PARTES', st['secao']))

    identidade = contrato.contratante_rg or '____________________'
    if contrato.contratante_rg_orgao_emissor:
        identidade += f' {contrato.contratante_rg_orgao_emissor}'

    story.append(Paragraph(
        f'<b>CONTRATANTE:</b> {contrato.contratante_nome}, nacionalidade '
        f'{contrato.contratante_nacionalidade or "—"}, profissão {contrato.contratante_profissao or "—"}, '
        f'identidade {identidade}, CPF {contrato.contratante_cpf}, residente e domiciliado(a) na '
        f'{contrato.contratante_endereco}.',
        st['clausula'],
    ))
    story.append(Paragraph(
        f'<b>CONTRATADO:</b> {cfg.razao_social_contratada}, pessoa jurídica com sede na '
        f'{cfg.endereco_contratada}, inscrita no CNPJ sob o nº {cfg.cnpj_contratada}, neste ato '
        f'representada por {cfg.representante_nome}, {cfg.representante_nacionalidade}, '
        f'{cfg.representante_estado_civil}, {cfg.representante_profissao}, Carteira de Identidade nº '
        f'{cfg.representante_rg}, CPF nº {cfg.representante_cpf}, residente e domiciliado na '
        f'{cfg.representante_endereco}.',
        st['clausula'],
    ))

    # ── 2. Do objeto ────────────────────────────────────────────────────────
    story.append(Paragraph('2. DO OBJETO DO CONTRATO', st['secao']))
    story.append(Paragraph(
        f'<b>Cláusula 1ª:</b> É objeto do presente o fornecimento de gêneros alimentícios da empresa '
        f'{cfg.razao_social_contratada}, em evento que se realizará na data {_data(contrato.data_evento)}, '
        f'às {_hora(contrato.hora_evento)}, no local: {contrato.local_evento or "a definir"}.',
        st['clausula'],
    ))
    story.append(Paragraph(
        'Parágrafo único: O objeto do contrato consta especificado no Anexo 1 (nota de pedidos), devendo '
        'ocorrer a entrega e organização no horário acima, no local apontado na Cláusula 1ª pela parte '
        'CONTRATANTE.',
        st['clausula'],
    ))

    # ── 3. Obrigações da CONTRATANTE ────────────────────────────────────────
    story.append(Paragraph('3. OBRIGAÇÕES DA CONTRATANTE', st['secao']))
    story.append(Paragraph(
        '<b>Cláusula 2ª:</b> A CONTRATANTE deverá fornecer ao CONTRATADO, no ato da assinatura ou em até '
        '48 (quarenta e oito) horas após, todas as informações necessárias sobre o seu evento (data, local '
        'e horário), sob pena de não ser garantida a disponibilidade para a data pretendida.',
        st['clausula'],
    ))
    story.append(Paragraph(
        '<b>Cláusula 3ª:</b> A CONTRATANTE deverá efetuar o pagamento na forma e condições estabelecidas '
        'na Cláusula 6ª e seus parágrafos.',
        st['clausula'],
    ))
    story.append(Paragraph(
        f'<b>Cláusula 4ª:</b> A CONTRATANTE deverá entregar ao CONTRATADO os materiais de personalização '
        f'(caixetas, tags e derivados) no prazo MÁXIMO de {cfg.prazo_personalizacao_dias} dias anteriores '
        f'à data do evento fixada na Cláusula 1ª.',
        st['clausula'],
    ))

    # ── 4. Obrigações do CONTRATADO ─────────────────────────────────────────
    story.append(Paragraph('4. OBRIGAÇÕES DO CONTRATADO', st['secao']))
    story.append(Paragraph(
        '<b>Cláusula 5ª:</b> O CONTRATADO deverá fornecer à CONTRATANTE todas as informações necessárias '
        'sobre o gênero alimentício a ser fornecido, uma vez solicitado pela CONTRATANTE.',
        st['clausula'],
    ))
    story.append(Paragraph(
        '<b>Cláusula 6ª:</b> O CONTRATADO se compromete a fornecer os gêneros alimentícios à CONTRATANTE, '
        'conforme descrito no Anexo 1 e acordado entre as partes.',
        st['clausula'],
    ))
    story.append(Paragraph(
        'Parágrafo único: O CONTRATADO não se responsabiliza por danos à conservação dos produtos '
        'decorrentes de condições inadequadas de armazenamento ou climatização após a entrega e '
        'conferência pela CONTRATANTE, nos termos da Cláusula 16ª. Eventuais vícios de qualidade dos '
        'produtos devem ser apontados no ato da entrega, mediante anotação no comprovante de recebimento.',
        st['clausula'],
    ))

    # ── 5. Do preço e das condições de pagamento ────────────────────────────
    story.append(Paragraph('5. DO PREÇO E DAS CONDIÇÕES DE PAGAMENTO', st['secao']))
    story.append(Paragraph(
        f'<b>Cláusula 7ª:</b> O fornecimento dos gêneros alimentícios, nos quantitativos descritos no '
        f'Anexo 1, somam o valor total de {_brl(contrato.valor_total)}.',
        st['clausula'],
    ))
    story.append(Paragraph(
        f'Parágrafo único: Para a confirmação do pedido e entrega na data marcada, a CONTRATANTE deverá '
        f'efetuar o pagamento de um sinal correspondente a {_pct(contrato.percentual_sinal)}% do valor total do '
        f'contrato, no valor de {_brl(contrato.valor_sinal)}, no ato da sua assinatura.',
        st['clausula'],
    ))
    story.append(Paragraph(
        '<b>Cláusula 8ª:</b> O valor referido na Cláusula 7ª já contempla as despesas com frete, conforme '
        'especificado no Anexo 1.',
        st['clausula'],
    ))
    story.append(Paragraph(
        f'<b>Cláusula 9ª:</b> A CONTRATANTE deverá adimplir o contrato em sua totalidade até '
        f'{cfg.prazo_quitacao_dias} dias antes da data do evento, ou seja, até {_data(contrato.data_quitacao)}.',
        st['clausula'],
    ))
    story.append(Paragraph(
        f'Parágrafo único: No caso do inadimplemento do contrato no prazo estabelecido na Cláusula 9ª, o '
        f'CONTRATADO poderá estabelecer multa no valor de {_pct(cfg.multa_inadimplencia_pct)}% do valor total do '
        f'contrato, ficando ainda sujeito ao pagamento de juros moratórios de {_pct(cfg.juros_mora_pct_mes)}% ao '
        f'mês e correção monetária pelo IPCA, contados da data do vencimento.',
        st['clausula'],
    ))

    # ── 6. Da rescisão ──────────────────────────────────────────────────────
    story.append(Paragraph('6. DA RESCISÃO', st['secao']))
    story.append(Paragraph(
        f'<b>Cláusula 10ª:</b> O presente contrato poderá ser rescindido unilateralmente por qualquer uma '
        f'das partes, desde que haja comunicação prévia com antecedência mínima de '
        f'{cfg.prazo_aviso_rescisao_dias} dias corridos da data do evento, por escrito, via e-mail ou '
        f'aplicativo de mensagem com confirmação de leitura, acarretando os ônus previstos neste instrumento.',
        st['clausula'],
    ))
    story.append(Paragraph(
        '<b>Cláusula 11ª:</b> Na hipótese de rescisão unilateral do presente contrato por iniciativa da '
        'CONTRATANTE, será devida multa compensatória calculada conforme a antecedência da comunicação de '
        'rescisão em relação à data do evento, destinada a compensar custos administrativos, reserva de '
        'agenda, bloqueio de data e despesas incorridas:',
        st['clausula'],
    ))

    tabela_rescisao = [
        ['Antecedência da comunicação', 'Multa sobre o valor total do contrato'],
        ['Acima de 60 dias',                              f'{_pct(cfg.multa_rescisao_acima_60_dias_pct)}%'],
        ['Entre 30 e 60 dias',                             f'{_pct(cfg.multa_rescisao_30_60_dias_pct)}%'],
        ['Menos de 30 dias',                               f'{_pct(cfg.multa_rescisao_abaixo_30_dias_pct)}%'],
        ['Menos de 7 dias ou após início da produção',     f'{_pct(cfg.multa_rescisao_abaixo_7_dias_pct)}%'],
    ]
    t = Table(tabela_rescisao, colWidths=[MW * 0.68, MW * 0.32])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), MARROM),
        ('TEXTCOLOR',     (0, 0), (-1, 0), colors.white),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8.3),
        ('ALIGN',         (1, 0), (1, -1), 'CENTER'),
        ('GRID',          (0, 0), (-1, -1), 0.4, CINZA_LIG),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LISTRA]),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(Spacer(1, 3))
    story.append(t)
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        'Parágrafo 1º: A multa prevista nesta cláusula é limitada ao montante já pago pela CONTRATANTE até '
        'a data da rescisão. Caso a soma dos valores pagos exceda o valor devido a título de multa e '
        'eventuais itens já executados ou entregues, o saldo remanescente será devolvido à CONTRATANTE em '
        f'até {cfg.prazo_devolucao_dias} dias úteis.',
        st['clausula'],
    ))
    story.append(Paragraph(
        'Parágrafo 2º: Itens já produzidos, personalizados ou comprovadamente executados até a data da '
        'rescisão poderão ser cobrados/retidos proporcionalmente, conforme orçamento de produção e '
        'comprovação do estágio de execução, abatendo-se tais valores do montante a devolver.',
        st['clausula'],
    ))
    story.append(Paragraph(
        f'<b>Cláusula 12ª:</b> No caso de rescisão unilateral por parte do CONTRATADO, haverá devolução '
        f'integral dos valores já quitados pela CONTRATANTE, no prazo de {cfg.prazo_devolucao_dias} dias '
        f'corridos.',
        st['clausula'],
    ))
    story.append(Paragraph(
        '<b>Cláusula 13ª:</b> No caso de rescisão bilateral, as partes formalizarão Termo de Distrato, no '
        'qual serão definidos os valores a reter, a devolver e os respectivos prazos, observando como '
        'parâmetro mínimo a retenção proporcional aos itens já produzidos ou insumos adquiridos pelo '
        'CONTRATADO até a data do distrato.',
        st['clausula'],
    ))
    story.append(Paragraph(
        '<b>Cláusula 14ª:</b> Em caso de cancelamento do evento por motivo de força maior ou caso fortuito '
        'devidamente comprovado por documentação idônea (conforme art. 393 do Código Civil), as partes '
        'negociarão de boa-fé a retenção proporcional aos custos já incorridos pelo CONTRATADO, ficando '
        'afastada a multa compensatória prevista na Cláusula 11ª.',
        st['clausula'],
    ))

    # ── 7. Das condições gerais ─────────────────────────────────────────────
    story.append(Paragraph('7. DAS CONDIÇÕES GERAIS', st['secao']))
    story.append(Paragraph(
        '<b>Cláusula 15ª:</b> Já estão inclusas as taxas com recursos humanos e materiais, assim como os '
        'encargos fiscais, sociais, comerciais, trabalhistas e previdenciários e quaisquer outras despesas '
        'necessárias ao cumprimento das obrigações decorrentes do presente contrato.',
        st['clausula'],
    ))
    story.append(Paragraph(
        '<b>Cláusula 16ª:</b> A CONTRATANTE deverá ter um responsável para receber as mercadorias e fazer '
        'a conferência dos gêneros alimentícios quanto à integridade dos produtos, na quantidade e '
        'qualidade acordada. A ausência de apontamentos no ato da entrega implica aceitação tácita dos '
        'produtos entregues.',
        st['clausula'],
    ))
    story.append(Paragraph(
        '<b>Cláusula 17ª:</b> É de inteira responsabilidade da CONTRATANTE as condições de armazenamento e '
        'acondicionamento dos gêneros entregues após a conferência e aceite de que trata a Cláusula 16ª.',
        st['clausula'],
    ))
    story.append(Paragraph(
        f'<b>Cláusula 18ª:</b> É de inteira responsabilidade da CONTRATANTE a entrega dos materiais de '
        f'personalização (caixetas, tags e derivados) no prazo MÁXIMO de {cfg.prazo_personalizacao_dias} '
        f'dias anteriores à data do evento, não se responsabilizando o CONTRATADO pelo resultado da '
        f'personalização em caso de atraso na entrega dos referidos materiais.',
        st['clausula'],
    ))
    story.append(Paragraph(
        f'<b>Cláusula 19ª:</b> A CONTRATANTE poderá aumentar a quantidade do objeto deste contrato até '
        f'{cfg.prazo_aumento_quantidade_dias} dias antes da data do evento fixado, mediante disponibilidade '
        f'do CONTRATADO e aditivo contratual por escrito. Não será admitida redução no quantitativo após a '
        f'assinatura deste instrumento, salvo mediante acordo expresso entre as partes e eventual ajuste no '
        f'valor contratual.',
        st['clausula'],
    ))
    story.append(Paragraph(
        f'<b>Cláusula 20ª:</b> A alteração da data do evento somente será aceita mediante disponibilidade '
        f'do CONTRATADO e comunicação por escrito. Solicitações com antecedência inferior a '
        f'{cfg.prazo_aviso_rescisao_dias} dias sujeitam a CONTRATANTE à multa prevista na Cláusula 11ª, '
        f'calculada conforme a antecedência da comunicação.',
        st['clausula'],
    ))

    # ── 8. Do foro ───────────────────────────────────────────────────────────
    story.append(Paragraph('8. DO FORO', st['secao']))
    story.append(Paragraph(
        f'<b>Cláusula 21ª:</b> Para dirimir quaisquer controvérsias oriundas do presente contrato, as '
        f'partes elegem o foro da comarca de {cfg.foro_comarca}, estado do {cfg.foro_estado}. Por estarem '
        f'assim justos e contratados, firmam o presente instrumento, em duas vias de igual teor, '
        f'juntamente com 1 (uma) testemunha.',
        st['clausula'],
    ))

    # ── Anexo 1 — Nota de pedidos ────────────────────────────────────────────
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width='100%', thickness=1.2, color=CARAMELO, spaceAfter=8))
    story.append(Paragraph('ANEXO 1 — NOTA DE PEDIDOS', st['secao']))

    # Contrato emitido a partir de Evento (dados podem ter divergido do
    # orçamento original após a conversão) lê os itens/agregados do Evento;
    # senão, do Orçamento — ver CLAUDE.md ("Não criar ItemContrato").
    fonte = contrato.evento if contrato.evento_id else contrato.orcamento
    itens = list(fonte.itens.all())
    n     = len(itens)

    table_data = [['Descrição', 'Qtd', 'Preço Unit.', 'Total']]
    for item in itens:
        nome = item.nome
        if item.observacao:
            nome += f'  ({item.observacao})'
        table_data.append([nome, str(item.quantidade), _brl(item.preco_unit), _brl(item.preco_total)])

    table_data.append(['', '', 'Subtotal', _brl(fonte.subtotal)])
    n_sub = len(table_data) - 1
    if float(fonte.desconto) > 0:
        table_data.append(['', '', 'Desconto', f'− {_brl(fonte.desconto)}'])
    if float(fonte.taxa_entrega) > 0:
        table_data.append(['', '', 'Taxa de entrega', _brl(fonte.taxa_entrega)])
    table_data.append(['', '', 'TOTAL', _brl(fonte.valor_total)])
    n_total = len(table_data) - 1

    col_w = [MW * 0.50, MW * 0.10, MW * 0.20, MW * 0.20]
    cmds = [
        ('BACKGROUND',    (0, 0), (-1, 0), MARROM),
        ('TEXTCOLOR',     (0, 0), (-1, 0), colors.white),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0), 8),
        ('FONTNAME',      (0, 1), (-1, n), 'Helvetica'),
        ('FONTSIZE',      (0, 1), (-1, n), 8.3),
        ('LINEBELOW',     (0, 0), (-1, 0), 0.5, CINZA_LIG),
        ('LINEBELOW',     (0, n), (-1, n), 0.8, CINZA_LIG),
        ('FONTSIZE',      (2, n_sub), (-1, -1), 8.3),
        ('FONTNAME',      (2, n_total), (-1, n_total), 'Helvetica-Bold'),
        ('TEXTCOLOR',     (2, n_total), (-1, n_total), CARAMELO),
        ('ALIGN',         (1, 0), (1, -1), 'CENTER'),
        ('ALIGN',         (2, 0), (-1, -1), 'RIGHT'),
        ('GRID',          (0, 0), (-1, n), 0.3, CINZA_LIG),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]
    for i in range(1, n + 1):
        if i % 2 == 0:
            cmds.append(('BACKGROUND', (0, i), (-1, i), LISTRA))

    tabela_itens = Table(table_data, colWidths=col_w, repeatRows=1)
    tabela_itens.setStyle(TableStyle(cmds))
    story.append(tabela_itens)

    # ── Assinaturas ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 26))
    story.append(Paragraph(
        f'{cfg.foro_comarca}, {_data_extenso(contrato.criado_em.date() if hasattr(contrato.criado_em, "date") else contrato.criado_em)}.',
        st['assinatura_label'],
    ))
    story.append(Spacer(1, 34))

    assinaturas = Table(
        [
            ['_' * 40, '_' * 40],
            ['CONTRATANTE', f'{cfg.razao_social_contratada}\n{cfg.representante_nome}'],
        ],
        colWidths=[MW * 0.48, MW * 0.48],
    )
    assinaturas.setStyle(TableStyle([
        ('ALIGN',    (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica'),
        ('TEXTCOLOR',(0, 0), (-1, 0), CINZA_LIG),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, 1), 8),
        ('TEXTCOLOR',(0, 1), (-1, 1), CINZA_MED),
        ('TOPPADDING', (0, 1), (-1, 1), 4),
    ]))
    story.append(assinaturas)

    story.append(Spacer(1, 26))
    story.append(Paragraph('_' * 40, st['assinatura_label']))
    story.append(Paragraph('Testemunha — Nome / CPF', st['assinatura_label']))

    hf = partial(_header_footer, cfg=cfg)
    doc.build(story, onFirstPage=hf, onLaterPages=hf)

    return buf.getvalue()


# ── Mesclagem com timbre ────────────────────────────────────────────────────────
# Nota: diferente de pdf_orcamento.py (sempre 1 página), o contrato pode ter
# várias páginas. Reler o timbre a cada iteração evita que o pypdf reutilize o
# mesmo stream de conteúdo do watermark entre páginas (o que faria todas as
# páginas finais mostrarem o conteúdo mesclado/acumulado da última iteração).

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

    content = PdfReader(BytesIO(content_bytes))
    writer  = PdfWriter()

    for content_page in content.pages:
        watermark = PdfReader(timbre_path)
        writer.add_page(watermark.pages[0])
        bg = writer.pages[-1]
        bg.merge_page(content_page)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()
