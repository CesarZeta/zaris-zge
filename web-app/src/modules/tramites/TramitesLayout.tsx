import type { ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/auth'

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
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const puedeConfigurar = hasPermission(2) // nivel <= 2 (Admin o Supervisor)

  const isCrear = partes[1] === 'nuevo'
  const isConfig = partes[1] === 'config'
  const isConfigDetalle = isConfig && partes.length >= 3
  const isDetalle = !isCrear && !isConfig && partes.length >= 2
  const numeroExpediente = isDetalle ? partes[1] : null
  const idTipoConfig = isConfigDetalle ? partes[2] : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, maxWidth: 1400, margin: '0 auto', width: '100%', padding: '0 8px' }}>
      <nav aria-label="Ruta de navegación" style={breadcrumbStyle}>
        <a href="#" onClick={goInicio} style={bcLinkStyle}>INICIO</a>
        <span style={bcSepStyle}>›</span>
        <span
          style={{ ...bcCurrentStyle, cursor: isDetalle || isCrear || isConfig ? 'pointer' : 'default' }}
          onClick={isDetalle || isCrear || isConfig ? () => navigate('/tramites') : undefined}
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
        {isConfig && (
          <>
            <span style={bcSepStyle}>›</span>
            <span
              style={{ ...bcCurrentStyle, cursor: isConfigDetalle ? 'pointer' : 'default' }}
              onClick={isConfigDetalle ? () => navigate('/tramites/config') : undefined}
            >
              Configuración
            </span>
            {isConfigDetalle && idTipoConfig && (
              <>
                <span style={bcSepStyle}>›</span>
                <span style={bcCurrentStyle}>Editor</span>
              </>
            )}
          </>
        )}
      </nav>

      {/* Tabs principales — visible siempre que no estemos en detalle de trámite ni crear */}
      {!isDetalle && !isCrear && (
        <div style={tabsBar}>
          <button
            onClick={() => navigate('/tramites')}
            style={{
              ...tabBtn,
              borderBottom: !isConfig ? '2px solid var(--zaris-orange)' : '2px solid transparent',
              color: !isConfig ? 'var(--fg-1)' : 'var(--fg-3)',
              fontWeight: !isConfig ? 600 : 400,
            }}
          >
            Bandeja
          </button>
          {puedeConfigurar && (
            <button
              onClick={() => navigate('/tramites/config')}
              style={{
                ...tabBtn,
                borderBottom: isConfig ? '2px solid var(--zaris-orange)' : '2px solid transparent',
                color: isConfig ? 'var(--fg-1)' : 'var(--fg-3)',
                fontWeight: isConfig ? 600 : 400,
              }}
            >
              Configuración
            </button>
          )}
        </div>
      )}

      {children}
    </div>
  )
}

const tabsBar: React.CSSProperties = {
  display: 'flex',
  gap: 4,
  borderBottom: '1px solid var(--border-primary)',
  marginBottom: 16,
}
const tabBtn: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  padding: '8px 16px',
  fontFamily: 'var(--font-display)',
  fontSize: 14,
  transition: 'color 150ms ease',
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
