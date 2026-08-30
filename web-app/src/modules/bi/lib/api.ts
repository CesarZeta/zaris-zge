import { api } from '../../../lib/api'
import type { ApiResponseWithHeaders } from '../../../lib/api'
import type {
  AreaCatalogo,
  BiFiltros,
  BiResumen,
  EvolucionDiasItem,
  HistogramaDinamico,
  ItemTemporal,
  MiArea,
  PendienteDetalle,
  PendienteGeo,
  PendientePorTipoItem,
  PendientesResumen,
  PorAreaItem,
  PorCanalItem,
  PorEstadoItem,
  ReclamoDetalle,
  ResueltoDetalle,
  SlaResumen,
  SubreclamoDetalle,
  SubreclamoPorTipoItem,
  SubreclamosResumen,
  TiemposMensualItem,
  TiemposPorTipoItem,
  TipoReclamoCatalogo,
} from './types'

// Endpoints de agregación. Router con guard JWT (§39); la UI gatea nivel <= 2.
const BASE = '/api/v1/bi'

// Filtros globales → query params. `tipo_nombre` es solo UI, no viaja.
function qp(f: BiFiltros) {
  return {
    desde: f.desde, hasta: f.hasta, id_area: f.id_area, prioridad: f.prioridad,
    estado: f.estado, id_tipo_reclamo: f.id_tipo_reclamo, canal: f.canal,
  }
}
// Sin el rango de fechas (drill a un mes concreto).
function qpSinFechas(f: BiFiltros) {
  return {
    id_area: f.id_area, prioridad: f.prioridad,
    estado: f.estado, id_tipo_reclamo: f.id_tipo_reclamo, canal: f.canal,
  }
}

