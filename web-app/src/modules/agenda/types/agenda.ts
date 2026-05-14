// Tipos del modulo Agenda - matchean los schemas Pydantic v2 del backend.

export type TipoRecurso = 'agente' | 'equipo' | 'espacio'
export type TipoOcupacion = 'ot' | 'evento' | 'turno'
export type TipoQR = 'nominal' | 'generico' | 'ninguno'
export type OrigenReserva = 'backoffice' | 'autoservicio'

export interface EstadoCatalogo {
  id: number
  codigo: string
  descripcion: string | null
  orden: number | null
}

export interface Evento {
  id_evento: number
  nombre: string
  descripcion: string | null
  id_subarea: number | null
  fecha: string         // YYYY-MM-DD
  hora_inicio: string   // HH:MM:SS
  hora_fin: string      // HH:MM:SS
  capacidad_ciudadanos: number
  cantidad_encargados: number
  tipo_qr: TipoQR
  admite_autoservicio: boolean
  token_publico: string | null
  id_estado_evento: number
  estado_codigo: string | null
  activo: boolean
  id_municipio: number
  fecha_alta: string
  fecha_modificacion: string
}

export interface EventoDetalle extends Evento {
  cupo_disponible: number
  reservas_activas: number
  encargados: EventoEncargado[]
}

export interface EventoCreatePayload {
  nombre: string
  descripcion?: string | null
  id_subarea?: number | null
  fecha: string
  hora_inicio: string
  hora_fin: string
  capacidad_ciudadanos: number
  cantidad_encargados: number
  tipo_qr: TipoQR
  admite_autoservicio: boolean
  id_municipio?: number
}

export type EventoUpdatePayload = Partial<EventoCreatePayload>

export interface EventoEncargado {
  id_evento_encargado: number
  id_evento: number
  tipo_recurso: TipoRecurso
  id_recurso: number
  recurso_nombre: string | null
  activo: boolean
  fecha_alta: string
}

export interface EncargadoCreateResponse {
  encargado: EventoEncargado
  ocupacion_creada_id: number
  conflictos: Record<string, unknown>[]
  mensaje: string | null
}

export interface Reserva {
  id_evento_reserva: number
  id_evento: number
  id_ciudadano: number
  ciudadano_apellido: string | null
  ciudadano_nombre: string | null
  ciudadano_dni: string | null
  id_estado_reserva: number
  estado_codigo: string | null
  origen: OrigenReserva
  qr_codigo: string | null
  activo: boolean
  fecha_alta: string
}

export interface ReservaCreatePayload {
  id_ciudadano: number
  origen: OrigenReserva
}

export interface Ocupacion {
  id_ocupacion: number
  tipo: TipoOcupacion
  tipo_recurso: TipoRecurso
  id_recurso: number
  fecha: string
  hora_inicio: string
  hora_fin: string
  id_orden_trabajo: number | null
  id_evento: number | null
  id_ciudadano: number | null
  duracion_aplicada_min: number | null
  rol_en_evento: string | null
  motivo: string | null
  descripcion_corta: string | null
  activo: boolean
  id_municipio: number
  fecha_alta: string
}

export interface OcupacionCreatePayload {
  tipo: TipoOcupacion
  tipo_recurso: TipoRecurso
  id_recurso: number
  fecha: string
  hora_inicio: string
  hora_fin: string
  id_orden_trabajo?: number | null
  id_evento?: number | null
  id_ciudadano?: number | null
  duracion_aplicada_min?: number | null
  rol_en_evento?: string | null
  motivo?: string | null
  id_municipio?: number
}

export type OcupacionUpdatePayload = Partial<Pick<
  OcupacionCreatePayload,
  'fecha' | 'hora_inicio' | 'hora_fin' | 'duracion_aplicada_min' | 'rol_en_evento' | 'motivo' | 'tipo_recurso' | 'id_recurso'
>>

export interface OcupacionCreated {
  ocupacion: Ocupacion
  conflictos: Record<string, unknown>[]
  mensaje: string | null
}

export interface Ausencia {
  id_ausencia: number
  fecha_desde: string
  fecha_hasta: string
  motivo: string | null
  genera_alerta: boolean | null
}

export interface RecursoAgenda {
  tipo_recurso: TipoRecurso
  id_recurso: number
  nombre: string | null
  desde: string
  hasta: string
  ocupaciones: Ocupacion[]
  ausencias: Ausencia[]
}

export interface DisponibilidadRangoEfectivo {
  hora_inicio: string   // HH:MM:SS
  hora_fin: string      // HH:MM:SS
  etiqueta: string | null
}

export interface EventoEnCalendario {
  id_evento: number
  nombre: string
  fecha: string
  hora_inicio: string
  hora_fin: string
  capacidad_ciudadanos: number
  reservas_activas: number
  cupo_libre: number
  estado_codigo: string | null
  id_espacio: number | null
  id_subarea: number | null
  encargados: Array<[string, number]>  // [tipo_recurso, id_recurso]
}

export interface CalendarioRecurso {
  tipo: TipoRecurso
  id_recurso: number
  nombre: string | null
  atendido: boolean | null  // null para agente/equipo, true/false para espacio
  ocupaciones: Ocupacion[]
  ausencias: Ausencia[]
  disponibilidad: DisponibilidadRangoEfectivo[]
}

