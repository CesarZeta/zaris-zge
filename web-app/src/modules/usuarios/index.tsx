import { Users } from 'lucide-react'
import { Navigate } from 'react-router-dom'
import type { ModuleManifest } from '../../lib/types'
import { UsuariosLayout } from './UsuariosLayout'
import { MaestroView } from './views/MaestroView'
import { UsuariosPermisosView } from './views/UsuariosPermisosView'
import { CatalogoModulosView } from './views/CatalogoModulosView'

const Wrap = (Component: React.FC) => () => (
  <UsuariosLayout>
    <Component />
  </UsuariosLayout>
)

const RedirectMaestro = () => <Navigate to="/usuarios/maestro" replace />

// Módulo Usuarios (2026-07-16): maestro de cuentas (migrado del vanilla
// frontend/usuarios.html) + las vistas de permisos que vivían en Config
// (pedido del usuario: los permisos son parte del maestro de usuarios;
// Config queda para lo cross del software).
export const usuariosModule: ModuleManifest = {
  id: 'usuarios',
  label: 'usuarios',
  icon: Users,
  moduloCodigo: 'usuarios',
  routes: [
    { index: true, element: RedirectMaestro, handle: { breadcrumb: 'usuarios' } },
    { path: 'maestro', element: Wrap(MaestroView), handle: { breadcrumb: 'usuarios · maestro' } },
    { path: 'permisos', element: Wrap(UsuariosPermisosView), handle: { breadcrumb: 'usuarios · permisos' } },
    { path: 'modulos', element: Wrap(CatalogoModulosView), handle: { breadcrumb: 'usuarios · módulos' } },
  ],
}
