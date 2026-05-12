import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, FileText, MapPin, Users } from 'lucide-react'
import {
  useCountCiudadanos,
  useReclamosActivos,
  useStatsReclamos,
} from '../hooks/useDashboardData'
import { DashboardMap } from '../components/DashboardMap'
import type { ReclamoListado } from '../../reclamos/types/reclamo'

export function Overview() {
  const navigate = useNavigate()
  const reclamosQ = useReclamosActivos()
  const statsQ    = useStatsReclamos()
  const ciudadanosQ = useCountCiudadanos()

  const reclamos = reclamosQ.data ?? []

  const conGeo = useMemo(
    () => reclamos.filter((r) => r.latitud != null && r.longitud != null),
    [reclamos],
  )

  const altaPrioridad = useMemo(
    () => reclamos.filter((r) => r.prioridad === 'Alta').length,
    [reclamos],
  )

  const totalReclamosActivos = reclamos.length
  const stats = statsQ.data ?? {}
  const sinAsignar = stats['Sin asignar'] ?? 0

  function abrirReclamo(r: ReclamoListado) {
    // Navega dentro del mismo router al detalle del reclamo.
    navigate(`/reclamos/${r.id_reclamo}`)
  }

  return (
    <div style={pageStyle}>
      {/* Mapa de fondo ocupa todo. */}
      <DashboardMap reclamos={conGeo} onMarkerClick={abrirReclamo} />

      {/* Stat cards flotantes arriba-izquierda. */}
      <div style={statsLayerStyle}>
        <div style={headerStyle}>
          <h1 style={titleStyle}>dashboard</h1>
          <p style={subtitleStyle}>Resumen operativo en tiempo real.</p>
        </div>

        <div style={cardsGridStyle}>
          <StatCard
            icon={FileText}
            label="Reclamos activos"
            value={totalReclamosActivos}
            sublabel={reclamosQ.isLoading ? 'cargando…' : `${conGeo.length} con geolocalización`}
          />
          <StatCard
            icon={AlertTriangle}
            label="Sin asignar"
            value={sinAsignar}
            sublabel={statsQ.isLoading ? 'cargando…' : 'requieren OT'}
            highlight={sinAsignar > 0}
          />
          <StatCard
            icon={MapPin}
            label="Prioridad alta"
            value={altaPrioridad}
            sublabel="en reclamos activos"
          />
          <StatCard
            icon={Users}
            label="Ciudadanos"
            value={ciudadanosQ.data ?? 0}
            sublabel={ciudadanosQ.isLoading ? 'cargando…' : 'registrados en BUC'}
          />
        </div>

        <div style={legendStyle}>
          <div style={legendTitle}>Estados</div>
          <div style={legendRowStyle}>
            <LegendDot color="#c62828" label="Sin asignar" />
            <LegendDot color="#ef6c00" label="En gestión" />
            <LegendDot color="#f57f17" label="En espera" />
            <LegendDot color="#6a1b9a" label="En auditoría" />
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({ icon: Icon, label, value, sublabel, highlight }: {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; color?: string }>
  label: string
  value: number
  sublabel?: string
  highlight?: boolean
}) {
  return (
    <div style={{
      ...cardStyle,
      borderLeft: highlight ? '3px solid var(--color-error)' : '3px solid var(--zaris-orange)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: '0.74rem', color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}>
          {label}
        </span>
        <Icon size={16} strokeWidth={1.5} color="var(--fg-3)" />
      </div>
      <div style={{ fontSize: '1.85rem', fontWeight: 600, color: 'var(--fg-1)', lineHeight: 1, marginBottom: 4 }}>
        {value}
      </div>
      {sublabel && (
        <div style={{ fontSize: '0.72rem', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
          {sublabel}
        </div>
      )}
    </div>
  )
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        width: 12, height: 12, borderRadius: '50%',
        background: color, border: '2px solid white',
        boxShadow: '0 1px 3px rgba(0,0,0,0.25)',
        display: 'inline-block',
      }} />
      <span style={{ fontSize: '0.74rem', color: 'var(--fg-2)' }}>{label}</span>
    </div>
  )
}

const pageStyle: React.CSSProperties = {
  position: 'relative',
  width: '100%',
  // El AppShell embebido pone el contenido en un main; le damos altura completa
  // restando el sidebar. height: 'calc(100vh - X)' no funciona porque el iframe
  // no tiene chrome propio. Usamos 100vh full y dejamos que overflow corte.
  height: 'calc(100vh - 32px)',
  minHeight: 540,
  overflow: 'hidden',
}

const statsLayerStyle: React.CSSProperties = {
  position: 'absolute',
  top: 16,
  left: 16,
  zIndex: 500,                       // sobre el overlay gris y los markers
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
  maxWidth: 'min(640px, calc(100% - 32px))',
}

const headerStyle: React.CSSProperties = {
  background: 'rgba(247,247,244,0.92)',  // surface-100 semi
  backdropFilter: 'blur(8px)',
  WebkitBackdropFilter: 'blur(8px)',
  border: '1px solid var(--border-primary)',
  borderRadius: 12,
  padding: '12px 16px',
  boxShadow: '0 4px 20px rgba(38,37,30,0.08)',
}

const titleStyle: React.CSSProperties = {
  fontSize: '1.4rem', fontWeight: 600, letterSpacing: '-0.5px',
  color: 'var(--fg-1)', margin: 0, lineHeight: 1.1,
}

const subtitleStyle: React.CSSProperties = {
  fontSize: '0.8rem', color: 'var(--fg-3)', margin: '4px 0 0',
}

const cardsGridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(2, minmax(140px, 1fr))',
  gap: 10,
}

const cardStyle: React.CSSProperties = {
  background: 'rgba(247,247,244,0.92)',
  backdropFilter: 'blur(8px)',
  WebkitBackdropFilter: 'blur(8px)',
  border: '1px solid var(--border-primary)',
  borderRadius: 12,
  padding: '12px 14px',
  boxShadow: '0 4px 20px rgba(38,37,30,0.08)',
}

const legendStyle: React.CSSProperties = {
  background: 'rgba(247,247,244,0.92)',
  backdropFilter: 'blur(8px)',
  WebkitBackdropFilter: 'blur(8px)',
  border: '1px solid var(--border-primary)',
  borderRadius: 10,
  padding: '8px 12px',
  boxShadow: '0 4px 20px rgba(38,37,30,0.08)',
}

const legendTitle: React.CSSProperties = {
  fontSize: '0.68rem', color: 'var(--fg-3)',
  textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600,
  marginBottom: 6,
}

const legendRowStyle: React.CSSProperties = {
  display: 'flex', gap: 14, flexWrap: 'wrap',
}
