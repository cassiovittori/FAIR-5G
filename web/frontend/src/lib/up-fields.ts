export interface Campo {
  nome: string
  label: string
  descricao: string
  min: number
  max: number
  padrao: number
}

// campo novo do upstream = um item novo aqui (+ uma linha no build_up_args do backend)
export const CAMPOS: Campo[] = [
  {
    nome: 'slices',
    label: 'Quantidade de fatias',
    descricao: 'Cada fatia de rede é provisionada com seu próprio UE.',
    min: 1,
    max: 8,
    padrao: 2,
  },
]