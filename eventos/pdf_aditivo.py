"""
Geração do PDF do Termo Aditivo ao Contrato de Aquisição de Produtos — emitido
quando o Evento (já com Contrato emitido) tem seus valores/itens alterados a
pedido do cliente antes do evento acontecer (ver Contrato.md). Reaproveita a
identidade visual e os helpers de pdf_contrato.py (mesmo papel timbrado,
mesma paleta) — nunca duplicar esse estilo aqui.

AditivoContrato é snapshot: todo o conteúdo abaixo vem só dos campos gravados
no próprio aditivo (itens_snapshot, valor_total_anterior/novo etc.), nunca
relido do Evento/Contrato ao vivo — reimprimir o mesmo aditivo depois de uma
nova alteração no Evento tem que mostrar exatamente o que valia naquele
momento (ver CLAUDE.md sobre snapshots).
"""
from functools import partial

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable

from .pdf_contrato import (
    CARAMELO, MARROM, CINZA_ESC, CINZA_MED, CINZA_LIG, LISTRA,
    ML, MR, MW, W, H, ESTILO_PRECO_RISCADO,
    _brl, _data, _data_extenso, _estilos, _header_footer, _mesclar_timbre,
)


def gerar_pdf_aditivo(aditivo) -> bytes:
    content_bytes = _gerar_conteudo(aditivo)
    return _mesclar_timbre(content_bytes)


def _gerar_conteudo(aditivo) -> bytes:
    from io import BytesIO
    from .models import ConfiguracaoContrato

    cfg      = ConfiguracaoContrato.get()
    st       = _estilos()
    contrato = aditivo.contrato

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=ML, rightMargin=W - MR,
        topMargin=68, bottomMargin=64,
    )

    story = []

    story.append(Paragraph(
        f'TERMO ADITIVO Nº {aditivo.numero} AO CONTRATO Nº {contrato.numero}',
        st['titulo'],
    ))

    story.append(Paragraph(
        f'Pelo presente termo, as partes já qualificadas no Contrato de Aquisição de Produtos '
        f'nº {contrato.numero}, firmado em {_data(contrato.criado_em.date() if hasattr(contrato.criado_em, "date") else contrato.criado_em)} '
        f'entre {contrato.contratante_nome} (CONTRATANTE) e {cfg.razao_social_contratada} (CONTRATADO), '
        f'resolvem aditar o instrumento original conforme as cláusulas abaixo, permanecendo em '
        f'pleno vigor todas as demais condições do contrato original não alteradas por este termo.',
        st['clausula'],
    ))

    story.append(Paragraph('1. DO MOTIVO', st['secao']))
    story.append(Paragraph(
        '<b>Cláusula 1ª:</b> O presente aditivo decorre de alteração solicitada pela CONTRATANTE nos '
        'itens/quantitativos do pedido originalmente contratado, conforme detalhado no Anexo deste '
        'termo.',
        st['clausula'],
    ))

    story.append(Paragraph('2. DO NOVO VALOR', st['secao']))
    story.append(Paragraph(
        f'<b>Cláusula 2ª:</b> Em razão da alteração referida na Cláusula 1ª, o valor total do '
        f'fornecimento passa de {_brl(aditivo.valor_total_anterior)} para <b>{_brl(aditivo.valor_total_novo)}</b>, '
        f'conforme o novo detalhamento constante do Anexo deste termo, que passa a substituir o Anexo 1 '
        f'do contrato original para todos os efeitos.',
        st['clausula'],
    ))
    if aditivo.valor_total_novo > aditivo.valor_total_anterior:
        story.append(Paragraph(
            f'Parágrafo único: A diferença de {_brl(aditivo.diferenca)} decorrente deste aditivo segue as '
            f'mesmas condições de pagamento e prazos já estabelecidos no contrato original (Cláusula 7ª '
            f'e seguintes), salvo se de outra forma acordado por escrito entre as partes.',
            st['clausula'],
        ))

    story.append(Paragraph('3. DAS DEMAIS CONDIÇÕES', st['secao']))
    story.append(Paragraph(
        '<b>Cláusula 3ª:</b> Permanecem inalteradas e em pleno vigor todas as demais cláusulas do '
        'contrato original, inclusive as relativas a prazos, rescisão, multas e foro, no que não '
        'contrariarem o disposto neste termo aditivo.',
        st['clausula'],
    ))

    # ── Anexo — itens atualizados (snapshot, nunca lido ao vivo do Evento) ──
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width='100%', thickness=1.2, color=CARAMELO, spaceAfter=8))
    story.append(Paragraph('ANEXO — ITENS ATUALIZADOS', st['secao']))

    itens = aditivo.itens_snapshot or []
    n     = len(itens)

    table_data = [['Descrição', 'Qtd', 'Preço Unit.', 'Total']]
    for item in itens:
        nome = item.get('nome', '')
        if item.get('natureza') != 'venda':
            rotulo = {'brinde': 'Brinde', 'permuta': 'Permuta'}.get(item.get('natureza'), '')
            if rotulo:
                nome += f' — {rotulo}'
        if item.get('observacao'):
            nome += f"  ({item['observacao']})"
        preco_unit_cell = (
            Paragraph(f"<strike>{_brl(item.get('preco_unit'))}</strike>", ESTILO_PRECO_RISCADO)
            if item.get('natureza') != 'venda' else _brl(item.get('preco_unit'))
        )
        table_data.append([nome, str(item.get('quantidade', '')), preco_unit_cell, _brl(item.get('preco_total'))])

    table_data.append(['', '', 'Subtotal', _brl(aditivo.subtotal_novo)])
    n_sub = len(table_data) - 1
    if float(aditivo.desconto_novo) > 0:
        table_data.append(['', '', 'Desconto', f'− {_brl(aditivo.desconto_novo)}'])
    if float(aditivo.taxa_entrega_novo) > 0:
        table_data.append(['', '', 'Taxa de entrega', _brl(aditivo.taxa_entrega_novo)])
    table_data.append(['', '', 'TOTAL', _brl(aditivo.valor_total_novo)])
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

    # ── Assinaturas (mesmo bloco de pdf_contrato.py) ────────────────────────
    story.append(Spacer(1, 26))
    story.append(Paragraph(
        f'{cfg.foro_comarca}, {_data_extenso(aditivo.criado_em.date() if hasattr(aditivo.criado_em, "date") else aditivo.criado_em)}.',
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
        ('ALIGN',     (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME',  (0, 0), (-1, 0), 'Helvetica'),
        ('TEXTCOLOR', (0, 0), (-1, 0), CINZA_LIG),
        ('FONTNAME',  (0, 1), (-1, 1), 'Helvetica'),
        ('FONTSIZE',  (0, 1), (-1, 1), 8),
        ('TEXTCOLOR', (0, 1), (-1, 1), CINZA_MED),
        ('TOPPADDING', (0, 1), (-1, 1), 4),
    ]))
    story.append(assinaturas)

    hf = partial(_header_footer, cfg=cfg)
    doc.build(story, onFirstPage=hf, onLaterPages=hf)

    return buf.getvalue()
