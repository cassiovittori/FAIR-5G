import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useTranslation } from 'react-i18next'
import { ArrowDownWideNarrow, ArrowUpNarrowWide, ChevronLeft, ChevronRight, ListFilter, Search } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Skeleton } from '@/components/ui/skeleton'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { StatusDot } from '@/components/StatusDot'
import { ApiError, listRuns, stopEnvironment, type Run } from '@/lib/api'
import { useToast } from '@/lib/toast'
import {
  ALL_STATUSES, DEFAULT_FILTERS, MAX_SLICES, environmentLabel, filterRuns, filtersToParams, fmtDateTime, fmtDuration,
  hasActiveFilters, parseFilters, type RunFilters,
} from '@/lib/runs'

const PAGE_SIZES = [10, 20, 50] as const
const BUSY: Run['status'][] = ['starting', 'running', 'stopping']
const SLICE_OPTIONS = Array.from({ length: MAX_SLICES }, (_, i) => i + 1)


export default function PesquisadorAmbientes({ onlyActive = false }: { onlyActive?: boolean }) {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const [runs, setRuns] = useState<Run[] | null>(null)
  const [loading, setLoading] = useState(true)
  // falha ao carregar (texto vem do locale, então troca junto com o idioma); erro ao parar vai para o toast,
  // senão o load() logo em seguida apagaria a mensagem
  const [loadError, setLoadError] = useState<'network' | 'load' | null>(null)
  const toast = useToast()
  const [stopping, setStopping] = useState(false)
  const [pageSize, setPageSize] = useState<number>(PAGE_SIZES[0])
  const [page, setPage] = useState(1)

  const filters = useMemo(() => parseFilters(searchParams), [searchParams])
  const filtering = !onlyActive && hasActiveFilters(filters)
  // a busca fica exposta; o contador do botão só conta o que está dentro do menu
  const menuFilterCount =
    (filters.statuses.length ? 1 : 0) + (filters.from || filters.to ? 1 : 0) + (filters.slices != null ? 1 : 0)

  function updateFilters(patch: Partial<RunFilters>) {
    setSearchParams(filtersToParams({ ...filters, ...patch }), { replace: true })
    setPage(1)
  }

  const clearFilters = () => updateFilters({ ...DEFAULT_FILTERS, order: filters.order })

  function toggleStatus(status: Run['status']) {
    updateFilters({
      statuses: filters.statuses.includes(status)
        ? filters.statuses.filter((s) => s !== status)
        : [...filters.statuses, status],
    })
  }

  async function load() {
    try {
      setRuns(await listRuns())
      setLoadError(null)
    } catch (err) {
      setLoadError(err instanceof ApiError && err.code === 'network_error' ? 'network' : 'load')
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
    () => filterRuns(runs ?? [], onlyActive ? { ...DEFAULT_FILTERS, statuses: BUSY } : filters),
    [runs, onlyActive, filters]
  )

  // a lista pode encolher (polling, filtro): a página atual é limitada ao total, sem effect
  const pages = Math.max(1, Math.ceil(shown.length / pageSize))
  const currentPage = Math.min(page, pages)

  async function handleStop() {
    setStopping(true)
    try {
      await stopEnvironment()
      await load()
    } catch(err) {
      toast.error(err instanceof Error ? err.message : t('ambientes.stopError'))
      await load()
    } finally {
      setStopping(false)
    }
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">{onlyActive ? t('ambientes.titleActive') : t('ambientes.titleAll')}</h1>
          <p className="text-sm text-muted-foreground">
            {onlyActive ? t('ambientes.subtitleActive') : t('ambientes.subtitleAll')}
          </p>
        </div>
        <Button asChild><Link to="/pesquisador/novo">{t('ambientes.create')}</Link></Button>
      </div>

      {!onlyActive && (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative w-full sm:w-72">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={filters.q}
                onChange={(e) => updateFilters({ q: e.target.value })}
                placeholder={t('ambientes.filters.search')}
                aria-label={t('ambientes.filters.search')}
                className="pl-8"
              />
            </div>

            <Popover>
              <PopoverTrigger asChild>
                <Button variant={menuFilterCount ? 'secondary' : 'outline'} className="gap-2">
                  <ListFilter className="h-4 w-4" />
                  {t('ambientes.filters.filter')}
                  {menuFilterCount > 0 && (
                    <span className="rounded-full bg-[#0633FF] px-1.5 text-xs text-white">{menuFilterCount}</span>
                  )}
                </Button>
              </PopoverTrigger>
              <PopoverContent align="start" className="w-80 space-y-4">
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">{t('ambientes.filters.status')}</p>
                  <div className="flex flex-wrap gap-1">
                    {ALL_STATUSES.map((status) => {
                      const active = filters.statuses.includes(status)
                      return (
                        <Button
                          key={status}
                          size="sm"
                          variant={active ? 'secondary' : 'outline'}
                          aria-pressed={active}
                          onClick={() => toggleStatus(status)}
                        >
                          {t(`status.${status}`)}
                        </Button>
                      )
                    })}
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">{t('ambientes.filters.createdAt')}</p>
                  <div className="grid grid-cols-2 gap-2">
                    <label className="space-y-1 text-xs text-muted-foreground">
                      <span>{t('ambientes.filters.from')}</span>
                      <Input
                        type="date"
                        value={filters.from}
                        max={filters.to || undefined}
                        onChange={(e) => updateFilters({ from: e.target.value })}
                      />
                    </label>
                    <label className="space-y-1 text-xs text-muted-foreground">
                      <span>{t('ambientes.filters.to')}</span>
                      <Input
                        type="date"
                        value={filters.to}
                        min={filters.from || undefined}
                        onChange={(e) => updateFilters({ to: e.target.value })}
                      />
                    </label>
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">{t('ambientes.filters.slices')}</p>
                  <Select
                    value={filters.slices == null ? 'any' : String(filters.slices)}
                    onValueChange={(v) => updateFilters({ slices: v === 'any' ? null : Number(v) })}
                  >
                    <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="any">{t('ambientes.filters.anySlices')}</SelectItem>
                      {SLICE_OPTIONS.map((n) => (
                        <SelectItem key={n} value={String(n)}>{t('ambientes.filters.slicesOption', { count: n })}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </PopoverContent>
            </Popover>

            {filtering && (
              <Button variant="ghost" onClick={clearFilters}>{t('ambientes.filters.clear')}</Button>
            )}

            <Button
              variant="outline"
              className="ml-auto gap-2"
              onClick={() => updateFilters({ order: filters.order === 'newest' ? 'oldest' : 'newest' })}
              title={t('ambientes.filters.toggleOrder')}
            >
              {filters.order === 'newest' ? <ArrowDownWideNarrow className="h-4 w-4" /> : <ArrowUpNarrowWide className="h-4 w-4" />}
              {filters.order === 'newest' ? t('ambientes.filters.newest') : t('ambientes.filters.oldest')}
            </Button>
          </div>
        </div>
      )}

      {loadError && (
        <p role="alert" className="text-sm text-destructive">
          {loadError === 'network' ? t('errors.network_error') : t('ambientes.loadError')}
        </p>
      )}

      <Card className="px-3 py-2">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('ambientes.columns.runId')}</TableHead>
              <TableHead>{t('ambientes.columns.name')}</TableHead>
              <TableHead>{t('ambientes.columns.status')}</TableHead>
              <TableHead>{t('ambientes.columns.createdAt')}</TableHead>
              <TableHead>{t('ambientes.columns.duration')}</TableHead>
              <TableHead className="text-right">{t('ambientes.columns.actions')}</TableHead>
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
                  {filtering ? (
                    <div className="space-y-2">
                      <p>{t('ambientes.empty.noMatch')}</p>
                      <Button variant="ghost" size="sm" onClick={clearFilters}>{t('ambientes.filters.clear')}</Button>
                    </div>
                  ) : onlyActive ? t('ambientes.empty.noneActive') : t('ambientes.empty.none')}
                </TableCell>
              </TableRow>
            ) : (
              shown.slice((currentPage - 1) * pageSize, currentPage * pageSize).map((run) => (
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
                        <Link to="/pesquisador/monitoramento" className="text-muted-foreground hover:underline">{t('ambientes.actions.monitor')}</Link>
                        <button onClick={handleStop} disabled={stopping} className="text-[#FF3B5C] hover:underline disabled:opacity-50">{t('ambientes.actions.stop')}</button>
                      </>
                    ) : run.status === 'starting' ? (
                      <Link to="/pesquisador/monitoramento" className="text-muted-foreground hover:underline">{t('ambientes.actions.follow')}</Link>
                    ) : run.status === 'stopping' ? (
                      <span className="text-muted-foreground">—</span>
                    ) : (
                      <>
                        <Link to={`/pesquisador/ambientes/${run.run_id}`} className="text-muted-foreground hover:underline">{t('ambientes.actions.view')}</Link>
                        <Link to={`/pesquisador/novo?from=${run.run_id}`} className="text-muted-foreground hover:underline">{t('ambientes.actions.duplicate')}</Link>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        {!loading && runs && (!onlyActive || pages > 1) && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t px-2 pt-3 pb-1 text-xs text-muted-foreground">
            {!onlyActive ? (
              <span>{t('ambientes.count', { count: runs.length, shown: shown.length })}</span>
            ) : <span />}

            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2">
                {t('ambientes.pagination.perPage')}
                <Select value={String(pageSize)} onValueChange={(v) => { setPageSize(Number(v)); setPage(1) }}>
                  <SelectTrigger size="sm" className="w-18"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PAGE_SIZES.map((n) => (
                      <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </label>

              <div className="flex items-center gap-1">
                <span className="mr-1">{t('ambientes.pagination.pageOf', { page: currentPage, pages })}</span>
                <Button
                  variant="outline" size="icon-sm"
                  onClick={() => setPage(currentPage - 1)} disabled={currentPage <= 1}
                  aria-label={t('ambientes.pagination.previous')} title={t('ambientes.pagination.previous')}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline" size="icon-sm"
                  onClick={() => setPage(currentPage + 1)} disabled={currentPage >= pages}
                  aria-label={t('ambientes.pagination.next')} title={t('ambientes.pagination.next')}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
