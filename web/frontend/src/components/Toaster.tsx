import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckCircle2, X, XCircle } from 'lucide-react'
import { ToastContext, type ToastApi } from '@/lib/toast'

type Kind = 'error' | 'success'
interface Toast { id: number; kind: Kind; message: string }

const DURATION_MS = 6000
const MAX_TOASTS = 3

// avisos de resultado de ações (parar, limpar...): ficam visíveis mesmo quando a tela
// recarrega os dados logo depois, o que apagaria uma mensagem inline
export function ToastProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(0)

  const dismiss = useCallback((id: number) => setToasts((prev) => prev.filter((x) => x.id !== id)), [])

  const push = useCallback((kind: Kind, message: string) => {
    const id = ++nextId.current
    setToasts((prev) => [
      // a mesma mensagem duas vezes (ex.: vários 401 ao mesmo tempo) vira uma só
      ...prev.filter((x) => x.message !== message).slice(-(MAX_TOASTS - 1)),
      { id, kind, message },
    ])
    setTimeout(() => dismiss(id), DURATION_MS)
  }, [dismiss])

  const api = useMemo<ToastApi>(() => ({
    error: (message) => push('error', message),
    success: (message) => push('success', message),
  }), [push])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[calc(100%-2rem)] max-w-sm flex-col gap-2">
        {toasts.map((x) => (
          <div
            key={x.id}
            role={x.kind === 'error' ? 'alert' : 'status'}
            className={`pointer-events-auto flex items-start gap-2 rounded-lg border bg-popover p-3 text-sm text-popover-foreground shadow-lg ${
              x.kind === 'error' ? 'border-destructive/50' : ''
            }`}
          >
            {x.kind === 'error'
              ? <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
              : <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#22C55E]" />}
            <p className="flex-1">{x.message}</p>
            <button
              onClick={() => dismiss(x.id)}
              aria-label={t('common.close')}
              className="rounded text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
