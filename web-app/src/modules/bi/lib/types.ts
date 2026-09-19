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
  // Filtro del Ejecutivo (2026-08-30, 2ª tanda): subárea dentro del área.
  id_subarea?: number
  // Filtros del tablero de ATENCIÓN (F6, 2026-09-19): ubicación (espacio) y prestación.
  id_espacio_ubicacion?: number
  id_tipo_prestacion?: number
}

// KPIs comparativos de la fila única de cada sección (GET /bi/comparativo).
export interface Comparativo {
  seccion: string
  total: number
  prom_mensual_12m: number
  total_12m: number
  /** Total del período INMEDIATAMENTE anterior (regla del Ejecutivo, César
   *  2026-09-01). El nombre es legacy del contrato: ya no es "año anterior". */
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

// Indicadores del período anterior (para los triangulitos de variación).
export interface EjIndicadoresAnt {
  total: number
  prom_dias: number | null
  pct_cierre: number | null
  pct_sla: number | null
  pct_sat: number | null
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
  ant?: EjIndicadoresAnt | null
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

export interface EjSubareaCatalogo {
  id_subarea: number
  nombre: string
  total: number
}

// ── Atención ("BI de atención por gestión", F6 2026-09-19) ────────────────────
// Shapes de /api/v1/bi/atencion/*. La jerarquía es GESTIÓN (área) → UBICACIÓN
// (espacio) → prestación / agente → turnos.

export interface AtIndicadores {
  total: number
  cumplidos: number
  ausentes: number
  cancelados: number
  pendientes: number
  autoservicio: number
  llamados: number
  re_llamados: number
  a_tiempo: number
  espera_prom_min: number | null
  espera_max_min: number | null
  atenciones_registradas: number
  horas_atendidas: number | null
  enviadas: number
  respuestas: number
  satisfechos: number
  /** cumplidos / otorgados con desenlace (sin pendientes) */
  pct_cumplimiento: number | null
  /** ausentes / (cumplidos + ausentes): turnos caídos entre los que llegaron a su hora */
  pct_ausentismo: number | null
  pct_cancelacion: number | null
  pct_a_tiempo: number | null
  pct_autoservicio: number | null
  pct_sat: number | null
  tasa_respuesta: number | null
}

export interface AtScore extends AtIndicadores {
  var_pct: number | null
  anterior: AtIndicadores | null
  por_estado: Array<{ estado: string; total: number }>
  por_origen: Array<{ origen: string; total: number }>
  niveles: EjNivel[]
}

export interface AtFila extends AtIndicadores {
  var_pct: number | null
  ant: AtIndicadores | null
}
export interface AtPrestacionFila extends AtFila {
  id_tipo_prestacion: number | null
  prestacion: string
}
export interface AtUbicacionFila extends AtFila {
  id_espacio: number | null
  ubicacion: string
  gestion: string
  prestaciones: AtPrestacionFila[]
}
export interface AtMatriz {
  filas: AtUbicacionFila[]
  total: AtFila
}

export interface AtEvolucionItem {
  mes: string
  total: number
  cumplidos: number
  ausentes: number
  cancelados: number
  pct_cumplimiento: number | null
  pct_ausentismo: number | null
  espera_prom_min: number | null
  pct_sat: number | null
}

export interface AtPorUbicacion extends AtIndicadores {
  id_espacio: number | null
  ubicacion: string
  gestion: string
}
export interface AtPorAgente extends AtIndicadores {
  id_agente: number
  agente: string
  ubicaciones: string | null
}

export interface AtEsperaUbicacion {
  id_espacio: number | null
  ubicacion: string
  gestion: string
  llamados: number
  re_llamados: number
  a_tiempo: number
  pct_a_tiempo: number | null
  espera_prom_min: number | null
  espera_max_min: number | null
}
export interface AtEspera {
  llamados: number
  re_llamados: number
  a_tiempo: number
  pct_a_tiempo: number | null
  espera_prom_min: number | null
  espera_max_min: number | null
  tolerancia_min: number
  tramos: Array<{ tramo: string; total: number }>
  por_ubicacion: AtEsperaUbicacion[]
}

export interface AtGuardiaInd {
  derivaciones: number
  atendidas: number
  ausentes: number
  pendientes: number
  con_ciudadano: number
  pct_atendidas: number | null
  pct_ausentes: number | null
  demora_prom_min: number | null
  demora_max_min: number | null
}
export interface AtGuardia extends AtGuardiaInd {
  var_pct: number | null
  anterior: AtGuardiaInd | null
  por_estado: Array<{ estado: string; total: number }>
  por_agente: Array<AtGuardiaInd & { id_agente: number; agente: string }>
  por_tipo: Array<AtGuardiaInd & { id_tipo: number | null; tipo: string }>
  por_prioridad: Array<AtGuardiaInd & { id_prioridad: number | null; prioridad: string }>
}

export interface AtEventosInd {
  eventos: number
  eventos_realizados: number
  eventos_cancelados: number
  cupo_total: number
  reservas: number
  vigentes: number
  asistieron: number
  canceladas: number
  autoservicio: number
  /** asistieron / reservas vigentes, SOLO de eventos ya realizados */
  pct_asistencia: number | null
  pct_cupo: number | null
  pct_autoservicio: number | null
}
export interface AtEventoFila {
  id_evento: number
  evento: string
  fecha: string
  hora_inicio: string | null
  estado: string
  ubicacion: string
  gestion: string
  cupo: number | null
  reservas: number
  vigentes: number
  asistieron: number
  canceladas: number
  autoservicio: number
  realizado: boolean
  pct_cupo: number | null
  pct_asistencia: number | null
}
export interface AtEventos extends AtEventosInd {
  var_pct: number | null
  anterior: AtEventosInd | null
  por_estado: Array<{ estado: string; total: number }>
  por_evento: AtEventoFila[]
}

export interface AtTurnoDetalle {
  id_turno: number
  fecha: string
  hora_inicio: string
  hora_fin: string
  numero_diario: string | null
  estado: string
  origen: string
  gestion: string
  ubicacion: string
  prestacion: string
  agente: string | null
  primer_llamado: string | null
  n_llamados: number
  espera_min: number | null
  atencion_registrada: boolean
  csat: number | null
}
export interface AtGuardiaDetalle {
  id_emergencia_atencion: number
  numero_operativo: string | null
  estado: string
  derivado_en: string
  atendido_en: string | null
  demora_min: number | null
  tipo: string
  prioridad: string
  ubicacion: string
  agente: string | null
  con_ciudadano: boolean
}

export interface AtUbicacionCatalogo {
  id_espacio: number
  nombre: string
  id_area: number | null
  gestion: string
}
export interface AtPrestacionCatalogo {
  id_tipo_prestacion: number
  nombre: string
  activo: boolean
  id_espacio_ubicacion: number | null
}
