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
