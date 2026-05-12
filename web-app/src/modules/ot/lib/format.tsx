import type { ReactNode } from 'react'
import type { EstadoOT, EstadoReclamoOT, PrioridadReclamo } from '../types/ot'

// ── Badges ───────────────────────────────────────────────────────────

const badgeBase: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  padding: '2px 8px', borderRadius: 999,
  fontSize: '0.7rem', fontWeight: 600,
  border: '1px solid transparent',
  whiteSpace: 'nowrap',
}

const PRIO_STYLES: Record<PrioridadReclamo, React.CSSProperties> = {
  Alta:  { background: '#ffebee', color: '#c62828', borderColor: '#ffcdd2' },
  Media: { background: '#fff3e0', color: '#ef6c00', borderColor: '#ffe0b2' },
  Baja:  { background: '#e8f5e9', color: '#2e7d32', borderColor: '#c8e6c9' },
}

export function BadgePrioridad({ prioridad }: { prioridad: PrioridadReclamo | string | null }) {
  const p = (prioridad as PrioridadReclamo) || 'Media'
  const style = PRIO_STYLES[p] ?? PRIO_STYLES.Media
  return <span style={{ ...badgeBase, ...style }}>{p}</span>
}

const ESTADO_REC_STYLES: Record<string, React.CSSProperties> = {
  'Sin asignar':   { background: '#eceff1', color: '#455a64', borderColor: '#cfd8dc' },
  'En gestión':    { background: '#e3f2fd', color: '#1565c0', borderColor: '#bbdefb' },
  'En espera':     { background: '#fff8e1', color: '#f57f17', borderColor: '#ffecb3' },
  'En auditoría':  { background: '#f3e5f5', color: '#6a1b9a', borderColor: '#e1bee7' },
  'Resuelto':      { background: '#e8f5e9', color: '#2e7d32', borderColor: '#c8e6c9' },
  'Cancelado':     { background: '#fafafa', color: '#616161', borderColor: '#e0e0e0' },
}

export function BadgeEstadoReclamo({ estado }: { estado: EstadoReclamoOT | string | null }) {
  const e = estado || '—'
  const style = ESTADO_REC_STYLES[e] ?? ESTADO_REC_STYLES['Sin asignar']
  return <span style={{ ...badgeBase, ...style }}>{e}</span>
}

const ESTADO_OT_STYLES: Record<string, React.CSSProperties> = {
  'En gestión':  { background: '#e3f2fd', color: '#1565c0', borderColor: '#bbdefb' },
  'En espera':   { background: '#fff8e1', color: '#f57f17', borderColor: '#ffecb3' },
  'Pendiente':   { background: '#ede7f6', color: '#4527a0', borderColor: '#d1c4e9' },
  'Terminada':   { background: '#e8f5e9', color: '#2e7d32', borderColor: '#c8e6c9' },
  'Cancelada':   { background: '#fafafa', color: '#616161', borderColor: '#e0e0e0' },
}

export function BadgeEstadoOT({ estado }: { estado: EstadoOT | string | null }) {
  const e = estado || '—'
  const style = ESTADO_OT_STYLES[e] ?? ESTADO_OT_STYLES['En gestión']
  return <span style={{ ...badgeBase, ...style }}>{e}</span>
}

// ── SLA formateado ───────────────────────────────────────────────────

export function SLACell({ sla_vencimiento, sla_dias }: {
  sla_vencimiento: string | null
  sla_dias: number | null
}): ReactNode {
  if (!sla_vencimiento) {
    return (
      <span style={{ fontSize: '0.68rem', color: 'var(--fg-3)' }}>
        {sla_dias != null ? `${sla_dias}d (sin fecha)` : '—'}
      </span>
    )
  }
  const venc = new Date(sla_vencimiento)
  const now = new Date()
  const ms = venc.getTime() - now.getTime()
  const minutes = Math.floor(Math.abs(ms) / 60000)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  const fmtAbs = (): string => {
    if (days > 0) return `${days}d ${hours % 24}h`
    if (hours > 0) return `${hours}h ${minutes % 60}m`
    return `${minutes}m`
  }

  if (ms < 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1, lineHeight: 1.2, whiteSpace: 'nowrap' }}>
        <span style={{
          color: 'white', background: 'var(--color-error)',
          padding: '3px 8px', borderRadius: 6,
          alignSelf: 'flex-start', fontSize: '0.78rem', fontWeight: 600,
        }}>Vencido hace {fmtAbs()}</span>
      </div>
    )
  }

  let color = '#2e7d32'
  if (hours < 24) color = '#ef6c00'
  if (hours < 6) color = 'var(--color-error)'
  const fecha = venc.toLocaleString('es-AR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 1, lineHeight: 1.2, whiteSpace: 'nowrap' }}>
      <span style={{ fontSize: '0.84rem', fontWeight: 600, color }}>{fmtAbs()}</span>
      <span style={{ fontSize: '0.68rem', color: 'var(--fg-3)' }}>vence {fecha}</span>
    </div>
  )
}

// ── Helpers de texto ─────────────────────────────────────────────────

export function nombreCiudadano(apellido: string | null, nombre: string | null): string {
  const a = apellido?.trim() || ''
  const n = nombre?.trim() || ''
  if (!a && !n) return '—'
  if (!a) return n
  if (!n) return a
  return `${a}, ${n}`
}

export function nombreAgente(apellido: string | null, nombre: string | null): string {
  return nombreCiudadano(apellido, nombre)
}
