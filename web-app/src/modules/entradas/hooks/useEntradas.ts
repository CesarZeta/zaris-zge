import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  cancelarEventoEntrada,
  crearEventoEntrada,
  listarEventosEntrada,
  type ListarEventosEntradaParams,
} from '../api/entradasApi'
import type { EventoCreatePayload } from '../../agenda/types/agenda'

/** Opciones del listado de eventos. `enabled: false` = búsqueda diferida (§23:
 *  la pantalla no pide nada al entrar); `version` en la queryKey para que
 *  "Ver eventos" vuelva a la red aunque no cambie nada (ver `ui/busqueda.tsx`). */
export interface OpcionesListado {
  enabled?: boolean
  version?: number
}

export function useEventosEntrada(params?: ListarEventosEntradaParams, opts: OpcionesListado = {}) {
  return useQuery({
    queryKey: ['entradas', 'eventos', params, opts.version ?? 0],
    queryFn: () => listarEventosEntrada(params),
    staleTime: 15 * 1000,
    enabled: opts.enabled ?? true,
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
