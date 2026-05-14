import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  cancelarTurno,
  crearTurno,
  cumplirTurno,
  listarAgentesActivos,
  listarTiposServicio,
  listarTurnos,
  reprogramarTurno,
} from '../api/turnosApi'
import type { CrearTurnoBody, ListarTurnosFiltros, ReprogramarTurnoBody } from '../types/turno'

const HORA = 60 * 60 * 1000

export function useTurnos(filtros: ListarTurnosFiltros) {
  return useQuery({
    queryKey: ['turnos', 'lista', filtros],
    queryFn: () => listarTurnos(filtros),
    staleTime: 15 * 1000,
  })
}

export function useTiposServicio() {
  return useQuery({
    queryKey: ['turnos', 'tipos-servicio'],
    queryFn: listarTiposServicio,
    staleTime: HORA,
  })
}

export function useAgentesActivos() {
  return useQuery({
    queryKey: ['turnos', 'agentes-activos'],
    queryFn: listarAgentesActivos,
    staleTime: HORA,
  })
}

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
