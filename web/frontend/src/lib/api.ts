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
export function streamLogs(
  path: string,
  onLine: (line: string) => void,
  onDone: () => void
): () => void {
  const controller = new AbortController()

  fetch(`${API_URL}${path}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok || !res.body) {
        onDone()
        return
      }
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
        console.error("stream de log caiu:", err)
        onDone()
      }
    })

  return () => controller.abort()
}

export const streamBootstrapLogs = (onLine: (line: string) => void, onDone: () => void) =>
  streamLogs("/logs/bootstrap", onLine, onDone)

//Runs
export interface Run {
  id: number
  run_id: string
  nome: string | null
  status: "created" |"starting"| "running" | "stopping" | "stopped" | "error"
  created_at: string
  started_at: string | null
  stopped_at: string | null
  slice_count: number
  log_path: string
  config: Record<string, unknown> | null
}

export const getRun = (runId: string) => api.get<Run>(`/runs/${runId}`)

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

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export type UpConfig = Record<string, number>

export async function startEnvironment(config: UpConfig, nome?: string): Promise<{ run_id: string }> {
  const res = await fetch(`${API_URL}/up`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify(nome ? { ...config, nome } : config),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    const msg = typeof data?.detail === "string" ? data.detail : `Erro ${res.status}`
    throw new ApiError(msg, res.status)
  }
  return res.json()
}

// Métricas de rede (Prometheus via backend) ---------------------------------
export interface SliceMetrics {
  id: number
  sessions: number | null
  ping_ok: boolean | null
  rtt_ms: number | null
  upf_in_pps: number | null
  upf_out_pps: number | null
  ambr_down_mbps: number
  ambr_up_mbps: number
  qos_index: number
}

export type NetworkMetrics =
  | { available: false; reason: string }
  | { available: true; global: { ues: number | null; gnbs: number | null }; slices: SliceMetrics[] }

export const networkMetrics = () => api.get<NetworkMetrics>("/metrics/network")

export interface SeriesPoint { t: number; v: number | null }
export interface SliceSeries { id: number; points: SeriesPoint[] }

export type NetworkHistory =
  | { available: false; reason: string }
  | { available: true; step: number; minutes: number; series: Record<string, SliceSeries[]> }

export const networkHistory = (minutes = 15, metrics?: string[]) =>
  api.get<NetworkHistory>(
    `/metrics/network/history?minutes=${minutes}` + (metrics?.length ? `&metrics=${metrics.join(",")}` : "")
  )

export interface NfStatus { job: string; instance: string; up: boolean; memory_mb: number | null }
export type NetworkNfs =
  | { available: false; reason: string }
  | { available: true; nfs: NfStatus[] }

export const networkNfs = () => api.get<NetworkNfs>("/metrics/network/nfs")