import { api, ApiError } from '../../../lib/api'
import type { LimiteMunicipio } from '../../dashboard/hooks/useDashboardData'

// Contorno del municipio (PLAN_CONTORNO_MUNICIPIO_DISENO.md). La depuración la hace el backend
// (services/contorno.py); acá solo se piden y se guardan las vistas.

export interface OrigenContorno {
  via: 'ign' | 'archivo'
  codigo?: string | null
  nombre?: string | null
  fuente?: string | null
  archivo?: string | null
  fecha?: string | null
}

export interface ZonaContorno {
  geo_bbox_centro_lat: string
  geo_bbox_centro_lon: string
  geo_bbox_delta_grados: string
}

export interface ContornoVista {
  geometria: LimiteMunicipio
  partes: number
  vertices_antes: number
  vertices_despues: number
  superficie_km2: number
  recuadro: { sur: number; oeste: number; norte: number; este: number }
  avisos: string[]
  origen: OrigenContorno | null
  zona: ZonaContorno
  aviso_zona?: string | null
}

/** Sección del instructivo que explica un rechazo (coincide con ContornoInvalido.paso del backend). */
export type PasoInstructivo = 'formato' | 'metros' | 'invertido' | 'tipo' | 'pais' | 'tamano' | 'geojsonio' | 'qgis'

/** Dónde vive el contorno: Configuración (el municipio de la sesión), la ficha del super o el alta. */
export type DestinoContorno =
  | { modo: 'config' }
  | { modo: 'ficha'; idMunicipio: number }
  | { modo: 'alta'; idPartido: number | null; codigoPais: string }

const base = (d: DestinoContorno) =>
  d.modo === 'config' ? '/api/v1/contorno' : d.modo === 'ficha' ? `/api/v1/super/municipios/${d.idMunicipio}/contorno` : ''

export const verContorno = (d: Exclude<DestinoContorno, { modo: 'alta' }>) =>
  api.get<{ contorno: ContornoVista | null; codigo_oficial: string | null }>(base(d))

export const previsualizar = (d: DestinoContorno, geojson: string, archivo: string | null) =>
  d.modo === 'alta'
    ? api.post<ContornoVista>('/api/v1/super/contorno/previsualizar', { geojson, archivo, codigo_pais: d.codigoPais })
    : api.post<ContornoVista>(`${base(d)}/previsualizar`, { geojson, archivo })

export const traerOficial = (d: DestinoContorno) =>
  d.modo === 'alta'
    ? api.get<ContornoVista>('/api/v1/super/contorno-oficial', { params: { id_partido: d.idPartido ?? 0 } })
    : api.get<ContornoVista>(`${base(d)}/oficial`)

export const guardarContorno = (d: Exclude<DestinoContorno, { modo: 'alta' }>, geojson: string, origen: OrigenContorno) =>
  api.put<{ contorno: ContornoVista; zona: ZonaContorno }>(base(d), { geojson, origen })

export const quitarContorno = (d: Exclude<DestinoContorno, { modo: 'alta' }>) => api.delete<void>(base(d))

/** El `paso` del instructivo que trae un 422 del contorno, si lo trae. */
export function pasoDelError(e: unknown): PasoInstructivo | null {
  const body = e instanceof ApiError ? (e.body as { paso?: string } | undefined) : undefined
  return (body?.paso as PasoInstructivo | undefined) ?? null
}

/** Texto corto del origen, para mostrar junto al contorno. */
export function textoOrigen(o: OrigenContorno | null): string {
  if (!o) return 'origen sin registrar'
  if (o.via === 'ign') return `Oficial del IGN${o.nombre ? ` (${o.nombre})` : ''}${o.fuente ? ` · fuente: ${o.fuente}` : ''}`
  return `Archivo${o.archivo ? ` «${o.archivo}»` : ''}`
}
