import { api } from '../../../lib/api'
import type {
  CrearTurnoBody,
  ListarTurnosFiltros,
  ReprogramarTurnoBody,
  TipoServicioTurno,
  Turno,
} from '../types/turno'

export const listarTiposServicio = () =>
  api.get<TipoServicioTurno[]>('/api/v1/turnos/catalogo/tipos-servicio')

export const listarTurnos = (filtros: ListarTurnosFiltros = {}) =>
  api.get<Turno[]>('/api/v1/turnos', { params: { ...filtros, limit: 300 } })

export const crearTurno = (body: CrearTurnoBody) =>
  api.post<Turno>('/api/v1/turnos', body)

export const reprogramarTurno = (id_turno: number, body: ReprogramarTurnoBody) =>
  api.put<Turno>(`/api/v1/turnos/${id_turno}`, body)

export const cumplirTurno = (id_turno: number) =>
  api.patch<Turno>(`/api/v1/turnos/${id_turno}/cumplir`)

export const cancelarTurno = (id_turno: number) =>
  api.patch<Turno>(`/api/v1/turnos/${id_turno}/cancelar`)
