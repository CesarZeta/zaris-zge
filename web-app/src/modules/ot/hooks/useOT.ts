import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  aprobarOT,
  cambiarEstadoOT,
  crearOT,
  crearOTConAgenda,
  getMesaAgenteMe,
  getMesaAuditorMe,
  getMesaSupervisor,
  getSlotsRecurso,
  listarAgentesActivos,
  listarEquiposActivos,
  rechazarOT,
  reasignarOT,
  tomarOT,
} from '../api/otApi'
import type {
  CambiarEstadoOTBody, CrearOTBody, CrearOTConAgendaBody, ReasignarOTBody, TipoRecursoOT,
} from '../types/ot'

const HORA = 60 * 60 * 1000

// ── Mesas ──
export function useMesaSupervisor(id_subarea?: number) {
  return useQuery({
    queryKey: ['ot', 'mesa-supervisor', id_subarea ?? 'all'],
    queryFn: () => getMesaSupervisor(id_subarea),
    staleTime: 15 * 1000,
    refetchInterval: 30 * 1000,
  })
}

export function useMesaAgente() {
  return useQuery({
    queryKey: ['ot', 'mesa-agente'],
    queryFn: getMesaAgenteMe,
    staleTime: 15 * 1000,
    refetchInterval: 30 * 1000,
    retry: false,
  })
}

export function useMesaAuditoria() {
  return useQuery({
    queryKey: ['ot', 'mesa-auditoria'],
    queryFn: getMesaAuditorMe,
    staleTime: 15 * 1000,
    refetchInterval: 30 * 1000,
    retry: false,
  })
}

// ── Catalogos para selects ──
export function useAgentesActivos(enabled = true) {
  return useQuery({
    queryKey: ['ot', 'agentes-activos'],
    queryFn: listarAgentesActivos,
    staleTime: HORA,
    enabled,
  })
}

export function useEquiposActivos(enabled = true) {
  return useQuery({
    queryKey: ['ot', 'equipos-activos'],
    queryFn: listarEquiposActivos,
    staleTime: HORA,
    enabled,
  })
}

// Slots libres de un recurso para una fecha (planificacion de OT).
// enabled solo cuando hay recurso y fecha elegidos.
export function useSlotsRecurso(
  tipo_recurso: TipoRecursoOT | null,
  id_recurso: number | null,
  fecha: string | null,
  duracion_min = 60,
) {
  return useQuery({
    queryKey: ['ot', 'slots-recurso', tipo_recurso, id_recurso, fecha, duracion_min],
    queryFn: () => getSlotsRecurso(tipo_recurso as TipoRecursoOT, id_recurso as number, fecha as string, duracion_min),
    enabled: tipo_recurso != null && id_recurso != null && fecha != null,
    staleTime: 15 * 1000,
  })
}

// ── Mutations ──
function invalidarMesas(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['ot'] })
}

export function useCrearOT() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CrearOTBody) => crearOT(body),
    onSuccess: () => invalidarMesas(qc),
  })
}

// Crea OT + ocupacion en la agenda. Invalida mesas de OT y queries de agenda
// (la ocupacion nueva debe aparecer en la grilla del modulo Agenda).
export function useCrearOTConAgenda() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CrearOTConAgendaBody) => crearOTConAgenda(body),
    onSuccess: () => {
      invalidarMesas(qc)
      qc.invalidateQueries({ queryKey: ['agenda'] })
    },
  })
}

export function useReasignarOT() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id_ot, body }: { id_ot: number; body: ReasignarOTBody }) => reasignarOT(id_ot, body),
    onSuccess: () => invalidarMesas(qc),
  })
}

export function useTomarOT() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id_ot, id_agente }: { id_ot: number; id_agente: number }) => tomarOT(id_ot, id_agente),
    onSuccess: () => invalidarMesas(qc),
  })
}

export function useCambiarEstadoOT() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id_ot, body }: { id_ot: number; body: CambiarEstadoOTBody }) => cambiarEstadoOT(id_ot, body),
    onSuccess: () => invalidarMesas(qc),
  })
}

export function useAprobarOT() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id_ot, observaciones }: { id_ot: number; observaciones: string }) => aprobarOT(id_ot, observaciones),
    onSuccess: () => invalidarMesas(qc),
  })
}

export function useRechazarOT() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id_ot, observaciones }: { id_ot: number; observaciones: string }) => rechazarOT(id_ot, observaciones),
    onSuccess: () => invalidarMesas(qc),
  })
}
