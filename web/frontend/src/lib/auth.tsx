import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { getToken, clearToken, login as apiLogin, me as apiMe, UNAUTHORIZED_EVENT, type User } from "@/lib/api"
import { useToast } from "@/lib/toast"

interface AuthContextType {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const toast = useToast()

  // qualquer 401 com token (expirado, usuário removido...): desloga, o ProtectedRoute leva
  // para o login e o aviso diz o motivo. Vários 401 juntos: só o primeiro ainda acha o token.
  useEffect(() => {
    function onUnauthorized(e: Event) {
      if (!getToken()) return
      clearToken()
      setUser(null)
      toast.error((e as CustomEvent<string>).detail)
    }
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [toast])

  useEffect(() => {
    if (!getToken()) {
      setLoading(false)
      return
    }
    apiMe()
      .then(setUser)
      // 401 já desloga pelo UNAUTHORIZED_EVENT; backend fora do ar não apaga o token
      // (cai no login, e o próximo carregamento entra sozinho quando ele voltar)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function login(email: string, password: string) {
    await apiLogin(email, password)
    setUser(await apiMe())
  }

  function logout() {
    clearToken()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within AuthProvider")
  return ctx
}