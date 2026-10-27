import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation()
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
          <Link to="/pesquisador/ambientes"><ArrowLeft className="mr-1 h-4 w-4" />{t('common.back')}</Link>
        </Button>
        <p className="text-sm text-muted-foreground">{t('detalhe.notFound')}</p>
      </div>
    )
  }

  // runs antigos não têm config salvo: cai no slice_count
  const config = run.config ?? { slices: run.slice_count }
  const fieldLabel = (key: string) => {
    if (key === 'ues_per_slice') return t('detalhe.uesPerSlice')
    const campo = CAMPOS.find((c) => c.nome === key)
    return campo ? t(campo.labelKey) : key
  }
  const fieldValue = (key: string, value: unknown) => {
    if (!Array.isArray(value)) return String(value)
    if (key === 'ues_per_slice' && value.length > 0 && value.every((v) => v === value[0])) {
      return t('detalhe.uesAllSame', { count: Number(value[0]) })
    }
    return value.join(', ')
  }
  // runs antigos (sem ues_per_slice) subiram com o padrão do upstream: 1 UE por fatia
  const ues = Array.isArray(config.ues_per_slice) ? config.ues_per_slice.map(Number) : Array<number>(run.slice_count).fill(1)
  const totalUes = ues.reduce((a, b) => a + b, 0)
  const busy = run.status === 'starting' || run.status === 'running' || run.status === 'stopping'

  const info = [
    { label: t('common.columns.createdAt'), value: fmtDateTime(run.created_at) },
    { label: t('detalhe.startedAt'), value: fmtDateTime(run.started_at) },
    { label: t('detalhe.stoppedAt'), value: fmtDateTime(run.stopped_at) },
    { label: t('common.columns.duration'), value: fmtDuration(run) },
  ]

  return (
    <div className="space-y-6 p-6">
      <Button asChild variant="ghost" size="sm">
        <Link to="/pesquisador/ambientes"><ArrowLeft className="mr-1 h-4 w-4" />{t('detalhe.backToAll')}</Link>
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
              <Link to="/pesquisador/monitoramento">{t('common.monitor')}</Link>
            </Button>
          )}
          <Button asChild>
            <Link to={`/pesquisador/novo?from=${run.run_id}`}>{t('common.duplicate')}</Link>
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
        <h2 className="text-xs font-medium tracking-wide text-muted-foreground">{t('detalhe.configUsed')}</h2>
        <Card className="divide-y">
          {Object.entries(config)
            .filter(([key, value]) => key !== 'nome' && value != null)
            .map(([key, value]) => (
              <div key={key} className="flex items-center justify-between px-6 py-3 text-sm">
                <span>{fieldLabel(key)}</span>
                <span className="font-mono">{fieldValue(key, value)}</span>
              </div>
            ))}
          <div className="flex items-center justify-between px-6 py-3 text-sm">
            <span>{t('detalhe.totalUes')}</span>
            <span className="font-mono">{totalUes}</span>
          </div>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-xs tracking-wide text-muted-foreground">{t('common.upLog')}</CardTitle>
        </CardHeader>
        <CardContent>
          <pre ref={logRef} className="max-h-96 overflow-auto rounded-md bg-muted p-3 font-mono text-xs whitespace-pre-wrap">
            {lines.length ? lines.join('\n') : t('common.waitingLog')}
          </pre>
        </CardContent>
      </Card>
    </div>
  )
}