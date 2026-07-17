"""
Cascata de extração de nota fiscal (fases 6-7 do módulo de Estoque):
XML da NF-e -> texto de PDF (heurística best-effort) -> IA multimodal.

Cada camada expõe uma função `extrair_*(...)` que devolve um dict
{'numero_nota', 'fornecedor_nome', 'itens': [{'descricao','quantidade','valor_unitario'}]}
ou `None` se não conseguir extrair nada utilizável — nunca lança exceção pro
chamador (a orquestração decide se cai pra próxima camada).

A camada de texto de PDF é heurística por natureza (regex sobre o texto cru
extraído via pypdf) — sem notas fiscais reais de fornecedores da Arretado
pra calibrar, pode não reconhecer todo layout de DANFE. Quando não achar
nada com confiança razoável, devolve None e a cascata cai pra IA.
"""
import io
import logging
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


def _limpar_namespaces(root):
    """Remove o prefixo de namespace de cada tag (`{ns}tag` -> `tag`), pra
    poder fazer .find()/.findall() sem precisar declarar o namespace da
    NF-e explicitamente — resiliente a XML com/sem xmlns declarado."""
    for elem in root.iter():
        if isinstance(elem.tag, str) and '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]
    return root


def _decimal_br(texto):
    """Converte string numérica em formato BR ('1.234,56') ou já com ponto
    ('1234.56') para Decimal. Retorna None se não for um número válido."""
    if texto is None:
        return None
    texto = texto.strip()
    if ',' in texto:
        texto = texto.replace('.', '').replace(',', '.')
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        return None


def extrair_xml(nome_arquivo, conteudo_bytes):
    """Camada 1 — XML da NF-e. Determinístico: só roda se a extensão for
    .xml e o parse encontrar a estrutura infNFe/det/prod esperada."""
    if not nome_arquivo.lower().endswith('.xml'):
        return None

    try:
        root = ET.fromstring(conteudo_bytes)
    except ET.ParseError:
        return None

    root = _limpar_namespaces(root)

    det_nodes = root.findall('.//det')
    if not det_nodes:
        return None

    itens = []
    for det in det_nodes:
        prod = det.find('prod')
        if prod is None:
            continue
        descricao = (prod.findtext('xProd') or '').strip()
        quantidade = _decimal_br(prod.findtext('qCom'))
        valor_unitario = _decimal_br(prod.findtext('vUnCom'))
        if not descricao or quantidade is None or valor_unitario is None:
            continue
        itens.append({
            'descricao': descricao,
            'quantidade': quantidade,
            'valor_unitario': valor_unitario,
        })

    if not itens:
        return None

    numero_nota = (root.findtext('.//ide/nNF') or '').strip()
    fornecedor_nome = (root.findtext('.//emit/xNome') or '').strip()

    return {'numero_nota': numero_nota, 'fornecedor_nome': fornecedor_nome, 'itens': itens}


_PADRAO_NUMERO_NOTA = re.compile(r'N[ºo°]?\s*(?:DA\s+)?NF-?E?[:\s]*n?[ºo°]?\s*(\d{1,15})', re.IGNORECASE)
# Linha de item: descrição seguida de pelo menos 3 números decimais (BR ou
# com ponto) no final — os 3 últimos são interpretados como
# quantidade / valor_unitario / valor_total.
_PADRAO_NUMEROS_FINAIS = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2,4}|\d+\.\d{2,4})')


def extrair_texto_pdf(nome_arquivo, conteudo_bytes):
    """Camada 2 — texto de PDF. Heurística best-effort: extrai o texto cru
    via pypdf e tenta reconhecer linhas de item por regex. Não é um parser
    de layout de DANFE de verdade — funciona "na maioria das vezes" em PDFs
    com tabela simples; quando não reconhece nada com confiança, devolve
    None e a cascata cai pra IA."""
    if not nome_arquivo.lower().endswith('.pdf'):
        return None

    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(conteudo_bytes))
        texto = '\n'.join((page.extract_text() or '') for page in reader.pages)
    except Exception as e:
        logger.warning('Falha ao extrair texto do PDF: %s', e)
        return None

    if not texto.strip():
        return None  # PDF sem texto embutido (scan/imagem) — cai pra IA

    itens = []
    for linha in texto.splitlines():
        numeros = _PADRAO_NUMEROS_FINAIS.findall(linha)
        if len(numeros) < 3:
            continue
        qtd, vl_unit, vl_total = (_decimal_br(n) for n in numeros[-3:])
        if qtd is None or vl_unit is None or vl_total is None or qtd == 0:
            continue
        # confiança: qtd * valor_unit deve bater aproximadamente com o total
        # (tolerância de 5% pra absorver arredondamento)
        esperado = qtd * vl_unit
        if esperado == 0 or abs(esperado - vl_total) / esperado > Decimal('0.05'):
            continue
        # descrição = texto antes do primeiro número da linha, sem código
        # numérico de item/EAN no começo
        pos_primeiro_numero = linha.find(numeros[0])
        descricao = linha[:pos_primeiro_numero].strip()
        descricao = re.sub(r'^\d+\s*', '', descricao).strip()
        if not descricao:
            continue
        itens.append({'descricao': descricao, 'quantidade': qtd, 'valor_unitario': vl_unit})

    if not itens:
        return None

    match_numero = _PADRAO_NUMERO_NOTA.search(texto)
    numero_nota = match_numero.group(1) if match_numero else ''

    return {'numero_nota': numero_nota, 'fornecedor_nome': '', 'itens': itens}


def extrair_ia(nome_arquivo, conteudo_bytes, media_type):
    """Camada 3 — fallback de IA multimodal (API Claude). Só entra quando
    XML e texto de PDF não conseguiram extrair nada. Nunca lança exceção
    pro chamador — qualquer falha (sem API key, erro HTTP, JSON inválido)
    vira None, e a cascata registra metodo_extracao='falhou'."""
    from .claude_client import ClaudeAPIError, extrair_nota_fiscal

    try:
        dados = extrair_nota_fiscal(conteudo_bytes, media_type)
    except ClaudeAPIError as e:
        logger.warning('Falha na extração via IA para "%s": %s', nome_arquivo, e)
        return None

    itens_brutos = dados.get('itens') or []
    itens = []
    for item in itens_brutos:
        try:
            descricao = str(item.get('descricao', '')).strip()
            quantidade = Decimal(str(item.get('quantidade', '')))
            valor_unitario = Decimal(str(item.get('valor_unitario', '')))
        except (InvalidOperation, ValueError, TypeError):
            continue
        if not descricao:
            continue
        itens.append({'descricao': descricao, 'quantidade': quantidade, 'valor_unitario': valor_unitario})

    if not itens:
        return None

    return {
        'numero_nota': str(dados.get('numero_nota', '') or '').strip(),
        'fornecedor_nome': str(dados.get('fornecedor_nome', '') or '').strip(),
        'itens': itens,
    }


def resolver_materia_prima(descricao, MateriaPrima):
    """Fuzzy match iexact -> icontains, mesmo padrão de
    fichas/management/commands/importar_planilha.py e
    estoque/signals.py::_debitar_pedido_ifood. Nunca cria automaticamente
    aqui — quem decide criar é a revisão manual do usuário."""
    primeira_palavra = descricao.split()[0] if descricao.split() else descricao
    return (
        MateriaPrima.objects.filter(nome__iexact=descricao).first()
        or MateriaPrima.objects.filter(nome__icontains=primeira_palavra).first()
    )
