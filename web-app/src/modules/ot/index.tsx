import { ClipboardList } from 'lucide-react'
import { Navigate } from 'react-router-dom'
import type { ModuleManifest } from '../../lib/types'
import { OTLayout } from './OTLayout'
import { SupervisorView } from './views/SupervisorView'
import { AgenteView } from './views/AgenteView'
import { AuditoriaView } from './views/AuditoriaView'

const Wrap = (Component: React.FC) => () => (
  <OTLayout>
    <Component />
  </OTLayout>
)

// /ot sin sub-ruta → redirige a supervisor (default).
const RedirectSupervisor = () => <Navigate to="/ot/supervisor" replace />

export const otModule: ModuleManifest = {
  id: 'ot',
  label: 'OT',
  icon: ClipboardList,
  // NO seteamos moduloCodigo a nivel manifest porque las 3 mesas tienen
  // moduloCodigo distinto (ot_supervisor / ot_agente / ot_auditoria).
  // El filtrado de permisos se hace por link en el sidebar vanilla
  // (data-modulo) y a nivel endpoint backend cuando corresponda.
  routes: [
    { index: true,           element: RedirectSupervisor, handle: { breadcrumb: 'OT' } },
    { path: 'supervisor',    element: Wrap(SupervisorView), handle: { breadcrumb: 'OT · Supervisor' } },
    { path: 'agente',        element: Wrap(AgenteView),     handle: { breadcrumb: 'OT · Agente' } },
    { path: 'auditoria',     element: Wrap(AuditoriaView),  handle: { breadcrumb: 'OT · Auditoría' } },
  ],
}
