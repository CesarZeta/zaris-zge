import { NavLink, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../stores/auth'
import { modules } from '../../modules'
import s from './Sidebar.module.css'

// Sidebar del shell DEV (localhost:5173) — clon visual del sidebar del shell
// vanilla de producción (.nav-flat de index.html + frontend/css/menu.css),
// pedido de César 2026-08-31. Solo nav plano con secciones: el brand vive en
// el topbar, el logout en el menú de usuario y la versión en la statusbar
// (como en prod). "Maestros" (admin_tablas, vanilla) no aparece: no existe
// como ruta del bundle React — el resto espeja el orden y los labels de prod.

export function Sidebar() {
  const user = useAuthStore((st) => st.user)
  const location = useLocation()

  // Labels de prod (capitalizados; los manifests usan minúsculas).
  const LABEL: Record<string, string> = {
    emergencias: 'Emergencias', reclamos: 'Reclamos', turnos: 'Turnos',
    entradas: 'Entradas', tramites: 'Trámites',
    ot: 'Órdenes de Trabajo',
    agenda: 'Agenda', contactos: 'Contactos',
    bi: 'Datos', encuestas: 'Encuestas', usuarios: 'Usuarios',
    config: 'Configuración', guias: 'Guías',
  }
  // Sección de cada módulo (espeja .nav-flat__section del shell vanilla, §30).
  const SECCION: Record<string, string> = {
    emergencias: 'Atención', reclamos: 'Atención', turnos: 'Atención',
    entradas: 'Atención', tramites: 'Atención',
    ot: 'Supervisión',
    agenda: 'Común', contactos: 'Común',
    bi: 'Administración', encuestas: 'Administración', usuarios: 'Administración',
    config: 'Administración', guias: 'Administración',
  }
  // Ítems de "gestión del agente": otra puerta al mismo módulo (mismo
  // moduloCodigo de permiso). Van DESPUÉS de 'ot', como en prod.
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
    if (mod.id === 'dashboard') return false // home = click en el brand (como prod)
    if (mod.hideFromSidebar) return false
    if (!mod.moduloCodigo) return true
    return permitido(mod.moduloCodigo)
  })

  let seccionActual = ''
  return (
    <aside className={s.sidebar} aria-label="Menú principal">
      <nav className={s.navFlat} aria-label="Navegación principal">
        {visibles.map((mod) => {
          const Icon = mod.icon
          const isActive = location.pathname.startsWith(`/${mod.id}`)
          const seccion = SECCION[mod.id]
          const mostrarHeader = seccion && seccion !== seccionActual
          if (seccion) seccionActual = seccion
          const extras = (EXTRA_DESPUES_DE[mod.id] ?? []).filter((x) => permitido(x.modulo))
          return (
            <div key={mod.id} style={{ display: 'contents' }}>
              {mostrarHeader && <div className={s.section}>{seccion}</div>}
              <NavLink to={`/${mod.id}`} className={`${s.item} ${isActive ? s.active : ''}`}>
                <Icon size={16} strokeWidth={1.5} className={s.icon} />
                <span>{LABEL[mod.id] ?? mod.label}</span>
              </NavLink>
              {extras.map((x) => (
                <NavLink
                  key={x.to}
                  to={x.to}
                  className={`${s.item} ${location.pathname.startsWith(x.to) ? s.active : ''}`}
                >
                  <Icon size={16} strokeWidth={1.5} className={s.icon} />
                  <span>{x.label}</span>
                </NavLink>
              ))}
            </div>
          )
        })}
      </nav>
    </aside>
  )
}
