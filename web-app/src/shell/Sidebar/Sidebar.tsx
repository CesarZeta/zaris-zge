import { NavLink, useLocation } from 'react-router-dom'
import { PanelLeft, LogOut } from 'lucide-react'
import { useAuthStore } from '../../stores/auth'
import { useUiStore } from '../../stores/ui'
import { modules } from '../../modules'
import s from './Sidebar.module.css'

export function Sidebar() {
  const { user, logout } = useAuthStore()
  const { sidebarCollapsed, toggleSidebar } = useUiStore()
  const location = useLocation()

  const initials = user?.nombre
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase() ?? '?'

  return (
    <aside className={`${s.sidebar} ${sidebarCollapsed ? s.collapsed : ''}`}>
      {/* Logo */}
      <div className={s.logo}>
        <div className={s.mark}>
          <svg width="16" height="16" viewBox="0 0 28 28" fill="none">
            <path d="M6 6h16L8 22h16" stroke="currentColor" strokeWidth="2.8" strokeLinecap="square" />
          </svg>
        </div>
        {!sidebarCollapsed && <span className={s.wordmark}>ZARIS</span>}
      </div>

      {/* Nav */}
      <nav className={s.nav} aria-label="Navegación principal">
        {(() => {
          // Sección de cada módulo (espeja .nav-flat__section del shell vanilla,
          // §30). El encabezado se renderiza solo cuando empieza una sección
          // nueva Y tiene al menos un ítem visible — así no queda título huérfano.
          const SECCION: Record<string, string> = {
            emergencias: 'Atención', reclamos: 'Atención', turnos: 'Atención',
            entradas: 'Atención', tramites: 'Atención',
            ot: 'Supervisión',
            agenda: 'Común', contactos: 'Común',
            bi: 'Administración', encuestas: 'Administración',
            config: 'Administración', guias: 'Administración',
          }
          // Ítems de "gestión del agente": otra puerta al mismo módulo (mismo
          // moduloCodigo de permiso), apuntando a la vista de lo propio. Se
          // emiten DESPUÉS del módulo 'ot' (sección Supervisión), espejando el
          // sidebar vanilla. ModuleManifest = 1 módulo : 1 ítem, así que estos
          // van como entradas explícitas fuera del map de módulos.
          const EXTRA_DESPUES_DE: Record<string, { to: string; label: string; modulo: string }[]> = {
            ot: [
              { to: '/turnos/mis-turnos', label: 'Gestión de Turnos', modulo: 'turnos' },
              { to: '/tramites/mi-bandeja', label: 'Gestión de Trámites', modulo: 'tramites' },
            ],
          }
          const permitido = (modulo: string) => {
            const permitidos = user?.modulos_permitidos
            if (!Array.isArray(permitidos)) return true // fail-open (§30)
            return permitidos.includes(modulo)
          }
          const visibles = modules.filter((mod) => {
            // Manifest puede pedir que el modulo no aparezca en sidebar (ej:
            // ciudadanos/empresas viven detras de la landing de Contactos).
            if (mod.hideFromSidebar) return false
            // CLAUDE.md §30. Si el manifest declara moduloCodigo y el usuario tiene
            // modulos_permitidos, ocultar si no esta en la lista. Si no hay info,
            // fail-open (el guard real esta en el backend).
            if (!mod.moduloCodigo) return true
            return permitido(mod.moduloCodigo)
          })
          let seccionActual = ''
          return visibles.map((mod) => {
            const Icon = mod.icon
            const isActive = location.pathname.startsWith(`/${mod.id}`)
            const seccion = SECCION[mod.id]
            const mostrarHeader = !sidebarCollapsed && seccion && seccion !== seccionActual
            if (seccion) seccionActual = seccion
            const extras = (EXTRA_DESPUES_DE[mod.id] ?? []).filter((x) => permitido(x.modulo))
            return (
              <div key={mod.id} style={{ display: 'contents' }}>
                {mostrarHeader && <div className={s.section}>{seccion}</div>}
                <NavLink
                  to={`/${mod.id}`}
                  className={`${s.navItem} ${isActive ? s.active : ''}`}
                  title={sidebarCollapsed ? mod.label : undefined}
                >
                  <Icon size={16} strokeWidth={1.5} />
                  {!sidebarCollapsed && <span>{mod.label}</span>}
                </NavLink>
                {extras.map((x) => (
                  <NavLink
                    key={x.to}
                    to={x.to}
                    className={`${s.navItem} ${location.pathname.startsWith(x.to) ? s.active : ''}`}
                    title={sidebarCollapsed ? x.label : undefined}
                  >
                    <Icon size={16} strokeWidth={1.5} />
                    {!sidebarCollapsed && <span>{x.label}</span>}
                  </NavLink>
                ))}
              </div>
            )
          })
        })()}
      </nav>

      {/* Footer */}
      <div className={s.footer}>
        {!sidebarCollapsed && user && (
          <div className={s.userCard}>
            <div className={s.avatar}>{initials}</div>
            <div className={s.userInfo}>
              <span className={s.userName}>{user.nombre}</span>
              <span className={s.userRole}>nivel {user.nivel_acceso}</span>
            </div>
          </div>
        )}
        <div className={s.footerActions}>
          <button
            className={s.logoutBtn}
            onClick={logout}
            title="Cerrar sesión"
            aria-label="Cerrar sesión"
          >
            <LogOut size={15} strokeWidth={1.5} />
          </button>
          <button
            className={s.collapseBtn}
            onClick={toggleSidebar}
            title={sidebarCollapsed ? 'Expandir sidebar' : 'Colapsar sidebar'}
            aria-label={sidebarCollapsed ? 'Expandir sidebar' : 'Colapsar sidebar'}
          >
            <PanelLeft size={15} strokeWidth={1.5} />
          </button>
        </div>
      </div>
    </aside>
  )
}
