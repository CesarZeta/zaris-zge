import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  cancelarEventoEntrada,
  crearEventoEntrada,
  listarEventosEntrada,
  type ListarEventosEntradaParams,
} from '../api/entradasApi'
import type { EventoCreatePayload } from '../../agenda/types/agenda'

export function useEventosEntrada(params?: ListarEventosEntradaParams) {
  return useQuery({
    queryKey: ['entradas', 'eventos', params],
    queryFn: () => listarEventosEntrada(params),
    staleTime: 15 * 1000,
  })
}

function invalidar(qc: ReturnType<typeof useQueryClient>) {
  // Comparte entidad con Agenda: invalidamos ambos arboles.
  qc.invalidateQueries({ queryKey: ['entradas'] })
  qc.invalidateQueries({ queryKey: ['agenda'] })
}

export function useCrearEventoEntrada() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: EventoCreatePayload) => crearEventoEntrada(p),
    onSuccess: () => invalidar(qc),
  })
}

export function useCancelarEventoEntrada() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => cancelarEventoEntrada(id),
    onSuccess: () => invalidar(qc),
  })
}
