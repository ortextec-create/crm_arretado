# Contrato de Aquisição de Produtos — Especificação Técnica

> Documento de referência para implementação (uso do Claude Code).
> Segue o padrão de `FRETE.md` e `FINANCEIRO.md`. Ver `CLAUDE.md` para padrões obrigatórios do projeto.
> Decisões já tomadas com o cliente:
> - Dados faltantes do CONTRATANTE (RG, profissão, nacionalidade, estado civil) → **campos permanentes em `Cliente`**
> - Disparo do contrato → **manual**, botão "Emitir Contrato" que aparece quando `Orcamento.status == 'aprovado'`

---

## 1. Objetivo

Gerar um PDF de contrato (baseado no modelo `CONTRATO_DE_AQUISIÇÃO_DE_PRODUTOS_-_2026.docx`) a partir de um
`Orcamento` já aprovado, e enviá-lo ao cliente via WhatsApp — reaproveitando a infraestrutura já existente
para orçamentos (`pdf_orcamento.py` + `notificacoes/servico.py`).

Fluxo:
```
Orcamento (status='aprovado')
   → usuário clica "Emitir Contrato"
   → modal pede/confirma dados do CONTRATANTE faltantes (RG, profissão, nacionalidade, estado civil, endereço)
   → grava esses dados no Cliente (persistente, reaproveitável em contratos futuros)
   → cria registro Contrato (snapshot dos dados no momento da emissão)
   → gera PDF (eventos/pdf_contrato.py)
   → usuário revisa e clica "Enviar por WhatsApp"
   → notificar_documento() envia + grava HistoricoMensagem
```

O contrato **não** bloqueia nem altera o fluxo de conversão Orçamento → Evento; é um artefato paralelo,
emitido a partir do orçamento aprovado.

---

## 2. Campos novos em `clientes.Cliente`

Adicionar (todos opcionais — cliente existente não tem esses dados até o primeiro contrato):

| Campo | Tipo | Observação |
|---|---|---|
| `rg` | CharField(20), blank | Carteira de identidade |
| `rg_orgao_emissor` | CharField(20), blank | Ex: "SSP-PI" |
| `nacionalidade` | CharField(50), blank, default `'brasileira'` | |
| `profissao` | CharField(100), blank | |
| `estado_civil` | CharField(20), choices, blank | `solteiro/casado/divorciado/viuvo/uniao_estavel` |

**Endereço:** o contrato exige logradouro/número/bairro/cidade/estado do CONTRATANTE — isso **já existe**
em `clientes.Endereco` (endereço principal do cliente). Não duplicar campo de endereço no `Cliente`; o
formulário de emissão do contrato deve usar `cliente.enderecos.filter(principal=True).first()` e, se não
existir, pedir um endereço avulso só para o contrato (ver seção 5).

Migration simples, sem impacto em dado existente (`null=True, blank=True` ou `default=''`).

---

## 3. Singleton `ConfiguracaoContrato` (app `eventos` ou `notificacoes`, a definir por conveniência)

Segue o padrão de `ConfiguracaoEntrega.get()` / `ParametrosNegocio.get()` — **nada pode ficar hardcoded**,
pois o CRM é revendável a outros clientes com CNPJ/regras diferentes.

| Campo | Tipo | Default sugerido |
|---|---|---|
| `razao_social_contratada` | CharField | "Arretado Doces" |
| `cnpj_contratada` | CharField | — |
| `endereco_contratada` | CharField | — |
| `representante_nome` | CharField | — |
| `representante_nacionalidade` | CharField | "brasileiro" |
| `representante_estado_civil` | CharField | — |
| `representante_profissao` | CharField | — |
| `representante_rg` | CharField | — |
| `representante_cpf` | CharField | — |
| `representante_endereco` | CharField | — |
| `percentual_sinal` | DecimalField | 50.00 |
| `prazo_quitacao_dias` | PositiveIntegerField | 7 (dias antes do evento) |
| `multa_inadimplencia_pct` | DecimalField | 20.00 |
| `juros_mora_pct_mes` | DecimalField | 1.00 |
| `prazo_personalizacao_dias` | PositiveIntegerField | 15 |
| `prazo_aumento_quantidade_dias` | PositiveIntegerField | 15 |
| `prazo_aviso_rescisao_dias` | PositiveIntegerField | 30 |
| `multa_rescisao_acima_60_dias_pct` | DecimalField | 15.00 |
| `multa_rescisao_30_60_dias_pct` | DecimalField | 25.00 |
| `multa_rescisao_abaixo_30_dias_pct` | DecimalField | 30.00 |
| `multa_rescisao_abaixo_7_dias_pct` | DecimalField | 40.00 |
| `prazo_devolucao_dias` | PositiveIntegerField | 30 |
| `foro_comarca` | CharField | "Teresina" |
| `foro_estado` | CharField | "Piauí" |

