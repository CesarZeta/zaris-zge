import type { Ocupacion } from '../types/agenda'
import { timeToMinutes } from '../../../lib/dates'
import { ConflictBadge } from './ConflictBadge'

interface Props {
  ocupacion: Ocupacion
  hourStart: number  // minutos desde 00:00 que arranca la grilla
  pxPerHour: number
  rowHeight: number
  enConflicto: boolean
  onClick: () => void
}

const COLORES: Record<Ocupacion['tipo'], { bg: string; border: string; text: string }> = {
  ot:     { bg: 'rgba(245,78,0,.16)',   border: 'var(--zaris-orange)',   text: 'var(--fg-1)' },
  evento: { bg: 'rgba(159,187,224,.30)', border: '#5a8fb8',              text: 'var(--fg-1)' },
  turno:  { bg: 'rgba(31,138,101,.16)', border: 'var(--color-success)', text: 'var(--fg-1)' },
}

export function GanttOccupationBlock({ ocupacion, hourStart, pxPerHour, rowHeight, enConflicto, onClick }: Props) {
  const inicio = timeToMinutes(ocupacion.hora_inicio.slice(0, 5))
  const fin    = timeToMinutes(ocupacion.hora_fin.slice(0, 5))
  const left   = ((inicio - hourStart) / 60) * pxPerHour
  const width  = Math.max(40, ((fin - inicio) / 60) * pxPerHour)
  const col    = COLORES[ocupacion.tipo] ?? COLORES.turno
  return (
    <button
      onClick={onClick}
      title={`${ocupacion.tipo} · ${ocupacion.hora_inicio.slice(0, 5)}-${ocupacion.hora_fin.slice(0, 5)} · ${ocupacion.descripcion_corta ?? ''}`}
      style={{
        position: 'absolute', left, width, top: 6, height: rowHeight - 12,
        background: col.bg, border: `1.5px solid ${enConflicto ? 'var(--color-error)' : col.border}`,
        borderRadius: 'var(--radius-md)', cursor: 'pointer', textAlign: 'left',
        padding: '4px 6px', overflow: 'hidden',
        fontFamily: 'var(--font-display)', fontSize: 11, color: col.text,
        display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 4 }}>
        <span style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.02em' }}>{ocupacion.tipo}</span>
        {enConflicto && <ConflictBadge small />}
      </div>
      <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {ocupacion.descripcion_corta || `${ocupacion.hora_inicio.slice(0, 5)}-${ocupacion.hora_fin.slice(0, 5)}`}
      </div>
    </button>
  )
}
