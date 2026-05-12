import { Users } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { CiudadanosLayout } from './CiudadanosLayout'
import { BuscarView } from './views/BuscarView'
import { FormView } from './views/FormView'
import { ListView } from './views/ListView'

const Wrap = (Component: React.FC) => () => (
  <CiudadanosLayout>
    <Component />
  </CiudadanosLayout>
)

export const ciudadanosModule: ModuleManifest = {
  id: 'ciudadanos',
  label: 'ciudadanos',
  icon: Users,
  moduloCodigo: 'padrones',
  routes: [
    { index: true,           element: Wrap(BuscarView), handle: { breadcrumb: 'ciudadanos · buscar' } },
    { path: 'buscar',        element: Wrap(BuscarView), handle: { breadcrumb: 'ciudadanos · buscar' } },
    { path: 'nuevo',         element: Wrap(FormView),   handle: { breadcrumb: 'ciudadanos · nuevo' } },
    { path: ':id',           element: Wrap(FormView),   handle: { breadcrumb: 'ciudadanos · detalle' } },
    { path: ':id/editar',    element: Wrap(FormView),   handle: { breadcrumb: 'ciudadanos · editar' } },
    { path: 'listado',       element: Wrap(ListView),   handle: { breadcrumb: 'ciudadanos · listado' } },
  ],
}
