// Badges para estado y prioridad. Colores espejo del vanilla (frontend/reclamos.html badgeEstado/badgePrio).

interface BadgeProps {
  kind: 'estado' | 'prioridad'
  value: string
}

const ESTADO_COLORS: Record<string, { bg: string; fg: string }> = {
  'Sin asignar':   { bg: 'rgba(207,45,86,.12)',   fg: '#cf2d56' },
  'En gestión':    { bg: 'rgba(192,133,50,.14)',  fg: '#c08532' },
  'En espera':     { bg: 'rgba(120,120,120,.12)', fg: '#666' },
  'En auditoría':  { bg: 'rgba(96,165,200,.14)',  fg: '#3b82a8' },
  'Resuelto':      { bg: 'rgba(31,138,101,.12)',  fg: '#1f8a65' },
  'Cancelado':     { bg: 'rgba(38,37,30,.08)',    fg: 'var(--fg-2)' },
}

const PRIORIDAD_COLORS: Record<string, { bg: string; fg: string }> = {
  'Baja':     { bg: 'rgba(31,138,101,.10)',  fg: '#1f8a65' },
  'Media':    { bg: 'rgba(192,133,50,.12)',  fg: '#c08532' },
  'Alta':     { bg: 'rgba(245,78,0,.12)',    fg: 'var(--zaris-orange)' },
  'Crítica':  { bg: 'rgba(207,45,86,.14)',   fg: '#cf2d56' },
}

export function Badge({ kind, value }: BadgeProps) {
  const palette = kind === 'estado' ? ESTADO_COLORS : PRIORIDAD_COLORS
  const c = palette[value] || { bg: 'rgba(38,37,30,.08)', fg: 'var(--fg-2)' }
  return (
    <span style={{
      display: 'inline-block',
      padding: '3px 10px',
      borderRadius: 'var(--radius-pill)',
      fontSize: 10,
      fontWeight: 600,
      background: c.bg,
      color: c.fg,
      textTransform: 'uppercase',
      letterSpacing: '0.04em',
      whiteSpace: 'nowrap',
    }}>
      {value}
    </span>
  )
}
