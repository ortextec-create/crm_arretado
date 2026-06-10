# Novos Sistemas — Arretado Doces CRM

> Documento de referência para os módulos desenvolvidos a partir de jun/2026.  
> Para padrões técnicos obrigatórios, ver `CLAUDE.md`.

---

## 1. Orçamentos (app `eventos/`)

### O que é

Sistema de orçamentos pré-evento que permite criar propostas numeradas (ORC-0001, ORC-0002…), enviá-las ao cliente, acompanhar aprovação e convertê-las automaticamente em Evento.

### Fluxo completo

```
Rascunho → Enviado → Aprovado → (convertido em Evento)
                  → Recusado
                  → Expirado
```

1. **Criar orçamento** — vincula um cliente CRM (busca com debounce), define data do evento, local, observações e adiciona itens (produto + quantidade + preço unitário)
2. **Enviar** — muda status para `enviado` (pode gerar notificação WhatsApp)
3. **Aprovar / Recusar** — cliente confirma ou não
4. **Converter em Evento** — cria automaticamente um `Evento` com os mesmos itens, data e local; o orçamento fica com status `convertido`

### Models principais

| Model | Campos-chave |
|---|---|
| `Orcamento` | `numero` (ORC-NNNN), `cliente` (FK), `status`, `data_evento`, `local` |
| `ItemOrcamento` | `orcamento` (FK), `descricao`, `quantidade`, `preco_unitario` |

### Frontend (`Orcamentos.jsx`)

- Lista com filtro por status (chips) e busca por número/nome/telefone
- Modal de criação com busca de cliente por debounce
- Adição de itens inline
- Botões de ação contextuais por status (Enviar / Aprovar / Recusar / Converter)

---

## 2. Catálogo (`app fichas/` + `Catalogo.jsx`)

### O que é

Visão completa dos produtos da confeitaria em formato de cards visuais, com controle de disponibilidade por canal de venda e segmentação.

### Campos novos em `pdv.Produto`

| Campo | Tipo | Descrição |
|---|---|---|
| `descricao` | TextField | Descrição livre do produto |
| `foto` | ImageField | Foto (upload_to='produtos/') |
| `segmento` | CharField | `unidade_pequena`, `unidade_media`, `bem_casado`, `bolo_encomenda`, `outro` |
| `disponivel_pdv` | BooleanField | Aparece no PDV? (default: True) |
| `disponivel_ifood` | BooleanField | Aparece no iFood? (default: False) |
| `disponivel_eventos` | BooleanField | Disponível para orçamentos/eventos? (default: False) |

### Segmentos e faixas de preço

| Segmento | Exemplos | Faixa |
|---|---|---|
| `unidade_pequena` | Brigadeiro, Beijinho, Paçoca | R$2,00 |
| `unidade_media` | Cappuccino, Crocante, Limão Siciliano | R$2,60–R$4,20 |
| `bem_casado` | Bem Casado Trad. (7 sabores), Red Velvet | R$5,10–R$5,80 |
| `bolo_encomenda` | Bolo de Iogurte com Mirtilo, Bolo com Ganache | R$95–R$420 |

### Frontend (`Catalogo.jsx`)

- **Grid de cards** com foto, nome, segmento, preço, custo, margem e toggles de disponibilidade
- **Semáforo de margem** via borda esquerda colorida: verde ≥ 30%, amarelo 15–30%, vermelho < 15%
- **Filtros:** busca por nome + filtro por segmento (chips) + filtro por disponibilidade
- **Modal de edição:** todos os campos + link para ficha técnica

---

## 3. Fichas Técnicas (`fichas/FichaTecnica` + `FichasTecnicas.jsx`)

### O que é

Receituário técnico de cada produto: lista de ingredientes com quantidades, cálculo automático de custo unitário e preço ideal baseado no markup do negócio.

### Models

```
MateriaPrima
  nome, unidade_compra, quantidade_compra, unidade_medida, valor_compra
  → custo_unitario = valor_compra / quantidade_compra  (property)

FichaTecnica
  nome, rendimento (unidades produzidas), embalagem_custo, produto_pdv_id (FK fraca)
  → custo_ingredientes   (soma de todos os itens)
  → custo_total_unitario (custo_ingredientes / rendimento + embalagem_custo)
  → preco_ideal          (custo_total_unitario × markup dos ParametrosNegocio)
  → margem_bruta_pct     (se houver produto PDV vinculado)

ItemFichaTecnica
  ficha (FK), materia_prima (FK), quantidade
  → custo_proporcional = custo_unitario × quantidade
```

### Vinculação ficha ↔ produto

A relação entre `FichaTecnica` e `pdv.Produto` é intencional­mente fraca (`produto_pdv_id` IntegerField, não ForeignKey). Isso permite:
- Produto existir sem ficha (ex: produto recém-cadastrado)
- Ficha existir sem produto (ex: receita em desenvolvimento)
- Evitar dependência circular entre apps

### Frontend (`FichasTecnicas.jsx`)

- **Layout dividido:** lista de fichas à esquerda (30%), detalhe à direita (70%)
- **Detalhe:** tabela de ingredientes com custo por linha, totais, preço ideal vs. preço atual
- **Edição inline:** adicionar/remover ingredientes, ajustar rendimento e embalagem

