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

export function TurnosLayout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const partes = location.pathname.split('/').filter(Boolean)
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const puedeGestionarPrestaciones = hasPermission(2) // nivel <= 2 (Admin o Supervisor)

  const sub = partes[1] // 'agenda' | 'atendidos' | 'consultas' | 'prestaciones' | undefined (turnos)
  const isAgenda = sub === 'agenda'
  const isAtendidos = sub === 'atendidos'
  const isConsultas = sub === 'consultas'
  const isPrestaciones = sub === 'prestaciones'
  const isTurnos = !isAgenda && !isAtendidos && !isConsultas && !isPrestaciones
  const subLabel = isAgenda ? 'Agenda' : isAtendidos ? 'Atendidos' : isConsultas ? 'Consultas' : isPrestaciones ? 'Prestaciones' : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, maxWidth: 1400, margin: '0 auto', width: '100%', padding: '0 8px' }}>
      <nav aria-label="Ruta de navegación" style={breadcrumbStyle}>
        <a href="#" onClick={goInicio} style={bcLinkStyle}>INICIO</a>
        <span style={bcSepStyle}>›</span>
        <span
          style={{ ...bcCurrentStyle, cursor: subLabel ? 'pointer' : 'default' }}
          onClick={subLabel ? () => navigate('/turnos') : undefined}
        >
          Turnos
        </span>
        {subLabel && (
          <>
            <span style={bcSepStyle}>›</span>
            <span style={bcCurrentStyle}>{subLabel}</span>
          </>
        )}
      </nav>

      <div style={tabsBar}>
        <Tab label="Turnos" active={isTurnos} onClick={() => navigate('/turnos')} />
        <Tab label="Agenda" active={isAgenda} onClick={() => navigate('/turnos/agenda')} />
        <Tab label="Atendidos" active={isAtendidos} onClick={() => navigate('/turnos/atendidos')} />
        <Tab label="Consultas" active={isConsultas} onClick={() => navigate('/turnos/consultas')} />
        {puedeGestionarPrestaciones && (
          <Tab label="Prestaciones" active={isPrestaciones} onClick={() => navigate('/turnos/prestaciones')} />
        )}
      </div>

      <div style={{ paddingTop: 16 }}>{children}</div>
    </div>
  )
}

function Tab({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        ...tabBtn,
        borderBottom: active ? '2px solid var(--zaris-orange)' : '2px solid transparent',
        color: active ? 'var(--fg-1)' : 'var(--fg-3)',
        fontWeight: active ? 600 : 400,
      }}
    >
      {label}
    </button>
  )
}

const breadcrumbStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6,
  fontFamily: 'var(--font-display)', fontSize: '0.78rem', margin: '8px 0 12px',
}
const bcLinkStyle: React.CSSProperties = {
  color: 'var(--zaris-orange)', textDecoration: 'none',
  textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600,
}
const bcSepStyle: React.CSSProperties = { color: 'var(--fg-3)' }
const bcCurrentStyle: React.CSSProperties = { color: 'var(--fg-2)', fontWeight: 600 }

const tabsBar: React.CSSProperties = {
  display: 'flex', gap: 4, borderBottom: '1px solid var(--border-primary)',
}
const tabBtn: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.88rem', cursor: 'pointer',
  background: 'transparent', border: 'none', padding: '10px 16px',
  marginBottom: -1,
}
