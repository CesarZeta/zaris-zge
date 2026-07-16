import { Users } from 'lucide-react'
import { Navigate } from 'react-router-dom'
import type { ModuleManifest } from '../../lib/types'
import { UsuariosLayout } from './UsuariosLayout'
import { MaestroView } from './views/MaestroView'
import { CatalogoModulosView } from './views/CatalogoModulosView'

const Wrap = (Component: React.FC) => () => (
  <UsuariosLayout>
    <Component />
  </UsuariosLayout>
)

const RedirectMaestro = () => <Navigate to="/usuarios/maestro" replace />

// Módulo Usuarios (2026-07-16): maestro de cuentas (migrado del vanilla
// frontend/usuarios.html) con los permisos por usuario integrados en el
// detalle (sub-tab Datos|Permisos — merge UX) + Catálogo de módulos como
// tab aparte (config global). Config queda para lo cross del software.
// El path /usuarios/permisos se conserva como redirect (deep-links viejos
// y el redirect de /config/permisos).
export const usuariosModule: ModuleManifest = {
  id: 'usuarios',
  label: 'usuarios',
  icon: Users,
  moduloCodigo: 'usuarios',
  routes: [
    { index: true, element: RedirectMaestro, handle: { breadcrumb: 'usuarios' } },
    { path: 'maestro', element: Wrap(MaestroView), handle: { breadcrumb: 'usuarios · maestro' } },
    { path: 'permisos', element: RedirectMaestro, handle: { breadcrumb: 'usuarios' } },
    { path: 'modulos', element: Wrap(CatalogoModulosView), handle: { breadcrumb: 'usuarios · módulos' } },
  ],
}
