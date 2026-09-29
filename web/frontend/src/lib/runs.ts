import type { Run } from '@/lib/api'

export function environmentLabel(run: Run) {
  const nome = run.nome?.trim()
  if (nome) return nome
  return `Ambiente — ${run.slice_count} fatia${run.slice_count === 1 ? '' : 's'}`
}

// o SQLite pode devolver datetime sem timezone; assume UTC
function parseDate(iso: string) {
  return new Date(/([zZ]|[+-]\d\d:?\d\d)$/.test(iso) ? iso : iso + 'Z')
}

export function fmtDateTime(iso: string | null) {
  if (!iso) return '—'
  return parseDate(iso).toLocaleString('pt-BR', {
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

// eslint-disable-next-line no-control-regex
const ANSI = /\x1b\[[0-9;?]*[A-Za-z]/g
export const stripAnsi = (s: string) => s.replace(ANSI, '')