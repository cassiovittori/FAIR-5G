import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { Trans, useTranslation } from 'react-i18next'
import { Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { listRuns, hostMetrics, loadErrorMessage, stopEnvironment, type Run, type HostMetrics } from '@/lib/api'
import { useToast } from '@/lib/toast'
import { StatusDot } from '@/components/StatusDot'
import { environmentLabel } from '@/lib/runs'
import i18n from '@/i18n'

export default function PesquisadorHome() {
  const { t } = useTranslation()
  const [runs, setRuns] = useState<Run[] | null>(null)
  const [metrics, setMetrics] = useState<HostMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [stopping, setStopping] = useState(false)
  const toast = useToast()

  async function load() {
    setLoading(true)
    try {
      const [runsData, metricsData] = await Promise.all([listRuns(), hostMetrics()])
      setRuns(runsData)
      setMetrics(metricsData)
    } catch (err) {
      setError(loadErrorMessage(err, i18n.t('home.loadError')))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  // métricas do host
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        setMetrics(await hostMetrics())
      } catch {
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [])

  const active = runs?.filter((r) => r.status === 'running') ?? []
  const starting = runs?.filter((r) => r.status === 'starting') ?? []
  const stoppingRuns = runs?.filter((r) => r.status === 'stopping') ?? []
  const recent = runs?.slice(0, 5) ?? []
  const inTransition = starting.length > 0 || stoppingRuns.length > 0

  // polling dos runs só enquanto algum ambiente está subindo ou descendo
  // (chama listRuns direto, sem passar pelo load(), pra não piscar o skeleton)
  useEffect(() => {
    if (!inTransition) return
    const interval = setInterval(async () => {
      try {
        setRuns(await listRuns())
      } catch {
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [inTransition])

  async function handleStop() {
    setStopping(true)
    try {
      await stopEnvironment()
      await load()
    } catch(err) {
      toast.error(err instanceof Error ? err.message : t('common.stopError'))
      await load()
    } finally {
      setStopping(false)
    }
  }

  return (
    <div className="space-y-8 p-6">
      <Card className="flex justify-between overflow-hidden p-8">
        <div className="max-w-xl space-y-2">
          <p className="text-sm text-muted-foreground">{t('home.greeting')}</p>
          <h1 className="text-2xl font-semibold"><Trans i18nKey="home.welcome" components={{ brand: <span className="font-mono" /> }} /></h1>
          <p className="text-sm text-muted-foreground">
            {t('home.intro')}
          </p>
        </div>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <section className="space-y-3">
        <h2 className="text-xs font-medium tracking-wide text-muted-foreground">{t('home.recent')}</h2>
        <Card className="pt-2 px-3 pb-0 gap-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('common.columns.runId')}</TableHead>
                <TableHead>{t('common.columns.name')}</TableHead>
                <TableHead>{t('common.columns.status')}</TableHead>
                <TableHead className="text-right">{t('common.columns.actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell><Skeleton className="h-4 w-12" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-40" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                    <TableCell className="text-right"><Skeleton className="ml-auto h-4 w-20" /></TableCell>
                  </TableRow>
                ))
              ) : recent.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="py-8 text-center text-sm text-muted-foreground">
                    {t('home.noneYet')}
                  </TableCell>
                </TableRow>
              ) : (
                recent.map((run) => (
                  <TableRow key={run.run_id}>
                    <TableCell className="font-mono text-xs">{run.run_id}</TableCell>
                    <TableCell>{environmentLabel(run)}</TableCell>
                    <TableCell><StatusDot status={run.status} /></TableCell>
                    <TableCell className="space-x-3 text-right text-sm">
                      {run.status === 'running' ? (
                        <>
                          <Link to="/pesquisador/monitoramento" className="text-muted-foreground hover:underline">{t('common.monitor')}</Link>
                          <button onClick={handleStop} disabled={stopping} className="text-[#FF3B5C] hover:underline disabled:opacity-50">{t('common.stop')}</button>
                        </>
                      ) : run.status === 'starting' ? (
                        <Link to="/pesquisador/monitoramento" className="text-muted-foreground hover:underline">{t('common.follow')}</Link>
                      ) : run.status === 'stopping' ? (
                        <span className="text-muted-foreground">—</span>
                      ) : (
                        <>
                          <Link to={`/pesquisador/ambientes/${run.run_id}`} className="text-muted-foreground hover:underline">{t('common.view')}</Link>
                          <Link to={`/pesquisador/novo?from=${run.run_id}`} className="text-muted-foreground hover:underline">{t('common.duplicate')}</Link>
                        </>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
          <div className="flex items-center justify-between border-t p-4">
            <Button asChild><Link to="/pesquisador/novo">{t('common.createEnvironment')}</Link></Button>
            <Link to="/pesquisador/ambientes" className="text-sm text-muted-foreground hover:underline">{t('home.viewAll')}</Link>
          </div>
        </Card>
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-xs tracking-wide text-muted-foreground">{t('home.activeEnvironment')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {loading ? (
              <div className="space-y-3">
                <Skeleton className="h-8 w-32" />
                <Skeleton className="h-9 w-full" />
              </div>
            ) : active.length > 0 ? (
              <>
                <div className="space-y-1">
                  <p className="text-l font-semibold">{active[0].run_id}</p>
                  <StatusDot status={active[0].status} />
                </div>
                <div className="flex gap-2">
                  <Button asChild className="flex-1">
                    <Link to="/pesquisador/monitoramento">{t('common.monitor')}</Link>
                  </Button>
                  <Button variant="outline" className="flex-1 hover:!border-destructive hover:!bg-destructive hover:!text-destructive-foreground" onClick={handleStop} disabled={stopping}>
                    {stopping ? t('common.stopping') : t('common.stop')}
                  </Button>
                </div>
              </>
            ) : starting.length > 0 ? (
              <>
                <div className="space-y-1">
                  <p className="text-l font-semibold">{starting[0].run_id}</p>
                  <StatusDot status={starting[0].status} />
                </div>
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t('home.waitingActive')}
                </p>
                <div className="flex gap-2">
                  <Button asChild className="flex-1">
                    <Link to="/pesquisador/monitoramento">{t('common.follow')}</Link>
                  </Button>
                  <Button variant="outline" className="flex-1" disabled>{t('common.stop')}</Button>
                </div>
              </>
            ) : stoppingRuns.length > 0 ? (
              <>
                <div className="space-y-1">
                  <p className="text-l font-semibold">{stoppingRuns[0].run_id}</p>
                  <StatusDot status={stoppingRuns[0].status} />
                </div>
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t('common.stoppingEnvironment')}
                </p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">{t('common.noActiveEnvironment')}</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-xs tracking-wide text-muted-foreground">{t('home.systemStatus')}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1">
              <div className="flex justify-between text-sm"><span>{t('home.hostCpu')}</span><span>{metrics ? `${Math.round(metrics.cpu_percent)}%` : '—'}</span></div>
              <Progress value={metrics?.cpu_percent ?? 0} />
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-sm"><span>{t('home.memory')}</span><span>{metrics ? `${Math.round(metrics.memory_percent)}%` : '—'}</span></div>
              <Progress value={metrics?.memory_percent ?? 0} />
            </div>
            <div className="flex justify-between text-sm">
              <span>{t('home.latestAlerts')}</span>
              <span className="text-[#0633FF]">-</span>
            </div>
          </CardContent>
        </Card>

        <Card className="flex flex-col items-center justify-center gap-2 p-6 text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted text-sm">?</div>
          <CardTitle className="text-sm">{t('home.gettingStarted')}</CardTitle>
          <CardDescription className="text-xs">{t('home.gettingStartedDescription')}</CardDescription>
          <Link to="/pesquisador/guia" className="text-xs text-muted-foreground hover:underline">{t('home.guideLink')}</Link>
        </Card>
      </div>
    </div>
  )
}