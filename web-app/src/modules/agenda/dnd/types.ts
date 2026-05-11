// Tipos compartidos por el sistema de drag & drop de Agenda.
import type { Ocupacion, TipoRecurso } from '../types/agenda'

export interface OTPendiente {
  id_ot: number
  nro_ot: string | null
  reclamo_descripcion: string | null
  reclamo_prioridad: string | null
  sla_dias: number | null
  estado_nombre: string | null
  id_agente: number | null
  id_equipo: number | null
  agente_apellido?: string | null
  agente_nombre?: string | null
  equipo_nombre?: string | null
  // Si el tipo_reclamo dice como bloquear agenda:
  tipo_audit?: boolean | null
}

export type DragPayload =
  | { kind: 'occupation'; ocupacion: Ocupacion }
  | { kind: 'pending-ot'; ot: OTPendiente }

export interface DropPayload {
  kind: 'row'
  tipo_recurso: TipoRecurso
  id_recurso: number
  // Offset X relativo al inicio de la fila (0 = HOUR_START * pxPerHour)
  // Lo poblamos en onDragEnd a partir de event.delta y la posicion absoluta.
}
