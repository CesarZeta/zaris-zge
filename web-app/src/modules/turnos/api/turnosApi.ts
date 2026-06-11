import { api } from '../../../lib/api'
import type {
  CrearTurnoBody,
  CumplirTurnoBody,
  ListarTurnosFiltros,
  PrestacionInput,
  ReprogramarTurnoBody,
  TipoPrestacion,
  Turno,
  TurnoAtencion,
} from '../types/turno'

// --- Prestaciones (catalogo) ---
export const listarPrestaciones = (params: { clase?: string; q?: string } = {}) =>
  api.get<TipoPrestacion[]>('/api/v1/turnos/prestaciones', { params })

export const crearPrestacion = (body: PrestacionInput) =>
  api.post<TipoPrestacion>('/api/v1/turnos/prestaciones', body)

export const editarPrestacion = (id: number, body: PrestacionInput) =>
  api.put<TipoPrestacion>(`/api/v1/turnos/prestaciones/${id}`, body)

export const eliminarPrestacion = (id: number) =>
  api.delete<void>(`/api/v1/turnos/prestaciones/${id}`)

// --- Turnos ---
export const listarTurnos = (filtros: ListarTurnosFiltros = {}) =>
  api.get<Turno[]>('/api/v1/turnos', { params: { ...filtros, limit: 300 } })

export const crearTurno = (body: CrearTurnoBody) =>
  api.post<Turno>('/api/v1/turnos', body)

export const reprogramarTurno = (id_turno: number, body: ReprogramarTurnoBody) =>
  api.put<Turno>(`/api/v1/turnos/${id_turno}`, body)

export const cumplirTurno = (id_turno: number, body?: CumplirTurnoBody) =>
  api.patch<Turno>(`/api/v1/turnos/${id_turno}/cumplir`, body ?? {})

export const listarAtenciones = (id_ciudadano: number) =>
  api.get<TurnoAtencion[]>('/api/v1/turnos/atenciones', { params: { id_ciudadano } })

export const cancelarTurno = (id_turno: number) =>
  api.patch<Turno>(`/api/v1/turnos/${id_turno}/cancelar`)
