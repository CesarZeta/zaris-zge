import { useMatches } from 'react-router-dom'
import { Search } from 'lucide-react'
import { useAuthStore } from '../../stores/auth'
import { useUiStore } from '../../stores/ui'
import { NotificacionesDropdown } from './NotificacionesDropdown'
import s from './TopBar.module.css'

export function TopBar() {
  const user = useAuthStore((s) => s.user)
  const openCmdk = useUiStore((s) => s.openCmdk)
  const matches = useMatches()

  const crumbs = matches
    .filter((m) => (m.handle as { breadcrumb?: string } | undefined)?.breadcrumb)
    .map((m) => (m.handle as { breadcrumb: string }).breadcrumb)

  return (
    <header className={s.topbar}>
      {/* Breadcrumb */}
      <nav className={s.breadcrumb} aria-label="Ruta actual">
        {crumbs.length === 0 ? (
          <span className={s.crumbCurrent}>inicio</span>
        ) : (
          crumbs.map((c, i) => (
            <span key={i} className={s.crumbGroup}>
              {i > 0 && <span className={s.sep}>·</span>}
              <span className={i === crumbs.length - 1 ? s.crumbCurrent : s.crumb}>{c}</span>
            </span>
          ))
        )}
      </nav>

      {/* Search trigger */}
      <button className={s.searchBtn} onClick={openCmdk} aria-label="Abrir búsqueda (Ctrl+K)">
        <Search size={13} strokeWidth={1.5} />
        <span>Buscar — o presione</span>
        <kbd className={s.kbd}>⌘K</kbd>
      </button>

      {/* Right actions */}
      <div className={s.right}>
        <NotificacionesDropdown />

        {user && (
          <div className={s.userPill} title={user.email}>
            <div className={s.avatar}>
              {user.nombre.split(' ').slice(0, 2).map((w) => w[0]).join('').toUpperCase()}
            </div>
            <span className={s.userName}>{user.nombre.split(' ')[0]}</span>
          </div>
        )}
      </div>
    </header>
  )
}
