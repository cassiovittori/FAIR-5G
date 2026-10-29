import i18n from "@/i18n"

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

export class ApiError extends Error {
  status: number
  code?: string
  params?: Record<string, unknown>
  constructor(message: string, status: number, code?: string, params?: Record<string, unknown>) {
    super(message)
    this.status = status
    this.code = code
    this.params = params
  }
}

// código do backend -> texto no idioma atual (chave `errors.<code>`); sem a chave, null
function translateCode(code: string, params: Record<string, unknown> = {}): string | null {
  const key = `errors.${code}`
  if (!i18n.exists(key)) return null
  // chave dinâmica: o t tipado só aceita chaves literais. O param `context` escolhe a
  // variante da chave (errors.run_busy_starting...)
  const t = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string
  return t(key, params)
}

interface ErrorDetail { code: string; params?: Record<string, unknown>; message?: string }
const isErrorDetail = (d: unknown): d is ErrorDetail =>
  typeof d === "object" && d != null && !Array.isArray(d) && typeof (d as ErrorDetail).code === "string"

// Formato do backend: {detail: {code, params, message}} (ver web/backend/errors.py).
// Também aceita o formato antigo: `detail` string (proxy, backend antigo) ou lista (422 antigo do pydantic).
// `fallback` substitui o "Erro <status>" genérico quando a resposta não diz nada legível.
export async function parseErrorResponse(res: Response, fallback?: string): Promise<ApiError> {
  const body = await res.json().catch(() => null)
  const detail = (body as { detail?: unknown } | null)?.detail
  const generic = fallback ?? i18n.t("common.httpError", { status: res.status })

  if (isErrorDetail(detail)) {
    const params = { ...(detail.params ?? {}) }
    if (detail.code === "validation_error") {
      const errors = Array.isArray(params.errors) ? (params.errors as { field?: string }[]) : []
      params.fields = errors.map((e) => e.field).filter(Boolean).join(", ")
    }
    const message = translateCode(detail.code, params) ?? detail.message ?? translateCode("unknown") ?? generic
    return new ApiError(message, res.status, detail.code, params)
  }
  if (typeof detail === "string") return new ApiError(detail, res.status)
  return new ApiError(generic, res.status)
}

// erro ao CARREGAR dados de uma tela: sem conexão diz o motivo; o resto fica com o texto da própria tela
// (ex.: "Não foi possível carregar os ambientes agora.")
export const loadErrorMessage = (err: unknown, fallback: string) =>
  err instanceof ApiError && err.code === "network_error" ? err.message : fallback

// `{available: false, reason}` das métricas: traduz pelo reason_code, senão o texto do backend
export const unavailableReason = (r: { reason: string; reason_code?: string }) =>
  (r.reason_code && translateCode(r.reason_code)) || r.reason

// sessão recusada pelo backend (token expirado/inválido): o AuthProvider escuta, desloga e avisa
export const UNAUTHORIZED_EVENT = "fair5g:unauthorized"

