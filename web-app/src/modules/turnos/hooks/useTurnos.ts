import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  cancelarTurno,
  crearPrestacion,
  crearTurno,
  cumplirTurno,
  editarPrestacion,
  eliminarPrestacion,
  listarAtenciones,
  listarPrestaciones,
  listarTurnos,
  reprogramarTurno,
} from '../api/turnosApi'
import type {
  CrearTurnoBody,
  CumplirTurnoBody,
  ListarTurnosFiltros,
  PrestacionInput,
  ReprogramarTurnoBody,
} from '../types/turno'

const HORA = 60 * 60 * 1000

export function useTurnos(filtros: ListarTurnosFiltros, opts: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['turnos', 'lista', filtros],
    queryFn: () => listarTurnos(filtros),
    staleTime: 15 * 1000,
    enabled: opts.enabled ?? true,
  })
}

// --- Prestaciones ---
export function usePrestaciones(params: { clase?: string; q?: string } = {}) {
  return useQuery({
    queryKey: ['turnos', 'prestaciones', params],
    queryFn: () => listarPrestaciones(params),
    staleTime: HORA,
  })
}

function invalidarPrest(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['turnos', 'prestaciones'] })
}

export function useCrearPrestacion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: PrestacionInput) => crearPrestacion(body),
    onSuccess: () => invalidarPrest(qc),
  })
}

export function useEditarPrestacion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: PrestacionInput }) => editarPrestacion(id, body),
    onSuccess: () => invalidarPrest(qc),
  })
}

export function useEliminarPrestacion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => eliminarPrestacion(id),
    onSuccess: () => invalidarPrest(qc),
  })
}

// --- Turnos ---
function invalidar(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['turnos', 'lista'] })
}

export function useCrearTurno() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CrearTurnoBody) => crearTurno(body),
    onSuccess: () => invalidar(qc),
  })
}

export function useReprogramarTurno() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id_turno, body }: { id_turno: number; body: ReprogramarTurnoBody }) =>
      reprogramarTurno(id_turno, body),
    onSuccess: () => invalidar(qc),
  })
}

export function useCumplirTurno() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id_turno, ...body }: { id_turno: number } & CumplirTurnoBody) =>
      cumplirTurno(id_turno, body),
    onSuccess: () => {
      invalidar(qc)
      qc.invalidateQueries({ queryKey: ['turnos', 'atenciones'] })
    },
  })
}

/** Historia de atenciones de un ciudadano (turnos con registra_atencion).
 *  Scopeada por nivel en el backend (mismo alcance que los turnos). */
export function useAtencionesCiudadano(id_ciudadano: number | null) {
  return useQuery({
    queryKey: ['turnos', 'atenciones', id_ciudadano],
    queryFn: () => listarAtenciones(id_ciudadano as number),
    enabled: id_ciudadano != null,
    staleTime: 15 * 1000,
  })
}

export function useCancelarTurno() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id_turno: number) => cancelarTurno(id_turno),
    onSuccess: () => invalidar(qc),
  })
}
