import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listarConflictos, resolverConflicto } from '../api/agendaApi'
import type { OpcionesListado } from './useAgenda'

/** Listado de conflictos. `opts` (§23 búsqueda diferida): `enabled: false`
 *  hasta el primer "Ver conflictos" y `version` en la queryKey para volver a
 *  la red con el mismo filtro. Default `enabled: true` (comportamiento previo,
 *  p. ej. el Timeline que lo usa para marcar bloques en conflicto). */
export function useConflictos(resuelto: boolean | undefined = false, opts: OpcionesListado = {}) {
  return useQuery({
    queryKey: ['agenda', 'conflictos', resuelto, opts.version ?? 0],
    queryFn:  () => listarConflictos({ resuelto }),
    enabled:  opts.enabled ?? true,
  })
}

export function useResolverConflicto() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (args: { id: number; observaciones?: string }) => resolverConflicto(args.id, args.observaciones),
    onSuccess:  () => qc.invalidateQueries({ queryKey: ['agenda'] }),
  })
}
