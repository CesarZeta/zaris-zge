import { api } from '../../../lib/api'
import type {
  CalendarioDia,
  CalendarioMes,
  CalendarioSemana,
  CiudadanoMinimo,
  Conflicto,
  DisponibilidadRangoEfectivo,
  DisponibilidadRecurso,
  DisponibilidadRecursoCreatePayload,
  DisponibilidadRecursoUpdatePayload,
  EncargadoCreateResponse,
  EspacioAgenda,
  EspacioAgendaCreatePayload,
  EspacioAgendaUpdatePayload,
  EspacioAgente,
  EstadoCatalogo,
  Evento,
  EventoBusquedaItem,
  EventoCreatePayload,
  EventoDetalle,
  EventoEncargado,
  EventoUpdatePayload,
  Ocupacion,
  OcupacionCreatePayload,
  OcupacionCreated,
  OcupacionUpdatePayload,
  OTBusquedaItem,
  RecursoAgenda,
  RecursoItem,
  RecursosConteos,
  Reserva,
  ReservaCreatePayload,
  SubareaItem,
  TipoRecurso,
} from '../types/agenda'

const BASE = '/api/v1/agenda'

// ----- Catalogos -----------------------------------------------------------
export function getEstadosEvento() {
  return api.get<EstadoCatalogo[]>(`${BASE}/catalogos/estados-evento`)
}
export function getEstadosReserva() {
  return api.get<EstadoCatalogo[]>(`${BASE}/catalogos/estados-reserva`)
}

// ----- Eventos -------------------------------------------------------------
export function listarEventos(params?: {
  fecha_desde?: string
  fecha_hasta?: string
  id_estado_evento?: number
  id_subarea?: number
  id_municipio?: number
  limit?: number
  offset?: number
}) {
  return api.getWithHeaders<Evento[]>(`${BASE}/eventos`, { params })
}
export function crearEvento(payload: EventoCreatePayload) {
  return api.post<Evento>(`${BASE}/eventos`, payload)
}
export function detalleEvento(id: number) {
  return api.get<EventoDetalle>(`${BASE}/eventos/${id}`)
}
export function actualizarEvento(id: number, payload: EventoUpdatePayload) {
  return api.put<Evento>(`${BASE}/eventos/${id}`, payload)
}
export function cancelarEvento(id: number) {
  return api.patch<Evento>(`${BASE}/eventos/${id}/cancelar`)
}
export function eliminarEvento(id: number) {
  return api.delete<void>(`${BASE}/eventos/${id}`)
}

// ----- Encargados ----------------------------------------------------------
export function listarEncargados(idEvento: number) {
  return api.get<EventoEncargado[]>(`${BASE}/eventos/${idEvento}/encargados`)
}
export function asignarEncargado(idEvento: number, tipo_recurso: TipoRecurso, id_recurso: number) {
  return api.post<EncargadoCreateResponse>(`${BASE}/eventos/${idEvento}/encargados`, { tipo_recurso, id_recurso })
}
export function desasignarEncargado(idEvento: number, idEncargado: number) {
  return api.delete<void>(`${BASE}/eventos/${idEvento}/encargados/${idEncargado}`)
}

// ----- Reservas ------------------------------------------------------------
export function listarReservas(idEvento: number) {
  return api.get<Reserva[]>(`${BASE}/eventos/${idEvento}/reservas`)
}
export function crearReserva(idEvento: number, payload: ReservaCreatePayload) {
  return api.post<Reserva>(`${BASE}/eventos/${idEvento}/reservas`, payload)
}
export function marcarAsistio(idReserva: number) {
  return api.patch<Reserva>(`${BASE}/reservas/${idReserva}/asistio`)
}
export function cancelarReserva(idReserva: number) {
  return api.patch<Reserva>(`${BASE}/reservas/${idReserva}/cancelar`)
}

// ----- Ocupaciones ---------------------------------------------------------
export function listarOcupaciones(params?: {
  tipo_recurso?: TipoRecurso
  id_recurso?: number
  fecha_desde?: string
  fecha_hasta?: string
  tipo?: string
  id_municipio?: number
  limit?: number
  offset?: number
}) {
  return api.getWithHeaders<Ocupacion[]>(`${BASE}/ocupaciones`, { params })
}
export function crearOcupacion(payload: OcupacionCreatePayload) {
  return api.post<OcupacionCreated>(`${BASE}/ocupaciones`, payload)
}
export function actualizarOcupacion(id: number, payload: OcupacionUpdatePayload) {
  return api.put<OcupacionCreated>(`${BASE}/ocupaciones/${id}`, payload)
}
export function eliminarOcupacion(id: number) {
  return api.delete<void>(`${BASE}/ocupaciones/${id}`)
}

