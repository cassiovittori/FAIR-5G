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

// UEs por fatia: espelha MIN/MAX/DEFAULT_UES_PER_SLICE de fair5gctl/core/slicing.py.
// O backend revalida com o upstream (fonte da verdade); aqui é só para a UI.
export const UES_PER_SLICE = { min: 1, max: 4, padrao: 1 }

// Aviso (não bloqueia) acima deste total de UEs. Palpite ajustável: cada UE é um
// nr-ue single-thread que satura um núcleo sob carga, e a VM pode ter poucas vCPUs.
export const UES_SOFT_WARNING_TOTAL = 6

