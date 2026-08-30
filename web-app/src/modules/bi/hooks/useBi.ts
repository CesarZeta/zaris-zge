import { useQuery } from '@tanstack/react-query'
import { biApi } from '../lib/api'
import type { BiFiltros } from '../lib/types'

// Clave estable a partir de los filtros GLOBALES (react-query la usa para cachear).
// Incluye TODOS los campos que viajan al backend: si se agrega un filtro nuevo a
// BiFiltros hay que sumarlo acá o las vistas muestran datos viejos.
export const filtrosKey = (f: BiFiltros) =>
  [f.desde, f.hasta, f.anio, (f.meses ?? []).join(','), f.id_area, f.prioridad, f.estado, f.id_tipo_reclamo, f.canal, f.id_localidad] as const
const key = (sub: string, f: BiFiltros) => ['bi', sub, ...filtrosKey(f)] as const

// KPIs comparativos de la fila única de cada sección.
export function useComparativo(seccion: 'resumen' | 'respuesta' | 'pendientes' | 'subreclamos', f: BiFiltros) {
  return useQuery({ queryKey: key(`comparativo-${seccion}`, f), queryFn: () => biApi.comparativo(seccion, f) })
}

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

// Área de servicio por defecto del usuario (agente vinculado, o sugerida).
export function useMiArea() {
  return useQuery({ queryKey: ['bi', 'mi-area'], queryFn: () => biApi.miArea(), staleTime: 10 * 60_000 })
}

// ── Fase 2: Resueltos / SLA ─────────────────────────────────────────────────
export function useSlaResumen(f: BiFiltros) {
  // Sin fechas a propósito: los KPIs "último mes / mes anterior" usan el mes calendario.
  return useQuery({
    queryKey: ['bi', 'sla-resumen', f.id_area, f.prioridad, f.estado, f.id_tipo_reclamo, f.canal, f.anio, (f.meses ?? []).join(',')],
    queryFn: () => biApi.slaResumen(f),
  })
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

// ── Fase 3: Pendientes ──────────────────────────────────────────────────────
export function usePendientesResumen(f: BiFiltros) {
  return useQuery({ queryKey: key('pend-resumen', f), queryFn: () => biApi.pendientesResumen(f) })
}

export function usePendientesPorTipo(f: BiFiltros, limit = 10) {
  return useQuery({ queryKey: [...key('pend-tipo', f), limit], queryFn: () => biApi.pendientesPorTipo(f, limit) })
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

// ── Ejecutivo ("Análisis de demanda ciudadana", 2026-08-30) ─────────────────
export function useEjScore(f: BiFiltros) {
  return useQuery({ queryKey: key('ej-score', f), queryFn: () => biApi.ejScore(f) })
}

export function useEjMatriz(f: BiFiltros) {
  return useQuery({ queryKey: key('ej-matriz', f), queryFn: () => biApi.ejMatriz(f) })
}

export function useEjTopTipos(f: BiFiltros, orden: 'cantidad' | 'demora', limit = 10) {
  return useQuery({ queryKey: [...key(`ej-top-${orden}`, f), limit], queryFn: () => biApi.ejTopTipos(f, orden, limit) })
}

export function useEjAltasCierres(f: BiFiltros) {
  return useQuery({ queryKey: key('ej-altas-cierres', f), queryFn: () => biApi.ejAltasCierres(f) })
}

export function useEjEvolucion(f: BiFiltros) {
  return useQuery({ queryKey: key('ej-evolucion', f), queryFn: () => biApi.ejEvolucion(f) })
}

export function useEjCierresPorEstado(f: BiFiltros) {
  return useQuery({ queryKey: key('ej-cierres-estado', f), queryFn: () => biApi.ejCierresPorEstado(f) })
}

export function useEjHistorico(f: BiFiltros, dim: 'subarea' | 'canal' | 'localidad') {
  return useQuery({ queryKey: [...key(`ej-historico-${dim}`, f)], queryFn: () => biApi.ejHistorico(dim, f) })
}

export function useEjPorLocalidad(f: BiFiltros) {
  return useQuery({ queryKey: key('ej-por-localidad', f), queryFn: () => biApi.ejPorLocalidad(f) })
}

export function useEjSatCierre(f: BiFiltros, por: 'subarea' | 'localidad') {
  return useQuery({ queryKey: [...key(`ej-sat-cierre-${por}`, f)], queryFn: () => biApi.ejSatCierre(por, f) })
}

export function useEjGeo(f: BiFiltros) {
  return useQuery({ queryKey: key('ej-geo', f), queryFn: () => biApi.ejGeo(f) })
}

export function useEjCatalogoLocalidades() {
  return useQuery({ queryKey: ['bi', 'ej-catalogo-localidades'], queryFn: () => biApi.ejCatalogoLocalidades(), staleTime: 5 * 60_000 })
}
