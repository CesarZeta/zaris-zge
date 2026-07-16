import type { ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { Users } from 'lucide-react'
import { shellGoInicio } from '../../lib/shellNav'

function goInicio(e: React.MouseEvent) {
  e.preventDefault()
  shellGoInicio()
}

// Paths ABSOLUTOS (regla del módulo Config §41): un `to` relativo se resuelve
// contra la ruta actual completa y cae al catch-all '*' → dashboard.
// Merge UX 2026-07-16: los permisos por usuario se editan DENTRO del detalle
// de cada usuario (sub-tab Datos|Permisos del maestro), no en solapa propia.
// El catálogo de módulos queda aparte porque es configuración GLOBAL.
const TABS = [
  { to: '/usuarios/maestro', slug: 'maestro', label: 'Usuarios' },
  { to: '/usuarios/modulos', slug: 'modulos', label: 'Catálogo de módulos' },
]

export function UsuariosLayout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const partes = location.pathname.split('/').filter(Boolean)
  const subtitulo = TABS.find((t) => partes[1] === t.slug)?.label

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18, maxWidth: 1400, margin: '0 auto', width: '100%', padding: '0 8px' }}>
      <nav
        aria-label="Ruta de navegacion"
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          fontFamily: 'var(--font-display)', fontSize: '0.78rem',
        }}
      >
        <a
          href="#"
          onClick={goInicio}
          style={{
            color: 'var(--zaris-orange)', textDecoration: 'none',
            textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600,
          }}
        >
          INICIO
        </a>
        <span style={{ color: 'var(--fg-3)' }}>›</span>
        <span style={{ color: 'var(--fg-2)', fontWeight: 600 }}>Usuarios</span>
        {subtitulo && subtitulo !== 'Usuarios' && (
          <>
            <span style={{ color: 'var(--fg-3)' }}>›</span>
            <span style={{ color: 'var(--fg-2)', fontWeight: 600 }}>{subtitulo}</span>
          </>
        )}
      </nav>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Users size={32} strokeWidth={1.5} color="var(--zaris-orange)" />
        <div>
          <h1 style={{
            fontSize: '1.55rem', fontWeight: 600, letterSpacing: '-0.5px',
            color: 'var(--fg-1)', lineHeight: 1.1, margin: 0,
          }}>
            Usuarios
          </h1>
          <p style={{ fontSize: '0.82rem', color: 'var(--fg-3)', margin: '2px 0 0' }}>
            Cuentas del sistema con sus permisos, y catálogo de módulos.
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border-primary)' }}>
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            style={({ isActive }) => ({
              background: 'transparent', border: 'none',
              fontFamily: 'var(--font-display)', fontSize: '0.92rem',
              fontWeight: isActive ? 600 : 500,
              padding: '10px 18px',
              color: isActive ? 'var(--zaris-orange)' : 'var(--fg-3)',
              borderBottom: `2px solid ${isActive ? 'var(--zaris-orange)' : 'transparent'}`,
              marginBottom: -1,
              textDecoration: 'none',
            })}
          >
            {t.label}
          </NavLink>
        ))}
      </div>

      {children}
    </div>
  )
}
