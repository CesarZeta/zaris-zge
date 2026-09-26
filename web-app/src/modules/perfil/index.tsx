import { User } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { PerfilPage } from './pages/PerfilPage'

// «Mi perfil» — datos del usuario logueado, QR/link de la App del vecino y
// cambio voluntario de contraseña. Sin moduloCodigo: visible para cualquier
// usuario autenticado (solo toca sus propios datos; no hay fila en `modulos`).
// hideFromSidebar: se entra desde el menú del avatar del shell (§14), no del
// sidebar. Ruta: web-app/dist/index.html#/perfil. Plan en PLAN_MI_PERFIL.md.
export const perfilModule: ModuleManifest = {
  id: 'perfil',
  label: 'mi perfil',
  icon: User,
  hideFromSidebar: true,
  routes: [
    { index: true, element: PerfilPage, handle: { breadcrumb: 'mi perfil' } },
  ],
}
