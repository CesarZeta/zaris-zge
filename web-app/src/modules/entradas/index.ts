import { Ticket } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { Overview } from './pages/Overview'

// Scaffold (2026-05-14). El modulo Entradas gestiona reservas a eventos que
// ocupan disponibilidad de espacios fisicos (ver §27 CLAUDE.md). Hoy solo
// landing minima; la logica (backoffice + autoservicio) se implementa en una
// sub-fase posterior. moduloCodigo='entradas' separado de 'agenda' en mig 44.
export const entradasModule: ModuleManifest = {
  id:    'entradas',
  label: 'entradas',
  icon:  Ticket,
  moduloCodigo: 'entradas',
  routes: [
    {
      index:   true,
      element: Overview,
      handle:  { breadcrumb: 'entradas' },
    },
  ],
}
