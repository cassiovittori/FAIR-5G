import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError, getRun, startEnvironment, stopEnvironment, type UpConfig } from '@/lib/api'
import { CAMPOS } from '@/lib/up-fields'

export default function PesquisadorNovo() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const from = searchParams.get('from')

  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(CAMPOS.map((c) => [c.nome, String(c.padrao)]))
  )
  const [copiedFrom, setCopiedFrom] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [conflict, setConflict] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [nome, setNome] = useState<string>('')

  // "Duplicar": preenche o form com a config do ambiente original
  useEffect(() => {
    if (!from) return
    getRun(from)
      .then((run) => {
        // runs antigos não têm config salvo: cai no slice_count (campo "slices")
        const cfg: Record<string, unknown> = { slices: run.slice_count, ...(run.config ?? {}) }
        setValues((prev) => {
          const next = { ...prev }
          for (const c of CAMPOS) {
            const v = cfg[c.nome]
            if (typeof v === 'number' && v >= c.min && v <= c.max) next[c.nome] = String(v)
          }
          return next
        })
        setCopiedFrom(run.run_id)
        if (run.nome) setNome(`${run.nome} (cópia)`)
      })
      .catch(() => setError('Não foi possível carregar a configuração do ambiente original.'))
  }, [from])

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
      await startEnvironment(config, nome.trim() || undefined)
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
    } catch(err) {
      setError(err instanceof Error ? err.message : 'Falha ao parar o ambiente.')
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
        {copiedFrom && (
          <p className="text-xs text-muted-foreground">
            Configuração copiada de <span className="font-mono">{copiedFrom}</span>. Ajuste o que quiser antes de criar.
          </p>
        )}
      </div>

      {conflict && (
        <Card className="border-[#F5A623]">
          <CardHeader>
            <CardTitle className="text-sm">Já existe um ambiente em uso</CardTitle>
            <CardDescription>
              Aguarde ele terminar de subir ou encerrar, ou pare o ambiente atual.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex gap-2">
            <Button asChild variant="outline" className="flex-1">
              <Link to="/pesquisador/monitoramento">Ver ambiente</Link>
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
            <div className="space-y-2">
                <Label htmlFor="nome">Nome (opcional)</Label>
                <Input
                    id="nome"
                    maxLength={60}
                    placeholder="Ex.: teste de latência com 4 fatias"
                    value={nome}
                    onChange={(e) => setNome(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                    Sem nome: "Ambiente — N fatias".
                </p>
            </div>
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