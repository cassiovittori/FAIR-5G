import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import type { ParseKeys, TFunction } from 'i18next'
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from 'recharts'
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { StatusDot } from '@/components/StatusDot'
import {
  listRuns, networkHistory, networkMetrics, networkNfs, stopEnvironment, streamLogs,
  type NetworkMetrics, type NetworkNfs, type Run, type SliceSeries,
} from '@/lib/api'
import { environmentLabel } from '@/lib/runs'
import { currentLocale } from '@/i18n'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
 
const POLL_MS = 5000
const MAX_LOG_LINES = 500
const SLICE_COLORS = ['#0633FF', '#F5A623', '#8B5CF6', '#22C55E', '#FF3B5C', '#06B6D4', '#EC4899', '#64748B']
 
// eslint-disable-next-line no-control-regex
const ANSI = /\x1b\[[0-9;?]*[A-Za-z]/g
 
type Tab = 'geral' | 'rede' | 'controle' | 'nfs'
 
interface ChartDef {
  tab: Tab
  titleKey: ParseKeys
  unit: string | { key: ParseKeys }
  // nome da métrica no backend (lista permitida do /metrics/network/history)
  // séries por fatia viram "Fatia N"; séries globais usam label/color daqui
  metrics: { name: string; labelKey?: ParseKeys; color?: string }[]
}
 
const PPS = { key: 'monitoramento.units.packetsPerSec' } as const

// gráfico novo = uma linha nova aqui (e a métrica precisa existir no HISTORY do backend)
const CHARTS: ChartDef[] = [
  { tab: 'geral', titleKey: 'monitoramento.charts.latency', unit: 'ms', metrics: [{ name: 'rtt_ms' }] },
  { tab: 'geral', titleKey: 'monitoramento.charts.upfIn', unit: PPS, metrics: [{ name: 'upf_in_pps' }] },
 
  { tab: 'rede', titleKey: 'monitoramento.charts.latency', unit: 'ms', metrics: [{ name: 'rtt_ms' }] },
  { tab: 'rede', titleKey: 'monitoramento.charts.jitter', unit: 'ms', metrics: [{ name: 'jitter_ms' }] },
  { tab: 'rede', titleKey: 'monitoramento.charts.packetLoss', unit: '%', metrics: [{ name: 'packet_loss' }] },
  { tab: 'rede', titleKey: 'monitoramento.charts.upfIn', unit: PPS, metrics: [{ name: 'upf_in_pps' }] },
  { tab: 'rede', titleKey: 'monitoramento.charts.upfOut', unit: PPS, metrics: [{ name: 'upf_out_pps' }] },
 
  {
    tab: 'controle', titleKey: 'monitoramento.charts.amfRegistration', unit: 'req/s',
    metrics: [
      { name: 'amf_reg_req', labelKey: 'monitoramento.series.attempts', color: '#0633FF' },
      { name: 'amf_reg_succ', labelKey: 'monitoramento.series.success', color: '#22C55E' },
    ],
  },
  {
    tab: 'controle', titleKey: 'monitoramento.charts.amfAuth', unit: 'req/s',
    metrics: [
      { name: 'amf_auth_req', labelKey: 'monitoramento.series.requests', color: '#0633FF' },
      { name: 'amf_auth_reject', labelKey: 'monitoramento.series.rejected', color: '#F5A623' },
      { name: 'amf_auth_fail', labelKey: 'monitoramento.series.failures', color: '#FF3B5C' },
    ],
  },
  { tab: 'controle', titleKey: 'monitoramento.charts.amfRegistered', unit: 'UEs', metrics: [{ name: 'amf_registered_by_slice' }] },
  { tab: 'controle', titleKey: 'monitoramento.charts.smfSessions', unit: { key: 'monitoramento.units.sessions' }, metrics: [{ name: 'sessions' }] },
  { tab: 'controle', titleKey: 'monitoramento.charts.smfQosFlows', unit: 'flows', metrics: [{ name: 'smf_qos_flows' }] },
  { tab: 'controle', titleKey: 'monitoramento.charts.upfQosFlows', unit: 'flows', metrics: [{ name: 'upf_qos_flows' }] },
]
 
const metricsFor = (tab: Tab) =>
  [...new Set(CHARTS.filter((c) => c.tab === tab).flatMap((c) => c.metrics.map((m) => m.name)))]
 
const sliceColor = (id: number) => SLICE_COLORS[(id - 1) % SLICE_COLORS.length]
const fmt = (n: number | null | undefined, digits = 2) => (n == null ? '—' : n.toFixed(digits))
const fmtTime = (t?: number) =>
  t == null ? '' : new Date(t * 1000).toLocaleTimeString(currentLocale(), { hour: '2-digit', minute: '2-digit', second: '2-digit' })
 
interface Line { key: string; label: string; color: string; dash?: string; points: SliceSeries['points'] }

// UEs da mesma fatia: mesma cor, traço diferente (UE 1 contínuo)
const UE_DASHES = [undefined, '6 3', '2 3', '8 3 2 3']
 
function buildLines(def: ChartDef, data: Record<string, SliceSeries[]>, only: number | 'all', t: TFunction): Line[] {
  const lines: Line[] = []
  def.metrics.forEach((m, mi) => {
    const series = data[m.name] ?? []
    // métricas por IP de UE trazem uma série por UE; "Fatia N · UE k" só quando a fatia tem mais de um
    const uesInSlice = new Map<number, number>()
    for (const s of series) uesInSlice.set(s.id, (uesInSlice.get(s.id) ?? 0) + 1)
    for (const s of series) {
      const perSlice = s.id !== 0
      if (perSlice && only !== 'all' && s.id !== only) continue
      const multiUe = s.ue != null && (uesInSlice.get(s.id) ?? 0) > 1
      lines.push({
        key: `${m.name}__${s.id}-${s.ue ?? 0}`,
        label: !perSlice
          ? (m.labelKey ? t(m.labelKey) : m.name)
          : multiUe ? t('monitoramento.ueLabel', { id: s.id, ue: s.ue }) : t('common.sliceN', { id: s.id }),
        color: perSlice ? sliceColor(s.id) : (m.color ?? SLICE_COLORS[mi % SLICE_COLORS.length]),
        dash: multiUe ? UE_DASHES[((s.ue ?? 1) - 1) % UE_DASHES.length] : undefined,
        points: s.points,
      })
    }
  })
  return lines
}
 
// junta as linhas em [{t, key1, key2, ...}] pro Recharts
function toRows(lines: Line[]) {
  const byT = new Map<number, Record<string, number | null>>()
  for (const l of lines) {
    for (const p of l.points) {
      const row = byT.get(p.t) ?? { t: p.t }
      row[l.key] = p.v
      byT.set(p.t, row)
    }
  }
  return [...byT.values()].sort((a, b) => (a.t as number) - (b.t as number))
}
 
function MetricChart({ def, data, only }: { def: ChartDef; data: Record<string, SliceSeries[]> | null; only: number | 'all' }) {
  const { t } = useTranslation()
  const lines = buildLines(def, data ?? {}, only, t)
  const rows = toRows(lines)
  const config = Object.fromEntries(lines.map((l) => [l.key, { label: l.label, color: l.color }])) as ChartConfig
 
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xs tracking-wide text-muted-foreground">
          {t(def.titleKey)} <span className="font-normal">({typeof def.unit === 'string' ? def.unit : t(def.unit.key)})</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="py-16 text-center text-sm text-muted-foreground">{t('monitoramento.collecting')}</p>
        ) : (
          <ChartContainer config={config} className="h-56 w-full">
            <LineChart data={rows} margin={{ left: 4, right: 8 }}>
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="t" type="number" domain={['dataMin', 'dataMax']}
                tickFormatter={fmtTime} tickLine={false} axisLine={false} minTickGap={40}
              />
              <YAxis tickLine={false} axisLine={false} width={44} />
              <ChartTooltip
                content={<ChartTooltipContent labelFormatter={(_, payload) => fmtTime(payload?.[0]?.payload?.t)} />}
              />
              <ChartLegend content={<ChartLegendContent />} />
              {lines.map((l) => (
                <Line
                  key={l.key} dataKey={l.key} type="monotone"
                  stroke={l.color} strokeDasharray={l.dash} strokeWidth={2} dot={false} isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  )
}
 
function ChartGrid({ tab, data, only }: { tab: Tab; data: Record<string, SliceSeries[]> | null; only: number | 'all' }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {CHARTS.filter((c) => c.tab === tab).map((c) => (
        <MetricChart key={c.titleKey} def={c} data={data} only={only} />
      ))}
    </div>
  )
}
 
export default function PesquisadorMonitoramento() {
  const { t } = useTranslation()
  const [run, setRun] = useState<Run | null>(null)
  const [net, setNet] = useState<NetworkMetrics | null>(null)
  const [series, setSeries] = useState<Record<string, SliceSeries[]> | null>(null)
  const [nfs, setNfs] = useState<NetworkNfs | null>(null)
  const [tab, setTab] = useState<Tab>('geral')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [stopping, setStopping] = useState(false)
  const [lines, setLines] = useState<string[]>([])
  const [showLog, setShowLog] = useState<boolean | null>(null) // null = padrão (aberto no starting e no stopping)
  const logRef = useRef<HTMLPreElement>(null)
  const [slice, setSlice] = useState<number | 'all'>('all')
 
  async function refresh() {
    try {
      const runs = await listRuns()
      const current = runs.find((r) => ['starting', 'running', 'stopping'].includes(r.status)) ?? null
      setRun(current)
      if (current?.status === 'running') {
        const names = metricsFor(tab)
        const [n, h, f] = await Promise.all([
          networkMetrics(),
          names.length ? networkHistory(15, names) : Promise.resolve(null),
          tab === 'nfs' ? networkNfs() : Promise.resolve(null),
        ])
        setNet(n)
        setSeries(h && h.available ? h.series : null)
        if (f) setNfs(f)
      } else {
        setNet(null)
        setSeries(null)
        setNfs(null)
      }
      setError(null)
    } catch {
      setError(t('monitoramento.refreshError'))
    } finally {
      setLoading(false)
    }
  }
 
  // reinicia o polling quando troca de aba, pra buscar só as métricas dela
  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, POLL_MS)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab])
 
  // log: durante o encerramento lê o down.log; nos demais estados, o up.log.
  // reabre o stream quando muda o run ou quando ele entra em encerramento
  const runId = run?.run_id
  const stoppingRun = run?.status === 'stopping'
  useEffect(() => {
    if (!runId) return
    setLines([])
    setShowLog(null) // volta ao padrão a cada fase
    const path = stoppingRun ? `/logs/${runId}/down` : `/logs/${runId}`
    return streamLogs(
      path,
      (line) => setLines((prev) => [...prev.slice(-(MAX_LOG_LINES - 1)), line.replace(ANSI, '')]),
      () => {}
    )
  }, [runId, stoppingRun])
 
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [lines])
 
  async function handleStop() {
    setStopping(true)
    try {
      await stopEnvironment()
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.stopError'))
      await refresh()
    } finally {
      setStopping(false)
    }
  }
 
  if (loading) {
    return (
      <div className="space-y-6 p-6">
        <Skeleton className="h-10 w-72" />
        <div className="grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-24" /><Skeleton className="h-24" /><Skeleton className="h-24" />
        </div>
        <Skeleton className="h-64" />
      </div>
    )
  }
 
  if (!run) {
    return (
      <div className="space-y-6 p-6">
        <h1 className="text-2xl font-semibold">{t('monitoramento.title')}</h1>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Card className="flex flex-col items-center gap-3 p-10 text-center">
          <p className="text-sm text-muted-foreground">{t('common.noActiveEnvironment')}</p>
          <Button asChild><Link to="/pesquisador/novo">{t('common.createEnvironment')}</Link></Button>
        </Card>
      </div>
    )
  }
 
  const logOpen = showLog ?? (run.status === 'starting' || run.status === 'stopping')
  const running = run.status === 'running'
  const only = slice !== 'all' && slice > run.slice_count ? 'all' : slice
 
  return (
    <div className="space-y-6 p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">{t('monitoramento.title')}</h1>
          <div className="flex items-center gap-3">
            <span className="text-sm">{environmentLabel(run)}</span>
            <span className="font-mono text-xs text-muted-foreground">{run.run_id}</span>
            <StatusDot status={run.status} />
            <span className="text-sm text-muted-foreground">
              {t('common.sliceCount', { count: run.slice_count })}
            </span>
          </div>
        </div>
        {running && (
          <Button
            variant="outline"
            className="hover:!border-destructive hover:!bg-destructive hover:!text-destructive-foreground"
            onClick={handleStop} disabled={stopping}
          >
            {stopping ? t('common.stopping') : t('common.stop')}
          </Button>
        )}
      </div>
 
      {error && <p className="text-sm text-destructive">{error}</p>}
 
      {!running && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {run.status === 'starting'
            ? t('monitoramento.waitingActive')
            : t('common.stoppingEnvironment')}
        </p>
      )}
 
      {running && net && 'reason' in net && (
        <p className="text-sm text-muted-foreground">{t('monitoramento.networkUnavailable', { reason: net.reason })}</p>
      )}
 
      {running && net?.available && (
        <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)} className="space-y-6">
          <div className="flex items-center justify-between gap-4">
            <TabsList>
              <TabsTrigger value="geral">{t('monitoramento.tabs.overview')}</TabsTrigger>
              <TabsTrigger value="rede">{t('monitoramento.tabs.network')}</TabsTrigger>
              <TabsTrigger value="controle">{t('monitoramento.tabs.control')}</TabsTrigger>
              <TabsTrigger value="nfs">{t('monitoramento.tabs.nfs')}</TabsTrigger>
            </TabsList>
 
            {tab !== 'nfs' && (
              <Select value={String(only)} onValueChange={(v) => setSlice(v === 'all' ? 'all' : Number(v))}>
                <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('monitoramento.allSlices')}</SelectItem>
                  {Array.from({ length: run.slice_count }, (_, i) => i + 1).map((id) => (
                    <SelectItem key={id} value={String(id)}>{t('common.sliceN', { id })}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
 
          <TabsContent value="geral" className="space-y-6">
            <div className="grid gap-4 lg:grid-cols-3">
              {[
                { label: t('monitoramento.cards.connectedUes'), value: fmt(net.global.ues, 0) },
                { label: 'GNBS', value: fmt(net.global.gnbs, 0) },
                { label: t('monitoramento.cards.slices'), value: String(net.slices.length) },
              ].map((c) => (
                <Card key={c.label}>
                  <CardHeader><CardTitle className="text-xs tracking-wide text-muted-foreground">{c.label}</CardTitle></CardHeader>
                  <CardContent><p className="text-3xl font-semibold">{c.value}</p></CardContent>
                </Card>
              ))}
            </div>
 
            <section className="space-y-3">
              <h2 className="text-xs font-medium tracking-wide text-muted-foreground">{t('monitoramento.cards.slices')}</h2>
              <Card className="px-3 py-2">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('monitoramento.columns.slice')}</TableHead>
                      <TableHead className="text-right">{t('monitoramento.columns.ues')}</TableHead>
                      <TableHead>PING</TableHead>
                      <TableHead className="text-right">RTT (ms)</TableHead>
                      <TableHead className="text-right">{t('monitoramento.columns.sessions')}</TableHead>
                      <TableHead className="text-right">{t('monitoramento.columns.upfIn')}</TableHead>
                      <TableHead className="text-right">{t('monitoramento.columns.upfOut')}</TableHead>
                      <TableHead className="text-right" title={t('monitoramento.ambrAggregateHint')}>{t('monitoramento.ambrAggregate')}</TableHead>
                      <TableHead className="text-right">QOS</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {net.slices.map((s) => (
                      <TableRow key={s.id}>
                        <TableCell>
                          <span className="inline-flex items-center gap-2">
                            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: sliceColor(s.id) }} />
                            {t('common.sliceN', { id: s.id })}
                          </span>
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">{s.ue_count ?? '—'}</TableCell>
                        <TableCell>
                          <span className="inline-flex items-center gap-1.5 text-sm">
                            <span
                              className="h-1.5 w-1.5 rounded-full"
                              style={{ backgroundColor: s.ping_ok == null ? '#64748B' : s.ping_ok ? '#0633FF' : '#FF3B5C' }}
                            />
                            {s.ping_ok == null ? '—' : s.ping_ok ? 'ok' : t('monitoramento.noResponse')}
                          </span>
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">{fmt(s.rtt_ms, 3)}</TableCell>
                        <TableCell className="text-right font-mono text-sm">{fmt(s.sessions, 0)}</TableCell>
                        <TableCell className="text-right font-mono text-sm">{fmt(s.upf_in_pps)}</TableCell>
                        <TableCell className="text-right font-mono text-sm">{fmt(s.upf_out_pps)}</TableCell>
                        <TableCell className="text-right font-mono text-sm">{s.ambr_down_mbps} / {s.ambr_up_mbps}</TableCell>
                        <TableCell className="text-right font-mono text-sm">{s.qos_index}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            </section>
 
            <ChartGrid tab="geral" data={series} only={only} />
          </TabsContent>
 
          <TabsContent value="rede"><ChartGrid tab="rede" data={series} only={only} /></TabsContent>
          <TabsContent value="controle"><ChartGrid tab="controle" data={series} only={only} /></TabsContent>
 
          <TabsContent value="nfs">
            {!nfs ? (
              <Skeleton className="h-64" />
            ) : 'reason' in nfs ? (
              <p className="text-sm text-muted-foreground">{t('monitoramento.nfsUnavailable', { reason: nfs.reason })}</p>
            ) : (
              <Card className="px-3 py-2">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>NF</TableHead>
                      <TableHead>{t('monitoramento.columns.instance')}</TableHead>
                      <TableHead>{t('common.columns.status')}</TableHead>
                      <TableHead className="text-right">{t('monitoramento.columns.memory')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {nfs.nfs.map((f) => (
                      <TableRow key={`${f.job}-${f.instance}`}>
                        <TableCell className="font-mono text-sm uppercase">{f.job}</TableCell>
                        <TableCell className="font-mono text-xs">{f.instance}</TableCell>
                        <TableCell>
                          <span className="inline-flex items-center gap-1.5 text-sm">
                            <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: f.up ? '#0633FF' : '#FF3B5C' }} />
                            {f.up ? 'up' : 'down'}
                          </span>
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">{fmt(f.memory_mb, 1)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            )}
          </TabsContent>
        </Tabs>
      )}
 
      <Card>
        <CardHeader>
          <button className="flex items-center gap-2 text-left" onClick={() => setShowLog(!logOpen)}>
            {logOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            <CardTitle className="text-xs tracking-wide text-muted-foreground">
              {run.status === 'stopping' ? t('monitoramento.downLog') : t('common.upLog')}
            </CardTitle>
          </button>
        </CardHeader>
        {logOpen && (
          <CardContent>
            <pre ref={logRef} className="max-h-72 overflow-auto rounded-md bg-muted p-3 font-mono text-xs whitespace-pre-wrap">
              {lines.length ? lines.join('\n') : t('common.waitingLog')}
            </pre>
          </CardContent>
        )}
      </Card>
    </div>
  )
}
 
