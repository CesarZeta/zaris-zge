import { Clock } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { Overview } from './pages/Overview'

// Scaffold (2026-05-14). El modulo Turnos gestiona ocupaciones tipo 'turno'
// sobre la disponibilidad de agentes (ver §27 CLAUDE.md). Hoy solo landing
// minima; la logica (backoffice + autoservicio) se implementa en una sub-fase
// posterior. moduloCodigo='turnos' separado de 'agenda' en migracion 44.
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
