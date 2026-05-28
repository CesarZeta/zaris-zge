import type { ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { BarChart3 } from 'lucide-react'
import { shellGoInicio } from '../../lib/shellNav'

// Tabs con paths ABSOLUTOS (no relativos): un `to="contacto"` relativo se
// resolveria contra la ruta actual completa y caeria al catch-all → dashboard
// (bug §41). Siempre `/encuestas/<tab>`.
const TABS: { to: string; label: string }[] = [
  { to: '/encuestas',            label: 'Resumen' },
  { to: '/encuestas/contacto',   label: 'Pedidos de contacto' },
  { to: '/encuestas/envios',     label: 'Envíos' },
  { to: '/encuestas/plantillas', label: 'Encuestas' },
]

export function EncuestasLayout({ children }: { children: ReactNode }) {
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
        <span style={{ color: 'var(--fg-2)', fontWeight: 600 }}>Encuestas</span>
      </nav>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <BarChart3 size={32} strokeWidth={1.5} color="var(--zaris-orange)" />
        <div>
          <h1 style={{ fontSize: '1.55rem', fontWeight: 600, letterSpacing: '-0.5px', color: 'var(--fg-1)', lineHeight: 1.1, margin: 0 }}>
            Encuestas de satisfacción
          </h1>
          <p style={{ fontSize: '0.82rem', color: 'var(--fg-3)', margin: '2px 0 0' }}>
            Resultados de las encuestas CSAT que se envían al cerrar reclamos.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border-primary)' }}>
        {TABS.map((t) => {
          // 'end' para que /encuestas (Resumen) no quede activo en sub-rutas.
          const active = t.to === '/encuestas'
            ? location.pathname === '/encuestas' || location.pathname === '/encuestas/'
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
