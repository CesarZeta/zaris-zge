import { useQuery } from '@tanstack/react-query'
import { getEstadosEvento, getEstadosReserva } from '../api/agendaApi'

const HORA_CACHE = 60 * 60 * 1000

export function useEstadosEvento() {
  return useQuery({
    queryKey: ['agenda', 'catalogos', 'estados-evento'],
    queryFn:  () => getEstadosEvento(),
    staleTime: HORA_CACHE,
  })
}

export function useEstadosReserva() {
  return useQuery({
    queryKey: ['agenda', 'catalogos', 'estados-reserva'],
    queryFn:  () => getEstadosReserva(),
    staleTime: HORA_CACHE,
  })
}
