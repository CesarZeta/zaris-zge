import { api } from '../../../lib/api'
import type {
  CrearTurnoBody,
  CumplirTurnoBody,
  ListarTurnosFiltros,
  MesaUbicacion,
  PantallaColero,
  PrestacionInput,
  ReprogramarTurnoBody,
  TipoPrestacion,
  Turno,
  TurnoAtencion,
  UbicacionTurnos,
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

// --- Colero (mig 105, F3 plan ATENCION) ---

/** Llama al turno en la mesa. **Re-llamar es el MISMO endpoint**: no cambia el
 *  estado, suma una fila al log y refresca la pantalla de sala. */
export const llamarTurno = (id_turno: number, puesto?: string | null) =>
  api.patch<Turno>(`/api/v1/turnos/${id_turno}/llamar`, { puesto: puesto || null })

export const marcarAusente = (id_turno: number, observaciones?: string | null) =>
  api.patch<Turno>(`/api/v1/turnos/${id_turno}/ausente`, { observaciones: observaciones || null })

/** Pantalla de sala — PÚBLICA, sin JWT (la TV no tiene sesión). */
export const pantallaColero = (token: string) =>
  api.get<PantallaColero>(`/api/v1/turnos/publico/pantalla/${token}`)

export const obtenerTurno = (id_turno: number) =>
  api.get<Turno>(`/api/v1/turnos/${id_turno}`)

// --- Ubicaciones de atencion (F2 plan ATENCION) ---
export const listarUbicaciones = (fecha?: string) =>
  api.get<UbicacionTurnos[]>('/api/v1/turnos/ubicaciones', { params: fecha ? { fecha } : {} })

export const mesaUbicacion = (id_espacio: number, fecha?: string) =>
  api.get<MesaUbicacion>(`/api/v1/turnos/ubicaciones/${id_espacio}/mesa`, { params: fecha ? { fecha } : {} })
