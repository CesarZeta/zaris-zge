import { Settings } from 'lucide-react'
import { Navigate } from 'react-router-dom'
import type { ModuleManifest } from '../../lib/types'
import { ConfigLayout } from './ConfigLayout'
import { IdentidadView } from './views/IdentidadView'
import { SistemaView } from './views/SistemaView'

const Wrap = (Component: React.FC) => () => (
  <ConfigLayout>
    <Component />
  </ConfigLayout>
)

// La tab por defecto es la primera del layout (Sistema); Identidad va última.
// "Permisos por usuario" y "Catálogo de módulos" se mudaron al módulo Usuarios
// (2026-07-16): Config queda para lo cross del software. Los paths viejos
// /config/permisos y /config/modulos redirigen al destino nuevo (deep-links).
const RedirectSistema = () => <Navigate to="/config/sistema" replace />
const RedirectPermisosMovidos = () => <Navigate to="/usuarios/permisos" replace />
const RedirectModulosMovidos = () => <Navigate to="/usuarios/modulos" replace />

export const configModule: ModuleManifest = {
  id: 'config',
  label: 'configuración',
  icon: Settings,
  // moduloCodigo='usuarios' como aproximacion: si tenes acceso a 'usuarios',
  // tenes acceso a configuracion. Backend `require_admin` exige nivel=1 igual.
  moduloCodigo: 'usuarios',
  routes: [
    { index: true,           element: RedirectSistema,            handle: { breadcrumb: 'config' } },
    { path: 'sistema',       element: Wrap(SistemaView),          handle: { breadcrumb: 'config · sistema' } },
    { path: 'identidad',     element: Wrap(IdentidadView),        handle: { breadcrumb: 'config · identidad' } },
    { path: 'permisos',      element: RedirectPermisosMovidos,    handle: { breadcrumb: 'config' } },
    { path: 'modulos',       element: RedirectModulosMovidos,     handle: { breadcrumb: 'config' } },
  ],
}
