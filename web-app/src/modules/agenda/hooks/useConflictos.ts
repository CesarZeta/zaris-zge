import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listarConflictos, resolverConflicto } from '../api/agendaApi'

export function useConflictos(resuelto: boolean | undefined = false) {
  return useQuery({
    queryKey: ['agenda', 'conflictos', resuelto],
    queryFn:  () => listarConflictos({ resuelto }),
  })
}

export function useResolverConflicto() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (args: { id: number; observaciones?: string }) => resolverConflicto(args.id, args.observaciones),
    onSuccess:  () => qc.invalidateQueries({ queryKey: ['agenda'] }),
  })
}
