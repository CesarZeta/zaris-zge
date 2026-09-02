import type { ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { MapPin, X } from 'lucide-react'
import { useAuthStore } from '../../stores/auth'
import { useUbicacionTurnosStore } from './stores/ubicacionTurnos'

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
  const ubicacion = useUbicacionTurnosStore((s) => s.ubicacion)
  const setUbicacion = useUbicacionTurnosStore((s) => s.setUbicacion)

  // F2 plan ATENCION (2026-09-01): el módulo se navega ubicación-primero.
  // index = landing de ubicaciones; 'mesa' = mesa del día; 'lista' = listado.
  const sub = partes[1] // 'mesa' | 'lista' | 'agenda' | 'atendidos' | 'consultas' | 'prestaciones' | undefined
  const isMesa = sub === 'mesa'
  const isLista = sub === 'lista'
  const isAgenda = sub === 'agenda'
  const isAtendidos = sub === 'atendidos'
  const isConsultas = sub === 'consultas'
  const isPrestaciones = sub === 'prestaciones'
  const isUbicaciones = !isMesa && !isLista && !isAgenda && !isAtendidos && !isConsultas && !isPrestaciones
  const subLabel = isMesa ? 'Mesa del día' : isLista ? 'Turnos' : isAgenda ? 'Agenda'
    : isAtendidos ? 'Atendidos' : isConsultas ? 'Consultas' : isPrestaciones ? 'Prestaciones' : null

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
        <Tab label="Ubicaciones" active={isUbicaciones} onClick={() => navigate('/turnos')} />
        <Tab label="Mesa del día" active={isMesa} onClick={() => navigate('/turnos/mesa')} />
        <Tab label="Turnos" active={isLista} onClick={() => navigate('/turnos/lista')} />
        <Tab label="Agenda" active={isAgenda} onClick={() => navigate('/turnos/agenda')} />
        <Tab label="Atendidos" active={isAtendidos} onClick={() => navigate('/turnos/atendidos')} />
        <Tab label="Consultas" active={isConsultas} onClick={() => navigate('/turnos/consultas')} />
        {puedeGestionarPrestaciones && (
          <Tab label="Prestaciones" active={isPrestaciones} onClick={() => navigate('/turnos/prestaciones')} />
        )}
      </div>

      {/* Contexto de ubicación: scopea Mesa, Turnos, Agenda y Atendidos. */}
      {ubicacion && !isUbicaciones && !isConsultas && !isPrestaciones && (
        <div style={ctxBar}>
          <MapPin size={13} strokeWidth={1.5} style={{ color: 'var(--zaris-orange)' }} />
          <span>
            Ubicación: <strong style={{ color: 'var(--fg-1)' }}>{ubicacion.nombre}</strong>
          </span>
          <button onClick={() => navigate('/turnos')} style={ctxBtn}>Cambiar</button>
          <button
            onClick={() => setUbicacion(null)}
            style={ctxBtn}
            title="Quitar el filtro de ubicación (ver todas)"
          >
            <X size={12} strokeWidth={1.5} /> Quitar
          </button>
        </div>
      )}

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
  display: 'flex', gap: 4, borderBottom: '1px solid var(--border-primary)', flexWrap: 'wrap',
}
const tabBtn: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.88rem', cursor: 'pointer',
  background: 'transparent', border: 'none', padding: '10px 16px',
  marginBottom: -1,
}
const ctxBar: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
  fontFamily: 'var(--font-display)', fontSize: '0.78rem', color: 'var(--fg-2)',
  background: 'var(--surface-300)', border: '1px solid var(--border-primary)', borderTop: 'none',
  borderRadius: '0 0 10px 10px', padding: '6px 12px',
}
const ctxBtn: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.74rem', cursor: 'pointer',
  background: 'transparent', color: 'var(--zaris-orange)', border: 'none', fontWeight: 600,
  display: 'inline-flex', alignItems: 'center', gap: 3, padding: '2px 4px',
}
