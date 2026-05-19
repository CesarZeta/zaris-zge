import { BookOpen } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { GuiasLayout } from './GuiasLayout'
import { GuiasIndex } from './pages/GuiasIndex'

const Wrap = (Component: React.FC) => () => (
  <GuiasLayout>
    <Component />
  </GuiasLayout>
)

// Sin moduloCodigo → visible para cualquier usuario autenticado.
// Las guías son material informativo, no acceden a datos protegidos.
export const guiasModule: ModuleManifest = {
  id: 'guias',
  label: 'guías',
  icon: BookOpen,
  routes: [
    { index: true, element: Wrap(GuiasIndex), handle: { breadcrumb: 'guías' } },
  ],
}