Uso: `ConfiguracaoContrato.get()`. Editável na tela **Configurações** (nova seção "Contrato").

> Todas as cláusulas numéricas do modelo (multa 20%, juros 1%, sinal 50%, prazos de 7/15/30/60 dias)
> viram variáveis desse singleton — o texto do PDF é montado com f-strings usando esses valores, nunca
> número fixo no código do gerador de PDF.

---

## 4. Model `Contrato` (novo, app `eventos`)

Snapshot completo no momento da emissão (mesma filosofia de `ItemOrcamento`/`SnapshotPrecos` — histórico
fiel mesmo se o cliente ou a config mudarem depois).

```python
class Contrato(models.Model):
    STATUS_CHOICES = [
        ('gerado',   'Gerado'),
        ('enviado',  'Enviado'),
        ('cancelado','Cancelado'),
    ]

    numero      = models.CharField(max_length=20, unique=True, db_index=True)  # CTR-0001
    orcamento   = models.ForeignKey('Orcamento', on_delete=models.PROTECT, related_name='contratos')
    evento      = models.ForeignKey('Evento', null=True, blank=True, on_delete=models.SET_NULL, related_name='contratos')
    cliente     = models.ForeignKey('clientes.Cliente', null=True, on_delete=models.SET_NULL)

    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='gerado')

    # ── Snapshot CONTRATANTE (no momento da emissão) ──
    contratante_nome          = models.CharField(max_length=200)
    contratante_nacionalidade = models.CharField(max_length=50)
    contratante_profissao     = models.CharField(max_length=100, blank=True, default='')
    contratante_rg            = models.CharField(max_length=20, blank=True, default='')
    contratante_cpf           = models.CharField(max_length=14)
    contratante_estado_civil  = models.CharField(max_length=20, blank=True, default='')
    contratante_endereco      = models.CharField(max_length=400)  # linha completa já formatada

    # ── Snapshot do evento (herdado de Orcamento/Evento) ──
    data_evento    = models.DateField()
    hora_evento    = models.TimeField(null=True, blank=True)
    local_evento   = models.CharField(max_length=400)  # endereço completo formatado

    # ── Financeiro (snapshot da config no momento da emissão) ──
    valor_total           = models.DecimalField(max_digits=10, decimal_places=2)
    percentual_sinal      = models.DecimalField(max_digits=5, decimal_places=2)
    valor_sinal           = models.DecimalField(max_digits=10, decimal_places=2)
    data_quitacao         = models.DateField()  # data_evento - prazo_quitacao_dias

    criado_em     = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    @classmethod
    def proximo_numero(cls):
        # mesmo padrão de Evento.proximo_numero() — CTR-0001, CTR-0002...
        ...
```

Os **itens** (Anexo 1 / "nota de pedidos") **não são duplicados** — o PDF do contrato lê
`orcamento.itens.all()` diretamente (igual o PDF do orçamento já faz), então não precisa de um
`ItemContrato` separado.

---

## 5. Fluxo de emissão (frontend + backend)

### Backend — novos endpoints em `eventos/`

```
POST /api/v1/eventos/orcamentos/{id}/gerar-contrato/
  body: { rg, rg_orgao_emissor, nacionalidade, profissao, estado_civil, endereco_id (ou endereco_avulso) }
  → valida que orcamento.status == 'aprovado'
  → atualiza (ou cria) os campos novos no Cliente vinculado
  → cria Contrato (snapshot)
  → retorna ContratoSerializer

GET  /api/v1/eventos/contratos/{id}/pdf/
  → gera PDF via pdf_contrato.gerar_pdf_contrato(contrato) e retorna inline

POST /api/v1/eventos/contratos/{id}/enviar-whatsapp/
  → mesmo padrão de enviar-whatsapp de Orcamento:
    from .pdf_contrato import gerar_pdf_contrato
    from notificacoes.servico import notificar_documento
  → muda status para 'enviado'
```

