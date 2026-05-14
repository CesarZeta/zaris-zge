// Cliente HTTP minimal para los endpoints publicos de autoservicio.
// NO usa JWT, NO toca localStorage, NO redirige a /login en errores.

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://127.0.0.1:8000'

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers as Record<string, string> | undefined),
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const msg = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail ?? err)
    throw new Error(msg || `HTTP ${res.status}`)
  }
  return (await res.json()) as T
}

export interface EventoPublico {
  id_evento: number
  nombre: string
  descripcion: string | null
  fecha: string
  hora_inicio: string
  hora_fin: string
  cupo_disponible: number
  estado_codigo: string
  admite_autoservicio: boolean
  tipo_qr: 'nominal' | 'generico' | 'ninguno'
}

export interface ReservaPublicaCreate {
  dni: string
  apellido: string
  nombre: string
  telefono?: string
  email?: string
}

export interface ReservaPublica {
  id_evento_reserva: number
  token_reserva: string
  qr_codigo: string | null
  estado_codigo: string
  origen: string
  ciudadano_apellido: string | null
  ciudadano_nombre: string | null
  ciudadano_dni: string | null
  evento: EventoPublico
}

export function getEventoPublico(token: string) {
  return jsonFetch<EventoPublico>(`/api/v1/agenda/publico/evento/${token}`)
}

export function postReservaPublica(token: string, payload: ReservaPublicaCreate) {
  return jsonFetch<ReservaPublica>(`/api/v1/agenda/publico/evento/${token}/reservar`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getReservaPublica(tokenReserva: string) {
  return jsonFetch<ReservaPublica>(`/api/v1/agenda/publico/reserva/${tokenReserva}`)
}

export function deleteReservaPublica(tokenReserva: string) {
  return jsonFetch<ReservaPublica>(`/api/v1/agenda/publico/reserva/${tokenReserva}`, {
    method: 'DELETE',
  })
}

// =============================================================================
// Turnos — autoservicio publico
// =============================================================================
export interface TipoServicioTurno {
  id_tipo_servicio_turno: number
  nombre: string
  descripcion: string | null
  duracion_min: number
  activo: boolean
}

export interface AgenteDisponible {
  id_agente: number
  nombre: string
}

export interface SlotLibre {
  id_agente: number
  agente_nombre: string
  fecha: string
  hora_inicio: string
  hora_fin: string
}

export interface TurnoPublicoCreate {
  id_tipo_servicio_turno: number
  id_agente: number
  fecha: string
  hora_inicio: string
  dni: string
  apellido: string
  nombre: string
  telefono?: string
  email?: string
  observaciones?: string
}

export interface TurnoPublico {
  id_turno: number
  token_turno: string
  estado: 'reservado' | 'cumplido' | 'cancelado'
  fecha: string
  hora_inicio: string
  hora_fin: string
  tipo_servicio_nombre: string | null
  agente_nombre: string | null
  ciudadano_apellido: string | null
  ciudadano_nombre: string | null
  ciudadano_dni: string | null
}

export function getTiposServicioTurno() {
  return jsonFetch<TipoServicioTurno[]>('/api/v1/turnos/publico/tipos-servicio')
}

export function getAgentesTurno() {
  return jsonFetch<AgenteDisponible[]>('/api/v1/turnos/publico/agentes')
}

export function getSlotsTurno(params: {
  id_tipo_servicio_turno: number
  id_agente?: number
  fecha_desde?: string
  dias?: number
}) {
  const qs = new URLSearchParams()
  qs.set('id_tipo_servicio_turno', String(params.id_tipo_servicio_turno))
  if (params.id_agente != null) qs.set('id_agente', String(params.id_agente))
  if (params.fecha_desde) qs.set('fecha_desde', params.fecha_desde)
  if (params.dias != null) qs.set('dias', String(params.dias))
  return jsonFetch<SlotLibre[]>(`/api/v1/turnos/publico/slots?${qs.toString()}`)
}

export function postTurnoPublico(payload: TurnoPublicoCreate) {
  return jsonFetch<TurnoPublico>('/api/v1/turnos/publico/reservar', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getTurnoPublico(tokenTurno: string) {
  return jsonFetch<TurnoPublico>(`/api/v1/turnos/publico/turno/${tokenTurno}`)
}

export function deleteTurnoPublico(tokenTurno: string) {
  return jsonFetch<TurnoPublico>(`/api/v1/turnos/publico/turno/${tokenTurno}`, {
    method: 'DELETE',
  })
}
