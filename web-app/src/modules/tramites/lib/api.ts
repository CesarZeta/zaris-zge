import { api } from '../../../lib/api'
import type {
  TipoTramite,
  TipoTramiteDetalle,
  TramiteBandejaItem,
  TramiteDetalle,
  TramiteMovimiento,
  TramiteDocumento,
  TramiteRelacion,
  TransicionesPermitidas,
  CrearTramiteBody,
  BandejaParams,
} from '../types'

const BASE = '/api/v1/tramites'

/* ── Catálogo de tipos ───────────────────────────────────── */

export const listarTipos = (params?: { iniciador?: string; q?: string }) =>
  api.get<{ items: TipoTramite[]; total: number }>(`${BASE}/tipos`, { params })

export const obtenerTipo = (id: number) =>
  api.get<TipoTramiteDetalle>(`${BASE}/tipos/${id}`)

/* ── Bandeja ─────────────────────────────────────────────── */

export const listarBandeja = (params: BandejaParams) =>
  api.get<{ items: TramiteBandejaItem[]; total: number }>(BASE, { params: params as Record<string, string | number | boolean | null | undefined> })

/* ── Detalle y movimientos ───────────────────────────────── */

export const obtenerTramite = (numeroOId: string | number) =>
  api.get<TramiteDetalle>(`${BASE}/${numeroOId}`)

export const obtenerMovimientos = (numero: string, params?: { limit?: number; offset?: number }) =>
  api.get<{ movimientos: TramiteMovimiento[]; total: number; numero_expediente: string }>(
    `${BASE}/${numero}/movimientos`,
    { params },
  )

export const obtenerTransicionesPermitidas = (numero: string) =>
  api.get<TransicionesPermitidas>(`${BASE}/${numero}/transiciones-permitidas`)

export const obtenerDocumentos = (numero: string) =>
  api.get<TramiteDocumento[]>(`${BASE}/${numero}/documentos`)

/* ── Mutaciones del ciclo de vida ───────────────────────── */

export const crearTramite = (body: CrearTramiteBody) =>
  api.post<TramiteDetalle>(BASE, body)

export const tomarTramite = (numero: string) =>
  api.post<TramiteDetalle>(`${BASE}/${numero}/tomar`)

export const liberarTramite = (numero: string) =>
  api.post<TramiteDetalle>(`${BASE}/${numero}/liberar`)

export const transicionarTramite = (
  numero: string,
  body: { id_tipo_tramite_transicion: number; comentario?: string },
) => api.post<TramiteDetalle>(`${BASE}/${numero}/transicionar`, body)

export const pasarTramite = (
  numero: string,
  body: { destinatario_tipo: 'subarea' | 'equipo'; destinatario_id: number; comentario?: string },
) => api.post<TramiteDetalle>(`${BASE}/${numero}/pase`, body)

export const comentarTramite = (numero: string, comentario: string) =>
  api.post<{ id_tramite_movimiento: number }>(`${BASE}/${numero}/comentar`, { comentario })

export const relacionarTramite = (
  numero: string,
  body: { id_tramite_b: number; comentario?: string },
) => api.post<TramiteRelacion>(`${BASE}/${numero}/relacionar`, body)

/* ── Documentos ──────────────────────────────────────────── */

export function adjuntarDocumento(
  numero: string,
  file: File,
  opts?: {
    id_tipo_tramite_documento_requerido?: number
    nombre?: string
    onProgress?: (pct: number) => void
  },
): Promise<TramiteDocumento> {
  return new Promise((resolve, reject) => {
    const formData = new FormData()
    formData.append('file', file)
    if (opts?.nombre) formData.append('nombre', opts.nombre)
    if (opts?.id_tipo_tramite_documento_requerido != null) {
      formData.append(
        'id_tipo_tramite_documento_requerido',
        String(opts.id_tipo_tramite_documento_requerido),
      )
    }

    const token = getTokenFromStorage()
    const BASE_URL =
      (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://127.0.0.1:8000'

    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE_URL}${BASE}/${numero}/documentos`)
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && opts?.onProgress) {
        opts.onProgress(Math.round((e.loaded / e.total) * 100))
      }
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as TramiteDocumento)
      } else {
        try {
          const err = JSON.parse(xhr.responseText)
          reject(new Error(typeof err.detail === 'string' ? err.detail : xhr.statusText))
        } catch {
          reject(new Error(xhr.statusText))
        }
      }
    }
    xhr.onerror = () => reject(new Error('Error de red al subir el archivo'))
    xhr.send(formData)
  })
}

function getTokenFromStorage(): string | null {
  try {
    const raw = localStorage.getItem('zaris_session')
    if (!raw) return null
    const parsed = JSON.parse(raw) as Record<string, unknown>
    const state = parsed?.state as Record<string, unknown> | undefined
    return (state?.accessToken as string) ?? (parsed?.access_token as string) ?? null
  } catch {
    return null
  }
}

export function descargarDocumentoUrl(numero: string, idDoc: number): string {
  const BASE_URL =
    (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://127.0.0.1:8000'
  const token = getTokenFromStorage()
  return `${BASE_URL}${BASE}/${numero}/documentos/${idDoc}/contenido${token ? `?token=${token}` : ''}`
}

export const firmarDocumento = (
  numero: string,
  idDoc: number,
  body: { id_tramite_firma: number; comentario?: string },
) => api.post(`${BASE}/${numero}/documentos/${idDoc}/firmar`, body)

export const rechazarFirma = (
  numero: string,
  idDoc: number,
  body: { id_tramite_firma: number; motivo: string },
) => api.post(`${BASE}/${numero}/documentos/${idDoc}/rechazar-firma`, body)