### Regra de bloqueio

`gerar-contrato/` só é permitido se `orcamento.pode_aprovar is False and orcamento.status == 'aprovado'`
(ou seja, só depois de aprovado — reaproveitar a property já existente, não inventar uma nova).

### Frontend (`Orcamentos.jsx`)

- Botão **"Emitir Contrato"** aparece na lista/detalhe apenas quando `status === 'aprovado'`
  (mesmo padrão de botões contextuais por status que já existe: Enviar/Aprovar/Recusar/Converter)
- Ao clicar, abre modal **"Emitir Contrato"**:
  - Se o cliente já tem `rg`, `profissao`, `nacionalidade`, `estado_civil` preenchidos → mostra
    read-only com opção "editar"
  - Se não tem → formulário para preencher (grava no Cliente ao confirmar)
  - Campo de endereço: usa endereço principal do cliente se existir; senão, input de endereço avulso
    (mesmo padrão de `endereco_avulso` já usado em Orçamentos/Eventos)
  - Botão "Gerar Contrato" → chama `gerar-contrato/`, depois já mostra preview do PDF
  - Botão "Enviar por WhatsApp" → mesmo componente reutilizado do envio de orçamento
    (`orcamentosApi` ganha `contratosApi` irmão, seguindo o padrão de um objeto por recurso em `services.js`)

---

## 6. Geração do PDF (`eventos/pdf_contrato.py`)

Replicar a estrutura visual de `pdf_orcamento.py` (papel timbrado, cores da marca) mas com o texto
jurídico do modelo enviado. Pontos de atenção:

- Todo número/prazo/percentual vem de `ConfiguracaoContrato.get()`, nunca hardcoded no gerador
- Tabela do Anexo 1 = reaproveitar a mesma lógica de tabela de itens do `pdf_orcamento.py`
  (nome, quantidade, preço unit., total)
- Data de quitação (`Cláusula 9ª`) = `contrato.data_quitacao`, já calculada e congelada no momento da
  emissão (não recalcular na hora de gerar o PDF, para não mudar se a config for alterada depois)
- Tabela de multas de rescisão (`Cláusula 11ª`) monta as 4 faixas a partir dos campos do singleton
- Assinatura: nome da CONTRATANTE (snapshot) e nome do representante da CONTRATADA (do singleton)

---

## 7. O que NÃO fazer (regras específicas deste módulo)

- Não hardcodar CNPJ, razão social, representante legal ou qualquer cláusula numérica da CONTRATADA
  no gerador de PDF — tudo vem de `ConfiguracaoContrato.get()` (requisito do projeto: sistema revendável)
- Não duplicar itens do orçamento em um model `ItemContrato` — o PDF lê direto de `orcamento.itens`
- Não permitir gerar contrato de orçamento que não esteja `status == 'aprovado'`
- Não recalcular `data_quitacao`/`valor_sinal` a partir da config atual ao reabrir/reimprimir um
  contrato já emitido — usar sempre o snapshot gravado em `Contrato`
- Seguir o padrão já validado: `notificar_documento()` para envio, nunca chamar `zapi_client` direto

---

## 8. Checklist de implementação

1. Migration `clientes`: adicionar `rg`, `rg_orgao_emissor`, `nacionalidade`, `profissao`, `estado_civil`
2. Novo model `ConfiguracaoContrato` (singleton) + migration + seed com valores padrão do modelo atual
3. Novo model `Contrato` em `eventos/models.py` + `proximo_numero()` (padrão CTR-0001)
4. `eventos/pdf_contrato.py` — gerador ReportLab
5. `eventos/views.py` — 3 novas actions (`gerar-contrato`, `pdf`, `enviar-whatsapp`) em `OrcamentoViewSet`
   ou um `ContratoViewSet` próprio (recomendado, para GET/pdf/enviar por id do contrato)
6. `eventos/serializers.py` — `ContratoSerializer`
7. Seção "Contrato" na tela `Configuracoes.jsx` (mesmo padrão das seções Z-API/WhatsApp)
8. Botão "Emitir Contrato" + modal em `Orcamentos.jsx`, novo `contratosApi` em `services.js`
9. Testar geração + envio ponta a ponta com um orçamento aprovado real
