import type { ReactNode } from 'react'
import { Users } from 'lucide-react'

// Navegacion al inicio del shell vanilla (CLAUDE.md §14).
function goInicio(e: React.MouseEvent) {
  e.preventDefault()
  const w = window.parent as Window & { shellNavigate?: (url: string) => void }
  if (w?.shellNavigate) {
    w.shellNavigate('frontend/welcome.html')
  } else {
    window.location.href = '/'
  }
}

export function CiudadanosLayout({ children }: { children: ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 1400, margin: '0 auto', width: '100%', padding: '0 8px' }}>
      {/* Breadcrumb */}
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
        <span style={{ color: 'var(--fg-2)', fontWeight: 600 }}>Ciudadano</span>
      </nav>

      {/* Titulo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Users size={32} strokeWidth={1.5} color="var(--zaris-orange)" />
        <div>
          <h1 style={{
            fontSize: '1.55rem', fontWeight: 600, letterSpacing: '-0.5px',
            color: 'var(--fg-1)', lineHeight: 1.1, margin: 0,
          }}>
            Padron de Ciudadanos
          </h1>
          <p style={{ fontSize: '0.82rem', color: 'var(--fg-3)', margin: '2px 0 0' }}>
            Base Unica de Ciudadanos — identificacion y datos personales
          </p>
        </div>
      </div>

      {children}
    </div>
  )
}
