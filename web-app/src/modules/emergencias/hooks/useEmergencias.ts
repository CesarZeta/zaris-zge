import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  agregarNotaEvento,
  cambiarEstadoEvento,
  cerrarEvento,
  crearContactoEventual,
  crearEvento,
  derivarEvento,
  detalleEvento,
  listarCanales,
  listarEstados,
  listarEventos,
  listarEventosAbiertos,
  listarOrganismos,
  listarPrioridades,
  listarSubtiposDeTipo,
  listarTipos,
  logEvento,
  marcarEnSitio,
  promoverContactoABuc,
  statsEventos,
} from '../api/emergenciasApi'
import type { ContactoEventualCreateBody, EventoCreateBody, ListarEventosFiltros } from '../types'

const HORA = 60 * 60 * 1000

// --- catalogos (estables, cache larga) ---
export const useTiposEmergencia = (idSubarea?: number) =>
  useQuery({
    queryKey: ['emergencias', 'tipos', idSubarea ?? 'todas'],
    queryFn: () => listarTipos(idSubarea),
    staleTime: HORA,
  })

export const useSubtiposDeTipo = (idTipo: number | null) =>
  useQuery({
    queryKey: ['emergencias', 'subtipos', idTipo],
    queryFn: () => listarSubtiposDeTipo(idTipo as number),
    enabled: idTipo != null,
    staleTime: HORA,
  })

export const usePrioridadesEmergencia = () =>
  useQuery({ queryKey: ['emergencias', 'prioridades'], queryFn: listarPrioridades, staleTime: HORA })

export const useEstadosEmergencia = () =>
  useQuery({ queryKey: ['emergencias', 'estados'], queryFn: listarEstados, staleTime: HORA })

export const useOrganismosEmergencia = () =>
  useQuery({ queryKey: ['emergencias', 'organismos'], queryFn: listarOrganismos, staleTime: HORA })

export const useCanalesEmergencia = () =>
  useQuery({ queryKey: ['emergencias', 'canales'], queryFn: listarCanales, staleTime: HORA })

// --- eventos ---
/** Tablero del dispatcher: refresca solo cada 30s (polling, plan 5.2). */
export const useEventosAbiertos = (params: { id_subarea?: number; id_prioridad?: number }) =>
  useQuery({
    queryKey: ['emergencias', 'abiertos', params],
    queryFn: () => listarEventosAbiertos(params),
    refetchInterval: 30 * 1000,
    staleTime: 10 * 1000,
  })

/** KPIs del tablero: mismo ritmo de polling que la lista de abiertos. */
export const useStatsEmergencias = (horas?: number) =>
  useQuery({
    queryKey: ['emergencias', 'stats', horas ?? 'todo'],
    queryFn: () => statsEventos(horas),
    refetchInterval: 30 * 1000,
    staleTime: 10 * 1000,
  })

export const useEventos = (filtros: ListarEventosFiltros) =>
  useQuery({
    queryKey: ['emergencias', 'eventos', filtros],
    queryFn: () => listarEventos(filtros),
    staleTime: 15 * 1000,
  })

export const useEventoDetalle = (id: number | null) =>
  useQuery({
    queryKey: ['emergencias', 'evento', id],
    queryFn: () => detalleEvento(id as number),
    enabled: id != null,
  })

export const useEventoLog = (id: number | null) =>
  useQuery({
    queryKey: ['emergencias', 'log', id],
    queryFn: () => logEvento(id as number),
    enabled: id != null,
  })

function invalidarEventos(qc: ReturnType<typeof useQueryClient>, id?: number) {
  qc.invalidateQueries({ queryKey: ['emergencias', 'abiertos'] })
  qc.invalidateQueries({ queryKey: ['emergencias', 'eventos'] })
  qc.invalidateQueries({ queryKey: ['emergencias', 'stats'] })
  if (id != null) {
    qc.invalidateQueries({ queryKey: ['emergencias', 'evento', id] })
    qc.invalidateQueries({ queryKey: ['emergencias', 'log', id] })
  }
}

export function useCrearEvento() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: EventoCreateBody) => crearEvento(body),
    onSuccess: () => invalidarEventos(qc),
  })
}

export function useCambiarEstado() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, nuevo_estado, observaciones }: { id: number; nuevo_estado: string; observaciones?: string }) =>
      cambiarEstadoEvento(id, nuevo_estado, observaciones),
    onSuccess: (_d, v) => invalidarEventos(qc, v.id),
  })
}

export function useDerivarEvento() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, id_organismo, observaciones }: { id: number; id_organismo: number; observaciones?: string }) =>
      derivarEvento(id, id_organismo, observaciones),
    onSuccess: (_d, v) => invalidarEventos(qc, v.id),
  })
}

export function useCerrarEvento() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number; veracidad: string; terminal_positivo: boolean; observaciones_cierre?: string }) =>
      cerrarEvento(id, body),
    onSuccess: (_d, v) => invalidarEventos(qc, v.id),
  })
}

export function useMarcarEnSitio() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => marcarEnSitio(id),
    onSuccess: (_d, id) => invalidarEventos(qc, id),
  })
}

export function useAgregarNota() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, observaciones }: { id: number; observaciones: string }) =>
      agregarNotaEvento(id, observaciones),
    onSuccess: (_d, v) => invalidarEventos(qc, v.id),
  })
}

export function useCrearContactoEventual() {
  return useMutation({
    mutationFn: (body: ContactoEventualCreateBody) => crearContactoEventual(body),
  })
}

export function usePromoverABuc() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number; id_ciudadano?: number; apellido?: string; nombre?: string; email?: string }) =>
      promoverContactoABuc(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['emergencias'] }),
  })
}
