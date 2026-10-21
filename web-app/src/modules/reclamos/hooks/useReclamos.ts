import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  avisarSupervisor,
  cambiarEstadoReclamo,
  cancelarReclamo,
  crearReclamo,
  crearSubreclamo,
  editarReclamo,
  enviarAuditoria,
  resolverReclamo,
  tomarReclamo,
  getCatalogoAreas,
  getCatalogoSubareas,
  getCatalogoTipos,
  getStats,
  listarAdjuntos,
  listarReclamos,
  obtenerReclamo,
  type OrdenListadoReclamos,
} from '../api/reclamosApi'
import type { ReclamoCreate, ReclamoUpdate } from '../types/reclamo'

const HORA = 60 * 60 * 1000

// ── Catalogos ──
export function useAreasCatalogo() {
  return useQuery({ queryKey: ['reclamos', 'areas'], queryFn: getCatalogoAreas, staleTime: HORA })
}

export function useSubareasCatalogo(id_area?: number) {
  return useQuery({
    queryKey: ['reclamos', 'subareas', id_area ?? 'all'],
    queryFn: () => getCatalogoSubareas({ id_area }),
    staleTime: HORA,
  })
}

export function useTiposCatalogo(id_area?: number) {
  return useQuery({
    queryKey: ['reclamos', 'tipos', id_area ?? 'all'],
    queryFn: () => getCatalogoTipos({ id_area, limit: 500 }),
    staleTime: HORA,
  })
}

// ── Stats (contadores top) ──
export function useStats() {
  return useQuery({
    queryKey: ['reclamos', 'stats'],
    queryFn: getStats,
    staleTime: 30 * 1000,
  })
}

// ── Listado con filtros ──
export interface FiltrosReclamos {
  estado?: string
  id_area?: number
  id_subarea?: number
  prioridad?: string
  texto?: string
  pendientes?: boolean
  orden?: OrdenListadoReclamos
  dir?: 'asc' | 'desc'
  limit?: number
}

/** Opciones de las queries de listado. `enabled: false` = búsqueda diferida
 *  (§23: la pantalla no pide nada al entrar); `version` va a la queryKey para
 *  que presionar Buscar con los mismos filtros vuelva a la red (ver
 *  `ui/busqueda.tsx`). El prefijo de invalidación `['reclamos']` sigue matcheando. */
export interface OpcionesListado {
  enabled?: boolean
  version?: number
}

export function useReclamosListado(filtros: FiltrosReclamos, opts: OpcionesListado = {}) {
  return useQuery({
    queryKey: ['reclamos', 'listado', filtros, opts.version ?? 0],
    queryFn: () => listarReclamos({ ...filtros, limit: filtros.limit ?? 200 }),
    staleTime: 15 * 1000,
    enabled: opts.enabled ?? true,
    // Al reordenar (o re-buscar) las filas anteriores siguen a la vista hasta
    // que llega la respuesta: sin esto la tabla desaparecía un instante.
    placeholderData: keepPreviousData,
  })
}

// ── Detalle ──
export function useReclamoDetalle(id: number | null) {
  return useQuery({
    queryKey: ['reclamos', 'detalle', id],
    queryFn:  () => obtenerReclamo(id as number),
    enabled:  id != null,
  })
}

// ── Adjuntos ──
export function useReclamoAdjuntos(id: number | null) {
  return useQuery({
    queryKey: ['reclamos', 'adjuntos', id],
    queryFn:  () => listarAdjuntos(id as number),
    enabled:  id != null,
  })
}

// ── Mutations ──
export function useCrearReclamo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ReclamoCreate) => crearReclamo(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reclamos'] })
    },
  })
}

export function useEditarReclamo(id: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ReclamoUpdate) => editarReclamo(id as number, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reclamos'] })
    },
  })
}

export function useCambiarEstadoReclamo(id: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { estado: string; nota?: string; resolucion?: string }) =>
      cambiarEstadoReclamo(id as number, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reclamos'] })
      // A Resuelto termina la OT abierta (2026-10-21): las mesas también cambian.
      qc.invalidateQueries({ queryKey: ['ot'] })
    },
  })
}

export function useCancelarReclamo(id: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { motivo: string }) =>
      cancelarReclamo(id as number, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reclamos'] })
    },
  })
}

// Auditoría posterior al cierre (mig 112): el reclamo cambia de estado y nace
// una OT de auditoría → invalida reclamos (detalle/listado/stats) y mesas de OT.
export function useEnviarAuditoria(id: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { observaciones?: string; id_agente_auditor?: number | null }) =>
      enviarAuditoria(id as number, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reclamos'] })
      qc.invalidateQueries({ queryKey: ['ot'] })
    },
  })
}

// Tomar / resolver (2026-10-21): invalidan Reclamos y las mesas de OT (la OT nace
// o se termina en la misma operación).
export function useTomarReclamo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => tomarReclamo(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reclamos'] })
      qc.invalidateQueries({ queryKey: ['ot'] })
    },
  })
}

export function useResolverReclamo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, resolucion }: { id: number; resolucion: string }) => resolverReclamo(id, resolucion),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reclamos'] })
      qc.invalidateQueries({ queryKey: ['ot'] })
    },
  })
}

// Aviso del operador al supervisor (Fase 3 roles). Invalida el detalle para
// que el historial muestre la entrada "Aviso al supervisor".
export function useAvisarSupervisor(id: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { accion_sugerida: string; comentario?: string }) =>
      avisarSupervisor(id as number, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reclamos'] })
    },
  })
}

export function useCrearSubreclamo(id: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { descripcion: string; id_tipo_reclamo: number; prioridad?: string; observaciones?: string }) =>
      crearSubreclamo(id as number, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reclamos'] })
    },
  })
}
