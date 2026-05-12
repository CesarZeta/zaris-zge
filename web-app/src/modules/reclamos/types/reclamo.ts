// Tipos del modulo Reclamos. Mirror del response shape de backend/app/api/routes/reclamos.py.
// Los SELECT del backend usan SQL crudo + _to_dict, no hay schema Pydantic estricto.

export type EstadoReclamo =
  | 'Sin asignar'
  | 'En gestión'
  | 'En espera'
  | 'En auditoría'
  | 'Resuelto'
  | 'Cancelado'

export type Prioridad = 'Baja' | 'Media' | 'Alta' | 'Crítica'

export interface AreaCatalogo {
  id_area: number
  nombre: string
}

export interface TipoCatalogo {
  id_tipo_reclamo: number
  nombre: string
  sla_dias: number | null
  audit: boolean
  id_area: number | null
  area_nombre: string | null
  id_subarea: number | null
  subarea_nombre: string | null
}

// Fila del listado /reclamos (GET "")
export interface ReclamoListado {
  id_reclamo: number
  nro_reclamo: string | null
  prioridad: Prioridad | null
  estado: EstadoReclamo
  descripcion: string
  domicilio_reclamo: string | null
  observaciones: string | null
  fecha_alta: string
  fecha_modificacion: string | null
  id_reclamo_padre: number | null
  id_ciudadano: number
  ciudadano_nombre: string | null
  ciudadano_apellido: string | null
  doc_nro: string | null
  id_tipo_reclamo: number | null
  tipo_nombre: string | null
  sla_dias: number | null
  tipo_audit: boolean | null
  id_area: number | null
  area_nombre: string | null
  id_agente_asignado: number | null
  agente_nombre: string | null
}

// Historial de cambios de estado
export interface HistorialItem {
  id_historial: number
  accion: string
  estado_anterior: string | null
  estado_nuevo: string | null
  nota: string | null
  fecha_alta: string
  usuario_nombre: string | null
}

// OT asociada
export interface OTAsociada {
  id_ot: number
  nro_ot: string | null
  es_auditoria: boolean
  resultado_auditoria: string | null
  fecha_creacion: string
  fecha_cierre: string | null
  observaciones: string | null
  estado_nombre: string
  estado_color: string | null
  agente_nombre: string | null
  agente_apellido: string | null
  equipo_nombre: string | null
}

// Subreclamo (hijo)
export interface Subreclamo {
  id_reclamo: number
  nro_reclamo: string | null
  estado: EstadoReclamo
  descripcion: string
  fecha_alta: string
}

// Reclamo full (GET /reclamos/{id})
export interface ReclamoDetalle extends ReclamoListado {
  direccion: string | null
  fecha_primer_asignacion: string | null
  fecha_cierre: string | null
  sla_vencimiento: string | null
  canal_origen: string | null
  fuente_geolocalizacion: string | null
  latitud: number | null
  longitud: number | null
  id_localidad: number | null
  localidad_nombre: string | null
  id_partido: number | null
  partido_nombre: string | null
  id_provincia: number | null
  provincia_nombre: string | null
  id_activo: number | null
  activo_codigo: string | null
  id_tipo_activo: number | null
  activo_tipo_nombre: string | null
  id_empresa: number | null
  empresa_nombre: string | null
  empresa_cuit: string | null
  cuil: string | null
  telefono: string | null
  ciudadano_email: string | null
  historial: HistorialItem[]
  ordenes_trabajo: OTAsociada[]
  subreclamos: Subreclamo[]
}

// Adjunto del reclamo (GET /reclamos/{id}/adjuntos)
export interface Adjunto {
  id_adjunto: number
  storage_path: string
  nombre_archivo: string
  mime_type: string
  tamano_bytes: number
  fecha_alta: string
  url: string  // URL firmada GET con TTL 1h
}

export interface StatsReclamos {
  [estado: string]: number
}

// Canal de origen del reclamo
export type CanalOrigen = 'web' | 'whatsapp' | 'telefono' | 'presencial' | 'oficio' | 'app_movil' | 'otro'

// Payload para POST /reclamos (alta)
export interface ReclamoCreate {
  id_ciudadano: number
  descripcion: string
  id_tipo_reclamo?: number | null
  id_area?: number | null
  prioridad?: Prioridad
  direccion?: string | null
  observaciones?: string | null
  latitud?: number | null
  longitud?: number | null
  id_localidad?: number | null
  id_activo?: number | null
  id_empresa?: number | null
  canal_origen?: CanalOrigen | null
  fuente_geolocalizacion?: string | null
}

// Respuesta POST /reclamos
export interface ReclamoCreateResponse {
  id_reclamo: number
  nro_reclamo: string | null
  estado: EstadoReclamo
}

// Payload para PUT /reclamos/{id} (allowlist segun estado backend)
export interface ReclamoUpdate {
  id_ciudadano?: number
  id_tipo_reclamo?: number | null
  descripcion?: string
  direccion?: string | null
  prioridad?: Prioridad
  latitud?: number | null
  longitud?: number | null
  id_localidad?: number | null
  id_activo?: number | null
  id_empresa?: number | null
  canal_origen?: CanalOrigen | null
  fuente_geolocalizacion?: string | null
  observaciones?: string | null
  nota_historial?: string | null
}
