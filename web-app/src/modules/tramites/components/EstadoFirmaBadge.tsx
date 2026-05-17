import type { EstadoFirma } from '../types'

const CONFIG: Record<EstadoFirma, { bg: string; fg: string; label: string }> = {
  no_requiere: { bg: 'var(--surface-400)',       fg: 'var(--fg-3)',           label: 'Sin firma' },
  pendiente:   { bg: 'rgba(192,133,50,.18)',      fg: 'var(--zaris-gold)',     label: 'Firma pendiente' },
  firmado:     { bg: 'rgba(31,138,101,.14)',      fg: '#1f8a65',               label: 'Firmado' },
  rechazado:   { bg: 'rgba(207,45,86,.14)',       fg: 'var(--color-error)',    label: 'Firma rechazada' },
}

export function EstadoFirmaBadge({ estado }: { estado: EstadoFirma }) {
  const c = CONFIG[estado] ?? CONFIG.no_requiere
  return (
    <span
      style={{
        background: c.bg,
        color: c.fg,
        fontSize: 10,
        fontWeight: 500,
        padding: '2px 8px',
        borderRadius: 'var(--radius-pill)',
        fontFamily: 'var(--font-display)',
        whiteSpace: 'nowrap',
      }}
    >
      {c.label}
    </span>
  )
}
