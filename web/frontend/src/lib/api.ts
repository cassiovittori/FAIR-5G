const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

const TOKEN_KEY = "fair5g_token"

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })

  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail ?? `Erro ${res.status}`)
  }

  return res.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
}

// Login ---------------------------------

export async function login(email: string, password: string) {
  const body = new URLSearchParams()
  body.set("username", email)
  body.set("password", password)

  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  })

  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail ?? "Falha no login")
  }

  const data = await res.json()
  setToken(data.access_token)
  return data
}

export interface User {
  id: number
  email: string
  role: string
}

export async function me(): Promise<User> {
  return api.get<User>("/auth/me")
}

// Bootstrap ---------------------------------
export interface BootstrapStatus {
  bootstrapped: boolean
  checks: { docker: boolean; mn: boolean; openflow: boolean }
}

export async function bootstrapStatus(): Promise<BootstrapStatus> {
  const res = await fetch(`${API_URL}/bootstrap/status`)
  if (!res.ok) throw new Error("falha ao consultar status do bootstrap")
  return res.json()
}

export async function runBootstrap(force = false): Promise<{ status: string; message?: string }> {
  const res = await fetch(`${API_URL}/bootstrap?force=${force}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` },
  })
  if (!res.ok) throw new Error("falha ao iniciar bootstrap")
  return res.json()
}

// lê o SSE via fetch (EventSource não manda Authorization header)
export function streamBootstrapLogs(
  onLine: (line: string) => void,
  onDone: () => void
): () => void {
  const controller = new AbortController()

  fetch(`${API_URL}/logs/bootstrap`, {
    headers: { Authorization: `Bearer ${getToken()}` },
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.body) return
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const events = buffer.split("\n\n")
        buffer = events.pop() ?? ""
        for (const evt of events) {
          if (evt.startsWith("data: ")) {
            const line = evt.slice(6)
            onLine(line)
            if (line.startsWith("Script done on")) {
              onDone()
              return
            }
          }
        }
      }
      onDone()
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        console.error("stream de log do bootstrap caiu:", err)
        onDone()
      }
    })

  return () => controller.abort() // cleanup no unmount
}

//Runs
export interface Run {
  id: number
  run_id: string
  status: "created" | "running" | "stopping" | "stopped" | "error"
  created_at: string
  started_at: string | null
  stopped_at: string | null
  slice_count: number
  log_path: string
}

export async function listRuns(): Promise<Run[]> {
  const res = await fetch(`${API_URL}/runs`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  })
  if (!res.ok) throw new Error("falha ao listar ambientes")
  return res.json()
}

export interface HostMetrics {
  cpu_percent: number
  memory_percent: number
}

export async function hostMetrics(): Promise<HostMetrics> {
  const res = await fetch(`${API_URL}/metrics/host`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  })
  if (!res.ok) throw new Error("falha ao consultar métricas do host")
  return res.json()
}

export async function stopEnvironment(): Promise<{ run_id: string; status: string }> {
  const res = await fetch(`${API_URL}/down`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` },
  })
  if (!res.ok) throw new Error("falha ao parar o ambiente")
  return res.json()
}