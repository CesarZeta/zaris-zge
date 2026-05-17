import type { ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

function goInicio(e: React.MouseEvent) {
  e.preventDefault()
  const w = window.parent as Window & { shellNavigate?: (url: string) => void }
  if (w?.shellNavigate) {
    w.shellNavigate('web-app/dist/index.html#/dashboard')
  } else {
    window.location.href = '/'
  }
}

export function TramitesLayout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const partes = location.pathname.split('/').filter(Boolean)

  const isDetalle = partes.length >= 2 && partes[1] !== 'nuevo'
  const isCrear = partes[1] === 'nuevo'
  const numeroExpediente = isDetalle ? partes[1] : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, maxWidth: 1400, margin: '0 auto', width: '100%', padding: '0 8px' }}>
      <nav
        aria-label="Ruta de navegación"
        style={breadcrumbStyle}
      >
        <a href="#" onClick={goInicio} style={bcLinkStyle}>INICIO</a>
        <span style={bcSepStyle}>›</span>
        <span
          style={{ ...bcCurrentStyle, cursor: isDetalle || isCrear ? 'pointer' : 'default' }}
          onClick={isDetalle || isCrear ? () => navigate('/tramites') : undefined}
        >
          Trámites
        </span>
        {isDetalle && numeroExpediente && (
          <>
            <span style={bcSepStyle}>›</span>
            <span style={{ ...bcCurrentStyle, fontFamily: 'var(--font-mono)' }}>{numeroExpediente}</span>
          </>
        )}
        {isCrear && (
          <>
            <span style={bcSepStyle}>›</span>
            <span style={bcCurrentStyle}>Nuevo</span>
          </>
        )}
      </nav>

      {children}
    </div>
  )
}

const breadcrumbStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6,
  fontFamily: 'var(--font-display)', fontSize: '0.78rem',
  marginBottom: 20,
}
const bcLinkStyle: React.CSSProperties = {
  color: 'var(--zaris-orange)', textDecoration: 'none',
  textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600,
}
const bcSepStyle: React.CSSProperties = {
  color: 'var(--fg-3)',
}
const bcCurrentStyle: React.CSSProperties = {
  color: 'var(--fg-2)', fontWeight: 600,
}
