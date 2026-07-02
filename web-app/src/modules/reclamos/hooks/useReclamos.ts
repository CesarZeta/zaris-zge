import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  avisarSupervisor,
  cambiarEstadoReclamo,
  cancelarReclamo,
  crearReclamo,
  crearSubreclamo,
  editarReclamo,
  getCatalogoAreas,
  getCatalogoSubareas,
  getCatalogoTipos,
  getStats,
  listarAdjuntos,
  listarReclamos,
  obtenerReclamo,
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
  limit?: number
}

export function useReclamosListado(filtros: FiltrosReclamos) {
  return useQuery({
    queryKey: ['reclamos', 'listado', filtros],
    queryFn: () => listarReclamos({ ...filtros, limit: filtros.limit ?? 200 }),
    staleTime: 15 * 1000,
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
    mutationFn: (body: { estado: string; nota?: string }) =>
      cambiarEstadoReclamo(id as number, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reclamos'] })
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
