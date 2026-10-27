import { Landmark } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { AltaMunicipioPage } from './pages/AltaMunicipioPage'
import { MunicipioFichaPage } from './pages/MunicipioFichaPage'
import { MunicipiosPage } from './pages/MunicipiosPage'
import { SuperAdministradoresPage } from './pages/SuperAdministradoresPage'

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
    { path: 'alta', element: AltaMunicipioPage, handle: { breadcrumb: 'municipios · alta' } },
    { path: 'super-administradores', element: SuperAdministradoresPage, handle: { breadcrumb: 'municipios · super administradores' } },
    { path: ':id', element: MunicipioFichaPage, handle: { breadcrumb: 'municipios · ficha' } },
  ],
}
