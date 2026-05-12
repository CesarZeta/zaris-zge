import { CalendarDays } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { AgendaLayout } from './AgendaLayout'
import { TimelineView } from './views/TimelineView'
import { MonthlyView } from './views/MonthlyView'
import { EventListView } from './views/EventListView'
import { ConflictsView } from './views/ConflictsView'

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
    { index: true,         element: WithLayout(TimelineView),   handle: { breadcrumb: 'agenda · timeline' } },
    { path: 'timeline',    element: WithLayout(TimelineView),   handle: { breadcrumb: 'agenda · timeline' } },
    { path: 'mensual',     element: WithLayout(MonthlyView),    handle: { breadcrumb: 'agenda · mensual' } },
    { path: 'eventos',     element: WithLayout(EventListView),  handle: { breadcrumb: 'agenda · eventos' } },
    { path: 'conflictos',  element: WithLayout(ConflictsView),  handle: { breadcrumb: 'agenda · conflictos' } },
  ],
}
