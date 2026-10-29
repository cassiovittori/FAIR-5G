import { createContext, useContext } from 'react'

export interface ToastApi {
  error: (message: string) => void
  success: (message: string) => void
}

export const ToastContext = createContext<ToastApi | null>(null)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
