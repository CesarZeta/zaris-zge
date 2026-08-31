import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { useAuthStore } from '../../stores/auth'
import { useIdentidadMunicipio } from '../../modules/dashboard/hooks/useDashboardData'
import { NotificacionesDropdown } from './NotificacionesDropdown'
import s from './TopBar.module.css'

// Topbar del shell DEV (localhost:5173) — clon visual del topbar del shell
// vanilla de producción (index.html + frontend/css/menu.css), pedido de César
// 2026-08-31 para que la vista previa en dev refleje la interfase real.
// Estructura de prod: brand ZARIS + "GESTION ESTADO" · separador · identidad
// del municipio | campana · contexto de usuario en 2 líneas · avatar.

const ROL_LABEL: Record<number, string> = {
  1: 'Administrador', 2: 'Supervisor', 3: 'Atención', 4: 'Gestión', 5: 'Consultor',
}

export function TopBar() {
  const user = useAuthStore((st) => st.user)
  const logout = useAuthStore((st) => st.logout)
  const identidadQ = useIdentidadMunicipio()
  const [menuAbierto, setMenuAbierto] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuAbierto) return
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuAbierto(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [menuAbierto])

  const iniciales = user?.nombre
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase() ?? '—'

  return (
    <header className={s.topbar}>
      <div className={s.left}>
        <Link to="/dashboard" className={s.brand} aria-label="ZARIS — Inicio">
          <svg className={s.brandMark} viewBox="0 0 500 500" aria-hidden="true">
            <g fill="none" stroke="currentColor" strokeWidth="34" strokeLinecap="round" strokeLinejoin="round">
              <path d="M 110 78 L 388 78" />
              <path d="M 388 78 L 110 430" />
              <path d="M 388 220 L 222 430" />
              <path d="M 388 362 L 334 430" />
            </g>
          </svg>
          <span className={s.brandName}>ZARIS</span>
          <span className={s.brandApp}>GESTION ESTADO</span>
        </Link>

        <span className={s.sep} aria-hidden="true" />

        <div className={s.muni}>
          {identidadQ.data?.municipio_logo_url ? (
            <img
              className={s.muniLogo}
              src={resolverLogoUrl(identidadQ.data.municipio_logo_url)}
              alt=""
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
            />
          ) : null}
          <span className={s.muniNombre}>{identidadQ.data?.municipio_nombre ?? ''}</span>
        </div>
      </div>

      <div className={s.right}>
        <NotificacionesDropdown />

        {user && (
          <div className={s.userMenu} ref={menuRef}>
            <button
              type="button"
              className={s.userTrigger}
              onClick={() => setMenuAbierto((v) => !v)}
              aria-haspopup="true"
              aria-expanded={menuAbierto}
            >
              <span className={s.context}>
                <strong>{user.nombre} · {ROL_LABEL[user.nivel_acceso] ?? `Nivel ${user.nivel_acceso}`}</strong>
                {user.cargo_nombre && <span className={s.contextCargo}>Cargo: {user.cargo_nombre}</span>}
              </span>
              <div className={s.avatar}>
                {user.foto_url ? <img src={user.foto_url} alt="" /> : iniciales}
              </div>
            </button>
            {menuAbierto && (
              <div className={s.dropdown} role="menu">
                <div className={s.dropdownInfo}>
                  <span className={s.dropdownNombre}>{user.nombre}</span>
                  <span className={s.dropdownEmail}>{user.email}</span>
                </div>
                <div className={s.dropdownDivider} />
                <button type="button" className={`${s.dropdownItem} ${s.dropdownItemDanger}`} onClick={logout}>
                  <LogOut size={14} strokeWidth={1.5} />
                  Cerrar sesión
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  )
}

// El logo del municipio puede venir absoluto (Supabase) o relativo a la raíz
// del shell vanilla — mismo criterio que Overview del Dashboard (§32 Q13).
function resolverLogoUrl(url: string): string {
  if (!url.startsWith('/')) return url
  const m = window.location.pathname.match(/^(.*)\/web-app\/dist\//)
  return (m ? m[1] : '') + url
}
