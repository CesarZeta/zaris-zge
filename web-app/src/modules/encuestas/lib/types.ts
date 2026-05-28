// Tipos del modulo Encuestas (CSAT). Espejan los schemas Out del backend
// (backend/app/schemas/encuestas.py). NO inventar campos: cada uno existe en
// la respuesta real del endpoint correspondiente. Ver CLAUDE.md §42.

export interface DashboardPeriodo {
  desde: string // ISO date 'YYYY-MM-DD'
  hasta: string
}

export interface DashboardDistribucionItem {
  clasificacion: number // 1..5
  count: number
}

export interface DashboardResumen {
  periodo: DashboardPeriodo
  csat_promedio: number
  tasa_respuesta_pct: number
  pct_insatisfechos: number
  alertas_contacto_pendientes: number
  total_enviadas: number
  total_completadas: number
  distribucion: DashboardDistribucionItem[]
}

export interface DashboardPorAreaItem {
  id_area: number | null
  nombre_area: string | null
  total_respuestas: number
  csat_promedio: number
}

export interface DashboardEvolucionItem {
  anio_mes: string // 'YYYY-MM'
  csat_promedio: number
  total_respuestas: number
}

export interface DashboardComentarioItem {
  id_envio: number
  fecha_respuesta: string | null
  clasificacion_inicial: number
  comentario: string
}

export interface RespuestaPendienteContacto {
  id_encuesta_respuesta: number
  id_encuesta_envio: number
  clasificacion_inicial: number
  rama_seguida: string
  fecha_respuesta: string | null
  atendida: boolean
  // origen polimorfico (mig 72): reclamo XOR turno
  id_reclamo: number | null
  nro_reclamo: string | null
  id_turno: number | null
  tipo: string | null            // reclamos | turnos
  referencia: string | null      // nro_reclamo o nombre de prestacion del turno
  id_ciudadano: number
  ciudadano_nombre: string | null
  ciudadano_apellido: string | null
  ciudadano_email: string | null
  ciudadano_telefono: string | null
}

export type EstadoEnvio =
  | 'pendiente'
  | 'enviada'
  | 'abierta'
  | 'completada'
  | 'expirada'
  | string

export interface EncuestaEnvio {
  id_encuesta_envio: number
  id_plantilla: number
  id_ciudadano: number
  // origen polimorfico (mig 72): reclamo XOR turno
  id_reclamo: number | null
  id_turno: number | null
  email_destino_snapshot: string
  fecha_expiracion: string
  token_unico: string
  fecha_envio: string | null
  fecha_apertura: string | null
  fecha_completada: string | null
  estado: EstadoEnvio
  intentos_envio: number
  ultimo_error_envio: string | null
  activo: boolean
  fecha_alta: string
  fecha_modificacion: string
  // derivados del backend (LEFT JOIN)
  tipo: string | null            // reclamos | turnos | tramites
  referencia: string | null      // nro_reclamo o nombre de prestacion
  nro_reclamo: string | null
}

export interface EncuestaRespuesta {
  id_encuesta_respuesta: number
  id_envio: number
  clasificacion_inicial: number
  rama_seguida: string
  tiempo_completado_seg: number | null
  solicita_contacto: boolean
  ip_origen: string | null
  atendida: boolean
  atendida_por: number | null
  fecha_atendida: string | null
  activo: boolean
  fecha_alta: string
  fecha_modificacion: string
}

export interface EncuestaRespuestaDetalle {
  id_encuesta_respuesta_detalle: number
  id_respuesta: number
  id_pregunta: number
  valor_numerico: number | null
  valor_texto: string | null
  id_opcion_seleccionada: number | null
  activo: boolean
}

export interface EncuestaEnvioConRespuesta extends EncuestaEnvio {
  respuesta: EncuestaRespuesta | null
  detalles_respuesta: EncuestaRespuestaDetalle[]
}

// --- Plantillas (catálogo de encuestas) ---

export interface EncuestaPlantilla {
  id_encuesta_plantilla: number
  nombre: string
  descripcion: string | null
  version: string
  tipo: string // reclamos | turnos | tramites
  activo: boolean
  id_municipio: number | null
  id_subarea: number | null
  fecha_alta: string
  fecha_modificacion: string
}

export interface EncuestaOpcion {
  id_encuesta_opcion: number
  id_pregunta: number
  texto: string
  valor: string
  orden: number
  activo: boolean
}

export interface EncuestaPregunta {
  id_encuesta_pregunta: number
  id_plantilla: number
  texto: string
  tipo: string // likert5 | texto_libre | si_no | multiple
  orden: number
  rama: string // todos | satisfechos | neutrales | insatisfechos
  obligatoria: boolean
  activo: boolean
  opciones: EncuestaOpcion[]
}

export interface EncuestaPlantillaDetalle extends EncuestaPlantilla {
  preguntas: EncuestaPregunta[]
}