// ----- Vista coordinador --------------------------------------------------
export function getAgendaRecurso(tipo_recurso: TipoRecurso, id_recurso: number, desde: string, hasta: string) {
  return api.get<RecursoAgenda>(`${BASE}/recurso/${tipo_recurso}/${id_recurso}`, {
    params: { desde, hasta },
  })
}
export function getCalendarioDia(
  fecha: string,
  id_municipio = 1,
  tipo_recurso: TipoRecurso | 'todos' = 'todos',
  id_subarea: number | null = null,
  atendido: boolean | null = null,
  scope_subarea_propia = false,
) {
  const params: Record<string, string | number | boolean | null | undefined> = { fecha, id_municipio, tipo_recurso }
  if (id_subarea != null) params.id_subarea = id_subarea
  if (atendido != null) params.atendido = atendido
  if (scope_subarea_propia) params.scope_subarea_propia = true
  return api.get<CalendarioDia>(`${BASE}/calendario`, { params })
}
export function getCalendarioSemana(
  desde: string,
  dias = 7,
  id_municipio = 1,
  tipo_recurso: TipoRecurso | 'todos' = 'todos',
  id_subarea: number | null = null,
  atendido: boolean | null = null,
  scope_subarea_propia = false,
) {
  const params: Record<string, string | number | boolean | null | undefined> = { desde, dias, id_municipio, tipo_recurso }
  if (id_subarea != null) params.id_subarea = id_subarea
  if (atendido != null) params.atendido = atendido
  if (scope_subarea_propia) params.scope_subarea_propia = true
  return api.get<CalendarioSemana>(`${BASE}/semana`, { params })
}
export function getCalendarioMes(
  anio: number,
  mes: number,
  id_municipio = 1,
  tipo_recurso: TipoRecurso | 'todos' = 'todos',
) {
  return api.get<CalendarioMes>(`${BASE}/mes`, { params: { anio, mes, id_municipio, tipo_recurso } })
}
export function getRecursosConteos(id_municipio = 1) {
  return api.get<RecursosConteos>(`${BASE}/recursos/conteos`, { params: { id_municipio } })
}

// ----- Conflictos ---------------------------------------------------------
export function listarConflictos(params?: { resuelto?: boolean; desde?: string; hasta?: string; limit?: number; offset?: number }) {
  return api.get<Conflicto[]>(`${BASE}/conflictos`, { params })
}
export function resolverConflicto(id: number, observaciones?: string) {
  return api.patch<Conflicto>(`${BASE}/conflictos/${id}/resolver`, { observaciones: observaciones ?? null })
}

// ----- BUC (busqueda de ciudadanos) ---------------------------------------
export function buscarCiudadanos(q: string, limit = 10) {
  return api.get<CiudadanoMinimo[]>(`/api/v1/buc/ciudadanos/buscar`, { params: { q, limit, tipo: 'auto' } })
}

// ----- Catalogos extra (sub-fase 3.B) -------------------------------------
export function listarSubareasAgenda(q?: string, limit = 50) {
  return api.get<SubareaItem[]>(`${BASE}/catalogos/subareas`, { params: { q, limit } })
}

export function listarRecursosAgenda(opts?: { tipo?: TipoRecurso; q?: string; id_municipio?: number; limit?: number }) {
  return api.get<RecursoItem[]>(`${BASE}/catalogos/recursos`, { params: opts })
}

export function buscarOTsAgenda(q?: string, estado?: string, limit = 20) {
  return api.get<OTBusquedaItem[]>(`${BASE}/catalogos/ot-busqueda`, { params: { q, estado, limit } })
}

export function buscarEventosAgenda(q?: string, opts?: { fecha_desde?: string; fecha_hasta?: string; id_municipio?: number; limit?: number }) {
  return api.get<EventoBusquedaItem[]>(`${BASE}/catalogos/evento-busqueda`, { params: { q, ...opts } })
}

// ----- Espacios (sub-fase B1) ---------------------------------------------
export function listarEspacios(params?: { atendido?: boolean; q?: string; id_municipio?: number; limit?: number; offset?: number }) {
  return api.getWithHeaders<EspacioAgenda[]>(`${BASE}/espacios`, { params })
}
export function crearEspacio(payload: EspacioAgendaCreatePayload) {
  return api.post<EspacioAgenda>(`${BASE}/espacios`, payload)
}
export function detalleEspacio(id: number) {
  return api.get<EspacioAgenda>(`${BASE}/espacios/${id}`)
}
export function actualizarEspacio(id: number, payload: EspacioAgendaUpdatePayload) {
  return api.put<EspacioAgenda>(`${BASE}/espacios/${id}`, payload)
}
export function eliminarEspacio(id: number) {
  return api.delete<void>(`${BASE}/espacios/${id}`)
}
export function listarAgentesDeEspacio(idEspacio: number) {
  return api.get<EspacioAgente[]>(`${BASE}/espacios/${idEspacio}/agentes`)
}
export function vincularAgenteAEspacio(idEspacio: number, id_agente: number) {
  return api.post<EspacioAgente>(`${BASE}/espacios/${idEspacio}/agentes`, { id_agente })
}
export function desvincularAgenteDeEspacio(idEspacio: number, idEspacioAgente: number) {
  return api.delete<void>(`${BASE}/espacios/${idEspacio}/agentes/${idEspacioAgente}`)
}

// ----- Disponibilidad de recurso (sub-fase B1) ----------------------------
export function listarDisponibilidad(params?: { tipo_recurso?: TipoRecurso; id_recurso?: number; id_municipio?: number; limit?: number }) {
  return api.get<DisponibilidadRecurso[]>(`${BASE}/disponibilidad`, { params })
}
export function crearDisponibilidad(payload: DisponibilidadRecursoCreatePayload) {
  return api.post<DisponibilidadRecurso>(`${BASE}/disponibilidad`, payload)
}
export function actualizarDisponibilidad(id: number, payload: DisponibilidadRecursoUpdatePayload) {
  return api.put<DisponibilidadRecurso>(`${BASE}/disponibilidad/${id}`, payload)
}
export function eliminarDisponibilidad(id: number) {
  return api.delete<void>(`${BASE}/disponibilidad/${id}`)
}
export function getDisponibilidadEfectiva(tipo_recurso: TipoRecurso, id_recurso: number, fecha: string) {
  return api.get<DisponibilidadRangoEfectivo[]>(`${BASE}/disponibilidad/efectiva`, {
    params: { tipo_recurso, id_recurso, fecha },
  })
}
