import { api } from '../../../lib/api'
import type { Evento, EventoCreatePayload } from '../../agenda/types/agenda'

const BASE = '/api/v1/agenda'

// El modulo Entradas reusa la entidad `eventos` del backend de Agenda, pero
// solo opera sobre los eventos que tienen un espacio fisico asignado
// (id_espacio != null). El backend expone el filtro `con_espacio`.

export interface ListarEventosEntradaParams {
  fecha_desde?: string
  fecha_hasta?: string
  id_estado_evento?: number
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
