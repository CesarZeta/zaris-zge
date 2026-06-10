// Tipos del modulo Emergencias (COM). Espejan los Out del router
// backend/app/api/routes/emergencias.py (Fases 2 y 3).

export interface EmergenciaTipo {
  id_emergencia_tipo: number
  id_subarea: number
  subarea_nombre?: string | null
  codigo_oficial?: number | null
  codigo: string
  nombre: string
  id_prioridad_default: number
  prioridad_codigo?: string | null
  id_organismo_derivacion_default?: number | null
  organismo_default_codigo?: string | null
  requiere_911: boolean
  es_emergencia: boolean
  activo: boolean
}

export interface EmergenciaSubtipo {
  id_emergencia_subtipo: number
  id_tipo: number
  codigo: string
  nombre: string
  id_prioridad_override?: number | null
  prioridad_override_codigo?: string | null
  activo: boolean
}

export interface EmergenciaPrioridad {
  id_emergencia_prioridad: number
  codigo: string
  nombre: string
  sla_minutos_arribo: number
  color_token: string
  orden_visual: number
  activo: boolean
}

export interface EmergenciaEstado {
  id_emergencia_estado: number
  codigo: string
  nombre: string
  es_inicial: boolean
  es_terminal: boolean
  es_terminal_positivo: boolean
  orden_visual: number
  activo: boolean
}

export interface EmergenciaOrganismo {
  id_emergencia_organismo_derivacion: number
  codigo: string
  nombre: string
  telefono_contacto?: string | null
  es_municipal: boolean
  activo: boolean
}

export interface EmergenciaCanal {
  id_emergencia_canal_ingreso: number
  codigo: string
  nombre: string
  requiere_operador: boolean
  activo: boolean
}

export interface ContactoEventual {
  id_emergencia_contacto_eventual: number
  dni: string
  nombre_apellido: string
  telefono: string
  direccion: string
  contacto_alt_nombre?: string | null
  contacto_alt_telefono?: string | null
  convertido_a_buc: boolean
  id_ciudadano_buc_destino?: number | null
  observaciones?: string | null
  activo: boolean
}

export interface CiudadanoBucMatch {
  id_ciudadano: number
  apellido: string
  nombre: string
  doc_nro: string
  cuil?: string | null
  telefono?: string | null
  email?: string | null
  calle?: string | null
  altura?: string | null
  localidad?: string | null
}

export type DenuncianteBusqueda =
  | { origen: 'BUC'; matches: CiudadanoBucMatch[] }
  | { origen: 'EVENTUAL'; matches: ContactoEventual[] }
  | { origen: 'NUEVO'; criterio: 'dni' | 'telefono' | 'nombre'; valor: string }

export interface EmergenciaEvento {
  id_emergencia_evento: number
  numero_operativo: string
  id_subarea: number
  subarea_nombre: string
  id_tipo: number
  tipo_codigo: string
  tipo_nombre: string
  id_subtipo?: number | null
  subtipo_codigo?: string | null
  subtipo_nombre?: string | null
  id_prioridad: number
  prioridad_codigo: string
  prioridad_color_token: string
  sla_minutos_arribo: number
  id_estado: number
  estado_codigo: string
  estado_nombre: string
  es_terminal: boolean
  es_terminal_positivo: boolean
  id_canal_ingreso: number
  canal_codigo: string
  id_organismo_derivacion?: number | null
  organismo_codigo?: string | null
  organismo_nombre?: string | null
  id_operador_receptor?: number | null
  denunciante_anonimo: boolean
  id_ciudadano_buc?: number | null
  id_contacto_eventual?: number | null
  denunciante_nombre?: string | null
  direccion_evento: string
  latitud?: number | null
  longitud?: number | null
  referencia_ubicacion?: string | null
  audio_grabacion_url?: string | null
  observaciones_recepcion?: string | null
  observaciones_cierre?: string | null
  veracidad?: 'CONFIRMADA' | 'FALSA_ALARMA' | 'NO_VERIFICABLE' | null
  fecha_hora_recepcion: string
  fecha_hora_despacho?: string | null
  fecha_hora_arribo?: string | null
  fecha_hora_cierre?: string | null
  activo: boolean
}

export interface EmergenciaEventoDetalle extends EmergenciaEvento {
  denunciante?: CiudadanoBucMatch | ContactoEventual | null
}

export interface EmergenciaLogEntry {
  id_emergencia_log: number
  id_evento: number
  id_usuario?: number | null
  usuario_nombre?: string | null
  fecha_hora: string
  tipo_accion: string
  estado_anterior?: string | null
  estado_nuevo?: string | null
  payload_json?: Record<string, unknown> | null
  observaciones?: string | null
}

export interface EventoCreateBody {
  id_subarea: number
  id_tipo: number
  id_subtipo?: number | null
  id_prioridad?: number | null
  id_canal_ingreso: number
  denunciante_anonimo: boolean
  id_ciudadano_buc?: number | null
  id_contacto_eventual?: number | null
  direccion_evento: string
  latitud?: number | null
  longitud?: number | null
  referencia_ubicacion?: string | null
  observaciones_recepcion?: string | null
}

export interface ContactoEventualCreateBody {
  dni: string
  nombre_apellido: string
  telefono: string
  direccion: string
  contacto_alt_nombre?: string | null
  contacto_alt_telefono?: string | null
}

export interface ListarEventosFiltros {
  estado?: string
  id_subarea?: number
  id_prioridad?: number
  q?: string
  fecha_desde?: string
  fecha_hasta?: string
  limit?: number
  offset?: number
}
