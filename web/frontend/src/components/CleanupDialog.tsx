import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckCircle2, Loader2, PowerOff, TriangleAlert, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from '@/components/ui/dialog'
import { forceCleanup, streamLogs } from '@/lib/api'
import { stripAnsi } from '@/lib/runs'

const MAX_LOG_LINES = 500
// última linha do `script`: Script done on ... [COMMAND_EXIT_CODE="0"]
const EXIT_CODE = /COMMAND_EXIT_CODE="(\d+)"/

type Phase = 'confirm' | 'running' | 'success' | 'failed'

// "disjuntor" da barra superior: roda o down mesmo quando nada aparece como ativo
export function CleanupDialog() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [phase, setPhase] = useState<Phase>('confirm')
  const [lines, setLines] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const stopStreamRef = useRef<(() => void) | undefined>(undefined)
  const logRef = useRef<HTMLPreElement>(null)

  useEffect(() => () => stopStreamRef.current?.(), [])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [lines])

  function handleOpenChange(next: boolean) {
    if (phase === 'running') return // não deixa fechar no meio do down
    if (next) {
      setPhase('confirm')
      setLines([])
      setError(null)
    }
    setOpen(next)
  }

  async function handleConfirm() {
    setError(null)
    setLines([])
    setPhase('running')
    try {
      const { log } = await forceCleanup()
      let exitCode: string | null = null
      stopStreamRef.current = streamLogs(
        log,
        (line) => {
          const m = EXIT_CODE.exec(line)
          if (m) exitCode = m[1]
          setLines((prev) => [...prev.slice(-(MAX_LOG_LINES - 1)), stripAnsi(line)])
        },
        () => setPhase(exitCode === '0' ? 'success' : 'failed')
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.unknownError'))
      setPhase('confirm')
    }
  }

  const running = phase === 'running'

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5 hover:border-destructive hover:text-destructive">
          <PowerOff className="h-3.5 w-3.5" />
          {t('cleanup.button')}
        </Button>
      </DialogTrigger>
      <DialogContent
        className="sm:max-w-2xl"
        showCloseButton={!running}
        onEscapeKeyDown={(e) => running && e.preventDefault()}
        onInteractOutside={(e) => running && e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>{t('cleanup.title')}</DialogTitle>
          <DialogDescription>{t('cleanup.description')}</DialogDescription>
        </DialogHeader>

        {phase === 'confirm' ? (
          <p className="flex items-start gap-2 rounded-md border border-[#F5A623]/40 bg-[#F5A623]/10 p-3 text-sm">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-[#F5A623]" />
            {t('cleanup.warning')}
          </p>
        ) : (
          <pre ref={logRef} className="h-72 overflow-auto rounded-md bg-muted p-3 font-mono text-xs whitespace-pre-wrap">
            {lines.length ? lines.join('\n') : t('common.waitingLog')}
          </pre>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}

        {phase === 'running' && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            {t('cleanup.running')}
          </p>
        )}
        {phase === 'success' && (
          <p className="flex items-center gap-2 text-sm">
            <CheckCircle2 className="h-4 w-4 text-[#22C55E]" />
            {t('cleanup.success')}
          </p>
        )}
        {phase === 'failed' && (
          <p className="flex items-center gap-2 text-sm text-destructive">
            <XCircle className="h-4 w-4" />
            {t('cleanup.failed')}
          </p>
        )}

        <DialogFooter>
          {phase === 'confirm' ? (
            <>
              <Button variant="ghost" onClick={() => handleOpenChange(false)}>{t('common.cancel')}</Button>
              <Button variant="destructive" onClick={handleConfirm}>{t('cleanup.confirm')}</Button>
            </>
          ) : (
            <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={running}>{t('common.close')}</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
