import { api } from '../../../lib/api'
import type {
  AreaCatalogo,
  TipoCatalogo,
  ReclamoListado,
  ReclamoDetalle,
  ReclamoCreate,
  ReclamoCreateResponse,
  ReclamoUpdate,
  StatsReclamos,
  Adjunto,
} from '../types/reclamo'

const BASE = '/api/v1/reclamos'

export const getStats = () =>
  api.get<StatsReclamos>(`${BASE}/stats`)

export const getCatalogoAreas = () =>
  api.get<AreaCatalogo[]>(`${BASE}/catalogo/areas`)

export const getCatalogoTipos = (params: { id_area?: number; q?: string; limit?: number } = {}) =>
  api.get<TipoCatalogo[]>(`${BASE}/catalogo/tipos`, { params })

export const listarReclamos = (params: {
  estado?: string
  id_area?: number
  prioridad?: string
  texto?: string
  limit?: number
  offset?: number
} = {}) =>
  api.get<ReclamoListado[]>(BASE, { params })

export const obtenerReclamo = (id: number) =>
  api.get<ReclamoDetalle>(`${BASE}/${id}`)

export const listarAdjuntos = (id: number) =>
  api.get<Adjunto[]>(`${BASE}/${id}/adjuntos`)

export const crearReclamo = (data: ReclamoCreate) =>
  api.post<ReclamoCreateResponse>(BASE, data)

export const editarReclamo = (id: number, data: ReclamoUpdate) =>
  api.put<{ ok: boolean; id_reclamo: number; campos: string[] }>(`${BASE}/${id}`, data)

export const cambiarEstadoReclamo = (id: number, body: { estado: string; nota?: string }) =>
  api.put<{ ok: boolean; id_reclamo: number; estado: string }>(`${BASE}/${id}/estado`, body)

export const cancelarReclamo = (id: number, body: { motivo: string }) =>
  api.put<{ ok: boolean; id_reclamo: number; estado: string }>(`${BASE}/${id}/cancelar`, body)

// ── Adjuntos ──

export interface UploadUrlResponse {
  id_adjunto: number
  upload_url: string
  token: string
  storage_path: string
  bucket: string
}

export const crearUploadUrl = (
  idReclamo: number,
  body: { nombre_archivo: string; mime_type: string; tamano_bytes: number; descripcion?: string },
) => api.post<UploadUrlResponse>(`${BASE}/${idReclamo}/adjuntos/upload-url`, body)

export const confirmarAdjunto = (idReclamo: number, idAdjunto: number) =>
  api.post<{ ok: boolean; id_adjunto: number; ya_confirmado?: boolean }>(
    `${BASE}/${idReclamo}/adjuntos/${idAdjunto}/confirm`,
    {},
  )

export const borrarAdjunto = (idReclamo: number, idAdjunto: number) =>
  api.delete<{ ok: boolean; id_adjunto: number }>(`${BASE}/${idReclamo}/adjuntos/${idAdjunto}`)

// ── Geo (proxy a Nominatim via backend) ──

export interface GeoBuscarResult {
  display_name: string
  lat: number | null
  lon: number | null
  type: string | null
  address: Record<string, string>
}

export interface GeoReverseResult {
  display_name: string
  address: Record<string, string>
  lat: number
  lon: number
}

export const geoBuscar = (q: string, limit = 5) =>
  api.get<GeoBuscarResult[]>(`/api/v1/geo/buscar`, { params: { q, limit } })

export const geoReverse = (lat: number, lon: number) =>
  api.get<GeoReverseResult>(`/api/v1/geo/reverse`, { params: { lat, lon } })
