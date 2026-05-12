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
        {modules.filter((mod) => {
          // CLAUDE.md §30. Si el manifest declara moduloCodigo y el usuario tiene
          // modulos_permitidos, ocultar si no esta en la lista. Si no hay info,
          // fail-open (el guard real esta en el backend).
          if (!mod.moduloCodigo) return true
          const permitidos = user?.modulos_permitidos
          if (!Array.isArray(permitidos)) return true
          return permitidos.includes(mod.moduloCodigo)
        }).map((mod) => {
          const Icon = mod.icon
          const isActive = location.pathname.startsWith(`/${mod.id}`)
          return (
            <NavLink
              key={mod.id}
              to={`/${mod.id}`}
              className={`${s.navItem} ${isActive ? s.active : ''}`}
              title={sidebarCollapsed ? mod.label : undefined}
            >
              <Icon size={16} strokeWidth={1.5} />
              {!sidebarCollapsed && <span>{mod.label}</span>}
            </NavLink>
          )
        })}
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
