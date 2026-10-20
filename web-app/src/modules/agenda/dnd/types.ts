// Tipos compartidos por el sistema de drag & drop de Agenda.
import type { Ocupacion, TipoRecurso } from '../types/agenda'

// Hasta 2026-10-21 también se arrastraban OTs pendientes desde un panel lateral
// ('pending-ot'); las OT ya no se agendan.
export type DragPayload = { kind: 'occupation'; ocupacion: Ocupacion }

export interface DropPayload {
  kind: 'row'
  tipo_recurso: TipoRecurso
  id_recurso: number
  // Offset X relativo al inicio de la fila (0 = HOUR_START * pxPerHour)
  // Lo poblamos en onDragEnd a partir de event.delta y la posicion absoluta.
}
