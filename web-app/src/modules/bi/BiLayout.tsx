import type { ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { Activity } from 'lucide-react'
import { shellGoInicio } from '../../lib/shellNav'
import { shellNavigate } from '../../lib/shellNav'

// Layout del tablero OPERATIVO. Tabs con paths ABSOLUTOS bajo /bi/operativo
// (un `to` relativo caería al catch-all → dashboard, bug §41).
const TABS: { to: string; label: string }[] = [
  { to: '/bi/operativo', label: 'Resumen' },
  { to: '/bi/operativo/resueltos', label: 'Resueltos / SLA' },
  { to: '/bi/operativo/pendientes', label: 'Pendientes' },
  { to: '/bi/operativo/subreclamos', label: 'Subreclamos' },
]

export function BiLayout({ children }: { children: ReactNode }) {
  const location = useLocation()

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18, maxWidth: 1400, margin: '0 auto', width: '100%', padding: '0 8px' }}>
      <nav
        aria-label="Ruta de navegación"
        style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'var(--font-display)', fontSize: '0.78rem' }}
      >
        <a
          href="#"
          onClick={(e) => { e.preventDefault(); shellGoInicio() }}
          style={{ color: 'var(--zaris-orange)', textDecoration: 'none', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}
        >
          INICIO
        </a>
        <span style={{ color: 'var(--fg-3)' }}>›</span>
        <a
          href="#"
          onClick={(e) => { e.preventDefault(); navDatos() }}
          style={{ color: 'var(--zaris-orange)', textDecoration: 'none', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}
        >
          DATOS
        </a>
        <span style={{ color: 'var(--fg-3)' }}>›</span>
        <span style={{ color: 'var(--fg-2)', fontWeight: 600 }}>Análisis de datos Operativo</span>
      </nav>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Activity size={32} strokeWidth={1.5} color="var(--zaris-orange)" />
        <div>
          <h1 style={{ fontSize: '1.55rem', fontWeight: 600, letterSpacing: '-0.5px', color: 'var(--fg-1)', lineHeight: 1.1, margin: 0 }}>
            Análisis de datos Operativo
          </h1>
          <p style={{ fontSize: '0.82rem', color: 'var(--fg-3)', margin: '2px 0 0' }}>
            Tableros del día a día: volumen, estados, áreas, canales, SLA, pendientes y subreclamos.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border-primary)', flexWrap: 'wrap' }}>
        {TABS.map((t) => {
          const active = t.to === '/bi/operativo'
            ? location.pathname === '/bi/operativo' || location.pathname === '/bi/operativo/'
            : location.pathname.startsWith(t.to)
          return (
            <NavLink
              key={t.to}
              to={t.to}
              style={{
                fontFamily: 'var(--font-display)', fontSize: '0.86rem', fontWeight: 500,
                padding: '8px 14px', textDecoration: 'none',
                color: active ? 'var(--fg-1)' : 'var(--fg-3)',
                borderBottom: `2px solid ${active ? 'var(--zaris-orange)' : 'transparent'}`,
                marginBottom: -1,
              }}
            >
              {t.label}
            </NavLink>
          )
        })}
      </div>

      {children}
    </div>
  )
}

// Navega a la landing DATOS, respetando iframe (shell vanilla) vs standalone.
function navDatos() {
  if (typeof window !== 'undefined' && window.self !== window.top) {
    shellNavigate('web-app/dist/index.html#/bi')
  } else {
    window.location.hash = '#/bi'
  }
}
