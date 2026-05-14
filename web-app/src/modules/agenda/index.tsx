import { CalendarDays } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { AgendaLayout } from './AgendaLayout'
import { VistasView } from './views/VistasView'
import { EventListView } from './views/EventListView'
import { ConflictsView } from './views/ConflictsView'
import { ConfigView } from './views/ConfigView'

const WithLayout = (Component: React.FC) => () => (
  <AgendaLayout>
    <Component />
  </AgendaLayout>
)

export const agendaModule: ModuleManifest = {
  id:    'agenda',
  label: 'agenda',
  icon:  CalendarDays,
  moduloCodigo: 'turnos',
  routes: [
    { index: true,         element: WithLayout(VistasView),     handle: { breadcrumb: 'agenda · vistas' } },
    // Compat retro: links viejos /agenda/timeline y /agenda/mensual caen en la
    // misma VistasView (la sub-vista activa la decide el store).
    { path: 'timeline',    element: WithLayout(VistasView),     handle: { breadcrumb: 'agenda · vistas' } },
    { path: 'mensual',     element: WithLayout(VistasView),     handle: { breadcrumb: 'agenda · vistas' } },
    { path: 'eventos',     element: WithLayout(EventListView),  handle: { breadcrumb: 'agenda · eventos' } },
    { path: 'conflictos',  element: WithLayout(ConflictsView),  handle: { breadcrumb: 'agenda · conflictos' } },
    { path: 'config',      element: WithLayout(ConfigView),     handle: { breadcrumb: 'agenda · config' } },
  ],
}
