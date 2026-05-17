export type IniciadorTipo = 'ciudadano' | 'empresa' | 'area_interna'
export type DestinatarioTipo = 'subarea' | 'equipo'
export type EstadoFirma = 'no_requiere' | 'pendiente' | 'firmado' | 'rechazado'
export type RolIntervencion = 'firma' | 'visado' | 'notificacion'
export type TipoMovimiento =
  | 'creacion' | 'numeracion' | 'pase' | 'toma' | 'liberacion'
  | 'cambio_estado' | 'transicion' | 'adjunto'
  | 'firma_solicitada' | 'firma_realizada' | 'firma_rechazada'
  | 'comentario' | 'relacion' | 'desistido' | 'reapertura'

export type TipoDatoCampo =
  | 'texto' | 'texto_largo' | 'numero' | 'decimal' | 'fecha' | 'fecha_hora'
  | 'booleano' | 'seleccion' | 'seleccion_multiple' | 'direccion'
  | 'ciudadano' | 'empresa' | 'agente' | 'subarea' | 'equipo'
  | 'archivo' | 'moneda'

export interface TipoTramite {
  id_tipo_tramite: number
  codigo: string
  nombre: string
  descripcion: string | null
  prefijo: string
  iniciadores_permitidos: IniciadorTipo[]
  permite_representante: boolean
  icono: string | null
  color: string | null
  id_version_publicada: number | null
}

export interface TipoTramiteCampo {
  id_tipo_tramite_campo: number
  nombre_interno: string
  etiqueta: string
  tipo_dato: TipoDatoCampo
  obligatorio: boolean
  orden: number
  opciones_jsonb: Array<{ valor: string; etiqueta: string }> | null
  validacion_jsonb: Record<string, unknown> | null
  ayuda: string | null
  visible_en_listado: boolean
}

export interface TipoTramiteEstado {
  id_tipo_tramite_estado: number
  codigo: string
  etiqueta: string
  color: string | null
  orden: number
  es_inicial: boolean
  es_final: boolean
  permite_adjuntar: boolean
  permite_comentar: boolean
}

export interface TipoTramiteTransicion {
  id_tipo_tramite_transicion: number
  id_estado_origen: number
  id_estado_destino: number
  etiqueta_accion: string
  orden: number
  requiere_comentario: boolean
  requiere_adjunto: boolean
  quien_puede_jsonb: {
    subareas?: number[]
    equipos?: number[]
    roles?: string[]
    iniciador?: boolean
  }
  destino_automatico_jsonb: { tipo: DestinatarioTipo; id: number } | null
}

export interface TipoTramiteDocRequerido {
  id_tipo_tramite_documento_requerido: number
  nombre: string
  descripcion: string | null
  obligatorio: boolean
  formatos_permitidos: string[]
  tamano_max_mb: number
  requiere_firma: boolean
  quien_debe_adjuntar: string
}

export interface TipoTramiteDetalle extends TipoTramite {
  version: {
    id_tipo_tramite_version: number
    version_num: number
    campos: TipoTramiteCampo[]
    estados: TipoTramiteEstado[]
    transiciones: TipoTramiteTransicion[]
    documentos_requeridos: TipoTramiteDocRequerido[]
  }
}

export interface TramiteBandejaItem {
  id_tramite: number
  numero_expediente: string
  asunto: string
  tipo_codigo: string
  tipo_nombre: string
  estado_codigo: string
  estado_etiqueta: string
  estado_color: string | null
  iniciador_tipo: IniciadorTipo
  iniciador_nombre: string
  destinatario_actual_tipo: DestinatarioTipo | null
  destinatario_actual_nombre: string | null
  tomado_por_nombre: string | null
  tomado_en: string | null
  fecha_alta: string
  dias_en_estado_actual: number
}

export interface TramiteDetalle {
  id_tramite: number
  numero_expediente: string
  asunto: string
  datos_jsonb: Record<string, unknown>
  iniciador_tipo: IniciadorTipo
  iniciador_nombre: string | null
  representante_nombre: string | null
  tipo_codigo: string
  tipo_nombre: string
  tipo_prefijo: string
  id_tipo_tramite_version: number
  version_num: number
  estado_codigo: string
  estado_etiqueta: string
  estado_color: string | null
  fecha_entrada_estado_actual: string
  destinatario_actual_tipo: string | null
  destinatario_actual_nombre: string | null
  tomado_por_nombre: string | null
  tomado_en: string | null
  ultimo_movimiento_tipo: string | null
  ultimo_movimiento_comentario: string | null
  ultimo_movimiento_fecha: string | null
  cant_documentos: number
  cant_firmas_pendientes: number
  relaciones: TramiteRelacion[]
  fecha_alta: string
  id_municipio: number
}

export interface TramiteMovimiento {
  id_tramite_movimiento: number
  orden_secuencial: number
  tipo: TipoMovimiento
  comentario: string | null
  origen_jsonb: { tipo: string; id: number; nombre: string } | null
  destino_jsonb: { tipo: string; id: number; nombre: string } | null
  metadata_jsonb: Record<string, unknown> | null
  id_estado_origen: number | null
  id_estado_destino: number | null
  estado_origen_etiqueta: string | null
  estado_destino_etiqueta: string | null
  agente_nombre: string
  ip: string | null
  fecha_alta: string
}

export interface TramiteDocumento {
  id_tramite_documento: number
  nombre: string
  nombre_archivo_original: string
  mime_type: string
  tamano_bytes: number
  hash_sha256: string
  requiere_firma: boolean
  estado_firma: EstadoFirma
  posicion_orden: number
  agente_subio_nombre: string
  fecha_alta: string
  firmas: TramiteFirma[]
}

export interface TramiteFirma {
  id_tramite_firma: number
  rol_intervencion: RolIntervencion
  orden: number
  asignado_a: { tipo: 'agente' | 'subarea' | 'equipo'; id: number; nombre: string }
  estado: 'pendiente' | 'firmado' | 'rechazado'
  firmante_nombre: string | null
  firmado_en: string | null
  ip_firma: string | null
  hash_documento_firmado: string | null
  motivo_rechazo: string | null
  rechazado_en: string | null
}

export interface TransicionPermitida extends TipoTramiteTransicion {
  etiqueta_destino: string
  disponible: boolean
  motivo_no_disponible: string | null
}

export interface TramiteRelacion {
  id_tramite_relacion: number
  id_tramite_relacionado: number
  numero_expediente_relacionado: string
  tipo_relacion: 'asociacion_simple' | 'conjunta' | 'fusion'
  comentario: string | null
  fecha_alta: string
}

export interface TransicionesPermitidas {
  estado_actual: TipoTramiteEstado
  tomado_por_mi: boolean
  puedo_operar: boolean
  transiciones: TransicionPermitida[]
}

export interface CrearTramiteBody {
  id_tipo_tramite: number
  id_tipo_tramite_version: number
  asunto: string
  iniciador_tipo: IniciadorTipo
  id_ciudadano_iniciador?: number | null
  id_empresa_iniciadora?: number | null
  id_subarea_iniciadora?: number | null
  id_ciudadano_representante?: number | null
  datos_jsonb: Record<string, unknown>
}

export interface BandejaParams {
  estado_codigo?: string
  id_tipo_tramite?: number
  iniciador_tipo?: string
  iniciador_id?: number
  destinatario_tipo?: DestinatarioTipo
  destinatario_id?: number
  numero?: string
  q?: string
  desde?: string
  hasta?: string
  solo_activos?: boolean
  mis_tramites?: boolean
  mi_subarea?: boolean
  mi_equipo?: boolean
  limit?: number
  offset?: number
}