---

## 4. Central de Precificação (`CentralPrecos.jsx` + `fichas/views.py`)

### O que é

Painel central para gestão de preços — desde atualização de custo de ingredientes após nota fiscal até ajuste em lote com preview e desfazer.

### 4 abas

#### Aba 1 — Matérias-Primas

Tabela editável de ingredientes. Permite atualizar o preço de compra de vários ingredientes de uma vez. A cada atualização, o backend recalcula automaticamente o impacto nos produtos vinculados e retorna os IDs afetados.

**Endpoint:** `POST /api/v1/fichas/materias-primas/{id}/atualizar-preco/`  
**Retorna:** `{ materia: {...}, produtos_impactados: [id1, id2, ...] }`

#### Aba 2 — Ajuste Linear por Segmento

Reajuste de preços em lote com **preview obrigatório antes de confirmar**.

```
POST /api/v1/fichas/ajuste-linear/
Body: {
  segmento: "bem_casado" | "todos" | "unidade_pequena" | ...,
  tipo: "percentual" | "valor_fixo",
  operacao: "aumento" | "desconto",
  valor: 10.0,
  confirmar: false  ← preview sem salvar
}
```

- `confirmar: false` → retorna preview (produto, preço atual, preço novo, variação) sem alterar BD
- `confirmar: true` → grava um `SnapshotPrecos` antes de aplicar, depois atualiza `Produto.preco` de todos no segmento
- Após confirmar: botão **"Desfazer este ajuste"** fica disponível

#### Aba 3 — Semáforo de Margens

Tabela de todos os produtos com indicador visual de saúde:

| Cor | Condição |
|---|---|
| 🟢 Verde | Margem ≥ 30% |
| 🟡 Amarelo | 15% ≤ Margem < 30% |
| 🔴 Vermelho | Margem < 15% (abaixo do ponto de equilíbrio) |

Ao clicar em qualquer produto, abre painel lateral com custo detalhado, preço ideal calculado e campo para editar o preço de venda diretamente.

#### Aba 4 — Parâmetros do Negócio

Singleton `ParametrosNegocio` com os números globais que alimentam todos os cálculos:

| Parâmetro | Valor atual | Significado |
|---|---|---|
| Faturamento meta | R$40.000/mês | Meta de receita |
| Despesa fixa | R$17.000/mês | Folha + gás + Simples |
| Despesa variável | 42,5% | iFood, embalagens, outros |
| Margem esperada | 30% | Lucro sobre venda |
| **Markup resultante** | **3,63×** | `1 / (1 - 0,425 - 0,30)` |

Alterar qualquer parâmetro recalcula automaticamente os preços ideais de todos os produtos.

### Desfazer ajuste (`SnapshotPrecos`)

Antes de cada ajuste em lote, o sistema grava um snapshot:
```json
{ "produto_id": preco_anterior, "produto_id2": preco_anterior2, ... }
```
`POST /api/v1/fichas/desfazer-ajuste/{snapshot_id}/` restaura todos os preços e marca `revertido=True`. Snapshots revertidos ficam no histórico mas não podem ser desfeitos novamente.

---

## 5. Importação da Planilha (`importar_planilha`)

### O que faz

Management command que lê `PLANILHA_DE_PRECIFICAÇÃO__ARRETADO.xlsx` e popula o banco de dados em uma única execução.

```bash
python manage.py importar_planilha --arquivo PLANILHA_DE_PRECIFICAÇÃO__ARRETADO.xlsx
# flags:
#   --dry-run          imprime o que seria importado sem salvar
#   --apenas-materias  importa só matérias-primas
#   --sobrescrever     atualiza registros existentes pelo nome
```

### O que foi importado (jun/2026)

| Tipo | Quantidade |
|---|---|
| Matérias-primas | 36 |
| Produtos (pdv.Produto) | 34 |
| Fichas técnicas | 9 |

**Fichas importadas:** Cappuccino, Crocante, Churros, Prestígio, Paçoca, Farinha Láctea, Caipirinha, Limão Siciliano, Cocotinha

**Pendências de dados:**
- `Cobertura cappucino`, `Folha decorativa`, `Castanha do Pará`, `Ameixa` — criados com custo zero, precisam de preço real
- `Brigadeiro Sensacional` — ficha ignorada (quantidades não estavam na planilha)

### Lógica de parsing (aba MATERIA PRIMA)

- `kg` → converte para `g`, multiplica quantidade por 1000
- `l` / `litro` → converte para `ml`, multiplica por 1000
- `unidades` / `un` → unidade `un`
- Preço zero ou ausente → cria com `valor_compra=0.01` e emite aviso `⚠`

### Lógica de inferência de segmento (aba Cálculo)

| Preço de venda | Segmento inferido |
|---|---|
| ≤ R$2,10 | `unidade_pequena` |
| ≤ R$4,50 | `unidade_media` |
| ≤ R$6,00 | `bem_casado` |
| > R$6,00 | `bolo_encomenda` |

---

## Histórico de Deploys

| Data | O que foi para produção |
|---|---|
| jun/2026 | WhatsApp Z-API (notificacoes/) |
| jun/2026 | Orçamentos + Eventos completos |
| jun/2026 | App `fichas/` + 3 telas de frontend + importação da planilha |
