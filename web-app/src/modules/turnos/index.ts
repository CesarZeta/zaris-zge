import { Clock } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { Overview } from './pages/Overview'

// Modulo Turnos: gestion backoffice de turnos de atencion. Un turno reserva un
// bloque de la disponibilidad de un agente para un tramite (tipo de servicio).
// Estados: reservado -> cumplido | cancelado. Cada turno mantiene una fila
// espejo en `ocupaciones` (tipo='turno') para aparecer en la grilla de Agenda.
// Backend: mig 45 + routes/turnos.py. moduloCodigo='turnos' (mig 44).
// Pendiente: vista autoservicio publica (sub-fase A1).
export const turnosModule: ModuleManifest = {
  id:    'turnos',
  label: 'turnos',
  icon:  Clock,
  moduloCodigo: 'turnos',
  routes: [
    {
      index:   true,
      element: Overview,
      handle:  { breadcrumb: 'turnos' },
    },
  ],
}
