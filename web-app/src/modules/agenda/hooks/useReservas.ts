import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { cancelarReserva, crearReserva, listarReservas, marcarAsistio } from '../api/agendaApi'
import type { ReservaCreatePayload } from '../types/agenda'

export function useReservas(idEvento: number | null) {
  return useQuery({
    queryKey: ['agenda', 'reservas', idEvento],
    queryFn:  () => listarReservas(idEvento as number),
    enabled:  idEvento != null,
  })
}

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['agenda'] })
}

export function useCrearReserva(idEvento: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: ReservaCreatePayload) => crearReserva(idEvento, p),
    onSuccess:  () => invalidate(qc),
  })
}

export function useMarcarAsistio() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (idReserva: number) => marcarAsistio(idReserva),
    onSuccess:  () => invalidate(qc),
  })
}

export function useCancelarReserva() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (idReserva: number) => cancelarReserva(idReserva),
    onSuccess:  () => invalidate(qc),
  })
}
