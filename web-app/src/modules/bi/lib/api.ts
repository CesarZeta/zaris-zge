import { api } from '../../../lib/api'
import type { ApiResponseWithHeaders } from '../../../lib/api'
import type {
  AreaCatalogo,
  BiFiltros,
  BiResumen,
  EvolucionDiasItem,
  ItemTemporal,
  PendienteDetalle,
  PendienteGeo,
  PendientePorTipoItem,
  PendientesPorMesItem,
  PendientesResumen,
  PorAreaItem,
  PorCanalItem,
  PorEstadoItem,
  ResueltoDetalle,
  SlaResumen,
  SubreclamoDetalle,
  SubreclamoPorTipoItem,
  SubreclamosResumen,
  TiemposMensualItem,
  TiemposPorTipoItem,
} from './types'

// Endpoints de agregación. Router con guard JWT (§39); la UI gatea nivel <= 2.
const BASE = '/api/v1/bi'

export const biApi = {
  resumen: (f: BiFiltros = {}) =>
    api.get<BiResumen>(`${BASE}/resumen`, { params: { ...f } }),

  porEstado: (f: BiFiltros = {}) =>
    api.get<PorEstadoItem[]>(`${BASE}/por-estado`, { params: { ...f } }),

  porCanal: (f: BiFiltros = {}) =>
    api.get<PorCanalItem[]>(`${BASE}/por-canal`, { params: { ...f } }),

  porArea: (f: BiFiltros = {}) =>
    api.get<PorAreaItem[]>(`${BASE}/por-area`, { params: { ...f } }),

  mensual: (f: BiFiltros = {}) =>
    api.get<ItemTemporal[]>(`${BASE}/mensual`, { params: { ...f } }),

  // Serie diaria. Si `mes` viene, acota a ese mes (drill-down); sino usa el rango
  // desde/hasta del filtro global (modo "Día").
  diario: (mes: string | null, f: BiFiltros = {}) =>
    api.get<ItemTemporal[]>(`${BASE}/diario`, {
      params: mes
        ? { mes, id_area: f.id_area, prioridad: f.prioridad }
        : { desde: f.desde, hasta: f.hasta, id_area: f.id_area, prioridad: f.prioridad },
    }),

  catalogoAreas: () =>
    api.get<AreaCatalogo[]>(`${BASE}/catalogo/areas`),

  // ── Fase 2: Resueltos / SLA ──────────────────────────────────────────────
  slaResumen: (f: BiFiltros = {}) =>
    api.get<SlaResumen>(`${BASE}/sla-resumen`, { params: { id_area: f.id_area, prioridad: f.prioridad } }),

  tiemposMensual: (f: BiFiltros = {}) =>
    api.get<TiemposMensualItem[]>(`${BASE}/tiempos-mensual`, { params: { ...f } }),

  tiemposPorTipo: (f: BiFiltros = {}, limit = 10) =>
    api.get<TiemposPorTipoItem[]>(`${BASE}/tiempos-por-tipo`, { params: { ...f, limit } }),

  evolucionDias: (f: BiFiltros = {}) =>
    api.get<EvolucionDiasItem[]>(`${BASE}/evolucion-dias`, { params: { ...f } }),

  resueltosDetalle: (f: BiFiltros = {}, limit = 50, offset = 0) =>
    api.getWithHeaders<ResueltoDetalle[]>(`${BASE}/resueltos-detalle`, { params: { ...f, limit, offset } }),

  // ── Fase 3: Pendientes ───────────────────────────────────────────────────
  pendientesResumen: (f: BiFiltros = {}) =>
    api.get<PendientesResumen>(`${BASE}/pendientes-resumen`, { params: { ...f } }),

  pendientesPorMes: (f: BiFiltros = {}) =>
    api.get<PendientesPorMesItem[]>(`${BASE}/pendientes-por-mes`, { params: { ...f } }),

  pendientesPorTipo: (f: BiFiltros = {}, limit = 10) =>
    api.get<PendientePorTipoItem[]>(`${BASE}/pendientes-por-tipo`, { params: { ...f, limit } }),

  // Histograma temporal de pendientes (desglose por estado). Shape compatible con ItemTemporal.
  pendientesMensual: (f: BiFiltros = {}) =>
    api.get<ItemTemporal[]>(`${BASE}/pendientes-mensual`, { params: { ...f } }),

  pendientesDiario: (mes: string | null, f: BiFiltros = {}) =>
    api.get<ItemTemporal[]>(`${BASE}/pendientes-diario`, {
      params: mes
        ? { mes, id_area: f.id_area, prioridad: f.prioridad }
        : { desde: f.desde, hasta: f.hasta, id_area: f.id_area, prioridad: f.prioridad },
    }),

  pendientesDetalle: (f: BiFiltros = {}, limit = 50, offset = 0) =>
    api.getWithHeaders<PendienteDetalle[]>(`${BASE}/pendientes-detalle`, { params: { ...f, limit, offset } }),

  pendientesGeo: (f: BiFiltros = {}) =>
    api.get<PendienteGeo[]>(`${BASE}/pendientes-geo`, { params: { ...f } }),

  // ── Fase 4: Subreclamos ──────────────────────────────────────────────────
  subreclamosResumen: (f: BiFiltros = {}) =>
    api.get<SubreclamosResumen>(`${BASE}/subreclamos-resumen`, { params: { ...f } }),

  subreclamosMensual: (f: BiFiltros = {}) =>
    api.get<ItemTemporal[]>(`${BASE}/subreclamos-mensual`, { params: { ...f } }),

  subreclamosDiario: (mes: string | null, f: BiFiltros = {}) =>
    api.get<ItemTemporal[]>(`${BASE}/subreclamos-diario`, {
      params: mes
        ? { mes, id_area: f.id_area, prioridad: f.prioridad }
        : { desde: f.desde, hasta: f.hasta, id_area: f.id_area, prioridad: f.prioridad },
    }),

  subreclamosPorTipo: (f: BiFiltros = {}, limit = 10) =>
    api.get<SubreclamoPorTipoItem[]>(`${BASE}/subreclamos-por-tipo`, { params: { ...f, limit } }),

  subreclamosDetalle: (f: BiFiltros = {}, limit = 50, offset = 0) =>
    api.getWithHeaders<SubreclamoDetalle[]>(`${BASE}/subreclamos-detalle`, { params: { ...f, limit, offset } }),
}

export type { ApiResponseWithHeaders }
