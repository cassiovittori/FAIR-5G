import type { Run } from '@/lib/api'

const STATUS_LABEL: Record<Run['status'], string> = {
  created: 'criado', running: 'ativo', starting: 'sendo criado', stopping: 'encerrando', stopped: 'encerrado', error: 'erro',
}
const STATUS_COLOR: Record<Run['status'], string> = {
  created: '#64748B', running: '#0633FF', starting: '#F5A623', stopping: '#F5A623', stopped: '#64748B', error: '#FF3B5C',
}

export function StatusDot({ status }: { status: Run['status'] }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: STATUS_COLOR[status] }} />
      {STATUS_LABEL[status]}
    </span>
  )
}