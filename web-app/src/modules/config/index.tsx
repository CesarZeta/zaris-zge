import { Settings } from 'lucide-react'
import { Navigate } from 'react-router-dom'
import type { ModuleManifest } from '../../lib/types'
import { ConfigLayout } from './ConfigLayout'
import { UsuariosPermisosView } from './views/UsuariosPermisosView'
import { CatalogoModulosView } from './views/CatalogoModulosView'
import { SistemaView } from './views/SistemaView'

const Wrap = (Component: React.FC) => () => (
  <ConfigLayout>
    <Component />
  </ConfigLayout>
)

const RedirectPermisos = () => <Navigate to="/config/permisos" replace />

export const configModule: ModuleManifest = {
  id: 'config',
  label: 'configuración',
  icon: Settings,
  // moduloCodigo='usuarios' como aproximacion: si tenes acceso a 'usuarios',
  // tenes acceso a configuracion. Backend `require_admin` exige nivel=1 igual.
  moduloCodigo: 'usuarios',
  routes: [
    { index: true,           element: RedirectPermisos,        handle: { breadcrumb: 'config' } },
    { path: 'permisos',      element: Wrap(UsuariosPermisosView), handle: { breadcrumb: 'config · permisos' } },
    { path: 'modulos',       element: Wrap(CatalogoModulosView),  handle: { breadcrumb: 'config · módulos' } },
    { path: 'sistema',       element: Wrap(SistemaView),          handle: { breadcrumb: 'config · sistema' } },
  ],
}