export interface CalendarioDia {
  fecha: string
  id_municipio: number
  recursos: CalendarioRecurso[]
  eventos: EventoEnCalendario[]
}

export interface CalendarioSemanaDia {
  fecha: string
  ocupaciones: Ocupacion[]
  ausencias: Ausencia[]
  eventos: EventoEnCalendario[]
  disponibilidad_por_recurso: Record<string, DisponibilidadRangoEfectivo[]>
}

export interface CalendarioSemana {
  desde: string
  hasta: string
  id_municipio: number
  recursos: CalendarioRecurso[]
  dias: CalendarioSemanaDia[]
}

export interface CalendarioMesDia {
  fecha: string
  eventos: number
  ocupaciones_total: number
  ocupaciones_por_tipo: Record<string, number>
  ausencias: number
}

export interface CalendarioMes {
  anio: number
  mes: number
  id_municipio: number
  dias: CalendarioMesDia[]
}

export interface Conflicto {
  id_conflicto: number
  fecha_deteccion: string
  tipo_recurso: TipoRecurso
  id_recurso: number
  id_ocupacion_origen: number | null
  id_ocupacion_conflicto: number | null
  resuelto: boolean
  observaciones: string | null
  ocupacion_origen_detalle: Record<string, unknown> | null
  ocupacion_conflicto_detalle: Record<string, unknown> | null
}

// Ciudadano (BUC) - minima estructura que usamos en buscador
export interface CiudadanoMinimo {
  id_ciudadano: number
  apellido: string | null
  nombre: string | null
  doc_nro: string | null
  cuil: string | null
  telefono: string | null
  email: string | null
}

// Catalogos de autocompletar / filtros (sub-fase 3.B)
export interface SubareaItem {
  id_subarea: number
  nombre: string
  id_area: number | null
  area_nombre: string | null
}

export interface RecursoItem {
  tipo_recurso: TipoRecurso
  id_recurso: number
  nombre: string
}

export interface OTBusquedaItem {
  id_ot: number
  nro_ot: string | null
  estado_nombre: string | null
  reclamo_descripcion: string | null
  nro_reclamo: string | null
  id_agente: number | null
  id_equipo: number | null
}

export interface EventoBusquedaItem {
  id_evento: number
  nombre: string
  fecha: string
  hora_inicio: string
  hora_fin: string
  estado_codigo: string | null
}

// ============================================================================
// Sub-fase B2: filtros UI, conteos, espacios, disponibilidad
// ============================================================================

// 4 valores que mapean a los pills del toggle. NO se manda 'todos' al backend
// (por performance: /semana con todos es O(n*7)). El frontend siempre elige uno.
export type FiltroRecursoUI = 'agentes' | 'equipos' | 'espacios_atendidos' | 'espacios_desatendidos'

// Vistas de la sub-pestana 'Vistas' del AgendaLayout.
export type VistaGrilla = 'dia' | 'semana' | 'mes'

export interface RecursosConteos {
  agentes: number
  equipos: number
  espacios_atendidos: number
  espacios_desatendidos: number
}

export interface EspacioAgenda {
  id_espacio: number
  nombre: string
  descripcion: string | null
  direccion: string | null
  capacidad_personas: number | null
  atendido: boolean
  id_subarea: number | null
  subarea_nombre: string | null
  activo: boolean
  id_municipio: number
  fecha_alta: string
  fecha_modificacion: string
  agentes_vinculados: EspacioAgente[]
}

export interface EspacioAgendaCreatePayload {
  nombre: string
  descripcion?: string | null
  direccion?: string | null
  capacidad_personas?: number | null
  atendido: boolean
  id_subarea?: number | null
  id_municipio?: number
}

export type EspacioAgendaUpdatePayload = Partial<EspacioAgendaCreatePayload> & {
  activo?: boolean
}

export interface EspacioAgente {
  id_espacio_agente: number
  id_espacio: number
  id_agente: number
  agente_nombre: string | null
  activo: boolean
  fecha_alta: string
}

export interface DisponibilidadRecurso {
  id_disponibilidad: number
  tipo_recurso: TipoRecurso
  id_recurso: number
  dias_semana: number      // bitmask 0-127
  hora_inicio: string      // HH:MM:SS
  hora_fin: string
  vigente_desde: string | null  // YYYY-MM-DD
  vigente_hasta: string | null
  etiqueta: string | null
  activo: boolean
  id_municipio: number
  fecha_alta: string
  fecha_modificacion: string
}

export interface DisponibilidadRecursoCreatePayload {
  tipo_recurso: TipoRecurso
  id_recurso: number
  dias_semana: number
  hora_inicio: string
  hora_fin: string
  vigente_desde?: string | null
  vigente_hasta?: string | null
  etiqueta?: string | null
  id_municipio?: number
  id_subarea?: number | null
}

export type DisponibilidadRecursoUpdatePayload = Partial<Omit<DisponibilidadRecursoCreatePayload, 'tipo_recurso' | 'id_recurso' | 'id_municipio' | 'id_subarea'>> & {
  activo?: boolean
}
