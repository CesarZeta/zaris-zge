// Tipos del módulo BI (Análisis de datos de gestión). Espejan las shapes que
// devuelven los endpoints /api/v1/bi/* del backend.

export interface BiResumen {
  total: number
  resueltos: number
  cancelados: number
  pendientes: number
  subreclamos: number
  pct_cumplido: number
}

export interface PorEstadoItem {
  estado: string
  total: number
}

export interface PorCanalItem {
  canal: string
  total: number
}

export interface PorAreaItem {
  id_area: number | null
  area: string
  total: number
  resueltos: number
  cancelados: number
  pendientes: number
}

export interface MensualItem {
  mes: string // 'YYYY-MM'
  total: number
  resueltos: number
  cancelados: number
  pendientes: number
}

export interface DiarioItem {
  dia: string // 'YYYY-MM-DD'
  total: number
  resueltos: number
  cancelados: number
  pendientes: number
}

// ── Fase 2: Resueltos / SLA ─────────────────────────────────────────────────
export interface SlaResumen {
  resueltos_mes_actual: number
  resueltos_mes_anterior: number
  dif_pct: number
  dias_cierre_promedio: number | null
  total_resueltos: number
  pct_dentro_sla: number | null
}

export interface TiemposMensualItem {
  mes: string // 'YYYY-MM'
  t0_3: number
  t4_7: number
  tmas7: number
  total: number
}

export interface TiemposPorTipoItem {
  tipo: string
  t0_3: number
  t4_7: number
  tmas7: number
  total: number
}

export interface EvolucionDiasItem {
  mes: string
  dias_prom: number
  total: number
}

export interface ResueltoDetalle {
  nro_reclamo: string | null
  fecha_cierre: string | null
  tipo: string
  prioridad: string
  dias: number
  canal: string
  area: string
}

// Item genérico del histograma temporal (HistogramaTemporal). Tiene 'mes' o 'dia',
// 'total', y las dataKeys de cada serie apilada.
export interface ItemTemporal {
  mes?: string
  dia?: string
  total: number
  [k: string]: string | number | undefined
}

// ── Fase 3: Pendientes ──────────────────────────────────────────────────────
export interface PendientesResumen {
  total: number
  dias_demora_promedio: number | null
  t0_3: number
  t4_7: number
  tmas7: number
  por_estado: PorEstadoItem[]
}

export interface PendientesPorMesItem {
  mes: string
  sin_asignar: number
  en_gestion: number
  en_espera: number
  en_auditoria: number
  total: number
}

export interface PendientePorTipoItem {
  tipo: string
  total: number
}

export interface PendienteDetalle {
  nro_reclamo: string | null
  fecha_alta: string | null
  tipo: string
  prioridad: string
  estado: string
  dias_demora: number
  canal: string
  area: string
}

// ── Fase 4: Subreclamos ─────────────────────────────────────────────────────
export interface SubreclamosResumen {
  total: number
  padres: number
  por_estado: PorEstadoItem[]
  por_estado_padre: PorEstadoItem[]
}

export interface SubreclamoPorTipoItem {
  tipo: string
  total: number
}

export interface SubreclamoDetalle {
  nro_reclamo: string | null
  fecha_alta: string | null
  tipo: string
  prioridad: string
  estado: string
  area: string
  nro_padre: string | null
  estado_padre: string | null
}

// Reclamo pendiente con coordenadas, para el mapa de geoposicionamiento.
export interface PendienteGeo {
  id_reclamo: number
  nro_reclamo: string | null
  tipo_nombre: string | null
  estado: string
  prioridad: string | null
  descripcion: string | null
  latitud: number | null
  longitud: number | null
}

export interface AreaCatalogo {
  id_area: number
  nombre: string
}

// Filtros comunes que la UI pasa a los endpoints.
export interface BiFiltros {
  desde?: string // 'YYYY-MM-DD'
  hasta?: string
  id_area?: number
  prioridad?: string
}
