import { api } from '../../../lib/api'
import type {
  AgenteLite,
  CambiarEstadoOTBody,
  CatalogoEstadoOT,
  CrearOTBody,
  CrearOTConAgendaBody,
  CrearOTConAgendaResponse,
  EquipoLite,
  MesaAgenteResponse,
  MesaAuditoriaResponse,
  MesaSupervisorRow,
  ReasignarOTBody,
  SlotsRecursoResponse,
  TipoRecursoOT,
} from '../types/ot'

const BASE = '/api/v1/ot'

// Catalogo (no se usa para selects pero queda disponible)
export const getCatalogoEstadosOT = () =>
  api.get<CatalogoEstadoOT[]>(`${BASE}/catalogo/estados`)

// Mesa supervisor — reclamos activos
export const getMesaSupervisor = (id_subarea?: number) =>
  api.get<MesaSupervisorRow[]>(`${BASE}/mesa/supervisor`, {
    params: { id_subarea },
  })

// Mesa agente — resuelve id_agente del usuario logueado
export const getMesaAgenteMe = () =>
  api.get<MesaAgenteResponse>(`${BASE}/agente/me`)

// Mesa auditoria — resuelve id_agente + valida es_auditor
export const getMesaAuditorMe = () =>
  api.get<MesaAuditoriaResponse>(`${BASE}/auditor/me`)

// Catalogos para selects (agentes/equipos activos)
export const listarAgentesActivos = () =>
  api.get<AgenteLite[]>('/api/v1/admin/agentes')

export const listarEquiposActivos = () =>
  api.get<EquipoLite[]>('/api/v1/admin/equipos')

// Slots libres de un recurso (agente/equipo) para una fecha
export const getSlotsRecurso = (
  tipo_recurso: TipoRecursoOT, id_recurso: number, fecha: string, duracion_min = 60,
) =>
  api.get<SlotsRecursoResponse>(`${BASE}/slots-recurso`, {
    params: { tipo_recurso, id_recurso, fecha, duracion_min },
  })

// Mutations
export const crearOT = (body: CrearOTBody) =>
  api.post<{ id_ot: number; nro_ot: string; id_reclamo: number }>(BASE, body)

// Crea OT + ocupacion en la agenda en una transaccion
export const crearOTConAgenda = (body: CrearOTConAgendaBody) =>
  api.post<CrearOTConAgendaResponse>(`${BASE}/con-agenda`, body)

export const reasignarOT = (id_ot: number, body: ReasignarOTBody) =>
  api.put<{ ok: boolean; id_ot: number; asignado_a: string }>(`${BASE}/${id_ot}/reasignar`, body)

export const tomarOT = (id_ot: number, id_agente: number) =>
  api.put<{ ok: boolean; id_ot: number; id_agente: number }>(`${BASE}/${id_ot}/tomar`, { id_agente })

export const cambiarEstadoOT = (id_ot: number, body: CambiarEstadoOTBody) =>
  api.put<{ ok: boolean; id_ot: number; estado: string }>(`${BASE}/${id_ot}/estado`, body)

export const aprobarOT = (id_ot: number, observaciones: string) =>
  api.put<{ ok: boolean; id_ot: number; resultado: 'aprobada' }>(`${BASE}/${id_ot}/aprobar`, { observaciones })

export const rechazarOT = (id_ot: number, observaciones: string) =>
  api.put<{ ok: boolean; id_ot: number; resultado: 'rechazada' }>(`${BASE}/${id_ot}/rechazar`, { observaciones })
