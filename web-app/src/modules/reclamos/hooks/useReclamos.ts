import { useQuery } from '@tanstack/react-query'
import {
  getCatalogoAreas,
  getCatalogoTipos,
  getStats,
  listarAdjuntos,
  listarReclamos,
  obtenerReclamo,
} from '../api/reclamosApi'

const HORA = 60 * 60 * 1000

// ── Catalogos ──
export function useAreasCatalogo() {
  return useQuery({ queryKey: ['reclamos', 'areas'], queryFn: getCatalogoAreas, staleTime: HORA })
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
