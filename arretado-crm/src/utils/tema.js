// Fase 3 do Multi-Empresa — aplicação de tema (ver MULTIEMPRESA.md).
// Mapeia os 12 campos de cor de `empresas.Empresa` para os tokens CSS reais
// de index.css (nomes diferentes dos usados na tabela conceitual do spec).

const MAPA_CORES_EMPRESA = {
  cor_fundo: '--bg',
  cor_surface: '--surface',
  cor_surface_alt: '--bg-alt',
  cor_borda: '--border',
  cor_texto: '--texto',
  cor_muted: '--texto-muted',
  cor_primaria: '--caramelo',
  cor_primaria_texto: '--caramelo-texto',
  cor_acento: '--acento',
  cor_sidebar: '--sidebar-bg',
  cor_sidebar_texto: '--sidebar-texto',
  cor_sidebar_ativo: '--sidebar-ativo',
}

// Aplica (ou limpa, se `empresa` for null/campo vazio) as cores de uma
// empresa como overrides inline na raiz do documento. Campo vazio sempre
// remove a propriedade (nunca só pula) — é o que garante reset correto ao
// trocar de empresa/tema e o que torna "cor vazia ⇒ UI atual" verdadeiro
// por construção (ver Padrões Obrigatórios do CLAUDE.md).
export function aplicarCoresEmpresa(empresa) {
  const root = document.documentElement.style
  for (const [campo, token] of Object.entries(MAPA_CORES_EMPRESA)) {
    const valor = empresa?.[campo]
    if (valor) root.setProperty(token, valor)
    else root.removeProperty(token)
  }
}

// modo: null (tema "empresa") | 'neutro_claro' | 'neutro_escuro'
export function aplicarModoNeutro(modo) {
  const raiz = document.documentElement
  if (modo === 'neutro_claro') raiz.dataset.theme = 'neutro-claro'
  else if (modo === 'neutro_escuro') raiz.dataset.theme = 'neutro-escuro'
  else delete raiz.dataset.theme
}

// Helper único usado por useAuth (autenticado) e Login (branding público) —
// decide entre tema neutro (cores de empresa limpas) e tema de empresa
// (cores aplicadas, sem data-theme).
export function aplicarTema({ empresa, preferenciaTema }) {
  if (preferenciaTema === 'neutro_claro' || preferenciaTema === 'neutro_escuro') {
    aplicarModoNeutro(preferenciaTema)
    aplicarCoresEmpresa(null)
  } else {
    aplicarModoNeutro(null)
    aplicarCoresEmpresa(empresa)
  }
}
