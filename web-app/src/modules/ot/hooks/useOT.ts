import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  aprobarOT,
  cambiarEstadoOT,
  crearOT,
  getMesaAgenteMe,
  getMesaAuditorMe,
  getMesaSupervisor,
  listarAgentesActivos,
  listarEquiposActivos,
  observarOT,
  reasignarOT,
  tomarOT,
} from '../api/otApi'
import type { MesaSupervisorFiltros } from '../api/otApi'
import type { CambiarEstadoOTBody, CrearOTBody, ReasignarOTBody } from '../types/ot'

const HORA = 60 * 60 * 1000

// ── Mesas ──

/** Opciones de las queries de mesa. `enabled: false` = búsqueda diferida
 *  (§23: la mesa no pide nada al entrar; con la query deshabilitada react-query
 *  tampoco pollea, el `refetchInterval` recién corre tras la primera búsqueda).
 *  `version` va a la queryKey para que presionar Buscar con los mismos filtros
 *  vuelva a la red (ver `ui/busqueda.tsx`). Los prefijos de invalidación
 *  (`['ot']`) siguen matcheando. */
export interface OpcionesMesa {
  enabled?: boolean
  version?: number
}

export function useMesaSupervisor(filtros?: MesaSupervisorFiltros, opts: OpcionesMesa = {}) {
  return useQuery({
    queryKey: ['ot', 'mesa-supervisor', filtros ?? {}, opts.version ?? 0],
    queryFn: () => getMesaSupervisor(filtros),
    staleTime: 15 * 1000,
    refetchInterval: 30 * 1000,
    placeholderData: (prev) => prev, // no vaciar la tabla al cambiar filtros
    enabled: opts.enabled ?? true,
  })
}

export function useMesaAgente(opts: OpcionesMesa = {}) {
  return useQuery({
    queryKey: ['ot', 'mesa-agente', opts.version ?? 0],
    queryFn: getMesaAgenteMe,
    staleTime: 15 * 1000,
    refetchInterval: 30 * 1000,
    retry: false,
    enabled: opts.enabled ?? true,
  })
}

export function useMesaAuditoria(opts: OpcionesMesa = {}) {
  return useQuery({
    queryKey: ['ot', 'mesa-auditoria', opts.version ?? 0],
    queryFn: getMesaAuditorMe,
    staleTime: 15 * 1000,
    refetchInterval: 30 * 1000,
    retry: false,
    enabled: opts.enabled ?? true,
  })
}

// ── Catalogos para selects ──
export function useAgentesActivos(enabled = true) {
  return useQuery({
    queryKey: ['ot', 'agentes-activos'],
    queryFn: listarAgentesActivos,
    staleTime: HORA,
    enabled,
  })
}

export function useEquiposActivos(enabled = true) {
  return useQuery({
    queryKey: ['ot', 'equipos-activos'],
    queryFn: listarEquiposActivos,
    staleTime: HORA,
    enabled,
  })
}

// ── Mutations ──
function invalidarMesas(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['ot'] })
}

export function useCrearOT() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CrearOTBody) => crearOT(body),
    onSuccess: () => invalidarMesas(qc),
  })
}

export function useReasignarOT() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id_ot, body }: { id_ot: number; body: ReasignarOTBody }) => reasignarOT(id_ot, body),
    onSuccess: () => invalidarMesas(qc),
  })
}

export function useTomarOT() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id_ot, id_agente }: { id_ot: number; id_agente: number }) => tomarOT(id_ot, id_agente),
    onSuccess: () => invalidarMesas(qc),
  })
}

export function useCambiarEstadoOT() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id_ot, body }: { id_ot: number; body: CambiarEstadoOTBody }) => cambiarEstadoOT(id_ot, body),
    onSuccess: () => invalidarMesas(qc),
  })
}

export function useAprobarOT() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id_ot, observaciones }: { id_ot: number; observaciones: string }) => aprobarOT(id_ot, observaciones),
    onSuccess: () => invalidarMesas(qc),
  })
}

export function useObservarOT() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id_ot, observaciones, generar_retrabajo }: {
      id_ot: number; observaciones: string; generar_retrabajo: boolean
    }) => observarOT(id_ot, observaciones, generar_retrabajo),
    // El retrabajo es un reclamo nuevo: también se invalida el módulo Reclamos.
    onSuccess: () => { invalidarMesas(qc); qc.invalidateQueries({ queryKey: ['reclamos'] }) },
  })
}
