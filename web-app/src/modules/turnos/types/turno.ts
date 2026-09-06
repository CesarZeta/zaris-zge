// mig 105 (colero): reservado -> llamado -> cumplido | ausente; y -> cancelado
export type EstadoTurno = 'reservado' | 'llamado' | 'cumplido' | 'ausente' | 'cancelado'
export type ClasePrestacion = 'atencion' | 'reserva_espacio'
export type TipoRecurso = 'agente' | 'espacio'

export interface TipoPrestacion {
  id_tipo_prestacion: number
  nombre: string
  descripcion: string | null
  clase: ClasePrestacion
  duracion_min: number
  tipo_recurso: TipoRecurso | null
  id_agente: number | null
  id_espacio: number | null
  recurso_nombre: string | null
  /** Ubicación donde se atiende (mig 103). Para recurso=espacio es ese espacio. */
  id_espacio_ubicacion: number | null
  ubicacion_nombre: string | null
  id_subarea: number | null
  subarea_nombre: string | null
  id_area: number | null
  area_nombre: string | null
  registra_atencion: boolean
  activo: boolean
}

export interface PrestacionInput {
  nombre: string
  descripcion?: string | null
  clase: ClasePrestacion
  duracion_min: number
  tipo_recurso: TipoRecurso
  id_agente?: number | null
  id_espacio?: number | null
  /** Ubicación donde se atiende. Si el recurso es un espacio y se omite,
   *  el backend usa ese mismo espacio. */
  id_espacio_ubicacion?: number | null
  id_subarea?: number | null
  registra_atencion?: boolean
}

export interface Turno {
  id_turno: number
  id_ciudadano: number
  ciudadano_nombre: string | null
  ciudadano_dni: string | null
  id_agente: number | null
  agente_nombre: string | null
  id_espacio: number | null
  espacio_nombre: string | null
  recurso_tipo: 'agente' | 'espacio' | null
  recurso_nombre: string | null
  /** Ubicación donde se atiende, copiada de la prestación al reservar (mig 103). */
  id_espacio_ubicacion: number | null
  ubicacion_nombre: string | null
  id_tipo_prestacion: number
  prestacion_nombre: string | null
  prestacion_clase: string | null
  registra_atencion: boolean | null
  prestacion_id_area: number | null
  prestacion_area_nombre: string | null
  id_ocupacion: number | null
  fecha: string
  hora_inicio: string
  hora_fin: string
  estado: EstadoTurno
  observaciones: string | null
  /** Colero (mig 105): número visible, asignado al primer llamado. */
  numero_diario: string | null
  ultimo_llamado_en: string | null
  ultimo_llamado_puesto: string | null
  cant_llamados: number
  activo: boolean
  id_municipio: number
  id_subarea: number | null
  fecha_alta: string
  fecha_modificacion: string
}

export interface CrearTurnoBody {
  id_ciudadano: number
  id_tipo_prestacion: number
  fecha: string
  hora_inicio: string
  hora_fin?: string
  observaciones?: string | null
  id_municipio?: number
  id_subarea?: number | null
}

export interface ReprogramarTurnoBody {
  id_tipo_prestacion?: number
  fecha?: string
  hora_inicio?: string
  hora_fin?: string
  observaciones?: string | null
}

/** Body de PATCH /turnos/{id}/cumplir. Si la prestación registra historia de
 *  atención, `intervencion` es obligatoria (el backend rechaza con 422). */
export interface CumplirTurnoBody {
  observaciones?: string | null
  intervencion?: string | null
  recomendaciones?: string | null
}

/** Una atención registrada al cumplir un turno (historia del ciudadano). */
export interface TurnoAtencion {
  id_turno_atencion: number
  id_turno: number
  id_ciudadano: number
  fecha: string
  prestacion_nombre: string | null
  recurso_nombre: string | null
  intervencion: string
  recomendaciones: string | null
  atendido_por: string | null
  fecha_alta: string
}

/** Una ubicación de atención (espacio con prestaciones o agentes vinculados),
 *  con su gestión (área vía subárea) y los contadores de turnos del día. */
export interface UbicacionTurnos {
  id_espacio: number
  nombre: string
  direccion: string | null
  id_subarea: number | null
  subarea_nombre: string | null
  id_area: number | null
  area_nombre: string | null
  prestaciones: number
  agentes: number
  reservados: number
  llamados: number
  cumplidos: number
  ausentes: number
  cancelados: number
}

export interface MesaRango {
  hora_inicio: string
  hora_fin: string
}

export interface MesaOcupacion {
  id_ocupacion: number
  tipo: string // 'turno' | 'evento' | 'ot' | 'bloqueo'
  hora_inicio: string
  hora_fin: string
  motivo: string | null
  id_turno: number | null
  turno_estado: string | null
  ciudadano_nombre: string | null
  prestacion_nombre: string | null
  /** Turno del mismo agente pero en OTRA ubicación: viene enmascarado (solo
   *  el bloque horario) — muestra al agente ocupado sin exponer la otra mesa. */
  de_otra_ubicacion: boolean
}

export interface MesaRecurso {
  tipo: 'espacio' | 'agente'
  id_recurso: number
  nombre: string
  disponibilidad: MesaRango[]
  ocupaciones: MesaOcupacion[]
}

/** Mesa del día de una ubicación: disponibilidad + ocupación por recurso. */
export interface MesaUbicacion {
  id_espacio: number
  nombre: string
  direccion: string | null
  fecha: string
  /** Colero (mig 105): token de la pantalla de sala. Sólo llega a nivel <= 2. */
  token_pantalla: string | null
  recursos: MesaRecurso[]
}

export interface ListarTurnosFiltros {
  estado?: EstadoTurno
  id_agente?: number
  id_espacio?: number
  id_espacio_ubicacion?: number
  id_ciudadano?: number
  id_tipo_prestacion?: number
  fecha_desde?: string
  fecha_hasta?: string
}

/** Pantalla de sala del colero (mig 105). Respuesta PÚBLICA: sólo número y
 *  "Nombre I." — nunca apellido completo, DNI, prestación ni id de turno. */
export interface PantallaLlamado {
  numero: string | null
  nombre_display: string
  puesto: string | null
  llamado_en: string
}

export interface PantallaColero {
  ubicacion_nombre: string
  fecha: string
  llamando: PantallaLlamado[]
  previos: PantallaLlamado[]
}
