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

// Histograma con series DINÁMICAS (apilado por tipo de reclamo: top 6 + Otros).
// El backend devuelve las series junto con los items (2026-08-30).
export interface SerieDinamica {
  key: string
  name: string
}
export interface HistogramaDinamico {
  series: SerieDinamica[]
  items: ItemTemporal[]
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
  // Días desde el alta (semáforo del mapa: 0-3 / 4-7 / +7). 2026-08-30.
  dias_demora?: number | null
}

export interface AreaCatalogo {
  id_area: number
  nombre: string
}

// Área de servicio por defecto del usuario (GET /bi/mi-area, 2026-08-30).
export interface MiArea {
  id_area: number | null
  nombre: string | null
  origen: 'agente' | 'sugerida' | null
}

// Detalle del universo filtrado (export de la sección Resumen).
export interface ReclamoDetalle {
  nro_reclamo: string | null
  fecha_alta: string | null
  fecha_cierre: string | null
  tipo: string
  prioridad: string
  estado: string
  canal: string
  area: string
  subarea: string
  direccion: string
  dias: number
  es_subreclamo: boolean
}

// Tipo de reclamo del catálogo (buscador del filtro global).
export interface TipoReclamoCatalogo {
  id_tipo_reclamo: number
  nombre: string
}

// Filtros GLOBALES del Operativo (una sola barra gobierna todas las secciones
// y las exportaciones, 2026-08-30). `tipo_nombre` es solo para mostrar en la UI
// (no viaja al backend).
export interface BiFiltros {
  desde?: string // 'YYYY-MM-DD'
  hasta?: string
  // Chips de año + tildes de meses (2026-08-30). Se combinan con desde/hasta por AND;
  // la UI limpia unos cuando se usan los otros.
  anio?: number
  meses?: number[]
  id_area?: number
  prioridad?: string
  estado?: string
  id_tipo_reclamo?: number
  tipo_nombre?: string
  canal?: string
  // Filtro del Ejecutivo (2026-08-30): localidad del catalogo.
  id_localidad?: number
}

// KPIs comparativos de la fila única de cada sección (GET /bi/comparativo).
export interface Comparativo {
  seccion: string
  total: number
  prom_mensual_12m: number
  total_12m: number
  anio_anterior: number
  comparable_actual: number
  var_pct: number
  periodo_actual: string
  periodo_anterior: string
}

// ── Ejecutivo ("Análisis de demanda ciudadana", 2026-08-30) ──────────────────
// Shapes de /api/v1/bi/ejecutivo/*.

export interface EjNivel {
  clasificacion: number // 1..5 (1-2 insatisfecho · 3 neutro · 4-5 satisfecho)
  total: number
}

export interface EjScore {
  total: number
  abiertos: number
  total_anterior: number | null
  var_pct: number | null
  prom_dias: number | null
  pct_cierre: number | null
  pct_sla: number | null
  pct_sat: number | null
  tasa_respuesta: number | null
  encuestas_enviadas: number
  encuestas_respondidas: number
  niveles: EjNivel[]
}

// Métricas comunes de la matriz y los tops (por subárea o por tipo).
export interface EjFilaBase {
  total: number
  var_pct: number | null
  prom_dias: number | null
  pct_cierre: number | null
  pct_sla: number | null
  pct_sat: number | null
  pct_rep: number | null
}

export interface EjTipoFila extends EjFilaBase {
  id_tipo: number | null
  tipo: string
}

export interface EjSubareaFila extends EjFilaBase {
  id_subarea: number | null
  subarea: string
  tipos: EjTipoFila[]
}

export interface EjMatriz {
  filas: EjSubareaFila[]
  total: EjFilaBase
}

export interface EjTopTipo extends EjFilaBase {
  id_tipo: number | null
  tipo: string
  subarea: string
}

export interface EjAltasCierresItem {
  mes: string
  altas: number
  cierres: number
}

export interface EjEvolucionItem {
  mes: string
  total: number
  pct_cierre: number | null
  pct_sla: number | null
  pct_sat: number | null
}

export interface EjPorLocalidadItem {
  id_localidad: number | null
  localidad: string
  total: number
}

export interface EjSatCierreItem {
  nombre: string
  total: number
  pct_cierre: number | null
  pct_sat: number | null
}

export interface EjGeoPunto {
  id_reclamo: number
  nro_reclamo: string | null
  estado: string
  prioridad: string | null
  tipo_nombre: string
  descripcion: string | null
  latitud: number
  longitud: number
  cerrado: boolean
  clasificacion: number | null
}

export interface EjLocalidadCatalogo {
  id_localidad: number
  nombre: string
  total: number
}
