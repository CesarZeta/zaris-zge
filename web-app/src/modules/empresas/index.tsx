import { Building2 } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { EmpresasLayout } from './EmpresasLayout'
import { BuscarView } from './views/BuscarView'
import { FormView } from './views/FormView'
import { ListView } from './views/ListView'

const Wrap = (Component: React.FC) => () => (
  <EmpresasLayout>
    <Component />
  </EmpresasLayout>
)

export const empresasModule: ModuleManifest = {
  id: 'empresas',
  label: 'empresas',
  icon: Building2,
  moduloCodigo: 'padrones',
  hideFromSidebar: true,  // Se llega via la landing del modulo Contactos.
  routes: [
    { index: true,           element: Wrap(BuscarView), handle: { breadcrumb: 'empresas · buscar' } },
    { path: 'buscar',        element: Wrap(BuscarView), handle: { breadcrumb: 'empresas · buscar' } },
    { path: 'nuevo',         element: Wrap(FormView),   handle: { breadcrumb: 'empresas · nuevo' } },
    { path: ':id',           element: Wrap(FormView),   handle: { breadcrumb: 'empresas · detalle' } },
    { path: ':id/editar',    element: Wrap(FormView),   handle: { breadcrumb: 'empresas · editar' } },
    { path: 'listado',       element: Wrap(ListView),   handle: { breadcrumb: 'empresas · listado' } },
  ],
}
