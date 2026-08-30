import { useQuery } from '@tanstack/react-query'
import { api } from '../../../lib/api'

// Un solo endpoint agregado (GET /api/v1/dashboard/resumen) devuelve conteos
// de las 6 tarjetas + capas geo en una pasada — evita 6 requests sueltas
// contra la latencia Railway<->Supabase (~2s por round trip).

const MINUTO = 60 * 1000

export interface DashboardTarjetas {
  emergencias_activas: number
  reclamos_activos: number
  espacios_disponibles: number
  turnos_otorgados: number
  entradas_emitidas: number
  tramites_abiertos: number
}

export interface GeoReclamo {
  id_reclamo: number
  nro_reclamo: string | null
  estado: string
  prioridad: string | null
  descripcion: string | null
  latitud: number
  longitud: number
  tipo_nombre: string | null
  // Solo en el BI de pendientes (/bi/pendientes-geo): días desde el alta.
  dias_demora?: number | null
}

export interface GeoEmergencia {
  id_emergencia_evento: number
  numero_operativo: string | null
  direccion_evento: string | null
  latitud: number
  longitud: number
  tipo_nombre: string | null
  estado_codigo: string
  estado_nombre: string
}

export interface GeoEspacio {
  id_espacio: number
  nombre: string
  direccion: string | null
  latitud: number
  longitud: number
  atendido: boolean
  turnos_vigentes: number
  entradas_vigentes: number
}

export interface GeoTramite {
  id_tramite: number
  numero_expediente: string
  asunto: string | null
  tipo_nombre: string | null
  estado_etiqueta: string | null
  direccion: string | null
  latitud: number
  longitud: number
}

export interface DashboardResumen {
  tarjetas: DashboardTarjetas
  geo: {
    reclamos: GeoReclamo[]
    emergencias: GeoEmergencia[]
    espacios: GeoEspacio[]
    tramites: GeoTramite[]
  }
}

export function useDashboardResumen() {
  return useQuery({
    queryKey: ['dashboard', 'resumen'],
    queryFn: () => api.get<DashboardResumen>('/api/v1/dashboard/resumen'),
    staleTime: MINUTO,
  })
}

// Identidad del municipio (nombre + logo) para el titulo del tablero.
// Endpoint publico, mismo que consume el topbar del shell vanilla.
export interface IdentidadMunicipio {
  app_nombre: string
  municipio_nombre: string
  municipio_logo_url: string
}

export function useIdentidadMunicipio() {
  return useQuery({
    queryKey: ['config', 'identidad'],
    queryFn: () => api.get<IdentidadMunicipio>('/api/v1/config/identidad'),
    staleTime: 10 * MINUTO,
  })
}
