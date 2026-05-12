import { FileText } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { ReclamosLayout } from './ReclamosLayout'
import { ListView } from './views/ListView'
import { DetailView } from './views/DetailView'
import { FormView } from './views/FormView'

const Wrap = (Component: React.FC) => () => (
  <ReclamosLayout>
    <Component />
  </ReclamosLayout>
)

export const reclamosModule: ModuleManifest = {
  id: 'reclamos',
  label: 'reclamos',
  icon: FileText,
  moduloCodigo: 'reclamos',
  routes: [
    { index: true,             element: Wrap(ListView),   handle: { breadcrumb: 'reclamos · listado' } },
    { path: 'nuevo',           element: Wrap(FormView),   handle: { breadcrumb: 'reclamos · nuevo' } },
    { path: ':id',             element: Wrap(DetailView), handle: { breadcrumb: 'reclamos · detalle' } },
    { path: ':id/editar',      element: Wrap(FormView),   handle: { breadcrumb: 'reclamos · editar' } },
  ],
}
