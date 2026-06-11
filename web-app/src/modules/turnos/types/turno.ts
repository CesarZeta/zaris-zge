export type EstadoTurno = 'reservado' | 'cumplido' | 'cancelado'
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

export interface ListarTurnosFiltros {
  estado?: EstadoTurno
  id_agente?: number
  id_espacio?: number
  id_ciudadano?: number
  id_tipo_prestacion?: number
  fecha_desde?: string
  fecha_hasta?: string
}
