import { api } from '../../../lib/api'
import type { Evento, EventoCreatePayload } from '../../agenda/types/agenda'
import type { OrdenEventos } from '../../agenda/api/agendaApi'

const BASE = '/api/v1/agenda'

// El modulo Entradas reusa la entidad `eventos` del backend de Agenda, pero
// solo opera sobre los eventos que tienen un espacio fisico asignado
// (id_espacio != null). El backend expone el filtro `con_espacio`.

/** Columnas ordenables: las define el listado de eventos de Agenda. */
export type { OrdenEventos }

export interface ListarEventosEntradaParams {
  fecha_desde?: string
  fecha_hasta?: string
  id_estado_evento?: number
  /** Orden: lo resuelve el backend (el listado tiene tope, §23). */
  orden?: OrdenEventos
  dir?: 'asc' | 'desc'
}

export function listarEventosEntrada(params?: ListarEventosEntradaParams) {
  return api.get<Evento[]>(`${BASE}/eventos`, {
    params: { ...params, con_espacio: true, limit: 200 },
  })
}

export function crearEventoEntrada(payload: EventoCreatePayload) {
  return api.post<Evento>(`${BASE}/eventos`, payload)
}

export function cancelarEventoEntrada(id: number) {
  return api.patch<Evento>(`${BASE}/eventos/${id}/cancelar`)
}
