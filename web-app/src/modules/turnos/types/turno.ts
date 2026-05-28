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

export interface ListarTurnosFiltros {
  estado?: EstadoTurno
  id_agente?: number
  id_espacio?: number
  id_ciudadano?: number
  id_tipo_prestacion?: number
  fecha_desde?: string
  fecha_hasta?: string
}
