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
