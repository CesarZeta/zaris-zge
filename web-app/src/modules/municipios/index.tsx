import { Landmark } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { MunicipiosPage } from './pages/MunicipiosPage'

// «Municipios» — exclusivo del super administrador (IT-01 F3). `moduloCodigo` = fila de
// `modulos` con min_nivel_acceso 0 (mig 127b): solo la ve el nivel 0. Los endpoints
// (/api/v1/super/*) tienen además su propio guard.
export const municipiosModule: ModuleManifest = {
  id: 'municipios',
  label: 'municipios',
  icon: Landmark,
  moduloCodigo: 'municipios',
  routes: [
    { index: true, element: MunicipiosPage, handle: { breadcrumb: 'municipios' } },
  ],
}
