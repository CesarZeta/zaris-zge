import { useStats } from '../hooks/useReclamos'
import type { StatsReclamos } from '../types/reclamo'

interface Props {
  estadoActivo: string | null
  onSelectEstado: (estado: string | null) => void
}

interface Card {
  key: string
  label: string
  match: (s: StatsReclamos) => number
  filtroEstado: string | null
  color: string
}

const CARDS: Card[] = [
  {
    key: 'total',
    label: 'Totales',
    match: (s) => Object.values(s).reduce((a, b) => a + b, 0),
    filtroEstado: null,
    color: 'var(--fg-1)',
  },
  {
    key: 'sin-asignar',
    label: 'Sin asignar',
    match: (s) => s['Sin asignar'] ?? 0,
    filtroEstado: 'Sin asignar',
    color: '#cf2d56',
  },
  {
    key: 'en-gestion',
    label: 'En gestión',
    match: (s) => (s['En gestión'] ?? 0) + (s['En espera'] ?? 0) + (s['En auditoría'] ?? 0),
    filtroEstado: 'En gestión',
    color: '#c08532',
  },
  {
    key: 'resueltos',
    label: 'Resueltos',
    match: (s) => s['Resuelto'] ?? 0,
    filtroEstado: 'Resuelto',
    color: '#1f8a65',
  },
]

export function StatsBar({ estadoActivo, onSelectEstado }: Props) {
  const stats = useStats()
  const data = stats.data ?? {}

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
      {CARDS.map((c) => {
        const total = c.match(data)
        const isActive = estadoActivo === c.filtroEstado || (estadoActivo == null && c.filtroEstado == null)
        return (
          <button
            key={c.key}
            onClick={() => onSelectEstado(c.filtroEstado)}
            style={{
              background: isActive ? 'var(--surface-200)' : 'var(--surface-100)',
              border: `1px solid ${isActive ? 'var(--zaris-orange)' : 'var(--border-primary)'}`,
              borderRadius: 'var(--radius-lg)',
              padding: '14px 16px',
              cursor: 'pointer',
              textAlign: 'left',
              fontFamily: 'var(--font-display)',
              transition: 'border-color 150ms, background 150ms',
            }}
            onMouseEnter={(e) => {
              if (!isActive) e.currentTarget.style.borderColor = 'var(--border-medium)'
            }}
            onMouseLeave={(e) => {
              if (!isActive) e.currentTarget.style.borderColor = 'var(--border-primary)'
            }}
          >
            <div style={{
              fontSize: 'var(--size-caption)', fontWeight: 600,
              textTransform: 'uppercase', letterSpacing: '0.05em',
              color: 'var(--fg-3)',
            }}>
              {c.label}
            </div>
            <div style={{
              fontSize: '1.75rem', fontWeight: 600,
              color: c.color, marginTop: 4,
              fontFamily: 'var(--font-display)',
            }}>
              {stats.isLoading ? '—' : total}
            </div>
          </button>
        )
      })}
    </div>
  )
}
