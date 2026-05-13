// BASE se resuelve por variable de entorno de Vite. Dev (sin .env) cae a localhost;
// prod (.env.production) apunta a Railway. Documentado en CLAUDE.md §6.
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://127.0.0.1:8000'

function getToken(): string | null {
  try {
    const raw = localStorage.getItem('zaris_session')
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed?.state?.accessToken ?? parsed?.access_token ?? null
  } catch {
    return null
  }
}

type ParamValue = string | number | boolean | null | undefined
type Params = Record<string, ParamValue>

function buildQuery(params?: Params): string {
  if (!params) return ''
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined || v === '') continue
    sp.append(k, String(v))
  }
  const qs = sp.toString()
  return qs ? `?${qs}` : ''
}

export interface ApiOptions {
  params?: Params
  /** When true, also return response headers (e.g. X-Total-Count). */
  withHeaders?: boolean
}

export interface ApiResponseWithHeaders<T> {
  data: T
  headers: Headers
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  opts: ApiOptions = {},
): Promise<T | ApiResponseWithHeaders<T>> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string>),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const url = `${BASE}${path}${buildQuery(opts.params)}`
  const res = await fetch(url, { ...init, headers })

  if (res.status === 401) {
    localStorage.removeItem('zaris_session')
    // Si vivimos en iframe del shell vanilla (prod), redirigir el parent al
    // login del shell. Si estamos standalone (localhost:5173 dev), al /login interno.
    if (typeof window !== 'undefined' && window.self !== window.top) {
      try {
        ;(window.parent as Window).location.href = (window.parent.location.pathname.match(/^\/[^/]+\//)?.[0] ?? '/') + 'frontend/login.html'
      } catch {
        window.location.href = '/login'
      }
    } else {
      window.location.href = '/login'
    }
    throw new Error('No autenticado')
  }

  if (res.status === 204) {
    return opts.withHeaders
      ? ({ data: undefined as T, headers: res.headers } as ApiResponseWithHeaders<T>)
      : (undefined as unknown as T)
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const msg = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail ?? err)
    throw new Error(msg || 'Error desconocido')
  }

  const data = (await res.json()) as T
  return opts.withHeaders
    ? ({ data, headers: res.headers } as ApiResponseWithHeaders<T>)
    : data
}

export const api = {
  get:    <T>(path: string, opts: ApiOptions = {}) =>
    request<T>(path, { method: 'GET' }, opts) as Promise<T>,
  getWithHeaders: <T>(path: string, opts: ApiOptions = {}) =>
    request<T>(path, { method: 'GET' }, { ...opts, withHeaders: true }) as Promise<ApiResponseWithHeaders<T>>,
  post:   <T>(path: string, body?: unknown, opts: ApiOptions = {}) =>
    request<T>(path, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined }, opts) as Promise<T>,
  put:    <T>(path: string, body?: unknown, opts: ApiOptions = {}) =>
    request<T>(path, { method: 'PUT', body: body !== undefined ? JSON.stringify(body) : undefined }, opts) as Promise<T>,
  patch:  <T>(path: string, body?: unknown, opts: ApiOptions = {}) =>
    request<T>(path, { method: 'PATCH', body: body !== undefined ? JSON.stringify(body) : undefined }, opts) as Promise<T>,
  delete: <T>(path: string, body?: unknown, opts: ApiOptions = {}) =>
    request<T>(path, { method: 'DELETE', body: body !== undefined ? JSON.stringify(body) : undefined }, opts) as Promise<T>,
}
