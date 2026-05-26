import { api } from '../../../lib/api'
import type {
  DashboardComentarioItem,
  DashboardEvolucionItem,
  DashboardPorAreaItem,
  DashboardResumen,
  EncuestaEnvio,
  EncuestaEnvioConRespuesta,
  EncuestaRespuesta,
  RespuestaPendienteContacto,
} from './types'

// Todos los paths cuelgan de /api/v1/admin/encuestas (router con guard JWT, §39).
// Los dashboards exigen nivel <= 2 en el backend (_require_supervisor); el modulo
// gatea la UI igual (ver index.tsx).
const BASE = '/api/v1/admin/encuestas'

export interface ResumenParams {
  desde?: string // 'YYYY-MM-DD'
  hasta?: string
  id_area?: number
}

export const encuestasApi = {
  resumen: (p: ResumenParams = {}) =>
    api.get<DashboardResumen>(`${BASE}/dashboard/resumen`, { params: { ...p } }),

  porArea: (p: { desde?: string; hasta?: string; limit?: number } = {}) =>
    api.get<DashboardPorAreaItem[]>(`${BASE}/dashboard/por-area`, { params: { ...p } }),

  evolucion: (p: { meses?: number } = {}) =>
    api.get<DashboardEvolucionItem[]>(`${BASE}/dashboard/evolucion`, { params: { ...p } }),

  comentarios: (p: { clasificacion?: number; limit?: number; offset?: number } = {}) =>
    api.get<DashboardComentarioItem[]>(`${BASE}/dashboard/comentarios`, { params: { ...p } }),

  // pendientes-contacto SIEMPRE devuelve los no-atendidos (solicita_contacto=TRUE
  // AND atendida=FALSE). No hay flag para incluir atendidos — al atender una, sale
  // de la lista. Por eso no exponemos filtro pendiente/atendido acá.
  pendientesContacto: (p: { limit?: number; offset?: number } = {}) =>
    api.get<RespuestaPendienteContacto[]>(`${BASE}/respuestas/pendientes-contacto`, { params: { ...p } }),

  atender: (idRespuesta: number) =>
    api.patch<EncuestaRespuesta>(`${BASE}/respuestas/${idRespuesta}/atender`),

  envios: (p: { estado?: string; limit?: number; offset?: number } = {}) =>
    api.get<EncuestaEnvio[]>(`${BASE}/envios`, { params: { ...p } }),

  envioDetalle: (idEnvio: number) =>
    api.get<EncuestaEnvioConRespuesta>(`${BASE}/envios/${idEnvio}`),
}
