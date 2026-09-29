import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError, startEnvironment, stopEnvironment, type UpConfig } from '@/lib/api'

interface Campo {
  nome: string // mesmo nome do campo no body do POST /up
  label: string
  descricao: string
  min: number
  max: number
  padrao: number
}

// campo novo do upstream = um item novo aqui (+ uma linha no build_up_args do backend)
const CAMPOS: Campo[] = [
  {
    nome: 'slices',
    label: 'Quantidade de fatias',
    descricao: 'Cada fatia de rede é provisionada com seu próprio UE.',
    min: 1,
    max: 8,
    padrao: 2,
  },
]

export default function PesquisadorNovo() {
  const navigate = useNavigate()
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(CAMPOS.map((c) => [c.nome, String(c.padrao)]))
  )
  const [submitting, setSubmitting] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [conflict, setConflict] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function buildConfig(): UpConfig | null {
    const config: UpConfig = {}
    for (const c of CAMPOS) {
      const n = Number(values[c.nome])
      if (!Number.isInteger(n) || n < c.min || n > c.max) {
        setError(`${c.label}: informe um número inteiro entre ${c.min} e ${c.max}.`)
        return null
      }
      config[c.nome] = n
    }
    return config
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setConflict(false)

    const config = buildConfig()
    if (!config) return

    setSubmitting(true)
    try {
      await startEnvironment(config)
      navigate('/pesquisador/monitoramento')
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setConflict(true)
      } else {
        setError(err instanceof Error ? err.message : 'Falha ao criar o ambiente.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  async function handleStop() {
    setStopping(true)
    try {
      await stopEnvironment()
      setConflict(false)
      setError('Ambiente sendo encerrado. Aguarde terminar e tente criar novamente.')
    } catch {
      setError('Falha ao parar o ambiente.')
    } finally {
      setStopping(false)
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6 p-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Criar ambiente</h1>
        <p className="text-sm text-muted-foreground">
          Defina a configuração do testbed. Só um ambiente pode ficar ativo por vez.
        </p>
      </div>

      {conflict && (
        <Card className="border-[#F5A623]">
          <CardHeader>
            <CardTitle className="text-sm">Já existe um ambiente ativo</CardTitle>
            <CardDescription>
              Pare o ambiente atual antes de criar outro.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex gap-2">
            <Button asChild variant="outline" className="flex-1">
              <Link to="/pesquisador">Ver ambiente ativo</Link>
            </Button>
            <Button variant="outline" className="flex-1" onClick={handleStop} disabled={stopping}>
              {stopping ? 'Parando...' : 'Parar'}
            </Button>
          </CardContent>
        </Card>
      )}

      <form onSubmit={handleSubmit}>
        <Card>
          <CardContent className="space-y-6 pt-6">
            {CAMPOS.map((c) => (
              <div key={c.nome} className="space-y-2">
                <Label htmlFor={c.nome}>{c.label}</Label>
                <Input
                  id={c.nome}
                  type="number"
                  min={c.min}
                  max={c.max}
                  value={values[c.nome]}
                  onChange={(e) => setValues((v) => ({ ...v, [c.nome]: e.target.value }))}
                />
                <p className="text-xs text-muted-foreground">
                  {c.descricao} De {c.min} a {c.max}, padrão {c.padrao}.
                </p>
              </div>
            ))}

            {error && <p className="text-sm text-destructive">{error}</p>}

            <div className="flex justify-end gap-2">
              <Button asChild variant="ghost">
                <Link to="/pesquisador">Cancelar</Link>
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting ? 'Criando...' : 'Criar ambiente'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </div>
  )
}