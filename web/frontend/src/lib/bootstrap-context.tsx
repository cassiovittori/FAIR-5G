import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { bootstrapStatus, type BootstrapStatus } from "@/lib/api"
import { useAuth } from "@/lib/auth"

interface BootstrapContextType {
  status: BootstrapStatus | null
  checking: boolean
  refresh: () => Promise<void>
}

const BootstrapContext = createContext<BootstrapContextType | null>(null)

export function BootstrapProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [status, setStatus] = useState<BootstrapStatus | null>(null)
  const [checking, setChecking] = useState(true)

  async function refresh() {
    try {
      setStatus(await bootstrapStatus())
    } catch {
      setStatus(null) // falha de rede aqui é tratada como "não confirmado" -> gate manda pro /bootstrap
    } finally {
      setChecking(false)
    }
  }

  useEffect(() => {
    if (user) refresh() // só checa depois que o login resolveu
  }, [user])

  return (
    <BootstrapContext.Provider value={{ status, checking, refresh }}>
      {children}
    </BootstrapContext.Provider>
  )
}

export function useBootstrap() {
  const ctx = useContext(BootstrapContext)
  if (!ctx) throw new Error("useBootstrap must be used within BootstrapProvider")
  return ctx
}