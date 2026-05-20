import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { borrarAdjuntoOT, listarAdjuntosOT } from '../api/otAdjuntosApi'

export function useOTAdjuntos(idOt: number | null) {
  return useQuery({
    queryKey: ['ot', 'adjuntos', idOt],
    queryFn: () => listarAdjuntosOT(idOt as number),
    enabled: idOt != null,
  })
}

export function useBorrarAdjuntoOT(idOt: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (idAdjunto: number) => borrarAdjuntoOT(idOt as number, idAdjunto),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ot', 'adjuntos', idOt] })
    },
  })
}
