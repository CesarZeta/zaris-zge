// Mirror de los responses de backend/app/api/routes/ordenes_trabajo.py.
// Los campos se exponen tal cual los devuelve el SQL (ISO strings, ya pasados por _to_dict).

export type PrioridadReclamo = 'Alta' | 'Media' | 'Baja'

export type EstadoReclamoOT =
  | 'Sin asignar'
  | 'En gestión'
  | 'En espera'
  | 'En auditoría'
  | 'Resuelto'
  | 'Cancelado'

export type EstadoOT =
  | 'En gestión'
  | 'En espera'
  | 'Pendiente'
  | 'Terminada'
  | 'Cancelada'

export interface CatalogoEstadoOT {
  id_estado_ot: number
  nombre: EstadoOT
  color: string | null
  es_final: boolean
}

// GET /ot/mesa/supervisor — un row por reclamo (con la OT activa embebida si existe)
export interface MesaSupervisorRow {
  id_reclamo: number
  nro_reclamo: string | null
  estado: EstadoReclamoOT
  prioridad: PrioridadReclamo | null
  descripcion: string | null
  domicilio_reclamo: string | null
  fecha_alta: string
  sla_vencimiento: string | null
  id_reclamo_padre: number | null
  ciudadano_nombre: string | null
  ciudadano_apellido: string | null
  doc_nro: string | null
  tipo_nombre: string | null
  sla_dias: number | null
  tipo_audit: boolean | null
  area_nombre: string | null
  id_subarea: number | null
  subarea_nombre: string | null
  cant_ots: number
  ot_activa_id: number | null
  ot_activa_nro: string | null
  ot_activa_estado: EstadoOT | null
  ot_id_agente: number | null
  ot_agente_nombre: string | null
  ot_id_equipo: number | null
  ot_equipo_nombre: string | null
}

// GET /ot/agente/me → { id_agente, ots: MesaAgenteRow[] }
export interface MesaAgenteResponse {
  id_agente: number
  ots: MesaAgenteRow[]
}

export interface MesaAgenteRow {
  id_ot: number
  nro_ot: string | null
  es_auditoria: boolean
  fecha_creacion: string
  observaciones: string | null
  estado_nombre: EstadoOT
  estado_color: string | null
  id_reclamo: number
  nro_reclamo: string | null
  reclamo_estado: EstadoReclamoOT
  reclamo_prioridad: PrioridadReclamo | null
  reclamo_descripcion: string | null
  reclamo_fecha_alta: string
  sla_vencimiento: string | null
  reclamo_direccion: string | null
  tipo_nombre: string | null
  sla_dias: number | null
  tipo_audit: boolean | null
  id_subarea: number | null
  subarea_nombre: string | null
  id_equipo: number | null
  equipo_nombre: string | null
  id_agente: number | null
  scope: 'mia' | 'disponible_equipo' | 'otro'
  ciudadano_nombre: string | null
  ciudadano_apellido: string | null
}

// GET /ot/auditor/me → { id_agente, ots: MesaAuditoriaRow[] }
export interface MesaAuditoriaResponse {
  id_agente: number
  ots: MesaAuditoriaRow[]
}

export interface MesaAuditoriaRow {
  id_ot: number
  nro_ot: string | null
  fecha_creacion: string
  observaciones: string | null
  estado_nombre: EstadoOT
  estado_color: string | null
  id_reclamo: number
  nro_reclamo: string | null
  reclamo_prioridad: PrioridadReclamo | null
  reclamo_descripcion: string | null
  id_subarea: number | null
  subarea_nombre: string | null
  sla_vencimiento: string | null
  tipo_nombre: string | null
  sla_dias: number | null
  id_agente: number | null
  agente_nombre: string | null
  agente_apellido: string | null
  ciudadano_nombre: string | null
  ciudadano_apellido: string | null
  id_ot_origen: number | null
  ot_origen_nro: string | null
  ot_origen_obs: string | null
  ot_origen_agente_apellido: string | null
  ot_origen_agente_nombre: string | null
}

// Catálogos para selects de asignación/reasignación.
export interface AgenteLite {
  id_agente: number
  nombre: string | null
  apellido: string | null
  legajo: string | null
  activo: boolean
}

export interface EquipoLite {
  id_equipo: number
  nombre: string | null
  activo: boolean
}

// POST /ot — supervisor crea OT
export interface CrearOTBody {
  id_reclamo: number
  id_agente?: number | null
  id_equipo?: number | null
  observaciones?: string
}

// PUT /ot/{id}/reasignar
export interface ReasignarOTBody {
  id_agente?: number | null
  id_equipo?: number | null
  nota: string
}

// PUT /ot/{id}/estado
export interface CambiarEstadoOTBody {
  estado: EstadoOT
  observaciones?: string
}
