import { Ticket } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { Overview } from './pages/Overview'

// Modulo Entradas: gestion backoffice de eventos con cupo en espacios fisicos.
// Reusa la entidad `eventos` del backend de Agenda (filtro con_espacio=true) y
// el ReservaModal de Agenda para gestionar las reservas de entradas. Backend:
// /agenda/eventos + /agenda/eventos/{id}/reservas (sin migracion nueva).
// moduloCodigo='entradas' (mig 44). Pendiente: vista autoservicio (sub-fase A1).
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
