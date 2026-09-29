import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { StatusDot } from '@/components/StatusDot'
import { listRuns, stopEnvironment, type Run } from '@/lib/api'
import { environmentLabel, fmtDateTime, fmtDuration } from '@/lib/runs'

const PAGE = 20
const BUSY: Run['status'][] = ['starting', 'running', 'stopping']

type Filter = 'all' | 'stopped' | 'error'

export default function PesquisadorAmbientes({ onlyActive = false }: { onlyActive?: boolean }) {
  const [runs, setRuns] = useState<Run[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [stopping, setStopping] = useState(false)
  const [filter, setFilter] = useState<Filter>('all')
  const [visible, setVisible] = useState(PAGE)

  async function load() {
    try {
      setRuns(await listRuns())
      setError(null)
    } catch {
      setError('Não foi possível carregar os ambientes agora.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  // polling só enquanto algum ambiente está subindo ou descendo
  const inTransition = runs?.some((r) => r.status === 'starting' || r.status === 'stopping') ?? false
  useEffect(() => {
    if (!inTransition) return
    const interval = setInterval(load, 3000)
    return () => clearInterval(interval)
  }, [inTransition])

  const shown = useMemo(
    () =>
      (runs ?? []).filter((r) => {
        if (onlyActive) return BUSY.includes(r.status)
        if (filter === 'stopped') return r.status === 'stopped'
        if (filter === 'error') return r.status === 'error'
        return true
      }),
    [runs, onlyActive, filter]
  )

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
    <div className="space-y-6 p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">{onlyActive ? 'Ambientes ativos' : 'Todos os ambientes'}</h1>
          <p className="text-sm text-muted-foreground">
            {onlyActive
              ? 'Ambientes em uso agora. Só um pode existir por vez.'
              : 'Histórico de tudo que já foi criado. Use "Duplicar" para reaproveitar uma configuração.'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!onlyActive && (
            <Select value={filter} onValueChange={(v) => { setFilter(v as Filter); setVisible(PAGE) }}>
              <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="stopped">Encerrados</SelectItem>
                <SelectItem value="error">Com erro</SelectItem>
              </SelectContent>
            </Select>
          )}
          <Button asChild><Link to="/pesquisador/novo">Criar ambiente</Link></Button>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card className="px-3 py-2">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>RUN_ID</TableHead>
              <TableHead>NOME</TableHead>
              <TableHead>STATUS</TableHead>
              <TableHead>CRIADO EM</TableHead>
              <TableHead>DURAÇÃO</TableHead>
              <TableHead className="text-right">AÇÕES</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-36" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-12" /></TableCell>
                  <TableCell className="text-right"><Skeleton className="ml-auto h-4 w-20" /></TableCell>
                </TableRow>
              ))
            ) : shown.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="py-8 text-center text-sm text-muted-foreground">
                  {onlyActive ? 'Nenhum ambiente ativo no momento.' : 'Nenhum ambiente encontrado.'}
                </TableCell>
              </TableRow>
            ) : (
              shown.slice(0, visible).map((run) => (
                <TableRow key={run.run_id}>
                  <TableCell className="font-mono text-xs">
                    <Link to={`/pesquisador/ambientes/${run.run_id}`} className="hover:underline">{run.run_id}</Link>
                  </TableCell>
                  <TableCell>{environmentLabel(run)}</TableCell>
                  <TableCell><StatusDot status={run.status} /></TableCell>
                  <TableCell className="text-sm text-muted-foreground">{fmtDateTime(run.created_at)}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">{fmtDuration(run)}</TableCell>
                  <TableCell className="space-x-3 text-right text-sm">
                    {run.status === 'running' ? (
                      <>
                        <Link to="/pesquisador/monitoramento" className="text-muted-foreground hover:underline">Monitorar</Link>
                        <button onClick={handleStop} disabled={stopping} className="text-[#FF3B5C] hover:underline disabled:opacity-50">Parar</button>
                      </>
                    ) : run.status === 'starting' ? (
                      <Link to="/pesquisador/monitoramento" className="text-muted-foreground hover:underline">Acompanhar</Link>
                    ) : run.status === 'stopping' ? (
                      <span className="text-muted-foreground">—</span>
                    ) : (
                      <>
                        <Link to={`/pesquisador/ambientes/${run.run_id}`} className="text-muted-foreground hover:underline">Ver</Link>
                        <Link to={`/pesquisador/novo?from=${run.run_id}`} className="text-muted-foreground hover:underline">Duplicar</Link>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        {shown.length > visible && (
          <div className="border-t p-3 text-center">
            <Button variant="ghost" onClick={() => setVisible((v) => v + PAGE)}>
              Mostrar mais ({shown.length - visible} restantes)
            </Button>
          </div>
        )}
      </Card>
    </div>
  )
}