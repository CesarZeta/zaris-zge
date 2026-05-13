import { Contact } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { Overview } from './pages/Overview'

export const contactosModule: ModuleManifest = {
  id:    'contactos',
  label: 'contactos',
  icon:  Contact,
  moduloCodigo: 'padrones',
  routes: [
    {
      index:   true,
      element: Overview,
      handle:  { breadcrumb: 'contactos' },
    },
  ],
}
