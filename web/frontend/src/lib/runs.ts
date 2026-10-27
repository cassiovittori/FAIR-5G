import type { Run } from '@/lib/api'
import i18n, { currentLocale } from '@/i18n'
import { CAMPOS } from '@/lib/up-fields'

export function environmentLabel(run: Run) {
  const nome = run.nome?.trim()
  if (nome) return nome
  return i18n.t('environment.defaultName', { count: run.slice_count })
}

// o SQLite pode devolver datetime sem timezone; assume UTC
export function parseDate(iso: string) {
  return new Date(/([zZ]|[+-]\d\d:?\d\d)$/.test(iso) ? iso : iso + 'Z')
}

export function fmtDateTime(iso: string | null) {
  if (!iso) return '—'
  return parseDate(iso).toLocaleString(currentLocale(), {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

export function fmtDuration(run: Run) {
  if (!run.started_at) return '—'
  const busy = run.status === 'starting' || run.status === 'running' || run.status === 'stopping'
  const end = run.stopped_at ? parseDate(run.stopped_at) : busy ? new Date() : null
  if (!end) return '—'
  const s = Math.max(0, Math.round((end.getTime() - parseDate(run.started_at).getTime()) / 1000))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h) return `${h}h ${m}min`
  if (m) return `${m}min`
  return `${s}s`
}

export type RunStatus = Run['status']
export const ALL_STATUSES: RunStatus[] = ['starting', 'running', 'stopping', 'stopped', 'error']

// mesmo limite do formulário de criação (CAMPOS.slices); 8 se o campo sumir
export const MAX_SLICES = CAMPOS.find((c) => c.nome === 'slices')?.max ?? 8

export interface RunFilters {
  q: string
  statuses: RunStatus[]            // vazio = todos
  from: string                     // 'YYYY-MM-DD' (dia local) ou ''
  to: string                       // idem
  slices: number | null
  order: 'newest' | 'oldest'
}
export const DEFAULT_FILTERS: RunFilters = { q: '', statuses: [], from: '', to: '', slices: null, order: 'newest' }

const DAY = /^\d{4}-\d{2}-\d{2}$/
const norm = (s: string) => s.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()
// dia LOCAL: new Date('YYYY-MM-DD') seria meia-noite UTC e erraria 3h no nosso fuso
const localDay = (ymd: string, plusDays = 0) => {
  const [y, m, d] = ymd.split('-').map(Number)
  return new Date(y, m - 1, d + plusDays)
}

export function filterRuns(runs: Run[], f: RunFilters): Run[] {
  const q = norm(f.q.trim())
  const from = DAY.test(f.from) ? localDay(f.from) : null
  const to = DAY.test(f.to) ? localDay(f.to, 1) : null   // limite exclusivo: inclui o dia "até" inteiro
  const out = runs.filter((r) => {
    if (f.statuses.length && !f.statuses.includes(r.status)) return false
    if (f.slices != null && r.slice_count !== f.slices) return false
    if (q && !norm(`${r.run_id} ${environmentLabel(r)}`).includes(q)) return false
    const t = parseDate(r.created_at).getTime()
    if (from && t < from.getTime()) return false
    if (to && t >= to.getTime()) return false
    return true
  })
  const dir = f.order === 'newest' ? -1 : 1
  return out.sort((a, b) => dir * (parseDate(a.created_at).getTime() - parseDate(b.created_at).getTime()))
}

export function parseFilters(p: URLSearchParams): RunFilters {
  const statuses = (p.get('status') ?? '').split(',').filter((s): s is RunStatus => (ALL_STATUSES as string[]).includes(s))
  const slices = Number(p.get('slices'))
  const day = (k: string) => (DAY.test(p.get(k) ?? '') ? (p.get(k) as string) : '')
  return {
    q: p.get('q') ?? '',
    statuses,
    from: day('from'),
    to: day('to'),
    slices: Number.isInteger(slices) && slices >= 1 && slices <= MAX_SLICES ? slices : null,
    order: p.get('order') === 'oldest' ? 'oldest' : 'newest',
  }
}

export function filtersToParams(f: RunFilters): URLSearchParams {
  const p = new URLSearchParams()
  if (f.q) p.set('q', f.q)
  if (f.statuses.length) p.set('status', f.statuses.join(','))
  if (f.from) p.set('from', f.from)
  if (f.to) p.set('to', f.to)
  if (f.slices != null) p.set('slices', String(f.slices))
  if (f.order !== 'newest') p.set('order', f.order)   // padrões não vão para a URL
  return p
}

export const hasActiveFilters = (f: RunFilters) =>
  f.q !== '' || f.statuses.length > 0 || f.from !== '' || f.to !== '' || f.slices != null

// eslint-disable-next-line no-control-regex
const ANSI = /\x1b\[[0-9;?]*[A-Za-z]/g
export const stripAnsi = (s: string) => s.replace(ANSI, '')