export const biApi = {
  resumen: (f: BiFiltros = {}) =>
    api.get<BiResumen>(`${BASE}/resumen`, { params: qp(f) }),

  porEstado: (f: BiFiltros = {}) =>
    api.get<PorEstadoItem[]>(`${BASE}/por-estado`, { params: qp(f) }),

  porCanal: (f: BiFiltros = {}) =>
    api.get<PorCanalItem[]>(`${BASE}/por-canal`, { params: qp(f) }),

  porArea: (f: BiFiltros = {}) =>
    api.get<PorAreaItem[]>(`${BASE}/por-area`, { params: qp(f) }),

  mensual: (f: BiFiltros = {}) =>
    api.get<ItemTemporal[]>(`${BASE}/mensual`, { params: qp(f) }),

  // Serie diaria. Si `mes` viene, acota a ese mes (drill-down); sino usa el rango
  // desde/hasta del filtro global (modo "Día").
  diario: (mes: string | null, f: BiFiltros = {}) =>
    api.get<ItemTemporal[]>(`${BASE}/diario`, {
      params: mes ? { mes, ...qpSinFechas(f) } : qp(f),
    }),

  // Histograma apilado por TIPO de reclamo (top 6 + Otros), toggle del Resumen.
  mensualPorTipo: (f: BiFiltros = {}) =>
    api.get<HistogramaDinamico>(`${BASE}/mensual-por-tipo`, { params: qp(f) }),

  diarioPorTipo: (mes: string | null, f: BiFiltros = {}) =>
    api.get<HistogramaDinamico>(`${BASE}/diario-por-tipo`, {
      params: mes ? { mes, ...qpSinFechas(f) } : qp(f),
    }),

  // Export del universo filtrado (sección Resumen).
  reclamosDetalle: (f: BiFiltros = {}, limit = 50, offset = 0) =>
    api.getWithHeaders<ReclamoDetalle[]>(`${BASE}/reclamos-detalle`, { params: { ...qp(f), limit, offset } }),

  catalogoAreas: () =>
    api.get<AreaCatalogo[]>(`${BASE}/catalogo/areas`),

  miArea: () =>
    api.get<MiArea>(`${BASE}/mi-area`),

  // Buscador del filtro "Tipo de reclamo" (catálogo de Reclamos, JWT).
  buscarTipos: (q: string, id_area?: number) =>
    api.get<TipoReclamoCatalogo[]>('/api/v1/reclamos/catalogo/tipos', { params: { q, id_area, limit: 20 } }),

  // ── Fase 2: Resueltos / SLA ──────────────────────────────────────────────
  slaResumen: (f: BiFiltros = {}) =>
    api.get<SlaResumen>(`${BASE}/sla-resumen`, { params: qpSinFechas(f) }),

  tiemposMensual: (f: BiFiltros = {}) =>
    api.get<TiemposMensualItem[]>(`${BASE}/tiempos-mensual`, { params: qp(f) }),

  tiemposPorTipo: (f: BiFiltros = {}, limit = 10) =>
    api.get<TiemposPorTipoItem[]>(`${BASE}/tiempos-por-tipo`, { params: { ...qp(f), limit } }),

  evolucionDias: (f: BiFiltros = {}) =>
    api.get<EvolucionDiasItem[]>(`${BASE}/evolucion-dias`, { params: qp(f) }),

  resueltosDetalle: (f: BiFiltros = {}, limit = 50, offset = 0) =>
    api.getWithHeaders<ResueltoDetalle[]>(`${BASE}/resueltos-detalle`, { params: { ...qp(f), limit, offset } }),

  // ── Fase 3: Pendientes ───────────────────────────────────────────────────
  pendientesResumen: (f: BiFiltros = {}) =>
    api.get<PendientesResumen>(`${BASE}/pendientes-resumen`, { params: qp(f) }),

  pendientesPorTipo: (f: BiFiltros = {}, limit = 10) =>
    api.get<PendientePorTipoItem[]>(`${BASE}/pendientes-por-tipo`, { params: { ...qp(f), limit } }),

  // Histograma temporal de pendientes (desglose por estado). Shape compatible con ItemTemporal.
  pendientesMensual: (f: BiFiltros = {}) =>
    api.get<ItemTemporal[]>(`${BASE}/pendientes-mensual`, { params: qp(f) }),

  pendientesDiario: (mes: string | null, f: BiFiltros = {}) =>
    api.get<ItemTemporal[]>(`${BASE}/pendientes-diario`, {
      params: mes ? { mes, ...qpSinFechas(f) } : qp(f),
    }),

  pendientesDetalle: (f: BiFiltros = {}, limit = 50, offset = 0) =>
    api.getWithHeaders<PendienteDetalle[]>(`${BASE}/pendientes-detalle`, { params: { ...qp(f), limit, offset } }),

  pendientesGeo: (f: BiFiltros = {}) =>
    api.get<PendienteGeo[]>(`${BASE}/pendientes-geo`, { params: qp(f) }),

  // ── Fase 4: Subreclamos ──────────────────────────────────────────────────
  subreclamosResumen: (f: BiFiltros = {}) =>
    api.get<SubreclamosResumen>(`${BASE}/subreclamos-resumen`, { params: qp(f) }),

  subreclamosMensual: (f: BiFiltros = {}) =>
    api.get<ItemTemporal[]>(`${BASE}/subreclamos-mensual`, { params: qp(f) }),

  subreclamosDiario: (mes: string | null, f: BiFiltros = {}) =>
    api.get<ItemTemporal[]>(`${BASE}/subreclamos-diario`, {
      params: mes ? { mes, ...qpSinFechas(f) } : qp(f),
    }),

  subreclamosPorTipo: (f: BiFiltros = {}, limit = 10) =>
    api.get<SubreclamoPorTipoItem[]>(`${BASE}/subreclamos-por-tipo`, { params: { ...qp(f), limit } }),

  subreclamosDetalle: (f: BiFiltros = {}, limit = 50, offset = 0) =>
    api.getWithHeaders<SubreclamoDetalle[]>(`${BASE}/subreclamos-detalle`, { params: { ...qp(f), limit, offset } }),
}

export type { ApiResponseWithHeaders }
