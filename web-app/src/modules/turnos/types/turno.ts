export type EstadoTurno = 'reservado' | 'cumplido' | 'cancelado'

export interface TipoServicioTurno {
  id_tipo_servicio_turno: number
  nombre: string
  descripcion: string | null
  duracion_min: number
  activo: boolean
}

export interface Turno {
  id_turno: number
  id_ciudadano: number
  ciudadano_nombre: string | null
  ciudadano_dni: string | null
  id_agente: number
  agente_nombre: string | null
  id_tipo_servicio_turno: number
  tipo_servicio_nombre: string | null
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
  id_agente: number
  id_tipo_servicio_turno: number
  fecha: string
  hora_inicio: string
  hora_fin?: string
  observaciones?: string | null
  id_municipio?: number
  id_subarea?: number | null
}

export interface ReprogramarTurnoBody {
  id_tipo_servicio_turno?: number
  fecha?: string
  hora_inicio?: string
  hora_fin?: string
  observaciones?: string | null
}

export interface ListarTurnosFiltros {
  estado?: EstadoTurno
  id_agente?: number
  id_ciudadano?: number
  fecha_desde?: string
  fecha_hasta?: string
}
