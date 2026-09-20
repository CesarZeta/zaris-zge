import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  actualizarEvento,
  cancelarEvento,
  crearEvento,
  detalleEvento,
  eliminarEvento,
  listarEventos,
} from '../api/agendaApi'
import type { EventoCreatePayload, EventoUpdatePayload } from '../types/agenda'
import type { OpcionesListado } from './useAgenda'

/** Listado de eventos. `opts` (§23 búsqueda diferida): `enabled: false` hasta
 *  el primer Buscar y `version` en la queryKey para que Buscar con los mismos
 *  filtros vuelva a la red. Default `enabled: true` (comportamiento previo). */
export function useEventos(params?: Parameters<typeof listarEventos>[0], opts: OpcionesListado = {}) {
  return useQuery({
    queryKey: ['agenda', 'eventos', params, opts.version ?? 0],
    queryFn:  () => listarEventos(params),
    enabled:  opts.enabled ?? true,
  })
}

export function useEventoDetalle(idEvento: number | null) {
  return useQuery({
    queryKey: ['agenda', 'evento', idEvento],
    queryFn:  () => detalleEvento(idEvento as number),
    enabled:  idEvento != null,
  })
}

function invalidateAgenda(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['agenda'] })
}

export function useCrearEvento() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: EventoCreatePayload) => crearEvento(p),
    onSuccess:  () => invalidateAgenda(qc),
  })
}

export function useActualizarEvento(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: EventoUpdatePayload) => actualizarEvento(id, p),
    onSuccess:  () => invalidateAgenda(qc),
  })
}

export function useCancelarEvento() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => cancelarEvento(id),
    onSuccess:  () => invalidateAgenda(qc),
  })
}

export function useEliminarEvento() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => eliminarEvento(id),
    onSuccess:  () => invalidateAgenda(qc),
  })
}
