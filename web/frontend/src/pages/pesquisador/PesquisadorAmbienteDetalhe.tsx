import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { ArrowLeft } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusDot } from '@/components/StatusDot'
import { getRun, streamLogs, type Run } from '@/lib/api'
import { CAMPOS } from '@/lib/up-fields'
import { environmentLabel, fmtDateTime, fmtDuration, stripAnsi } from '@/lib/runs'

const MAX_LOG_LINES = 500

export default function PesquisadorAmbienteDetalhe() {
  const { runId } = useParams()
  const [run, setRun] = useState<Run | null>(null)
  const [loading, setLoading] = useState(true)
  const [lines, setLines] = useState<string[]>([])
  const logRef = useRef<HTMLPreElement>(null)

  async function load(initial = false) {
    if (!runId) return
    try {
      setRun(await getRun(runId))
    } catch {
      if (initial) setRun(null) // no polling, falha pontual não apaga a tela
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setLoading(true)
    setRun(null)
    load(true)
  }, [runId])

  const transitioning = run?.status === 'starting' || run?.status === 'stopping'
  useEffect(() => {
    if (!transitioning) return
    const interval = setInterval(() => load(), 3000)
    return () => clearInterval(interval)
  }, [transitioning, runId])

  // log do up: para run encerrado, reenvia o arquivo inteiro e fecha em "Script done on"
  useEffect(() => {
    if (!runId) return
    setLines([])
    return streamLogs(
      `/logs/${runId}`,
      (line) => setLines((prev) => [...prev.slice(-(MAX_LOG_LINES - 1)), stripAnsi(line)]),
      () => {}
    )
  }, [runId])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [lines])

  if (loading) {
    return (
      <div className="space-y-6 p-6">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-40" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  if (!run) {
    return (
      <div className="space-y-4 p-6">
        <Button asChild variant="ghost" size="sm">
          <Link to="/pesquisador/ambientes"><ArrowLeft className="mr-1 h-4 w-4" />Voltar</Link>
        </Button>
        <p className="text-sm text-muted-foreground">Ambiente não encontrado.</p>
      </div>
    )
  }

  // runs antigos não têm config salvo: cai no slice_count
  const config = run.config ?? { slices: run.slice_count }
  const busy = run.status === 'starting' || run.status === 'running' || run.status === 'stopping'

  const info = [
    { label: 'CRIADO EM', value: fmtDateTime(run.created_at) },
    { label: 'INICIADO EM', value: fmtDateTime(run.started_at) },
    { label: 'ENCERRADO EM', value: fmtDateTime(run.stopped_at) },
    { label: 'DURAÇÃO', value: fmtDuration(run) },
  ]

  return (
    <div className="space-y-6 p-6">
      <Button asChild variant="ghost" size="sm">
        <Link to="/pesquisador/ambientes"><ArrowLeft className="mr-1 h-4 w-4" />Todos os ambientes</Link>
      </Button>

      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">{environmentLabel(run)}</h1>
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm">{run.run_id}</span>
            <StatusDot status={run.status} />
          </div>
        </div>
        <div className="flex gap-2">
          {busy && (
            <Button asChild variant="outline">
              <Link to="/pesquisador/monitoramento">Monitorar</Link>
            </Button>
          )}
          <Button asChild>
            <Link to={`/pesquisador/novo?from=${run.run_id}`}>Duplicar</Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        {info.map((i) => (
          <Card key={i.label}>
            <CardHeader><CardTitle className="text-xs tracking-wide text-muted-foreground">{i.label}</CardTitle></CardHeader>
            <CardContent><p className="font-mono text-sm">{i.value}</p></CardContent>
          </Card>
        ))}
      </div>

      <section className="space-y-3">
        <h2 className="text-xs font-medium tracking-wide text-muted-foreground">CONFIGURAÇÃO USADA</h2>
        <Card className="divide-y">
          {Object.entries(config)
            .filter(([key, value]) => key !== 'nome' && value != null)
            .map(([key, value]) => (
              <div key={key} className="flex items-center justify-between px-6 py-3 text-sm">
                <span>{CAMPOS.find((c) => c.nome === key)?.label ?? key}</span>
                <span className="font-mono">{String(value)}</span>
              </div>
            ))}
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-xs tracking-wide text-muted-foreground">LOG DA CRIAÇÃO DO AMBIENTE</CardTitle>
        </CardHeader>
        <CardContent>
          <pre ref={logRef} className="max-h-96 overflow-auto rounded-md bg-muted p-3 font-mono text-xs whitespace-pre-wrap">
            {lines.length ? lines.join('\n') : 'Aguardando log...'}
          </pre>
        </CardContent>
      </Card>
    </div>
  )
}