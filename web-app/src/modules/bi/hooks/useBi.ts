import { useQuery } from '@tanstack/react-query'
import { biApi } from '../lib/api'
import type { BiFiltros } from '../lib/types'

// Clave estable a partir de los filtros (react-query la usa para cachear).
const key = (sub: string, f: BiFiltros) => ['bi', sub, f.desde, f.hasta, f.id_area, f.prioridad] as const

export function useResumen(f: BiFiltros) {
  return useQuery({ queryKey: key('resumen', f), queryFn: () => biApi.resumen(f) })
}

export function usePorEstado(f: BiFiltros) {
  return useQuery({ queryKey: key('por-estado', f), queryFn: () => biApi.porEstado(f) })
}

export function usePorCanal(f: BiFiltros) {
  return useQuery({ queryKey: key('por-canal', f), queryFn: () => biApi.porCanal(f) })
}

export function usePorArea(f: BiFiltros) {
  return useQuery({ queryKey: key('por-area', f), queryFn: () => biApi.porArea(f) })
}

// Nota: el histograma temporal (HistogramaTemporal) maneja sus propias queries
// mensual/diario internamente con fetchers inyectados — no hay useMensual/useDiario.

export function useCatalogoAreas() {
  return useQuery({ queryKey: ['bi', 'catalogo-areas'], queryFn: () => biApi.catalogoAreas(), staleTime: 5 * 60_000 })
}

// ── Fase 2: Resueltos / SLA ─────────────────────────────────────────────────
export function useSlaResumen(f: BiFiltros) {
  return useQuery({ queryKey: ['bi', 'sla-resumen', f.id_area, f.prioridad], queryFn: () => biApi.slaResumen(f) })
}

export function useTiemposMensual(f: BiFiltros) {
  return useQuery({ queryKey: key('tiempos-mensual', f), queryFn: () => biApi.tiemposMensual(f) })
}

export function useTiemposPorTipo(f: BiFiltros, limit = 10) {
  return useQuery({ queryKey: [...key('tiempos-tipo', f), limit], queryFn: () => biApi.tiemposPorTipo(f, limit) })
}

export function useEvolucionDias(f: BiFiltros) {
  return useQuery({ queryKey: key('evolucion-dias', f), queryFn: () => biApi.evolucionDias(f) })
}

export function useResueltosDetalle(f: BiFiltros, limit = 50, offset = 0) {
  return useQuery({
    queryKey: [...key('resueltos-detalle', f), limit, offset],
    queryFn: () => biApi.resueltosDetalle(f, limit, offset),
  })
}

// ── Fase 3: Pendientes ──────────────────────────────────────────────────────
export function usePendientesResumen(f: BiFiltros) {
  return useQuery({ queryKey: key('pend-resumen', f), queryFn: () => biApi.pendientesResumen(f) })
}

export function usePendientesPorMes(f: BiFiltros) {
  return useQuery({ queryKey: key('pend-mes', f), queryFn: () => biApi.pendientesPorMes(f) })
}

export function usePendientesPorTipo(f: BiFiltros, limit = 10) {
  return useQuery({ queryKey: [...key('pend-tipo', f), limit], queryFn: () => biApi.pendientesPorTipo(f, limit) })
}

export function usePendientesDetalle(f: BiFiltros, limit = 50, offset = 0) {
  return useQuery({
    queryKey: [...key('pend-detalle', f), limit, offset],
    queryFn: () => biApi.pendientesDetalle(f, limit, offset),
  })
}

export function usePendientesGeo(f: BiFiltros) {
  return useQuery({ queryKey: key('pend-geo', f), queryFn: () => biApi.pendientesGeo(f) })
}

// ── Fase 4: Subreclamos ─────────────────────────────────────────────────────
export function useSubreclamosResumen(f: BiFiltros) {
  return useQuery({ queryKey: key('sub-resumen', f), queryFn: () => biApi.subreclamosResumen(f) })
}

export function useSubreclamosPorTipo(f: BiFiltros, limit = 10) {
  return useQuery({ queryKey: [...key('sub-tipo', f), limit], queryFn: () => biApi.subreclamosPorTipo(f, limit) })
}

export function useSubreclamosDetalle(f: BiFiltros, limit = 50, offset = 0) {
  return useQuery({
    queryKey: [...key('sub-detalle', f), limit, offset],
    queryFn: () => biApi.subreclamosDetalle(f, limit, offset),
  })
}
