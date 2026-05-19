import type { ReactNode } from 'react'

function goInicio(e: React.MouseEvent) {
  e.preventDefault()
  const w = window.parent as Window & { shellNavigate?: (url: string) => void }
  if (w?.shellNavigate) w.shellNavigate('web-app/dist/index.html#/dashboard')
  else window.location.href = '/'
}

export function GuiasLayout({ children }: { children: ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18, maxWidth: 1400, margin: '0 auto', width: '100%', padding: '0 8px' }}>
      <nav aria-label="Ruta de navegación" style={breadcrumbStyle}>
        <a href="#" onClick={goInicio} style={bcLinkStyle}>INICIO</a>
        <span style={bcSepStyle}>›</span>
        <span style={bcCurrentStyle}>Guías</span>
      </nav>
      {children}
    </div>
  )
}

const breadcrumbStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6,
  fontFamily: 'var(--font-display)', fontSize: '0.78rem',
  marginBottom: 12,
}
const bcLinkStyle: React.CSSProperties = {
  color: 'var(--zaris-orange)', textDecoration: 'none',
  textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600,
}
const bcSepStyle: React.CSSProperties = { color: 'var(--fg-3)' }
const bcCurrentStyle: React.CSSProperties = { color: 'var(--fg-2)', fontWeight: 600 }