// backend fora do ar / sem rede: o fetch lança TypeError com texto do navegador (em inglês)
async function apiFetch(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_URL}${path}`, init)
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err
    throw new ApiError(i18n.t("errors.network_error"), 0, "network_error")
  }
}

async function request<T>(path: string, options: RequestInit = {}, fallback?: string): Promise<T> {
  const token = getToken()

  const res = await apiFetch(path, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })

  if (!res.ok) {
    const err = await parseErrorResponse(res, fallback)
    if (res.status === 401 && token) window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT, { detail: err.message }))
    throw err
  }

  // 204 (DELETE) não tem corpo
  return res.status === 204 ? (undefined as T) : res.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  delete: <T = void>(path: string) => request<T>(path, { method: "DELETE" }),
}

// Login ---------------------------------

export async function login(email: string, password: string) {
  const body = new URLSearchParams()
  body.set("username", email)
  body.set("password", password)

  const res = await apiFetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  })

  // form-urlencoded (OAuth2), por isso não passa pelo request()
  if (!res.ok) throw await parseErrorResponse(res, i18n.t("auth.loginFailed"))

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
  checks: { docker: boolean; mn: boolean; openflow: boolean; ue_image: boolean }
}

export const bootstrapStatus = () =>
  request<BootstrapStatus>("/bootstrap/status", {}, i18n.t("errors.bootstrapStatus"))

export const runBootstrap = (force = false) =>
  request<{ status: string; message?: string }>(`/bootstrap?force=${force}`, { method: "POST" }, i18n.t("bootstrap.startError"))

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

export const listRuns = () => request<Run[]>("/runs", {}, i18n.t("errors.listRuns"))

export interface HostMetrics {
  cpu_percent: number
  memory_percent: number
}

export const hostMetrics = () => request<HostMetrics>("/metrics/host", {}, i18n.t("errors.hostMetrics"))

// "disjuntor": roda o down mesmo sem ambiente registrado. Devolve o caminho do stream de log.
export const forceCleanup = () => request<{ log: string }>("/cleanup", { method: "POST" })

export const stopEnvironment = () =>
  request<{ run_id: string; status: string }>("/down", { method: "POST" }, i18n.t("common.stopError"))

export type UpConfig = Record<string, number | number[]>

// 409 (ambiente em uso) chega como ApiError com status 409: o formulário mostra o card de conflito
export const startEnvironment = (config: UpConfig, nome?: string) =>
  api.post<{ run_id: string }>("/up", nome ? { ...config, nome } : config)

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
  ue_count: number
  ues: { ue: number; ip: string; ping_ok: boolean | null; rtt_ms: number | null }[]
}

export type NetworkMetrics =
  | { available: false; reason: string; reason_code?: string }
  | { available: true; global: { ues: number | null; gnbs: number | null }; slices: SliceMetrics[] }

export const networkMetrics = () => api.get<NetworkMetrics>("/metrics/network")

export interface SeriesPoint { t: number; v: number | null }
// ue só nas métricas por IP de UE (rtt/perda/jitter); ausente nas demais e no histórico de runs antigos
export interface SliceSeries { id: number; ue?: number; points: SeriesPoint[] }

export type NetworkHistory =
  | { available: false; reason: string; reason_code?: string }
  | { available: true; step: number; minutes: number; series: Record<string, SliceSeries[]> }

export const networkHistory = (minutes = 15, metrics?: string[]) =>
  api.get<NetworkHistory>(
    `/metrics/network/history?minutes=${minutes}` + (metrics?.length ? `&metrics=${metrics.join(",")}` : "")
  )

export interface NfStatus { job: string; instance: string; up: boolean; memory_mb: number | null }
export type NetworkNfs =
  | { available: false; reason: string; reason_code?: string }
  | { available: true; nfs: NfStatus[] }

export const networkNfs = () => api.get<NetworkNfs>("/metrics/network/nfs")

// Presets: templates (config nomeada, reutilizável) e rascunhos (form salvo pela metade) ---------------------------------
export type PresetTipo = "template" | "rascunho"

export interface Preset {
  id: number
  tipo: PresetTipo
  nome: string | null           // sempre preenchido em template; rascunho pode não ter
  descricao: string | null
  config: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface PresetCreate {
  tipo: PresetTipo
  nome?: string | null
  descricao?: string | null
  config: Record<string, unknown>
}

// `tipo` não muda depois de criado
export type PresetUpdate = Partial<Pick<PresetCreate, "nome" | "descricao" | "config">>

export const listPresets = (tipo?: PresetTipo) => api.get<Preset[]>(tipo ? `/presets?tipo=${tipo}` : "/presets")
export const getPreset = (id: number | string) => api.get<Preset>(`/presets/${id}`)
export const createPreset = (body: PresetCreate) => api.post<Preset>("/presets", body)
export const updatePreset = (id: number, body: PresetUpdate) => api.put<Preset>(`/presets/${id}`, body)
export const deletePreset = (id: number) => api.delete(`/presets/${id}`)
