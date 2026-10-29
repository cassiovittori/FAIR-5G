// Conteúdo do Guia (/pesquisador/guia). Texto em `crases` vira <code> na página.
// Os ids viram âncoras (#campo-<id>, #termo-<id>, #faq-<id>) e precisam ser iguais nos idiomas.

export interface GuiaLink {
  to: string
  label: string
}

export interface GuiaSection {
  id: string
  title: string
  body: string[]          // um parágrafo por item
  links?: GuiaLink[]
}

export interface GuiaTerm {
  id: string
  term: string            // sigla / nome curto
  full?: string           // nome por extenso
  body: string
  where?: string          // onde aparece na ferramenta
}

export interface GuiaFaq {
  id: string
  q: string
  a: string[]
}

export interface GuiaContent {
  steps: {
    notice: { title: string; body: string }
    items: GuiaSection[]
  }
  fields: {
    items: GuiaSection[]  // ids: slices, ues, nome (âncoras campo-*)
    example: GuiaSection
    isolation: GuiaSection
  }
  glossary: GuiaTerm[]
  faq: GuiaFaq[]
}
