import type { ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { Settings } from 'lucide-react'

function goInicio(e: React.MouseEvent) {
  e.preventDefault()
  const w = window.parent as Window & { shellNavigate?: (url: string) => void }
  if (w?.shellNavigate) w.shellNavigate('web-app/dist/index.html#/dashboard')
  else window.location.href = '/'
}

const TABS = [
  { to: 'identidad', label: 'Identidad' },
  { to: 'permisos',  label: 'Permisos por usuario' },
  { to: 'modulos',   label: 'Catálogo de módulos' },
  { to: 'sistema',   label: 'Sistema' },
]

export function ConfigLayout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const partes = location.pathname.split('/').filter(Boolean)
  const subtitulo = TABS.find((t) => partes[1] === t.to)?.label

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
        <span style={{ color: 'var(--fg-2)', fontWeight: 600 }}>Configuración</span>
        {subtitulo && (
          <>
            <span style={{ color: 'var(--fg-3)' }}>›</span>
            <span style={{ color: 'var(--fg-2)', fontWeight: 600 }}>{subtitulo}</span>
          </>
        )}
      </nav>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Settings size={32} strokeWidth={1.5} color="var(--zaris-orange)" />
        <div>
          <h1 style={{
            fontSize: '1.55rem', fontWeight: 600, letterSpacing: '-0.5px',
            color: 'var(--fg-1)', lineHeight: 1.1, margin: 0,
          }}>
            Configuración
          </h1>
          <p style={{ fontSize: '0.82rem', color: 'var(--fg-3)', margin: '2px 0 0' }}>
            Permisos, catálogo de módulos y ajustes generales del sistema.
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
