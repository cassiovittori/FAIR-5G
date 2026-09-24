import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
//import { Separator } from '@/components/ui/separator'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { listRuns, hostMetrics, stopEnvironment, type Run, type HostMetrics } from '@/lib/api'

const STATUS_LABEL: Record<Run['status'], string> = {
  created: 'criado', running: 'ativo', stopping: 'encerrando', stopped: 'encerrado', error: 'erro',
}
const STATUS_COLOR: Record<Run['status'], string> = {
  created: '#64748B', running: '#0633FF', stopping: '#F5A623', stopped: '#64748B', error: '#FF3B5C',
}

function StatusDot({ status }: { status: Run['status'] }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: STATUS_COLOR[status] }} />
      {STATUS_LABEL[status]}
    </span>
  )
}

// backend ainda não tem campo "nome" no Run -- usando slice_count até decidirmos se cria um
function environmentLabel(run: Run) {
  return `Ambiente — ${run.slice_count} fatia${run.slice_count === 1 ? '' : 's'}`
}

export default function PesquisadorHome() {
  const [runs, setRuns] = useState<Run[] | null>(null)
  const [metrics, setMetrics] = useState<HostMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [stopping, setStopping] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const [runsData, metricsData] = await Promise.all([listRuns(), hostMetrics()])
      setRuns(runsData)
      setMetrics(metricsData)
    } catch {
      setError('Não foi possível carregar os dados do Pesquisador agora.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

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
  const recent = runs?.slice(0, 5) ?? []

  async function handleStop() {
    setStopping(true)
    try {
      await stopEnvironment()
      await load()
    } catch {
      setError('Falha ao parar o ambiente.')
    } finally {
      setStopping(false)
    }
  }

  return (
    <div className="space-y-8 p-6">
      <Card className="flex justify-between overflow-hidden p-8">
        <div className="max-w-xl space-y-2">
          <p className="text-sm text-muted-foreground">Olá, Usuário</p>
          <h1 className="text-2xl font-semibold">Bem vindo ao <span className="font-mono">FAIR-5G</span></h1>
          <p className="text-sm text-muted-foreground">
            O FAIR-5G é uma plataforma de pesquisa voltada para criação e gerenciamento de ambientes
            de rede 5G. Configure novos ambientes de teste em poucos passos, acompanhe o status do
            sistema em tempo real e conte com um guia integrado.
          </p>
        </div>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <section className="space-y-3">
        <h2 className="text-xs font-medium tracking-wide text-muted-foreground">AMBIENTES RECENTES</h2>
        <Card className='pt-2 px-3 pb-0 gap-0'>
            <Table>
            <TableHeader>
                <TableRow>
                <TableHead>RUN_ID</TableHead>
                <TableHead>NOME</TableHead>
                <TableHead>STATUS</TableHead>
                <TableHead className="text-right">AÇÕES</TableHead>
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
                    Nenhum ambiente criado ainda.
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
                            <Link to="/pesquisador/monitoramento" className="text-muted-foreground hover:underline">Monitorar</Link>
                            <button onClick={handleStop} disabled={stopping} className="text-[#FF3B5C] hover:underline disabled:opacity-50">Parar</button>
                        </>
                        ) : (
                        <>
                            <Link to={`/pesquisador/ambientes/${run.run_id}`} className="text-muted-foreground hover:underline">Ver</Link>
                            <Link to="/pesquisador/novo" className="text-muted-foreground hover:underline">Duplicar</Link>
                        </>
                        )}
                    </TableCell>
                    </TableRow>
                ))
                )}
            </TableBody>
            </Table>
            <div className="flex items-center justify-between border-t p-4">
            <Button asChild><Link to="/pesquisador/novo">Criar ambiente</Link></Button>
            <Link to="/pesquisador/ambientes" className="text-sm text-muted-foreground hover:underline">Ver todos ›</Link>
            </div>
        </Card>
        </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
            <CardHeader>
                <CardTitle className="text-xs tracking-wide text-muted-foreground">AMBIENTE ATIVO</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                {loading ? (
                <div className="space-y-3">
                    <Skeleton className="h-8 w-32" />
                    <Skeleton className="h-9 w-full" />
                </div>
                ) : active.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nenhum ambiente ativo no momento.</p>
                ) : (
                <>
                    <div className="space-y-1">
                    <p className="text-l font-semibold">{active[0].run_id}</p>
                    <StatusDot status={active[0].status} />
                    </div>
                    <div className="flex gap-2">
                    <Button asChild className="flex-1">
                        <Link to="/pesquisador/monitoramento">Monitorar</Link>
                    </Button>
                    <Button variant="outline" className="flex-1 hover:!border-destructive hover:!bg-destructive hover:!text-destructive-foreground" onClick={handleStop} disabled={stopping}>
                        {stopping ? "Parando..." : "Parar"}
                    </Button>
                    </div>
                </>
                )}
            </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-xs tracking-wide text-muted-foreground">STATUS GERAL DO SISTEMA</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1">
              <div className="flex justify-between text-sm"><span>CPU do host</span><span>{metrics ? `${Math.round(metrics.cpu_percent)}%` : '—'}</span></div>
              <Progress value={metrics?.cpu_percent ?? 0} />
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-sm"><span>Memória</span><span>{metrics ? `${Math.round(metrics.memory_percent)}%` : '—'}</span></div>
              <Progress value={metrics?.memory_percent ?? 0} />
            </div>
            <div className="flex justify-between text-sm">
              <span>Últimos alertas</span>
              <span className="text-[#0633FF]">-</span>
            </div>
          </CardContent>
        </Card>

        <Card className="flex flex-col items-center justify-center gap-2 p-6 text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted text-sm">?</div>
          <CardTitle className="text-sm">Primeiros passos</CardTitle>
          <CardDescription className="text-xs">Precisa de ajuda? Acesse o guia e veja como configurar seu primeiro ambiente.</CardDescription>
          <Link to="/pesquisador/guia" className="text-xs text-muted-foreground hover:underline">Guia ›</Link>
        </Card>
      </div>
    </div>
  )
}