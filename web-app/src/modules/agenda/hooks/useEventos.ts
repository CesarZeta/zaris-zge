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

export function useEventos(params?: Parameters<typeof listarEventos>[0]) {
  return useQuery({
    queryKey: ['agenda', 'eventos', params],
    queryFn:  () => listarEventos(params),
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
