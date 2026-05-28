import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  cancelarTurno,
  crearPrestacion,
  crearTurno,
  cumplirTurno,
  editarPrestacion,
  eliminarPrestacion,
  listarPrestaciones,
  listarTurnos,
  reprogramarTurno,
} from '../api/turnosApi'
import type {
  CrearTurnoBody,
  ListarTurnosFiltros,
  PrestacionInput,
  ReprogramarTurnoBody,
} from '../types/turno'

const HORA = 60 * 60 * 1000

export function useTurnos(filtros: ListarTurnosFiltros) {
  return useQuery({
    queryKey: ['turnos', 'lista', filtros],
    queryFn: () => listarTurnos(filtros),
    staleTime: 15 * 1000,
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
    mutationFn: (id_turno: number) => cumplirTurno(id_turno),
    onSuccess: () => invalidar(qc),
  })
}

export function useCancelarTurno() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id_turno: number) => cancelarTurno(id_turno),
    onSuccess: () => invalidar(qc),
  })
}
