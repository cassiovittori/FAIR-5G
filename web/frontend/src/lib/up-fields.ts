import type { ParseKeys } from 'i18next'

export interface Campo {
  nome: string
  labelKey: ParseKeys
  descricaoKey: ParseKeys
  min: number
  max: number
  padrao: number
}

// campo novo do upstream = um item novo aqui (+ uma linha no build_up_args do backend)
export const CAMPOS: Campo[] = [
  {
    nome: 'slices',
    labelKey: 'upFields.slices.label',
    descricaoKey: 'upFields.slices.description',
    min: 1,
    max: 8,
    padrao: 2,
  },
]