import { FileText } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { TramitesLayout } from './TramitesLayout'
import { BandejaTramites } from './pages/BandejaTramites'
import { CrearTramite } from './pages/CrearTramite'
import { DetalleTramite } from './pages/DetalleTramite'

const Wrap = (Component: React.FC) => () => (
  <TramitesLayout>
    <Component />
  </TramitesLayout>
)

export const tramitesModule: ModuleManifest = {
  id: 'tramites',
  label: 'trámites',
  icon: FileText,
  moduloCodigo: 'tramites',
  routes: [
    { index: true,       element: Wrap(BandejaTramites), handle: { breadcrumb: 'trámites · bandeja' } },
    { path: 'nuevo',     element: Wrap(CrearTramite),    handle: { breadcrumb: 'trámites · nuevo' } },
    { path: ':numero',   element: Wrap(DetalleTramite),  handle: { breadcrumb: 'trámites · detalle' } },
  ],
}
